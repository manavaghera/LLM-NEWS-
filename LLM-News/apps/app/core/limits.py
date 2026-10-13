"""Protects the AI bill: a per-visitor rate limit on AI endpoints and a daily cap on all AI calls.

AI_RATE_LIMIT          AI requests per visitor per minute (default 20)
AI_VISITOR_DAILY_LIMIT chat questions and other uncached AI requests per visitor per day (default 50), so one
                       visitor can't use up everyone's AI_DAILY_CALL_LIMIT; 0 disables it
AI_DAILY_CALL_LIMIT    AI calls per day across all visitors (default 500); 0 disables the cap
TRUST_PROXY_HEADERS  "true" behind the bundled nginx, so visitors are told apart by X-Forwarded-For

Production counters are stored in the operational database, so restarts and backend
replicas cannot reset or bypass them.
"""
import hashlib
import math
import os
import threading
import time
from collections import deque
from datetime import date
from typing import Deque, Dict

from fastapi import Request

from . import config  # noqa: F401  (loads .env before the limits below are read)
from .database import connect


def wait_text(seconds: int) -> str:
    """45 -> "45 seconds", 600 -> "10 minutes", 32400 -> "9 hours" """
    if seconds < 120:
        return f"{seconds} seconds"
    if seconds < 2 * 3600:
        return f"{math.ceil(seconds / 60)} minutes"
    return f"{math.ceil(seconds / 3600)} hours"


class RateLimited(Exception):
    def __init__(self, retry_after: int, reason: str = "Too many requests."):
        super().__init__(f"{reason} Try again in {wait_text(retry_after)}.")
        self.retry_after = retry_after


class BudgetExceeded(Exception):
    def __init__(self, limit: int):
        super().__init__(f"The daily AI limit ({limit} requests) has been reached. It resets at midnight.")


class RateLimiter:
    """Sliding-window limit per key (e.g. per visitor IP)."""

    def __init__(self, limit: int, window_seconds: float = 60, reason: str = "Too many requests.",
                 *, scope: str = "", persistent: bool = False):
        self.limit = limit
        self.window = window_seconds
        self.reason = reason
        self.scope = scope
        self.persistent = persistent
        if persistent and not scope:
            raise ValueError("Persistent rate limits require a stable scope")
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        if self.limit <= 0:
            return
        if self.persistent:
            self._check_database(key)
            return
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                raise RateLimited(max(1, math.ceil(self.window - (now - hits[0]))), self.reason)
            hits.append(now)
            if len(self._hits) > 10_000:  # forget idle visitors
                for stale in [k for k, v in self._hits.items() if not v]:
                    del self._hits[stale]

    def _check_database(self, key: str) -> None:
        now_ms = int(time.time() * 1000)
        expires_at_ms = now_ms + max(1, math.ceil(self.window * 1000))
        key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
        with connect("limits") as database:
            database.write_lock(f"rate-limit:{self.scope}:{key_hash}")
            database.execute("DELETE FROM rate_limit_hits WHERE expires_at_ms <= ?", (now_ms,))
            row = database.execute(
                "SELECT COUNT(*) AS count, MIN(expires_at_ms) AS retry_at "
                "FROM rate_limit_hits WHERE scope=? AND key_hash=? AND expires_at_ms>?",
                (self.scope, key_hash, now_ms),
            ).fetchone()
            if int(row["count"]) >= self.limit:
                retry_after = max(1, math.ceil((int(row["retry_at"]) - now_ms) / 1000))
                raise RateLimited(retry_after, self.reason)
            database.execute(
                "INSERT INTO rate_limit_hits(scope,key_hash,hit_at_ms,expires_at_ms) VALUES(?,?,?,?)",
                (self.scope, key_hash, now_ms, expires_at_ms),
            )


class DailyBudget:
    """Counts AI calls per calendar day and refuses calls past the limit."""

    def __init__(self, limit: int, *, scope: str = "", persistent: bool = False):
        self.limit = limit
        self.scope = scope
        self.persistent = persistent
        if persistent and not scope:
            raise ValueError("Persistent daily budgets require a stable scope")
        self._day = date.today()
        self.used = 0
        self._lock = threading.Lock()

    def consume(self, calls: int = 1) -> None:
        if self.limit <= 0:
            return
        if self.persistent:
            self._consume_database(calls)
            return
        with self._lock:
            if date.today() != self._day:
                self._day, self.used = date.today(), 0
            if self.used + calls > self.limit:
                raise BudgetExceeded(self.limit)
            self.used += calls

    def _consume_database(self, calls: int) -> None:
        day = date.today().isoformat()
        with connect("limits") as database:
            database.write_lock(f"daily-budget:{self.scope}:{day}")
            row = database.execute(
                "SELECT used FROM daily_budgets WHERE scope=? AND day=?", (self.scope, day)
            ).fetchone()
            used = int(row["used"]) if row else 0
            if used + calls > self.limit:
                raise BudgetExceeded(self.limit)
            database.execute(
                "INSERT INTO daily_budgets(scope,day,used) VALUES(?,?,?) "
                "ON CONFLICT(scope,day) DO UPDATE SET used=excluded.used",
                (self.scope, day, used + calls),
            )
            self.used = used + calls


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


ai_rate_limiter = RateLimiter(
    _int_env("AI_RATE_LIMIT", 20), scope="ai-minute", persistent=True)
_visitor_daily = _int_env("AI_VISITOR_DAILY_LIMIT", 50)
ai_visitor_daily_limiter = RateLimiter(
    _visitor_daily, 24 * 3600, f"You've reached today's limit of {_visitor_daily} AI questions.",
    scope="ai-visitor-day", persistent=True)
ai_budget = DailyBudget(_int_env("AI_DAILY_CALL_LIMIT", 500), scope="ai-global-day", persistent=True)


def client_ip(request: Request) -> str:
    """The visitor's address. Each of our proxies appends the address it saw to X-Forwarded-For, so with
    PROXY_COUNT proxies in front (1: nginx; 2: Caddy then nginx) the visitor is that many entries from the
    end. Anything earlier was sent by the visitor and can't be trusted."""
    if os.getenv("TRUST_PROXY_HEADERS", "").lower() == "true":
        entries = [e.strip() for e in request.headers.get("x-forwarded-for", "").split(",") if e.strip()]
        try:
            hops = max(1, int(os.getenv("PROXY_COUNT", "1")))
        except ValueError:
            hops = 1
        if len(entries) >= hops:
            return entries[-hops]
    return request.client.host if request.client else "unknown"


def limit_ai_requests(request: Request) -> None:
    """FastAPI dependency for endpoints that call an AI model."""
    ai_rate_limiter.check(client_ip(request))


def limit_uncached_ai_requests(request: Request) -> None:
    """For endpoints that call the AI on every request (chat, free-text translation, category digests):
    also a daily allowance per visitor. Cached results (article translations, the daily digest) cost
    at most one call per article and language, so they only get the per-minute limit."""
    visitor = client_ip(request)
    ai_rate_limiter.check(visitor)
    ai_visitor_daily_limiter.check(visitor)

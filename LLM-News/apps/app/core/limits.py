"""Protects the AI bill: a per-visitor rate limit on AI endpoints and a daily cap on all AI calls.

AI_RATE_LIMIT          AI requests per visitor per minute (default 20)
AI_VISITOR_DAILY_LIMIT chat questions and other uncached AI requests per visitor per day (default 50), so one
                       visitor can't use up everyone's AI_DAILY_CALL_LIMIT; 0 disables it
AI_DAILY_CALL_LIMIT    AI calls per day across all visitors (default 500); 0 disables the cap
TRUST_PROXY_HEADERS  "true" behind the bundled nginx, so visitors are told apart by X-Forwarded-For

Counts live in memory, so they reset when the backend restarts.
"""
import math
import os
import threading
import time
from collections import deque
from datetime import date
from typing import Deque, Dict

from fastapi import Request

from . import config  # noqa: F401  (loads .env before the limits below are read)


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

    def __init__(self, limit: int, window_seconds: float = 60, reason: str = "Too many requests."):
        self.limit = limit
        self.window = window_seconds
        self.reason = reason
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        if self.limit <= 0:
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


class DailyBudget:
    """Counts AI calls per calendar day and refuses calls past the limit."""

    def __init__(self, limit: int):
        self.limit = limit
        self._day = date.today()
        self.used = 0
        self._lock = threading.Lock()

    def consume(self, calls: int = 1) -> None:
        if self.limit <= 0:
            return
        with self._lock:
            if date.today() != self._day:
                self._day, self.used = date.today(), 0
            if self.used + calls > self.limit:
                raise BudgetExceeded(self.limit)
            self.used += calls


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


ai_rate_limiter = RateLimiter(_int_env("AI_RATE_LIMIT", 20))
_visitor_daily = _int_env("AI_VISITOR_DAILY_LIMIT", 50)
ai_visitor_daily_limiter = RateLimiter(
    _visitor_daily, 24 * 3600, f"You've reached today's limit of {_visitor_daily} AI questions.")
ai_budget = DailyBudget(_int_env("AI_DAILY_CALL_LIMIT", 500))


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

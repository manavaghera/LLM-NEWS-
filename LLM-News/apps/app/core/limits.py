"""Protects the AI bill: a per-visitor rate limit on AI endpoints and a daily cap on all AI calls.

AI_RATE_LIMIT        AI requests per visitor per minute (default 20)
AI_DAILY_CALL_LIMIT  AI calls per day across all visitors (default 500); 0 disables the cap
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


class RateLimited(Exception):
    def __init__(self, retry_after: int):
        super().__init__(f"Too many requests. Try again in {retry_after} seconds.")
        self.retry_after = retry_after


class BudgetExceeded(Exception):
    def __init__(self, limit: int):
        super().__init__(f"The daily AI limit ({limit} requests) has been reached. It resets at midnight.")


class RateLimiter:
    """Sliding-window limit per key (e.g. per visitor IP)."""

    def __init__(self, limit: int, window_seconds: float = 60):
        self.limit = limit
        self.window = window_seconds
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
                raise RateLimited(max(1, math.ceil(self.window - (now - hits[0]))))
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
ai_budget = DailyBudget(_int_env("AI_DAILY_CALL_LIMIT", 500))


def client_ip(request: Request) -> str:
    """The visitor's address. Behind our nginx the last X-Forwarded-For entry is the one nginx added."""
    if os.getenv("TRUST_PROXY_HEADERS", "").lower() == "true":
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def limit_ai_requests(request: Request) -> None:
    """FastAPI dependency for endpoints that call an AI model."""
    ai_rate_limiter.check(client_ip(request))

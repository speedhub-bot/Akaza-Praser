"""Per-engine token-bucket rate limiter."""

from __future__ import annotations

import asyncio
import random
import time
from threading import Lock


class TokenBucket:
    """Simple token bucket (not async — callers ``await`` the sleep)."""

    def __init__(self, tokens_per_sec: float = 1.0, burst: int = 3) -> None:
        self._rate = tokens_per_sec
        self._burst = burst
        self._tokens = float(burst)
        self._last = time.monotonic()
        self._lock = Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        self._last = now

    def wait_time(self) -> float:
        """Return seconds to wait before a token is available."""
        with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return 0.0
            deficit = 1.0 - self._tokens
            return deficit / self._rate

    async def acquire(self) -> None:
        w = self.wait_time()
        if w > 0:
            await asyncio.sleep(w + random.uniform(0, 0.2))


class EngineRateLimiter:
    """Creates and manages per-engine buckets."""

    def __init__(self, default_rate: float = 0.8, burst: int = 3) -> None:
        self._lock = Lock()
        self._buckets: dict[str, TokenBucket] = {}
        self._default_rate = default_rate
        self._burst = burst

    def get(self, engine: str) -> TokenBucket:
        with self._lock:
            if engine not in self._buckets:
                self._buckets[engine] = TokenBucket(
                    self._default_rate, self._burst
                )
            return self._buckets[engine]

    async def acquire(self, engine: str) -> None:
        await self.get(engine).acquire()

    def set_cooldown(self, engine: str, seconds: float) -> None:
        """Force a cooldown by draining the bucket below zero."""
        bucket = self.get(engine)
        with bucket._lock:
            bucket._tokens = -(seconds * bucket._rate)

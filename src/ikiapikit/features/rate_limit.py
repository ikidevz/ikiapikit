import httpx
import time
import asyncio
import logging

from typing import Any, Optional

logger = logging.getLogger("iki-apikit")


class RateLimitState:
    """
    Tracks X-RateLimit-* headers from API responses and enforces
    proactive client-side throttling.

    Supported header families:
      • Standard / GitHub: X-RateLimit-Remaining / X-RateLimit-Reset
      • HubSpot: X-HubSpot-RateLimit-Daily-Remaining
      • Stripe:  X-RateLimit-Remaining-second
    """

    def __init__(self, min_remaining: int = 5, safety_buffer: float = 0.1):
        self.min_remaining = min_remaining
        self.safety_buffer = safety_buffer
        self._remaining: Optional[int] = None
        self._reset_at: Optional[float] = None
        self._limit: Optional[int] = None
        self._headroom: dict[str, Any] = {}

    def ingest(self, headers: httpx.Headers) -> None:
        """Extract rate-limit metadata from a response's headers."""
        remaining = headers.get(
            "X-RateLimit-Remaining") or headers.get("x-ratelimit-remaining")
        limit = headers.get(
            "X-RateLimit-Limit") or headers.get("x-ratelimit-limit")
        reset = headers.get(
            "X-RateLimit-Reset") or headers.get("x-ratelimit-reset")

        if remaining is None:
            remaining = headers.get("X-HubSpot-RateLimit-Daily-Remaining")
        if remaining is None:
            remaining = headers.get("X-RateLimit-Remaining-second")

        if remaining is not None:
            try:
                self._remaining = int(remaining)
            except ValueError:
                pass
        if limit is not None:
            try:
                self._limit = int(limit)
            except ValueError:
                pass
        if reset is not None:
            try:
                self._reset_at = float(reset)
            except ValueError:
                pass

        self._headroom = {
            "remaining": self._remaining,
            "limit": self._limit,
            "reset_at": self._reset_at,
            "used_pct": (
                round((1 - self._remaining / self._limit) * 100, 1)
                if self._remaining is not None and self._limit and self._limit > 0
                else None
            ),
        }

    def should_throttle(self) -> bool:
        if self._remaining is None:
            return False
        return self._remaining <= self.min_remaining

    def sleep_duration(self) -> float:
        if self._reset_at is not None:
            return max(0.0, self._reset_at - time.time()) + self.safety_buffer
        return 5.0

    def throttle_sync(self) -> None:
        if self.should_throttle():
            duration = self.sleep_duration()
            logger.warning("Rate limit headroom low (remaining=%s). Sleeping %.1fs.",
                           self._remaining, duration)
            time.sleep(duration)

    async def throttle_async(self) -> None:
        if self.should_throttle():
            duration = self.sleep_duration()
            logger.warning("Rate limit headroom low (remaining=%s). Sleeping %.1fs.",
                           self._remaining, duration)
            await asyncio.sleep(duration)

    @property
    def headroom(self) -> dict:
        return dict(self._headroom)

    def __repr__(self) -> str:
        return (
            f"RateLimitState(remaining={self._remaining}, "
            f"limit={self._limit}, reset_at={self._reset_at})"
        )

import httpx
from abc import ABC, abstractmethod


class AuthStrategy(ABC):
    """Abstract base for all authentication strategies."""

    @abstractmethod
    def apply_sync(self, request: httpx.Request) -> httpx.Request:
        """Mutate the request in place for sync usage."""

    async def apply_async(self, request: httpx.Request) -> httpx.Request:
        """Async variant — default delegates to sync."""
        return self.apply_sync(request)

    def refresh_sync(self) -> None:
        """Refresh credentials if needed (e.g. OAuth2 token expiry)."""

    async def refresh_async(self) -> None:
        """Async refresh."""
        self.refresh_sync()

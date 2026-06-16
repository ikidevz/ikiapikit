import httpx
import time
from typing import Any, Optional

from .base import AuthStrategy


class OAuth2ClientCredentials(AuthStrategy):
    """OAuth2 Client Credentials flow with automatic token refresh."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_url: str,
        scopes: Optional[list[str]] = None,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._scopes = scopes or []
        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0

    def _is_expired(self) -> bool:
        return time.monotonic() >= self._expires_at - 30  # 30s buffer

    def _fetch_token_sync(self) -> None:
        data: dict[str, Any] = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        if self._scopes:
            data["scope"] = " ".join(self._scopes)
        with httpx.Client() as c:
            resp = c.post(self._token_url, data=data, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
        self._access_token = payload["access_token"]
        self._expires_at = time.monotonic() + payload.get("expires_in", 3600)

    async def _fetch_token_async(self) -> None:
        data: dict[str, Any] = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        if self._scopes:
            data["scope"] = " ".join(self._scopes)
        async with httpx.AsyncClient() as c:
            resp = await c.post(self._token_url, data=data, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
        self._access_token = payload["access_token"]
        self._expires_at = time.monotonic() + payload.get("expires_in", 3600)

    def refresh_sync(self) -> None:
        self._fetch_token_sync()

    async def refresh_async(self) -> None:
        await self._fetch_token_async()

    def apply_sync(self, request: httpx.Request) -> httpx.Request:
        if self._is_expired():
            self._fetch_token_sync()
        request.headers["Authorization"] = f"Bearer {self._access_token}"
        return request

    async def apply_async(self, request: httpx.Request) -> httpx.Request:
        if self._is_expired():
            await self._fetch_token_async()
        request.headers["Authorization"] = f"Bearer {self._access_token}"
        return request

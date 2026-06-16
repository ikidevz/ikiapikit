import httpx
import time
import base64

from typing import Any, Optional
from .base import AuthStrategy


class NoAuth(AuthStrategy):
    """No-op auth — passes request through unchanged."""

    def apply_sync(self, request: httpx.Request) -> httpx.Request:
        return request


class BearerAuth(AuthStrategy):
    """Injects an Authorization: Bearer <token> header."""

    def __init__(self, token: str):
        self._token = token

    def apply_sync(self, request: httpx.Request) -> httpx.Request:
        request.headers["Authorization"] = f"Bearer {self._token}"
        return request


class ApiKeyAuth(AuthStrategy):
    """Injects an API key via a request header or query parameter."""

    def __init__(
        self,
        api_key: str,
        header: str = "X-API-Key",
        query_param: Optional[str] = None,
    ):
        self._key = api_key
        self._header = header
        self._query_param = query_param

    def apply_sync(self, request: httpx.Request) -> httpx.Request:
        if self._query_param:
            existing = dict(request.url.params)
            existing[self._query_param] = self._key
            new_url = request.url.copy_with(params=existing)
            request = httpx.Request(
                method=request.method,
                url=new_url,
                headers=request.headers,
                content=request.content,
            )
        else:
            request.headers[self._header] = self._key
        return request


class BasicAuth(AuthStrategy):
    """Injects HTTP Basic Authentication (Base64-encoded credentials)."""

    def __init__(self, username: str, password: str):
        credentials = base64.b64encode(
            f"{username}:{password}".encode()).decode()
        self._header = f"Basic {credentials}"

    def apply_sync(self, request: httpx.Request) -> httpx.Request:
        request.headers["Authorization"] = self._header
        return request

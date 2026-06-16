"""
tests/http/test_rest_client.py  —  §6  RestClient (sync + async).
"""

from __future__ import annotations

import pytest
import httpx
import respx

from ikiapikit import (
    AuthError,
    PaginationConfig,
    RetryConfig,
    RestClient,
    OffsetPaginator,
)
from .conftest import make_config, BASE_URL


class TestRestClientSync:
    def test_request_sync_raises_auth_error_on_401(self):
        cfg = make_config()
        client = RestClient(cfg)
        with respx.mock(base_url=BASE_URL) as mock:          # ← capture as `mock`
            mock.get("/secret").mock(return_value=httpx.Response(401))
            with pytest.raises(AuthError):
                client.request_sync("GET", "/secret")

    def test_request_sync_retries_on_500(self):
        cfg = make_config()
        client = RestClient(cfg)
        call_count = 0

        def handler(request):
            nonlocal call_count
            call_count += 1
            return httpx.Response(500) if call_count < 2 else httpx.Response(200, json={"ok": True})

        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/flaky").mock(side_effect=handler)
            result = client.request_sync("GET", "/flaky")
        assert result == {"ok": True}
        assert call_count == 2

    def test_get_all_pages_sync_single_page(self):
        cfg = make_config(strategy="none")
        client = RestClient(cfg)
        data = [{"id": 1}, {"id": 2}]
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/items").mock(return_value=httpx.Response(200, json=data))
            records = client.get_all_pages_sync("/items")
        assert records == data

    def test_get_all_pages_sync_offset_pagination(self):
        cfg = make_config(strategy="offset", page_size=2)
        client = RestClient(cfg)
        page1 = [{"id": 0}, {"id": 1}]
        page2 = [{"id": 2}]
        call_count = [0]

        def handler(request):
            call_count[0] += 1
            return httpx.Response(200, json=page1 if call_count[0] == 1 else page2)

        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/items").mock(side_effect=handler)
            records = client.get_all_pages_sync(
                "/items", paginator=OffsetPaginator(cfg.pagination))
        assert len(records) == 3


class TestRestClientAsync:
    @pytest.mark.asyncio
    async def test_request_async_returns_json(self):
        cfg = make_config()
        client = RestClient(cfg)
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get(
                "/data").mock(return_value=httpx.Response(200, json={"ok": True}))
            result = await client.request_async("GET", "/data")
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_request_async_raises_auth_error_on_401(self):
        cfg = make_config()
        client = RestClient(cfg)
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/auth").mock(return_value=httpx.Response(401))
            with pytest.raises(AuthError):
                await client.request_async("GET", "/auth")

    @pytest.mark.asyncio
    async def test_astream_yields_records(self):
        cfg = make_config(strategy="none")
        client = RestClient(cfg)
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/stream").mock(return_value=httpx.Response(200, json=data))
            received = []
            async for rec in client.astream("/stream"):
                received.append(rec)
        assert received == data

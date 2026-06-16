"""
tests/test_rate_limit_inspector.py  —  §13 & §14  RateLimitState + ApiInspector.
"""

from __future__ import annotations

import time

import httpx
import pytest
import respx

from kit import (
    Apikit,
    RateLimitState,
    ApiInspector,
    InspectorResult,
)
from tests.conftest import make_config, BASE_URL


# ============================================================================
# §13  RATE LIMIT STATE
# ============================================================================


class TestRateLimitState:
    def _make_headers(self, remaining: int, limit: int, reset: float) -> httpx.Headers:
        return httpx.Headers({
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Reset": str(reset),
        })

    def test_ingest_standard_headers(self):
        rl = RateLimitState()
        rl.ingest(self._make_headers(remaining=100, limit=5000, reset=time.time() + 3600))
        assert rl._remaining == 100
        assert rl._limit == 5000

    def test_should_throttle_when_low(self):
        rl = RateLimitState(min_remaining=10)
        rl.ingest(self._make_headers(remaining=5, limit=5000, reset=time.time() + 60))
        assert rl.should_throttle() is True

    def test_should_not_throttle_when_sufficient(self):
        rl = RateLimitState(min_remaining=10)
        rl.ingest(self._make_headers(remaining=100, limit=5000, reset=time.time() + 60))
        assert rl.should_throttle() is False

    def test_should_not_throttle_when_no_headers(self):
        rl = RateLimitState()
        assert rl.should_throttle() is False

    def test_sleep_duration_uses_reset_header(self):
        rl = RateLimitState()
        reset_at = time.time() + 30
        rl._reset_at = reset_at
        duration = rl.sleep_duration()
        assert 28 < duration < 32

    def test_sleep_duration_fallback_when_no_reset(self):
        rl = RateLimitState()
        assert rl.sleep_duration() == 5.0

    def test_headroom_property(self):
        rl = RateLimitState()
        rl.ingest(self._make_headers(remaining=50, limit=100, reset=time.time() + 60))
        h = rl.headroom
        assert h["remaining"] == 50
        assert h["limit"] == 100
        assert h["used_pct"] == 50.0

    def test_repr(self):
        rl = RateLimitState()
        assert "RateLimitState" in repr(rl)

    def test_ingest_hubspot_header(self):
        rl = RateLimitState()
        headers = httpx.Headers({"X-HubSpot-RateLimit-Daily-Remaining": "9800"})
        rl.ingest(headers)
        assert rl._remaining == 9800

    def test_ingest_stripe_header(self):
        rl = RateLimitState()
        headers = httpx.Headers({"X-RateLimit-Remaining-second": "98"})
        rl.ingest(headers)
        assert rl._remaining == 98


# ============================================================================
# §14  INSPECTOR
# ============================================================================


class TestApiInspector:
    def test_inspect_sync_returns_result(self):
        cfg = make_config()
        inspector = ApiInspector(cfg)
        body = {"items": [{"id": 1}], "next_cursor": "abc"}
        with respx.mock(base_url=BASE_URL):
            respx.get(f"{BASE_URL}/probe").mock(
                return_value=httpx.Response(
                    200, json=body,
                    headers={"Content-Type": "application/json"},
                )
            )
            result = inspector.inspect_sync("/probe")
        assert isinstance(result, InspectorResult)
        assert result.status_code == 200
        assert result.latency_ms >= 0
        assert result.detected_pagination == "cursor"
        assert result.record_count == 1

    @pytest.mark.asyncio
    async def test_inspect_async_returns_result(self):
        cfg = make_config()
        inspector = ApiInspector(cfg)
        body = [{"id": 1}, {"id": 2}]
        with respx.mock(base_url=BASE_URL):
            respx.get(f"{BASE_URL}/async-probe").mock(
                return_value=httpx.Response(200, json=body))
            result = await inspector.inspect_async("/async-probe")
        assert result.record_count == 2

    def test_inspect_sync_dry_run(self):
        cfg = make_config()
        inspector = ApiInspector(cfg)
        result = inspector.inspect_sync("/dryprobe", dry_run=True)
        assert result.dry_run is True
        assert result.status_code == 0

    def test_detect_pagination_link_header(self):
        cfg = make_config()
        inspector = ApiInspector(cfg)
        headers = {"Link": '<https://api.example.com/p2>; rel="next"'}
        assert inspector._detect_pagination({}, headers) == "link"

    def test_detect_pagination_cursor_body(self):
        cfg = make_config()
        inspector = ApiInspector(cfg)
        body = {"results": [], "next_cursor": "tok"}
        assert inspector._detect_pagination(body, {}) == "cursor"

    def test_detect_pagination_offset_body(self):
        cfg = make_config()
        inspector = ApiInspector(cfg)
        body = {"items": [], "total": 500, "offset": 0}
        assert inspector._detect_pagination(body, {}) == "offset"

    def test_detect_pagination_none(self):
        cfg = make_config()
        inspector = ApiInspector(cfg)
        assert inspector._detect_pagination({"data": []}, {}) is None

    def test_inspector_result_suggested_config(self):
        cfg = make_config()
        inspector = ApiInspector(cfg)
        body = {"items": [{"id": 1}]}
        with respx.mock(base_url=BASE_URL):
            respx.get(f"{BASE_URL}/config-probe").mock(
                return_value=httpx.Response(200, json=body))
            result = inspector.inspect_sync("/config-probe")
        config_str = result.suggested_config()
        assert "ApiConfig" in config_str
        assert "base_url" in config_str

    def test_inspector_result_schema_sample(self):
        cfg = make_config()
        inspector = ApiInspector(cfg)
        body = [{"id": 1, "name": "Alice", "score": 9.5}]
        with respx.mock(base_url=BASE_URL):
            respx.get(f"{BASE_URL}/schema-probe").mock(
                return_value=httpx.Response(200, json=body))
            result = inspector.inspect_sync("/schema-probe")
        schema = result.schema_sample()
        assert "id" in schema
        assert schema["id"] == "int"


class TestApikitInspect:
    def test_inspect_via_facade(self, client: Apikit):
        body = [{"id": 1}]
        with respx.mock(base_url=BASE_URL):
            respx.get(f"{BASE_URL}/probe").mock(return_value=httpx.Response(200, json=body))
            result = client.inspect("/probe")
        assert isinstance(result, InspectorResult)

    @pytest.mark.asyncio
    async def test_ainspect_via_facade(self, client: Apikit):
        body = [{"id": 2}]
        with respx.mock(base_url=BASE_URL):
            respx.get(f"{BASE_URL}/async-probe").mock(
                return_value=httpx.Response(200, json=body))
            result = await client.ainspect("/async-probe")
        assert isinstance(result, InspectorResult)

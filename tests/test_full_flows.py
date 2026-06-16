"""
tests/integration/test_full_flows.py  —  End-to-end Apikit flows (sync, async, connectors).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
import respx

from kit import (
    Apikit,
    ApiConfig,
    AuthConfig,
    RetryConfig,
    PaginationConfig,
    ConfigManager,
)
from tests.conftest import make_config, BASE_URL


# ============================================================================
# Sync flows
# ============================================================================


class TestIntegrationSyncFlow:
    def test_fetch_polars_with_offset_pagination(self):
        pl = pytest.importorskip("polars")
        cfg = ApiConfig(
            base_url=BASE_URL,
            auth=AuthConfig(type="bearer", token="tok"),
            pagination=PaginationConfig(strategy="offset", page_size=2, data_path=None),
            retry=RetryConfig(max_attempts=1, min_wait=0.0, max_wait=0.0),
        )
        client = Apikit.from_config(cfg)

        page1 = [{"id": 0}, {"id": 1}]
        page2 = [{"id": 2}]
        call_count = [0]

        def handler(request):
            call_count[0] += 1
            return httpx.Response(200, json=page1 if call_count[0] == 1 else page2)

        with respx.mock(base_url=BASE_URL):
            respx.get(f"{BASE_URL}/items").mock(side_effect=handler)
            df = client.fetch_polars("/items", paginate=True, show_progress=False)
        assert isinstance(df, pl.DataFrame)
        assert len(df) == 3

    def test_fetch_records_with_nested_data_path(self):
        cfg = make_config()
        client = Apikit.from_config(cfg)
        response = {"data": {"items": [{"id": 1}, {"id": 2}]}}
        with respx.mock(base_url=BASE_URL):
            respx.get(f"{BASE_URL}/wrapped").mock(return_value=httpx.Response(200, json=response))
            records = client.fetch_records("/wrapped", data_path="data.items", show_progress=False)
        assert len(records) == 2

    def test_post_then_delete_workflow(self):
        cfg = make_config()
        client = Apikit.from_config(cfg)
        with respx.mock(base_url=BASE_URL):
            respx.post(f"{BASE_URL}/items").mock(
                return_value=httpx.Response(201, json={"id": "new_1"}))
            respx.delete(f"{BASE_URL}/items/new_1").mock(
                return_value=httpx.Response(200, json={"deleted": True}))
            created = client.post("/items", body={"name": "test"})
            deleted = client.delete(f"/items/{created['id']}")
        assert deleted["deleted"] is True


# ============================================================================
# Async flows
# ============================================================================


class TestIntegrationAsyncFlow:
    @pytest.mark.asyncio
    async def test_concurrent_fetches(self):
        pl = pytest.importorskip("polars")
        cfg = make_config()
        client = Apikit.from_config(cfg)

        with respx.mock(base_url=BASE_URL):
            respx.get(f"{BASE_URL}/users").mock(
                return_value=httpx.Response(200, json=[{"id": 1}]))
            respx.get(f"{BASE_URL}/orders").mock(
                return_value=httpx.Response(200, json=[{"id": 2}]))

            users, orders = await asyncio.gather(
                client.afetch_polars("/users", show_progress=False),
                client.afetch_polars("/orders", show_progress=False),
            )
        assert len(users) == 1
        assert len(orders) == 1

    @pytest.mark.asyncio
    async def test_stream_then_collect(self):
        cfg = make_config()
        client = Apikit.from_config(cfg)
        data = [{"id": i} for i in range(5)]
        with respx.mock(base_url=BASE_URL):
            respx.get(f"{BASE_URL}/stream").mock(return_value=httpx.Response(200, json=data))
            collected = [rec async for rec in client.astream("/stream", paginate=False)]
        assert len(collected) == 5
        assert [r["id"] for r in collected] == list(range(5))


# ============================================================================
# Flattening + writers
# ============================================================================


class TestIntegrationFlatteningAndWriters:
    def test_fetch_flatten_write_csv(self, tmp_dir: Path):
        pytest.importorskip("polars")
        cfg = make_config()
        client = Apikit.from_config(cfg)
        data = [{"id": 1, "meta": {"score": 9.5, "tag": "A"}}]
        with respx.mock(base_url=BASE_URL):
            respx.get(f"{BASE_URL}/data").mock(return_value=httpx.Response(200, json=data))
            path = client.fetch_to_file("/data", format="csv", file_path=tmp_dir / "out.csv")
        assert path.exists()
        content = path.read_text()
        assert "meta__score" in content
        assert "meta__tag" in content

    def test_fetch_flatten_write_parquet(self, tmp_dir: Path):
        pytest.importorskip("polars")
        cfg = make_config()
        client = Apikit.from_config(cfg)
        data = [{"id": i, "nested": {"val": i * 2}} for i in range(3)]
        with respx.mock(base_url=BASE_URL):
            respx.get(f"{BASE_URL}/data").mock(return_value=httpx.Response(200, json=data))
            path = client.fetch_to_file(
                "/data", format="parquet", file_path=tmp_dir / "out.parquet")
        assert path.exists()
        assert path.stat().st_size > 0


# ============================================================================
# Connectors + config round-trip
# ============================================================================


class TestIntegrationConnectorAndConfig:
    def test_from_name_github_builds_correct_config(self):
        client = Apikit.from_name("github", token="ghp_test")
        assert "github.com" in client.config.base_url
        assert client.config.auth.type == "bearer"
        assert client.config.pagination.strategy == "link"

    def test_from_name_stripe_builds_cursor_pagination(self):
        client = Apikit.from_name("stripe", token="sk_test")
        assert client.config.pagination.strategy == "cursor"

    def test_config_manager_round_trip(self, tmp_dir: Path):
        mgr = ConfigManager(config_path=tmp_dir / "config.toml")
        mgr.add_connector(
            "integration_api",
            base_url="https://integration.example.com",
            auth_type="bearer",
            token="int_tok",
            store_secret_in_keyring=False,
        )
        cfg = mgr.get_api_config("integration_api")
        assert cfg.base_url == "https://integration.example.com"
        client = Apikit.from_config(cfg)
        assert "integration.example.com" in client.config.base_url

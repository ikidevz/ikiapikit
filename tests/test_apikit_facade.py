"""
tests/test_apikit_facade.py  —  §12  Apikit facade (constructors, fetch, mutations, file output, GraphQL, streaming).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx

from ikiapikit import (
    Apikit,
    ApiConfig,
    ConnectorNotFoundError,
    DryRunResult,
)
from .conftest import BASE_URL


# ============================================================================
# Constructors
# ============================================================================


class TestApikitConstructors:
    def test_from_config(self, config: ApiConfig):
        client = Apikit.from_config(config)
        assert client.config.base_url == BASE_URL

    def test_from_name_builtin(self):
        client = Apikit.from_name("github", token="ghp_test")
        assert "github" in client.config.base_url

    def test_from_name_unknown_raises(self, tmp_dir: Path):
        with patch("kit.ConfigManager") as mock_mgr:
            mock_mgr.return_value.get_api_config.side_effect = ConnectorNotFoundError(
                "nope")
            with pytest.raises(ConnectorNotFoundError):
                Apikit.from_name("totally_unknown_api_xyz")

    def test_repr(self, client: Apikit):
        r = repr(client)
        assert "Apikit(" in r
        assert BASE_URL in r

    def test_config_property(self, client: Apikit, config: ApiConfig):
        assert client.config.base_url == config.base_url

    def test_inline_constructor(self):
        c = Apikit(
            base_url="https://api.example.com",
            auth="bearer",
            token="tok",
            timeout=60.0,
            max_retries=5,
        )
        assert c.config.timeout == 60.0
        assert c.config.retry.max_attempts == 5


# ============================================================================
# Fetch records
# ============================================================================


class TestApikitFetchRecords:
    def test_fetch_records_sync(self, client: Apikit):
        data = [{"id": 1}, {"id": 2}]
        with respx.mock(base_url=BASE_URL):
            respx.get(
                f"{BASE_URL}/items").mock(return_value=httpx.Response(200, json=data))
            records = client.fetch_records("/items", show_progress=False)
        assert records == data

    def test_fetch_records_dry_run_returns_dry_run_result(self, client: Apikit):
        result = client.fetch_records(
            "/users", dry_run=True, show_progress=False)
        assert isinstance(result, DryRunResult)
        assert result.method == "GET"
        assert "/users" in result.url

    def test_fetch_records_with_params(self, client: Apikit):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/items").mock(return_value=httpx.Response(200, json=[]))
            client.fetch_records(
                "/items", params={"status": "active"}, show_progress=False)
            assert "status=active" in str(mock.calls[0].request.url)

    @pytest.mark.asyncio
    async def test_afetch_records(self, client: Apikit):
        data = [{"id": 10}]
        with respx.mock(base_url=BASE_URL):
            respx.get(f"{BASE_URL}/async-items").mock(
                return_value=httpx.Response(200, json=data))
            records = await client.afetch_records("/async-items", show_progress=False)
        assert records == data


# ============================================================================
# DataFrame methods
# ============================================================================


class TestApikitDataFrameMethods:
    def test_fetch_polars(self, client: Apikit):
        pl = pytest.importorskip("polars")
        data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        with respx.mock(base_url=BASE_URL):
            respx.get(
                f"{BASE_URL}/users").mock(return_value=httpx.Response(200, json=data))
            df = client.fetch_polars("/users", show_progress=False)
        assert isinstance(df, pl.DataFrame)
        assert len(df) == 2

    def test_fetch_pandas(self, client: Apikit):
        pd = pytest.importorskip("pandas")
        data = [{"id": 1}, {"id": 2}]
        with respx.mock(base_url=BASE_URL):
            respx.get(
                f"{BASE_URL}/items").mock(return_value=httpx.Response(200, json=data))
            df = client.fetch_pandas("/items", show_progress=False)
        assert hasattr(df, "columns")
        assert len(df) == 2

    @pytest.mark.asyncio
    async def test_afetch_polars(self, client: Apikit):
        pl = pytest.importorskip("polars")
        data = [{"id": 3}]
        with respx.mock(base_url=BASE_URL):
            respx.get(f"{BASE_URL}/async-data").mock(
                return_value=httpx.Response(200, json=data))
            df = await client.afetch_polars("/async-data", show_progress=False)
        assert isinstance(df, pl.DataFrame)


# ============================================================================
# Mutations
# ============================================================================


class TestApikitMutations:
    def test_post(self, client: Apikit):
        with respx.mock(base_url=BASE_URL):
            respx.post(f"{BASE_URL}/contacts").mock(
                return_value=httpx.Response(201, json={"id": "ct_1"}))
            result = client.post("/contacts", body={"name": "Alice"})
        assert result == {"id": "ct_1"}

    def test_put(self, client: Apikit):
        with respx.mock(base_url=BASE_URL):
            respx.put(f"{BASE_URL}/contacts/ct_1").mock(
                return_value=httpx.Response(200, json={"updated": True}))
            result = client.put(
                "/contacts/ct_1", body={"name": "Alice Updated"})
        assert result["updated"] is True

    def test_delete(self, client: Apikit):
        with respx.mock(base_url=BASE_URL):
            respx.delete(f"{BASE_URL}/contacts/ct_1").mock(
                return_value=httpx.Response(200, json={"deleted": True}))
            result = client.delete("/contacts/ct_1")
        assert result["deleted"] is True


# ============================================================================
# File output
# ============================================================================


class TestApikitFetchToFile:
    def test_fetch_to_file_ndjson(self, client: Apikit, tmp_dir: Path):
        data = [{"id": 1}, {"id": 2}]
        with respx.mock(base_url=BASE_URL):
            respx.get(
                f"{BASE_URL}/data").mock(return_value=httpx.Response(200, json=data))
            path = client.fetch_to_file(
                "/data", format="ndjson",
                file_path=tmp_dir / "out.ndjson",
            )
        assert path.exists()

    def test_fetch_to_file_json(self, client: Apikit, tmp_dir: Path):
        data = [{"id": 1}]
        with respx.mock(base_url=BASE_URL):
            respx.get(
                f"{BASE_URL}/data").mock(return_value=httpx.Response(200, json=data))
            path = client.fetch_to_file(
                "/data", format="json", file_path=tmp_dir / "out.json")
        assert path.exists()
        loaded = json.loads(path.read_bytes())
        assert loaded == data

    @pytest.mark.asyncio
    async def test_afetch_to_file(self, client: Apikit, tmp_dir: Path):
        data = [{"id": 5}]
        with respx.mock(base_url=BASE_URL):
            respx.get(
                f"{BASE_URL}/async-data").mock(return_value=httpx.Response(200, json=data))
            path = await client.afetch_to_file(
                "/async-data", format="json",
                file_path=tmp_dir / "async_out.json",
            )
        assert path.exists()


# ============================================================================
# GraphQL
# ============================================================================


class TestApikitGraphQL:
    def test_graphql_single_query(self, client: Apikit):
        body = {"data": {"me": {"login": "octocat"}}}
        with respx.mock(base_url=BASE_URL):
            respx.post(
                f"{BASE_URL}/graphql").mock(return_value=httpx.Response(200, json=body))
            result = client.graphql("/graphql", "{ me { login } }")
        assert result == {"me": {"login": "octocat"}}

    @pytest.mark.asyncio
    async def test_agraphql(self, client: Apikit):
        body = {"data": {"me": {"login": "async_user"}}}
        with respx.mock(base_url=BASE_URL):
            respx.post(
                f"{BASE_URL}/graphql").mock(return_value=httpx.Response(200, json=body))
            result = await client.agraphql("/graphql", "{ me { login } }")
        assert result == {"me": {"login": "async_user"}}


# ============================================================================
# Streaming
# ============================================================================


class TestApikitAstream:
    @pytest.mark.asyncio
    async def test_astream_yields_all_records(self, client: Apikit):
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        with respx.mock(base_url=BASE_URL):
            respx.get(
                f"{BASE_URL}/events").mock(return_value=httpx.Response(200, json=data))
            collected = []
            async for record in client.astream("/events", paginate=False):
                collected.append(record)
        assert collected == data

    @pytest.mark.asyncio
    async def test_astream_early_exit(self, client: Apikit):
        data = [{"id": i} for i in range(10)]
        with respx.mock(base_url=BASE_URL):
            respx.get(
                f"{BASE_URL}/logs").mock(return_value=httpx.Response(200, json=data))
            collected = []
            async for record in client.astream("/logs", paginate=False):
                collected.append(record)
                if len(collected) == 3:
                    break
        assert len(collected) == 3

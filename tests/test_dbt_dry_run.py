"""
tests/test_dbt_dry_run.py  —  §16 & §17  DbtExporter + DryRunResult.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from ikiapikit import (
    Apikit,
    DbtExporter,
    DryRunResult,
)
from .conftest import make_config, BASE_URL


# ============================================================================
# §16  DBT EXPORTER
# ============================================================================


class TestDbtExporter:
    def test_export_creates_files(self, tmp_dir: Path, records: list[dict]):
        pytest.importorskip("polars")
        exporter = DbtExporter(output_dir=tmp_dir / "dbt")
        paths = exporter.export(records, "test_table",
                                database="raw", schema="public")
        assert "seed" in paths
        assert "sources" in paths
        assert "schema" in paths
        for path in paths.values():
            assert path.exists()

    def test_export_dry_run_returns_empty_paths(self, tmp_dir: Path, records: list[dict]):
        exporter = DbtExporter(output_dir=tmp_dir / "dbt", dry_run=True)
        paths = exporter.export(records, "test_table")
        assert paths == {}

    def test_export_seed_csv_has_correct_rows(self, tmp_dir: Path):
        pytest.importorskip("polars")
        recs = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        exporter = DbtExporter(output_dir=tmp_dir / "dbt")
        paths = exporter.export(recs, "users")
        seed_path = paths["seed"]
        content = seed_path.read_text()
        assert "Alice" in content
        assert "Bob" in content

    def test_infer_columns_from_sample(self, tmp_dir: Path):
        exporter = DbtExporter(output_dir=tmp_dir)
        recs = [{"id": 1, "score": 9.5, "label": "good"}]
        cols = exporter._infer_columns(recs)
        names = [c["name"] for c in cols]
        assert "id" in names
        assert "score" in names
        assert "label" in names

    def test_infer_columns_empty_records(self, tmp_dir: Path):
        exporter = DbtExporter(output_dir=tmp_dir)
        assert exporter._infer_columns([]) == []

    def test_render_sources_yaml_contains_name(self, tmp_dir: Path):
        exporter = DbtExporter(output_dir=tmp_dir)
        cols = [{"name": "id", "dtype": "int", "description": "Primary key"}]
        yaml = exporter._render_sources_yaml(
            "my_table", "raw", "public", "My desc", cols, None, None)
        assert "my_table" in yaml
        assert "raw" in yaml

    def test_render_schema_yaml_contains_columns(self, tmp_dir: Path):
        exporter = DbtExporter(output_dir=tmp_dir)
        cols = [{"name": "id", "dtype": "int", "description": "Primary key"}]
        yaml = exporter._render_schema_yaml(
            "my_model", "A model", cols, None, None)
        assert "my_model" in yaml
        assert "id" in yaml
        assert "int" in yaml

    def test_export_from_client(self, tmp_dir: Path):
        pytest.importorskip("polars")
        cfg = make_config()
        client = Apikit.from_config(cfg)
        data = [{"id": i, "value": i * 10} for i in range(3)]
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/data").mock(
                return_value=httpx.Response(200, json=data))
            exporter = DbtExporter(output_dir=tmp_dir / "dbt")
            paths = exporter.export_from_client(
                client, "/data", "my_data",
                paginate=False, database="raw", schema="api",
            )
        assert "seed" in paths


# ============================================================================
# §17  DRY RUN RESULT
# ============================================================================


class TestDryRunResult:
    def _make_result(self, **kwargs) -> DryRunResult:
        defaults = dict(
            method="GET",
            url="https://api.example.com/users",
            params={"status": "active"},
            headers={"Accept": "application/json",
                     "Authorization": "Bearer tok"},
            auth_type="bearer",
            pagination_strategy="cursor",
            page_size=100,
        )
        defaults.update(kwargs)
        return DryRunResult(**defaults)

    def test_to_dict_has_all_fields(self):
        result = self._make_result()
        d = result.to_dict()
        assert d["method"] == "GET"
        assert d["auth_type"] == "bearer"
        assert d["pagination_strategy"] == "cursor"
        assert d["page_size"] == 100

    def test_to_dict_params(self):
        result = self._make_result(params={"q": "test"})
        assert result.to_dict()["params"] == {"q": "test"}

    def test_to_dict_empty_params(self):
        result = self._make_result(params=None)
        assert result.to_dict()["params"] == {}

    def test_output_path_serialized_as_string(self):
        result = self._make_result(
            output_format="parquet", output_path=Path("/tmp/out.parquet"))
        assert result.to_dict()["output_path"] == Path(
            "/tmp/out.parquet").as_posix()

    def test_output_path_none_when_not_set(self):
        result = self._make_result()
        assert result.to_dict()["output_path"] is None

    def test_display_does_not_raise(self, capsys):
        result = self._make_result()
        result.display()

    def test_fetch_records_dry_run_integration(self):
        cfg = make_config()
        client = Apikit.from_config(cfg)
        result = client.fetch_records(
            "/users", dry_run=True, show_progress=False)
        assert isinstance(result, DryRunResult)
        assert result.auth_type == "bearer"
        assert "users" in result.url

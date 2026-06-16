"""
tests/test_schema_flattening.py  —  §9  JSON flattening & schema inference.
"""

from __future__ import annotations

import pytest
import sys

from ikiapikit import (
    flatten_dict,
    flatten_records,
    records_to_polars,
    records_to_pandas,
    infer_schema_dataframe
)

from unittest.mock import patch


class TestFlattenDict:
    def test_flat_dict_unchanged(self):
        d = {"a": 1, "b": "hello"}
        assert flatten_dict(d) == d

    def test_nested_one_level(self):
        d = {"user": {"name": "Alice", "age": 30}}
        flat = flatten_dict(d)
        assert flat == {"user_name": "Alice", "user_age": 30}

    def test_nested_multi_level(self):
        d = {"a": {"b": {"c": 42}}}
        assert flatten_dict(d) == {"a_b_c": 42}

    def test_list_values_serialized_as_json(self):
        d = {"tags": ["x", "y"]}
        flat = flatten_dict(d)
        assert flat["tags"] == '["x","y"]'

    def test_custom_separator(self):
        d = {"a": {"b": 1}}
        flat = flatten_dict(d, sep=".")
        assert "a.b" in flat

    def test_empty_dict(self):
        assert flatten_dict({}) == {}


class TestFlattenRecords:
    def test_list_of_dicts(self, nested_record: dict):
        flat = flatten_records([nested_record])
        assert flat[0]["user_name"] == "Alice"
        assert flat[0]["user_address_city"] == "NYC"

    def test_non_dict_wrapped_in_value(self):
        result = flatten_records([42, "hello"])
        assert result[0] == {"value": 42}
        assert result[1] == {"value": "hello"}

    def test_empty_list(self):
        assert flatten_records([]) == []


HAS_POLARS = True


class TestRecordsToPolars:
    def test_returns_polars_dataframe(self, records: list[dict]):
        pl = pytest.importorskip("polars")
        df = records_to_polars(records)
        assert isinstance(df, pl.DataFrame)
        assert len(df) == len(records)

    def test_flattens_nested(self, nested_record: dict):
        pl = pytest.importorskip("polars")
        df = records_to_polars([nested_record])
        assert "user_name" in df.columns
        assert "user_address_city" in df.columns

    def test_raises_without_polars(self, records: list[dict]):
        import ikiapikit
        with patch.dict(sys.modules, {"polars": None}), \
                patch.object(ikiapikit, "pl", None, create=True):
            with pytest.raises(ImportError, match="polars"):
                records_to_polars(records)


class TestRecordsToPandas:
    def test_returns_pandas_dataframe(self, records: list[dict]):
        pd = pytest.importorskip("pandas")
        df = records_to_pandas(records)
        assert hasattr(df, "columns")
        assert len(df) == len(records)


class TestInferPolarsSchema:
    def test_returns_dict_of_types(self, records: list[dict]):
        pytest.importorskip("polars")
        schema = infer_schema_dataframe(records, 'polars')
        assert schema is not None
        assert "id" in schema

    def test_returns_none_for_empty(self):
        assert infer_schema_dataframe([], 'polars') is None

    def test_returns_none_without_polars(self, records: list[dict]):
        with patch.dict(sys.modules, {"polars": None}):
            assert infer_schema_dataframe(records, 'polars') is None

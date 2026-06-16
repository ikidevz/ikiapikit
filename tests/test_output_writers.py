"""
tests/test_output_writers.py  —  §8  Output writers and get_writer factory.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from ikiapikit import (
    NdJsonWriter,
    JsonWriter,
    CsvWriter,
    ParquetWriter,
    ArrowWriter,
    get_writer,
    OutputError,
)

HAS_POLARS = True
HAS_PANDAS = True


class TestNdJsonWriter:
    def test_write_to_file(self, tmp_dir: Path, records: list[dict]):
        path = tmp_dir / "out.ndjson"
        NdJsonWriter().write(records, path)
        lines = path.read_bytes().split(b"\n")
        assert len(lines) == len(records)

    def test_write_to_buffer(self, records: list[dict]):
        buf = io.BytesIO()
        NdJsonWriter().write(records, buf)
        content = buf.getvalue()
        assert content.count(b"\n") == len(records) - 1

    def test_to_bytes(self, records: list[dict]):
        data = NdJsonWriter().to_bytes(records)
        assert isinstance(data, bytes)
        assert len(data) > 0


class TestJsonWriter:
    def test_write_to_file_pretty(self, tmp_dir: Path, records: list[dict]):
        path = tmp_dir / "out.json"
        JsonWriter().write(records, path)
        loaded = json.loads(path.read_bytes())
        assert loaded == records

    def test_write_to_buffer(self, records: list[dict]):
        buf = io.BytesIO()
        JsonWriter().write(records, buf)
        loaded = json.loads(buf.getvalue())
        assert loaded == records


class TestCsvWriter:
    def test_write_to_file(self, tmp_dir: Path, records: list[dict]):
        pytest.importorskip("polars", reason="polars not installed")
        path = tmp_dir / "out.csv"
        CsvWriter().write(records, path)
        assert path.exists()
        assert path.stat().st_size > 0

    def test_raises_output_error_without_backends(self, tmp_dir: Path, records: list[dict]):
        orig_polars = HAS_POLARS
        orig_pandas = HAS_PANDAS
        try:
            HAS_POLARS = False
            HAS_PANDAS = False
            with pytest.raises(OutputError, match="polars or pandas"):
                CsvWriter().write(records, tmp_dir / "out.csv")
        finally:
            HAS_POLARS = orig_polars
            HAS_PANDAS = orig_pandas


class TestParquetWriter:
    def test_write_to_file(self, tmp_dir: Path, records: list[dict]):
        pytest.importorskip("polars", reason="polars not installed")
        path = tmp_dir / "out.parquet"
        ParquetWriter().write(records, path)
        assert path.exists()
        assert path.stat().st_size > 0

    def test_write_to_buffer(self, records: list[dict]):
        pytest.importorskip("polars", reason="polars not installed")
        buf = io.BytesIO()
        ParquetWriter().write(records, buf)
        assert buf.tell() > 0


class TestGetWriter:
    @pytest.mark.parametrize("fmt,expected_cls", [
        ("ndjson",  NdJsonWriter),
        ("jsonl",   NdJsonWriter),
        ("json",    JsonWriter),
        ("csv",     CsvWriter),
        ("parquet", ParquetWriter),
        ("arrow",   ArrowWriter),
    ])
    def test_returns_correct_writer(self, fmt, expected_cls):
        assert isinstance(get_writer(fmt), expected_cls)

    def test_unknown_format_raises_output_error(self):
        with pytest.raises(OutputError, match="Unknown format"):
            get_writer("xml")

    def test_case_insensitive(self):
        assert isinstance(get_writer("NDJSON"), NdJsonWriter)
        assert isinstance(get_writer("Parquet"), ParquetWriter)

from .base import OutputWriter
from ...core.exceptions import OutputError
from ...core.types import OutputFormat

from .json_writers import NdJsonWriter, JsonWriter
from .tabular_writers import CsvWriter, ParquetWriter, ArrowWriter
from .duckdb_writer import DuckDBWriter


_WRITERS: dict[str, type[OutputWriter]] = {
    "ndjson": NdJsonWriter,
    "jsonl": NdJsonWriter,
    "json": JsonWriter,
    "csv": CsvWriter,
    "parquet": ParquetWriter,
    "arrow": ArrowWriter,
    "duckdb": DuckDBWriter,
}


def get_writer(fmt: OutputFormat) -> OutputWriter:
    """Factory: return the correct OutputWriter for a format string."""
    cls = _WRITERS.get(fmt.lower())
    if cls is None:
        raise OutputError(
            f"Unknown format: {fmt!r}. Choose from: {list(_WRITERS)}")
    return cls()

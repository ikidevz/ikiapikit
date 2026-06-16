import io
import pyarrow as pa

from ...core.exceptions import OutputError
from ..transform.flatten import flatten_records
from .base import OutputWriter, HAS_ARROW
from typing import Union
from pathlib import Path


class DuckDBWriter(OutputWriter):
    """Write to a DuckDB database file."""

    def __init__(self, table_name: str = "data"):
        self.table_name = table_name

    def write(self, records: list[dict], dest: Union[str, Path, io.IOBase]) -> None:
        try:
            import duckdb
        except ImportError:
            raise OutputError("DuckDB output requires: pip install duckdb")
        flat = flatten_records(records)
        if not isinstance(dest, (str, Path)):
            raise OutputError(
                "DuckDB output requires a file path, not a buffer.")
        con = duckdb.connect(str(dest))
        if HAS_ARROW:
            arrow_table = pa.Table.from_pylist(flat)
            con.register("_arrow_data", arrow_table)
            con.execute(
                f"CREATE OR REPLACE TABLE {self.table_name} AS SELECT * FROM _arrow_data")
        else:
            import json as _json
            rows_json = _json.dumps(flat)
            con.execute(
                f"CREATE OR REPLACE TABLE {self.table_name} AS "
                f"SELECT * FROM read_json_auto('{rows_json}')"
            )
        con.close()

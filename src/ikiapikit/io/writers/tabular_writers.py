
import io
import polars as pl
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .base import OutputWriter, HAS_POLARS, HAS_PANDAS, HAS_ARROW
from ..transform.flatten import flatten_records
from ...core.exceptions import OutputError
from typing import Union
from pathlib import Path


class CsvWriter(OutputWriter):
    """CSV via Polars (preferred) or Pandas."""

    def write(self, records: list[dict], dest: Union[str, Path, io.IOBase]) -> None:
        if HAS_POLARS:
            df = pl.DataFrame(flatten_records(records))
            if isinstance(dest, (str, Path)):
                df.write_csv(str(dest))
            else:
                dest.write(df.write_csv().encode())
        elif HAS_PANDAS:
            df = pd.DataFrame(flatten_records(records))
            if isinstance(dest, (str, Path)):
                df.to_csv(str(dest), index=False)
            else:
                dest.write(df.to_csv(index=False).encode())
        else:
            raise OutputError("CSV output requires polars or pandas.")


class ParquetWriter(OutputWriter):
    """Parquet via Polars (preferred) or PyArrow."""

    def write(self, records: list[dict], dest: Union[str, Path, io.IOBase]) -> None:
        flat = flatten_records(records)
        if HAS_POLARS:
            df = pl.DataFrame(flat)
            if isinstance(dest, (str, Path)):
                df.write_parquet(str(dest))
            else:
                buf = io.BytesIO()
                df.write_parquet(buf)
                dest.write(buf.getvalue())
        elif HAS_ARROW:
            table = pa.Table.from_pylist(flat)
            if isinstance(dest, (str, Path)):
                pq.write_table(table, str(dest))
            else:
                pq.write_table(table, dest)
        else:
            raise OutputError("Parquet output requires polars or pyarrow.")


class ArrowWriter(OutputWriter):
    """Apache Arrow IPC (Feather v2)."""

    def write(self, records: list[dict], dest: Union[str, Path, io.IOBase]) -> None:
        if not HAS_ARROW:
            raise OutputError("Arrow output requires pyarrow.")
        flat = flatten_records(records)
        table = pa.Table.from_pylist(flat)
        if isinstance(dest, (str, Path)):
            with pa.OSFile(str(dest), "wb") as f:
                writer = pa.ipc.new_file(f, table.schema)
                writer.write_table(table)
                writer.close()
        else:
            sink = pa.BufferOutputStream()
            writer = pa.ipc.new_file(sink, table.schema)
            writer.write_table(table)
            writer.close()
            dest.write(sink.getvalue().to_pybytes())

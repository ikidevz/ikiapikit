import orjson
import io

from .base import OutputWriter
from typing import Union
from pathlib import Path


class NdJsonWriter(OutputWriter):
    """Newline-delimited JSON (NDJSON / JSONL)."""

    def write(self, records: list[dict], dest: Union[str, Path, io.IOBase]) -> None:
        lines = b"\n".join(orjson.dumps(r) for r in records)
        if isinstance(dest, (str, Path)):
            Path(dest).write_bytes(lines)
        else:
            dest.write(lines)


class JsonWriter(OutputWriter):
    """Pretty JSON array."""

    def write(self, records: list[dict], dest: Union[str, Path, io.IOBase]) -> None:
        data = orjson.dumps(records, option=orjson.OPT_INDENT_2)
        if isinstance(dest, (str, Path)):
            Path(dest).write_bytes(data)
        else:
            dest.write(data)

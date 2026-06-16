import io

from pathlib import Path
from abc import ABC, abstractmethod
from typing import Union


HAS_POLARS = True
HAS_PANDAS = True
HAS_ARROW = True


class OutputWriter(ABC):
    """Abstract output writer — converts records to a file or bytes."""

    @abstractmethod
    def write(self, records: list[dict], dest: Union[str, Path, io.IOBase]) -> None:
        """Write records to dest."""

    def to_bytes(self, records: list[dict]) -> bytes:
        buf = io.BytesIO()
        self.write(records, buf)
        return buf.getvalue()

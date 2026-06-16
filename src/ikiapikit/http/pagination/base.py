import httpx

from abc import ABC, abstractmethod
from typing import Any, Optional

from ...core.models import PaginationConfig
from ...core.exceptions import PaginationError


class PaginatorBase(ABC):
    """Abstract base for pagination strategies."""

    def __init__(self, cfg: PaginationConfig):
        self.cfg = cfg
        self._page_count = 0

    def _check_limit(self) -> None:
        self._page_count += 1
        if self._page_count > self.cfg.max_pages:
            raise PaginationError(
                f"Exceeded max_pages={self.cfg.max_pages}. "
                "Increase pagination.max_pages or add a filter."
            )

    @abstractmethod
    def first_params(self, user_params: dict) -> dict:
        """Return query params for the first page."""

    @abstractmethod
    def next_params(
        self,
        user_params: dict,
        response_json: Any,
        response_headers: httpx.Headers,
    ) -> Optional[dict]:
        """Compute params for the next page. Return None when exhausted."""

    def extract_records(self, response_json: Any) -> list:
        """Pull the list of records out of the response payload."""
        if self.cfg.data_path:
            data = get_nested(response_json, self.cfg.data_path)
            if isinstance(data, list):
                return data
        if isinstance(response_json, list):
            return response_json
        if isinstance(response_json, dict):
            for v in response_json.values():
                if isinstance(v, list):
                    return v
        return []


def get_nested(obj: Any, dot_path: str) -> Any:
    """Traverse a dict using a dot-notation path. Returns None on miss."""
    if not dot_path:
        return obj
    parts = dot_path.split(".")
    cur = obj
    for part in parts:
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, (list, tuple)) and part.isdigit():
            cur = cur[int(part)]
        else:
            return None
    return cur

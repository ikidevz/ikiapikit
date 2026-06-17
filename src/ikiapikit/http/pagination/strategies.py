from .base import PaginatorBase, get_nested
from typing import Any, Optional

from ...core.models import PaginationConfig


class NoPaginator(PaginatorBase):
    """Single-page strategy — fetches one page and stops."""

    def first_params(self, user_params: dict) -> dict:
        return user_params

    def next_params(self, user_params, response_json, response_headers) -> Optional[dict]:
        return None

    def extract_records(self, response_json: Any) -> list:
        if self.cfg.data_path:
            data = get_nested(response_json, self.cfg.data_path)
            if isinstance(data, list):
                return data
            if data is not None:
                return [data]
        if isinstance(response_json, list):
            return response_json
        return [response_json]


class OffsetPaginator(PaginatorBase):
    """limit / offset style."""

    def __init__(self, cfg: PaginationConfig):
        super().__init__(cfg)
        self._offset = 0

    def first_params(self, user_params: dict) -> dict:
        return {
            **user_params,
            self.cfg.limit_param: self.cfg.page_size,
            self.cfg.offset_param: 0,
        }

    def next_params(self, user_params, response_json, response_headers) -> Optional[dict]:
        records = self.extract_records(response_json)
        if len(records) < self.cfg.page_size:
            return None
        if self._is_at_limit():
            return None
        self._offset += self.cfg.page_size
        return {
            **user_params,
            self.cfg.limit_param: self.cfg.page_size,
            self.cfg.offset_param: self._offset,
        }


class PageNumberPaginator(PaginatorBase):
    """page / per_page style."""

    def __init__(self, cfg: PaginationConfig):
        super().__init__(cfg)
        self._page = 1

    def first_params(self, user_params: dict) -> dict:
        return {
            **user_params,
            self.cfg.page_param: 1,
            self.cfg.limit_param: self.cfg.page_size,
        }

    def next_params(self, user_params, response_json, response_headers) -> Optional[dict]:
        records = self.extract_records(response_json)

        if not records or len(records) < self.cfg.page_size:
            return None

        if self.cfg.total_pages_path:
            total = get_nested(response_json, self.cfg.total_pages_path)
            if total is not None and self._page >= int(total):
                return None

        total_count = response_headers.get("x-total-count")
        if total_count and (self._page * self.cfg.page_size) >= int(total_count):
            return None

        if self._is_at_limit():
            return None

        self._page += 1
        return {
            **user_params,
            self.cfg.page_param: self._page,
            self.cfg.limit_param: self.cfg.page_size,
        }

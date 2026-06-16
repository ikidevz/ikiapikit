from .base import PaginatorBase, get_nested
from typing import Optional


class CursorPaginator(PaginatorBase):
    """Cursor / token based pagination."""

    def first_params(self, user_params: dict) -> dict:
        return {**user_params, self.cfg.limit_param: self.cfg.page_size}

    def next_params(self, user_params, response_json, response_headers) -> Optional[dict]:
        self._check_limit()
        cursor = get_nested(response_json, self.cfg.next_cursor_path)
        if not cursor:
            return None
        return {
            **user_params,
            self.cfg.limit_param: self.cfg.page_size,
            self.cfg.cursor_param: cursor,
        }

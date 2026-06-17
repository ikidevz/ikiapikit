from .base import PaginatorBase, get_nested
from typing import Optional


class CursorPaginator(PaginatorBase):
    """Cursor / token based pagination."""

    def first_params(self, user_params: dict) -> dict:
        return {**user_params, self.cfg.limit_param: self.cfg.page_size}

    def next_params(self, user_params, response_json, response_headers) -> Optional[dict]:
        if self.cfg.has_more_path:
            has_more = get_nested(response_json, self.cfg.has_more_path)
            if not has_more:
                return None

        cursor = get_nested(response_json, self.cfg.next_cursor_path)
        if cursor is None:
            return None

        if self._is_at_limit():
            return None

        return {
            **user_params,
            self.cfg.limit_param: self.cfg.page_size,
            self.cfg.cursor_param: cursor,
        }

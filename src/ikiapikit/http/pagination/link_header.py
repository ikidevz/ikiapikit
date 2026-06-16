
from .base import PaginatorBase
from typing import Optional
from ...core.models import PaginationConfig


class LinkHeaderPaginator(PaginatorBase):
    """RFC 5988 Link header pagination (e.g. GitHub API)."""

    def __init__(self, cfg: PaginationConfig):
        super().__init__(cfg)
        self._next_url: Optional[str] = None

    def first_params(self, user_params: dict) -> dict:
        return {**user_params, self.cfg.limit_param: self.cfg.page_size}

    def next_params(self, user_params, response_json, response_headers) -> Optional[dict]:
        self._check_limit()
        link_header = response_headers.get("Link", "")
        self._next_url = self._parse_link(link_header, "next")
        if not self._next_url:
            return None
        return {"__link_next_url__": self._next_url}

    @staticmethod
    def _parse_link(header: str, rel: str) -> Optional[str]:
        """Parse RFC 5988 Link header for a given rel value."""
        for part in header.split(","):
            segments = [s.strip() for s in part.split(";")]
            if len(segments) < 2:
                continue
            url_part = segments[0].strip("<>")
            for seg in segments[1:]:
                if seg == f'rel="{rel}"' or seg == f"rel={rel}":
                    return url_part
        return None

from .base import PaginatorBase
from .strategies import (
    NoPaginator,
    OffsetPaginator,
    PageNumberPaginator,
    CursorPaginator,
    LinkHeaderPaginator
)
from ...core.models import PaginationConfig


def build_paginator(cfg: PaginationConfig) -> PaginatorBase:
    """Factory: select the correct pagination strategy."""
    mapping: dict[str, type[PaginatorBase]] = {
        "none": NoPaginator,
        "offset": OffsetPaginator,
        "page": PageNumberPaginator,
        "cursor": CursorPaginator,
        "link": LinkHeaderPaginator,
    }
    cls = mapping.get(cfg.strategy, NoPaginator)
    return cls(cfg)

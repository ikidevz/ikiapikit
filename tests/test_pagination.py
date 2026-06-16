"""
tests/test_pagination.py  —  §5  Pagination strategies.
"""

from __future__ import annotations

import pytest
import httpx

from ikiapikit import (
    PaginationConfig,
    NoPaginator,
    OffsetPaginator,
    PageNumberPaginator,
    CursorPaginator,
    LinkHeaderPaginator,
    build_paginator,
    _get_nested,
    PaginationError,
)


class TestGetNested:
    def test_simple_key(self):
        assert _get_nested({"a": 1}, "a") == 1

    def test_nested_path(self):
        assert _get_nested({"a": {"b": {"c": 42}}}, "a.b.c") == 42

    def test_missing_key_returns_none(self):
        assert _get_nested({"a": 1}, "b") is None

    def test_list_index(self):
        assert _get_nested({"items": [10, 20, 30]}, "items.1") == 20

    def test_empty_path_returns_obj(self):
        obj = {"x": 1}
        assert _get_nested(obj, "") is obj


class TestNoPaginator:
    def test_first_params_unchanged(self):
        pag = NoPaginator(PaginationConfig())
        assert pag.first_params({"q": "a"}) == {"q": "a"}

    def test_next_params_always_none(self):
        pag = NoPaginator(PaginationConfig())
        assert pag.next_params({}, {}, httpx.Headers()) is None

    def test_extract_records_list_response(self):
        pag = NoPaginator(PaginationConfig())
        assert pag.extract_records([1, 2, 3]) == [1, 2, 3]

    def test_extract_records_dict_wraps_in_list(self):
        pag = NoPaginator(PaginationConfig())
        assert pag.extract_records({"id": 1}) == [{"id": 1}]

    def test_extract_records_with_data_path(self):
        pag = NoPaginator(PaginationConfig(data_path="results"))
        assert pag.extract_records({"results": [1, 2, 3]}) == [1, 2, 3]


class TestOffsetPaginator:
    def test_first_params_injects_limit_and_offset(self):
        pag = OffsetPaginator(PaginationConfig(page_size=10))
        params = pag.first_params({"q": "a"})
        assert params["limit"] == 10
        assert params["offset"] == 0

    def test_next_params_advances_offset(self):
        pag = OffsetPaginator(PaginationConfig(page_size=2))
        records_full_page = [{"id": i} for i in range(2)]
        resp = {"items": records_full_page}
        pag._offset = 0
        next_p = pag.next_params(
            {"limit": 2, "offset": 0}, resp, httpx.Headers())
        assert next_p["offset"] == 2

    def test_next_params_returns_none_on_short_page(self):
        pag = OffsetPaginator(PaginationConfig(page_size=10))
        pag._offset = 0
        resp = [{"id": i} for i in range(3)]
        assert pag.next_params({}, resp, httpx.Headers()) is None

    def test_max_pages_raises_pagination_error(self):
        pag = OffsetPaginator(PaginationConfig(page_size=1, max_pages=2))
        for _ in range(2):
            pag._check_limit()
        with pytest.raises(PaginationError):
            pag._check_limit()


class TestPageNumberPaginator:
    def test_first_params_starts_at_page_1(self):
        pag = PageNumberPaginator(PaginationConfig(page_size=5))
        params = pag.first_params({})
        assert params["page"] == 1
        assert params["limit"] == 5

    def test_next_params_increments_page(self):
        pag = PageNumberPaginator(PaginationConfig(page_size=2))
        full_page = [{"id": i} for i in range(2)]
        next_p = pag.next_params({}, full_page, httpx.Headers())
        assert next_p["page"] == 2

    def test_next_params_none_on_short_page(self):
        pag = PageNumberPaginator(PaginationConfig(page_size=10))
        short_page = [{"id": 1}]
        assert pag.next_params({}, short_page, httpx.Headers()) is None


class TestCursorPaginator:
    def test_first_params_injects_limit(self):
        pag = CursorPaginator(PaginationConfig(page_size=20))
        params = pag.first_params({})
        assert params["limit"] == 20

    def test_next_params_injects_cursor(self):
        pag = CursorPaginator(PaginationConfig(
            page_size=2, cursor_param="after", next_cursor_path="next_cursor"))
        resp = {"results": [1, 2], "next_cursor": "cursor_abc"}
        next_p = pag.next_params({}, resp, httpx.Headers())
        assert next_p["after"] == "cursor_abc"

    def test_next_params_none_when_no_cursor(self):
        pag = CursorPaginator(PaginationConfig(
            page_size=2, next_cursor_path="next_cursor"))
        resp = {"results": [1, 2], "next_cursor": None}
        assert pag.next_params({}, resp, httpx.Headers()) is None


class TestLinkHeaderPaginator:
    def test_parse_link_extracts_next_url(self):
        header = '<https://api.example.com/items?page=2>; rel="next", <https://api.example.com/items?page=5>; rel="last"'
        url = LinkHeaderPaginator._parse_link(header, "next")
        assert url == "https://api.example.com/items?page=2"

    def test_parse_link_returns_none_when_missing(self):
        assert LinkHeaderPaginator._parse_link("", "next") is None

    def test_next_params_returns_sentinel_with_url(self):
        pag = LinkHeaderPaginator(PaginationConfig(page_size=10))
        headers = httpx.Headers(
            {"Link": '<https://api.example.com/p2>; rel="next"'})
        next_p = pag.next_params({}, [], headers)
        assert next_p["__link_next_url__"] == "https://api.example.com/p2"

    def test_next_params_none_when_no_link_header(self):
        pag = LinkHeaderPaginator(PaginationConfig(page_size=10))
        assert pag.next_params({}, [], httpx.Headers()) is None


class TestBuildPaginator:
    @pytest.mark.parametrize("strategy,expected_cls", [
        ("none",   NoPaginator),
        ("offset", OffsetPaginator),
        ("page",   PageNumberPaginator),
        ("cursor", CursorPaginator),
        ("link",   LinkHeaderPaginator),
    ])
    def test_returns_correct_type(self, strategy, expected_cls):
        cfg = PaginationConfig(strategy=strategy)
        assert isinstance(build_paginator(cfg), expected_cls)

    def test_unknown_strategy_returns_no_paginator(self):
        cfg = PaginationConfig(strategy="none")
        assert isinstance(build_paginator(cfg), NoPaginator)

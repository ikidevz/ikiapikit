"""
tests/test_models.py  —  §3  Pydantic model validation.
"""

from __future__ import annotations

import pytest

from kit import (
    ApiConfig,
    AuthConfig,
    RetryConfig,
    PaginationConfig,
)


class TestApiConfig:
    def test_trailing_slash_stripped(self):
        cfg = ApiConfig(base_url="https://api.example.com/")
        assert cfg.base_url == "https://api.example.com"

    def test_defaults(self):
        cfg = ApiConfig(base_url="https://api.example.com")
        assert cfg.auth.type == "none"
        assert cfg.timeout == 30.0
        assert cfg.verify_ssl is True
        assert cfg.follow_redirects is True

    def test_headers_default_empty(self):
        cfg = ApiConfig(base_url="https://api.example.com")
        assert cfg.headers == {}


class TestAuthConfig:
    def test_bearer_requires_token(self):
        with pytest.raises(ValueError, match="token"):
            AuthConfig(type="bearer")

    def test_apikey_requires_api_key(self):
        with pytest.raises(ValueError, match="api_key"):
            AuthConfig(type="apikey")

    def test_basic_requires_username_and_password(self):
        with pytest.raises(ValueError, match="username"):
            AuthConfig(type="basic", username="user")

    def test_oauth2_requires_all_fields(self):
        with pytest.raises(ValueError):
            AuthConfig(type="oauth2", client_id="id")

    def test_none_type_valid(self):
        cfg = AuthConfig(type="none")
        assert cfg.type == "none"

    def test_bearer_valid(self):
        cfg = AuthConfig(type="bearer", token="tok")
        assert cfg.token.get_secret_value() == "tok"

    def test_apikey_with_header(self):
        cfg = AuthConfig(type="apikey", api_key="mykey", api_key_header="X-Custom")
        assert cfg.api_key_header == "X-Custom"

    def test_apikey_with_query_param(self):
        cfg = AuthConfig(type="apikey", api_key="mykey", api_key_query_param="key")
        assert cfg.api_key_query_param == "key"

    def test_basic_valid(self):
        cfg = AuthConfig(type="basic", username="u", password="p")
        assert cfg.username == "u"

    def test_oauth2_valid(self):
        cfg = AuthConfig(
            type="oauth2",
            client_id="cid",
            client_secret="csecret",
            token_url="https://auth.example.com/token",
        )
        assert cfg.client_id == "cid"


class TestRetryConfig:
    def test_defaults(self):
        cfg = RetryConfig()
        assert cfg.max_attempts == 3
        assert 429 in cfg.retry_on_status
        assert 500 in cfg.retry_on_status


class TestPaginationConfig:
    def test_defaults(self):
        cfg = PaginationConfig()
        assert cfg.strategy == "none"
        assert cfg.page_size == 100
        assert cfg.max_pages == 1_000

    def test_custom_values(self):
        cfg = PaginationConfig(strategy="offset", page_size=50, max_pages=10)
        assert cfg.strategy == "offset"
        assert cfg.page_size == 50

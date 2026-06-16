"""
tests/test_auth.py  —  §4  Authentication strategies.
"""

from __future__ import annotations

import pytest
import httpx
import respx

from kit import (
    AuthConfig,
    NoAuth,
    BearerAuth,
    ApiKeyAuth,
    BasicAuth,
    OAuth2ClientCredentials,
    build_auth_strategy,
)


class TestNoAuth:
    def test_passes_request_unchanged(self):
        req = httpx.Request("GET", "https://api.example.com/test")
        result = NoAuth().apply_sync(req)
        assert "Authorization" not in result.headers

    @pytest.mark.asyncio
    async def test_async_same_as_sync(self):
        req = httpx.Request("GET", "https://api.example.com/test")
        result = await NoAuth().apply_async(req)
        assert "Authorization" not in result.headers


class TestBearerAuth:
    def test_injects_authorization_header(self):
        req = httpx.Request("GET", "https://api.example.com/test")
        result = BearerAuth("my-token").apply_sync(req)
        assert result.headers["Authorization"] == "Bearer my-token"

    def test_overwrites_existing_header(self):
        req = httpx.Request(
            "GET", "https://api.example.com/test",
            headers={"Authorization": "Bearer old-token"},
        )
        result = BearerAuth("new-token").apply_sync(req)
        assert result.headers["Authorization"] == "Bearer new-token"


class TestApiKeyAuth:
    def test_injects_header(self):
        req = httpx.Request("GET", "https://api.example.com/test")
        result = ApiKeyAuth("my-key", header="X-API-Key").apply_sync(req)
        assert result.headers["X-API-Key"] == "my-key"

    def test_custom_header_name(self):
        req = httpx.Request("GET", "https://api.example.com/test")
        result = ApiKeyAuth("my-key", header="X-Auth-Token").apply_sync(req)
        assert result.headers["X-Auth-Token"] == "my-key"

    def test_query_param_mode(self):
        req = httpx.Request("GET", "https://api.example.com/test")
        result = ApiKeyAuth("my-key", query_param="api_key").apply_sync(req)
        assert "Authorization" not in result.headers
        assert "api_key=my-key" in str(result.url)


class TestBasicAuth:
    def test_injects_base64_header(self):
        import base64
        req = httpx.Request("GET", "https://api.example.com/test")
        result = BasicAuth("user", "pass").apply_sync(req)
        expected = "Basic " + base64.b64encode(b"user:pass").decode()
        assert result.headers["Authorization"] == expected


class TestOAuth2ClientCredentials:
    def test_is_expired_before_fetch(self):
        auth = OAuth2ClientCredentials("id", "secret", "https://auth.example.com/token")
        assert auth._is_expired() is True

    @pytest.mark.asyncio
    async def test_fetches_token_on_first_request(self):
        auth = OAuth2ClientCredentials("id", "secret", "https://auth.example.com/token")
        mock_token_response = {"access_token": "tok123", "expires_in": 3600}

        with respx.mock:
            respx.post("https://auth.example.com/token").mock(
                return_value=httpx.Response(200, json=mock_token_response)
            )
            req = httpx.Request("GET", "https://api.example.com/test")
            result = await auth.apply_async(req)
            assert result.headers["Authorization"] == "Bearer tok123"

    def test_refresh_sync_updates_token(self):
        auth = OAuth2ClientCredentials("id", "secret", "https://auth.example.com/token")
        mock_token_response = {"access_token": "refreshed_tok", "expires_in": 3600}

        with respx.mock:
            respx.post("https://auth.example.com/token").mock(
                return_value=httpx.Response(200, json=mock_token_response)
            )
            auth.refresh_sync()
            assert auth._access_token == "refreshed_tok"


class TestBuildAuthStrategy:
    def test_none_returns_no_auth(self):
        cfg = AuthConfig(type="none")
        assert isinstance(build_auth_strategy(cfg), NoAuth)

    def test_bearer_returns_bearer_auth(self):
        cfg = AuthConfig(type="bearer", token="tok")
        assert isinstance(build_auth_strategy(cfg), BearerAuth)

    def test_apikey_returns_api_key_auth(self):
        cfg = AuthConfig(type="apikey", api_key="key")
        assert isinstance(build_auth_strategy(cfg), ApiKeyAuth)

    def test_basic_returns_basic_auth(self):
        cfg = AuthConfig(type="basic", username="u", password="p")
        assert isinstance(build_auth_strategy(cfg), BasicAuth)

    def test_oauth2_returns_oauth2(self):
        cfg = AuthConfig(
            type="oauth2", client_id="id", client_secret="secret",
            token_url="https://auth.example.com/token",
        )
        assert isinstance(build_auth_strategy(cfg), OAuth2ClientCredentials)

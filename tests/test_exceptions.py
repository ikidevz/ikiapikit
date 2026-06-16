"""
tests/test_exceptions.py  —  §2  Exception hierarchy and behaviour.
"""

from __future__ import annotations

import pytest

from kit import (
    ApikitError,
    AuthError,
    RateLimitError,
    PaginationError,
    ConfigError,
    ConnectorNotFoundError,
    OutputError,
    GraphQLError,
    WebhookSignatureError,
)


class TestExceptions:
    def test_hierarchy(self):
        assert issubclass(AuthError, ApikitError)
        assert issubclass(RateLimitError, ApikitError)
        assert issubclass(PaginationError, ApikitError)
        assert issubclass(ConfigError, ApikitError)
        assert issubclass(ConnectorNotFoundError, ApikitError)
        assert issubclass(OutputError, ApikitError)
        assert issubclass(GraphQLError, ApikitError)
        assert issubclass(WebhookSignatureError, ApikitError)

    def test_rate_limit_error_stores_retry_after(self):
        err = RateLimitError(retry_after=42.0)
        assert err.retry_after == 42.0
        assert "42.0" in str(err)

    def test_graphql_error_stores_errors_list(self):
        errors = [{"message": "Field not found"}, {"message": "Auth failed"}]
        err = GraphQLError(errors)
        assert err.errors == errors
        assert "Field not found" in str(err)
        assert "Auth failed" in str(err)

    def test_rate_limit_error_none_retry(self):
        err = RateLimitError(retry_after=None)
        assert err.retry_after is None

    def test_all_exceptions_catchable_as_apikit_error(self):
        for exc_cls in (
            AuthError, RateLimitError, PaginationError, ConfigError,
            ConnectorNotFoundError, OutputError,
        ):
            with pytest.raises(ApikitError):
                raise exc_cls("test")

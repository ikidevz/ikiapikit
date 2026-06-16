from typing import Optional


class ApikitError(Exception):
    """Base exception for all apikit errors."""


class AuthError(ApikitError):
    """Authentication / authorisation failure."""


class RateLimitError(ApikitError):
    """HTTP 429 — server is rate-limiting us."""

    def __init__(self, retry_after: Optional[float] = None):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after: {retry_after}s")


class PaginationError(ApikitError):
    """Pagination strategy failed or detected an infinite loop."""


class ConfigError(ApikitError):
    """Configuration file / keyring error."""


class ConnectorNotFoundError(ApikitError):
    """Named connector not registered."""


class OutputError(ApikitError):
    """Failed to write output in the requested format."""


class WebhookSignatureError(ApikitError):
    """Raised when a webhook signature fails validation."""


class GraphQLError(ApikitError):
    """GraphQL endpoint returned errors."""

    def __init__(self, errors: list[dict]):
        self.errors = errors
        msgs = "; ".join(e.get("message", str(e)) for e in errors)
        super().__init__(f"GraphQL errors: {msgs}")


class RecordValidationError(ApikitError):
    """One or more records failed Pydantic model validation."""

    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__(f"{len(errors)} record(s) failed validation")


class HookError(ApikitError):
    """A registered hook raised an unexpected exception."""

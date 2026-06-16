from typing import Optional
from pydantic import BaseModel
from typing import List, Dict, Literal

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from .constants import DEFAULT_MAX_RETRIES, DEFAULT_PAGE_SIZE, DEFAULT_MAX_PAGES, DEFAULT_TIMEOUT
from .types import AuthType, PaginationStrategy


class AuthConfig(BaseModel):
    """Authentication configuration."""

    type: AuthType = "none"

    # Bearer / API-key
    token: Optional[SecretStr] = None
    api_key: Optional[SecretStr] = None
    api_key_header: str = "X-API-Key"
    api_key_query_param: Optional[str] = None

    # Basic auth
    username: Optional[str] = None
    password: Optional[SecretStr] = None

    # OAuth2 Client Credentials
    client_id: Optional[str] = None
    client_secret: Optional[SecretStr] = None
    token_url: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_credentials(self) -> "AuthConfig":
        if self.type == "bearer" and not self.token:
            raise ValueError("bearer auth requires 'token'")
        if self.type == "apikey" and not (self.api_key or self.api_key_query_param):
            raise ValueError("apikey auth requires 'api_key'")
        if self.type == "basic" and not (self.username and self.password):
            raise ValueError("basic auth requires 'username' and 'password'")
        if self.type == "oauth2" and not (self.client_id and self.client_secret and self.token_url):
            raise ValueError(
                "oauth2 requires 'client_id', 'client_secret', and 'token_url'")
        return self


class RetryConfig(BaseModel):
    """Retry / resilience configuration."""

    max_attempts: int = DEFAULT_MAX_RETRIES
    min_wait: float = 1.0        # seconds
    max_wait: float = 60.0       # seconds
    jitter: float = 1.0          # seconds of random jitter
    retry_on_status: List[int] = Field(
        default_factory=lambda: [429, 500, 502, 503, 504])


class PaginationConfig(BaseModel):
    """Pagination behaviour."""

    strategy: PaginationStrategy = "none"
    page_size: int = DEFAULT_PAGE_SIZE
    max_pages: int = DEFAULT_MAX_PAGES

    # Offset pagination
    offset_param: str = "offset"
    limit_param: str = "limit"

    # Page-number pagination
    page_param: str = "page"

    # Cursor pagination
    cursor_param: str = "cursor"
    next_cursor_path: str = "next_cursor"

    # GraphQL cursor
    graphql_after_var: str = "after"
    graphql_page_info_path: str = "pageInfo"

    # Where the actual records live in the response (dot-path)
    data_path: Optional[str] = None
    total_path: Optional[str] = None


class ApiConfig(BaseModel):
    """Top-level API configuration — the single source of truth."""

    name: Optional[str] = None
    base_url: str
    auth: AuthConfig = Field(default_factory=AuthConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    pagination: PaginationConfig = Field(default_factory=PaginationConfig)
    headers: Dict[str, str] = Field(default_factory=dict)
    timeout: float = DEFAULT_TIMEOUT
    verify_ssl: bool = True
    follow_redirects: bool = True

    @field_validator("base_url")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")


class CacheConfig(BaseModel):
    """Configuration for the response cache."""

    enabled: bool = True
    ttl: int = 300
    max_entries: int = 1_000
    backend: Literal["memory", "disk"] = "memory"
    disk_path: Optional[str] = None
    honour_cache_control: bool = True

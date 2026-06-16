from typing import Any, Dict, Callable, Optional
from pydantic import BaseModel, Field

from ..core.types import AuthType
from ..core.models import PaginationConfig, ApiConfig, AuthConfig
from ..core.exceptions import ConnectorNotFoundError


class ConnectorDefinition(BaseModel):
    """A pre-built connector definition — a template for popular APIs."""

    name: str
    base_url: str
    auth_type: AuthType = "none"
    default_headers: Dict[str, str] = Field(default_factory=dict)
    pagination: PaginationConfig = Field(default_factory=PaginationConfig)
    description: str = ""


class ConnectorRegistry:
    """
    Central registry for pre-built API connectors.

    Usage:
        @ConnectorRegistry.register
        def stripe() -> ConnectorDefinition:
            return ConnectorDefinition(name="stripe", ...)

        defn = ConnectorRegistry.get("stripe")
    """

    _registry: dict[str, ConnectorDefinition] = {}

    @classmethod
    def register(cls, fn: Callable[[], ConnectorDefinition]) -> Callable:
        """Decorator: register a connector factory function."""
        defn = fn()
        cls._registry[defn.name] = defn
        return fn

    @classmethod
    def get(cls, name: str) -> ConnectorDefinition:
        defn = cls._registry.get(name)
        if defn is None:
            raise ConnectorNotFoundError(
                f"No built-in connector named '{name}'. "
                f"Available: {list(cls._registry.keys())}"
            )
        return defn

    @classmethod
    def list(cls) -> list[str]:
        return list(cls._registry.keys())

    @classmethod
    def build_config(cls, name: str, token: Optional[str] = None, **kwargs: Any) -> ApiConfig:
        """Build an ApiConfig from a registered connector definition."""
        defn = cls.get(name)
        if token:
            auth_kwargs: dict[str, Any] = {"type": defn.auth_type}
            if defn.auth_type == "bearer":
                auth_kwargs["token"] = token
            elif defn.auth_type == "apikey":
                auth_kwargs["api_key"] = token
        else:
            auth_kwargs = {"type": "none"}
        return ApiConfig(
            name=defn.name,
            base_url=defn.base_url,
            auth=AuthConfig(**auth_kwargs),
            headers={**defn.default_headers, **kwargs.get("headers", {})},
            pagination=defn.pagination,
        )

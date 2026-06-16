from ..base import ConnectorRegistry, ConnectorDefinition
from ...core.models import PaginationConfig


@ConnectorRegistry.register
def _jsonplaceholder_connector() -> ConnectorDefinition:
    """Demo connector — no auth required."""
    return ConnectorDefinition(
        name="jsonplaceholder",
        base_url="https://jsonplaceholder.typicode.com",
        auth_type="none",
        pagination=PaginationConfig(strategy="none"),
        description="JSONPlaceholder — free fake REST API for demos.",
    )

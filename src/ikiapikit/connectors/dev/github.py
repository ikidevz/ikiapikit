from ..base import ConnectorRegistry, ConnectorDefinition
from ...core.models import PaginationConfig


@ConnectorRegistry.register
def _github_connector() -> ConnectorDefinition:
    return ConnectorDefinition(
        name="github",
        base_url="https://api.github.com",
        auth_type="bearer",
        default_headers={"Accept": "application/vnd.github+json"},
        pagination=PaginationConfig(
            strategy="link",
            limit_param="per_page",
            page_size=100,
        ),
        description="GitHub REST API v3 — bearer token, Link-header pagination.",
    )

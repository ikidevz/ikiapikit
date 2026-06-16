from ..base import ConnectorRegistry, ConnectorDefinition
from ...core.models import PaginationConfig


@ConnectorRegistry.register
def _hubspot_connector() -> ConnectorDefinition:
    return ConnectorDefinition(
        name="hubspot",
        base_url="https://api.hubapi.com",
        auth_type="bearer",
        pagination=PaginationConfig(
            strategy="cursor",
            cursor_param="after",
            next_cursor_path="paging.next.after",
            data_path="results",
            limit_param="limit",
            page_size=100,
        ),
        description="HubSpot CRM API — bearer token, cursor pagination.",
    )

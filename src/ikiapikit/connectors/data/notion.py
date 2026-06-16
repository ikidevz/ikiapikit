from ..base import ConnectorRegistry, ConnectorDefinition
from ...core.models import PaginationConfig


@ConnectorRegistry.register
def _notion_connector() -> ConnectorDefinition:
    return ConnectorDefinition(
        name="notion",
        base_url="https://api.notion.com/v1",
        auth_type="bearer",
        default_headers={"Notion-Version": "2022-06-28"},
        pagination=PaginationConfig(
            strategy="cursor",
            page_size=100,
            cursor_param="start_cursor",
            next_cursor_path="next_cursor",
            data_path="results",
            limit_param="page_size",
        ),
        description="Notion API v1 — bearer token, cursor pagination.",
    )

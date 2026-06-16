from ..base import ConnectorRegistry, ConnectorDefinition
from ...core.models import PaginationConfig


@ConnectorRegistry.register
def _airtable_connector() -> ConnectorDefinition:
    return ConnectorDefinition(
        name="airtable",
        base_url="https://api.airtable.com/v0",
        auth_type="bearer",
        pagination=PaginationConfig(
            strategy="cursor",
            page_size=100,
            cursor_param="offset",
            next_cursor_path="offset",
            data_path="records",
            limit_param="pageSize",
        ),
        description="Airtable REST API — bearer token, cursor pagination (offset).",
    )

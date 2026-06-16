from ..base import ConnectorRegistry, ConnectorDefinition
from ...core.models import PaginationConfig


@ConnectorRegistry.register
def _jira_connector() -> ConnectorDefinition:
    return ConnectorDefinition(
        name="jira",
        base_url="https://your-domain.atlassian.net/rest/api/3",
        auth_type="basic",
        pagination=PaginationConfig(
            strategy="offset",
            page_size=50,
            limit_param="maxResults",
            offset_param="startAt",
            data_path="issues",
            total_path="total",
        ),
        description="Jira REST API v3 — basic auth (email:api_token), offset pagination.",
    )

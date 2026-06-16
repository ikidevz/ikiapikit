from ..base import ConnectorRegistry, ConnectorDefinition
from ...core.models import PaginationConfig


@ConnectorRegistry.register
def _salesforce_connector() -> ConnectorDefinition:
    return ConnectorDefinition(
        name="salesforce",
        base_url="https://login.salesforce.com/services/data/v59.0",
        auth_type="oauth2",
        default_headers={"Accept": "application/json"},
        pagination=PaginationConfig(
            strategy="offset",
            page_size=200,
            limit_param="limit",
            offset_param="offset",
            data_path="records",
            total_path="totalSize",
        ),
        description="Salesforce REST API v59 — OAuth2 Client Credentials, offset pagination.",
    )

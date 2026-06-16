from ..base import ConnectorRegistry, ConnectorDefinition
from ...core.models import PaginationConfig


@ConnectorRegistry.register
def _shopify_connector() -> ConnectorDefinition:
    return ConnectorDefinition(
        name="shopify",
        base_url="https://your-store.myshopify.com/admin/api/2024-01",
        auth_type="apikey",
        default_headers={"Content-Type": "application/json"},
        pagination=PaginationConfig(
            strategy="link",
            page_size=250,
            limit_param="limit",
        ),
        description="Shopify Admin REST API — API key, Link-header pagination (250/page).",
    )

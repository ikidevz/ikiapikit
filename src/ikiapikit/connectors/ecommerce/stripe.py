from ..base import ConnectorRegistry, ConnectorDefinition
from ...core.models import PaginationConfig


@ConnectorRegistry.register
def _stripe_connector() -> ConnectorDefinition:
    return ConnectorDefinition(
        name="stripe",
        base_url="https://api.stripe.com/v1",
        auth_type="bearer",
        pagination=PaginationConfig(
            strategy="cursor",
            cursor_param="starting_after",
            next_cursor_path="data.-1.id",
            data_path="data",
            limit_param="limit",
            page_size=100,
        ),
        description="Stripe REST API — bearer token auth, cursor pagination.",
    )

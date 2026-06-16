from ..core.models import ApiConfig
from ..core.constants import DEFAULT_PAGE_SIZE
from ..core.exceptions import GraphQLError
from .client import RestClient
from .pagination.base import get_nested

from typing import Optional


class GraphQLClient:
    """
    Unified GraphQL client with cursor-based pagination (Relay spec),
    variable injection, and error surface.
    """

    def __init__(self, config: ApiConfig, endpoint: str):
        self.config = config
        self.endpoint = endpoint
        self._http = RestClient(config)

    def _build_payload(
        self,
        query: str,
        variables: Optional[dict] = None,
        operation_name: Optional[str] = None,
    ) -> dict:
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables
        if operation_name:
            payload["operationName"] = operation_name
        return payload

    @staticmethod
    def _raise_for_errors(data: dict) -> None:
        errors = data.get("errors")
        if errors:
            raise GraphQLError(errors)

    def query_sync(
        self,
        query: str,
        variables: Optional[dict] = None,
        operation_name: Optional[str] = None,
    ) -> dict:
        """Execute a single GraphQL query synchronously."""
        payload = self._build_payload(query, variables, operation_name)
        data = self._http.request_sync(
            "POST", self.endpoint, json_body=payload)
        self._raise_for_errors(data)
        return data.get("data", {})

    async def query_async(
        self,
        query: str,
        variables: Optional[dict] = None,
        operation_name: Optional[str] = None,
    ) -> dict:
        """Execute a single GraphQL query asynchronously."""
        payload = self._build_payload(query, variables, operation_name)
        data = await self._http.request_async("POST", self.endpoint, json_body=payload)
        self._raise_for_errors(data)
        return data.get("data", {})

    def paginate_sync(
        self,
        query: str,
        variables: Optional[dict] = None,
        connection_path: Optional[str] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[dict]:
        """Paginate a Relay-style connection synchronously."""
        variables = dict(variables or {})
        variables.setdefault("first", page_size)
        all_nodes: list[dict] = []

        while True:
            data = self.query_sync(query, variables)
            connection = get_nested(
                data, connection_path) if connection_path else data
            if not isinstance(connection, dict):
                break

            nodes = connection.get("nodes") or connection.get("edges") or []
            if nodes and isinstance(nodes[0], dict) and "node" in nodes[0]:
                nodes = [n["node"] for n in nodes]
            all_nodes.extend(nodes)

            page_info = connection.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            variables["after"] = page_info.get("endCursor")

        return all_nodes

    async def paginate_async(
        self,
        query: str,
        variables: Optional[dict] = None,
        connection_path: Optional[str] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[dict]:
        """Async variant of paginate_sync."""
        variables = dict(variables or {})
        variables.setdefault("first", page_size)
        all_nodes: list[dict] = []

        while True:
            data = await self.query_async(query, variables)
            connection = get_nested(
                data, connection_path) if connection_path else data
            if not isinstance(connection, dict):
                break

            nodes = connection.get("nodes") or connection.get("edges") or []
            if nodes and isinstance(nodes[0], dict) and "node" in nodes[0]:
                nodes = [n["node"] for n in nodes]
            all_nodes.extend(nodes)

            page_info = connection.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            variables["after"] = page_info.get("endCursor")

        return all_nodes

"""
tests/http/test_graphql_client.py  —  §7  GraphQL client.
"""

from __future__ import annotations

import pytest
import httpx
import respx

from kit import GraphQLClient, GraphQLError
from tests.conftest import make_config, BASE_URL

GQL_QUERY = "query { users { id name } }"


class TestGraphQLClient:
    def test_query_sync_returns_data(self):
        cfg = make_config()
        gql = GraphQLClient(cfg, "/graphql")
        response_body = {"data": {"users": [{"id": 1, "name": "Alice"}]}}
        with respx.mock(base_url=BASE_URL):
            respx.post(f"{BASE_URL}/graphql").mock(
                return_value=httpx.Response(200, json=response_body))
            result = gql.query_sync(GQL_QUERY)
        assert result == {"users": [{"id": 1, "name": "Alice"}]}

    def test_query_sync_raises_graphql_error(self):
        cfg = make_config()
        gql = GraphQLClient(cfg, "/graphql")
        error_body = {"errors": [{"message": "Field not found"}]}
        with respx.mock(base_url=BASE_URL):
            respx.post(f"{BASE_URL}/graphql").mock(
                return_value=httpx.Response(200, json=error_body))
            with pytest.raises(GraphQLError) as exc_info:
                gql.query_sync(GQL_QUERY)
        assert "Field not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_async_returns_data(self):
        cfg = make_config()
        gql = GraphQLClient(cfg, "/graphql")
        response_body = {"data": {"orders": [{"id": 99}]}}
        with respx.mock(base_url=BASE_URL):
            respx.post(f"{BASE_URL}/graphql").mock(
                return_value=httpx.Response(200, json=response_body))
            result = await gql.query_async(GQL_QUERY)
        assert result == {"orders": [{"id": 99}]}

    def test_paginate_sync_follows_relay_cursor(self):
        cfg = make_config()
        gql = GraphQLClient(cfg, "/graphql")
        page1 = {
            "data": {
                "items": {
                    "nodes": [{"id": 1}, {"id": 2}],
                    "pageInfo": {"hasNextPage": True, "endCursor": "cursor_A"},
                }
            }
        }
        page2 = {
            "data": {
                "items": {
                    "nodes": [{"id": 3}],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }
        responses = [page1, page2]
        idx = [0]

        def handler(request):
            resp = responses[idx[0]]
            idx[0] += 1
            return httpx.Response(200, json=resp)

        with respx.mock(base_url=BASE_URL):
            respx.post(f"{BASE_URL}/graphql").mock(side_effect=handler)
            nodes = gql.paginate_sync(GQL_QUERY, connection_path="items")
        assert [n["id"] for n in nodes] == [1, 2, 3]

    def test_paginate_sync_handles_edges_style(self):
        cfg = make_config()
        gql = GraphQLClient(cfg, "/graphql")
        page = {
            "data": {
                "connection": {
                    "edges": [{"node": {"id": 10}}, {"node": {"id": 20}}],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }
        with respx.mock(base_url=BASE_URL):
            respx.post(f"{BASE_URL}/graphql").mock(
                return_value=httpx.Response(200, json=page))
            nodes = gql.paginate_sync(GQL_QUERY, connection_path="connection")
        assert [n["id"] for n in nodes] == [10, 20]

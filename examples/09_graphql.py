"""
09_graphql.py
=============
GraphQL — single queries, variables, and Relay cursor pagination.

Demonstrates:
  • client.graphql()         — single query, no pagination
  • client.graphql()         — query with variables
  • client.graphql(paginate=True) — Relay hasNextPage / endCursor
  • client.agraphql()        — async GraphQL
  • GraphQLError handling    — errors[] in 200 response

Uses the free public GraphQL API:
  • https://countries.trevorblades.com/  — countries, continents (no auth)
  • GitHub GraphQL (examples with token placeholder)

Run:
    python 09_graphql.py

For GitHub examples, set:
    GITHUB_TOKEN=ghp_... python 09_graphql.py
"""

import asyncio
import os
from ikiapikit import Apikit, GraphQLError

COUNTRIES_URL = "https://countries.trevorblades.com/"

print("=" * 60)
print("09 · GRAPHQL")
print("=" * 60)

# ── 1. Single query — no variables ───────────────────────────────────────────
print("\n▶ Single query (no variables)")
client = Apikit(base_url=COUNTRIES_URL, auth="none")

result = client.graphql(
    "/",
    """
    query {
        continents {
            code
            name
        }
    }
    """,
)
continents = result.get("continents", [])
print(f"  Got {len(continents)} continents:")
for c in continents:
    print(f"    {c['code']}  {c['name']}")

# ── 2. Query with variables ───────────────────────────────────────────────────
print("\n▶ Query with variables")
result = client.graphql(
    "/",
    """
    query GetCountriesInContinent($code: ID!) {
        continent(code: $code) {
            name
            countries {
                code
                name
                capital
                emoji
            }
        }
    }
    """,
    variables={"code": "AS"},
)
continent = result.get("continent", {})
countries = continent.get("countries", [])
print(f"  Continent : {continent.get('name')}")
print(f"  Countries : {len(countries)}")
for c in countries[:5]:
    print(
        f"    {c['emoji']}  {c['code']}  {c['name']:<30} capital={c.get('capital', '-')}")
if len(countries) > 5:
    print(f"    ... and {len(countries)-5} more")

# ── 3. Query for a specific country ──────────────────────────────────────────
print("\n▶ Query for Philippines (PH)")
result = client.graphql(
    "/",
    """
    query GetCountry($code: ID!) {
        country(code: $code) {
            name
            capital
            currency
            emoji
            languages { name }
            states { name }
        }
    }
    """,
    variables={"code": "PH"},
)
ph = result.get("country", {})
print(f"  Name      : {ph.get('name')}")
print(f"  Capital   : {ph.get('capital')}")
print(f"  Currency  : {ph.get('currency')}")
print(f"  Emoji     : {ph.get('emoji')}")
languages = [l['name'] for l in ph.get('languages', [])]
print(f"  Languages : {', '.join(languages)}")

# ── 4. Relay pagination (GitHub — token required) ─────────────────────────────
print("\n▶ Relay cursor pagination (GitHub example)")
github_token = os.environ.get("GITHUB_TOKEN", "")
if github_token:
    gh_client = Apikit(
        base_url="https://api.github.com",
        auth="bearer",
        token=github_token,
        headers={"Accept": "application/vnd.github+json"},
    )
    issues = gh_client.graphql(
        "/graphql",
        """
        query($first: Int, $after: String) {
            repository(owner: "pallets", name: "flask") {
                issues(first: $first, after: $after, states: OPEN) {
                    nodes {
                        number
                        title
                        createdAt
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
            }
        }
        """,
        paginate=True,
        connection_path="repository.issues",
        page_size=20,
    )
    print(f"  Fetched {len(issues)} open issues from pallets/flask")
    for issue in issues[:3]:
        print(f"    #{issue['number']}  {issue['title'][:55]}...")
else:
    print("  (Set GITHUB_TOKEN=ghp_... to run the live GitHub example)")
    print("  Config would be:")
    print("    client = Apikit(base_url='https://api.github.com',")
    print("                    auth='bearer', token='ghp_...')")
    print("    issues = client.graphql(")
    print("        '/graphql',")
    print("        QUERY,")
    print("        paginate=True,")
    print("        connection_path='repository.issues',")
    print("    )")

# ── 5. GraphQLError handling ──────────────────────────────────────────────────
print("\n▶ GraphQLError — API returns errors[] in a 200 response")
try:
    bad_result = client.graphql(
        "/",
        """
        query {
            country(code: "NOTEXIST") {
                nonExistentField
            }
        }
        """,
    )
except GraphQLError as e:
    print(f"  Caught GraphQLError: {e.errors[0].get('message', str(e))[:80]}")
except Exception as e:
    print(f"  Got error: {type(e).__name__}: {str(e)[:80]}")

# ── 6. Async GraphQL ──────────────────────────────────────────────────────────
print("\n▶ agraphql()  — async variant")


async def demo_async_graphql():
    client = Apikit(base_url=COUNTRIES_URL, auth="none")
    result = await client.agraphql(
        "/",
        """
        query {
            languages {
                code
                name
                native
            }
        }
        """,
    )
    languages = result.get("languages", [])
    print(f"  Async fetched {len(languages)} languages")
    for lang in languages[:4]:
        print(
            f"    {lang['code']}  {lang['name']:<20} native={lang.get('native', '-')}")
    print(f"    ...")

asyncio.run(demo_async_graphql())

print("\n✓ GraphQL examples complete.\n")

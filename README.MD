<div align="center">

```
██╗██╗  ██╗██╗ █████╗ ██████╗ ██╗██╗  ██╗██╗████████╗
██║██║ ██╔╝██║██╔══██╗██╔══██╗██║██║ ██╔╝██║╚══██╔══╝
██║█████╔╝ ██║███████║██████╔╝██║█████╔╝ ██║   ██║
██║██╔═██╗ ██║██╔══██║██╔═══╝ ██║██╔═██╗ ██║   ██║
██║██║  ██╗██║██║  ██║██║     ██║██║  ██╗██║   ██║
╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝   ╚═╝
```

**The Swiss-Army Knife for REST & GraphQL APIs**

_Built for data engineers, data scientists, and analysts_

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/apikit)](https://pypi.org/project/apikit/)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-89%25-green)](tests/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

</div>

---

## What is iki-apikit?

`iki-apikit` is a production-ready Python library that gives you a **single, ergonomic facade** for working with any REST or GraphQL API. It handles the hard parts — auth, pagination, retries, rate limits, output formats, and DataFrame conversion — so you can focus on the data.

```python
from iki_apikit import Apikit

client = Apikit.from_name("github", token="ghp_...")

# One line to Polars DataFrame, auto-paginated, nested JSON flattened
df = client.fetch_polars("/orgs/myorg/repos", paginate=True)

# Stream huge datasets without loading everything into memory
async for record in client.astream("/events", paginate=True):
    await save_to_db(record)

# Write directly to Parquet
client.fetch_to_file("/orders", format="parquet", file_path="orders.parquet", paginate=True)
```

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Quick Reference](#quick-reference)
4. [Creating a Client](#creating-a-client)
5. [Fetching Data](#fetching-data)
6. [DataFrame Output](#dataframe-output)
7. [Async Support & Streaming](#async-support--streaming)
8. [Mutations — POST, PUT, DELETE](#mutations--post-put-delete)
9. [Write Directly to Files](#write-directly-to-files)
10. [GraphQL](#graphql)
11. [Authentication](#authentication)
12. [Pagination](#pagination)
13. [Output Formats](#output-formats)
14. [JSON Flattening & Schema Inference](#json-flattening--schema-inference)
15. [Retry & Rate Limit Handling](#retry--rate-limit-handling)
16. [Built-in Connectors](#built-in-connectors)
17. [Custom Connectors](#custom-connectors)
18. [Config Management](#config-management)
19. [Inspect an Endpoint](#inspect-an-endpoint)
20. [Webhook Receiver](#webhook-receiver)
21. [dbt Export](#dbt-export)
22. [Dry Run Mode](#dry-run-mode)
23. [Error Handling](#error-handling)
24. [Architecture](#architecture)
25. [Tech Stack](#tech-stack)
26. [Testing](#testing)
27. [Environment Variables](#environment-variables)

---

## Installation

```bash
pip install iki_apikit
```

All backends — Polars, Pandas, PyArrow, DuckDB, keyring — are included out of the box. Install once, use every feature immediately.

---

## Quick Start

```python
from iki_apikit import Apikit

# ── Named connector (pre-built) ──────────────────────────────────────────────
client = Apikit.from_name("github", token="ghp_...")
df = client.fetch_polars("/repos/myorg/myrepo/issues", paginate=True)

# ── Ad-hoc client ────────────────────────────────────────────────────────────
client = Apikit(base_url="https://api.example.com", auth="bearer", token="your-token")
df = client.fetch_pandas("/users", paginate=True)

# ── Async fetch ──────────────────────────────────────────────────────────────
df = await client.afetch_polars("/customers", paginate=True)

# ── Stream records one at a time (memory-efficient) ─────────────────────────
async for record in client.astream("/events", paginate=True):
    process(record)

# ── Write to Parquet on disk ─────────────────────────────────────────────────
client.fetch_to_file("/data", format="parquet", file_path="output.parquet", paginate=True)
```

---

## Quick Reference

A cheat-sheet for the most common patterns:

| Task                      | Method                                                                         |
| ------------------------- | ------------------------------------------------------------------------------ |
| Fetch as list of dicts    | `client.fetch_records("/endpoint")`                                            |
| Fetch as Polars DataFrame | `client.fetch_polars("/endpoint")`                                             |
| Fetch as Pandas DataFrame | `client.fetch_pandas("/endpoint")`                                             |
| Async fetch               | `await client.afetch_polars("/endpoint")`                                      |
| Stream records            | `async for rec in client.astream("/endpoint")`                                 |
| Write to file             | `client.fetch_to_file("/endpoint", format="parquet", file_path="out.parquet")` |
| POST / PUT / DELETE       | `client.post("/endpoint", body={...})`                                         |
| GraphQL query             | `client.graphql("/graphql", "query { ... }")`                                  |
| Probe an endpoint         | `client.inspect("/endpoint")`                                                  |
| Preview without network   | `client.fetch_records("/endpoint", dry_run=True)`                              |
| Use a built-in connector  | `Apikit.from_name("github", token="...")`                                      |
| Save a connector config   | `ConfigManager().add_connector("name", base_url="...", ...)`                   |

**Auth types:** `"bearer"` · `"apikey"` · `"basic"` · `"oauth2"` · `"none"`

**Pagination strategies:** `"offset"` · `"page"` · `"cursor"` · `"link"` · `"none"`

**Output formats:** `"parquet"` · `"ndjson"` · `"jsonl"` · `"csv"` · `"arrow"` · `"json"` · `"duckdb"`

---

## Creating a Client

**Ad-hoc — provide everything inline:**

```python
from iki_apikitimport Apikit

client = Apikit(
    base_url="https://api.example.com",
    auth="bearer",           # "bearer" | "apikey" | "basic" | "oauth2" | "none"
    token="your-token",
    headers={"X-App-Version": "2.0"},
    timeout=30.0,
    max_retries=3,
    verify_ssl=True,
)
```

**Named connector — from the built-in registry or your config file:**

```python
client = Apikit.from_name("github", token="ghp_...")
client = Apikit.from_name("stripe", token="sk_live_...")
client = Apikit.from_name("my_company_api")   # from ~/.config/apikit/config.toml
```

**Full config object — for maximum control:**

```python
from iki_apikitimport Apikit, ApiConfig, AuthConfig, RetryConfig, PaginationConfig

cfg = ApiConfig(
    base_url="https://api.example.com",
    auth=AuthConfig(type="bearer", token="your-token"),
    retry=RetryConfig(max_attempts=5, min_wait=1.0, max_wait=60.0),
    pagination=PaginationConfig(
        strategy="cursor",
        page_size=200,
        cursor_param="next",
        next_cursor_path="paging.next_token",
        data_path="records",
    ),
    headers={"Accept-Version": "2.0"},
    timeout=45.0,
)

client = Apikit.from_config(cfg)
```

---

## Fetching Data

**Raw records — list of dicts:**

```python
records = client.fetch_records(
    "/opportunities",
    params={"status": "open"},
    paginate=True,
    strategy="offset",       # override pagination strategy for this call
    page_size=100,
    data_path="data.items",  # dot-path to the records array in the response
    show_progress=True,      # Rich progress bar
)
# → [{"id": 1, "name": "...", "owner": {...}}, ...]
```

**Single record by ID:**

```python
user = client.fetch_records("/users/42")[0]
```

**Nested data path — unwrap deeply nested responses:**

```python
# Response: {"data": {"items": [{"id": 1}, ...]}}
records = client.fetch_records("/wrapped", data_path="data.items")
```

---

## DataFrame Output

**Polars** (recommended — fastest, lowest memory):

```python
# Nested JSON is flattened automatically using __ separator
df = client.fetch_polars("/users", paginate=True)

# Input:  {"id": 1, "user": {"name": "Alice", "dept": {"code": "ENG"}}}
# Output: id | user__name | user__dept__code
#          1 | Alice      | ENG

# Skip flattening if you want raw nested columns
df = client.fetch_polars("/users", flatten=False)
```

**Pandas:**

```python
df = client.fetch_pandas("/orders", paginate=True, data_path="data.orders")

# Chain directly with Pandas
revenue = (
    client.fetch_pandas("/transactions", paginate=True)
    .groupby("status")["amount"]
    .sum()
)
```

---

## Async Support & Streaming

Every sync method has an `a`-prefixed async twin:

| Sync              | Async              |
| ----------------- | ------------------ |
| `fetch_records()` | `afetch_records()` |
| `fetch_polars()`  | `afetch_polars()`  |
| `fetch_pandas()`  | `afetch_pandas()`  |
| `fetch_to_file()` | `afetch_to_file()` |
| `graphql()`       | `agraphql()`       |
| `inspect()`       | `ainspect()`       |

**Concurrent fetches — multiple endpoints at once:**

```python
import asyncio

async def main():
    client = Apikit(base_url="https://api.example.com", auth="bearer", token="...")

    users, orders, products = await asyncio.gather(
        client.afetch_polars("/users",    paginate=True),
        client.afetch_polars("/orders",   paginate=True),
        client.afetch_polars("/products", paginate=True),
    )
    # All three fetched concurrently
```

**Async streaming — one record at a time:**

```python
async def process_all():
    count = 0
    async for record in client.astream("/events", paginate=True, page_size=500):
        await save_to_database(record)
        count += 1
    print(f"Processed {count:,} events")
```

**Early exit:**

```python
async for record in client.astream("/logs", paginate=True):
    if record["severity"] == "CRITICAL":
        alert(record)
        break   # stops cleanly, no wasted requests
```

---

## Mutations — POST, PUT, DELETE

```python
# Create
new_contact = client.post(
    "/contacts",
    body={"name": "Alice Smith", "email": "alice@example.com"},
)
print(new_contact["id"])   # → "ct_abc123"

# Update
updated = client.put(
    f"/contacts/{new_contact['id']}",
    body={"stage": "qualified"},
)

# Delete
result = client.delete(f"/contacts/{new_contact['id']}")
print(result["deleted"])   # → True

# With query params on mutations
client.post("/search", body={"query": "python"}, params={"dry_run": "true"})
```

---

## Write Directly to Files

```python
# Sync
path = client.fetch_to_file(
    "/transactions",
    format="parquet",   # parquet | ndjson | jsonl | csv | arrow | json | duckdb
    file_path="transactions.parquet",
    paginate=True,
    page_size=500,
)

# Async
path = await client.afetch_to_file(
    "/events",
    format="ndjson",
    file_path="events.ndjson",
    paginate=True,
)

# DuckDB — instant SQL on the fetched data
client.fetch_to_file("/orders", format="duckdb", file_path="orders.duckdb")

import duckdb
con = duckdb.connect("orders.duckdb")
df = con.execute("SELECT status, SUM(amount) FROM data GROUP BY status").df()
```

---

## GraphQL

**Single query:**

```python
result = client.graphql(
    "/graphql",
    """
    query GetUser($id: ID!) {
        user(id: $id) { id name email role }
    }
    """,
    variables={"id": "usr_42"},
)
print(result["user"]["name"])
```

**Relay cursor pagination — follows `pageInfo.hasNextPage` automatically:**

```python
all_issues = client.graphql(
    "/graphql",
    """
    query($first: Int, $after: String) {
        repository(owner: "myorg", name: "myrepo") {
            issues(first: $first, after: $after, states: OPEN) {
                nodes { id title createdAt }
                pageInfo { hasNextPage endCursor }
            }
        }
    }
    """,
    paginate=True,
    connection_path="repository.issues",
    page_size=100,
)
print(f"Fetched {len(all_issues)} open issues")
```

**Async GraphQL:**

```python
result = await client.agraphql("/graphql", "{ me { login } }")
```

---

## Authentication

### Bearer Token

```python
client = Apikit(base_url="https://api.example.com", auth="bearer", token="your-token")
```

### API Key

```python
# Via header (default: X-API-Key)
client = Apikit(base_url="...", auth="apikey", api_key="key", api_key_header="X-API-Key")

# Via query parameter (?api_key=...)
client = Apikit(base_url="...", auth="apikey", api_key="key", api_key_query_param="api_key")
```

### HTTP Basic

```python
client = Apikit(base_url="...", auth="basic", username="admin", password="secret")
```

### OAuth2 Client Credentials

Fully automatic — fetches the token on first request, refreshes 30 seconds before expiry:

```python
client = Apikit(
    base_url="https://api.example.com",
    auth="oauth2",
    client_id="your-client-id",
    client_secret="your-client-secret",
    token_url="https://auth.example.com/oauth/token",
    scopes=["read:data", "write:data"],
)

# Just use it — token lifecycle is completely automatic
df = client.fetch_polars("/protected/data", paginate=True)
```

### No Auth

```python
client = Apikit(base_url="https://jsonplaceholder.typicode.com", auth="none")
```

---

## Pagination

### Offset

```python
cfg = PaginationConfig(
    strategy="offset",
    page_size=100,
    limit_param="limit",
    offset_param="offset",
    data_path="items",
)
```

### Page-Number

```python
cfg = PaginationConfig(strategy="page", page_size=50, page_param="page", limit_param="per_page")
```

### Cursor

```python
# Response: {"results": [...], "next_cursor": "cur_xyz"}
cfg = PaginationConfig(
    strategy="cursor",
    page_size=100,
    cursor_param="cursor",
    next_cursor_path="next_cursor",
    data_path="results",
)
```

### Link-Header (RFC 5988)

Used by GitHub, GitLab, and others. Parses `Link: <url>; rel="next"` headers automatically:

```python
cfg = PaginationConfig(strategy="link", page_size=100)
```

### GraphQL Relay

Follows `pageInfo.hasNextPage` + `endCursor`. Pass `paginate=True` to `graphql()`.

### Per-call overrides

Any `fetch_*` call can override pagination without changing the client config:

```python
records = client.fetch_records(
    "/items",
    paginate=True,
    strategy="cursor",
    page_size=250,
    data_path="results",
)
```

---

## Output Formats

| Format        | Key                    | Library          | Best For                        |
| ------------- | ---------------------- | ---------------- | ------------------------------- |
| **Parquet**   | `"parquet"`            | Polars / PyArrow | Analytics, S3, DuckDB           |
| **NDJSON**    | `"ndjson"` / `"jsonl"` | orjson           | Streaming, Kafka, log pipelines |
| **JSON**      | `"json"`               | orjson           | APIs, debugging                 |
| **CSV**       | `"csv"`                | Polars / Pandas  | Excel, legacy tools             |
| **Arrow IPC** | `"arrow"`              | PyArrow          | Fast inter-process exchange     |
| **DuckDB**    | `"duckdb"`             | DuckDB           | In-process SQL                  |

```python
from apikit import get_writer
import io

records = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

# To file
get_writer("parquet").write(records, "output.parquet")

# To in-memory buffer
buf = io.BytesIO()
get_writer("ndjson").write(records, buf)
```

---

## JSON Flattening & Schema Inference

Nested JSON is flattened using `__` as the separator by default. Lists are serialized to JSON strings.

```python
# Input record:
# {"id": 1, "user": {"name": "Alice", "address": {"city": "NYC"}}, "tags": ["a", "b"]}

# After flattening (automatic in fetch_polars / fetch_pandas / file writers):
# {"id": 1, "user__name": "Alice", "user__address__city": "NYC", "tags": '["a","b"]'}

from apikit import _flatten_dict, _flatten_records, records_to_polars

flat = _flatten_dict({"a": {"b": {"c": 42}}})
# → {"a__b__c": 42}

flat = _flatten_dict({"a": {"b": 1}}, sep=".")
# → {"a.b": 1}  — custom separator

df = records_to_polars(raw_api_response)
```

**Schema inference:**

```python
from apikit import infer_polars_schema

records = client.fetch_records("/contacts", page_size=10)
schema = infer_polars_schema(records)
# → {"id": Int64, "name": Utf8, "score": Float64, "meta__plan": Utf8, ...}
```

---

## Retry & Rate Limit Handling

**Retry configuration:**

```python
from apikit import RetryConfig

cfg = RetryConfig(
    max_attempts=5,
    min_wait=1.0,
    max_wait=60.0,
    jitter=1.0,
    retry_on_status=[429, 500, 502, 503, 504],
)
```

When the API returns `429`, apikit reads the `Retry-After` header, sleeps that duration, and retries automatically. `401 Unauthorized` is never retried — it raises `AuthError` immediately.

**Manual rate limit inspection:**

```python
from apikit import RateLimitState

rl = RateLimitState(min_remaining=100)
rl.ingest(response.headers)   # parses X-RateLimit-* headers from any provider

if rl.should_throttle():
    time.sleep(rl.sleep_duration())

print(rl.headroom)
# → {"remaining": 4950, "limit": 5000, "used_pct": 1.0}
```

Apikit understands rate-limit headers from GitHub, HubSpot, Stripe, and generic `X-RateLimit-*` variants automatically.

---

## Built-in Connectors

```python
client = Apikit.from_name("github",          token="ghp_...")
client = Apikit.from_name("stripe",          token="sk_live_...")
client = Apikit.from_name("hubspot",         token="pat-...")
client = Apikit.from_name("notion",          token="secret_...")
client = Apikit.from_name("airtable",        token="pat...")
client = Apikit.from_name("shopify",         token="shpat_...")
client = Apikit.from_name("jira",            token="email:api_token")
client = Apikit.from_name("salesforce",      token="oauth_token")
client = Apikit.from_name("jsonplaceholder")  # no auth needed
```

| Connector         | Auth    | Pagination              |
| ----------------- | ------- | ----------------------- |
| `github`          | Bearer  | Link-header (RFC 5988)  |
| `stripe`          | Bearer  | Cursor (`data` path)    |
| `hubspot`         | Bearer  | Cursor (`results` path) |
| `notion`          | Bearer  | Cursor (`start_cursor`) |
| `airtable`        | Bearer  | Cursor (`offset`)       |
| `shopify`         | API Key | Link-header (250/page)  |
| `jira`            | Basic   | Offset (`startAt`)      |
| `salesforce`      | OAuth2  | Offset (`records` path) |
| `jsonplaceholder` | None    | None (demo)             |

List all registered connectors at runtime:

```python
from apikit import ConnectorRegistry

print(ConnectorRegistry.list())
# → ["github", "stripe", "hubspot", "notion", ...]
```

---

## Custom Connectors

```python
from apikit import ConnectorRegistry, ConnectorDefinition, PaginationConfig

@ConnectorRegistry.register
def _my_api() -> ConnectorDefinition:
    return ConnectorDefinition(
        name="my_api",
        base_url="https://api.mycompany.com/v2",
        auth_type="bearer",
        pagination=PaginationConfig(
            strategy="cursor",
            page_size=200,
            cursor_param="next",
            next_cursor_path="paging.next_token",
            data_path="records",
        ),
        description="My Company API — bearer token, cursor pagination.",
    )

# Available immediately by name — anywhere in your codebase
client = Apikit.from_name("my_api", token="your-token")
```

---

## Config Management

Save API configs to `~/.config/apikit/config.toml`. Secrets go to the OS keyring (macOS Keychain, Windows Credential Manager, Linux Secret Service) and are never written to disk in plain text.

```python
from apikit import ConfigManager

mgr = ConfigManager()

# Save
mgr.add_connector(
    name="my_api",
    base_url="https://api.mycompany.com/v2",
    auth_type="bearer",
    token="your-secret-token",       # stored in keyring, not in TOML
)

# Load
client = Apikit.from_name("my_api")

# List / Remove
print(mgr.list_connectors())         # → ["my_api", ...]
mgr.remove_connector("my_api")       # also removes keyring entries
```

Config file format (`~/.config/apikit/config.toml`):

```toml
[connectors.my_api]
base_url  = "https://api.mycompany.com/v2"
auth_type = "bearer"
# token is in the OS keyring, not stored here

[connectors.another_api]
base_url         = "https://another.example.com"
auth_type        = "apikey"
api_key_header   = "X-Custom-Key"
timeout          = 60
```

Override the default config path with the `APIKIT_CONFIG_PATH` environment variable.

---

## Inspect an Endpoint

Probe any endpoint to get latency, schema, pagination hints, and rate-limit state — with a ready-to-paste `ApiConfig` snippet:

```python
result = client.inspect("/users")

# Returns InspectorResult with:
# result.status_code          → 200
# result.latency_ms           → 87.3
# result.detected_pagination  → "cursor"
# result.record_count         → 25
# result.rate_limit_state     → RateLimitState(remaining=4950, limit=5000)
# result.schema_sample()      → {"id": "int", "name": "str", ...}
# result.suggested_config()   → copy-paste ApiConfig snippet

# Async variant
result = await client.ainspect("/users")

# Dry run — shows what would be sent without making the request
result = client.inspect("/users", dry_run=True)
```

---

## Webhook Receiver

A local HTTP server that validates, records, and streams incoming webhooks. Useful for local development and testing integrations.

```python
from apikit import WebhookReceiver, StripeWebhookValidator

receiver = WebhookReceiver(
    port=8080,
    path="/webhook",
    validator=StripeWebhookValidator("whsec_..."),
    output_file="events.ndjson",   # stream to NDJSON as events arrive
    provider="stripe",
    max_events=1000,               # ring buffer — oldest dropped when full
)

receiver.start()

# Your app runs here...
time.sleep(60)

receiver.stop()

# Access received events
print(f"Received {receiver.event_count} events")
df = receiver.to_polars()
```

**Available validators:**

```python
from apikit import (
    StripeWebhookValidator,     # Stripe-Signature header + timestamp tolerance
    GitHubWebhookValidator,     # X-Hub-Signature-256 header
    GenericHmacValidator,       # any HMAC-SHA256 header with configurable prefix
)

# Generic — adapt to any provider
validator = GenericHmacValidator(
    secret="my-secret",
    header_name="X-Signature",
    prefix="sha256=",           # strip prefix before comparing
)
```

---

## dbt Export

Generate dbt-ready seed CSV + `sources.yml` + `schema.yml` from any API fetch:

```python
from apikit import DbtExporter

exporter = DbtExporter(output_dir="dbt_seeds/")

# Export from records directly
exporter.export(
    records=records,
    name="stripe_customers",
    database="raw",
    schema="stripe",
    description="Customers fetched from Stripe REST API",
    tags=["stripe", "customers"],
)

# Or fetch + export in one call
exporter.export_from_client(
    client=client,
    endpoint="/customers",
    name="stripe_customers",
    paginate=True,
    database="raw",
    schema="stripe",
)

# Dry run — preview what would be written without touching disk
DbtExporter(output_dir="dbt_seeds/", dry_run=True).export(records, "preview")
```

Writes:

- `dbt_seeds/seeds/stripe_customers.csv`
- `dbt_seeds/models/sources.yml`
- `dbt_seeds/models/stripe_customers.yml`

The `sources.yml` is append-safe — re-running won't duplicate source entries.

---

## Dry Run Mode

See exactly what apikit would send without making any network calls. Works on every fetch method:

```python
result = client.fetch_records("/users", params={"status": "active"}, dry_run=True)

# Prints to stderr:
# ── DRY RUN ──────────────────────────────────────────
#   Method        GET
#   URL           https://api.example.com/users
#   Params        {'status': 'active'}
#   Auth          bearer
#   Headers       {'Authorization': '***', 'Accept': 'application/json'}
#   Pagination    strategy=none, page_size=100
# ─────────────────────────────────────────────────────

# Structured dict for programmatic use
print(result.to_dict())
# → {
#     "method": "GET",
#     "url": "https://api.example.com/users",
#     "params": {"status": "active"},
#     "auth_type": "bearer",
#     "pagination_strategy": "none",
#     "page_size": 100,
#     "output_format": None,
#     "output_path": None,
#   }
```

`dry_run=True` also works on `fetch_to_file()` and `inspect()`.

---

## Error Handling

All apikit errors inherit from `ApikitError`:

```python
from apikit import (
    ApikitError,             # base class
    AuthError,               # 401 Unauthorized
    RateLimitError,          # 429 after all retries exhausted
    PaginationError,         # max_pages exceeded
    ConfigError,             # config file read/write failure
    ConnectorNotFoundError,  # unknown connector name
    OutputError,             # writer failure or unsupported format
    GraphQLError,            # API returned {"errors": [...]}
    WebhookSignatureError,   # webhook signature validation failed
)

try:
    df = client.fetch_polars("/data", paginate=True)
except AuthError:
    print("Check your token")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except PaginationError:
    print("Hit max_pages limit — add a filter or increase max_pages")
except GraphQLError as e:
    print(f"GraphQL errors: {e.errors}")
except ApikitError as e:
    print(f"apikit error: {e}")
```

**Key behaviours:**

- `401` raises `AuthError` immediately — never retried.
- `429` is retried using the `Retry-After` header; raises `RateLimitError` when retries are exhausted.
- `500`, `502`, `503`, `504` are retried with exponential back-off + jitter.
- GraphQL `200` responses with an `errors` field raise `GraphQLError`.
- `WebhookSignatureError` carries the reason (missing header, timestamp expired, signature mismatch).

---

## Architecture

apikit is built around five design patterns that keep it extensible without modifying core code:

```
┌─────────────────────────────────────────────────────────────────────┐
│                          User Code                                   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Apikit  ── Facade Pattern                          │
│  from_name()  fetch_polars()  afetch_pandas()  astream()            │
│  fetch_to_file()  graphql()  post()  put()  delete()  inspect()     │
└────┬──────────────────┬──────────────────────┬───────────────────────┘
     │                  │                      │
     ▼                  ▼                      ▼
┌─────────┐     ┌────────────┐        ┌──────────────┐
│ Config  │     │ RestClient │        │ GraphQL      │
│ Manager │     │ (httpx)    │        │ Client       │
│ Repo ▶  │     └─────┬──────┘        └──────┬───────┘
└────┬────┘           │                      │
     │                ▼                      │
     ▼         ┌──────────────┐             │
┌──────────┐   │ Auth Strategy│◄────────────┘
│Connector │   │ (Strategy ▶) │
│ Registry │   └──────────────┘
│ (Plugin▶)│          │
└──────────┘          ▼
               ┌──────────────┐     ┌───────────────────┐
               │  Paginator   │     │  Output Writer    │
               │ (Strategy ▶) │     │  (Strategy ▶)     │
               └──────────────┘     └───────────────────┘
```

| Pattern                 | Applied To                                      | Benefit                                                        |
| ----------------------- | ----------------------------------------------- | -------------------------------------------------------------- |
| **Facade**              | `Apikit` class                                  | Single ergonomic entry point — hides all complexity            |
| **Strategy**            | `AuthStrategy`, `PaginatorBase`, `OutputWriter` | Swap any behaviour at runtime without changing call sites      |
| **Repository / Plugin** | `ConnectorRegistry`                             | Add new API connectors with a decorator — zero core changes    |
| **Builder**             | `ApiConfig` + Pydantic                          | Compose configuration incrementally, validated at construction |

---

## Tech Stack

| Purpose                     | Library              |
| --------------------------- | -------------------- |
| HTTP (sync + async)         | `httpx`              |
| Config models & validation  | `pydantic` v2        |
| Retry & resilience          | `tenacity`           |
| Fast JSON serialization     | `orjson`             |
| Terminal output             | `rich`               |
| Primary DataFrame backend   | `polars` (optional)  |
| Secondary DataFrame backend | `pandas` (optional)  |
| Columnar I/O                | `pyarrow` (optional) |
| In-process SQL              | `duckdb` (optional)  |
| TOML config writing         | `tomli-w`            |
| Secret storage              | `keyring` (optional) |

---

## Testing

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# With coverage report
pytest --cov=apikit --cov-report=term-missing

# Run a specific layer
pytest tests/http/ -v
pytest tests/features/webhook/ -v
pytest tests/integration/ -v

# Run a single test file
pytest tests/test_auth.py -v

# Skip optional-dependency tests
pytest -k "not duckdb"
```

**Test layout:**

```
tests/
├── conftest.py                      # shared fixtures
├── test_exceptions.py               # §2  exception hierarchy
├── test_models.py                   # §3  Pydantic config models
├── test_auth.py                     # §4  auth strategies
├── test_pagination.py               # §5  pagination strategies
├── test_output_writers.py           # §8  output writers
├── test_schema_flattening.py        # §9  JSON flattening & schema inference
├── test_config_registry.py          # §10 & §11  ConfigManager + ConnectorRegistry
├── test_apikit_facade.py            # §12  Apikit facade
├── test_rate_limit_inspector.py     # §13 & §14  RateLimitState + ApiInspector
├── test_dbt_dry_run.py              # §16 & §17  DbtExporter + DryRunResult
├── http/
│   ├── test_rest_client.py          # §6  RestClient (sync + async)
│   └── test_graphql_client.py       # §7  GraphQL client
├── features/
│   └── webhook/
│       └── test_webhook.py          # §15  webhook validators & receiver
└── integration/
    └── test_full_flows.py           # end-to-end flows
```

---

## Environment Variables

| Variable             | Description                                                        |
| -------------------- | ------------------------------------------------------------------ |
| `APIKIT_TOKEN`       | Default bearer token read by `Apikit.from_name()`                  |
| `APIKIT_API_KEY`     | Default API key                                                    |
| `APIKIT_CONFIG_PATH` | Override `~/.config/apikit/config.toml` path                       |
| `APIKIT_LOG_LEVEL`   | Logging verbosity: `DEBUG`, `INFO`, `WARNING` (default: `WARNING`) |

---

<div align="center">

Built with ❤️ for data professionals who work with APIs every day.

_Simple, composable, fast._

</div>

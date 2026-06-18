"""
13_connectors.py
================
Built-in connector registry, custom connector registration, and
loading connectors by name at runtime.

Demonstrates:
  • ConnectorRegistry.list()         — enumerate every built-in
  • ConnectorRegistry.get()          — inspect a connector definition
  • ConnectorRegistry.build_config() — turn a definition into a full ApiConfig
  • Apikit.from_name()               — instantiate a client by name (built-in)
  • @ConnectorRegistry.register      — register your own custom connector
  • ConnectorDefinition              — the fields that make up a connector
  • ConfigManager.add_connector()    — save a custom connector to config file
  • Apikit.from_name()               — instantiate from a saved config connector
  • ConnectorNotFoundError           — raised when name is not found anywhere

Built-in connectors in the registry:
  stripe, github, hubspot, jsonplaceholder, salesforce,
  notion, airtable, shopify, jira

Real network calls use only JSONPlaceholder (no auth required).
All other connector demos are config/structure only — no live token needed.

Run:
    python 13_connectors.py
"""

import tempfile
from pathlib import Path

from ikiapikit import (
    Apikit,
    ApiConfig,
    PaginationConfig,
    ConnectorRegistry,
    ConnectorDefinition,
    ConnectorNotFoundError,
    ConfigManager,
)

print("=" * 60)
print("13 · CONNECTOR REGISTRY")
print("=" * 60)


# ── 1. List all built-in connectors ──────────────────────────────────────────
print("\n▶ ConnectorRegistry.list()  — all built-in connectors")
names = ConnectorRegistry.list()
print(f"  {len(names)} built-ins: {names}")


# ── 2. Inspect a connector definition ────────────────────────────────────────
print("\n▶ ConnectorRegistry.get()  — inspect each built-in")
for name in names:
    defn = ConnectorRegistry.get(name)
    print(
        f"  {defn.name:<16} base_url={defn.base_url:<52} "
        f"auth={defn.auth_type:<8} "
        f"pagination={defn.pagination.strategy}"
    )


# ── 3. Drill into one connector definition ───────────────────────────────────
print("\n▶ Detailed look at the 'hubspot' connector definition")
hs = ConnectorRegistry.get("hubspot")
print(f"  name              : {hs.name}")
print(f"  base_url          : {hs.base_url}")
print(f"  auth_type         : {hs.auth_type}")
print(f"  description       : {hs.description}")
print(f"  pagination strategy    : {hs.pagination.strategy}")
print(f"  pagination cursor_param: {hs.pagination.cursor_param}")
print(f"  pagination next_cursor_path: {hs.pagination.next_cursor_path}")
print(f"  pagination data_path   : {hs.pagination.data_path}")
print(f"  pagination page_size   : {hs.pagination.page_size}")


# ── 4. ConnectorRegistry.build_config() ──────────────────────────────────────
print("\n▶ ConnectorRegistry.build_config()  — definition → ApiConfig")
stripe_cfg: ApiConfig = ConnectorRegistry.build_config(
    "stripe", token="sk_test_abc123"
)
print(f"  name       : {stripe_cfg.name}")
print(f"  base_url   : {stripe_cfg.base_url}")
print(f"  auth type  : {stripe_cfg.auth.type}")
print(f"  pagination : strategy={stripe_cfg.pagination.strategy}, "
      f"page_size={stripe_cfg.pagination.page_size}, "
      f"data_path={stripe_cfg.pagination.data_path!r}")

notion_cfg: ApiConfig = ConnectorRegistry.build_config(
    "notion", token="secret_abc123"
)
print(f"\n  notion headers : {notion_cfg.headers}")  # includes Notion-Version
print(f"  notion cursor  : param={notion_cfg.pagination.cursor_param!r}, "
      f"path={notion_cfg.pagination.next_cursor_path!r}")

jira_cfg: ApiConfig = ConnectorRegistry.build_config("jira")
print(f"\n  jira  : auth={jira_cfg.auth.type}, "
      f"offset_param={jira_cfg.pagination.offset_param!r}, "
      f"data_path={jira_cfg.pagination.data_path!r}")


# ── 5. Apikit.from_name() — built-in ─────────────────────────────────────────
print("\n▶ Apikit.from_name()  — instantiate from a built-in connector name")

# jsonplaceholder needs no token — works live
jp_client = Apikit.from_name("jsonplaceholder")
print(f"  {jp_client!r}")
records = jp_client.fetch_records(
    "/posts", params={"_limit": 3}, show_progress=False)
print(f"  Live fetch /posts: {len(records)} records")
print(f"  First title: {records[0]['title'][:55]}...")

# Token-required connectors — show construction, skip live call
github_client = Apikit.from_name("github", token="ghp_YOUR_TOKEN_HERE")
print(f"\n  {github_client!r}")
print(f"  config.headers: {github_client.config.headers}")

shopify_client = Apikit.from_name("shopify", token="shpat_YOUR_TOKEN_HERE")
print(f"\n  {shopify_client!r}")
print(f"  pagination: strategy={shopify_client.config.pagination.strategy}, "
      f"page_size={shopify_client.config.pagination.page_size}")


# ── 6. ConnectorNotFoundError ────────────────────────────────────────────────
print("\n▶ ConnectorNotFoundError  — raised for unknown connector names")
try:
    ConnectorRegistry.get("does_not_exist")
except ConnectorNotFoundError as e:
    print(f"  Caught: {e}")


# ── 7. @ConnectorRegistry.register — custom connector ────────────────────────
print("\n▶ @ConnectorRegistry.register  — register a custom connector")


@ConnectorRegistry.register
def _my_internal_api() -> ConnectorDefinition:
    return ConnectorDefinition(
        name="my_internal_api",
        base_url="https://api.internal.example.com/v2",
        auth_type="bearer",
        default_headers={"X-App-Name": "data-pipeline"},
        pagination=PaginationConfig(
            strategy="page",
            page_param="page",
            limit_param="per_page",
            page_size=200,
        ),
        description="Internal company API — bearer token, page-number pagination.",
    )


# It's now in the registry alongside the built-ins
print(f"  Registry after registration: {ConnectorRegistry.list()}")

defn = ConnectorRegistry.get("my_internal_api")
print(f"  Custom connector: name={defn.name!r}, base_url={defn.base_url!r}")
print(f"  headers: {defn.default_headers}")

# Build a client from the custom connector
custom_client = Apikit.from_name("my_internal_api", token="internal-token-xyz")
print(f"  {custom_client!r}")
print(f"  pagination: {custom_client.config.pagination.strategy}, "
      f"page_size={custom_client.config.pagination.page_size}")


# ── 8. Register a second custom connector — cursor-paginated SaaS ────────────
print("\n▶ Registering a cursor-paginated SaaS connector")


@ConnectorRegistry.register
def _analytics_api() -> ConnectorDefinition:
    return ConnectorDefinition(
        name="analytics_api",
        base_url="https://api.analytics.example.com",
        auth_type="apikey",
        default_headers={"Accept": "application/json", "X-Client": "apikit"},
        pagination=PaginationConfig(
            strategy="cursor",
            cursor_param="next_token",
            next_cursor_path="meta.next_token",
            data_path="events",
            limit_param="limit",
            page_size=500,
        ),
        description="Analytics SaaS — API key header, cursor pagination.",
    )


analytics_cfg = ConnectorRegistry.build_config(
    "analytics_api", token="ak_live_xyz789"
)
print(f"  base_url   : {analytics_cfg.base_url}")
print(f"  auth type  : {analytics_cfg.auth.type}")
print(f"  data_path  : {analytics_cfg.pagination.data_path!r}")
print(f"  next_cursor: {analytics_cfg.pagination.next_cursor_path!r}")
# Usage:
# client = Apikit.from_name("analytics_api", token="ak_live_xyz789")
# records = client.fetch_records("/v1/events", paginate=True)


# ── 9. ConfigManager — save custom connectors to disk ────────────────────────
print("\n▶ ConfigManager.add_connector()  — persist a connector to TOML")
print("  (used for connectors that don't belong in the shared registry)")

with tempfile.TemporaryDirectory() as tmp:
    cfg_path = Path(tmp) / "apikit" / "config.toml"
    manager = ConfigManager(config_path=cfg_path)

    # Save two team-specific connectors
    manager.add_connector(
        name="staging_api",
        base_url="https://staging.api.example.com/v1",
        auth_type="bearer",
        token="stg_token_abc",
        store_secret_in_keyring=False,
    )
    manager.add_connector(
        name="partner_feed",
        base_url="https://feed.partner.io/api",
        auth_type="apikey",
        api_key="pf_key_live_xyz",
        store_secret_in_keyring=False,
    )

    print(f"  Saved connectors: {manager.list_connectors()}")

    # Load one back as ApiConfig
    staging_cfg = manager.get_api_config("staging_api")
    print(f"  staging_api: base_url={staging_cfg.base_url!r}, "
          f"auth={staging_cfg.auth.type!r}")

    # Build an Apikit client from the saved config
    staging_client = Apikit.from_config(staging_cfg)
    print(f"  {staging_client!r}")

    # Show the raw TOML entry
    raw = manager.get_connector_raw("partner_feed")
    print(f"  partner_feed raw entry: {raw}")

    # Remove one
    manager.remove_connector("partner_feed")
    print(f"  After remove: {manager.list_connectors()}")


# ── 10. All built-in connector configs side by side ──────────────────────────
print("\n▶ All built-in connector configs — quick reference")
print(f"  {'Name':<16} {'Auth':<8} {'Pagination':<8} {'Page size'}")
print(f"  {'-'*16} {'-'*8} {'-'*10} {'-'*9}")
for name in ConnectorRegistry.list():
    d = ConnectorRegistry.get(name)
    print(
        f"  {d.name:<16} {d.auth_type:<8} "
        f"{d.pagination.strategy:<10} {d.pagination.page_size}"
    )

print("\n✓ Connector registry examples complete.\n")

"""
10_inspect_dry_run_config.py
============================
Discover unknown APIs, preview requests before sending, and manage
persistent connector configs — without touching any real credentials.

Demonstrates:
  • client.inspect()     — probe an endpoint: schema, latency, pagination hints,
                           rate-limit state, and a ready-to-paste ApiConfig snippet
  • client.ainspect()   — async variant of inspect()
  • dry_run=True         — on fetch_records / post / fetch_to_file:
                           prints the full request plan, returns DryRunResult
  • DryRunResult.to_dict()  — machine-readable dry-run output
  • ConfigManager        — save a named connector to ~/.config/apikit/config.toml
                           (secrets stored in OS keyring)
  • Apikit.from_name()   — load a saved connector by name at runtime
  • ConnectorRegistry.list() — enumerate every built-in connector

Real endpoints used:
  • JSONPlaceholder — no auth required, always available
  • httpbin.org     — for dry-run header inspection

Run:
    python 10_inspect_dry_run_config.py
"""

import asyncio
import tempfile
from pathlib import Path

from iki_apikit import (
    Apikit,
    ApiConfig,
    AuthConfig,
    PaginationConfig,
    ConfigManager,
    ConnectorRegistry,
    InspectorResult,
    DryRunResult,
)

BASE = "https://jsonplaceholder.typicode.com"

print("=" * 60)
print("10 · INSPECT / DRY RUN / CONFIG MANAGER")
print("=" * 60)

# ── 1. inspect() — single probe, rich summary ─────────────────────────────────
print("\n▶ client.inspect('/posts')  — probe the endpoint")
client = Apikit(base_url=BASE, auth="none")

result: InspectorResult = client.inspect("/posts", params={"_limit": 5})
# Rich output was already printed to the terminal by inspect() itself.
# Access the structured result programmatically:
print(f"\n  [programmatic access]")
print(f"  status_code      : {result.status_code}")
print(f"  latency_ms       : {result.latency_ms:.1f} ms")
print(f"  record_count     : {result.record_count}")
print(f"  detected_pagination : {result.detected_pagination!r}")

schema = result.schema_sample()
print(f"  schema_sample()  : {schema}")

# ── 2. inspect() on a nested endpoint ────────────────────────────────────────
print("\n▶ client.inspect('/users')  — nested JSON, richer schema")
result_users = client.inspect("/users")
schema_users = result_users.schema_sample()
print(f"\n  [programmatic access]")
print(f"  record_count : {result_users.record_count}")
print(f"  schema fields: {list(schema_users.keys())[:8]} ...")

# ── 3. suggested_config() — copy-paste snippet ────────────────────────────────
print("\n▶ result.suggested_config()  — ready-to-paste ApiConfig")
print()
print(result_users.suggested_config())

# ── 4. inspect() — dry_run=True (no network call) ────────────────────────────
print("\n▶ client.inspect('/comments', dry_run=True)  — no network call")
dry_inspect = client.inspect("/comments", dry_run=True)
print(f"  dry_run      : {dry_inspect.dry_run}")
print(f"  status_code  : {dry_inspect.status_code}  (0 = not sent)")
print(f"  content_type : {dry_inspect.content_type!r}")

# ── 5. ainspect() — async variant ────────────────────────────────────────────
print("\n▶ client.ainspect('/todos')  — async probe")


async def demo_async_inspect():
    client_a = Apikit(base_url=BASE, auth="none")
    result_a = await client_a.ainspect("/todos", params={"_limit": 3})
    print(f"  async latency_ms  : {result_a.latency_ms:.1f} ms")
    print(f"  async record_count: {result_a.record_count}")

asyncio.run(demo_async_inspect())

# ── 6. fetch_records(dry_run=True) ───────────────────────────────────────────
print("\n▶ fetch_records('/albums', dry_run=True)  — inspect before you fetch")
cfg = ApiConfig(
    base_url=BASE,
    auth=AuthConfig(type="none"),
    pagination=PaginationConfig(
        strategy="offset",
        page_size=25,
        limit_param="_limit",
        offset_param="_start",
    ),
)
paginated_client = Apikit.from_config(cfg)

dry_result: DryRunResult = paginated_client.fetch_records(
    "/albums",
    params={"userId": 1},
    paginate=True,
    dry_run=True,
)
# Rich preview was already printed; access the dict for programmatic use:
info = dry_result.to_dict()
print(f"\n  [DryRunResult.to_dict()]")
print(f"  method               : {info['method']}")
print(f"  url                  : {info['url']}")
print(f"  params               : {info['params']}")
print(f"  auth_type            : {info['auth_type']}")
print(f"  pagination_strategy  : {info['pagination_strategy']}")
print(f"  page_size            : {info['page_size']}")

# ── 7. post(dry_run=True) — preview a write before committing ─────────────────
print("\n▶ fetch_records('/posts', dry_run=True)  — with bearer auth header")
bearer_client = Apikit(
    base_url="https://httpbin.org",
    auth="bearer",
    token="preview-only-token",
)
dry_post = bearer_client.fetch_records(
    "/get",
    params={"source": "apikit"},
    dry_run=True,
)
info2 = dry_post.to_dict()
print(
    f"\n  auth_type : {info2['auth_type']}  (Authorization header shown as ***)")

# ── 8. fetch_to_file with dry_run ────────────────────────────────────────────
print("\n▶ fetch_to_file('/posts', format='parquet', dry_run=True)")
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "posts.parquet"
    dry_file = paginated_client.fetch_records(
        "/posts",
        paginate=True,
        dry_run=True,
    )
    print(f"  No file written — dry_run skips the network and disk entirely")
    print(f"  Would have written to: {out}")

# ── 9. ConfigManager — save a named connector ─────────────────────────────────
print("\n▶ ConfigManager — persist a connector to ~/.config/apikit/config.toml")

# Use a temp path so this demo doesn't pollute your real config
with tempfile.TemporaryDirectory() as tmp:
    cfg_path = Path(tmp) / "apikit" / "config.toml"
    manager = ConfigManager(config_path=cfg_path)

    # Save a connector (token stored in keyring when available, else in file)
    manager.add_connector(
        name="my_internal_api",
        base_url="https://api.internal.example.com",
        auth_type="bearer",
        token="super-secret-token-abc123",
        store_secret_in_keyring=False,   # disable keyring for this demo
    )

    # Add a second connector
    manager.add_connector(
        name="partner_api",
        base_url="https://api.partner.com/v2",
        auth_type="apikey",
        api_key="pk_live_xyz789",
        store_secret_in_keyring=False,
    )

    print(f"  Config file written to : {cfg_path}")
    print(f"  Connectors saved       : {manager.list_connectors()}")

    # Load a connector back by name
    api_config = manager.get_api_config("my_internal_api")
    print(f"  Loaded 'my_internal_api': base_url={api_config.base_url!r}, "
          f"auth={api_config.auth.type!r}")

    # Build an Apikit directly from the saved ApiConfig object
    # (Apikit.from_name() does the same thing when using the default config path
    #  at ~/.config/apikit/config.toml — here we use manager.get_api_config()
    #  directly because we're pointing at a temp path)
    print("\n  Apikit.from_config(manager.get_api_config('my_internal_api'))")
    loaded_client = Apikit.from_config(api_config)
    print(f"  {loaded_client!r}")

    # Remove a connector
    manager.remove_connector("partner_api")
    print(f"\n  After remove: {manager.list_connectors()}")

# ── 10. ConnectorRegistry — enumerate built-ins ──────────────────────────────
print("\n▶ ConnectorRegistry.list()  — all built-in connectors")
built_ins = ConnectorRegistry.list()
for name in built_ins:
    defn = ConnectorRegistry.get(name)
    print(f"  {name:<20} {defn.base_url:<45} auth={defn.auth_type}")

print("\n✓ Inspect / Dry Run / Config Manager examples complete.\n")

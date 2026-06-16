"""
03_pagination.py
================
Every pagination strategy apikit supports, shown with working examples.

Demonstrates:
  • strategy="none"   — single page, no iteration
  • strategy="offset" — limit/offset style
  • strategy="page"   — page number / per_page style
  • strategy="cursor" — opaque cursor / next_token
  • strategy="link"   — RFC 5988 Link header (GitHub style)
  • Per-call overrides — change strategy without rebuilding the client

Real endpoints:
  • JSONPlaceholder supports _page / _limit params (page + offset style)
  • httpbin.org for showing the assembled query strings

Run:
    python 03_pagination.py
"""

from iki_apikit import ApiConfig, AuthConfig
from iki_apikit import Apikit, ApiConfig, PaginationConfig

print("=" * 60)
print("03 · PAGINATION STRATEGIES")
print("=" * 60)

# ── 1. No pagination ──────────────────────────────────────────────────────────
print("\n▶ strategy='none'  — fetch one page and stop")
client = Apikit(base_url="https://jsonplaceholder.typicode.com", auth="none")
records = client.fetch_records(
    "/posts", params={"_limit": 5}, paginate=False, show_progress=False)
print(f"  Got {len(records)} records (first page only)")

# ── 2. Offset pagination ──────────────────────────────────────────────────────
print("\n▶ strategy='offset'  — limit / offset style")
cfg = ApiConfig(
    base_url="https://jsonplaceholder.typicode.com",
    auth=AuthConfig_stub := __import__("iki_apikit").AuthConfig(type="none"),
    pagination=PaginationConfig(
        strategy="offset",
        page_size=10,
        limit_param="_limit",
        offset_param="_start",
        max_pages=3,           # cap at 3 pages = 30 records for this demo
    ),
)
client = Apikit.from_config(cfg)
records = client.fetch_records("/posts", paginate=True, show_progress=True)
print(f"  Fetched {len(records)} records across 3 offset pages (10 per page)")
print(f"  IDs range: {records[0]['id']} → {records[-1]['id']}")

# ── 3. Page-number pagination ─────────────────────────────────────────────────
print("\n▶ strategy='page'  — page number + per_page")

cfg = ApiConfig(
    base_url="https://jsonplaceholder.typicode.com",
    auth=AuthConfig(type="none"),
    pagination=PaginationConfig(
        strategy="page",
        page_size=10,
        page_param="_page",
        limit_param="_limit",
        max_pages=2,
    ),
)
client = Apikit.from_config(cfg)
records = client.fetch_records("/comments", paginate=True, show_progress=True)
print(f"  Fetched {len(records)} comments across 2 pages")

# ── 4. Cursor pagination (simulated with JSONPlaceholder) ─────────────────────
print("\n▶ strategy='cursor'  — cursor / next_token style")
print("  (Simulated: real cursor APIs include HubSpot, Stripe, Notion)")
print("  Showing config structure for a real cursor API:")
cfg_cursor = ApiConfig(
    base_url="https://api.hubapi.com",         # example — requires real token
    auth=AuthConfig(type="bearer", token="pat-na1-YOUR_TOKEN_HERE"),
    pagination=PaginationConfig(
        strategy="cursor",
        page_size=100,
        cursor_param="after",
        next_cursor_path="paging.next.after",  # dot-path into response JSON
        data_path="results",                   # where the records live
        limit_param="limit",
    ),
)
print(f"  Cursor param        : {cfg_cursor.pagination.cursor_param!r}")
print(f"  Next cursor at path : {cfg_cursor.pagination.next_cursor_path!r}")
print(f"  Records at path     : {cfg_cursor.pagination.data_path!r}")
print("  Call: client.fetch_records('/crm/v3/contacts', paginate=True)")

# ── 5. Link-header pagination (GitHub style) ──────────────────────────────────
print("\n▶ strategy='link'  — RFC 5988 Link header")
print("  This is used by GitHub, GitLab, Shopify, and others.")
print("  apikit parses:  Link: <https://...?page=2>; rel=\"next\"")
print("  Config for GitHub (replace token with a real PAT):")
cfg_link = ApiConfig(
    base_url="https://api.github.com",
    auth=AuthConfig(type="bearer", token="ghp_YOUR_TOKEN_HERE"),
    headers={"Accept": "application/vnd.github+json"},
    pagination=PaginationConfig(
        strategy="link",
        limit_param="per_page",
        page_size=100,
    ),
)
print(f"  Strategy  : {cfg_link.pagination.strategy!r}")
print(f"  Page size : {cfg_link.pagination.page_size}")
print("  Call: client.fetch_records('/orgs/myorg/repos', paginate=True)")

# ── 6. Using the built-in GitHub connector (link-header pre-configured) ───────
print("\n▶ Apikit.from_name('github')  — link-header pre-configured")
print("  client = Apikit.from_name('github', token='ghp_...')")
print("  df = client.fetch_polars('/repos/myorg/myrepo/issues', paginate=True)")
print("  → apikit automatically follows every Link: rel=next page")

# ── 7. Per-call strategy override ────────────────────────────────────────────
print("\n▶ Per-call strategy override — no client rebuild needed")
client = Apikit(base_url="https://jsonplaceholder.typicode.com", auth="none")
records = client.fetch_records(
    "/albums",
    paginate=True,
    strategy="offset",        # override for this call only
    page_size=10,
    show_progress=True,
)
print(f"  Per-call override: got {len(records)} albums with offset strategy")

# ── 8. data_path — unwrap nested response bodies ─────────────────────────────
print("\n▶ data_path — when records are nested inside the response")
print("  Example: response = {'data': {'items': [{...}, ...]}}")
print("  Use: client.fetch_records('/endpoint', data_path='data.items')")
print("  Works with ALL pagination strategies.")

print("\n✓ Pagination examples complete.\n")

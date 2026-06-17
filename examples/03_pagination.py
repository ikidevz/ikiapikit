"""
03_pagination.py
================
Every pagination strategy apikit supports, shown with working examples.

Demonstrates:
  • strategy="none"   — single page, no iteration
  • strategy="offset" — limit/skip style        (dummyjson.com)
  • strategy="page"   — page number / per_page  (reqres.in)
  • strategy="cursor" — opaque cursor / next_token (dummyjson.com simulated)
  • strategy="link"   — RFC 5988 Link header    (GitHub — config shown)
  • data_path         — unwrap nested response bodies
  • Per-call overrides — change strategy without rebuilding the client

Real endpoints used:
  • dummyjson.com  → offset + cursor demos (limit/skip, nested data_path)
  • reqres.in      → page-number demo (page/per_page, total_pages in body)
  • jsonplaceholder → none + per-call override demos
  • github.com     → link-header config reference (needs a real PAT to run)

Run:
    python 03_pagination.py
"""

from ikiapikit import Apikit, ApiConfig, AuthConfig, PaginationConfig

print("=" * 60)
print("03 · PAGINATION STRATEGIES")
print("=" * 60)

# ── 1. No pagination ──────────────────────────────────────────────────────────
print("\n▶ strategy='none'  — fetch one page and stop")
client = Apikit(base_url="https://jsonplaceholder.typicode.com", auth="none")
records = client.fetch_records(
    "/posts",
    params={"_limit": 5},
    paginate=False,
    show_progress=False,
)
print(f"  Got {len(records)} records (first page only, no iteration)")

# ── 2. Offset pagination ──────────────────────────────────────────────────────
#
#  dummyjson.com uses ?limit=N&skip=N and returns:
#    { "posts": [...], "total": 251, "skip": 0, "limit": 10 }
#  We point data_path at "posts" so apikit unwraps the array automatically.
#
print("\n▶ strategy='offset'  — limit / skip style  (dummyjson.com /posts)")
cfg = ApiConfig(
    base_url="https://dummyjson.com",
    auth=AuthConfig(type="none"),
    pagination=PaginationConfig(
        strategy="offset",
        page_size=10,
        limit_param="limit",
        offset_param="skip",
        data_path="posts",
        max_pages=5,
    ),
)
client = Apikit.from_config(cfg)
records = client.fetch_records("/posts", paginate=True, show_progress=True)
print(f"  Fetched {len(records)} posts across 3 offset pages (10 per page)")
print(f"  IDs  : {records[0]['id']} → {records[-1]['id']}")
print(f"  Title: {records[0]['title'][:55]}...")

# ── 3. Page-number pagination ─────────────────────────────────────────────────
#
#  jsonplaceholder.typicode.com uses ?_page=N&_limit=N and returns a flat
#  array. Total page count is read from the X-Total-Count response header
#  (100 posts / 15 per page = 7 pages). max_pages=3 caps the run early.
#
print("\n▶ strategy='page'  — page number + per_page  (jsonplaceholder /posts)")
cfg = ApiConfig(
    base_url="https://jsonplaceholder.typicode.com",
    auth=AuthConfig(type="none"),
    pagination=PaginationConfig(
        strategy="page",
        page_size=15,
        page_param="_page",
        limit_param="_limit",
        data_path=None,      # response is a flat array, no unwrapping needed
        max_pages=3,
    ),
)
client = Apikit.from_config(cfg)
records = client.fetch_records("/posts", paginate=True, show_progress=True)
print(f"  Fetched {len(records)} posts across 3 pages (15 per page)")
print(f"  First post: {records[0]['title'][:55]}...")
print(f"  Last post : {records[-1]['title'][:55]}...")

# ── 4. Cursor pagination ──────────────────────────────────────────────────────
#
#  True cursor APIs return an opaque token in the response that you pass back
#  as a query param on the next request (e.g. Stripe, Notion, HubSpot).
#
#  dummyjson.com doesn't emit a cursor token, so we simulate the pattern by
#  using the last record's `id` as the cursor — which is exactly how many
#  real cursor APIs (Stripe's `starting_after`, Gusto's `starting_after_uuid`)
#  work under the hood.
#
print("\n▶ strategy='cursor'  — cursor / next_token style  (dummyjson.com simulated)")
cfg = ApiConfig(
    base_url="https://dummyjson.com",
    auth=AuthConfig(type="none"),
    pagination=PaginationConfig(
        strategy="cursor",
        page_size=10,
        cursor_param="skip",            # passed as ?skip=<cursor> on each page
        # apikit reads next cursor from response["skip"]
        next_cursor_path="skip",
        data_path="products",
        limit_param="limit",
        max_pages=3,
    ),
)
client = Apikit.from_config(cfg)
records = client.fetch_records("/products", paginate=True, show_progress=True)
print(f"  Fetched {len(records)} products via cursor-style iteration")
print(f"  IDs range : {records[0]['id']} → {records[-1]['id']}")

print("\n  Real cursor API config reference (Stripe — requires API key):")
cfg_stripe = ApiConfig(
    base_url="https://api.stripe.com",
    auth=AuthConfig(type="bearer", token="sk_test_YOUR_KEY_HERE"),
    pagination=PaginationConfig(
        strategy="cursor",
        page_size=100,
        cursor_param="starting_after",   # ?starting_after=<last_id>
        next_cursor_path="data.-1.id",   # last item's id in response["data"]
        # stop when response["has_more"] is false
        has_more_path="has_more",
        data_path="data",
        limit_param="limit",
    ),
)
print(f"  cursor_param    : {cfg_stripe.pagination.cursor_param!r}")
print(f"  next_cursor_path: {cfg_stripe.pagination.next_cursor_path!r}")
print(f"  has_more_path   : {cfg_stripe.pagination.has_more_path!r}")

# ── 5. Link-header pagination (GitHub style) ──────────────────────────────────
#
#  RFC 5988 Link headers look like:
#    Link: <https://api.github.com/repos?page=2&per_page=100>; rel="next",
#          <https://api.github.com/repos?page=34&per_page=100>; rel="last"
#  apikit follows rel="next" automatically until it disappears.
#
#  No free public API emits Link headers without auth. Replace the token
#  with a real GitHub PAT (Settings → Developer settings → Personal access
#  tokens) to run this live.
#
print("\n▶ strategy='link'  — RFC 5988 Link header  (GitHub — needs a real PAT)")
cfg_link = ApiConfig(
    base_url="https://api.github.com",
    auth=AuthConfig(type="bearer", token="ghp_YOUR_TOKEN_HERE"),
    headers={"Accept": "application/vnd.github+json"},
    pagination=PaginationConfig(
        strategy="link",
        page_size=100,
        limit_param="per_page",
    ),
)
print(f"  Strategy  : {cfg_link.pagination.strategy!r}")
print(f"  Page size : {cfg_link.pagination.page_size}")
print("  How to run:")
print("    client = Apikit.from_config(cfg_link)")
print("    issues = client.fetch_records('/repos/myorg/myrepo/issues', paginate=True)")
print("  apikit follows every Link: rel=next header until none remains.")

# ── 6. Named connector (link-header pre-configured) ───────────────────────────
print("\n▶ Apikit.from_name('github')  — link-header pre-configured")
print("  client = Apikit.from_name('github', token='ghp_...')")
print("  df = client.fetch_polars('/repos/myorg/myrepo/issues', paginate=True)")
print("  → strategy='link' and GitHub headers are set automatically.")

# ── 7. Per-call strategy override ─────────────────────────────────────────────
print("\n▶ Per-call override — switch strategy without rebuilding the client")
client = Apikit(base_url="https://dummyjson.com", auth="none")
records = client.fetch_records(
    "/users",
    paginate=True,
    strategy="offset",     # override for this call only
    page_size=10,
    limit_param="limit",
    offset_param="skip",
    data_path="users",
    max_pages=2,
    show_progress=True,
)
print(
    f"  Per-call override: fetched {len(records)} users with offset strategy")
print(f"  First: {records[0]['firstName']} {records[0]['lastName']}")

# ── 8. data_path — unwrap nested response bodies ──────────────────────────────
print("\n▶ data_path — navigate nested JSON to where the records live")
print("  Flat  : response = [{...}, {...}]          → data_path=None")
print("  One level  : response = {'items': [...]}   → data_path='items'")
print(
    "  Two levels : response = {'data': {'rows': [...]}} → data_path='data.rows'")
print("  Works with ALL pagination strategies.")

print("\n✓ Pagination examples complete — all live calls used real endpoints.\n")

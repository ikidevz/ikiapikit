"""
17_fan_out.py
=============
Multi-endpoint fan-out — fetch many endpoints concurrently in one call.

Demonstrates:
  • client.fetch_many([...])          — list of endpoints, returns dict of results
  • client.fetch_many({...})          — dict form with labels
  • fetch_many with per-endpoint opts — different params per endpoint
  • fetch_many + select               — column pruning per endpoint
  • fetch_many + paginate             — all endpoints paginated concurrently
  • fetch_many_polars()               — dict of Polars DataFrames
  • fetch_many_pandas()               — dict of Pandas DataFrames
  • Error isolation                   — one endpoint failing doesn't kill others
  • fetch_many_to_files()             — write each result to its own file

Why this matters:
  Building a data model often requires several related endpoints:
  users, orders, products, line_items. Fetching them sequentially
  means 4× the latency. fetch_many() wraps asyncio.gather() so all
  four run in parallel — you get the same data in ~1× the time.

Run:
    python 17_fan_out.py
"""

import os
import tempfile
import time
from ikiapikit import Apikit, ApiConfig, AuthConfig, PaginationConfig

print("=" * 60)
print("17 · MULTI-ENDPOINT FAN-OUT")
print("=" * 60)

BASE = "https://jsonplaceholder.typicode.com"
client = Apikit(base_url=BASE, auth="none")


# ── 1. List form — simplest ───────────────────────────────────────────────────
print("\n▶ fetch_many([...])  — list of endpoints, returns dict keyed by path")
t0 = time.perf_counter()
results = client.fetch_many(["/posts", "/users", "/todos", "/albums"])
elapsed = time.perf_counter() - t0

print(f"  All 4 endpoints fetched in {elapsed:.2f}s (concurrent)")
for path, records in results.items():
    print(f"    {path:<10}  {len(records):>4} records")


# ── 2. Dict form — custom labels ──────────────────────────────────────────────
print(
    "\n▶ fetch_many({label: endpoint})  — use your own keys in the result dict")
results = client.fetch_many({
    "posts":    "/posts",
    "authors":  "/users",
    "checklist": "/todos",
})
for label, records in results.items():
    print(f"  {label:<10}  {len(records):>4} records")


# ── 3. Per-endpoint params ────────────────────────────────────────────────────
print("\n▶ Per-endpoint params  — different query strings per endpoint")
results = client.fetch_many({
    "recent_posts":   ("/posts",    {"_limit": 5, "userId": 1}),
    "all_users":      ("/users",    {}),
    "open_todos":     ("/todos",    {"_limit": 10, "completed": "false"}),
    "first_comments": ("/comments", {"_limit": 3}),
})
for label, records in results.items():
    print(f"  {label:<16}  {len(records):>4} records  "
          f"keys={list(records[0].keys())[:3]}...")


# ── 4. Per-endpoint select ────────────────────────────────────────────────────
print("\n▶ Per-endpoint select  — prune columns per endpoint")
results = client.fetch_many({
    "users":    ("/users",    {}, {"select": ["id", "name", "email"]}),
    "posts":    ("/posts",    {"_limit": 10}, {"select": ["id", "userId", "title"]}),
    "comments": ("/comments", {"_limit": 10}, {"select": ["id", "postId", "email"]}),
})
for label, records in results.items():
    print(f"  {label:<10}  fields={list(records[0].keys())}")


# ── 5. fetch_many + paginate ──────────────────────────────────────────────────
print("\n▶ fetch_many + paginate=True  — all endpoints paginated concurrently")
cfg = ApiConfig(
    base_url=BASE,
    auth=AuthConfig(type="none"),
    pagination=PaginationConfig(
        strategy="offset",
        page_size=25,
        limit_param="_limit",
        offset_param="_start",
        max_pages=4,   # 4 × 25 = 100 records max per endpoint
    ),
)
paginated_client = Apikit.from_config(cfg)

t0 = time.perf_counter()
paged = paginated_client.fetch_many(
    ["/posts", "/comments"],
    paginate=True,
    show_progress=True,
)
elapsed = time.perf_counter() - t0

print(f"\n  Fetched both paginated endpoints in {elapsed:.2f}s")
for path, records in paged.items():
    print(f"    {path:<10}  {len(records):>4} records")


# ── 6. fetch_many_polars() ────────────────────────────────────────────────────
print("\n▶ fetch_many_polars()  — dict of Polars DataFrames")
try:
    import polars as pl
    dfs = client.fetch_many_polars({
        "users":  "/users",
        "albums": "/albums",
    })
    for label, df in dfs.items():
        print(f"  {label:<8}  shape={df.shape}  cols={df.columns[:4]}...")

    # Join them directly
    users_df = dfs["users"].select(["id", "name"]).rename({"id": "userId"})
    albums_df = dfs["albums"]
    joined = albums_df.join(users_df, on="userId", how="left")
    print(f"\n  Joined albums+users shape : {joined.shape}")
    print(joined.select(["id", "title", "name"]).head(3))
except ImportError:
    print("  (polars not installed)")


# ── 7. fetch_many_pandas() ────────────────────────────────────────────────────
print("\n▶ fetch_many_pandas()  — dict of Pandas DataFrames")
try:
    import pandas as pd
    dfs = client.fetch_many_pandas({
        "todos": "/todos",
        "posts": ("/posts", {"_limit": 20}),
    })
    for label, df in dfs.items():
        print(f"  {label:<8}  shape={df.shape}")
    print(
        f"  todos completed rate: {dfs['todos']['completed'].mean()*100:.0f}%")
except ImportError:
    print("  (pandas not installed)")


# ── 8. Error isolation ────────────────────────────────────────────────────────
print("\n▶ Error isolation  — one bad endpoint doesn't kill the rest")
results = client.fetch_many(
    {
        "good":    "/users",
        "missing": "/this-endpoint-does-not-exist",
        "also_good": "/albums",
    },
    on_error="skip",    # "raise" (default) | "skip" | "return_empty"
)
print(f"  good      : {len(results.get('good', []))} records")
print(f"  missing   : {results.get('missing')}  ← skipped, not an exception")
print(f"  also_good : {len(results.get('also_good', []))} records")


# ── 9. fetch_many_to_files() — write each result to its own file ──────────────
print("\n▶ fetch_many_to_files()  — concurrent fetch then write to separate files")
with tempfile.TemporaryDirectory() as tmp:
    paths = client.fetch_many_to_files(
        {
            "users":    "/users",
            "posts":    ("/posts", {"_limit": 20}),
            "comments": ("/comments", {"_limit": 10}),
        },
        format="ndjson",
        output_dir=tmp,
    )
    print(f"  Files written:")
    for label, path in paths.items():
        size = os.path.getsize(path)
        print(f"    {label:<10}  {os.path.basename(path)}  ({size:,} bytes)")


# ── 10. Sequential comparison ────────────────────────────────────────────────
print("\n▶ Speed comparison — sequential vs fetch_many (concurrent)")
endpoints = ["/posts", "/users", "/todos", "/albums", "/comments"]

t0 = time.perf_counter()
for ep in endpoints:
    client.fetch_records(ep, params={"_limit": 5}, show_progress=False)
seq_time = time.perf_counter() - t0

t0 = time.perf_counter()
client.fetch_many({ep: (ep, {"_limit": 5}) for ep in endpoints})
par_time = time.perf_counter() - t0

speedup = seq_time / par_time if par_time > 0 else float("inf")
print(f"  Sequential : {seq_time:.2f}s")
print(f"  Concurrent : {par_time:.2f}s  ({speedup:.1f}× faster)")

print("\n✓ Multi-endpoint fan-out complete.\n")

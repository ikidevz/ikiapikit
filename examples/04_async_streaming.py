"""
04_async_streaming.py
=====================
Async fetching, concurrent requests, and record-level streaming.

Demonstrates:
  • afetch_records()  — async version of fetch_records
  • afetch_polars()   — async → Polars DataFrame
  • afetch_pandas()   — async → Pandas DataFrame
  • asyncio.gather()  — three endpoints fetched concurrently
  • astream()         — yield records one at a time (memory-efficient)
  • Early exit from a stream

Run:
    python 04_async_streaming.py
"""

import asyncio
import time
from iki_apikit import Apikit

BASE = "https://jsonplaceholder.typicode.com"


# ── 1. Basic async fetch ──────────────────────────────────────────────────────
async def demo_basic_async():
    print("\n▶ afetch_records()  — async single endpoint")
    client = Apikit(base_url=BASE, auth="none")
    records = await client.afetch_records("/posts", params={"_limit": 5}, show_progress=False)
    print(f"  Got {len(records)} posts asynchronously")
    print(f"  First: {records[0]['title'][:55]}...")


# ── 2. Concurrent fetches ─────────────────────────────────────────────────────
async def demo_concurrent():
    print("\n▶ asyncio.gather()  — three endpoints at once")
    client = Apikit(base_url=BASE, auth="none")

    start = time.perf_counter()
    posts, users, todos = await asyncio.gather(
        client.afetch_records(
            "/posts",  params={"_limit": 20}, show_progress=False),
        client.afetch_records("/users",  show_progress=False),
        client.afetch_records(
            "/todos",  params={"_limit": 20}, show_progress=False),
    )
    elapsed = time.perf_counter() - start

    print(f"  posts={len(posts)}  users={len(users)}  todos={len(todos)}")
    print(f"  All three fetched concurrently in {elapsed:.2f}s")

    # Compare with sequential (estimate)
    print("  (sequential would take ~3× longer)")


# ── 3. Async Polars / Pandas ──────────────────────────────────────────────────
async def demo_async_dataframes():
    print("\n▶ afetch_polars() / afetch_pandas()")
    client = Apikit(base_url=BASE, auth="none")

    try:
        import polars as pl
        df = await client.afetch_polars("/users", show_progress=False)
        print(f"  Polars shape  : {df.shape}")
        print(f"  Columns       : {df.columns[:5]}...")
    except ImportError:
        print("  (polars not installed)")

    try:
        import pandas as pd
        df = await client.afetch_pandas("/todos", params={"_limit": 10}, show_progress=False)
        print(f"  Pandas shape  : {df.shape}")
    except ImportError:
        print("  (pandas not installed)")


# ── 4. Async streaming ────────────────────────────────────────────────────────
async def demo_streaming():
    print("\n▶ astream()  — yield records one at a time")
    from iki_apikit import ApiConfig, AuthConfig, PaginationConfig

    cfg = ApiConfig(
        base_url=BASE,
        auth=AuthConfig(type="none"),
        pagination=PaginationConfig(
            strategy="offset",
            page_size=20,
            limit_param="_limit",
            offset_param="_start",
            max_pages=3,
        ),
    )
    client = Apikit.from_config(cfg)

    count = 0
    user_ids = set()
    async for record in client.astream("/posts", paginate=True):
        count += 1
        user_ids.add(record.get("userId"))

    print(f"  Streamed {count} records total")
    print(f"  Unique userId values: {sorted(user_ids)}")
    print("  ✓ Memory usage: only one page in memory at a time")


# ── 5. Early exit from stream ─────────────────────────────────────────────────
async def demo_early_exit():
    print("\n▶ astream() with early exit  — stop as soon as condition is met")
    from iki_apikit import ApiConfig, AuthConfig, PaginationConfig

    cfg = ApiConfig(
        base_url=BASE,
        auth=AuthConfig(type="none"),
        pagination=PaginationConfig(
            strategy="offset",
            page_size=10,
            limit_param="_limit",
            offset_param="_start",
            max_pages=100,
        ),
    )
    client = Apikit.from_config(cfg)

    target_user_id = 5
    found = []
    pages_consumed = 0

    async for record in client.astream("/posts", paginate=True):
        if record.get("userId") == target_user_id:
            found.append(record)
        # Stop as soon as we've found 3 posts from user 5
        if len(found) >= 3:
            break

    print(f"  Found {len(found)} posts from userId={target_user_id}")
    print(f"  Stopped early — no wasted requests beyond what was needed")


# ── 6. Async file write ───────────────────────────────────────────────────────
async def demo_async_file():
    print("\n▶ afetch_to_file()  — async fetch then write to disk")
    import tempfile
    import os
    from iki_apikit import ApiConfig, AuthConfig, PaginationConfig

    cfg = ApiConfig(
        base_url=BASE,
        auth=AuthConfig(type="none"),
        pagination=PaginationConfig(
            strategy="offset",
            page_size=25,
            limit_param="_limit",
            offset_param="_start",
            max_pages=2,
        ),
    )
    client = Apikit.from_config(cfg)

    with tempfile.TemporaryDirectory() as tmpdir:
        out = os.path.join(tmpdir, "posts.ndjson")
        path = await client.afetch_to_file(
            "/posts",
            format="ndjson",
            file_path=out,
            paginate=True,
        )
        size = os.path.getsize(out)
        with open(out) as f:
            lines = f.readlines()
        print(f"  Wrote {len(lines)} records to ndjson ({size:,} bytes)")


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    print("=" * 60)
    print("04 · ASYNC SUPPORT & STREAMING")
    print("=" * 60)
    await demo_basic_async()
    await demo_concurrent()
    await demo_async_dataframes()
    await demo_streaming()
    await demo_early_exit()
    await demo_async_file()
    print("\n✓ Async & streaming examples complete.\n")


if __name__ == "__main__":
    asyncio.run(main())

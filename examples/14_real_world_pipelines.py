"""
14_real_world_pipelines.py
==========================
End-to-end pipelines that combine auth, pagination, transforms,
output formats, dry-run, and inspection the way you'd actually use
them in production.

Pipelines in this file:
  A. API → Parquet data lake          (paginated fetch → parquet on disk)
  B. Multi-endpoint concurrent ETL    (async gather → merged Polars DataFrame)
  C. Incremental sync with cursor     (cursor pagination, last-seen ID guard)
  D. Schema discovery before pipeline (inspect → auto-configure → fetch)
  E. API → dbt seed + YAML            (fetch → DbtExporter, ready to dbt seed)
  F. Webhook → DataFrame pipeline     (receive → validate → Polars analysis)
  G. Dry-run CI gate                  (dry_run=True to assert config is correct)

All live calls use JSONPlaceholder or the countries GraphQL API.
Sections for Stripe / HubSpot / GitHub show real config but skip live calls.

Run:
    python 14_real_world_pipelines.py
"""

import asyncio
import hashlib
import hmac
import json
import tempfile
import time
from pathlib import Path

import polars as pl

from ikiapikit import (
    Apikit,
    ApiConfig,
    AuthConfig,
    PaginationConfig,
    DbtExporter,
    WebhookReceiver,
    GitHubWebhookValidator,
    DryRunResult,
)

BASE = "https://jsonplaceholder.typicode.com"


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline A — Paginated fetch → Parquet data lake
# ─────────────────────────────────────────────────────────────────────────────
def pipeline_a():
    print("─" * 60)
    print("Pipeline A · Paginated fetch → Parquet data lake")
    print("─" * 60)

    cfg = ApiConfig(
        base_url=BASE,
        auth=AuthConfig(type="none"),
        pagination=PaginationConfig(
            strategy="offset",
            page_size=25,
            limit_param="_limit",
            offset_param="_start",
            max_pages=4,          # 100 records total
        ),
    )
    client = Apikit.from_config(cfg)

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "posts.parquet"

        # One-liner: fetch all pages and write to Parquet
        client.fetch_to_file(
            "/posts",
            format="parquet",
            file_path=out,
            paginate=True,
        )

        # Verify with Polars
        df = pl.read_parquet(out)
        print(f"  Rows written  : {df.height}")
        print(f"  Columns       : {df.columns}")
        print(f"  Unique users  : {df['userId'].n_unique()}")
        print(f"  File size     : {out.stat().st_size:,} bytes")
        print(f"  Sample:\n{df.select(['id', 'userId', 'title']).head(3)}")

    print()


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline B — Multi-endpoint concurrent ETL → merged DataFrame
# ─────────────────────────────────────────────────────────────────────────────
async def pipeline_b():
    print("─" * 60)
    print("Pipeline B · Concurrent fetch → merged Polars DataFrame")
    print("─" * 60)

    client = Apikit(base_url=BASE, auth="none")

    start = time.perf_counter()
    users_raw, posts_raw, todos_raw = await asyncio.gather(
        client.afetch_records("/users", show_progress=False),
        client.afetch_records(
            "/posts", params={"_limit": 20}, show_progress=False),
        client.afetch_records(
            "/todos", params={"_limit": 20}, show_progress=False),
    )
    elapsed = time.perf_counter() - start
    print(f"  Fetched 3 endpoints concurrently in {elapsed:.2f}s")

    # Build DataFrames
    users = pl.DataFrame(users_raw).select(["id", "name", "email", "username"])
    posts = pl.DataFrame(posts_raw).rename({"id": "post_id", "userId": "id"})
    todos = pl.DataFrame(todos_raw).rename({"id": "todo_id", "userId": "id"})

    # Join: users ← posts
    users_with_posts = (
        users
        .join(posts.select(["id", "post_id", "title"]), on="id", how="left")
        .rename({"title": "post_title"})
    )
    print(f"  users joined with posts : {users_with_posts.shape}")

    # Join: users ← todos (count complete tasks per user)
    todo_summary = (
        todos
        .group_by("id")
        .agg([
            pl.len().alias("total_todos"),
            pl.col("completed").sum().alias("completed_todos"),
        ])
    )
    user_summary = users.join(todo_summary, on="id", how="left").fill_null(0)
    print(f"  user todo summary:\n{user_summary.head(4)}")

    print()


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline C — Incremental sync with cursor guard
# ─────────────────────────────────────────────────────────────────────────────
def pipeline_c():
    print("─" * 60)
    print("Pipeline C · Incremental sync — only fetch records newer than last seen")
    print("─" * 60)

    # Simulate a state file that tracks the last synced ID
    with tempfile.TemporaryDirectory() as tmp:
        state_file = Path(tmp) / "sync_state.json"

        def load_state() -> dict:
            if state_file.exists():
                return json.loads(state_file.read_text())
            return {"last_id": 0, "total_synced": 0}

        def save_state(state: dict) -> None:
            state_file.write_text(json.dumps(state))

        client = Apikit(base_url=BASE, auth="none")

        # ── Run 1: first sync, pick up everything ─────────────────────────────
        state = load_state()
        print(f"\n  Run 1 — last_id={state['last_id']}")

        all_records = client.fetch_records(
            "/posts", params={"_limit": 10}, show_progress=False
        )
        new_records = [r for r in all_records if r["id"] > state["last_id"]]
        if new_records:
            state["last_id"] = max(r["id"] for r in new_records)
            state["total_synced"] += len(new_records)
            save_state(state)

        print(f"  New records   : {len(new_records)}")
        print(f"  Last ID now   : {state['last_id']}")
        print(f"  Total synced  : {state['total_synced']}")

        # ── Run 2: incremental — simulate 5 more records arriving ─────────────
        all_records_2 = client.fetch_records(
            "/posts", params={"_limit": 15}, show_progress=False
        )
        state = load_state()
        print(f"\n  Run 2 — last_id={state['last_id']} (incremental)")

        new_records_2 = [
            r for r in all_records_2 if r["id"] > state["last_id"]]
        if new_records_2:
            state["last_id"] = max(r["id"] for r in new_records_2)
            state["total_synced"] += len(new_records_2)
            save_state(state)

        print(f"  New records   : {len(new_records_2)}")
        print(f"  Last ID now   : {state['last_id']}")
        print(f"  Total synced  : {state['total_synced']}")

    print()


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline D — Schema discovery → auto-configure → fetch
# ─────────────────────────────────────────────────────────────────────────────
def pipeline_d():
    print("─" * 60)
    print("Pipeline D · Inspect endpoint → read schema → fetch & transform")
    print("─" * 60)

    client = Apikit(base_url=BASE, auth="none")

    # Step 1: probe the endpoint before committing to a full fetch
    print("\n  Step 1: inspect /users")
    result = client.inspect("/users", params={"_limit": 2})

    print(f"\n  latency_ms     : {result.latency_ms:.1f}")
    print(f"  record_count   : {result.record_count}")
    print(f"  detected_pag   : {result.detected_pagination!r}")

    schema = result.schema_sample()
    print(f"  schema fields  : {list(schema.keys())}")

    # Step 2: decide columns to keep based on schema
    string_cols = [k for k, v in schema.items() if v == "str"]
    int_cols = [k for k, v in schema.items() if v == "int"]
    print(
        f"\n  Step 2: identified {len(string_cols)} str cols, {len(int_cols)} int cols")

    # Step 3: full fetch now that we know what we're dealing with
    print("\n  Step 3: full fetch with flatten=True")
    df = client.fetch_polars("/users", flatten=True, show_progress=False)
    print(f"  DataFrame shape: {df.shape}")

    # Step 4: select only the top-level (non-nested) columns
    top_level = [c for c in df.columns if "_" not in c]
    print(f"  Top-level cols : {top_level}")
    print(f"  Sample:\n{df.select(top_level).head(3)}")

    print()


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline E — Fetch → dbt seed artifacts
# ─────────────────────────────────────────────────────────────────────────────
def pipeline_e():
    print("─" * 60)
    print("Pipeline E · Fetch API data → dbt seed + sources.yml + schema.yml")
    print("─" * 60)

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

    with tempfile.TemporaryDirectory() as tmp:
        exporter = DbtExporter(output_dir=tmp)

        # Fetch + export in one shot
        paths = exporter.export_from_client(
            client=client,
            endpoint="/comments",
            name="jp_comments",
            database="raw",
            schema="jsonplaceholder",
            description="Comments from JSONPlaceholder demo API",
            tags=["demo", "jsonplaceholder"],
            meta={"owner": "data-eng", "pii": False},
            flatten=True,
        )

        # Verify what was written
        seed_lines = paths["seed"].read_text().splitlines()
        print(f"  Seed rows (incl. header): {len(seed_lines)}")
        print(f"  Seed header: {seed_lines[0]}")

        schema_text = paths["schema"].read_text()
        print(f"\n  schema.yml (first 12 lines):")
        for line in schema_text.splitlines()[:12]:
            print(f"    {line}")

        sources_text = paths["sources"].read_text()
        print(f"\n  sources.yml (first 10 lines):")
        for line in sources_text.splitlines()[:10]:
            print(f"    {line}")

        print(f"\n  Next steps:")
        print(f"    cp {paths['seed']} your_dbt_project/seeds/")
        print(f"    cp {paths['schema']} your_dbt_project/models/")
        print(f"    cp {paths['sources']} your_dbt_project/models/")
        print(f"    dbt seed && dbt run")

    print()


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline F — Webhook → validate → DataFrame analysis
# ─────────────────────────────────────────────────────────────────────────────
def pipeline_f():
    print("─" * 60)
    print("Pipeline F · Webhook receiver → validate → Polars analysis")
    print("─" * 60)

    import httpx

    SECRET = "pipeline_f_secret"

    def _sign(payload: bytes) -> str:
        digest = hmac.new(SECRET.encode(), payload, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    receiver = WebhookReceiver(
        port=9191,
        path="/events",
        validator=GitHubWebhookValidator(SECRET),
        provider="ecommerce",
    )
    receiver.start()
    time.sleep(0.1)

    # Simulate 10 order events arriving
    import random
    random.seed(42)
    statuses = ["paid", "paid", "paid", "refunded", "paid",
                "failed", "paid", "paid", "refunded", "paid"]
    amounts = [1200, 450, 8900, 3300, 750, 2100, 6600, 980, 4400, 1550]

    for i, (status, amount) in enumerate(zip(statuses, amounts), 1):
        body = {
            "order_id": f"ORD-{1000+i}",
            "status": status,
            "amount_php": amount,
            "customer_id": f"CUST-{random.randint(1, 5):03d}",
        }
        raw = json.dumps(body).encode()
        httpx.post(
            f"http://127.0.0.1:9191/events",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _sign(raw),
            },
            timeout=3,
        )
        time.sleep(0.02)

    receiver.stop()

    # Analyse with Polars
    df = receiver.to_polars()
    print(f"\n  Events captured: {df.height}")

    # Unnest the payload column (it's a struct/dict)
    orders = pl.DataFrame([e.payload for e in receiver.events])
    print(f"  Orders DataFrame:\n{orders}")

    summary = (
        orders
        .group_by("status")
        .agg([
            pl.len().alias("count"),
            pl.col("amount_php").sum().alias("total_php"),
        ])
        .sort("total_php", descending=True)
    )
    print(f"\n  Revenue by status:\n{summary}")

    total = orders.filter(pl.col("status") == "paid")["amount_php"].sum()
    print(f"\n  Total paid revenue: ₱{total:,}")

    print()


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline G — Dry-run CI gate
# (assert your config is correct before running in production)
# ─────────────────────────────────────────────────────────────────────────────
def pipeline_g():
    print("─" * 60)
    print("Pipeline G · Dry-run CI gate — assert config before production run")
    print("─" * 60)

    cfg = ApiConfig(
        base_url="https://api.stripe.com/v1",
        auth=AuthConfig(type="bearer", token="sk_live_YOUR_KEY"),
        pagination=PaginationConfig(
            strategy="cursor",
            cursor_param="starting_after",
            next_cursor_path="data.-1.id",
            data_path="data",
            limit_param="limit",
            page_size=100,
        ),
    )
    client = Apikit.from_config(cfg)

    # In CI, run dry_run=True to validate config shape — no network call made
    result: DryRunResult = client.fetch_records(
        "/customers",
        paginate=True,
        dry_run=True,
    )

    info = result.to_dict()

    # Assert the things that must be true before you deploy
    assert info["method"] == "GET",                        "method must be GET"
    assert "stripe.com" in info["url"],                    "wrong base URL"
    assert info["auth_type"] == "bearer",                  "must use bearer auth"
    assert info["pagination_strategy"] == "cursor",        "must use cursor pagination"
    assert info["page_size"] == 100,                       "page_size must be 100"

    print(f"\n  All CI assertions passed ✓")
    print(f"  method     : {info['method']}")
    print(f"  url        : {info['url']}")
    print(f"  auth_type  : {info['auth_type']}")
    print(
        f"  pagination : {info['pagination_strategy']} / {info['page_size']} per page")
    print(f"\n  Safe to deploy — no network call was made during validation.")

    print()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 60)
print("14 · REAL-WORLD PIPELINES")
print("=" * 60)

pipeline_a()
asyncio.run(pipeline_b())
pipeline_c()
pipeline_d()
pipeline_e()
pipeline_f()
pipeline_g()

print("✓ All pipelines complete.\n")

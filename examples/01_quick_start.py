"""
01_quick_start.py
=================
The fastest way to get data out of an API.

Demonstrates:
  • fetch_records()  — raw list of dicts
  • fetch_polars()   — Polars DataFrame with nested-JSON flattening
  • fetch_pandas()   — Pandas DataFrame

Uses JSONPlaceholder (https://jsonplaceholder.typicode.com) — no auth needed.

Run:
    python 01_quick_start.py
"""

from iki_apikit import Apikit

# ── 1. Create a client ────────────────────────────────────────────────────────
client = Apikit(base_url="https://jsonplaceholder.typicode.com", auth="none")
# Equivalent shorthand using the built-in connector:
# client = Apikit.from_name("jsonplaceholder")

print("=" * 60)
print("01 · QUICK START")
print("=" * 60)

# ── 2. Fetch raw records ──────────────────────────────────────────────────────
print("\n▶ fetch_records('/posts', params={'_limit': 5})")
records = client.fetch_records(
    "/posts", params={"_limit": 5}, show_progress=False)
print(f"  Got {len(records)} records")
print(f"  First record keys : {list(records[0].keys())}")
print(f"  First title       : {records[0]['title'][:50]}...")

# ── 3. Fetch as Polars DataFrame ──────────────────────────────────────────────
print("\n▶ fetch_polars('/users')")
try:
    import polars as pl
    df = client.fetch_polars("/users", show_progress=False)
    print(f"  Shape   : {df.shape}")
    print(f"  Columns : {df.columns}")
    print(f"  Sample  :\n{df.select(['id', 'name', 'email']).head(3)}")
except ImportError:
    print("  (polars not installed — run: pip install polars)")

# ── 4. Fetch as Pandas DataFrame ─────────────────────────────────────────────
print("\n▶ fetch_pandas('/todos', params={'_limit': 10})")
try:
    import pandas as pd
    df = client.fetch_pandas(
        "/todos", params={"_limit": 10}, show_progress=False)
    print(f"  Shape         : {df.shape}")
    completed_pct = df["completed"].mean() * 100
    print(f"  % completed   : {completed_pct:.0f}%")
    print(
        f"  Sample:\n{df[['id', 'title', 'completed']].head(3).to_string(index=False)}")
except ImportError:
    print("  (pandas not installed — run: pip install pandas)")

# ── 5. Nested JSON flattening demo ────────────────────────────────────────────
print("\n▶ Nested JSON flattening — /users (has nested address/company objects)")
try:
    import polars as pl
    df = client.fetch_polars("/users", flatten=True, show_progress=False)
    nested_cols = [c for c in df.columns if "__" in c]
    print(f"  Flattened columns ({len(nested_cols)} nested):")
    for col in nested_cols[:8]:
        print(f"    {col}")
    if len(nested_cols) > 8:
        print(f"    ... and {len(nested_cols) - 8} more")
except ImportError:
    pass

print("\n✓ Quick start complete.\n")

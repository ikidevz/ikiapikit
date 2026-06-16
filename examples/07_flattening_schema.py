"""
07_flattening_schema.py
=======================
Deep-nested JSON flattening and automatic schema inference.

Demonstrates:
  • _flatten_dict()       — flatten a single dict (custom separator)
  • _flatten_records()    — flatten a list of records
  • records_to_polars()   — list → Polars DataFrame, auto-flattened
  • records_to_pandas()   — list → Pandas DataFrame, auto-flattened
  • infer_polars_schema() — detect column types from first 100 records
  • infer_pandas_schema() — detect dtypes from first 100 records
  • Lists inside records are serialized to JSON strings

Run:
    python 07_flattening_schema.py
"""

import json
from iki_apikit import (
    Apikit,
    _flatten_dict,
    _flatten_records,
    records_to_polars,
    records_to_pandas,
    infer_polars_schema,
)

print("=" * 60)
print("07 · JSON FLATTENING & SCHEMA INFERENCE")
print("=" * 60)

# ── 1. _flatten_dict — single record ──────────────────────────────────────────
print("\n▶ _flatten_dict()  — flatten nested keys with '__' separator")
raw = {
    "id": 42,
    "user": {
        "name": "Alice",
        "address": {
            "city": "Davao",
            "country": "PH",
        },
    },
    "tags": ["python", "data"],   # lists become JSON strings
    "score": 98.6,
}
flat = _flatten_dict(raw)
print("  Input  (nested):")
print(f"  {json.dumps(raw, indent=2)[:200]}")
print("  Output (flat):")
for k, v in flat.items():
    print(f"    {k:<35} = {v!r}")

# ── 2. Custom separator ────────────────────────────────────────────────────────
print("\n▶ _flatten_dict()  — custom separator ('.')")
flat_dot = _flatten_dict({"a": {"b": {"c": 1, "d": 2}}}, sep=".")
print(f"  {flat_dot}")

# ── 3. _flatten_records — list of records ────────────────────────────────────
print("\n▶ _flatten_records()  — list of nested dicts")
records = [
    {"id": 1, "meta": {"plan": "pro",  "seats": 10}},
    {"id": 2, "meta": {"plan": "free", "seats": 1}},
    {"id": 3, "meta": {"plan": "pro",  "seats": 50}},
]
flat_records = _flatten_records(records)
print(f"  Input has nested 'meta' dict")
print(f"  Flat columns: {list(flat_records[0].keys())}")
for r in flat_records:
    print(
        f"    id={r['id']}  meta__plan={r['meta__plan']!r}  meta__seats={r['meta__seats']}")

# ── 4. Real API data — /users has nested address + company ───────────────────
print("\n▶ Real API data — /users (JSONPlaceholder) — nested address + company")
client = Apikit(base_url="https://jsonplaceholder.typicode.com", auth="none")
users = client.fetch_records("/users", show_progress=False)
flat_users = _flatten_records(users)
print(f"  Original keys   : {list(users[0].keys())}")
print(f"  Flattened keys  : {list(flat_users[0].keys())}")
nested_keys = [k for k in flat_users[0] if "__" in k]
print(f"  Nested columns  : {nested_keys}")

# ── 5. records_to_polars ──────────────────────────────────────────────────────
print("\n▶ records_to_polars()  — auto-flatten + Polars DataFrame")
try:
    import polars as pl
    df = records_to_polars(users)
    print(f"  Shape      : {df.shape}")
    print(f"  All columns:")
    for col in df.columns:
        print(f"    {col:<40} {df[col].dtype}")
except ImportError:
    print("  (polars not installed)")

# ── 6. records_to_pandas ──────────────────────────────────────────────────────
print("\n▶ records_to_pandas()  — auto-flatten + Pandas DataFrame")
try:
    import pandas as pd
    from iki_apikit import records_to_pandas
    df = records_to_pandas(users)
    print(f"  Shape  : {df.shape}")
    print(f"  dtypes sample:")
    for col, dtype in list(df.dtypes.items())[:5]:
        print(f"    {col:<40} {dtype}")
except ImportError:
    print("  (pandas not installed)")

# ── 7. Schema inference ───────────────────────────────────────────────────────
print("\n▶ infer_polars_schema()  — detect Polars dtypes from first 100 records")
try:
    schema = infer_polars_schema(users)
    if schema:
        print("  Inferred Polars schema:")
        for col, dtype in schema.items():
            print(f"    {col:<40} {dtype}")
except ImportError:
    print("  (polars not installed)")

print("\n▶ infer_pandas_schema()  — detect Pandas dtypes")
try:
    from iki_apikit.io.transform.schema import infer_pandas_schema
    schema = infer_pandas_schema(users)
    if schema:
        for col, dtype in list(schema.items())[:6]:
            print(f"    {col:<40} {dtype}")
except (ImportError, ModuleNotFoundError):
    # Fallback: use records_to_pandas and .dtypes
    try:
        from iki_apikit import records_to_pandas
        df = records_to_pandas(users)
        for col, dtype in list(df.dtypes.items())[:6]:
            print(f"    {col:<40} {dtype}")
    except ImportError:
        print("  (pandas not installed)")

# ── 8. Lists inside records ───────────────────────────────────────────────────
print("\n▶ Lists inside records — serialized to JSON strings")
records_with_lists = [
    {"id": 1, "tags": ["python", "api"], "scores": [98, 87, 92]},
    {"id": 2, "tags": ["data"],          "scores": [75]},
]
flat = _flatten_records(records_with_lists)
print(
    f"  tags   : {flat[0]['tags']!r}   (type: {type(flat[0]['tags']).__name__})")
print(f"  scores : {flat[0]['scores']!r}")

print("\n✓ Flattening & schema inference complete.\n")

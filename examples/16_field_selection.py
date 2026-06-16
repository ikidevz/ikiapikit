"""
16_field_selection.py
=====================
Field selection and column pruning — fetch only what you need.

Demonstrates:
  • select=[...]          — keep only named top-level fields
  • exclude=[...]         — drop named fields, keep everything else
  • select with nested    — dot-path selection ("address.city")
  • rename={...}          — rename fields during fetch
  • select + paginate     — pruning applies across all pages
  • select + flatten      — pruning happens after flattening
  • transform_fn          — arbitrary per-record transformation
  • Memory savings        — compare sizes with and without selection

Why this matters:
  APIs often return 30+ fields when you only need 3. Before records hit a
  Polars/Pandas DataFrame or a Parquet file, stripping unused columns:
    • Reduces peak memory (critical for large paginated fetches)
    • Speeds up Parquet writes (fewer columns = smaller schema)
    • Makes downstream code cleaner — no "where did that column come from?"
    • Avoids leaking PII fields into files that don't need them

Run:
    python 16_field_selection.py
"""

import sys as _sys

from ikiapikit import Apikit, ApiConfig, AuthConfig, PaginationConfig

print("=" * 60)
print("16 · FIELD SELECTION & COLUMN PRUNING")
print("=" * 60)

BASE = "https://jsonplaceholder.typicode.com"
client = Apikit(base_url=BASE, auth="none")


# ── 1. Full record vs selected ────────────────────────────────────────────────
print("\n▶ Default fetch — all fields returned by the API")
full = client.fetch_records("/users", show_progress=False)
print(f"  Fields in raw /users record : {list(full[0].keys())}")
print(f"  That's {len(full[0])} top-level keys (plus nested objects)")


# ── 2. select=[...] — keep only what you need ────────────────────────────────
print("\n▶ select=['id', 'name', 'email']  — keep only 3 fields")
slim = client.fetch_records(
    "/users",
    select=["id", "name", "email"],
    show_progress=False,
)
print(f"  Fields now   : {list(slim[0].keys())}")
print(f"  Sample record: {slim[0]}")


# ── 3. exclude=[...] — drop specific fields ───────────────────────────────────
print("\n▶ exclude=['address', 'company']  — drop nested PII / noise")
no_pii = client.fetch_records(
    "/users",
    exclude=["address", "company"],
    show_progress=False,
)
print(f"  Fields kept  : {list(no_pii[0].keys())}")
print(f"  (address and company removed)")


# ── 4. Dot-path selection on nested fields ────────────────────────────────────
print("\n▶ select with dot-paths  — pull specific nested fields up to top level")
nested_select = client.fetch_records(
    "/users",
    select=["id", "name", "address.city", "company.name"],
    show_progress=False,
)
print(f"  Fields : {list(nested_select[0].keys())}")
for u in nested_select[:3]:
    print(f"    id={u['id']}  name={u['name']:<20}  "
          f"city={u.get('address.city', '?'):<12}  "
          f"company={u.get('company.name', '?')}")


# ── 5. rename — clean up field names on the fly ───────────────────────────────
print("\n▶ rename={'username': 'handle', 'email': 'contact_email'}")
renamed = client.fetch_records(
    "/users",
    select=["id", "username", "email"],
    rename={"username": "handle", "email": "contact_email"},
    show_progress=False,
)
print(f"  Fields : {list(renamed[0].keys())}")
print(f"  Sample : {renamed[0]}")


# ── 6. select + flatten — pruning after flattening ───────────────────────────
print("\n▶ select + flatten=True  — pick from flattened column names")
flat_select = client.fetch_records(
    "/users",
    flatten=True,
    select=["id", "name", "address__city",
            "address__zipcode", "company__name"],
    show_progress=False,
)
print(f"  Fields : {list(flat_select[0].keys())}")
for u in flat_select[:3]:
    print(f"    {u['id']}  {u['name']:<20}  "
          f"{u.get('address__city', '?'):<12}  "
          f"{u.get('address__zipcode', '?'):<10}  "
          f"{u.get('company__name', '?')}")


# ── 7. select + paginate — applies across every page ─────────────────────────
print("\n▶ select + paginate=True  — pruning happens per page, before accumulation")
cfg = ApiConfig(
    base_url=BASE,
    auth=AuthConfig(type="none"),
    pagination=PaginationConfig(
        strategy="offset",
        page_size=25,
        limit_param="_limit",
        offset_param="_start",
        max_pages=4,
    ),
)
paginated_client = Apikit.from_config(cfg)

slim_posts = paginated_client.fetch_records(
    "/posts",
    paginate=True,
    select=["id", "userId", "title"],
    show_progress=True,
)
print(f"  Fetched {len(slim_posts)} posts across 4 pages")
print(
    f"  Fields : {list(slim_posts[0].keys())}  (body field stripped per page)")

# Memory comparison
full_posts = paginated_client.fetch_records(
    "/posts", paginate=True, show_progress=False)
slim_bytes = _sys.getsizeof(str(slim_posts))
full_bytes = _sys.getsizeof(str(full_posts))
print(f"  Memory (rough): full={full_bytes:,}B  slim={slim_bytes:,}B  "
      f"({100*(1 - slim_bytes/full_bytes):.0f}% smaller)")


# ── 8. transform_fn — arbitrary per-record transform ─────────────────────────
print("\n▶ transform_fn  — arbitrary per-record transformation")


def clean_post(record: dict) -> dict:
    """Keep id + userId, uppercase the title, word-count the body."""
    return {
        "id":         record["id"],
        "user_id":    record["userId"],
        "title_upper": record["title"].upper(),
        "body_words":  len(record.get("body", "").split()),
    }


transformed = client.fetch_records(
    "/posts",
    params={"_limit": 5},
    transform_fn=clean_post,
    show_progress=False,
)
print(f"  Fields : {list(transformed[0].keys())}")
for r in transformed[:3]:
    print(
        f"    id={r['id']}  words={r['body_words']}  title={r['title_upper'][:40]}...")


# ── 9. select + fetch_polars ──────────────────────────────────────────────────
print("\n▶ select + fetch_polars()  — clean DataFrame with only needed columns")
try:
    import polars as pl
    df = client.fetch_polars(
        "/comments",
        params={"_limit": 20},
        select=["id", "postId", "email"],
        show_progress=False,
    )
    print(f"  DataFrame shape : {df.shape}")
    print(f"  Columns         : {df.columns}")
    print(df.head(3))
except ImportError:
    print("  (polars not installed)")


# ── 10. PII stripping pattern ─────────────────────────────────────────────────
print("\n▶ PII stripping pattern — safe export excluding sensitive fields")
print("""
  PII_FIELDS = {"email", "phone", "address", "company", "website"}

  safe_records = client.fetch_records(
      "/users",
      exclude=list(PII_FIELDS),
      show_progress=False,
  )
  client.fetch_to_file(
      "/users",
      format="parquet",
      file_path="users_safe.parquet",
      exclude=list(PII_FIELDS),
  )
  # Parquet file contains no PII fields
""")


print("\n✓ Field selection & column pruning complete.\n")

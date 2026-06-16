"""
12_dbt_exporter.py
==================
Turn raw API data into dbt-ready artifacts in one call.

Demonstrates:
  • DbtExporter.export()              — records → seed CSV + sources.yml + schema.yml
  • DbtExporter.export_from_client()  — fetch + export in one shot
  • dry_run=True                       — print what would be written, touch nothing
  • Custom database / schema / tags / meta
  • Multiple exports to the same sources.yml (appended, not overwritten)
  • Inspecting the generated YAML with Python so you can verify the output

Uses JSONPlaceholder — no auth required.

dbt workflow after running this:
    dbt seed          # loads the CSV into your warehouse
    dbt source freshness  # uses sources.yml
    dbt run           # uses schema.yml for column docs + data_type

Run:
    python 12_dbt_exporter.py
"""

import json
import tempfile
from pathlib import Path

from iki_apikit import Apikit, ApiConfig, AuthConfig, PaginationConfig, DbtExporter

BASE = "https://jsonplaceholder.typicode.com"

print("=" * 60)
print("12 · DBT EXPORTER")
print("=" * 60)

client = Apikit(base_url=BASE, auth="none")


# ── 1. Basic export — records already in memory ───────────────────────────────
print("\n▶ DbtExporter.export()  — records in memory → dbt seed artifacts")

users = client.fetch_records("/users", show_progress=False)
print(f"  Fetched {len(users)} users from JSONPlaceholder")

with tempfile.TemporaryDirectory() as tmp:
    exporter = DbtExporter(output_dir=tmp)

    paths = exporter.export(
        records=users,
        name="jsonplaceholder_users",
        database="raw",
        schema="jsonplaceholder",
        description="Users fetched from JSONPlaceholder demo API",
        tags=["demo", "users"],
        meta={"owner": "data-eng", "pii": False},
        flatten=True,   # nested address/company objects are flattened
    )

    print(f"\n  Files written:")
    for kind, path in paths.items():
        rel = Path(path).relative_to(tmp)
        print(f"    {kind:<10} → {rel}  ({Path(path).stat().st_size:,} bytes)")

    # Peek at the seed CSV header
    seed_path = paths["seed"]
    header = seed_path.read_text().splitlines()[0]
    print(f"\n  Seed CSV header (first 100 chars):")
    print(f"    {header[:100]}{'...' if len(header) > 100 else ''}")

    # Peek at the schema YAML
    schema_path = paths["schema"]
    schema_yaml = schema_path.read_text()
    print(f"\n  schema.yml (first 20 lines):")
    for i, line in enumerate(schema_yaml.splitlines()[:20]):
        print(f"    {line}")

    # Peek at sources.yml
    sources_path = paths["sources"]
    print(f"\n  sources.yml (first 15 lines):")
    for line in sources_path.read_text().splitlines()[:15]:
        print(f"    {line}")


# ── 2. export_from_client() — fetch + export in one call ─────────────────────
print("\n▶ DbtExporter.export_from_client()  — fetch + export in one shot")

with tempfile.TemporaryDirectory() as tmp:
    exporter = DbtExporter(output_dir=tmp)

    # Paginated fetch + dbt export
    cfg = ApiConfig(
        base_url=BASE,
        auth=AuthConfig(type="none"),
        pagination=PaginationConfig(
            strategy="offset",
            page_size=25,
            limit_param="_limit",
            offset_param="_start",
            max_pages=4,   # 4 × 25 = 100 posts
        ),
    )
    paginated_client = Apikit.from_config(cfg)

    paths = exporter.export_from_client(
        client=paginated_client,
        endpoint="/posts",
        name="jsonplaceholder_posts",
        database="raw",
        schema="jsonplaceholder",
        description="Blog posts from JSONPlaceholder",
        tags=["demo", "posts"],
        flatten=True,
    )

    seed_lines = paths["seed"].read_text().splitlines()
    print(f"\n  Seed rows (incl. header): {len(seed_lines)}")
    print(f"  Seed header             : {seed_lines[0]}")


# ── 3. Multiple exports → same sources.yml ────────────────────────────────────
print("\n▶ Multiple exports → appended to the same sources.yml")

todos = client.fetch_records(
    "/todos", params={"_limit": 10}, show_progress=False)
comments = client.fetch_records(
    "/comments", params={"_limit": 5}, show_progress=False)

with tempfile.TemporaryDirectory() as tmp:
    exporter = DbtExporter(output_dir=tmp)

    exporter.export(todos,    name="jp_todos",    database="raw",
                    schema="jsonplaceholder", flatten=True)
    exporter.export(comments, name="jp_comments", database="raw",
                    schema="jsonplaceholder", flatten=True)

    sources_text = (Path(tmp) / "models" / "sources.yml").read_text()
    # Both table names must appear in the same file
    has_todos = "name: jp_todos" in sources_text
    has_comments = "name: jp_comments" in sources_text
    print(f"  jp_todos    in sources.yml : {has_todos}")
    print(f"  jp_comments in sources.yml : {has_comments}")
    print(f"  sources.yml total lines    : {len(sources_text.splitlines())}")

    # Show distinct model schema files
    model_files = sorted(Path(tmp).glob("models/*.yml"))
    print(f"  Model YAML files:")
    for f in model_files:
        print(f"    {f.name}")


# ── 4. dry_run=True — print plan, write nothing ───────────────────────────────
print("\n▶ DbtExporter(dry_run=True)  — prints plan, creates no files")

with tempfile.TemporaryDirectory() as tmp:
    dry_exporter = DbtExporter(output_dir=tmp, dry_run=True)

    paths_dry = dry_exporter.export(
        records=users,
        name="users_dry_run",
        database="analytics",
        schema="api_sources",
        description="Dry run — nothing will be written",
        flatten=True,
    )

    # No files should exist
    written = list(Path(tmp).rglob("*"))
    print(f"  Files actually created : {len(written)}  (expected 0)")
    print(f"  paths dict returned    : {paths_dry}  (empty on dry run)")


# ── 5. flatten=False — keep nested structures as-is ──────────────────────────
print("\n▶ export(flatten=False)  — raw nested dicts go straight to CSV")

with tempfile.TemporaryDirectory() as tmp:
    exporter_raw = DbtExporter(output_dir=tmp)

    # fetch_records already returns flat dicts, but a custom nested list
    # shows the flatten=False behaviour
    nested_records = [
        {"id": 1, "meta": {"env": "prod", "region": "ph"}, "score": 99.5},
        {"id": 2, "meta": {"env": "staging", "region": "sg"}, "score": 72.1},
    ]

    paths_raw = exporter_raw.export(
        records=nested_records,
        name="nested_example",
        database="raw",
        schema="demo",
        flatten=False,   # write the dicts as-is; 'meta' stays as a string
    )

    seed_content = paths_raw["seed"].read_text()
    print(f"  CSV header (flatten=False): {seed_content.splitlines()[0]}")

    # Compare with flatten=True
    paths_flat = exporter_raw.export(
        records=nested_records,
        name="flat_example",
        database="raw",
        schema="demo",
        flatten=True,    # 'meta' becomes meta__env, meta__region
    )
    print(f"  CSV header (flatten=True) : "
          f"{paths_flat['seed'].read_text().splitlines()[0]}")


print("\n✓ dbt exporter examples complete.\n")

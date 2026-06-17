"""
06_output_formats.py
====================
Write fetched data to every supported output format.

Demonstrates:
  • fetch_to_file()  — Parquet, NDJSON, JSONL, CSV, Arrow IPC, JSON
  • get_writer()     — use writers directly (to file or in-memory buffer)
  • DuckDB output    — instant SQL on fetched data
  • Writing to an io.BytesIO buffer (no disk needed)

Run:
    python 06_output_formats.py

Formats: parquet | ndjson | jsonl | csv | arrow | json | duckdb
"""

import io
import os
import tempfile
from ikiapikit import Apikit, get_writer, ApiConfig, AuthConfig, PaginationConfig

BASE = "https://jsonplaceholder.typicode.com"

client = Apikit(base_url=BASE, auth="none")
records = client.fetch_records("/users", show_progress=False)
print("=" * 60)
print("06 · OUTPUT FORMATS")
print("=" * 60)
print(f"\nBase dataset: {len(records)} user records")

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
    def path(filename):
        return os.path.join(tmpdir, filename)

    # ── 1. Parquet ────────────────────────────────────────────────────────────
    print("\n▶ format='parquet'  (Polars or PyArrow)")
    try:
        p = path("users.parquet")
        get_writer("parquet").write(records, p)
        size = os.path.getsize(p)
        print(f"  Written: users.parquet  ({size:,} bytes)")
        try:
            import polars as pl
            df = pl.read_parquet(p)
            print(f"  Read back: {df.shape[0]} rows × {df.shape[1]} cols")
        except ImportError:
            import pyarrow.parquet as pq
            tbl = pq.read_table(p)
            print(f"  Read back: {tbl.num_rows} rows × {tbl.num_columns} cols")
    except Exception as e:
        print(f"  (skipped — {e})")

    # ── 2. NDJSON / JSONL ─────────────────────────────────────────────────────
    print("\n▶ format='ndjson'  (one JSON object per line)")
    p = path("users.ndjson")
    get_writer("ndjson").write(records, p)
    with open(p) as f:
        lines = f.readlines()
    print(f"  Written: {len(lines)} lines ({os.path.getsize(p):,} bytes)")
    print(f"  First line preview: {lines[0][:80].strip()}...")

    # ── 3. JSON (pretty array) ────────────────────────────────────────────────
    print("\n▶ format='json'  (pretty-printed JSON array)")
    p = path("users.json")
    get_writer("json").write(records, p)
    print(f"  Written: {os.path.getsize(p):,} bytes")
    with open(p) as f:
        content = f.read()
    print(f"  Starts with: {content[:60]}...")

    # ── 4. CSV ────────────────────────────────────────────────────────────────
    print("\n▶ format='csv'  (Polars or Pandas)")
    try:
        p = path("users.csv")
        get_writer("csv").write(records, p)
        with open(p) as f:
            rows = f.readlines()
        print(f"  Written: {len(rows)-1} data rows + header")
        print(f"  Header: {rows[0][:80].strip()}")
    except Exception as e:
        print(f"  (skipped — {e})")

    # ── 5. Arrow IPC (Feather v2) ─────────────────────────────────────────────
    print("\n▶ format='arrow'  (Apache Arrow IPC / Feather v2)")
    try:
        p = path("users.arrow")
        get_writer("arrow").write(records, p)
        size = os.path.getsize(p)
        print(f"  Written: {size:,} bytes")
        import pyarrow.ipc as ipc
        # Explicitly close the reader before tempdir cleanup on Windows
        with ipc.open_file(p) as reader:
            tbl = reader.read_all()
        print(f"  Read back: {tbl.num_rows} rows × {tbl.num_columns} cols")
    except Exception as e:
        print(f"  (skipped — {e})")

    # ── 6. DuckDB ─────────────────────────────────────────────────────────────
    print("\n▶ format='duckdb'  (in-process SQL database)")
    try:
        p = path("users.duckdb")
        get_writer("duckdb").write(records, p)
        import duckdb
        # Use context manager so the connection closes before tempdir cleanup
        with duckdb.connect(p) as con:
            result = con.execute(
                "SELECT name, email FROM data LIMIT 3"
            ).fetchall()
        print(f"  DuckDB query SELECT name, email FROM data LIMIT 3:")
        for row in result:
            print(f"    {row[0]:<20} {row[1]}")
    except ImportError:
        print("  (duckdb not installed — run: pip install duckdb)")
    except Exception as e:
        print(f"  (skipped — {e})")

    # ── 7. fetch_to_file() convenience method ────────────────────────────────
    print("\n▶ client.fetch_to_file()  — one-liner fetch + write")
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
    paginated_client = Apikit.from_config(cfg)
    out_path = path("posts.parquet")
    try:
        paginated_client.fetch_to_file(
            "/posts",
            format="parquet",
            file_path=out_path,
            paginate=True,
        )
        print(f"  Parquet written, size: {os.path.getsize(out_path):,} bytes")
    except Exception as e:
        print(f"  (parquet skipped — {e}); trying csv...")
        out_path = path("posts.csv")
        paginated_client.fetch_to_file(
            "/posts",
            format="csv",
            file_path=out_path,
            paginate=True,
        )
        print(f"  CSV written, size: {os.path.getsize(out_path):,} bytes")

    # ── 8. Writing to an in-memory buffer (no disk) ───────────────────────────
    print("\n▶ Writing to io.BytesIO()  — no disk required")
    buf = io.BytesIO()
    get_writer("ndjson").write(records, buf)
    buf.seek(0)
    content = buf.read()
    print(f"  Buffer size : {len(content):,} bytes")
    print(f"  Line count  : {content.count(b'\\n')}")

    raw_bytes = get_writer("json").to_bytes(records)
    print(f"  to_bytes()  : {len(raw_bytes):,} bytes of JSON")

print("\n✓ Output formats complete.\n")

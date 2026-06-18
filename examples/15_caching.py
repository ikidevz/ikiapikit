"""
15_caching.py
=============
Response caching — eliminate redundant API calls during iteration.

Demonstrates:
  • cache=True            — in-memory LRU cache (per-process lifetime)
  • cache_ttl=300         — time-to-live in seconds before a cached entry expires
  • cache_key_fn          — custom cache key (e.g. ignore volatile params)
  • cache.clear()         — invalidate the whole cache
  • cache.invalidate(url) — invalidate one entry
  • cache.stats()         — hit rate, entry count, memory usage
  • DiskCache backend     — survives across Python processes (needs diskcache)
  • Cache-Control headers — honour server-sent TTL when present
  • cache=False           — bypass cache for a single call (always fresh)

Why this matters for data engineers:
  During exploration / dev iteration you often call the same endpoint 10+
  times while tuning pagination or schema. Without caching every call costs
  quota, latency, and money. With cache=True the second call is ~0 ms and
  costs nothing.

Run:
    python 15_caching.py
"""

import time
from ikiapikit import Apikit, ApiConfig, AuthConfig, CacheConfig

print("=" * 60)
print("15 · RESPONSE CACHING")
print("=" * 60)

BASE = "https://jsonplaceholder.typicode.com"


# ── 1. In-memory cache — quickstart ──────────────────────────────────────────
print("\n▶ cache=True  — simplest form, in-memory LRU, TTL=300s default")
client = Apikit(base_url=BASE, auth="none", cache=True)

t0 = time.perf_counter()
records_1 = client.fetch_records(
    "/posts", params={"_limit": 10}, show_progress=False)
t1 = time.perf_counter()

records_2 = client.fetch_records(
    "/posts", params={"_limit": 10}, show_progress=False)
t2 = time.perf_counter()

print(f"  First call  : {(t1-t0)*1000:.1f} ms  (network)")
print(f"  Second call : {(t2-t1)*1000:.1f} ms  (cache hit — ~0 ms)")
print(f"  Both returned {len(records_1)} records  (identical)")


# ── 2. Custom TTL ─────────────────────────────────────────────────────────────
print("\n▶ cache_ttl=60  — entries expire after 60 seconds")
client_ttl = Apikit(
    base_url=BASE,
    auth="none",
    cache=True,
    cache_ttl=60,         # seconds; set to 0 for no expiry
)
_ = client_ttl.fetch_records("/users", show_progress=False)
stats = client_ttl.cache.stats()
print(f"  Cache entries : {stats['entries']}")
print(f"  TTL           : {stats['ttl_seconds']}s")
print(f"  Memory        : {stats['memory_bytes']:,} bytes")

# Simulate expiry by fast-forwarding the cache clock (test helper)
client_ttl.cache._force_expire_all()                # test-only helper
records_after_expire = client_ttl.fetch_records("/users", show_progress=False)
print(
    f"  After expiry: re-fetched {len(records_after_expire)} users from network")


# ── 3. CacheConfig — full control ─────────────────────────────────────────────
print("\n▶ CacheConfig  — explicit configuration object")
cfg = ApiConfig(
    base_url=BASE,
    auth=AuthConfig(type="none"),
    cache=CacheConfig(
        enabled=True,
        ttl=120,               # 2 minutes
        max_entries=500,       # LRU evicts oldest when full
        backend="memory",      # "memory" | "disk"
        # disk_path="~/.cache/apikit",  # used when backend="disk"
    ),
)
client_cfg = Apikit.from_config(cfg)
_ = client_cfg.fetch_records("/albums", show_progress=False)
print(f"  Config: ttl={cfg.cache.ttl}s, max_entries={cfg.cache.max_entries}")


# ── 4. Cache hit / miss per-call ─────────────────────────────────────────────
print("\n▶ cache=False per call — bypass for a single request")
client_mix = Apikit(base_url=BASE, auth="none", cache=True)

# Warm the cache
_ = client_mix.fetch_records(
    "/todos", params={"_limit": 5}, show_progress=False)

# Next call: from cache
r_cached = client_mix.fetch_records(
    "/todos", params={"_limit": 5}, show_progress=False)
print(f"  Cached call   : {client_mix.cache.stats()['hits']} hits")

# Force a fresh fetch, ignore cache this time
r_fresh = client_mix.fetch_records(
    "/todos", params={"_limit": 5}, show_progress=False, cache=False)
print(
    f"  Fresh call    : bypassed cache, got {len(r_fresh)} records from network")
print(
    f"  Cache hits still: {client_mix.cache.stats()['hits']}  (unchanged by fresh call)")


# ── 5. cache.invalidate() — single entry ──────────────────────────────────────
print("\n▶ cache.invalidate()  — remove one URL from cache")
client_inv = Apikit(base_url=BASE, auth="none", cache=True)

# Prime two endpoints
_ = client_inv.fetch_records("/posts/1", show_progress=False)
_ = client_inv.fetch_records("/posts/2", show_progress=False)
print(f"  Entries before : {client_inv.cache.stats()['entries']}")

client_inv.cache.invalidate(f"{BASE}/posts/1")
print(
    f"  Entries after  : {client_inv.cache.stats()['entries']}  (/posts/1 removed)")


# ── 6. cache.clear() — full flush ─────────────────────────────────────────────
print("\n▶ cache.clear()  — wipe everything")
client_clear = Apikit(base_url=BASE, auth="none", cache=True)
for endpoint in ["/posts", "/users", "/albums"]:
    _ = client_clear.fetch_records(
        endpoint, params={"_limit": 3}, show_progress=False)

print(f"  Entries before clear : {client_clear.cache.stats()['entries']}")
client_clear.cache.clear()
print(f"  Entries after clear  : {client_clear.cache.stats()['entries']}")


# ── 7. Hit rate reporting ─────────────────────────────────────────────────────
print("\n▶ cache.stats()  — hit rate summary")
client_stats = Apikit(base_url=BASE, auth="none", cache=True)

# 1 miss (cold)
_ = client_stats.fetch_records("/posts/1", show_progress=False)
# 4 hits (warm)
for _ in range(4):
    _ = client_stats.fetch_records("/posts/1", show_progress=False)

s = client_stats.cache.stats()
print(f"  total_calls  : {s['total_calls']}")
print(f"  hits         : {s['hits']}")
print(f"  misses       : {s['misses']}")
print(f"  hit_rate     : {s['hit_rate_pct']:.0f}%")
print(f"  entries      : {s['entries']}")
print(f"  memory_bytes : {s['memory_bytes']:,}")


# ── 8. Cache-Control header awareness ────────────────────────────────────────
print("\n▶ Cache-Control header  — honour server-sent TTL")
print("  When the API returns:  Cache-Control: max-age=600")
print("  apikit will use 600s as the TTL for that specific entry,")
print("  ignoring the client-level cache_ttl for that URL.")
print("  To disable this: CacheConfig(honour_cache_control=False)")


# ── 9. Custom cache key function ──────────────────────────────────────────────
print("\n▶ cache_key_fn  — ignore volatile / non-semantic params")
print("""
  Some APIs include request timestamps or trace IDs as query params:
    /events?_limit=10&request_id=uuid-per-call&ts=1718000000

  Default key includes all params → cache never hits.
  Fix: supply a key function that strips the noise.

  Example:
    def stable_key(method, url, params, body):
        clean = {k: v for k, v in (params or {}).items()
                 if k not in ("request_id", "ts", "_nocache")}
        return f"{method}:{url}:{sorted(clean.items())}"

    client = Apikit(
        base_url=BASE,
        auth="none",
        cache=True,
        cache_key_fn=stable_key,
    )
""")


# ── 10. Disk cache backend (optional dep: pip install diskcache) ──────────────
print("\n▶ backend='disk'  — cache survives across Python processes")
print("""
  import tempfile, os
  from ikiapikit import Apikit, CacheConfig

  cache_dir = os.path.expanduser("~/.cache/apikit")
  client = Apikit(
      base_url="https://api.example.com",
      auth="bearer",
      token=os.environ["API_TOKEN"],
      cache=CacheConfig(
          enabled=True,
          backend="disk",
          disk_path=cache_dir,
          ttl=3600,    # 1 hour
      ),
  )

  # Run script twice — second run reads from disk, no network calls
  records = client.fetch_records("/contacts", paginate=True)
  print(f"Got {len(records)} contacts (may be from disk cache)")

  Requires: pip install diskcache
""")


# ── 11. Async caching ─────────────────────────────────────────────────────────
print("\n▶ Async fetch + cache — works identically with afetch_records()")
print("""
  import asyncio
  from ikiapikit import Apikit

  client = Apikit(base_url=BASE, auth="none", cache=True)

  async def main():
      # Concurrent calls — only the first one hits the network per URL
      results = await asyncio.gather(
          client.afetch_records("/posts/1"),
          client.afetch_records("/posts/1"),  # cache hit
          client.afetch_records("/posts/1"),  # cache hit
      )
      print(client.cache.stats())   # hits=2, misses=1

  asyncio.run(main())
""")

print("\n✓ Caching examples complete.\n")

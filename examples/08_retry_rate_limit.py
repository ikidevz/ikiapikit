"""
08_retry_rate_limit.py
======================
Retry configuration and proactive rate-limit tracking.

Demonstrates:
  • RetryConfig — custom back-off, jitter, status codes to retry
  • RateLimitState — ingest X-RateLimit-* headers
  • should_throttle() + sleep_duration() — proactive throttling
  • How apikit handles 429 automatically (reads Retry-After)
  • Simulated 429 via httpbin.org's /status endpoint

Run:
    python 08_retry_rate_limit.py
"""

from iki_apikit import AuthError
from iki_apikit import RetryConfig
import time
import httpx
from iki_apikit import Apikit, ApiConfig, AuthConfig, RetryConfig, RateLimitState

print("=" * 60)
print("08 · RETRY & RATE LIMIT HANDLING")
print("=" * 60)

# ── 1. Default retry config ───────────────────────────────────────────────────
print("\n▶ Default RetryConfig")
cfg = RetryConfig()
print(f"  max_attempts     : {cfg.max_attempts}")
print(f"  min_wait         : {cfg.min_wait}s")
print(f"  max_wait         : {cfg.max_wait}s")
print(f"  jitter           : {cfg.jitter}s")
print(f"  retry_on_status  : {cfg.retry_on_status}")

# ── 2. Custom retry config ────────────────────────────────────────────────────
print("\n▶ Custom RetryConfig — more aggressive retry for an unreliable API")
custom_retry = RetryConfig(
    max_attempts=7,
    min_wait=0.5,
    max_wait=120.0,
    jitter=2.0,
    retry_on_status=[429, 500, 502, 503, 504,
                     520, 522],  # add Cloudflare codes
)
api_cfg = ApiConfig(
    base_url="https://jsonplaceholder.typicode.com",
    auth=AuthConfig(type="none"),
    retry=custom_retry,
)
client = Apikit.from_config(api_cfg)
records = client.fetch_records("/posts/1", show_progress=False)
print(f"  Successfully fetched post: {records[0]['title'][:50]}...")
print(f"  (Would retry up to {custom_retry.max_attempts} times on 5xx)")

# ── 3. RateLimitState — parsing real response headers ────────────────────────
print("\n▶ RateLimitState — parse X-RateLimit-* headers")
rl = RateLimitState(min_remaining=50, safety_buffer=0.5)

# Simulate headers as returned by GitHub / generic APIs


class FakeHeaders:
    def __init__(self, d):
        self._d = {k.lower(): v for k, v in d.items()}

    def get(self, key, default=None):
        return self._d.get(key.lower(), self._d.get(key, default))


# Scenario A: plenty of quota left
headers_ok = FakeHeaders({
    "X-RateLimit-Remaining": "4800",
    "X-RateLimit-Limit":     "5000",
    "X-RateLimit-Reset":     str(int(time.time()) + 3600),
})
rl.ingest(headers_ok)
print(f"  Scenario A (plenty left):")
print(f"    headroom        : {rl.headroom}")
print(f"    should_throttle : {rl.should_throttle()}")

# Scenario B: nearly exhausted
headers_low = FakeHeaders({
    "X-RateLimit-Remaining": "10",
    "X-RateLimit-Limit":     "5000",
    "X-RateLimit-Reset":     str(int(time.time()) + 45),
})
rl.ingest(headers_low)
print(f"\n  Scenario B (nearly exhausted, min_remaining=50):")
print(f"    headroom        : {rl.headroom}")
print(f"    should_throttle : {rl.should_throttle()}")
print(
    f"    sleep_duration  : {rl.sleep_duration():.1f}s  (would sleep until reset)")

# ── 4. HubSpot-style headers ──────────────────────────────────────────────────
print("\n▶ RateLimitState — HubSpot daily-limit headers")
rl_hs = RateLimitState(min_remaining=1000)
headers_hs = FakeHeaders({
    "X-HubSpot-RateLimit-Daily-Remaining": "38000",
})
rl_hs.ingest(headers_hs)
print(f"  HubSpot remaining : {rl_hs.headroom['remaining']}")
print(f"  should_throttle   : {rl_hs.should_throttle()}")

# ── 5. Stripe per-second headers ──────────────────────────────────────────────
print("\n▶ RateLimitState — Stripe per-second headers")
rl_stripe = RateLimitState(min_remaining=5)
headers_stripe = FakeHeaders({
    "X-RateLimit-Remaining-second": "97",
    "X-RateLimit-Limit":            "100",
})
rl_stripe.ingest(headers_stripe)
print(f"  Stripe remaining/sec : {rl_stripe.headroom['remaining']}")
print(f"  should_throttle      : {rl_stripe.should_throttle()}")

# ── 6. Manual throttle loop ───────────────────────────────────────────────────
print("\n▶ Manual throttle loop pattern")
print("""
  # Typical usage when calling the REST client directly:
  rl = RateLimitState(min_remaining=100)

  for batch in batches:
      response_data, response_headers = client._http.request_sync_full("GET", "/endpoint")
      rl.ingest(response_headers)      # update from every response
      rl.throttle_sync()               # sleeps if headroom is low
      process(response_data)
""")

# ── 7. 401 is never retried ───────────────────────────────────────────────────
print("▶ Auth errors — 401 raises AuthError immediately (no retry)")
bad_client = Apikit(
    base_url="https://httpbin.org",
    auth="bearer",
    token="INVALID_TOKEN",
)
try:
    bad_client.fetch_records("/bearer", show_progress=False)
except AuthError as e:
    print(f"  Got AuthError as expected: {e}")
except Exception as e:
    print(
        f"  Got error (httpbin may behave differently): {type(e).__name__}: {e}")

print("\n✓ Retry & rate limit examples complete.\n")

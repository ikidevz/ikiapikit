"""
02_authentication.py
====================
Every authentication mode apikit supports.

Demonstrates:
  • auth="none"    — public APIs
  • auth="bearer"  — Authorization: Bearer <token>
  • auth="apikey"  — custom header OR query param
  • auth="basic"   — HTTP Basic (Base64)
  • auth="oauth2"  — Client Credentials flow, auto token refresh

Real endpoints used:
  • Bearer   → httpbin.org/bearer          (reflects your token back)
  • API Key  → httpbin.org/headers         (reflects headers)
  • Basic    → httpbin.org/basic-auth/...  (challenge endpoint)
  • No Auth  → jsonplaceholder             (public)
  • OAuth2   → requires a real OAuth2 server — demo shows config only

Run:
    python 02_authentication.py
"""

from iki_apikit import Apikit, ApiConfig, AuthConfig

print("=" * 60)
print("02 · AUTHENTICATION")
print("=" * 60)

# ── 1. No auth ────────────────────────────────────────────────────────────────
print("\n▶ auth='none'  (JSONPlaceholder)")
client = Apikit(base_url="https://jsonplaceholder.typicode.com", auth="none")
data = client.fetch_records("/posts/1", show_progress=False)
print(f"  Title: {data[0]['title'][:60]}...")

# ── 2. Bearer token ───────────────────────────────────────────────────────────
print("\n▶ auth='bearer'  (httpbin reflects the Authorization header)")
client = Apikit(
    base_url="https://httpbin.org",
    auth="bearer",
    token="my-super-secret-token",
)
resp = client.fetch_records("/bearer", show_progress=False)
print(f"  Authenticated : {resp[0].get('authenticated')}")
print(f"  Token echoed  : {resp[0].get('token')}")

# ── 3. API Key via header ──────────────────────────────────────────────────────
print("\n▶ auth='apikey' via header  (httpbin reflects headers)")
client = Apikit(
    base_url="https://httpbin.org",
    auth="apikey",
    api_key="ak_live_abc123xyz",
    api_key_header="X-API-Key",           # default, shown explicitly
)
resp = client.fetch_records("/headers", show_progress=False)
headers = resp[0].get("headers", {})
print(
    f"  X-API-Key header echoed: {headers.get('X-Api-Key') or headers.get('X-API-Key')}")

# ── 4. API Key via query param ────────────────────────────────────────────────
print("\n▶ auth='apikey' via query param  (httpbin reflects query args)")
client = Apikit(
    base_url="https://httpbin.org",
    auth="apikey",
    api_key="qp_key_12345",
    api_key_query_param="api_key",        # injected as ?api_key=...
)
resp = client.fetch_records("/get", show_progress=False)
args = resp[0].get("args", {})
print(f"  api_key in query string: {args.get('api_key')}")

# ── 5. HTTP Basic auth ────────────────────────────────────────────────────────
print("\n▶ auth='basic'  (httpbin /basic-auth requires user:passwd in the URL)")
client = Apikit(
    base_url="https://httpbin.org",
    auth="basic",
    username="alice",
    password="secret123",
)
resp = client.fetch_records("/basic-auth/alice/secret123", show_progress=False)
print(f"  Authenticated : {resp[0].get('authenticated')}")
print(f"  User          : {resp[0].get('user')}")

# ── 6. OAuth2 Client Credentials — config demo ───────────────────────────────
print("\n▶ auth='oauth2'  (Client Credentials — config structure shown)")
print("  Replace token_url / credentials with your real OAuth2 provider.")
cfg = ApiConfig(
    base_url="https://api.example.com",
    auth=AuthConfig(
        type="oauth2",
        client_id="your-client-id",
        client_secret="your-client-secret",
        token_url="https://auth.example.com/oauth/token",
        scopes=["read:data", "write:data"],
    ),
)
print(f"  Config built  : base_url={cfg.base_url!r}, auth={cfg.auth.type!r}")
print("  On first use, apikit fetches the token automatically.")
print("  Token is refreshed 30s before expiry — zero manual handling.")

# ── 7. AuthConfig built from a full config object ────────────────────────────
print("\n▶ Apikit.from_config(ApiConfig(...))  — maximum control")
cfg = ApiConfig(
    base_url="https://httpbin.org",
    auth=AuthConfig(type="bearer", token="config-level-token"),
    headers={"X-App-Version": "2.0"},
)
client = Apikit.from_config(cfg)
resp = client.fetch_records("/bearer", show_progress=False)
print(f"  Authenticated : {resp[0].get('authenticated')}")
print(f"  Token         : {resp[0].get('token')}")

print("\n✓ Authentication examples complete.\n")

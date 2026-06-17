"""
02_authentication.py
====================
Every authentication mode apikit supports — all using real, live endpoints.

Demonstrates:
  • auth="none"    — public APIs (JSONPlaceholder)
  • auth="bearer"  — Authorization: Bearer <token> (httpbin.org)
  • auth="apikey"  — custom header OR query param (httpbin.org)
  • auth="basic"   — HTTP Basic / Base64 (httpbin.org)
  • auth="oauth2"  — Client Credentials flow with real token + API call
                     (demo.duendesoftware.com — no signup required)

OAuth2 demo credentials (public, permanent):
  token_url     : https://demo.duendesoftware.com/connect/token
  client_id     : m2m
  client_secret : secret
  scope         : api
  test API      : https://demo.duendesoftware.com/api/test

Run:
    python 02_authentication.py
"""

import requests
from ikiapikit import Apikit, ApiConfig, AuthConfig

print("=" * 60)
print("02 · AUTHENTICATION")
print("=" * 60)

# ── 1. No auth ────────────────────────────────────────────────────────────────
print("\n▶ auth='none'  (JSONPlaceholder — public API, no credentials)")
client = Apikit(base_url="https://jsonplaceholder.typicode.com", auth="none")
data = client.fetch_records("/posts/1", show_progress=False)
print(f"  Post ID  : {data[0]['id']}")
print(f"  Title    : {data[0]['title'][:60]}...")

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

# ── 3. API Key via header ─────────────────────────────────────────────────────
print("\n▶ auth='apikey' via header  (httpbin reflects headers)")
client = Apikit(
    base_url="https://httpbin.org",
    auth="apikey",
    api_key="ak_live_abc123xyz",
    api_key_header="X-API-Key",  # default; shown explicitly for clarity
)
resp = client.fetch_records("/headers", show_progress=False)
headers = resp[0].get("headers", {})
echoed = headers.get("X-Api-Key") or headers.get("X-API-Key")
print(f"  X-API-Key header echoed : {echoed}")

# ── 4. API Key via query param ────────────────────────────────────────────────
print("\n▶ auth='apikey' via query param  (httpbin reflects query args)")
client = Apikit(
    base_url="https://httpbin.org",
    auth="apikey",
    api_key="qp_key_12345",
    api_key_query_param="api_key",  # injected as ?api_key=...
)
resp = client.fetch_records("/get", show_progress=False)
args = resp[0].get("args", {})
print(f"  api_key in query string : {args.get('api_key')}")

# ── 5. HTTP Basic auth ────────────────────────────────────────────────────────
print("\n▶ auth='basic'  (httpbin /basic-auth requires user:passwd in path)")
client = Apikit(
    base_url="https://httpbin.org",
    auth="basic",
    username="alice",
    password="secret123",
)
resp = client.fetch_records("/basic-auth/alice/secret123", show_progress=False)
print(f"  Authenticated : {resp[0].get('authenticated')}")
print(f"  User          : {resp[0].get('user')}")

# ── 6. OAuth2 Client Credentials — live demo server ──────────────────────────
#
#  Uses the Duende IdentityServer public demo (demo.duendesoftware.com).
#  No account or signup needed — these credentials are permanent and public.
#
#  Available test clients on the demo server:
#    m2m        → client_credentials, secret="secret",  token lifetime 1h
#    m2m.short  → client_credentials, secret="secret",  token lifetime 75s
#                 (useful for testing auto-refresh logic in apikit)
#
print("\n▶ auth='oauth2'  (Duende IdentityServer public demo — real tokens)")

# Option A: let apikit handle everything (fetch + auto-refresh)
cfg = ApiConfig(
    base_url="https://demo.duendesoftware.com",
    auth=AuthConfig(
        type="oauth2",
        client_id="m2m",
        client_secret="secret",
        token_url="https://demo.duendesoftware.com/connect/token",
        scopes=["api"],
    ),
)
client = Apikit.from_config(cfg)

# First call: apikit fetches the token automatically before the request
resp = client.fetch_records("/api/test", show_progress=False)
print(f"  API response  : {resp[0]}")
print("  Token was fetched automatically and injected as Bearer.")

# Option B: fetch the token manually and inspect it
print("\n  ── Manual token inspection (same credentials) ──")

token_resp = requests.post(
    "https://demo.duendesoftware.com/connect/token",
    data={
        "grant_type": "client_credentials",
        "client_id": "m2m",
        "client_secret": "secret",
        "scope": "api",
    },
)
token_data = token_resp.json()
access_token = token_data["access_token"]

print(f"  Token type    : {token_data['token_type']}")
print(f"  Expires in    : {token_data['expires_in']}s")
print(f"  Access token  : {access_token[:48]}...")

# Verify the token actually works against the protected endpoint
api_resp = requests.get(
    "https://demo.duendesoftware.com/api/test",
    headers={"Authorization": f"Bearer {access_token}"},
)
print(f"  API status    : {api_resp.status_code}")
print(f"  API response  : {api_resp.text[:120]}")

# Short-lived token (75 s) — handy for testing auto-refresh
print("\n  ── m2m.short client (75-second token — test refresh logic) ──")
short_resp = requests.post(
    "https://demo.duendesoftware.com/connect/token",
    data={
        "grant_type": "client_credentials",
        "client_id": "m2m.short",
        "client_secret": "secret",
        "scope": "api",
    },
)
short_data = short_resp.json()
print(
    f"  Expires in    : {short_data['expires_in']}s  ← apikit will refresh 30s before this")
print(f"  Access token  : {short_data['access_token'][:48]}...")

# ── 7. from_config with extra headers ────────────────────────────────────────
print("\n▶ Apikit.from_config(ApiConfig(...))  — bearer + custom headers")
cfg = ApiConfig(
    base_url="https://httpbin.org",
    auth=AuthConfig(type="bearer", token="config-level-token"),
    headers={"X-App-Version": "2.0"},
)
client = Apikit.from_config(cfg)
resp = client.fetch_records("/bearer", show_progress=False)
print(f"  Authenticated : {resp[0].get('authenticated')}")
print(f"  Token         : {resp[0].get('token')}")

print("\n✓ All authentication examples complete — every call used a real endpoint.\n")

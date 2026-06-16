"""
11_webhooks.py
==============
Receive, validate, and process inbound webhooks locally — no ngrok needed.

Demonstrates:
  • WebhookReceiver        — local HTTP server in a background thread
  • StripeWebhookValidator — HMAC-SHA256 via Stripe-Signature header
  • GitHubWebhookValidator — HMAC-SHA256 via X-Hub-Signature-256 header
  • GenericHmacValidator   — configurable header + prefix (HubSpot, Shopify)
  • WebhookEvent           — event_id, received_at, headers, payload
  • receiver.to_polars()   — all captured events as a Polars DataFrame
  • receiver.to_pandas()   — same, Pandas
  • output_file="events.ndjson" — stream events to disk as they arrive
  • dry_run=True            — print server config without binding a port
  • WebhookSignatureError  — raised on tampered or missing signatures

The demo fires real HTTP requests at the local server using httpx so you
can see the full round-trip without needing a live webhook provider.

Run:
    python 11_webhooks.py
"""

import hashlib
import hmac
import json
import time
import tempfile
import os
import threading
from pathlib import Path

import httpx

from iki_apikit import (
    WebhookReceiver,
    WebhookEvent,
    StripeWebhookValidator,
    GitHubWebhookValidator,
    GenericHmacValidator,
    WebhookSignatureError,
)

print("=" * 60)
print("11 · WEBHOOK RECEIVER")
print("=" * 60)


# ── helpers ───────────────────────────────────────────────────────────────────

def _stripe_sig(payload: bytes, secret: str) -> str:
    """Reproduce Stripe's Stripe-Signature header for testing."""
    ts = str(int(time.time()))
    signed = f"{ts}.".encode() + payload
    v1 = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={v1}"


def _github_sig(payload: bytes, secret: str) -> str:
    """Reproduce GitHub's X-Hub-Signature-256 header for testing."""
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _generic_sig(payload: bytes, secret: str) -> str:
    """Generic HMAC-SHA256 for HubSpot / Shopify style."""
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def _post(port: int, path: str, payload: dict, headers: dict) -> httpx.Response:
    """Fire a POST to the local receiver."""
    raw = json.dumps(payload).encode()
    return httpx.post(
        f"http://127.0.0.1:{port}{path}",
        content=raw,
        headers={"Content-Type": "application/json", **headers},
        timeout=5,
    )


# ── 1. dry_run=True — preview without binding ─────────────────────────────────
print("\n▶ WebhookReceiver(dry_run=True)  — config preview, no port bound")
receiver_dry = WebhookReceiver(
    port=8080,
    path="/webhook",
    validator=StripeWebhookValidator("whsec_preview_only"),
    dry_run=True,
)
receiver_dry.start()   # prints the config, does NOT bind a socket
print(f"  event_count after dry start: {receiver_dry.event_count}  (always 0)")


# ── 2. Stripe webhook receiver ────────────────────────────────────────────────
print("\n▶ StripeWebhookValidator  — real HMAC-SHA256 round-trip")

STRIPE_SECRET = "whsec_test_abc123xyz"
stripe_receiver = WebhookReceiver(
    port=8181,
    path="/stripe/webhook",
    validator=StripeWebhookValidator(STRIPE_SECRET, tolerance_seconds=300),
    provider="stripe",
    max_events=500,
)
stripe_receiver.start()
time.sleep(0.1)  # let the server thread bind

# Simulate a payment_intent.succeeded event
event_payload = {
    "id": "evt_1OTestAbcDef",
    "type": "payment_intent.succeeded",
    "data": {
        "object": {
            "id": "pi_3OTestAbcDef",
            "amount": 4999,
            "currency": "php",
            "status": "succeeded",
        }
    },
}
raw = json.dumps(event_payload).encode()
sig = _stripe_sig(raw, STRIPE_SECRET)

resp = _post(8181, "/stripe/webhook", event_payload, {"Stripe-Signature": sig})
print(f"  POST → status: {resp.status_code}  body: {resp.json()}")
time.sleep(0.05)

# Send a second event
event2 = {
    "id": "evt_2OTestXyz",
    "type": "customer.subscription.deleted",
    "data": {"object": {"id": "sub_abc", "status": "canceled"}},
}
raw2 = json.dumps(event2).encode()
sig2 = _stripe_sig(raw2, STRIPE_SECRET)
_post(8181, "/stripe/webhook", event2, {"Stripe-Signature": sig2})
time.sleep(0.05)

print(f"  Events captured : {stripe_receiver.event_count}")
for ev in stripe_receiver.events:
    print(f"    {ev.event_id:<30} type={ev.payload.get('type')!r}")

# Access as DataFrame
try:
    df = stripe_receiver.to_polars()
    print(f"  to_polars() shape : {df.shape}")
    print(f"  columns           : {df.columns}")
except ImportError:
    df = stripe_receiver.to_pandas()
    print(f"  to_pandas() shape : {df.shape}")

stripe_receiver.stop()


# ── 3. Tampered signature → WebhookSignatureError ────────────────────────────
print("\n▶ Tampered payload → 400 + WebhookSignatureError")

# Start a fresh receiver on a different port
tamper_receiver = WebhookReceiver(
    port=8182,
    path="/webhook",
    validator=StripeWebhookValidator("whsec_real_secret"),
    provider="stripe",
)
tamper_receiver.start()
time.sleep(0.1)

bad_payload = {"evil": "tampered data"}
good_raw = json.dumps({"legit": "original"}).encode()
bad_sig = _stripe_sig(good_raw, "whsec_real_secret")  # sig for different body

resp_bad = _post(8182, "/webhook", bad_payload, {"Stripe-Signature": bad_sig})
print(f"  Status for tampered body  : {resp_bad.status_code}  (expected 400)")
print(f"  Response                  : {resp_bad.json()}")
print(
    f"  Events accepted           : {tamper_receiver.event_count}  (should be 0)")

tamper_receiver.stop()


# ── 4. GitHub webhook receiver ────────────────────────────────────────────────
print("\n▶ GitHubWebhookValidator  — X-Hub-Signature-256")

GITHUB_SECRET = "github_webhook_secret_2024"
gh_receiver = WebhookReceiver(
    port=8183,
    path="/github",
    validator=GitHubWebhookValidator(GITHUB_SECRET),
    provider="github",
)
gh_receiver.start()
time.sleep(0.1)

push_event = {
    "ref": "refs/heads/main",
    "repository": {"full_name": "myorg/myrepo", "default_branch": "main"},
    "pusher": {"name": "alice"},
    "commits": [
        {"id": "abc123", "message": "feat: add apikit webhook example",
            "author": {"name": "Alice"}},
        {"id": "def456", "message": "chore: update deps", "author": {"name": "Alice"}},
    ],
}
raw_push = json.dumps(push_event).encode()
gh_sig = _github_sig(raw_push, GITHUB_SECRET)

resp_gh = _post(8183, "/github", push_event, {
    "X-GitHub-Event": "push",
    "X-Hub-Signature-256": gh_sig,
    "X-GitHub-Delivery": "abc-def-ghi-123",   # used as event_id
})
print(f"  POST → {resp_gh.status_code}")
time.sleep(0.05)

ev: WebhookEvent = gh_receiver.events[0]
print(f"  event_id    : {ev.event_id}")
print(f"  provider    : {ev.provider}")
print(f"  commits     : {len(ev.payload['commits'])}")
print(f"  pusher      : {ev.payload['pusher']['name']}")
print(f"  to_dict()   : {list(ev.to_dict().keys())}")

gh_receiver.stop()


# ── 5. GenericHmacValidator — HubSpot / Shopify style ────────────────────────
print("\n▶ GenericHmacValidator  — custom header + prefix (HubSpot style)")

HUBSPOT_SECRET = "hs_signing_secret_xyz"
hs_receiver = WebhookReceiver(
    port=8184,
    path="/hs-webhook",
    validator=GenericHmacValidator(
        secret=HUBSPOT_SECRET,
        header_name="X-HubSpot-Signature",
        prefix="",           # HubSpot doesn't add a prefix
    ),
    provider="hubspot",
)
hs_receiver.start()
time.sleep(0.1)

hs_payload = {
    "subscriptionType": "contact.creation",
    "objectId": 12345,
    "changeSource": "CRM",
    "eventId": 9988776655,
}
raw_hs = json.dumps(hs_payload).encode()
hs_sig = _generic_sig(raw_hs, HUBSPOT_SECRET)

resp_hs = _post(8184, "/hs-webhook", hs_payload,
                {"X-HubSpot-Signature": hs_sig})
print(f"  HubSpot POST → {resp_hs.status_code}")
time.sleep(0.05)
print(
    f"  Event captured: subscriptionType={hs_receiver.events[0].payload['subscriptionType']!r}")

hs_receiver.stop()


# ── 6. Events streamed to disk (NDJSON) ───────────────────────────────────────
print("\n▶ output_file='events.ndjson'  — events written as they arrive")

with tempfile.TemporaryDirectory() as tmp:
    out_path = Path(tmp) / "events.ndjson"

    file_receiver = WebhookReceiver(
        port=8185,
        path="/events",
        output_file=out_path,
        output_format="ndjson",
        validator=GitHubWebhookValidator(GITHUB_SECRET),
        provider="github",
    )
    file_receiver.start()
    time.sleep(0.1)

    # Send 3 events
    for i in range(1, 4):
        body = {"action": "opened", "issue": {
            "number": i, "title": f"Bug #{i}"}}
        raw_body = json.dumps(body).encode()
        sig_val = _github_sig(raw_body, GITHUB_SECRET)
        _post(8185, "/events", body, {"X-Hub-Signature-256": sig_val})
        time.sleep(0.05)

    file_receiver.stop()

    lines = out_path.read_text().strip().split("\n")
    print(f"  Lines written to disk : {len(lines)}")
    for line in lines:
        record = json.loads(line)
        print(f"    event_id={record['event_id']!r}  "
              f"issue_number={record['payload']['issue']['number']}")


# ── 7. receiver.clear() — flush in-memory events ─────────────────────────────
print("\n▶ receiver.clear()  — flush in-memory buffer mid-run")
clear_receiver = WebhookReceiver(
    port=8186,
    path="/w",
    validator=GitHubWebhookValidator(GITHUB_SECRET),
)
clear_receiver.start()
time.sleep(0.1)

for i in range(3):
    b = json.dumps({"n": i}).encode()
    _post(8186, "/w", {"n": i},
          {"X-Hub-Signature-256": _github_sig(b, GITHUB_SECRET)})
    time.sleep(0.03)

print(f"  Before clear: {clear_receiver.event_count} events")
clear_receiver.clear()
print(f"  After clear : {clear_receiver.event_count} events")
clear_receiver.stop()


print("\n✓ Webhook examples complete.\n")

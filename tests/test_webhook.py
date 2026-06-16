"""
tests/features/webhook/test_webhook.py  —  §15  Webhook validators, events, and receiver.
"""

from __future__ import annotations

import time

import pytest

from kit import (
    WebhookReceiver,
    WebhookEvent,
    StripeWebhookValidator,
    GitHubWebhookValidator,
    GenericHmacValidator,
    WebhookSignatureError,
)


# ============================================================================
# Stripe
# ============================================================================


class TestStripeWebhookValidator:
    def _make_sig(self, secret: str, timestamp: int, payload: bytes) -> str:
        import hmac as hmac_lib
        import hashlib as hl
        signed = f"{timestamp}.".encode() + payload
        sig = hmac_lib.new(secret.encode(), signed, hl.sha256).hexdigest()
        return f"t={timestamp},v1={sig}"

    def test_valid_signature(self):
        secret = "whsec_test"
        payload = b'{"type":"payment_intent.created"}'
        ts = int(time.time())
        sig = self._make_sig(secret, ts, payload)
        validator = StripeWebhookValidator(secret)
        assert validator.validate(payload, {"stripe-signature": sig}) is True

    def test_invalid_signature_raises(self):
        validator = StripeWebhookValidator("correct_secret")
        payload = b'{"type":"test"}'
        ts = int(time.time())
        bad_sig = f"t={ts},v1=deadbeef"
        with pytest.raises(WebhookSignatureError, match="mismatch"):
            validator.validate(payload, {"stripe-signature": bad_sig})

    def test_missing_header_raises(self):
        validator = StripeWebhookValidator("secret")
        with pytest.raises(WebhookSignatureError, match="Missing"):
            validator.validate(b"payload", {})

    def test_expired_timestamp_raises(self):
        secret = "whsec_test"
        payload = b'{"type":"test"}'
        old_ts = int(time.time()) - 400
        sig = self._make_sig(secret, old_ts, payload)
        validator = StripeWebhookValidator(secret, tolerance_seconds=300)
        with pytest.raises(WebhookSignatureError, match="timestamp"):
            validator.validate(payload, {"stripe-signature": sig})


# ============================================================================
# GitHub
# ============================================================================


class TestGitHubWebhookValidator:
    def _make_sig(self, secret: str, payload: bytes) -> str:
        import hmac as hmac_lib
        import hashlib as hl
        return "sha256=" + hmac_lib.new(secret.encode(), payload, hl.sha256).hexdigest()

    def test_valid_signature(self):
        secret = "github_secret"
        payload = b'{"action":"opened"}'
        sig = self._make_sig(secret, payload)
        validator = GitHubWebhookValidator(secret)
        assert validator.validate(payload, {"x-hub-signature-256": sig}) is True

    def test_invalid_signature_raises(self):
        validator = GitHubWebhookValidator("secret")
        with pytest.raises(WebhookSignatureError, match="mismatch"):
            validator.validate(b"payload", {"x-hub-signature-256": "sha256=deadbeef"})

    def test_missing_header_raises(self):
        validator = GitHubWebhookValidator("secret")
        with pytest.raises(WebhookSignatureError, match="Missing"):
            validator.validate(b"payload", {})

    def test_wrong_prefix_raises(self):
        validator = GitHubWebhookValidator("secret")
        with pytest.raises(WebhookSignatureError):
            validator.validate(b"payload", {"x-hub-signature-256": "md5=abc123"})


# ============================================================================
# Generic HMAC
# ============================================================================


class TestGenericHmacValidator:
    def _make_sig(self, secret: str, payload: bytes) -> str:
        import hmac as hmac_lib
        import hashlib as hl
        return hmac_lib.new(secret.encode(), payload, hl.sha256).hexdigest()

    def test_valid_signature(self):
        secret = "hmac_secret"
        payload = b"test payload"
        sig = self._make_sig(secret, payload)
        validator = GenericHmacValidator(secret, header_name="X-Signature")
        assert validator.validate(payload, {"x-signature": sig}) is True

    def test_invalid_signature_raises(self):
        validator = GenericHmacValidator("secret", header_name="X-Sig")
        with pytest.raises(WebhookSignatureError, match="mismatch"):
            validator.validate(b"payload", {"x-sig": "badhash"})

    def test_prefix_stripping(self):
        secret = "s"
        payload = b"data"
        import hmac as hmac_lib
        import hashlib as hl
        raw = hmac_lib.new(secret.encode(), payload, hl.sha256).hexdigest()
        validator = GenericHmacValidator(secret, header_name="X-Sig", prefix="sha256=")
        assert validator.validate(payload, {"x-sig": f"sha256={raw}"}) is True


# ============================================================================
# WebhookEvent
# ============================================================================


class TestWebhookEvent:
    def test_to_dict_has_all_fields(self):
        event = WebhookEvent(
            event_id="wh_001",
            received_at=1234567890.0,
            headers={"content-type": "application/json"},
            payload={"type": "payment"},
            raw=b'{"type":"payment"}',
            provider="stripe",
        )
        d = event.to_dict()
        assert d["event_id"] == "wh_001"
        assert d["provider"] == "stripe"
        assert d["payload"] == {"type": "payment"}

    def test_repr(self):
        event = WebhookEvent("id1", 0.0, {}, {}, b"", "github")
        assert "WebhookEvent" in repr(event)
        assert "id1" in repr(event)


# ============================================================================
# WebhookReceiver
# ============================================================================


class TestWebhookReceiver:
    def test_dry_run_start_does_not_bind_port(self):
        receiver = WebhookReceiver(port=9999, dry_run=True)
        receiver.start()
        assert receiver._server is None

    def test_events_empty_on_init(self):
        receiver = WebhookReceiver(dry_run=True)
        assert receiver.event_count == 0
        assert receiver.events == []

    def test_clear_removes_events(self):
        receiver = WebhookReceiver(dry_run=True)
        event = WebhookEvent("wh_1", time.time(), {}, {"type": "test"}, b"{}", "test")
        with receiver._event_lock:
            receiver._events.append(event)
        assert receiver.event_count == 1
        receiver.clear()
        assert receiver.event_count == 0

    def test_store_event_respects_max(self):
        receiver = WebhookReceiver(max_events=2, dry_run=True)
        for i in range(5):
            event = WebhookEvent(f"wh_{i}", time.time(), {}, {}, b"{}", None)
            receiver._store_event(event)
        assert receiver.event_count == 2

    def test_to_polars_from_events(self):
        pytest.importorskip("polars")
        receiver = WebhookReceiver(dry_run=True)
        event = WebhookEvent("wh_1", time.time(), {}, {"type": "test"}, b"{}", "test")
        with receiver._event_lock:
            receiver._events.append(event)
        df = receiver.to_polars()
        assert len(df) == 1

    def test_make_event_uses_x_request_id_header(self):
        receiver = WebhookReceiver(dry_run=True)
        headers = {"x-request-id": "req-abc123"}
        payload = {"type": "test"}
        event = receiver._make_event(b"{}", headers, payload)
        assert event.event_id == "req-abc123"

    def test_make_event_falls_back_to_counter(self):
        receiver = WebhookReceiver(dry_run=True)
        event = receiver._make_event(b"{}", {}, {})
        assert event.event_id.startswith("wh_")

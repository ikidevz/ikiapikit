import hmac
import hashlib
import time

from ...core.exceptions import WebhookSignatureError

from abc import ABC, abstractmethod


class WebhookValidator(ABC):
    """Abstract base for provider-specific webhook signature validators."""

    @abstractmethod
    def validate(self, payload: bytes, headers: dict) -> bool:
        """Return True if signature is valid, raise WebhookSignatureError if not."""


class StripeWebhookValidator(WebhookValidator):
    """Validates Stripe webhook signatures via Stripe-Signature header."""

    def __init__(self, signing_secret: str, tolerance_seconds: int = 300):
        self._secret = signing_secret
        self._tolerance = tolerance_seconds

    def validate(self, payload: bytes, headers: dict) -> bool:
        sig_header = headers.get(
            "stripe-signature") or headers.get("Stripe-Signature", "")
        parts = dict(item.split("=", 1)
                     for item in sig_header.split(",") if "=" in item)
        timestamp = parts.get("t")
        v1 = parts.get("v1")
        if not timestamp or not v1:
            raise WebhookSignatureError(
                "Missing Stripe-Signature header components.")
        if abs(time.time() - float(timestamp)) > self._tolerance:
            raise WebhookSignatureError(
                "Stripe webhook timestamp too old (replay attack?).")
        signed_payload = f"{timestamp}.".encode() + payload
        expected = hmac.new(self._secret.encode(),
                            signed_payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, v1):
            raise WebhookSignatureError("Stripe webhook signature mismatch.")
        return True


class GitHubWebhookValidator(WebhookValidator):
    """Validates GitHub webhook signatures via X-Hub-Signature-256."""

    def __init__(self, secret: str):
        self._secret = secret

    def validate(self, payload: bytes, headers: dict) -> bool:
        sig = headers.get(
            "x-hub-signature-256") or headers.get("X-Hub-Signature-256", "")
        if not sig.startswith("sha256="):
            raise WebhookSignatureError("Missing X-Hub-Signature-256 header.")
        expected = "sha256=" + hmac.new(
            self._secret.encode(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise WebhookSignatureError("GitHub webhook signature mismatch.")
        return True


class GenericHmacValidator(WebhookValidator):
    """Generic HMAC-SHA256 validator for HubSpot, Shopify, and others."""

    def __init__(
        self,
        secret: str,
        header_name: str = "X-Signature",
        prefix: str = "",
        algorithm: str = "sha256",
    ):
        self._secret = secret
        self._header = header_name.lower()
        self._prefix = prefix
        self._algo = algorithm

    def validate(self, payload: bytes, headers: dict) -> bool:
        sig = headers.get(self._header, "")
        if self._prefix and sig.startswith(self._prefix):
            sig = sig[len(self._prefix):]
        hash_fn = hashlib.sha256 if self._algo == "sha256" else hashlib.sha1
        expected = hmac.new(self._secret.encode(),
                            payload, hash_fn).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise WebhookSignatureError(
                f"Signature mismatch for header '{self._header}'.")
        return True

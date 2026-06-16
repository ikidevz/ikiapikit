from typing import Optional


class WebhookEvent:
    """A single received and validated webhook event."""

    def __init__(
        self,
        event_id: str,
        received_at: float,
        headers: dict,
        payload: dict,
        raw: bytes,
        provider: Optional[str] = None,
    ):
        self.event_id = event_id
        self.received_at = received_at
        self.headers = headers
        self.payload = payload
        self.raw = raw
        self.provider = provider

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "received_at": self.received_at,
            "provider": self.provider,
            "headers": self.headers,
            "payload": self.payload,
        }

    def __repr__(self) -> str:
        return f"WebhookEvent(id={self.event_id!r}, provider={self.provider!r})"

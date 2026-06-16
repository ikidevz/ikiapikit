import time
import orjson
import logging
import threading
import polars as pl
import pandas as pd

from ...core.types import OutputFormat
from ...core.exceptions import ApikitError, WebhookSignatureError
from ...io.writers.factory import get_writer
from ...io.transform.dataframes import records_to_pandas, records_to_polars
from .validators import WebhookValidator
from .event import WebhookEvent

from pathlib import Path
from typing import Optional, Union
from rich.console import Console
from http.server import BaseHTTPRequestHandler, HTTPServer
console = Console(stderr=True)
logger = logging.getLogger("iki-apikit")

_HAS_HTTP_SERVER = True


class WebhookReceiver:
    """
    A lightweight local HTTP server that receives, validates, and records
    incoming webhooks — no ngrok or external tools needed.

    Usage:
        receiver = WebhookReceiver(
            port=8080,
            path="/webhook",
            validator=StripeWebhookValidator("whsec_..."),
            output_file="events.ndjson",
        )
        receiver.start()
        events = receiver.events
        receiver.stop()
    """

    def __init__(
        self,
        port: int = 8080,
        host: str = "0.0.0.0",
        path: str = "/webhook",
        validator: Optional[WebhookValidator] = None,
        output_file: Optional[Union[str, Path]] = None,
        output_format: OutputFormat = "ndjson",
        max_events: int = 10_000,
        dry_run: bool = False,
        provider: Optional[str] = None,
    ):
        self.port = port
        self.host = host
        self.path = path
        self.validator = validator
        self.output_file = Path(output_file) if output_file else None
        self.output_format = output_format
        self.max_events = max_events
        self.dry_run = dry_run
        self.provider = provider

        self._events: list[WebhookEvent] = []
        self._event_lock = threading.Lock()
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._event_counter = 0

    def start(self) -> None:
        """Start the webhook receiver in a background thread."""
        if self.dry_run:
            console.print(
                f"[bold yellow]DRY RUN[/] — WebhookReceiver would listen on "
                f"[cyan]http://{self.host}:{self.port}{self.path}[/]"
            )
            return

        if not _HAS_HTTP_SERVER:
            raise ApikitError("http.server module not available.")

        receiver = self

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self_h):
                if self_h.path != receiver.path:
                    self_h.send_response(404)
                    self_h.end_headers()
                    return
                try:
                    length = int(self_h.headers.get("Content-Length", 0))
                    raw = self_h.rfile.read(length)
                    headers_dict = {
                        k.lower(): v for k, v in self_h.headers.items()}
                    if receiver.validator:
                        receiver.validator.validate(raw, headers_dict)
                    payload = orjson.loads(raw)
                    event = receiver._make_event(raw, headers_dict, payload)
                    receiver._store_event(event)
                    self_h.send_response(200)
                    self_h.send_header("Content-Type", "application/json")
                    self_h.end_headers()
                    self_h.wfile.write(orjson.dumps(
                        {"received": True, "id": event.event_id}))
                except WebhookSignatureError as e:
                    logger.warning("Signature validation failed: %s", e)
                    self_h.send_response(400)
                    self_h.end_headers()
                    self_h.wfile.write(orjson.dumps({"error": str(e)}))
                except Exception as e:
                    logger.error("Webhook handler error: %s", e)
                    self_h.send_response(500)
                    self_h.end_headers()

            def log_message(self_h, fmt, *args):
                logger.debug("Webhook: " + fmt, *args)

        self._server = HTTPServer((self.host, self.port), _Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True)
        self._thread.start()
        console.print(
            f"[green]✓[/] WebhookReceiver started → "
            f"[cyan]http://{self.host}:{self.port}{self.path}[/]"
        )

    def stop(self) -> None:
        """Stop the server and flush buffered output."""
        if self.dry_run:
            return
        if self._server:
            self._server.shutdown()
            console.print("[yellow]WebhookReceiver stopped.[/]")
        if self.output_file and self.output_format == "parquet" and self._events:
            records = [e.to_dict() for e in self._events]
            get_writer("parquet").write(records, self.output_file)

    @property
    def events(self) -> list[WebhookEvent]:
        with self._event_lock:
            return list(self._events)

    @property
    def event_count(self) -> int:
        with self._event_lock:
            return len(self._events)

    def to_polars(self) -> "pl.DataFrame":
        return records_to_polars([e.to_dict() for e in self.events])

    def to_pandas(self) -> "pd.DataFrame":
        return records_to_pandas([e.to_dict() for e in self.events])

    def clear(self) -> None:
        with self._event_lock:
            self._events.clear()

    def _make_event(self, raw: bytes, headers: dict, payload: dict) -> WebhookEvent:
        self._event_counter += 1
        event_id = (
            headers.get("x-request-id")
            or headers.get("x-webhook-id")
            or headers.get("x-github-delivery")
            or f"wh_{self._event_counter:06d}"
        )
        return WebhookEvent(
            event_id=event_id, received_at=time.time(),
            headers=headers, payload=payload, raw=raw, provider=self.provider,
        )

    def _store_event(self, event: WebhookEvent) -> None:
        with self._event_lock:
            if len(self._events) < self.max_events:
                self._events.append(event)
        if self.output_file and self.output_format in ("ndjson", "jsonl"):
            with open(self.output_file, "ab") as f:
                f.write(orjson.dumps(event.to_dict()) + b"\n")
        logger.info("Received webhook event %s", event.event_id)

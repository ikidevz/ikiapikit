import httpx
import asyncio
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger("ikiapikit")


class HookContext:
    """
    Rich context object passed to every hook callback.

    Not all fields are populated for every event — unused fields default to
    None or 0. Check the event type via the 'event' field if needed.
    """

    __slots__ = (
        "event", "url", "method", "status_code", "latency_ms",
        "headers", "record_count", "page_number", "cumulative_records",
        "attempt", "wait_seconds", "error_type", "error_message", "error",
    )

    def __init__(
        self,
        event: str,
        url: str = "",
        method: str = "GET",
        status_code: int = 0,
        latency_ms: float = 0.0,
        headers: Optional[dict] = None,
        record_count: int = 0,
        page_number: int = 0,
        cumulative_records: int = 0,
        attempt: int = 0,
        wait_seconds: float = 0.0,
        error_type: str = "",
        error_message: str = "",
        error: Optional[Exception] = None,
    ):
        self.event = event
        self.url = url
        self.method = method
        self.status_code = status_code
        self.latency_ms = latency_ms
        self.headers = headers or {}
        self.record_count = record_count
        self.page_number = page_number
        self.cumulative_records = cumulative_records
        self.attempt = attempt
        self.wait_seconds = wait_seconds
        self.error_type = error_type
        self.error_message = error_message
        self.error = error


HookFn = Callable[[HookContext], Any]


class HookChain:
    """
    Fan-out hook: wraps multiple hook callbacks for a single event type.

    Usage:
        chain = HookChain(on_error=[slack_fn, pagerduty_fn, metrics_fn])
        client = Apikit(..., on_error=chain)
    """

    def __init__(
        self,
        on_error: Optional[list[HookFn]] = None,
        on_rate_limit: Optional[list[HookFn]] = None,
        on_retry: Optional[list[HookFn]] = None,
        on_response: Optional[list[HookFn]] = None,
        on_page: Optional[list[HookFn]] = None,
    ):
        self._hooks: dict[str, list[HookFn]] = {
            "on_error":      on_error or [],
            "on_rate_limit": on_rate_limit or [],
            "on_retry":      on_retry or [],
            "on_response":   on_response or [],
            "on_page":       on_page or [],
        }

    def __call__(self, ctx: HookContext) -> None:
        """Fire all hooks registered for ctx.event."""
        for fn in self._hooks.get(ctx.event, []):
            try:
                result = fn(ctx)
                if asyncio.iscoroutine(result):
                    asyncio.get_event_loop().run_until_complete(result)
            except Exception as exc:
                logger.warning("Hook %s raised: %s", fn, exc)


class HookRegistry:
    """
    Internal registry — holds one (optional) callable per event.
    Each callable may itself be a HookChain for fan-out.
    """

    def __init__(
        self,
        on_error: Optional[HookFn] = None,
        on_rate_limit: Optional[HookFn] = None,
        on_retry: Optional[HookFn] = None,
        on_response: Optional[HookFn] = None,
        on_page: Optional[HookFn] = None,
    ):
        self._hooks: dict[str, Optional[HookFn]] = {
            "on_error":      on_error,
            "on_rate_limit": on_rate_limit,
            "on_retry":      on_retry,
            "on_response":   on_response,
            "on_page":       on_page,
        }

    def fire(self, event: str, ctx: HookContext) -> None:
        fn = self._hooks.get(event)
        if fn is None:
            return
        try:
            result = fn(ctx)
            if asyncio.iscoroutine(result):
                asyncio.get_event_loop().run_until_complete(result)
        except Exception as exc:
            logger.warning("Hook '%s' raised: %s", event, exc)

    def remove(self, fn: HookFn, event: str) -> None:
        if self._hooks.get(event) is fn:
            self._hooks[event] = None

    def clear(self, event: Optional[str] = None) -> None:
        if event:
            self._hooks[event] = None
        else:
            self._hooks = {k: None for k in self._hooks}

    def clear_all(self) -> None:
        self.clear()


class LogHook:
    """
    Built-in hook: writes a structured log line on every successful response.

    Usage:
        client = Apikit(..., on_response=LogHook())
    """

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        level: int = logging.INFO,
        include_headers: bool = False,
    ):
        self._logger = logger or logging.getLogger("apikit.hooks.log")
        self._level = level
        self._include_headers = include_headers

    def __call__(self, ctx: HookContext) -> None:
        msg = (
            f"[apikit] {ctx.method} {ctx.url} → {ctx.status_code} "
            f"({ctx.latency_ms:.0f}ms, {ctx.record_count} records)"
        )
        if self._include_headers:
            msg += f" headers={dict(ctx.headers)}"
        self._logger.log(self._level, msg)


class SlackHook:
    """
    Built-in hook: posts an alert to a Slack webhook URL on errors / 429s.

    Usage:
        slack = SlackHook(webhook_url=os.environ["SLACK_WEBHOOK_URL"])
        client = Apikit(..., on_error=slack, on_rate_limit=slack)
    """

    def __init__(
        self,
        webhook_url: str,
        channel: Optional[str] = None,
        mention: Optional[str] = None,
        min_status: int = 400,
    ):
        self._url = webhook_url
        self._channel = channel
        self._mention = mention
        self._min_status = min_status

    def __call__(self, ctx: HookContext) -> None:
        if ctx.status_code and ctx.status_code < self._min_status:
            return
        mention = f"{self._mention} " if self._mention else ""
        text = (
            f"{mention}:warning: *apikit alert* — "
            f"`{ctx.method} {ctx.url}` returned `{ctx.status_code}`"
        )
        if ctx.error_message:
            text += f"\n>{ctx.error_message}"
        payload: dict[str, Any] = {"text": text}
        if self._channel:
            payload["channel"] = self._channel
        try:
            with httpx.Client(timeout=5) as c:
                c.post(self._url, json=payload)
        except Exception as exc:
            logger.warning("SlackHook failed to post: %s", exc)

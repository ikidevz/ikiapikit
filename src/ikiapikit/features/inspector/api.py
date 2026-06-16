import time
import orjson

from typing import Any, Optional
from ...core.models import ApiConfig
from ...http.client import RestClient
from .result import InspectorResult
from ...features.rate_limit import RateLimitState


class ApiInspector:
    """
    Fires a single probe request to an endpoint and returns a rich
    InspectorResult with headers, latency, schema, pagination hints,
    rate-limit state, and a ready-to-use ApiConfig snippet.
    """

    _CURSOR_PATTERNS = ["next_cursor", "nextCursor", "next_token", "cursor"]
    _OFFSET_PATTERNS = ["offset", "skip", "start"]

    def __init__(self, config: ApiConfig):
        self.config = config
        self._http = RestClient(config)

    def inspect_sync(
        self,
        endpoint: str,
        *,
        params: Optional[dict] = None,
        dry_run: bool = False,
    ) -> InspectorResult:
        if dry_run:
            return self._dry_run_result(endpoint, params)
        start = time.monotonic()
        body, headers = self._http.request_sync_full(
            "GET", endpoint, params=params)
        latency_ms = (time.monotonic() - start) * 1000
        return self._build_result(endpoint, body, headers, latency_ms, dry_run=False)

    async def inspect_async(
        self,
        endpoint: str,
        *,
        params: Optional[dict] = None,
        dry_run: bool = False,
    ) -> InspectorResult:
        if dry_run:
            return self._dry_run_result(endpoint, params)
        start = time.monotonic()
        body, headers = await self._http.request_async_full("GET", endpoint, params=params)
        latency_ms = (time.monotonic() - start) * 1000
        return self._build_result(endpoint, body, headers, latency_ms, dry_run=False)

    def _build_result(self, endpoint, body, headers, latency_ms, dry_run) -> InspectorResult:
        rl = RateLimitState()
        rl.ingest(headers)
        records = self._extract_records(body)
        content_type = headers.get("content-type", "unknown")
        size = len(orjson.dumps(body))
        pagination = self._detect_pagination(body, dict(headers))
        full_url = endpoint if endpoint.startswith(
            "http") else f"{self.config.base_url}{endpoint}"

        result = InspectorResult(
            url=full_url, status_code=200, latency_ms=round(latency_ms, 1),
            response_headers=dict(headers), response_body=body,
            rate_limit_state=rl, detected_pagination=pagination,
            content_type=content_type,
            record_count=len(records) if isinstance(records, list) else 1,
            response_size_bytes=size, dry_run=dry_run,
        )
        result._records = records if isinstance(records, list) else []
        return result

    def _dry_run_result(self, endpoint, params) -> InspectorResult:
        full_url = endpoint if endpoint.startswith(
            "http") else f"{self.config.base_url}{endpoint}"
        return InspectorResult(
            url=full_url, status_code=0, latency_ms=0.0,
            response_headers={}, response_body=None,
            rate_limit_state=RateLimitState(), detected_pagination=None,
            content_type="dry-run", record_count=0, response_size_bytes=0, dry_run=True,
        )

    def _extract_records(self, body: Any) -> list:
        if isinstance(body, list):
            return body
        if isinstance(body, dict):
            for v in body.values():
                if isinstance(v, list) and len(v) > 0:
                    return v
        return [body] if body else []

    def _detect_pagination(self, body: Any, headers: dict) -> Optional[str]:
        header_keys_lower = {k.lower() for k in headers}
        if "link" in header_keys_lower:
            return "link"
        if isinstance(body, dict):
            body_keys_lower = {k.lower() for k in body}
            for pat in self._CURSOR_PATTERNS:
                if pat.lower() in body_keys_lower:
                    return "cursor"
            if "pageinfo" in body_keys_lower or "page_info" in body_keys_lower:
                return "cursor"
            if "total" in body_keys_lower or "count" in body_keys_lower:
                for pat in self._OFFSET_PATTERNS:
                    if pat in body_keys_lower:
                        return "offset"
                return "page"
            if "next" in body_keys_lower:
                val = body.get("next") or body.get("Next")
                if isinstance(val, str) and val.startswith("http"):
                    return "link"
        return None

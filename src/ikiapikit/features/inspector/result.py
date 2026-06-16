from typing import Any, Optional
from urllib.parse import urlparse

from ...features.rate_limit import RateLimitState
from ...io.transform.flatten import flatten_records


class InspectorResult:
    """
    The result of a single inspect() call — everything you need to understand
    and configure a new API endpoint.
    """

    def __init__(
        self,
        url: str,
        status_code: int,
        latency_ms: float,
        response_headers: dict,
        response_body: Any,
        rate_limit_state: RateLimitState,
        detected_pagination: Optional[str],
        content_type: str,
        record_count: int,
        response_size_bytes: int,
        dry_run: bool = False,
    ):
        self.url = url
        self.status_code = status_code
        self.latency_ms = latency_ms
        self.response_headers = response_headers
        self.response_body = response_body
        self.rate_limit_state = rate_limit_state
        self.detected_pagination = detected_pagination
        self.content_type = content_type
        self.record_count = record_count
        self.response_size_bytes = response_size_bytes
        self.dry_run = dry_run
        self._records: list[dict] = []

    def suggested_config(self) -> str:
        """Generate a copy-paste ready ApiConfig snippet based on findings."""
        pagination_strategy = self.detected_pagination or "none"
        lines = [
            "from apikit import Apikit, ApiConfig, AuthConfig, PaginationConfig",
            "",
            "cfg = ApiConfig(",
            f'    base_url="{self._base_url()}",',
            '    auth=AuthConfig(type="bearer", token="YOUR_TOKEN"),',
        ]
        if pagination_strategy != "none":
            lines += [
                "    pagination=PaginationConfig(",
                f'        strategy="{pagination_strategy}",',
                "        page_size=100,",
                "    ),",
            ]
        lines += [")", "client = Apikit.from_config(cfg)"]
        return "\n".join(lines)

    def _base_url(self) -> str:
        parsed = urlparse(self.url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def schema_sample(self) -> dict:
        """Return field → python_type mapping from first record."""
        if not self._records:
            return {}
        flat = flatten_records(self._records[:1])
        return {k: type(v).__name__ for k, v in flat[0].items()} if flat else {}

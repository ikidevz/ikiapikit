import httpx
import logging
import orjson
import time
import asyncio

from .auth.factory import build_auth_strategy
from .pagination.base import PaginatorBase
from .pagination.strategies import NoPaginator
from ..core.models import ApiConfig
from ..core.exceptions import AuthError, RateLimitError

from typing import Optional, Generator, Any, AsyncIterator
from contextlib import asynccontextmanager, contextmanager
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    before_sleep_log,
)
from rich.progress import Progress

logger = logging.getLogger("iki-apikit")


class RetryableHTTPError(Exception):
    """Internal wrapper to trigger tenacity retry on specific status codes."""

    def __init__(self, response: httpx.Response):
        self.response = response
        super().__init__(f"HTTP {response.status_code}")


class RestClient:
    """
    Low-level HTTP client — wraps httpx with auth injection, retry, and
    rate-limit detection.
    """

    def __init__(self, config: ApiConfig):
        self.config = config
        self.auth = build_auth_strategy(config.auth)
        self._base_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            **config.headers,
        }

    # ── Sync ─────────────────────────────────────────────────────────────────

    @contextmanager
    def _sync_client(self) -> Generator[httpx.Client, None, None]:
        with httpx.Client(
            base_url=self.config.base_url,
            headers=self._base_headers,
            timeout=self.config.timeout,
            verify=self.config.verify_ssl,
            follow_redirects=self.config.follow_redirects,
        ) as client:
            yield client

    def _apply_auth_sync(self, request: httpx.Request) -> httpx.Request:
        return self.auth.apply_sync(request)

    def request_sync(
        self,
        method: str,
        url: str,
        *,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> Any:
        """Make a single sync HTTP request with retry logic. Returns parsed JSON body."""
        data, _ = self.request_sync_full(
            method, url, params=params, json_body=json_body, headers=headers)
        return data

    def request_sync_full(
        self,
        method: str,
        url: str,
        *,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> tuple:
        """Make a single sync HTTP request. Returns (parsed_body, response_headers)."""
        retry_cfg = self.config.retry

        @retry(
            retry=retry_if_exception_type(RetryableHTTPError),
            stop=stop_after_attempt(retry_cfg.max_attempts),
            wait=wait_exponential_jitter(
                initial=retry_cfg.min_wait,
                max=retry_cfg.max_wait,
                jitter=retry_cfg.jitter,
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        def _do() -> tuple:
            with self._sync_client() as client:
                req = client.build_request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=headers,
                )
                req = self._apply_auth_sync(req)
                resp = client.request(
                    method=req.method,
                    url=req.url,
                    headers=req.headers,
                    content=req.content,
                    params=params,
                )

                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", 5))
                    logger.warning("Rate limited — sleeping %ss", retry_after)
                    time.sleep(retry_after)
                    raise RetryableHTTPError(resp)

                if resp.status_code in retry_cfg.retry_on_status:
                    raise RetryableHTTPError(resp)

                if resp.status_code == 401:
                    raise AuthError(f"401 Unauthorized for {url}")

                resp.raise_for_status()
                body = orjson.loads(resp.content) if resp.content else {}
                return body, resp.headers

        return _do()

    def get_all_pages_sync(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        paginator: Optional[PaginatorBase] = None,
        progress: Optional[Progress] = None,
        task_id: Optional[Any] = None,
    ) -> list[dict]:
        """Fetch all pages synchronously, returning a flat list of records."""
        params = params or {}
        if paginator is None:
            paginator = NoPaginator(self.config.pagination)

        all_records: list[dict] = []
        current_params = paginator.first_params(params)
        current_url = endpoint

        while True:
            if "__link_next_url__" in current_params:
                current_url = current_params.pop("__link_next_url__")
                resp_json, resp_headers = self.request_sync_full(
                    "GET", current_url, params=None)
            else:
                resp_json, resp_headers = self.request_sync_full(
                    "GET", current_url, params=current_params)

            records = paginator.extract_records(resp_json)
            all_records.extend(records)

            if progress and task_id is not None:
                progress.advance(task_id, len(records))

            if not records:
                break

            next_params = paginator.next_params(
                current_params, resp_json, resp_headers)

            if next_params is None:
                break
            current_params = next_params

        return all_records

    # ── Async ─────────────────────────────────────────────────────────────────

    @asynccontextmanager
    async def _async_client(self):
        async with httpx.AsyncClient(
            base_url=self.config.base_url,
            headers=self._base_headers,
            timeout=self.config.timeout,
            verify=self.config.verify_ssl,
            follow_redirects=self.config.follow_redirects,
        ) as client:
            yield client

    async def request_async(
        self,
        method: str,
        url: str,
        *,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> Any:
        """Make a single async HTTP request with retry logic."""
        retry_cfg = self.config.retry
        attempt = 0

        while True:
            attempt += 1
            async with self._async_client() as client:
                req = client.build_request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=headers,
                )
                req = self._apply_auth_sync(req)
                resp = await client.request(
                    method=req.method,
                    url=req.url,
                    headers=req.headers,
                    content=req.content,
                    params=params,
                )

            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", 5))
                logger.warning("Rate limited — sleeping %ss", retry_after)
                await asyncio.sleep(retry_after)
                if attempt >= retry_cfg.max_attempts:
                    raise RateLimitError(retry_after)
                continue

            if resp.status_code in retry_cfg.retry_on_status:
                if attempt >= retry_cfg.max_attempts:
                    resp.raise_for_status()
                wait = min(retry_cfg.min_wait *
                           (2 ** (attempt - 1)), retry_cfg.max_wait)
                await asyncio.sleep(wait)
                continue

            if resp.status_code == 401:
                raise AuthError(f"401 Unauthorized for {url}")

            resp.raise_for_status()
            return orjson.loads(resp.content) if resp.content else {}

    async def request_async_full(
        self,
        method: str,
        url: str,
        *,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> tuple:
        """Async request returning (body, response_headers)."""
        retry_cfg = self.config.retry
        attempt = 0
        while True:
            attempt += 1
            async with self._async_client() as client:
                req = client.build_request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=headers,
                )
                req = self._apply_auth_sync(req)
                resp = await client.request(
                    method=req.method,
                    url=req.url,
                    headers=req.headers,
                    content=req.content,
                    params=params,
                )
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", 5))
                logger.warning("Rate limited — sleeping %ss", retry_after)
                await asyncio.sleep(retry_after)
                if attempt >= retry_cfg.max_attempts:
                    raise RateLimitError(retry_after)
                continue
            if resp.status_code in retry_cfg.retry_on_status:
                if attempt >= retry_cfg.max_attempts:
                    resp.raise_for_status()
                wait = min(retry_cfg.min_wait *
                           (2 ** (attempt - 1)), retry_cfg.max_wait)
                await asyncio.sleep(wait)
                continue
            if resp.status_code == 401:
                raise AuthError(f"401 Unauthorized for {url}")
            resp.raise_for_status()
            body = orjson.loads(resp.content) if resp.content else {}
            return body, resp.headers

    async def get_all_pages_async(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        paginator: Optional[PaginatorBase] = None,
        progress: Optional[Progress] = None,
        task_id: Optional[Any] = None,
    ) -> list[dict]:
        """Fetch all pages asynchronously, returning a flat list of records."""
        params = params or {}
        if paginator is None:
            paginator = NoPaginator(self.config.pagination)

        all_records: list[dict] = []
        current_params = paginator.first_params(params)
        current_url = endpoint

        while True:
            if "__link_next_url__" in current_params:
                current_url = current_params.pop("__link_next_url__")
                resp_json, resp_headers = await self.request_async_full("GET", current_url, params=None)
            else:
                resp_json, resp_headers = await self.request_async_full("GET", current_url, params=current_params)

            records = paginator.extract_records(resp_json)
            all_records.extend(records)

            if progress and task_id is not None:
                progress.advance(task_id, len(records))

            if not records:
                break

            next_params = paginator.next_params(
                current_params, resp_json, resp_headers)

            if next_params is None:
                break
            current_params = next_params

        return all_records

    async def astream(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        paginator: Optional[PaginatorBase] = None,
    ) -> AsyncIterator[dict]:
        """Async generator — yields individual records as they arrive."""
        params = params or {}
        if paginator is None:
            paginator = NoPaginator(self.config.pagination)

        current_params = paginator.first_params(params)
        current_url = endpoint

        while True:
            if "__link_next_url__" in current_params:
                current_url = current_params.pop("__link_next_url__")
                resp_json, resp_headers = await self.request_async_full("GET", current_url, params=None)
            else:
                resp_json, resp_headers = await self.request_async_full("GET", current_url, params=current_params)

            records = paginator.extract_records(resp_json)
            for record in records:
                yield record

            if not records:
                break

            next_params = paginator.next_params(
                current_params, resp_json, resp_headers)
            if next_params is None:
                break
            current_params = next_params

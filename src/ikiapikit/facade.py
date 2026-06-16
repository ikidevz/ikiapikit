from ikiapikit import (
    DEFAULT_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_PAGE_SIZE,
    AuthType,
    ApiConfig,
    AuthConfig,
    CacheConfig,
    RetryConfig,
    HookFn,
    RestClient,
    LruCache,
    build_cache,
    HookRegistry,
    DryRunResult,
    ConnectorRegistry,
    ConnectorNotFoundError,
    ConfigManager,
    SecretStr,
    PaginationStrategy,
    PaginatorBase,
    NoPaginator,
    build_paginator,
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
    HookContext,
    flatten_records,
    apply_field_ops,
    validate_records,
    ValidationResult,
    records_to_polars,
    ApikitError,
    records_to_pandas,
    OutputFormat,
    get_writer,
    InspectorResult,
    ApiInspector,
    print_inspector_result,
    GraphQLClient,

)

from typing import (
    Any,
    AsyncIterator,
    Callable,
    Literal,
    Optional,
    Union
)
from pathlib import Path
from rich.console import Console
import polars as pl
import pandas as pd
import httpx
import logging
import asyncio

logger = logging.getLogger("ikiapikit")
console = Console(stderr=True)


def _pl() -> Any:
    """Lazy import of polars — raises a clear message if not installed."""
    try:
        import polars as _polars
        return _polars
    except ImportError:
        raise ApikitError("polars is required: pip install polars")


def _pd() -> Any:
    """Lazy import of pandas — raises a clear message if not installed."""
    try:
        import pandas as _pandas
        return _pandas
    except ImportError:
        raise ApikitError("pandas is required: pip install pandas")


class Apikit:
    """
    The single entry point for all apikit operations.

    Quick start:
        client = Apikit.from_name("github", token="ghp_...")
        client = Apikit(base_url="https://api.example.com", auth="bearer", token="my-token")

        df = client.fetch_polars("/users", paginate=True)
        df = await client.afetch_pandas("/orders", paginate=True)
        async for record in client.astream("/events"):
            process(record)
        client.fetch_to_file("/data", format="parquet", file_path="output.parquet")

    New in this version:
        # Caching
        client = Apikit(..., cache=True, cache_ttl=300)

        # Hooks
        client = Apikit(..., on_error=my_fn, on_rate_limit=slack_hook)

        # Field selection
        client.fetch_records("/users", select=["id", "name", "email"])
        client.fetch_records("/users", exclude=["address", "company"])

        # Fan-out
        results = client.fetch_many(["/posts", "/users", "/todos"])

        # Validation
        result = client.fetch_records("/users", model=UserModel)

        # New HTTP methods
        client.patch("/contacts/1", body={"email": "new@example.com"})
        client.head("/posts/1")
        client.options("/api/endpoint")
    """

    def __init__(
        self,
        base_url: str,
        *,
        auth: AuthType = "none",
        token: Optional[str] = None,
        api_key: Optional[str] = None,
        api_key_header: str = "X-API-Key",
        api_key_query_param: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        token_url: Optional[str] = None,
        scopes: Optional[list[str]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: float = DEFAULT_TIMEOUT,
        verify_ssl: bool = True,
        max_retries: int = DEFAULT_MAX_RETRIES,
        config: Optional[ApiConfig] = None,
        # ── Feature 2: Caching ────────────────────────────────────────────────
        cache: Union[bool, "CacheConfig", None] = False,
        cache_ttl: int = 300,
        cache_key_fn: Optional[Callable] = None,
        # ── Feature 10: Hooks ─────────────────────────────────────────────────
        on_error: Optional[HookFn] = None,
        on_rate_limit: Optional[HookFn] = None,
        on_retry: Optional[HookFn] = None,
        on_response: Optional[HookFn] = None,
        on_page: Optional[HookFn] = None,
    ):
        if config is not None:
            self._config = config
        else:
            auth_cfg = AuthConfig(
                type=auth,
                token=token,
                api_key=api_key,
                api_key_header=api_key_header,
                api_key_query_param=api_key_query_param,
                username=username,
                password=password,
                client_id=client_id,
                client_secret=client_secret,
                token_url=token_url,
                scopes=scopes or [],
            )
            self._config = ApiConfig(
                base_url=base_url,
                auth=auth_cfg,
                headers=headers or {},
                timeout=timeout,
                verify_ssl=verify_ssl,
                retry=RetryConfig(max_attempts=max_retries),
            )

        self._http = RestClient(self._config)

        # ── Cache setup ───────────────────────────────────────────────────────
        # If cache=True but cache_ttl provided, honour the explicit TTL
        if cache is True and cache_ttl != 300:
            _cache_obj = LruCache(ttl=cache_ttl)
        else:
            _cache_obj = build_cache(cache)
        if cache_key_fn is not None and hasattr(_cache_obj, "make_key"):
            _cache_obj.make_key = cache_key_fn  # type: ignore[method-assign]
        self.cache = _cache_obj

        # ── Hook registry setup ───────────────────────────────────────────────
        self.hooks = HookRegistry(
            on_error=on_error,
            on_rate_limit=on_rate_limit,
            on_retry=on_retry,
            on_response=on_response,
            on_page=on_page,
        )

    # ── Constructors ──────────────────────────────────────────────────────────

    @classmethod
    def from_config(
        cls,
        config: ApiConfig,
        *,
        cache: Union[bool, "CacheConfig", None] = False,
        cache_ttl: int = 300,
        on_error: Optional[HookFn] = None,
        on_rate_limit: Optional[HookFn] = None,
        on_retry: Optional[HookFn] = None,
        on_response: Optional[HookFn] = None,
        on_page: Optional[HookFn] = None,
    ) -> "Apikit":
        """Create from a fully-populated ApiConfig object."""
        return cls(
            base_url=config.base_url,
            config=config,
            cache=cache,
            cache_ttl=cache_ttl,
            on_error=on_error,
            on_rate_limit=on_rate_limit,
            on_retry=on_retry,
            on_response=on_response,
            on_page=on_page,
        )

    @classmethod
    def from_name(cls, name: str, token: Optional[str] = None, **kwargs: Any) -> "Apikit":
        """
        Create from a named connector (built-in registry first, then config file).

        Example:
            client = Apikit.from_name("github", token="ghp_...")
            client = Apikit.from_name("my_company_api")
        """
        try:
            config = ConnectorRegistry.build_config(
                name, token=token, **kwargs)
            return cls.from_config(config)
        except ConnectorNotFoundError:
            pass

        manager = ConfigManager()
        config = manager.get_api_config(name)
        if token:
            config.auth.token = SecretStr(token)
        return cls.from_config(config)

    # ── Pagination helper ─────────────────────────────────────────────────────

    def _make_paginator(
        self,
        paginate: bool,
        strategy: Optional[PaginationStrategy] = None,
        page_size: Optional[int] = None,
        data_path: Optional[str] = None,
    ) -> PaginatorBase:
        if not paginate:
            if data_path:
                cfg = self._config.pagination.model_copy()
                cfg.data_path = data_path
                return NoPaginator(cfg)
            return NoPaginator(self._config.pagination)
        cfg = self._config.pagination.model_copy()
        if strategy:
            cfg.strategy = strategy
        if page_size:
            cfg.page_size = page_size
        if data_path:
            cfg.data_path = data_path
        return build_paginator(cfg)

    @staticmethod
    def _make_progress() -> Progress:
        return Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Sync Methods
    # ─────────────────────────────────────────────────────────────────────────

    def fetch_records(
        self,
        endpoint: str,
        *,
        params: Optional[dict] = None,
        paginate: bool = False,
        strategy: Optional[PaginationStrategy] = None,
        page_size: Optional[int] = None,
        data_path: Optional[str] = None,
        show_progress: bool = True,
        dry_run: bool = False,
        # ── Feature 2: Cache ──────────────────────────────────────────────────
        cache: Optional[bool] = None,
        # ── Feature 6: Field selection ────────────────────────────────────────
        flatten: bool = False,
        select: Optional[list[str]] = None,
        exclude: Optional[list[str]] = None,
        rename: Optional[dict[str, str]] = None,
        transform_fn: Optional[Callable[[dict], dict]] = None,
        # ── Feature 8: Validation ─────────────────────────────────────────────
        model: Optional[type] = None,
        on_invalid: Literal["collect", "skip", "raise"] = "collect",
        strict: bool = False,
    ) -> Any:
        """
        Fetch records from a REST endpoint synchronously.

        Args:
            endpoint:     API path, e.g. "/users" or "/posts/1".
            params:       Query string parameters dict.
            paginate:     If True, follow all pagination pages.
            strategy:     Override pagination strategy for this call only.
            page_size:    Override page size for this call only.
            data_path:    Dot-path to records inside the response body.
            show_progress: Show Rich progress bar.
            dry_run:      Preview request without making network calls.
            cache:        True/False to override instance cache setting per call.
            flatten:      Flatten nested dicts with __ separator before selection.
            select:       Keep only these field names (dot-paths supported).
            exclude:      Drop these field names from every record.
            rename:       Rename fields: {"old_name": "new_name"}.
            transform_fn: Arbitrary per-record function applied after select/exclude/rename.
            model:        Pydantic BaseModel subclass — validate every record.
            on_invalid:   "collect" | "skip" | "raise" (used with model=).
            strict:       If True, disable Pydantic type coercion (used with model=).

        Returns:
            list[dict]        — default
            ValidationResult  — when model= and on_invalid='collect'
            list[ModelInstance] — when model= and on_invalid='skip'
            DryRunResult      — when dry_run=True
        """
        if dry_run:
            full_url = (
                endpoint if endpoint.startswith("http")
                else f"{self._config.base_url}{endpoint}"
            )
            result = DryRunResult(
                method="GET",
                url=full_url,
                params=params,
                headers=dict(self._http._base_headers),
                auth_type=self._config.auth.type,
                pagination_strategy=strategy or self._config.pagination.strategy,
                page_size=page_size or self._config.pagination.page_size,
            )
            result.display()
            return result

        # ── Cache check ───────────────────────────────────────────────────────
        use_cache = self.cache.enabled if cache is None else cache
        cache_key = self.cache.make_key(
            "GET", f"{self._config.base_url}{endpoint}", params)
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        # ── Fetch ─────────────────────────────────────────────────────────────
        paginator = self._make_paginator(
            paginate, strategy, page_size, data_path)
        cumulative = 0
        page_num = 0

        with self._make_progress() as progress:
            task = progress.add_task(f"Fetching {endpoint} …", total=None)

            if paginate and self.hooks._hooks.get("on_page"):
                # Intercept page-by-page to fire on_page hook
                records: list[dict] = []
                params_iter = params or {}
                current_params = paginator.first_params(params_iter)
                current_url = endpoint

                while True:
                    import time as _time
                    t0 = _time.monotonic()
                    if "__link_next_url__" in current_params:
                        current_url = current_params.pop("__link_next_url__")
                        resp_json, resp_headers = self._http.request_sync_full(
                            "GET", current_url, params=None)
                    else:
                        resp_json, resp_headers = self._http.request_sync_full(
                            "GET", current_url, params=current_params)
                    latency = (_time.monotonic() - t0) * 1000

                    page_records = paginator.extract_records(resp_json)
                    records.extend(page_records)
                    cumulative += len(page_records)
                    page_num += 1

                    if show_progress:
                        progress.advance(task, len(page_records))

                    self.hooks.fire("on_page", HookContext(
                        event="on_page",
                        url=f"{self._config.base_url}{current_url}",
                        method="GET",
                        status_code=200,
                        latency_ms=latency,
                        headers=dict(resp_headers),
                        record_count=len(page_records),
                        page_number=page_num,
                        cumulative_records=cumulative,
                    ))

                    if not page_records:
                        break
                    next_params = paginator.next_params(
                        current_params, resp_json, resp_headers)
                    if next_params is None:
                        break
                    current_params = next_params
            else:
                import time as _time
                t0 = _time.monotonic()
                records = self._http.get_all_pages_sync(
                    endpoint, params=params, paginator=paginator,
                    progress=progress if show_progress else None,
                    task_id=task if show_progress else None,
                )
                latency = (_time.monotonic() - t0) * 1000
                self.hooks.fire("on_response", HookContext(
                    event="on_response",
                    url=f"{self._config.base_url}{endpoint}",
                    method="GET",
                    status_code=200,
                    latency_ms=latency,
                    record_count=len(records),
                ))

            progress.update(task, total=len(records), completed=len(records))

        # ── Field ops: flatten → select → exclude → rename → transform ────────
        if flatten:
            records = flatten_records(records)
        records = apply_field_ops(
            records, select=select, exclude=exclude,
            rename=rename, transform_fn=transform_fn,
        )

        # ── Validation ────────────────────────────────────────────────────────
        if model is not None:
            result = validate_records(
                records, model, on_invalid=on_invalid, strict=strict)
            return result

        # ── Cache store ───────────────────────────────────────────────────────
        if use_cache:
            self.cache.set(cache_key, records)

        return records

    def fetch_polars(
        self,
        endpoint: str,
        *,
        params: Optional[dict] = None,
        paginate: bool = False,
        strategy: Optional[PaginationStrategy] = None,
        page_size: Optional[int] = None,
        data_path: Optional[str] = None,
        flatten: bool = True,
        select: Optional[list[str]] = None,
        exclude: Optional[list[str]] = None,
        rename: Optional[dict[str, str]] = None,
        model: Optional[type] = None,
        show_progress: bool = True,
    ) -> "pl.DataFrame":
        """Fetch data and return a Polars DataFrame."""
        records = self.fetch_records(
            endpoint, params=params, paginate=paginate, strategy=strategy,
            page_size=page_size, data_path=data_path, show_progress=show_progress,
            flatten=False,  # we handle flatten below for polars
            select=select, exclude=exclude, rename=rename,
        )
        if isinstance(records, ValidationResult):
            records = records.valid_dicts()
        return records_to_polars(records) if flatten else _pl().DataFrame(records)

    def fetch_pandas(
        self,
        endpoint: str,
        *,
        params: Optional[dict] = None,
        paginate: bool = False,
        strategy: Optional[PaginationStrategy] = None,
        page_size: Optional[int] = None,
        data_path: Optional[str] = None,
        flatten: bool = True,
        select: Optional[list[str]] = None,
        exclude: Optional[list[str]] = None,
        rename: Optional[dict[str, str]] = None,
        model: Optional[type] = None,
        show_progress: bool = True,
    ) -> "pd.DataFrame":
        """Fetch data and return a Pandas DataFrame."""
        records = self.fetch_records(
            endpoint, params=params, paginate=paginate, strategy=strategy,
            page_size=page_size, data_path=data_path, show_progress=show_progress,
            flatten=False,
            select=select, exclude=exclude, rename=rename,
        )
        if isinstance(records, ValidationResult):
            records = records.valid_dicts()
        return records_to_pandas(records) if flatten else _pd().DataFrame(records)

    def post(self, endpoint: str, *, body: Optional[dict] = None, params: Optional[dict] = None) -> Any:
        """POST to an endpoint and return the parsed JSON response."""
        try:
            return self._http.request_sync("POST", endpoint, params=params, json_body=body)
        except Exception as exc:
            self.hooks.fire("on_error", HookContext(
                event="on_error", url=f"{self._config.base_url}{endpoint}",
                method="POST", error_type=type(exc).__name__, error_message=str(exc), error=exc,
            ))
            raise

    def put(self, endpoint: str, *, body: Optional[dict] = None, params: Optional[dict] = None) -> Any:
        """PUT to an endpoint and return the parsed JSON response."""
        try:
            return self._http.request_sync("PUT", endpoint, params=params, json_body=body)
        except Exception as exc:
            self.hooks.fire("on_error", HookContext(
                event="on_error", url=f"{self._config.base_url}{endpoint}",
                method="PUT", error_type=type(exc).__name__, error_message=str(exc), error=exc,
            ))
            raise

    def patch(self, endpoint: str, *, body: Optional[dict] = None, params: Optional[dict] = None) -> Any:
        """PATCH an endpoint (partial update) and return the parsed JSON response."""
        try:
            return self._http.request_sync("PATCH", endpoint, params=params, json_body=body)
        except Exception as exc:
            self.hooks.fire("on_error", HookContext(
                event="on_error", url=f"{self._config.base_url}{endpoint}",
                method="PATCH", error_type=type(exc).__name__, error_message=str(exc), error=exc,
            ))
            raise

    def delete(self, endpoint: str, *, params: Optional[dict] = None) -> Any:
        """DELETE an endpoint and return the parsed JSON response."""
        try:
            return self._http.request_sync("DELETE", endpoint, params=params)
        except Exception as exc:
            self.hooks.fire("on_error", HookContext(
                event="on_error", url=f"{self._config.base_url}{endpoint}",
                method="DELETE", error_type=type(exc).__name__, error_message=str(exc), error=exc,
            ))
            raise

    def head(self, endpoint: str, *, params: Optional[dict] = None) -> Any:
        """
        HEAD an endpoint — returns the raw httpx.Response (no body).
        Use for existence checks, ETag probing, or Content-Length without downloading.
        """
        full_url = (
            endpoint if endpoint.startswith("http")
            else f"{self._config.base_url}{endpoint}"
        )
        with httpx.Client(
            headers=self._http._base_headers,
            timeout=self._config.timeout,
            verify=self._config.verify_ssl,
            follow_redirects=self._config.follow_redirects,
        ) as client:
            req = client.build_request("HEAD", full_url, params=params)
            req = self._http.auth.apply_sync(req)
            return client.send(req)

    def options(self, endpoint: str, *, params: Optional[dict] = None, headers: Optional[dict] = None) -> Any:
        """
        OPTIONS an endpoint — returns the raw httpx.Response.
        Use to discover allowed methods or check CORS preflight config.
        """
        full_url = (
            endpoint if endpoint.startswith("http")
            else f"{self._config.base_url}{endpoint}"
        )
        merged_headers = {**self._http._base_headers, **(headers or {})}
        with httpx.Client(
            headers=merged_headers,
            timeout=self._config.timeout,
            verify=self._config.verify_ssl,
            follow_redirects=self._config.follow_redirects,
        ) as client:
            req = client.build_request("OPTIONS", full_url, params=params)
            req = self._http.auth.apply_sync(req)
            return client.send(req)

    def fetch_to_file(
        self,
        endpoint: str,
        *,
        format: OutputFormat,
        file_path: Union[str, Path],
        params: Optional[dict] = None,
        paginate: bool = False,
        strategy: Optional[PaginationStrategy] = None,
        page_size: Optional[int] = None,
        data_path: Optional[str] = None,
    ) -> Path:
        """Fetch data synchronously and write directly to a file."""
        records = self.fetch_records(
            endpoint, params=params, paginate=paginate, strategy=strategy,
            page_size=page_size, data_path=data_path,
        )
        writer = get_writer(format)
        path = Path(file_path)
        writer.write(records, path)
        console.log(f"[green]✓[/] Wrote {len(records):,} records → {path}")
        return path

    def graphql(
        self,
        endpoint: str,
        query: str,
        *,
        variables: Optional[dict] = None,
        paginate: bool = False,
        connection_path: Optional[str] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Any:
        """Execute a GraphQL query synchronously."""
        gql = GraphQLClient(self._config, endpoint)
        if paginate:
            return gql.paginate_sync(
                query, variables=variables,
                connection_path=connection_path, page_size=page_size,
            )
        return gql.query_sync(query, variables=variables)

    def inspect(
        self,
        endpoint: str,
        *,
        params: Optional[dict] = None,
        dry_run: bool = False,
    ) -> "InspectorResult":
        """Probe an endpoint and return a rich InspectorResult."""
        inspector = ApiInspector(self._config)
        result = inspector.inspect_sync(
            endpoint, params=params, dry_run=dry_run)
        print_inspector_result(result)
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Async Methods
    # ─────────────────────────────────────────────────────────────────────────

    async def afetch_records(
        self,
        endpoint: str,
        *,
        params: Optional[dict] = None,
        paginate: bool = False,
        strategy: Optional[PaginationStrategy] = None,
        page_size: Optional[int] = None,
        data_path: Optional[str] = None,
        show_progress: bool = True,
        cache: Optional[bool] = None,
        flatten: bool = False,
        select: Optional[list[str]] = None,
        exclude: Optional[list[str]] = None,
        rename: Optional[dict[str, str]] = None,
        transform_fn: Optional[Callable[[dict], dict]] = None,
        model: Optional[type] = None,
        on_invalid: Literal["collect", "skip", "raise"] = "collect",
        strict: bool = False,
    ) -> Any:
        """Async version of fetch_records — same params, same post-processing."""
        # ── Cache check ───────────────────────────────────────────────────────
        use_cache = self.cache.enabled if cache is None else cache
        cache_key = self.cache.make_key(
            "GET", f"{self._config.base_url}{endpoint}", params)
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        paginator = self._make_paginator(
            paginate, strategy, page_size, data_path)
        with self._make_progress() as progress:
            task = progress.add_task(f"Fetching {endpoint} …", total=None)
            records = await self._http.get_all_pages_async(
                endpoint, params=params, paginator=paginator,
                progress=progress if show_progress else None,
                task_id=task if show_progress else None,
            )
            progress.update(task, total=len(records), completed=len(records))

        # ── Field ops ─────────────────────────────────────────────────────────
        if flatten:
            records = flatten_records(records)
        records = apply_field_ops(
            records, select=select, exclude=exclude,
            rename=rename, transform_fn=transform_fn,
        )

        # ── Validation ────────────────────────────────────────────────────────
        if model is not None:
            return validate_records(records, model, on_invalid=on_invalid, strict=strict)

        # ── Cache store ───────────────────────────────────────────────────────
        if use_cache:
            self.cache.set(cache_key, records)

        return records

    async def afetch_polars(
        self,
        endpoint: str,
        *,
        params: Optional[dict] = None,
        paginate: bool = False,
        strategy: Optional[PaginationStrategy] = None,
        page_size: Optional[int] = None,
        data_path: Optional[str] = None,
        flatten: bool = True,
        show_progress: bool = True,
    ) -> "pl.DataFrame":
        """Async fetch → Polars DataFrame."""
        records = await self.afetch_records(
            endpoint, params=params, paginate=paginate, strategy=strategy,
            page_size=page_size, data_path=data_path, show_progress=show_progress,
        )
        return records_to_polars(records) if flatten else pl.DataFrame(records)

    async def afetch_pandas(
        self,
        endpoint: str,
        *,
        params: Optional[dict] = None,
        paginate: bool = False,
        strategy: Optional[PaginationStrategy] = None,
        page_size: Optional[int] = None,
        data_path: Optional[str] = None,
        flatten: bool = True,
        show_progress: bool = True,
    ) -> "pd.DataFrame":
        """Async fetch → Pandas DataFrame."""
        records = await self.afetch_records(
            endpoint, params=params, paginate=paginate, strategy=strategy,
            page_size=page_size, data_path=data_path, show_progress=show_progress,
        )
        return records_to_pandas(records) if flatten else pd.DataFrame(records)

    async def astream(
        self,
        endpoint: str,
        *,
        params: Optional[dict] = None,
        paginate: bool = True,
        strategy: Optional[PaginationStrategy] = None,
        page_size: Optional[int] = None,
        data_path: Optional[str] = None,
    ) -> AsyncIterator[dict]:
        """Async generator — yields individual records as they are fetched."""
        paginator = self._make_paginator(
            paginate, strategy, page_size, data_path)
        async for record in self._http.astream(endpoint, params=params, paginator=paginator):
            yield record

    async def afetch_to_file(
        self,
        endpoint: str,
        *,
        format: OutputFormat,
        file_path: Union[str, Path],
        params: Optional[dict] = None,
        paginate: bool = False,
        strategy: Optional[PaginationStrategy] = None,
        page_size: Optional[int] = None,
        data_path: Optional[str] = None,
    ) -> Path:
        """Async fetch → write to file."""
        records = await self.afetch_records(
            endpoint, params=params, paginate=paginate, strategy=strategy,
            page_size=page_size, data_path=data_path,
        )
        writer = get_writer(format)
        path = Path(file_path)
        writer.write(records, path)
        console.log(f"[green]✓[/] Wrote {len(records):,} records → {path}")
        return path

    async def agraphql(
        self,
        endpoint: str,
        query: str,
        *,
        variables: Optional[dict] = None,
        paginate: bool = False,
        connection_path: Optional[str] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Any:
        """Async GraphQL query."""
        gql = GraphQLClient(self._config, endpoint)
        if paginate:
            return await gql.paginate_async(
                query, variables=variables,
                connection_path=connection_path, page_size=page_size,
            )
        return await gql.query_async(query, variables=variables)

    async def ainspect(
        self,
        endpoint: str,
        *,
        params: Optional[dict] = None,
        dry_run: bool = False,
    ) -> "InspectorResult":
        """Async variant of inspect()."""
        inspector = ApiInspector(self._config)
        result = await inspector.inspect_async(endpoint, params=params, dry_run=dry_run)
        print_inspector_result(result)
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Feature 7: Multi-endpoint Fan-out
    # ─────────────────────────────────────────────────────────────────────────

    def fetch_many(
        self,
        endpoints: Union[list, dict],
        *,
        paginate: bool = False,
        on_error: Literal["raise", "skip", "return_empty"] = "raise",
        show_progress: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Fetch multiple endpoints concurrently and return a dict of results.

        Args:
            endpoints: A list of endpoint paths, a dict of {label: endpoint},
                       or a dict of {label: (endpoint, params)} or
                       {label: (endpoint, params, extra_kwargs)}.
            paginate:  Paginate all endpoints.
            on_error:  "raise" — propagate exceptions (default).
                       "skip"  — omit failed endpoints from result.
                       "return_empty" — include failed endpoints as empty lists.
            **kwargs:  Forwarded to each afetch_records() call (select, exclude, etc.).

        Returns:
            dict mapping label/path → list[dict]

        Example:
            results = client.fetch_many(["/posts", "/users", "/todos"])
            results = client.fetch_many({"posts": "/posts", "authors": "/users"})
            results = client.fetch_many({"recent": ("/posts", {"_limit": 5})})
        """
        # Normalise input → list of (label, endpoint, params, extra)
        tasks: list[tuple[str, str, dict, dict]] = []
        if isinstance(endpoints, list):
            for ep in endpoints:
                tasks.append((ep, ep, {}, {}))
        elif isinstance(endpoints, dict):
            for label, value in endpoints.items():
                if isinstance(value, str):
                    tasks.append((label, value, {}, {}))
                elif isinstance(value, tuple):
                    ep = value[0]
                    ep_params = value[1] if len(value) > 1 else {}
                    ep_extra = value[2] if len(value) > 2 else {}
                    tasks.append((label, ep, ep_params or {}, ep_extra))

        async def _run_all() -> dict[str, Any]:
            async def _one(label: str, ep: str, ep_params: dict, ep_extra: dict) -> tuple[str, Any]:
                merged_params = {**ep_params}
                merged_kwargs = {**kwargs, **ep_extra}
                try:
                    records = await self.afetch_records(
                        ep, params=merged_params or None, paginate=paginate,
                        show_progress=show_progress, **merged_kwargs,
                    )
                    return label, records
                except Exception as exc:
                    if on_error == "raise":
                        raise
                    if on_error == "return_empty":
                        logger.warning(
                            "fetch_many: %s failed (%s), returning []", label, exc)
                        return label, []
                    # on_error == "skip"
                    logger.warning(
                        "fetch_many: %s failed (%s), skipping", label, exc)
                    return label, None

            coros = [_one(label, ep, params_, extra)
                     for label, ep, params_, extra in tasks]
            pairs = await asyncio.gather(*coros, return_exceptions=False)
            return {label: records for label, records in pairs if records is not None}

        return asyncio.run(_run_all())

    def fetch_many_polars(
        self,
        endpoints: Union[list, dict],
        *,
        paginate: bool = False,
        flatten: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Fetch multiple endpoints concurrently → dict of Polars DataFrames.

        Example:
            dfs = client.fetch_many_polars({"users": "/users", "posts": "/posts"})
            joined = dfs["posts"].join(dfs["users"].rename({"id": "userId"}), on="userId")
        """
        results = self.fetch_many(endpoints, paginate=paginate, **kwargs)
        out = {}
        for label, records in results.items():
            out[label] = records_to_polars(
                records) if flatten else _pl().DataFrame(records)
        return out

    def fetch_many_pandas(
        self,
        endpoints: Union[list, dict],
        *,
        paginate: bool = False,
        flatten: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Fetch multiple endpoints concurrently → dict of Pandas DataFrames.

        Example:
            dfs = client.fetch_many_pandas({"users": "/users", "todos": "/todos"})
        """
        results = self.fetch_many(endpoints, paginate=paginate, **kwargs)
        out = {}
        for label, records in results.items():
            out[label] = records_to_pandas(
                records) if flatten else _pd().DataFrame(records)
        return out

    def fetch_many_to_files(
        self,
        endpoints: Union[list, dict],
        *,
        format: OutputFormat,
        output_dir: Union[str, Path],
        paginate: bool = False,
        **kwargs: Any,
    ) -> dict[str, Path]:
        """
        Fetch multiple endpoints concurrently and write each to a separate file.

        Returns:
            dict mapping label → Path of written file.

        Example:
            paths = client.fetch_many_to_files(
                {"users": "/users", "posts": "/posts"},
                format="parquet", output_dir="/tmp/data",
            )
        """
        results = self.fetch_many(endpoints, paginate=paginate, **kwargs)
        writer = get_writer(format)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = {}
        for label, records in results.items():
            safe_label = label.lstrip("/").replace("/", "_")
            file_ext = format if format != "ndjson" else "ndjson"
            out_path = output_dir / f"{safe_label}.{file_ext}"
            writer.write(records, out_path)
            console.log(
                f"[green]✓[/] {label} → {out_path.name} ({len(records):,} records)")
            paths[label] = out_path
        return paths

    # ─────────────────────────────────────────────────────────────────────────
    # Feature 8: Validation helper (public, for use outside fetch_records)
    # ─────────────────────────────────────────────────────────────────────────

    def _validate_records(
        self,
        records: list[dict],
        model: type,
        *,
        on_invalid: Literal["collect", "skip", "raise"] = "collect",
        strict: bool = False,
    ) -> Any:
        """
        Validate a list of raw dicts against a Pydantic model.
        Exposed publicly so it can be called on pre-fetched records.

        Example:
            records = client.fetch_records("/users")
            result = client._validate_records(records, UserModel)
            print(result.valid_count, result.error_count)
        """
        return validate_records(records, model, on_invalid=on_invalid, strict=strict)

    # ─────────────────────────────────────────────────────────────────────────
    # Introspection
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def config(self) -> ApiConfig:
        """Return the underlying ApiConfig."""
        return self._config

    def __repr__(self) -> str:
        return (
            f"Apikit(base_url={self._config.base_url!r}, "
            f"auth={self._config.auth.type!r})"
        )

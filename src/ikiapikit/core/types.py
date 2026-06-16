from typing import Literal

OutputFormat = Literal["parquet", "ndjson",
                       "jsonl", "csv", "arrow", "json", "duckdb"]
AuthType = Literal["bearer", "apikey", "oauth2", "basic", "none"]
PaginationStrategy = Literal["offset", "page", "cursor", "link", "none"]
Backend = Literal["polars", "pandas"]

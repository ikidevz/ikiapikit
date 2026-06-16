"""
tests/conftest.py  —  Shared fixtures for the full apikit test suite.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from ikiapikit import (
    Apikit,
    ApiConfig,
    AuthConfig,
    RetryConfig,
    PaginationConfig,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://api.example.com"
BEARER_TOKEN = "test-bearer-token"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_config(
    *,
    auth_type: str = "bearer",
    token: str = BEARER_TOKEN,
    strategy: str = "none",
    page_size: int = 10,
    base_url: str = BASE_URL,
) -> ApiConfig:
    return ApiConfig(
        base_url=base_url,
        auth=AuthConfig(
            type=auth_type,
            token=token if auth_type == "bearer" else None,
        ),
        pagination=PaginationConfig(strategy=strategy, page_size=page_size),
        retry=RetryConfig(max_attempts=2, min_wait=0.0, max_wait=0.1),
    )


def sample_records(n: int = 5) -> list[dict]:
    return [
        {"id": i, "name": f"item_{i}", "meta": {"score": i * 10}}
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config() -> ApiConfig:
    return make_config()


@pytest.fixture
def client(config: ApiConfig) -> Apikit:
    client = Apikit.from_config(config)

    # sanity check (prevents silent fixture corruption)
    assert hasattr(
        client, "fetch_records"), "Apikit instance not created correctly"

    return client


@pytest.fixture
def records() -> list[dict]:
    return sample_records(5)


@pytest.fixture
def nested_record() -> dict:
    return {
        "id": 1,
        "user": {
            "name": "Alice",
            "address": {"city": "NYC", "zip": "10001"},
        },
        "metrics": {"clicks": 420, "conversions": 12},
        "tags": ["python", "data"],
    }


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path

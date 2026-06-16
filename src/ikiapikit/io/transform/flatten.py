import orjson
from typing import Any


def flatten_dict(d: dict, parent_key: str = "", sep: str = "_") -> dict:
    """
    Recursively flatten a nested dict.

    Example:
        {"user": {"id": 1, "name": "Alice"}} →
        {"user__id": 1, "user__name": "Alice"}
    """
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep).items())
        elif isinstance(v, list):
            items.append((new_key, orjson.dumps(v).decode()))
        else:
            items.append((new_key, v))
    return dict(items)


def flatten_records(records: list, sep: str = "_") -> list[dict]:
    """Flatten a list of (possibly nested) record dicts."""
    result = []
    for r in records:
        if isinstance(r, dict):
            result.append(flatten_dict(r, sep=sep))
        else:
            result.append({"value": r})
    return result

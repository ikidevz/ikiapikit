from typing import Any, Callable, Optional
from ...http.pagination.base import get_nested


def apply_select(records: list[dict], select: list[str]) -> list[dict]:
    """
    Keep only the named fields in each record.
    Dot-paths (e.g. "address.city") are resolved against the raw record
    and promoted to a top-level key using the dot-path as the key name.

    Example:
        select=["id", "address.city"]
        {"id": 1, "address": {"city": "Davao"}} → {"id": 1, "address.city": "Davao"}
    """
    simple = [f for f in select if "." not in f]
    dotted = [f for f in select if "." in f]

    result = []
    for rec in records:
        out: dict[str, Any] = {k: rec[k] for k in simple if k in rec}
        for path in dotted:
            val = get_nested(rec, path)
            if val is not None:
                out[path] = val
        result.append(out)
    return result


def apply_exclude(records: list[dict], exclude: list[str]) -> list[dict]:
    """Drop the named fields from every record."""
    exclude_set = set(exclude)
    return [{k: v for k, v in rec.items() if k not in exclude_set} for rec in records]


def apply_rename(records: list[dict], rename: dict[str, str]) -> list[dict]:
    """Rename fields according to the mapping {old_name: new_name}."""
    result = []
    for rec in records:
        out = {}
        for k, v in rec.items():
            out[rename.get(k, k)] = v
        result.append(out)
    return result


def apply_transform(records: list[dict], transform_fn: Callable[[dict], dict]) -> list[dict]:
    """Apply an arbitrary per-record transformation function."""
    return [transform_fn(r) for r in records]


def apply_field_ops(
    records: list[dict],
    *,
    select: Optional[list[str]] = None,
    exclude: Optional[list[str]] = None,
    rename: Optional[dict[str, str]] = None,
    transform_fn: Optional[Callable[[dict], dict]] = None,
) -> list[dict]:
    """Apply select → exclude → rename → transform in order."""
    if select:
        records = apply_select(records, select)
    if exclude:
        records = apply_exclude(records, exclude)
    if rename:
        records = apply_rename(records, rename)
    if transform_fn:
        records = apply_transform(records, transform_fn)
    return records

from typing import Any, Literal
from rich.console import Console
from rich.table import Table
from ..core.exceptions import RecordValidationError, ApikitError

console = Console(stderr=True)


class ValidationResult:
    """
    Container returned by fetch_records(model=..., on_invalid='collect').

    Attributes:
        valid   — list of validated model instances
        errors  — list of dicts with keys: index, field, message, record
        total   — total records processed
    """

    def __init__(self, valid: list, errors: list[dict], total: int):
        self.valid = valid
        self.errors = errors
        self.total = total

    @property
    def valid_count(self) -> int:
        return len(self.valid)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    def valid_dicts(self) -> list[dict]:
        """Return valid records as plain dicts (model_dump)."""
        return [v.model_dump() if hasattr(v, "model_dump") else dict(v) for v in self.valid]

    def summary(self) -> None:
        """Print a Rich-formatted validation summary."""
        table = Table(title="Validation Summary", show_header=True)
        table.add_column("Metric", style="bold")
        table.add_column("Count", justify="right")
        table.add_row("Total records", str(self.total))
        table.add_row("[green]Valid[/]", str(self.valid_count))
        table.add_row("[red]Invalid[/]", str(self.error_count))
        if self.total:
            pct = self.valid_count / self.total * 100
            table.add_row("Pass rate", f"{pct:.1f}%")
        console.print(table)

        if self.errors:
            err_table = Table(title="Validation Errors", show_header=True)
            err_table.add_column("Index", justify="right")
            err_table.add_column("Field")
            err_table.add_column("Message")
            for err in self.errors[:20]:
                err_table.add_row(
                    str(err.get("index", "?")),
                    err.get("field", "?"),
                    err.get("message", "")[:80],
                )
            if len(self.errors) > 20:
                err_table.add_row(
                    "...", "...", f"({len(self.errors)-20} more errors)")
            console.print(err_table)


def validate_records(
    records: list[dict],
    model: type,
    *,
    on_invalid: Literal["collect", "skip", "raise"] = "collect",
    strict: bool = False,
) -> Any:
    """
    Validate a list of raw dicts against a Pydantic model.

    Args:
        records:    Raw dicts from the API.
        model:      A Pydantic BaseModel subclass.
        on_invalid: "collect" → return ValidationResult with both valid + errors.
                    "skip"    → return plain list of valid model instances only.
                    "raise"   → raise RecordValidationError on first failure.
        strict:     If True, disable Pydantic coercion (exact types required).

    Returns:
        ValidationResult (on_invalid='collect') or list (on_invalid='skip'/'raise').
    """
    try:
        from pydantic import ValidationError as PydanticValidationError
    except ImportError:
        raise ApikitError(
            "Pydantic is required for record validation: pip install pydantic")

    valid: list = []
    errors: list[dict] = []

    for i, record in enumerate(records):
        try:
            if strict:
                instance = model.model_validate(record, strict=True)
            else:
                instance = model.model_validate(record)
            valid.append(instance)
        except Exception as exc:
            # Extract Pydantic error details when available
            error_details: list[dict] = []
            if hasattr(exc, "errors"):
                for e in exc.errors():
                    error_details.append({
                        "index": i,
                        "field": ".".join(str(loc) for loc in e.get("loc", [])),
                        "message": e.get("msg", str(exc)),
                        "record": record,
                    })
            else:
                error_details.append({
                    "index": i,
                    "field": "?",
                    "message": str(exc),
                    "record": record,
                })

            if on_invalid == "raise":
                raise RecordValidationError(error_details) from exc
            errors.extend(error_details)

    if on_invalid == "skip":
        return valid
    return ValidationResult(valid=valid, errors=errors, total=len(records))

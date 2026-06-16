from rich.console import Console
from rich.table import Table

from .result import InspectorResult
console = Console(stderr=True)


def print_inspector_result(result: InspectorResult) -> None:
    """Render an InspectorResult to the Rich console."""
    if result.dry_run:
        console.print(
            f"\n[bold yellow]DRY RUN[/] — would GET [cyan]{result.url}[/]")
        return

    console.print()
    console.rule(f"[bold cyan]Inspector — {result.url}[/]")

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")

    table.add_row("Status", f"[green]{result.status_code}[/]" if result.status_code < 400
                  else f"[red]{result.status_code}[/]")
    table.add_row("Latency", f"{result.latency_ms:.1f} ms")
    table.add_row(
        "Response", f"{result.response_size_bytes:,} bytes — {result.content_type}")
    table.add_row("Records", str(result.record_count))
    table.add_row(
        "Pagination", f"[cyan]{result.detected_pagination or 'none detected'}[/]")

    rl = result.rate_limit_state.headroom
    if rl.get("remaining") is not None:
        used = rl.get("used_pct")
        pct_str = f" ({used}% used)" if used is not None else ""
        table.add_row(
            "Rate Limit", f"{rl['remaining']} remaining of {rl.get('limit', '?')}{pct_str}")

    console.print(table)

    schema = result.schema_sample()
    if schema:
        console.print()
        console.print("[bold]Schema sample:[/]")
        s_table = Table(show_lines=True)
        s_table.add_column("Field", style="cyan")
        s_table.add_column("Type", style="yellow")
        for field, dtype in list(schema.items())[:15]:
            s_table.add_row(field, dtype)
        if len(schema) > 15:
            s_table.add_row(f"… {len(schema)-15} more fields", "")
        console.print(s_table)

    console.print()
    console.print("[bold]Suggested ApiConfig:[/]")
    console.print(f"[dim]{result.suggested_config()}[/]")
    console.rule()

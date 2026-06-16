
from pathlib import Path
from rich.console import Console
from typing import Optional

console = Console(stderr=True)


class DryRunResult:
    """
    What a real fetch or operation would have done, without doing it.
    Returned by Apikit methods when dry_run=True.
    """

    def __init__(
        self,
        method: str,
        url: str,
        params: Optional[dict],
        headers: dict,
        auth_type: str,
        pagination_strategy: str,
        page_size: int,
        output_format: Optional[str] = None,
        output_path: Optional[Path] = None,
        body: Optional[dict] = None,
    ):
        self.method = method
        self.url = url
        self.params = params or {}
        self.headers = headers
        self.auth_type = auth_type
        self.pagination_strategy = pagination_strategy
        self.page_size = page_size
        self.output_format = output_format
        self.output_path = output_path
        self.body = body

    def display(self) -> None:
        """Print a Rich-formatted preview of what would be sent."""
        console.print()
        console.print(
            "[bold yellow]── DRY RUN ──────────────────────────────────────────[/]")
        console.print(f"  [bold]Method[/]        {self.method}")
        console.print(f"  [bold]URL[/]           [cyan]{self.url}[/]")
        if self.params:
            console.print(f"  [bold]Params[/]        {self.params}")
        if self.body:
            console.print(f"  [bold]Body[/]          {self.body}")
        console.print(f"  [bold]Auth[/]          {self.auth_type}")
        safe_headers = {
            k: ("***" if k.lower() in ("authorization", "x-api-key") else v)
            for k, v in self.headers.items()
        }
        console.print(f"  [bold]Headers[/]       {safe_headers}")
        console.print(
            f"  [bold]Pagination[/]    strategy={self.pagination_strategy}, page_size={self.page_size}")
        console.print(
            "[bold yellow]─────────────────────────────────────────────────────[/]")

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "url": self.url,
            "params": self.params,
            "auth_type": self.auth_type,
            "pagination_strategy": self.pagination_strategy,
            "page_size": self.page_size,
            "output_format": self.output_format,
            "output_path": self.output_path.as_posix() if self.output_path else None,
        }

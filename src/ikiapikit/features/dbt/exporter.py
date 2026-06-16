from rich.console import Console
from typing import Any, Union, Optional
from pathlib import Path

from ...facade import Apikit

from ...io.transform.flatten import flatten_records
from ...io.writers.factory import get_writer

console = Console(stderr=True)


class DbtExporter:
    """
    Generates dbt-ready artifacts from API data:
      • Seed CSV files  — drop-in dbt seed sources
      • sources.yml    — dbt source definitions with column stubs
      • schema.yml     — model schema with column descriptions

    Usage:
        exporter = DbtExporter(output_dir="dbt_seeds/")
        exporter.export(records=records, name="stripe_customers",
                        database="raw", schema="stripe")
    """

    def __init__(self, output_dir: Union[str, Path] = "dbt_seeds", dry_run: bool = False):
        self.output_dir = Path(output_dir)
        self.dry_run = dry_run

    def export(
        self,
        records: list[dict],
        name: str,
        *,
        database: str = "raw",
        schema: str = "public",
        description: str = "",
        tags: Optional[list[str]] = None,
        meta: Optional[dict] = None,
        flatten: bool = True,
    ) -> dict[str, Path]:
        """Export records as dbt seed CSV + sources.yml + schema.yml."""
        flat = flatten_records(records) if flatten else records
        columns = self._infer_columns(flat)
        paths: dict[str, Path] = {}

        if self.dry_run:
            self._print_dry_run(name, database, schema,
                                description, columns, tags)
            return paths

        self.output_dir.mkdir(parents=True, exist_ok=True)
        paths["seed"] = self._write_seed(flat, name)
        paths["sources"] = self._write_sources(
            name, database, schema, description, columns, tags, meta)
        paths["schema"] = self._write_schema(
            name, description, columns, tags, meta)

        console.print(f"[green]✓[/] dbt export complete for [bold]{name}[/]:")
        for kind, path in paths.items():
            console.print(f"  {kind:10s} → [cyan]{path}[/]")

        return paths

    def export_from_client(
        self,
        client: "Apikit",
        endpoint: str,
        name: str,
        *,
        paginate: bool = True,
        page_size: int = 500,
        data_path: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Path]:
        """Fetch from API and export in one call."""
        records = client.fetch_records(
            endpoint, paginate=paginate, page_size=page_size,
            data_path=data_path, show_progress=True,
        )
        return self.export(records, name, **kwargs)

    def _infer_columns(self, records: list[dict]) -> list[dict]:
        if not records:
            return []
        sample = records[0]
        return [
            {"name": key, "dtype": type(value).__name__,
             "description": f"{key.replace('__', ' › ')} field"}
            for key, value in sample.items()
        ]

    def _write_seed(self, records: list[dict], name: str) -> Path:
        seeds_dir = self.output_dir / "seeds"
        seeds_dir.mkdir(parents=True, exist_ok=True)
        path = seeds_dir / f"{name}.csv"
        get_writer("csv").write(records, path)
        return path

    def _write_sources(self, name, database, schema, description, columns, tags, meta) -> Path:
        models_dir = self.output_dir / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        path = models_dir / "sources.yml"
        content = self._render_sources_yaml(
            name, database, schema, description, columns, tags, meta)
        existing = path.read_text() if path.exists() else ""
        if f"name: {name}" not in existing:
            with open(path, "a") as f:
                if not existing:
                    f.write("version: 2\n\nsources:\n")
                f.write(content)
        return path

    def _write_schema(self, name, description, columns, tags, meta) -> Path:
        models_dir = self.output_dir / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        path = models_dir / f"{name}.yml"
        path.write_text(self._render_schema_yaml(
            name, description, columns, tags, meta))
        return path

    def _render_sources_yaml(self, name, database, schema, description, columns, tags, meta) -> str:
        lines = [
            f"  - name: {name}", f"    database: {database}", f"    schema: {schema}",
        ]
        if description:
            lines.append(f'    description: "{description}"')
        if tags:
            lines.append(f"    tags: {tags}")
        if meta:
            lines.append(f"    meta: {meta}")
        lines.extend(["    tables:", f"      - name: {name}"])
        if columns:
            lines.append("        columns:")
            for col in columns:
                lines.append(f"          - name: {col['name']}")
                lines.append(
                    f"            description: \"{col['description']}\"")
        lines.append("")
        return "\n".join(lines)

    def _render_schema_yaml(self, name, description, columns, tags, meta) -> str:
        lines = ["version: 2", "", "models:", f"  - name: {name}"]
        if description:
            lines.append(f'    description: "{description}"')
        if tags:
            lines.append(f"    tags: {tags}")
        if meta:
            lines.append(f"    meta: {meta}")
        if columns:
            lines.append("    columns:")
            for col in columns:
                lines.append(f"      - name: {col['name']}")
                lines.append(f"        description: \"{col['description']}\"")
                lines.append(f"        data_type: {col['dtype']}")
        lines.append("")
        return "\n".join(lines)

    def _print_dry_run(self, name, database, schema, description, columns, tags) -> None:
        console.print(
            f"\n[bold yellow]DRY RUN[/] — dbt export for [bold cyan]{name}[/]")
        console.print(f"  Would write to: [cyan]{self.output_dir}[/]")
        console.print(f"  database={database!r}, schema={schema!r}")

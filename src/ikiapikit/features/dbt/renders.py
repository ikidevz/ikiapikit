

def render_sources_yaml(self, name, database, schema, description, columns, tags, meta) -> str:
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


def render_schema_yaml(self, name, description, columns, tags, meta) -> str:
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

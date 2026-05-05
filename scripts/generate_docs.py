# /// script
# requires-python = ">=3.11"
# ///
"""Generate MCP server documentation by introspecting the running server.

Spawns sop-mcp as a subprocess, connects via FastMCP Client, and renders
tool schemas + resource list as markdown.

Usage:
    uv run scripts/generate_docs.py > docs/mcp-reference.md
"""

from __future__ import annotations

import asyncio
import json
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def main() -> None:
    transport = StdioTransport(
        command=sys.executable,
        args=["-c", "from src.sop_mcp.server import run; run()"],
    )

    async with Client(transport) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()

    # Render markdown
    lines: list[str] = []
    lines.append("# SOP-MCP Server Reference")
    lines.append("")
    lines.append("Auto-generated from the running server's tool and resource schemas.")
    lines.append("")

    # Tools
    lines.append("## Tools")
    lines.append("")
    for tool in sorted(tools, key=lambda t: t.name):
        lines.append(f"### `{tool.name}`")
        lines.append("")
        if tool.description:
            lines.append(tool.description)
            lines.append("")

        schema = tool.inputSchema
        props = schema.get("properties", {})
        required = set(schema.get("required", []))

        if props:
            lines.append("**Parameters:**")
            lines.append("")
            lines.append("| Name | Type | Required | Description |")
            lines.append("|------|------|----------|-------------|")
            for name, prop in props.items():
                ptype = prop.get("type", "any")
                req = "✓" if name in required else ""
                desc = prop.get("description", "")
                lines.append(f"| `{name}` | {ptype} | {req} | {desc} |")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Resources
    lines.append("## Resources")
    lines.append("")
    lines.append("| URI | Name | MIME Type | Description |")
    lines.append("|-----|------|----------|-------------|")
    for r in sorted(resources, key=lambda r: str(r.uri)):
        uri = str(r.uri)
        desc = (r.description or "")[:80]
        lines.append(f"| `{uri}` | {r.name} | {r.mimeType} | {desc} |")
    lines.append("")

    print("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())

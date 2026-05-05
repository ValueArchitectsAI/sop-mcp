"""Generate MCP server documentation by introspecting the running server.

Spawns sop-mcp as a subprocess, connects via FastMCP Client, and generates:
- docs/mcp-reference.md  — full tool + resource reference
- llms.txt               — LLM-friendly server description

Usage:
    uv run python scripts/generate_docs.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

PROJECT_ROOT = Path(__file__).parent.parent


async def _introspect():
    """Connect to the server and return tools + resources."""
    transport = StdioTransport(
        command=sys.executable,
        args=["-c", "from src.sop_mcp.server import run; run()"],
    )
    async with Client(transport) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
    return tools, resources


def _generate_reference(tools, resources) -> str:
    """Generate the full MCP reference markdown."""
    lines: list[str] = []
    lines.append("# SOP-MCP Server Reference")
    lines.append("")
    lines.append("> Auto-generated from the running server. Do not edit manually.")
    lines.append("> Regenerate with: `uv run python scripts/generate_docs.py`")
    lines.append("")

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

    lines.append("## Resources")
    lines.append("")
    lines.append("| URI | Description |")
    lines.append("|-----|-------------|")
    for r in sorted(resources, key=lambda r: str(r.uri)):
        uri = str(r.uri)
        desc = (r.description or "")[:100]
        lines.append(f"| `{uri}` | {desc} |")
    lines.append("")

    return "\n".join(lines)


_CONFIG_SNIPPET = """## Configuration

```json
{
  "mcpServers": {
    "sop-mcp": {
      "command": "uvx",
      "args": ["sop-mcp"],
      "env": { "SOP_STORAGE_DIR": "/path/to/sops" }
    }
  }
}
```
"""

_USAGE_SNIPPET = """## Usage

1. Call `list_resources` to discover available SOPs
2. Call `run_sop(sop_name="...")` to start executing an SOP
3. Execute each step, then call `run_sop(current_step=N, step_output="...")` to advance
4. Use `publish_sop` to create new SOPs
5. Use `submit_sop_feedback` to record improvement suggestions
"""


def _generate_llms_txt(tools, resources) -> str:
    """Generate llms.txt — concise server description for AI discovery."""
    lines: list[str] = [
        "# SOP-MCP",
        "",
        "An MCP server that guides AI agents through Standard Operating Procedures (SOPs) one step at a time.",
        "",
        "## Tools",
        "",
    ]
    for tool in sorted(tools, key=lambda t: t.name):
        if tool.name in ("list_resources", "read_resource"):
            continue  # skip auto-generated resource tools
        desc = (tool.description or "").split("\n")[0]
        lines.append(f"- **{tool.name}**: {desc}")

    lines.extend(["", "## Resources", ""])
    for r in sorted(resources, key=lambda r: str(r.uri)):
        if "/" in str(r.uri).replace("sop://", ""):
            continue  # skip attachment sub-resources
        lines.append(f"- `{r.uri}`: {r.description or r.name}")

    lines.append("")
    lines.append(_USAGE_SNIPPET)
    lines.append(_CONFIG_SNIPPET)

    return "\n".join(lines)


def main():
    tools, resources = asyncio.run(_introspect())

    # Write docs/mcp-reference.md
    ref_path = PROJECT_ROOT / "docs" / "mcp-reference.md"
    ref_path.parent.mkdir(parents=True, exist_ok=True)
    ref_path.write_text(_generate_reference(tools, resources))
    print(f"✓ {ref_path.relative_to(PROJECT_ROOT)}")

    # Write llms.txt
    llms_path = PROJECT_ROOT / "llms.txt"
    llms_path.write_text(_generate_llms_txt(tools, resources))
    print(f"✓ {llms_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()

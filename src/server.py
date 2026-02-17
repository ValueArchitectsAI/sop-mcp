"""SOP MCP Server - Main business logic.

This module contains the MCP server with dynamically registered SOP tools
and FileSystemProvider-discovered static tools (publish_sop, submit_sop_feedback).
"""

import logging
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.providers import FileSystemProvider
from fastmcp.server.transforms import ResourcesAsTools

from src.mcp.resources.sop_content import register_sop_resources
from src.mcp.tools.publish_sop import EPHEMERAL_WARNING, publish_sop  # noqa: F401
from src.mcp.tools.run_sop import _create_sop_handler, _merge_outputs  # noqa: F401
from src.mcp.tools.submit_sop_feedback import submit_sop_feedback  # noqa: F401
from src.utils import SOP, get_storage_backend

logger = logging.getLogger(__name__)

# Initialize storage backend at module level (Requirement 6.1)
backend = get_storage_backend()

# Initialize FastMCP server with FileSystemProvider for static tools
mcp = FastMCP(
    "SOP MCP Server",
    providers=[FileSystemProvider(Path(__file__).parent / "mcp")],
)


def register_sop_tools() -> None:
    """Register one run_ tool per SOP folder with optional version parameter."""
    for sop_name in backend.list_sops():
        try:
            content = backend.read_sop(sop_name)
            sop = SOP.from_content(content)
        except (FileNotFoundError, ValueError):
            continue

        versions = backend.list_versions(sop_name)
        version_info = ", ".join(f"v{v}" for v in versions)

        prereq_info = ""
        if sop.mcp_server_prerequisites:
            servers = ", ".join(sop.mcp_server_prerequisites)
            prereq_info = f"\n\nRequired MCP Servers: {servers}. Ensure these are available before running this SOP."

        mcp.tool(
            name=f"run_{sop.tool_name}",
            description=(
                f"{sop.title}. {sop.truncated_overview}\n\n"
                f"Available versions: {version_info}. Defaults to latest (v{sop.version}).\n\n"
                "The 'version' parameter is optional and defaults to the latest version.\n\n"
                "IMPORTANT: When you call this tool, you MUST execute ALL actions described in the "
                "returned step_content. Do NOT just read or summarize the step — perform the actions "
                "using your available tools. After completing a step, call this tool again with the "
                "current_step value to advance to the next step."
                f"{prereq_info}"
            ),
        )(_create_sop_handler(sop, versions))


# Register dynamic SOP tools and concrete resources at module load time
register_sop_tools()
register_sop_resources(mcp)

# Expose resources as tools for clients that lack resource protocol support
mcp.add_transform(ResourcesAsTools(mcp))


def run():
    """Entry point for uvx / uv run sop-mcp."""
    mcp.run(transport="stdio")

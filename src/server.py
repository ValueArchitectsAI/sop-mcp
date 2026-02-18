"""SOP MCP Server - Main business logic.

This module contains the MCP server with FileSystemProvider-discovered
tools (run_sop, publish_sop, submit_sop_feedback) and dynamically
registered SOP resources.
"""

import logging
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.providers import FileSystemProvider
from fastmcp.server.transforms import ResourcesAsTools

from src.mcp.resources.sop_content import register_sop_resources
from src.mcp.tools.publish_sop import EPHEMERAL_WARNING, publish_sop  # noqa: F401
from src.mcp.tools.run_sop import run_sop  # noqa: F401
from src.mcp.tools.submit_sop_feedback import submit_sop_feedback  # noqa: F401
from src.utils import get_storage_backend

logger = logging.getLogger(__name__)

# Initialize storage backend at module level (Requirement 6.1)
backend = get_storage_backend()

# Initialize FastMCP server with FileSystemProvider for static tools
mcp = FastMCP(
    "SOP MCP Server",
    providers=[FileSystemProvider(Path(__file__).parent / "mcp")],
)

# Register concrete SOP resources for discoverability
register_sop_resources(mcp)

# Expose resources as tools for clients that lack resource protocol support
mcp.add_transform(ResourcesAsTools(mcp))


def run():
    """Entry point for uvx / uv run sop-mcp."""
    mcp.run(transport="stdio")

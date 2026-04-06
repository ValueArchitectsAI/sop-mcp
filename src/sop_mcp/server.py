"""SOP MCP Server - Main business logic.

This module contains the MCP server with FileSystemProvider-discovered
tools (run_sop, publish_sop, submit_sop_feedback) and dynamically
registered SOP resources.
"""

import logging
import os
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.providers import FileSystemProvider
from fastmcp.server.transforms import ResourcesAsTools

from src.sop_mcp.resources.sop_content import register_sop_resources
from src.sop_mcp.tools.publish_sop import EPHEMERAL_WARNING, publish_sop  # noqa: F401
from src.sop_mcp.tools.run_sop import run_sop  # noqa: F401
from src.sop_mcp.tools.submit_sop_feedback import submit_sop_feedback  # noqa: F401
from src.sop_mcp.utils import get_storage_backend

logger = logging.getLogger(__name__)

# Initialize storage backend at module level (Requirement 6.1)
backend = get_storage_backend()


def _init_hooks():
    """Bootstrap the hook system if SOP_HOOK_CONFIG is set.

    Returns the HookExecutor instance (or None if hooks are disabled).
    """
    from src.sop_mcp.hooks import (
        HookExecutor,
        HookRegistry,
        LLMSuggestionHandler,
        ShellHandler,
        WebhookHandler,
        hooks_enabled,
        parse_hook_config,
    )

    if not hooks_enabled():
        logger.debug("Hook system disabled (SOP_HOOK_CONFIG not set)")
        return None

    config_str = os.environ.get("SOP_HOOK_CONFIG", "")
    callbacks = parse_hook_config(config_str)
    if not callbacks:
        logger.warning("SOP_HOOK_CONFIG set but no valid hooks parsed")
        return None

    registry = HookRegistry()
    for cb in callbacks:
        registry.register(cb.event_type, cb)

    executor = HookExecutor(registry)
    executor.register_handler("shell", ShellHandler())
    executor.register_handler("webhook", WebhookHandler())
    executor.register_handler("llm", LLMSuggestionHandler(executor))

    logger.info("Hook system initialized with %d callbacks", len(callbacks))
    return executor


_hook_executor = _init_hooks()

# Initialize FastMCP server with FileSystemProvider for static tools
mcp = FastMCP(
    "SOP MCP Server",
    providers=[FileSystemProvider(Path(__file__).parent)],
)

# Add hook middleware (fires events after tool calls)
from src.sop_mcp.hook_middleware import HookMiddleware  # noqa: E402

_hook_middleware = HookMiddleware(executor=_hook_executor)
mcp.add_middleware(_hook_middleware)

# Register concrete SOP resources for discoverability
register_sop_resources(mcp)

# Expose resources as tools for clients that lack resource protocol support
mcp.add_transform(ResourcesAsTools(mcp))


def run():
    """Entry point for uvx / uv run sop-mcp."""
    mcp.run(transport="stdio")

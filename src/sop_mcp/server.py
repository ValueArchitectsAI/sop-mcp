"""SOP MCP Server — stdio entry point.

Run with: ``uvx sop-mcp`` or ``uv run sop-mcp``
"""

from __future__ import annotations

import logging
import os

from src.sop_mcp.hooks import HookExecutor, install_hooks
from src.sop_mcp.tools import publish_sop, run_sop, submit_sop_feedback
from src.sop_mcp.utils import get_storage_backend, register_sop_resources
from src.sop_mcp.utils.stdiomcp import StdioMCP

logger = logging.getLogger(__name__)

# Initialize storage backend at module level
backend = get_storage_backend()


def _init_hooks() -> HookExecutor | None:
    """Bootstrap the hook system if SOP_HOOK_CONFIG is set."""
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


# Initialize MCP server
mcp = StdioMCP("SOP MCP Server")

# Register tools
for _mod in (run_sop, publish_sop, submit_sop_feedback):
    mcp.tool(name=_mod.NAME, description=_mod.DESCRIPTION)(_mod.handler)

# Register SOP resources for discoverability
register_sop_resources(mcp)

# Install hook system (no-op if SOP_HOOK_CONFIG not set)
install_hooks(mcp, _init_hooks())


def run() -> None:
    """Entry point for uvx / uv run sop-mcp."""
    mcp.run(transport="stdio")

"""Hook integration for the MCP server.

Wraps ``mcp.call_tool`` to fire hook events after every tool call.
Uses the tool name directly as the event type (e.g. run_sop, publish_sop,
submit_sop_feedback). Also fires a bonus ``sop_completed`` event when
run_sop reaches the final step.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _extract_context(tool_name: str, arguments: Dict[str, Any], result_data: Dict[str, Any]) -> Dict[str, str]:
    """Build context variables from tool arguments and result."""
    ctx: Dict[str, str] = {}
    for k, v in result_data.items():
        ctx[k] = str(v) if v is not None else ""
    for k, v in arguments.items():
        if v is not None:
            ctx[k] = str(v)
    return ctx


def install_hooks(mcp_server: Any, executor: Optional[Any]) -> None:
    """Monkey-patch ``mcp_server.call_tool`` to fire hook events after each call.

    If *executor* is ``None`` this is a no-op.
    """
    if executor is None:
        return

    original_call_tool = mcp_server.call_tool

    async def _hooked_call_tool(name: str, arguments: dict[str, Any]):
        result = await original_call_tool(name, arguments)

        # Parse result for context extraction
        # StdioMCP.call_tool returns a JSON string
        result_data: Dict[str, Any] = {}
        try:
            if isinstance(result, str):
                result_data = json.loads(result)
            elif isinstance(result, dict):
                result_data = result
        except (json.JSONDecodeError, TypeError):
            pass

        ctx = _extract_context(name, arguments, result_data)

        # Fire hook for every tool call
        try:
            executor.execute_event(name, context=ctx)
            logger.info("Hook event '%s' fired", name)
        except Exception as e:
            logger.warning("Hook execution failed for '%s' event: %s", name, e)

        # Bonus: fire sop_completed when run_sop reaches the last step
        if name == "run_sop":
            try:
                current = result_data.get("current_step")
                total = result_data.get("total_steps")
                if current is not None and total is not None and int(current) == int(total):
                    executor.execute_event("sop_completed", context=ctx)
                    logger.info("Hook event 'sop_completed' fired")
            except Exception as e:
                logger.warning("Hook execution failed for 'sop_completed' event: %s", e)

        # Inject LLM suggestions into response
        if executor.suggested_actions:
            suggestions = list(executor.suggested_actions)
            executor.suggested_actions.clear()
            try:
                result_data["suggested_actions"] = suggestions
                result = json.dumps(result_data)
                logger.info("Injected %d suggested_action(s) into response", len(suggestions))
            except Exception as e:
                logger.warning("Failed to inject suggested_actions: %s", e)

        return result

    mcp_server.call_tool = _hooked_call_tool

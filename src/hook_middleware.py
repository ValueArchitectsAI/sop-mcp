"""FastMCP middleware that fires hook events on every tool call.

Uses the tool name directly as the event type (e.g. run_sop, publish_sop,
submit_sop_feedback). Also fires a bonus ``sop_completed`` event when
run_sop reaches the final step.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastmcp.server.middleware import Middleware, MiddlewareContext

logger = logging.getLogger(__name__)


def _extract_context(tool_name: str, arguments: Dict[str, Any], result_data: Dict[str, Any]) -> Dict[str, str]:
    """Build context variables from tool arguments and result.

    Merges all string-coercible values from both arguments and result_data
    so any field is available for substitution.
    """
    ctx: Dict[str, str] = {}

    # Pull everything from the result
    for k, v in result_data.items():
        ctx[k] = str(v) if v is not None else ""

    # Overlay with arguments (user-provided values take precedence)
    for k, v in arguments.items():
        if v is not None:
            ctx[k] = str(v)

    return ctx


class HookMiddleware(Middleware):
    """Fires hook events after every tool call.

    Event type = tool name (e.g. ``run_sop``).
    Bonus ``sop_completed`` event fires when run_sop finishes the last step.

    The executor is stored directly on this instance to avoid dual-module
    class identity issues caused by FileSystemProvider.
    """

    def __init__(self, executor: Optional[Any] = None):
        self.executor = executor

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        result = await call_next(context)

        executor = self.executor
        if not executor:
            return result

        tool_name = context.message.name

        # Parse result for context extraction
        result_data: Dict[str, Any] = {}
        try:
            if hasattr(result, "structured_content") and result.structured_content:
                result_data = result.structured_content
            elif hasattr(result, "content") and result.content:
                result_data = json.loads(result.content[0].text)
        except (json.JSONDecodeError, AttributeError, IndexError, TypeError):
            pass

        arguments = context.message.arguments or {}
        ctx = _extract_context(tool_name, arguments, result_data)

        # Fire hook for every tool call using tool name as event type
        try:
            executor.execute_event(tool_name, context=ctx)
            logger.info("Hook event '%s' fired", tool_name)
        except Exception as e:
            logger.warning("Hook execution failed for '%s' event: %s", tool_name, e)

        # Bonus: fire sop_completed when run_sop reaches the last step
        if tool_name == "run_sop":
            try:
                current = result_data.get("current_step")
                total = result_data.get("total_steps")
                if current is not None and total is not None and int(current) == int(total):
                    try:
                        executor.execute_event("sop_completed", context=ctx)
                        logger.info("Hook event 'sop_completed' fired")
                    except Exception as e:
                        logger.warning("Hook execution failed for 'sop_completed' event: %s", e)
            except (ValueError, TypeError):
                pass

        return result

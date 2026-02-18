"""Continue executing an SOP with required context from the previous step."""

import logging
from typing import Annotated, Any

from fastmcp.tools import tool

from src.mcp.tools.run_sop import SopNameType, execute_step

logger = logging.getLogger(__name__)


@tool(
    description=(
        "Continue executing an SOP with the output from the previous step. "
        "You MUST provide step_output (your concrete output for the completed step) "
        "and previous_outputs (accumulated outputs from the response of the prior call).\n\n"
        "Each call returns the next step. Execute it, then call again with current_step "
        "incremented. When status is 'complete', use previous_outputs to compile your "
        "final comprehensive document with ALL concrete values from every step.\n\n"
        "IMPORTANT: You MUST execute ALL actions described in the returned step content. "
        "Do NOT just read or summarize the step — perform the actions using your available tools."
    ),
)
def run_sop_strict(
    sop_name: Annotated[SopNameType, "Name of the SOP being executed."],
    current_step: Annotated[int, "The step just completed (1-based)."],
    step_output: Annotated[
        str,
        "The concrete output you produced for the completed step. "
        "Include all specific values, names, dates, and details.",
    ],
    previous_outputs: Annotated[
        dict[str, str],
        "Accumulated outputs from prior steps. Pass this field back from the previous response.",
    ],
    version: Annotated[str | None, "Semantic version to run. Defaults to latest."] = None,
) -> dict[str, Any]:
    """Continue an SOP with required context from the previous step."""
    logger.info(
        "Invoking run_sop_strict: sop_name=%s, current_step=%s, version=%s",
        sop_name,
        current_step,
        version,
    )
    accumulated = dict(previous_outputs)
    accumulated[str(current_step)] = step_output

    response = execute_step(sop_name, current_step, version, tool_name="run_sop_strict")
    response["previous_outputs"] = accumulated
    return response

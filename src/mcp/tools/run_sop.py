"""Start or advance a Standard Operating Procedure."""

import logging
from typing import Annotated, Any, Literal

from fastmcp.tools import tool

from src.utils import SOP, get_storage_backend

logger = logging.getLogger(__name__)

backend = get_storage_backend()

_available_sops = backend.list_sops()
SopNameType = Literal[tuple(_available_sops)] if _available_sops else str


@tool(
    description=(
        "Start or advance a Standard Operating Procedure step by step. "
        "Use list_resources to discover available SOPs, then call this tool with the SOP name.\n\n"
        "Each call returns one step. Execute the step, then call again with current_step "
        "incremented to advance.\n\n"
        "IMPORTANT: You MUST execute ALL actions described in the returned step content. "
        "Do NOT just read or summarize the step — perform the actions using your available tools.\n\n"
        "When continuing (current_step >= 1), you MUST provide step_output with the concrete "
        "output you produced for the completed step."
    ),
)
def run_sop(
    sop_name: Annotated[SopNameType, "Name of the SOP to execute."],
    current_step: Annotated[int, "The step to advance from. 0 to start."] = 0,
    version: Annotated[str | None, "Semantic version to run. Defaults to latest."] = None,
    step_output: Annotated[
        str | None,
        "The concrete output you produced for the completed step. "
        "Include all specific values, names, dates, and details. "
        "Required when current_step >= 1, omit when starting (current_step=0).",
    ] = None,
) -> dict[str, Any]:
    """Start or advance an SOP — returns the next step."""
    logger.info("Invoking run_sop: sop_name=%s, current_step=%s, version=%s", sop_name, current_step, version)

    if current_step >= 1 and not step_output:
        raise ValueError(
            "step_output is required when current_step >= 1. "
            "Provide the concrete output you produced for the completed step."
        )

    sop = SOP(sop_name, version=version, base_dir=backend.base_dir)
    total = sop.total_steps

    if current_step < 0 or current_step > total:
        raise ValueError(f"current_step must be 0–{total} for '{sop_name}' (v{sop.version}), got {current_step}")

    response: dict[str, Any] = {
        "sop_name": sop.name,
        "sop_version": sop.version,
        "current_step": current_step,
        "total_steps": total,
    }

    if current_step == total:
        response["instruction"] = "SOP execution complete."
        return response

    next_step = current_step + 1
    logger.info("run_sop(%s) step %d/%d", sop_name, next_step, total)

    instruction = ""
    if next_step == 1:
        instruction += f"You are executing: {sop.title}\nTotal steps: {total}\nOverview: {sop.overview}\n\n---\n\n"
    instruction += f"Step {next_step} of {total}\n\n{sop.steps[current_step]}"

    instruction += "\n\n---\n\n"
    instruction += "⚠️ EXECUTION RULES — YOU MUST FOLLOW THESE BEFORE ADVANCING:\n"
    instruction += (
        "1. You MUST fully execute ALL actions described in this step and produce the concrete expected output.\n"
    )
    instruction += "2. You MUST NOT call run_sop to advance to the next step until you have completed this step.\n"
    instruction += "3. You MUST NOT skip, summarize, or batch multiple steps together.\n"
    instruction += (
        "4. Only after you have produced the expected output for this step "
        "should you call `run_sop` with current_step incremented.\n"
    )

    response["instruction"] = instruction
    return response

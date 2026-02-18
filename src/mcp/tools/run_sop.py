"""Start executing a Standard Operating Procedure."""

import logging
from typing import Annotated, Any, Literal

from fastmcp.tools import tool

from src.utils import SOP, get_storage_backend

logger = logging.getLogger(__name__)

backend = get_storage_backend()

_available_sops = backend.list_sops()
SopNameType = Literal[tuple(_available_sops)] if _available_sops else str


def execute_step(
    sop_name: str,
    current_step: int,
    version: str | None,
    *,
    tool_name: str = "run_sop",
) -> dict[str, Any]:
    """Return the next step content or completion signal."""
    sop = SOP(sop_name, version=version) if version else SOP(sop_name)
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

    is_last_step = next_step == total

    instruction += "\n\n---\n\n"
    instruction += "⚠️ EXECUTION RULES — YOU MUST FOLLOW THESE BEFORE ADVANCING:\n"
    instruction += (
        "1. You MUST fully execute ALL actions described in this step and produce the concrete expected output.\n"
    )
    instruction += f"2. You MUST NOT call {tool_name} to advance to the next step until you have completed this step.\n"
    instruction += "3. You MUST NOT skip, summarize, or batch multiple steps together.\n"
    instruction += (
        f"4. Only after you have produced the expected output for this step "
        f"may you call `{tool_name}` with current_step incremented.\n"
    )

    if is_last_step:
        instruction += (
            f"\n⚠️ THIS IS THE FINAL STEP ({next_step} of {total}). "
            f"After completing it, you MUST call `{tool_name}` with `current_step={total}` "
            "to finalize the SOP execution and receive the completion signal. "
            "Do NOT skip this final call.\n"
        )

    response["instruction"] = instruction

    return response


@tool(
    description=(
        "Start or advance a Standard Operating Procedure step by step. "
        "Use list_resources to discover available SOPs, then call this tool with the SOP name.\n\n"
        "Each call returns one step. Execute the step, then call again with current_step "
        "incremented to advance.\n\n"
        "IMPORTANT: You MUST execute ALL actions described in the returned step content. "
        "Do NOT just read or summarize the step — perform the actions using your available tools."
    ),
)
def run_sop(
    sop_name: Annotated[SopNameType, "Name of the SOP to execute."],
    current_step: Annotated[int, "The step to advance from. 0 to start."] = 0,
    version: Annotated[str | None, "Semantic version to run. Defaults to latest."] = None,
) -> dict[str, Any]:
    """Start or advance an SOP — returns the next step."""
    logger.info("Invoking run_sop: sop_name=%s, current_step=%s, version=%s", sop_name, current_step, version)
    return execute_step(sop_name, current_step, version)

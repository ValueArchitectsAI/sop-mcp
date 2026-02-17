"""Dynamic SOP step-runner tool execution logic.

Provides the handler factory and helpers used by the dynamically registered
run_* SOP tools.  Registration happens in server.py.
"""

import logging
from typing import Annotated, Any, Literal

from pydantic import Field

from src.utils import SOP

logger = logging.getLogger(__name__)


def _build_step_instruction(
    step_content: str,
    current_step: int,
    total_steps: int,
    is_complete: bool,
    sop: SOP | None = None,
) -> str:
    """Build the full instruction returned for a single SOP step.

    Structure: [overview header] + step content + execution instruction.
    """
    parts: list[str] = []

    if current_step == 1 and sop is not None:
        parts.append(f"You are executing: {sop.title}\nTotal steps: {total_steps}\nOverview: {sop.overview}\n\n---\n")

    parts.append(f"Step {current_step} of {total_steps}\n\n{step_content}\n")

    if is_complete:
        parts.append(
            "---\n"
            "EXECUTION INSTRUCTION: This is the LAST step of the SOP. Generate the concrete output\n"
            "described above using realistic data. Then call this tool with "
            f"completed_step_id={current_step}\n"
            "and include your complete output in the step_output field. Your step_output MUST\n"
            "contain specific values, not just field names or summaries.\n"
            "\n"
            "Include the `previous_outputs` from this response in your next tool call.\n"
            "\n"
            "Once done, ask the user if they'd like to provide feedback about this SOP via\n"
            "the submit_sop_feedback tool.\n"
        )
    else:
        parts.append(
            "---\n"
            "EXECUTION INSTRUCTION: Generate the concrete output described above using realistic\n"
            f"data. Then call this tool with completed_step_id={current_step} and include your\n"
            "complete output in the step_output field. Your step_output MUST contain specific\n"
            "values, not just field names or summaries.\n"
            "\n"
            "Include the `previous_outputs` from this response in your next tool call.\n"
        )

    return "\n".join(parts)


def _merge_outputs(
    previous_outputs: dict[str, str] | None,
    current_step: int | None,
    step_output: str | None,
) -> dict[str, str]:
    """Merge step_output into previous_outputs under str(current_step).

    Returns a new dict — never mutates the input.
    """
    merged = dict(previous_outputs) if previous_outputs else {}
    if current_step is not None and step_output is not None:
        merged[str(current_step)] = step_output
    return merged


def _create_sop_handler(sop: SOP, versions: list[str]):
    """Create a handler function for an SOP tool.

    Schema metadata (total_steps, version enum) is baked in from the SOP instance.
    Version-specific content is loaded via SOP(name, version=...) at call time.
    """
    total_steps = sop.total_steps
    sop_name = sop.name
    latest_version = sop.version

    StepType = Annotated[
        int,
        Field(
            default=0,
            ge=0,
            le=total_steps,
            description=f"The step to advance from. 0 to start, {total_steps} to complete.",
        ),
    ]

    VersionType = Annotated[
        Literal[tuple(versions)],
        Field(
            default=latest_version,
            description=f"Semantic version. Available: {', '.join(versions)}. Defaults to {latest_version}.",
        ),
    ]

    def handler(
        current_step: StepType,
        version: VersionType,
        step_output: Annotated[
            str,
            "The concrete output you produced for the completed step. "
            "Include all specific values, names, dates, and details.",
        ]
        | None = None,
        previous_outputs: Annotated[
            dict[str, str],
            "Accumulated outputs from prior steps. Pass this field back from the previous response.",
        ]
        | None = None,
    ) -> dict[str, Any]:
        """Execute an SOP step by step."""
        tool_name = f"run_{sop_name}"
        logger.info("Invoking %s with args: current_step=%s, version=%s", tool_name, current_step, version)

        loaded_sop = SOP(sop_name, version=version)

        # Completion
        if current_step == loaded_sop.total_steps:
            logger.info("%s completed successfully", tool_name)
            accumulated = _merge_outputs(previous_outputs, current_step, step_output)
            completion_signal = (
                "All steps complete. Now produce your FINAL COMPREHENSIVE DOCUMENT.\n\n"
                "Use the `previous_outputs` field below to compile your final document.\n"
                "Include all concrete values from every step.\n"
                "Review the step_output you submitted for each step in this conversation.\n"
                "Compile them into a single detailed document that includes ALL concrete values,\n"
                "names, dates, numbers, and specifics from every step. Do not summarize — include\n"
                "the full detail from each step's output."
            )
            response = {
                "sop_name": loaded_sop.name,
                "sop_version": loaded_sop.version,
                "instruction": completion_signal,
            }
            if accumulated:
                response["previous_outputs"] = accumulated
            return response

        # Return next step
        next_step = current_step + 1
        is_complete = next_step == loaded_sop.total_steps
        accumulated = _merge_outputs(previous_outputs, current_step, step_output)
        logger.info("%s completed successfully", tool_name)
        response = {
            "sop_name": loaded_sop.name,
            "sop_version": loaded_sop.version,
            "instruction": _build_step_instruction(
                loaded_sop.steps[next_step - 1],
                next_step,
                loaded_sop.total_steps,
                is_complete,
                sop=loaded_sop if current_step == 0 else None,
            ),
        }
        if accumulated:
            response["previous_outputs"] = accumulated
        return response

    return handler

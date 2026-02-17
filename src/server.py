"""SOP MCP Server - Main business logic.

This module contains the MCP server with dynamically registered SOP tools
using FastMCP (high-level MCP SDK API).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastmcp import FastMCP

from src.utils import SOP, get_storage_backend

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("SOP MCP Server")

# Initialize storage backend at module level (Requirement 6.1)
backend = get_storage_backend()

EPHEMERAL_WARNING = (
    "⚠️ WARNING: This data was written to ephemeral storage and may be lost "
    "when the package cache is refreshed. Set the SOP_STORAGE_DIR environment "
    "variable to a persistent path to avoid data loss."
)


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

    # 1. SOP overview header (first step only)
    if current_step == 1 and sop is not None:
        parts.append(f"You are executing: {sop.title}\nTotal steps: {total_steps}\nOverview: {sop.overview}\n\n---\n")

    # 2. Step content
    parts.append(f"Step {current_step} of {total_steps}\n\n{step_content}\n")

    # 3. Execution instruction
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

    Returns a new dict — never mutates the input.  When both
    previous_outputs and step_output are None/empty the result is ``{}``.
    """
    merged = dict(previous_outputs) if previous_outputs else {}
    if current_step is not None and step_output is not None:
        merged[str(current_step)] = step_output
    return merged


def _create_sop_handler(sop_name: str):
    """Create a handler function for an SOP tool that supports an optional version parameter."""

    def handler(
        current_step: int | None = None,
        version: str | None = None,
        step_output: str | None = None,
        previous_outputs: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute an SOP step by step.

        Args:
            current_step: The step to advance from. Omit to start from the beginning.
            version: Optional semantic version (e.g. "1.0", "2.1.0"). Defaults to latest.
            step_output: The concrete output you produced for the completed
                step. Include all specific values, names, dates, and details
                as specified in the step's Expected Output section.
            previous_outputs: Accumulated outputs from prior steps. Keys are step
                number strings, values are the concrete output text. Pass this field
                back from the previous response to maintain context across steps.
        """
        tool_name = f"run_{sop_name}"
        logger.info("Invoking %s with args: current_step=%s, version=%s", tool_name, current_step, version)

        try:
            content = backend.read_sop(sop_name, version)
            sop = SOP.from_content(content)
        except FileNotFoundError as e:
            logger.warning("%s error: %s", tool_name, e)
            return {"error": str(e)}
        except ValueError as e:
            logger.warning("%s error: %s", tool_name, e)
            return {"error": str(e)}

        if sop.total_steps == 0:
            logger.warning("%s error: SOP has no steps", tool_name)
            return {"error": "SOP has no steps"}

        # If no current_step provided, start from step 1 with overview
        if current_step is None:
            is_complete = sop.total_steps == 1
            logger.info("%s completed successfully", tool_name)
            response = {
                "sop_name": sop.name,
                "sop_version": sop.version,
                "instruction": _build_step_instruction(sop.steps[0], 1, sop.total_steps, is_complete, sop=sop),
            }
            if sop.mcp_server_prerequisites:
                response["required_mcp_servers"] = sop.mcp_server_prerequisites
            if previous_outputs:
                response["previous_outputs"] = previous_outputs
            return response

        # Validate step number
        if current_step < 1 or current_step > sop.total_steps:
            logger.warning("%s error: Invalid step %s", tool_name, current_step)
            return {"error": f"Invalid step {current_step}. SOP has {sop.total_steps} steps (1-{sop.total_steps})."}

        # Check if already complete
        if current_step == sop.total_steps:
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
                "sop_name": sop.name,
                "sop_version": sop.version,
                "instruction": completion_signal,
            }
            if accumulated:
                response["previous_outputs"] = accumulated
            return response

        # Return next step
        next_step = current_step + 1
        is_complete = next_step == sop.total_steps
        accumulated = _merge_outputs(previous_outputs, current_step, step_output)
        logger.info("%s completed successfully", tool_name)
        response = {
            "sop_name": sop.name,
            "sop_version": sop.version,
            "instruction": _build_step_instruction(
                sop.steps[next_step - 1],
                next_step,
                sop.total_steps,
                is_complete,
                sop=sop,
            ),
        }
        if accumulated:
            response["previous_outputs"] = accumulated
        return response

    return handler


# --- Publish SOP tool ---


@mcp.tool()
def publish_sop(content: str, change_type: str = "minor") -> dict[str, Any]:
    """Publish a new or updated Standard Operating Procedure document.

    The SOP name is extracted from the content (expected format: SOP-WORD-WORD-WORD).
    The version is auto-bumped based on the change_type using semantic versioning:
    - "major": breaking change (e.g. 1.2.0 -> 2.0.0)
    - "minor": new feature / non-breaking change (e.g. 1.2.0 -> 1.3.0)
    - "patch": bugfix (e.g. 1.2.0 -> 1.2.1)

    For brand-new SOPs the initial version is 1.0.0 regardless of change_type.
    The version is written into the document and the SOP becomes the latest.
    """
    logger.info("Invoking publish_sop with args: content=<%s chars>, change_type=%s", len(content), change_type)

    if not content or not content.strip():
        return {"error": "SOP content is required"}

    if change_type not in ("major", "minor", "patch"):
        return {"error": f"Invalid change_type '{change_type}'. Must be one of: major, minor, patch"}

    try:
        sop = SOP.from_content(content)
    except ValueError as e:
        logger.warning("publish_sop error: %s", e)
        return {"error": str(e)}

    # Determine the new version by inspecting existing versions in the backend
    from src.utils.sop_parser import _parse_semver, _set_version_in_content

    existing_versions = backend.list_versions(sop.name)
    if not existing_versions:
        new_version = "1.0.0"
    else:
        latest = max(existing_versions, key=_parse_semver)
        parts = list(_parse_semver(latest))
        while len(parts) < 3:
            parts.append(0)
        if change_type == "major":
            parts[0] += 1
            parts[1] = 0
            parts[2] = 0
        elif change_type == "minor":
            parts[1] += 1
            parts[2] = 0
        elif change_type == "patch":
            parts[2] += 1
        new_version = ".".join(str(p) for p in parts)

    # Update version in content and write via backend
    content = _set_version_in_content(content, new_version)
    try:
        backend.write_sop(sop.name, new_version, content)
    except OSError as e:
        logger.warning("publish_sop error: %s", e)
        return {"error": str(e)}

    # Re-parse to get final state
    sop = SOP.from_content(content)

    logger.info("publish_sop completed successfully")
    result: dict[str, Any] = {
        "success": True,
        "sop_name": sop.name,
        "title": sop.title,
        "version": new_version,
        "change_type": change_type,
        "total_steps": sop.total_steps,
        "message": (
            f"SOP '{sop.name}' published as v{new_version} ({change_type}). "
            "Restart the server to register the new tool."
        ),
    }
    warnings = []
    if backend.is_ephemeral:
        warnings.append(EPHEMERAL_WARNING)
    # Check for missing time estimates in steps
    steps_missing_time = [i + 1 for i, step in enumerate(sop.steps) if "**Time Estimate:**" not in step]
    if steps_missing_time:
        warnings.append(
            f"Steps {', '.join(str(s) for s in steps_missing_time)} are missing a "
            "**Time Estimate:** field. Each step SHOULD include an estimated duration in minutes."
        )
    # Check for missing MCP server prerequisites (SHOULD-level)
    if not sop.mcp_server_prerequisites:
        tool_pattern = re.compile(r"`\w+`\s+tool|call\s+the\s+`?\w+`?\s+tool", re.IGNORECASE)
        if tool_pattern.search("\n".join(sop.steps)):
            warnings.append(
                "SOP steps reference MCP tools but no **Required MCP Servers** "
                "field was found in the Prerequisites section. Each SOP SHOULD "
                "declare required MCP servers."
            )
    if warnings:
        result["warning"] = " | ".join(warnings)
    return result


@mcp.tool()
def submit_sop_feedback(sop_name: str, feedback: str) -> dict[str, Any]:
    """Submit improvement feedback for a specific SOP.

    Collects user feedback about an SOP and stores it in a feedback.md file
    inside the SOP's folder. This feedback will be used to optimize the SOP
    in its next revision.

    Args:
        sop_name: Name of the SOP to provide feedback for (e.g. "authoring_new_sop").
        feedback: The improvement suggestion or feedback text.
    """
    logger.info("Invoking submit_sop_feedback with args: sop_name=%s, feedback=<%s chars>", sop_name, len(feedback))
    available = backend.list_sops()
    if sop_name not in available:
        logger.warning("submit_sop_feedback error: SOP '%s' not found", sop_name)
        return {"error": f"SOP '{sop_name}' not found. Available: {', '.join(available)}"}

    try:
        content = backend.read_sop(sop_name)
        sop = SOP.from_content(content)
    except (FileNotFoundError, ValueError) as e:
        logger.warning("submit_sop_feedback error: %s", e)
        return {"error": str(e)}

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = f"## Feedback — {timestamp}\n\n**SOP Version:** v{sop.version}\n\n{feedback}\n\n---\n\n"

    try:
        backend.append_feedback(sop_name, entry)
    except OSError as e:
        logger.warning("Failed to write feedback for %s: %s", sop_name, e)
        return {"error": f"Failed to write feedback file: {e}"}

    logger.info("Feedback submitted for %s v%s at %s", sop_name, sop.version, timestamp)
    result: dict[str, Any] = {
        "success": True,
        "sop_name": sop_name,
        "sop_version": sop.version,
        "timestamp": timestamp,
        "message": f"Feedback recorded for '{sop_name}' (v{sop.version}). It will be considered in the next revision.",
    }
    if backend.is_ephemeral:
        result["warning"] = EPHEMERAL_WARNING
    return result


# --- Explain SOP tool ---


@mcp.tool()
def explain_sop(sop_name: str | None = None) -> dict[str, Any]:
    """Get details about available SOPs.

    Call with no arguments to list all SOPs, or pass a specific sop_name to get its full overview and step outline."""
    logger.info("Invoking explain_sop with args: sop_name=%s", sop_name)
    available = backend.list_sops()

    if sop_name is None:
        summaries = []
        for name in available:
            try:
                content = backend.read_sop(name)
                sop = SOP.from_content(content)
                summaries.append(
                    {
                        "name": name,
                        "title": sop.title,
                        "version": sop.version,
                        "overview": sop.truncated_overview,
                        "total_steps": sop.total_steps,
                    }
                )
            except (FileNotFoundError, ValueError):
                summaries.append({"name": name, "error": "Could not parse SOP"})
        logger.info("explain_sop completed successfully")
        return {"available_sops": summaries, "total": len(summaries)}

    if sop_name not in available:
        logger.warning("explain_sop error: SOP '%s' not found", sop_name)
        return {"error": f"SOP '{sop_name}' not found. Available: {', '.join(available)}"}

    try:
        content = backend.read_sop(sop_name)
        sop = SOP.from_content(content)
    except (FileNotFoundError, ValueError) as e:
        logger.warning("explain_sop error: %s", e)
        return {"error": str(e)}

    step_outline = [step.splitlines()[0].replace("### ", "") for step in sop.steps]

    result = {
        "sop_name": sop.name,
        "title": sop.title,
        "version": sop.version,
        "overview": sop.overview,
        "total_steps": sop.total_steps,
        "steps": step_outline,
    }
    if sop.prerequisites:
        result["prerequisites"] = sop.prerequisites

    logger.info("explain_sop completed successfully")
    return result


# --- Dynamic SOP tool registration ---


def register_sop_tools():
    """Register one run_ tool per SOP folder with optional version parameter."""
    for sop_name in backend.list_sops():
        try:
            content = backend.read_sop(sop_name)
            sop = SOP.from_content(content)
        except (FileNotFoundError, ValueError):
            continue

        versions = backend.list_versions(sop_name)
        version_info = ", ".join(f"v{v}" for v in versions)

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
            ),
        )(_create_sop_handler(sop_name))


# Register all SOP tools at module load time
register_sop_tools()


def run():
    """Entry point for uvx / uv run sop-mcp."""
    mcp.run(transport="stdio")

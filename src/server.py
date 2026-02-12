"""SOP MCP Server - Main business logic.

This module contains the MCP server with dynamically registered SOP tools
using FastMCP (high-level MCP SDK API).
"""

from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.utils import SOP, SOPS_DIR, list_available_sops, resolve_sop, list_versions


# Initialize FastMCP server
mcp = FastMCP("SOP MCP Server")


def _build_step_instruction(step_content: str, current_step: int, total_steps: int, is_complete: bool) -> str:
    """Build an explicit instruction that tells the LLM to execute the step."""
    instruction = (
        f"You are now executing Step {current_step} of {total_steps}. "
        "You MUST perform ALL actions described below. Do NOT just summarize or describe them — "
        "actually carry them out using your available tools (file operations, shell commands, code generation, etc.). "
        "If a step requires user input or decisions, ask the user before proceeding.\n\n"
    )
    if is_complete:
        instruction += (
            "This is the FINAL step. After completing the actions below, summarize what was accomplished "
            "across all steps.\n\n"
            "OPTIONAL: Once done, ask the user if they'd like to provide feedback about this SOP's flow "
            "(e.g. unclear steps, missing info, ordering issues). If they do, call the submit_sop_feedback "
            "tool with their input so it can be used to improve the next revision.\n\n"
        )
    else:
        instruction += (
            f"After completing ALL actions in this step, call this tool again with current_step={current_step} "
            "to advance to the next step. Do NOT skip ahead.\n\n"
        )
    return instruction


def _create_sop_handler(sop_name: str):
    """Create a handler function for an SOP tool that supports an optional version parameter."""
    def handler(current_step: int | None = None, version: str | None = None) -> dict[str, Any]:
        """Execute an SOP step by step.

        Args:
            current_step: The step to advance from. Omit to start from the beginning.
            version: Optional semantic version (e.g. "1.0", "2.1.0"). Defaults to latest.
        """
        try:
            sop = resolve_sop(sop_name, version)
        except FileNotFoundError as e:
            return {"error": str(e)}
        except ValueError as e:
            return {"error": str(e)}

        if sop.total_steps == 0:
            return {"error": "SOP has no steps"}

        # If no current_step provided, start from step 1 with overview
        if current_step is None:
            is_complete = sop.total_steps == 1
            return {
                "sop_name": sop.name,
                "sop_version": sop.version,
                "title": sop.title,
                "overview": sop.overview,
                "instruction": _build_step_instruction(sop.steps[0], 1, sop.total_steps, is_complete),
                "current_step": 1,
                "total_steps": sop.total_steps,
                "step_content": sop.steps[0],
                "is_complete": is_complete,
            }

        # Validate step number
        if current_step < 1 or current_step > sop.total_steps:
            return {"error": f"Invalid step {current_step}. SOP has {sop.total_steps} steps (1-{sop.total_steps})."}

        # Check if already complete
        if current_step == sop.total_steps:
            return {
                "sop_name": sop.name,
                "sop_version": sop.version,
                "instruction": _build_step_instruction(sop.steps[current_step - 1], current_step, sop.total_steps, True),
                "current_step": current_step,
                "total_steps": sop.total_steps,
                "step_content": sop.steps[current_step - 1],
                "is_complete": True,
                "message": "SOP completed successfully!",
            }

        # Return next step
        next_step = current_step + 1
        is_complete = next_step == sop.total_steps
        return {
            "sop_name": sop.name,
            "sop_version": sop.version,
            "instruction": _build_step_instruction(sop.steps[next_step - 1], next_step, sop.total_steps, is_complete),
            "current_step": next_step,
            "total_steps": sop.total_steps,
            "step_content": sop.steps[next_step - 1],
            "is_complete": is_complete,
            "message": "SOP completed successfully!" if is_complete else None,
        }

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
    try:
        sop = SOP.publish(content, change_type)
    except ValueError as e:
        return {"error": str(e)}

    return {
        "success": True,
        "sop_name": sop.name,
        "title": sop.title,
        "version": sop.version,
        "change_type": change_type,
        "total_steps": sop.total_steps,
        "message": f"SOP '{sop.name}' published as v{sop.version} ({change_type}). Restart the server to register the new tool.",
    }

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
    available = list_available_sops()
    if sop_name not in available:
        return {"error": f"SOP '{sop_name}' not found. Available: {', '.join(available)}"}

    try:
        sop = SOP(sop_name)
    except (FileNotFoundError, ValueError) as e:
        return {"error": str(e)}

    feedback_path = SOPS_DIR / sop_name / "feedback.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    entry = f"## Feedback — {timestamp}\n\n**SOP Version:** v{sop.version}\n\n{feedback}\n\n---\n\n"

    # Append to existing file or create with header
    if feedback_path.exists():
        feedback_path.open("a", encoding="utf-8").write(entry)
    else:
        header = f"# Feedback Log — {sop.title}\n\nThis file collects improvement feedback for future SOP revisions.\n\n---\n\n"
        feedback_path.write_text(header + entry, encoding="utf-8")

    return {
        "success": True,
        "sop_name": sop_name,
        "sop_version": sop.version,
        "timestamp": timestamp,
        "feedback_file": str(feedback_path),
        "message": f"Feedback recorded for '{sop_name}' (v{sop.version}). It will be considered in the next revision.",
    }



# --- Explain SOP tool ---

@mcp.tool()
def explain_sop(sop_name: str | None = None) -> dict[str, Any]:
    """Get details about available SOPs. Call with no arguments to list all SOPs, or pass a specific sop_name to get its full overview and step outline."""
    available = list_available_sops()

    if sop_name is None:
        summaries = []
        for name in available:
            try:
                sop = SOP(name)
                summaries.append({"name": name, "title": sop.title, "version": sop.version, "overview": sop.truncated_overview, "total_steps": sop.total_steps})
            except (FileNotFoundError, ValueError):
                summaries.append({"name": name, "error": "Could not parse SOP"})
        return {"available_sops": summaries, "total": len(summaries)}

    if sop_name not in available:
        return {"error": f"SOP '{sop_name}' not found. Available: {', '.join(available)}"}

    try:
        sop = SOP(sop_name)
    except (FileNotFoundError, ValueError) as e:
        return {"error": str(e)}

    step_outline = [step.splitlines()[0].replace("### ", "") for step in sop.steps]

    return {
        "sop_name": sop.name,
        "title": sop.title,
        "version": sop.version,
        "overview": sop.overview,
        "total_steps": sop.total_steps,
        "steps": step_outline,
    }


# --- Dynamic SOP tool registration ---

def register_sop_tools():
    """Register one run_ tool per SOP folder with optional version parameter."""
    from src.utils.sop_parser import _parse_semver

    for sop_name in list_available_sops():
        try:
            sop = SOP(sop_name)
        except (FileNotFoundError, ValueError):
            continue

        versions = list_versions(sop_name)
        version_info = ", ".join(f"v{v}" for v in versions)

        mcp.tool(
            name=f"run_{sop.tool_name}",
            description=(
                f"{sop.title}. {sop.truncated_overview}\n\n"
                f"Available versions: {version_info}. Defaults to latest (v{sop.version}).\n\n"
                "The 'version' parameter is optional and defaults to the latest version.\n\n"
                "IMPORTANT: When you call this tool, you MUST execute ALL actions described in the returned step_content. "
                "Do NOT just read or summarize the step — perform the actions using your available tools. "
                "After completing a step, call this tool again with the current_step value to advance to the next step."
            ),
        )(_create_sop_handler(sop_name))


# Register all SOP tools at module load time
register_sop_tools()


def run():
    """Entry point for uvx / uv run sop-mcp."""
    mcp.run(transport="stdio")

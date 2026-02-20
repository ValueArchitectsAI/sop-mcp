"""Publish SOP tool — discovered by FileSystemProvider."""

import logging
import re
from typing import Annotated, Any

from fastmcp.tools import tool
from pydantic import Field

from src.utils import SOP, ChangeType
from src.utils.sop_parser import _parse_semver, _set_version_in_content

logger = logging.getLogger(__name__)


def _get_backend():
    """Lazy import to use the same backend instance as src.server (supports test patching)."""
    import src.server

    return src.server.backend


EPHEMERAL_WARNING = (
    "⚠️ WARNING: This data was written to ephemeral storage and may be lost "
    "when the package cache is refreshed. Set the SOP_STORAGE_DIR environment "
    "variable to a persistent path to avoid data loss."
)


@tool(
    description=(
        "Publish a new or updated Standard Operating Procedure document.\n\n"
        "The content parameter MUST contain the complete SOP markdown string. "
        "Pass the entire document as a single string value — do not omit it or pass an empty object.\n\n"
        'Example call: {"content": "# My SOP\\n\\n## Document Information\\n- **Document ID**: '
        "my_sop_name\\n- **Version**: 1.0.0\\n\\n## Overview\\nDescription.\\n\\n"
        '### Step 1: First step\\nDo the thing.", "change_type": "minor"}\n\n'
        "The SOP name is extracted from the Document ID field in the content. "
        "The version is auto-bumped based on change_type. "
        "New SOPs always start at v1.0.0."
    ),
)
def publish_sop(
    content: Annotated[
        str,
        Field(
            min_length=1,
            description=(
                "The complete SOP markdown document as a string. "
                "Must include: a # title, **Document ID** (lowercase_with_underscores, 3+ words), "
                "**Version**, ## Overview section, and at least one ### Step N: section."
            ),
        ),
    ],
    change_type: Annotated[
        ChangeType,
        Field(
            default=ChangeType.MINOR,
            description="Semver bump type: major (breaking), minor (feature), patch (bugfix).",
        ),
    ] = ChangeType.MINOR,
) -> dict[str, Any]:
    """Publish a new or updated SOP document.

    The SOP name is extracted from the content (the Document ID field).
    The version is auto-bumped based on the change_type using semantic versioning.
    For brand-new SOPs the initial version is 1.0.0 regardless of change_type.
    """
    logger.info("Invoking publish_sop with args: content=<%s chars>, change_type=%s", len(content), change_type.value)

    try:
        sop = SOP.from_content(content)
    except ValueError as e:
        logger.warning("publish_sop error: %s", e)
        return {"error": str(e)}

    existing_versions = _get_backend().list_versions(sop.name)
    if not existing_versions:
        new_version = "1.0.0"
    else:
        latest = max(existing_versions, key=_parse_semver)
        parts = list(_parse_semver(latest))
        while len(parts) < 3:
            parts.append(0)
        if change_type is ChangeType.MAJOR:
            parts[0] += 1
            parts[1] = 0
            parts[2] = 0
        elif change_type is ChangeType.MINOR:
            parts[1] += 1
            parts[2] = 0
        elif change_type is ChangeType.PATCH:
            parts[2] += 1
        new_version = ".".join(str(p) for p in parts)

    content = _set_version_in_content(content, new_version)
    try:
        _get_backend().write_sop(sop.name, new_version, content)
    except OSError as e:
        logger.warning("publish_sop error: %s", e)
        return {"error": str(e)}

    sop = SOP.from_content(content)

    logger.info("publish_sop completed successfully")
    result: dict[str, Any] = {
        "success": True,
        "sop_name": sop.name,
        "title": sop.title,
        "version": new_version,
        "change_type": change_type.value,
        "total_steps": sop.total_steps,
        "message": (
            f"SOP '{sop.name}' published as v{new_version} ({change_type.value}). "
            "Restart the server to register the new tool."
        ),
    }
    warnings = []
    if _get_backend().is_ephemeral:
        warnings.append(EPHEMERAL_WARNING)
    steps_missing_time = [i + 1 for i, step in enumerate(sop.steps) if "**Time Estimate:**" not in step]
    if steps_missing_time:
        warnings.append(
            f"Steps {', '.join(str(s) for s in steps_missing_time)} are missing a "
            "**Time Estimate:** field. Each step SHOULD include an estimated duration in minutes."
        )
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

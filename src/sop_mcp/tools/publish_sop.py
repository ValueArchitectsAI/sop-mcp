"""Publish SOP tool."""

import logging
import re
from enum import Enum
from typing import Any

from src.sop_mcp.utils import SOP, register_sop_resources, set_version_in_content
from src.sop_mcp.utils.sop_parser import _normalise_stage, _split_frontmatter
from src.sop_mcp.utils.storage import LocalFilesystemBackend

logger = logging.getLogger(__name__)


backend = LocalFilesystemBackend.from_env()


class Scope(Enum):
    """Scope of an SOP document."""

    PERSONAL = "personal"
    SHARED = "shared"


NAME = "publish_sop"
DESCRIPTION = (
    "Publish a new or updated Standard Operating Procedure document.\n\n"
    "The content parameter MUST contain the complete SOP markdown string with "
    "YAML frontmatter declaring:\n"
    "  - name   (required, snake_case, ≥3 underscore segments)\n"
    "  - owner  (required, non-empty string — team, alias, or email)\n"
    "  - stage  (required, 'preprod' or 'prod')\n"
    "  - version (auto-managed by this tool; set to 1 for new SOPs)\n"
    "  - description (optional — when omitted, the SOP's `## Overview` section "
    "is used for short summaries)\n\n"
    'Example call: {"content": "---\\nname: my_sop_name\\nversion: 1\\n'
    "owner: my-team\\nstage: preprod\\n---\\n\\n"
    "# My SOP\\n\\n## Overview\\nOverview text.\\n\\n"
    '### Step 1: First step\\nDo the thing."}\n\n'
    "Versioning: plain positive integers — 1, 2, 3, 4, … New SOPs start at 1; "
    "each subsequent publish increments by one. No semver.\n\n"
    "Layout: SOPs are stored flat in the storage directory by default. Pass an "
    "optional `path` (e.g. 'generated/', 'teams/eng/') to group the file under "
    "a subdirectory — identity is still the frontmatter `name`, so path is "
    "organizational only. When an SOP with the same `name` already exists at a "
    "different path, the publish is rejected to prevent duplicates; omit "
    "`path` to update an existing SOP in place.\n\n"
    "SOPs are published as personal (private) by default. Use scope='shared' "
    "for team-wide SOPs."
)


def _bump(latest: int) -> int:
    return latest + 1


def _overwrite_meta(content: str, *, version: int, stage: str) -> str:
    """Overwrite the frontmatter's version and stage values before writing."""
    import yaml

    meta, body = _split_frontmatter(content)
    meta["version"] = version
    meta["stage"] = stage
    new_frontmatter = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{new_frontmatter}\n---\n{body}"


def _collect_warnings(sop: SOP) -> list[str]:
    """Collect post-publish warnings about the SOP quality."""
    warnings: list[str] = []

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

    return warnings


def _refresh_resources() -> None:
    """Re-register MCP resources after a publish."""
    try:
        from src.sop_mcp.server import mcp as _mcp

        register_sop_resources(_mcp, backend=backend, notify=True)
    except Exception as exc:
        logger.warning("Failed to re-register resources after publish: %s", exc)


def handler(
    content: str,
    stage: str,
    scope: str = "personal",
    path: str | None = None,
) -> dict[str, Any]:
    """Publish a new or updated SOP document."""
    sc = Scope(scope) if isinstance(scope, str) else scope
    try:
        stage_norm = _normalise_stage(stage)
    except ValueError as exc:
        return {"error": str(exc)}

    logger.info(
        "Invoking publish_sop with args: content=<%s chars>, stage=%s, scope=%s, path=%s",
        len(content),
        stage_norm,
        sc.value,
        path,
    )

    try:
        sop = SOP.from_content(content)
    except ValueError as e:
        logger.warning("publish_sop error: %s", e)
        return {"error": str(e)}

    if not sop.owner:
        return {"error": "Frontmatter `owner` is required and must be a non-empty string."}

    existing_versions = backend.list_versions(sop.name)
    new_version = 1 if not existing_versions else _bump(max(existing_versions))

    try:
        content = _overwrite_meta(content, version=new_version, stage=stage_norm)
        content = set_version_in_content(content, new_version)
    except ValueError as e:
        return {"error": str(e)}

    try:
        written_path = backend.write_sop(sop.name, new_version, content, path=path)
    except (OSError, ValueError) as e:
        logger.warning("publish_sop error: %s", e)
        return {"error": str(e)}

    sop = SOP.from_content(content)
    _refresh_resources()

    logger.info("publish_sop completed successfully")
    result: dict[str, Any] = {
        "success": True,
        "sop_name": sop.name,
        "title": sop.title,
        "version": new_version,
        "stage": sop.stage,
        "owner": sop.owner,
        "scope": sc.value,
        "total_steps": sop.total_steps,
        "path": str(written_path.relative_to(backend.base_dir)),
        "message": f"SOP '{sop.name}' published as v{new_version} ({sop.stage}) with {sc.value} scope.",
    }

    warnings = _collect_warnings(sop)
    if warnings:
        result["warning"] = " | ".join(warnings)
    return result

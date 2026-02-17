"""SOP Parser module for extracting structured data from SOP markdown files.

This module provides the SOP class for loading and accessing Standard Operating
Procedure markdown files, plus utilities for listing and locating SOPs.

Storage layout:
    src/sops/{sop_name}/
        v{version}.md   — versioned snapshots (latest resolved by highest semver)

Naming convention:
    Folder name = Document ID = lowercase with underscores (e.g. "sop_creation_guide")
    Tool name   = "run_{folder_name}" (e.g. "run_sop_creation_guide")
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Any


class ChangeType(Enum):
    """Semantic versioning bump type for SOP publishing."""

    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


# Directory where SOP files are stored, relative to the src directory
SOPS_DIR = Path(__file__).parent.parent / "sops"


def _parse_semver(version_str: str) -> tuple[int, ...]:
    """Parse a version string into a comparable tuple.

    Handles formats like "1.0", "1.0.0", "2.1.3".
    """
    parts = version_str.strip().split(".")
    return tuple(int(p) for p in parts)


class SOP:
    """Represents a parsed Standard Operating Procedure document.

    Attributes:
        name: The SOP identifier (e.g. "SOP-AUTHORING-NEW-SOP").
        path: Resolved file path (None if created from content).
        title: The SOP title extracted from the level-1 heading.
        overview: The Overview section content.
        steps: List of step contents.
        version: Semantic version extracted from the document (e.g. "1.0").
        tool_name: Tool name slug derived from the document ID.
    """

    def __init__(self, name: str, version: str | None = None, base_dir: Path | None = None) -> None:
        self.name = name
        sop_dir = (base_dir or SOPS_DIR) / name

        if version is not None:
            self.path = sop_dir / f"v{version}.md"
        else:
            # Resolve latest by picking the highest semver v*.md file
            self.path = _resolve_latest_path(sop_dir)

        if not self.path.exists():
            raise FileNotFoundError(f"SOP file not found: {self.path}")

        content = self.path.read_text(encoding="utf-8")
        parsed = _parse_content(content)
        self.title: str = parsed["title"]
        self.overview: str = parsed["overview"]
        self.steps: list[str] = parsed["steps"]
        self.version: str = parsed["version"]
        self.tool_name: str = _name_to_tool_name(self.name)
        self.prerequisites: str = parsed.get("prerequisites", "")
        self.mcp_server_prerequisites: list[str] = parsed.get("mcp_server_prerequisites", [])

    @classmethod
    def from_content(cls, content: str) -> "SOP":
        """Create an SOP instance from raw markdown content (no file required).

        The SOP name is extracted from the content via the Document ID field.
        Expected format: lowercase words separated by underscores, at least 3 words
        (e.g. "sop_creation_guide").

        Raises ValueError if the name cannot be found or the content is malformed.
        """
        name = _extract_doc_id(content)
        if not name:
            raise ValueError(
                "Could not extract SOP name from content. "
                "Expected **Document ID**: with a lowercase underscore-separated name "
                "(at least 3 words, e.g. sop_creation_guide)"
            )

        instance = object.__new__(cls)
        instance.name = name
        instance.path = None

        parsed = _parse_content(content)
        instance.title = parsed["title"]
        instance.overview = parsed["overview"]
        instance.steps = parsed["steps"]
        instance.version = parsed["version"]
        instance.tool_name = _name_to_tool_name(instance.name)
        instance.prerequisites = parsed.get("prerequisites", "")
        instance.mcp_server_prerequisites = parsed.get("mcp_server_prerequisites", [])
        return instance

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def truncated_overview(self) -> str:
        """Overview text, truncated to 150 chars if needed."""
        if len(self.overview) > 150:
            return self.overview[:147] + "..."
        return self.overview

    @classmethod
    def publish(cls, content: str, change_type: ChangeType = ChangeType.MINOR) -> "SOP":
        """Validate content, auto-bump the semantic version, write to disk, and return the SOP.

        The version is determined automatically based on the change_type and the
        latest existing version for this SOP's base name:
        - ChangeType.MAJOR: breaking change (e.g. 1.2.0 -> 2.0.0)
        - ChangeType.MINOR: new feature / non-breaking change (e.g. 1.2.0 -> 1.3.0)
        - ChangeType.PATCH: bugfix (e.g. 1.2.0 -> 1.2.1)

        For brand-new SOPs the initial version is 1.0.0 regardless of change_type.
        The version is written into the document and the SOP becomes the latest.

        Files are written to:
            src/sops/{sop_name}/v{version}.md

        Raises:
            ValueError: If content is empty, malformed, or change_type is invalid.
        """
        if not content or not content.strip():
            raise ValueError("SOP content is required")

        if not isinstance(change_type, ChangeType):
            raise ValueError(f"Invalid change_type '{change_type}'. Must be a ChangeType enum member.")

        sop = cls.from_content(content)

        # Determine the new version
        new_version = _bump_version(sop.name, change_type)

        # Update or insert the version in the content
        content = _set_version_in_content(content, new_version)

        # Write to directory structure — folder name matches doc ID (lowercase, underscores)
        sop_dir = SOPS_DIR / sop.name
        sop_dir.mkdir(parents=True, exist_ok=True)

        versioned_path = sop_dir / f"v{new_version}.md"
        versioned_path.write_text(content, encoding="utf-8")

        # Return the freshly-loaded SOP
        return cls(sop.name)


# --- Internal parsing helpers ---


def _parse_content(content: str) -> dict[str, Any]:
    """Parse SOP markdown content and extract title, overview, steps, and version."""
    title = _extract_title(content)
    overview = _extract_overview(content)
    steps = _extract_steps(content)
    version = _extract_version(content)
    prerequisites = _extract_prerequisites(content)
    mcp_server_prerequisites = _extract_mcp_server_prerequisites(content)
    return {
        "title": title,
        "overview": overview,
        "steps": steps,
        "version": version,
        "prerequisites": prerequisites,
        "mcp_server_prerequisites": mcp_server_prerequisites,
    }


def _extract_title(content: str) -> str:
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if not match:
        raise ValueError("SOP file is missing a title (level-1 heading)")
    return match.group(1).strip()


def _extract_overview(content: str) -> str:
    pattern = r"^##\s+Overview\s*\n(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError("SOP file is missing an Overview section")
    return match.group(1).strip()


def _extract_steps(content: str) -> list[str]:
    pattern = r"^(###\s+Step\s+\d+:\s+.+?)(?=^###\s+Step\s+\d+:|\Z)"
    matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
    if not matches:
        raise ValueError("SOP file has no steps (expected ### Step N: format)")
    return [step.strip() for step in matches]


def _extract_version(content: str) -> str:
    """Extract semantic version from the SOP document metadata.

    Looks for patterns like:
    - "**Version:** 1.1"
    - "**Version**: 1.0.0"
    - "- **Version**: 2.0"
    - "| **Version** | 1.1 |"  (table format)
    Returns "1.0.0" as default if no version is found.
    """
    # Inline format: **Version:** 1.1 or **Version**: 1.0.0
    match = re.search(r"\*\*Version:?\*\*:?\s*(\d+(?:\.\d+)*)", content)
    if match:
        return match.group(1)
    # Table format: | **Version** | 1.1 |
    match = re.search(r"\*\*Version\*\*\s*\|\s*(\d+(?:\.\d+)*)", content)
    if match:
        return match.group(1)
    return "1.0.0"


def _extract_prerequisites(content: str) -> str:
    """Extract the raw text of the ## Prerequisites section.

    Returns the section body (everything between ``## Prerequisites`` and the
    next ``##`` heading or end-of-document).  Returns an empty string when the
    section is not present.
    """
    pattern = r"^##\s+Prerequisites\s*\n(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if not match:
        return ""
    return match.group(1).strip()


def _extract_mcp_server_prerequisites(content: str) -> list[str]:
    """Extract MCP server names from the **Required MCP Servers** field.

    Recognised label formats::

        **Required MCP Servers** (should):
        **Required MCP Servers**:

    Each bulleted list item (``- name``) following the label is collected.
    Descriptions after `` — ``, `` – ``, or `` - `` separators are stripped.
    Empty or whitespace-only items are skipped.  Collection stops at the next
    non-list-item line (blank lines are tolerated between items).

    Returns an empty list when the field is not found.
    """
    # Match the label line — optional "(should)" and colon
    label_pattern = r"\*\*Required MCP Servers\*\*(?:\s*\(should\))?\s*:"
    label_match = re.search(label_pattern, content)
    if not label_match:
        return []

    # Grab everything after the label until end-of-string
    rest = content[label_match.end() :]

    servers: list[str] = []
    for line in rest.split("\n"):
        stripped = line.strip()
        # Skip blank lines between items
        if not stripped:
            continue
        # A bare dash (possibly with trailing whitespace) is an empty list item — skip it
        if stripped == "-":
            continue
        # Stop when we hit a non-list-item line
        if not stripped.startswith("- "):
            break
        item = stripped[2:].strip()
        # Strip description after separator: " — ", " – ", or " - "
        item = re.split(r"\s(?:—|–|-)\s", item, maxsplit=1)[0].strip()
        if item:
            servers.append(item)

    return servers


def _resolve_latest_path(sop_dir: Path) -> Path:
    """Find the highest semver v*.md file in an SOP directory."""
    versioned = list(sop_dir.glob("v*.md"))
    if not versioned:
        raise FileNotFoundError(f"SOP file not found: {sop_dir}/v*.md")
    versioned.sort(key=lambda f: _parse_semver(f.stem[1:]), reverse=True)
    return versioned[0]


def _extract_doc_id(content: str) -> str | None:
    """Extract the Document ID from SOP markdown content.

    Looks for a line like:
        - **Document ID**: sop_creation_guide

    Returns the ID string (lowercase, underscores) or None if not found.
    The ID must have at least 3 words (2+ underscores).
    """
    match = re.search(
        r"\*\*Document\s+ID\*\*:?\s*([a-z][a-z0-9]*(?:_[a-z0-9]+){2,})",
        content,
    )
    return match.group(1) if match else None


def _name_to_tool_name(sop_name: str) -> str:
    """Derive tool name from the SOP folder name.

    Folder name is already lowercase with underscores (e.g. "sop_creation_guide").
    Returns as-is since it's already in the right format.
    """
    return sop_name


# --- Module-level utilities ---


def list_available_sops() -> list[str]:
    """Return sorted list of available SOP folder names from the sops directory.

    Layout: src/sops/{name}/v{version}.md
    Folder names are lowercase with underscores (e.g. "sop_creation_guide").
    """
    if not SOPS_DIR.exists():
        return []

    names: list[str] = []
    for d in SOPS_DIR.iterdir():
        if d.is_dir() and list(d.glob("v*.md")):
            names.append(d.name)

    return sorted(names)


def list_versions(sop_name: str) -> list[str]:
    """Return sorted list of available versions for an SOP.

    Reads v*.md files from src/sops/{sop_name}/.
    """
    sop_dir = SOPS_DIR / sop_name
    if not sop_dir.is_dir():
        return []

    versions = []
    for f in sop_dir.glob("v*.md"):
        v = f.stem[1:]  # strip leading 'v'
        versions.append(v)
    versions.sort(key=_parse_semver)
    return versions


def resolve_sop(sop_name: str, version: str | None = None) -> SOP:
    """Resolve an SOP by folder name and optional semantic version.

    The version parameter is optional. When omitted (None), latest is returned.

    Args:
        sop_name: The SOP folder name (e.g. "sop_creation_guide").
        version: Optional semantic version string (e.g. "1.0"). Defaults to latest.

    Raises:
        FileNotFoundError: If the SOP does not exist.
        ValueError: If the requested version is not found.
    """
    sop_dir = SOPS_DIR / sop_name
    if not sop_dir.is_dir():
        raise FileNotFoundError(f"No SOP found for '{sop_name}'")

    if version is None:
        return SOP(sop_name)

    try:
        sop = SOP(sop_name, version=version)
        if sop.version == version:
            return sop
    except (FileNotFoundError, ValueError):
        pass

    available = list_versions(sop_name)
    raise ValueError(f"Version '{version}' not found for '{sop_name}'. Available versions: {', '.join(available)}")


def _bump_version(sop_name: str, change_type: ChangeType) -> str:
    """Calculate the next version for an SOP given a change type.

    If no prior versions exist, returns "1.0.0".
    Otherwise bumps the latest version according to semver rules:
    - ChangeType.MAJOR: X+1.0.0
    - ChangeType.MINOR: X.Y+1.0
    - ChangeType.PATCH: X.Y.Z+1
    """
    versions = list_versions(sop_name)

    if not versions:
        return "1.0.0"

    latest = max(versions, key=_parse_semver)
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

    return ".".join(str(p) for p in parts)


def _set_version_in_content(content: str, version: str) -> str:
    """Insert or replace the **Version:** line in SOP markdown content."""
    pattern = r"(\*\*Version:?\*\*:?\s*)\d+(?:\.\d+)*"
    if re.search(pattern, content):
        return re.sub(pattern, rf"\g<1>{version}", content, count=1)

    lines = content.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("# "):
            lines.insert(i + 1, f"\n**Version:** {version}")
            break

    return "\n".join(lines)

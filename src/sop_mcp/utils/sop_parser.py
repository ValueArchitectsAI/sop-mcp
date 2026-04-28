"""SOP Parser — load Standard Operating Procedures from flat markdown files.

Each SOP is stored as a single file::

    {base_dir}/{sop_name}.sop.md

The file begins with YAML frontmatter carrying metadata::

    ---
    name: sop_creation_guide
    description: Step-by-step guide for creating SOPs…   # optional
    version: 1
    owner: value-architects
    stage: preprod   # or: prod
    ---

    # Title …

    ## Overview
    …

    ### Step 1: …

Versions are plain positive integers (``1``, ``2``, ``3``…) — no semver.
Legacy files still carrying ``"1.0"`` / ``"1.0.0"`` are tolerated on read
(coerced to the leading major integer); ``publish_sop`` overwrites every
write with the new integer, so stale forms are replaced on the next publish.
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class Stage(Enum):
    """Deployment stage of an SOP."""

    PREPROD = "preprod"
    PROD = "prod"


# Directory where SOP files are stored
SOPS_DIR = Path(__file__).parent.parent / "resources"

# Suffix used on disk for SOP markdown files
SOP_SUFFIX = ".sop.md"

# YAML frontmatter delimiter
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)


def _coerce_version(value: Any) -> int:
    """Coerce a raw version value into a positive integer.

    Accepts: ``1``, ``"1"``, ``"1.0"``, ``"1.0.0"``, ``"2.3"`` …
    All dotted forms collapse to their leading major integer.
    Raises ``ValueError`` for anything non-numeric or ``<= 0``.
    """
    if value is None:
        return 1
    if isinstance(value, bool):  # bool is a subclass of int — exclude explicitly
        raise ValueError(f"Invalid version value: {value!r}")
    if isinstance(value, int):
        if value <= 0:
            raise ValueError(f"Version must be a positive integer, got {value}")
        return value

    s = str(value).strip()
    if not s:
        return 1
    # "1.0" / "1.0.0" → 1
    head = s.split(".", 1)[0]
    if not head.isdigit():
        raise ValueError(f"Version must be a positive integer (1, 2, 3, …), got {value!r}")
    n = int(head)
    if n <= 0:
        raise ValueError(f"Version must be a positive integer, got {n}")
    return n


class SOP:
    """Represents a parsed Standard Operating Procedure document."""

    def __init__(self, name: str, version: int | None = None, base_dir: Path | None = None) -> None:
        self.name = name
        self.path = (base_dir or SOPS_DIR) / f"{name}{SOP_SUFFIX}"

        if not self.path.exists():
            raise FileNotFoundError(f"SOP file not found: {self.path}")

        content = self.path.read_text(encoding="utf-8")
        parsed = _parse_content(content)

        # When an explicit version is requested, verify it matches the file.
        if version is not None and parsed["version"] != _coerce_version(version):
            raise FileNotFoundError(
                f"Version '{version}' not found for '{name}'. Available version: {parsed['version']}"
            )

        self._populate(parsed)

    @classmethod
    def from_content(cls, content: str) -> "SOP":
        """Create an SOP instance from raw markdown content (no file required)."""
        parsed = _parse_content(content)
        name = parsed["name"]
        if not name:
            raise ValueError(
                "Could not extract SOP name from content. "
                "Expected a YAML frontmatter `name:` field with a lowercase "
                "underscore-separated name (at least 3 words, e.g. sop_creation_guide)"
            )

        instance = object.__new__(cls)
        instance.name = name
        instance.path = None
        instance._populate(parsed)
        return instance

    def _populate(self, parsed: dict[str, Any]) -> None:
        self.title: str = parsed["title"]
        self.overview: str = parsed["overview"]
        self.steps: list[str] = parsed["steps"]
        self.version: int = parsed["version"]
        self.description: str = parsed["description"]
        self.owner: str = parsed["owner"]
        self.stage: str = parsed["stage"]
        self.tool_name: str = self.name
        self.prerequisites: str = parsed.get("prerequisites", "")
        self.mcp_server_prerequisites: list[str] = parsed.get("mcp_server_prerequisites", [])

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def truncated_overview(self) -> str:
        """Overview text, truncated to 150 chars if needed."""
        if len(self.overview) > 150:
            return self.overview[:147] + "..."
        return self.overview


# --- Frontmatter + content parsing ---


def _split_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Split YAML frontmatter from the remaining markdown body.

    Returns ``(metadata, body)``.  When no frontmatter is present, metadata
    is an empty dict and body is the original content.
    """
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return {}, content
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML frontmatter: {exc}") from exc
    if not isinstance(meta, dict):
        raise ValueError("YAML frontmatter must be a mapping")
    return meta, content[m.end() :]


def _parse_content(content: str) -> dict[str, Any]:
    """Parse SOP markdown content and extract frontmatter + body structure."""
    meta, body = _split_frontmatter(content)

    name = meta.get("name")
    version = _coerce_version(meta.get("version"))
    description = meta.get("description") or ""
    owner = meta.get("owner") or ""
    stage = _normalise_stage(meta.get("stage"))

    return {
        "name": name,
        "version": version,
        "description": description,
        "owner": owner,
        "stage": stage,
        "title": _extract_title(body),
        "overview": _extract_overview(body),
        "steps": _extract_steps(body),
        "prerequisites": _extract_prerequisites(body),
        "mcp_server_prerequisites": _extract_mcp_server_prerequisites(body),
    }


def _normalise_stage(value: Any) -> str:
    """Coerce stage into one of ``preprod`` / ``prod``; default to preprod."""
    if value is None:
        return Stage.PREPROD.value
    s = str(value).strip().lower()
    if s in {"prod", "production"}:
        return Stage.PROD.value
    if s in {"preprod", "pre-prod", "pre_prod", "staging"}:
        return Stage.PREPROD.value
    raise ValueError(f"Invalid stage '{value}'. Expected 'preprod' or 'prod'.")


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


def _extract_prerequisites(content: str) -> str:
    pattern = r"^##\s+Prerequisites\s*\n(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if not match:
        return ""
    return match.group(1).strip()


def _extract_mcp_server_prerequisites(content: str) -> list[str]:
    """Extract MCP server names listed under ``**Required MCP Servers**``."""
    label_pattern = r"\*\*Required MCP Servers\*\*(?:\s*\(should\))?\s*:"
    label_match = re.search(label_pattern, content)
    if not label_match:
        return []

    rest = content[label_match.end() :]
    servers: list[str] = []
    for line in rest.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "-":
            continue
        if not stripped.startswith("- "):
            break
        item = stripped[2:].strip()
        item = re.split(r"\s(?:—|–|-)\s", item, maxsplit=1)[0].strip()
        if item:
            servers.append(item)
    return servers


# --- Frontmatter writing ---


def build_frontmatter(
    *,
    name: str,
    version: int,
    owner: str,
    stage: str = Stage.PREPROD.value,
    description: str = "",
) -> str:
    """Render a YAML frontmatter block with the canonical SOP fields."""
    version_int = _coerce_version(version)
    stage_norm = _normalise_stage(stage)
    meta: dict[str, Any] = {
        "name": name,
        "version": version_int,
        "owner": owner,
        "stage": stage_norm,
    }
    if description:
        meta["description"] = description
    body = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{body}\n---\n"


def set_version_in_content(content: str, version: int) -> str:
    """Update the ``version:`` value in the frontmatter and normalise the rest."""
    version_int = _coerce_version(version)
    meta, body = _split_frontmatter(content)
    if not meta:
        raise ValueError(
            "Cannot set version on content without YAML frontmatter. "
            "Add a frontmatter block with at least `name:` and `version:`."
        )
    meta["version"] = version_int
    if "stage" in meta:
        meta["stage"] = _normalise_stage(meta.get("stage"))
    new_frontmatter = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{new_frontmatter}\n---\n{body}"


# --- Module-level utilities ---


def list_available_sops(base_dir: Path | None = None) -> list[str]:
    """Return sorted list of available SOP names in the resources directory."""
    d = base_dir or SOPS_DIR
    if not d.exists():
        return []
    names = [f.name[: -len(SOP_SUFFIX)] for f in d.rglob(f"*{SOP_SUFFIX}") if f.is_file()]
    return sorted(names)


def list_versions(sop_name: str, base_dir: Path | None = None) -> list[int]:
    """Return the single version carried in the SOP file, or ``[]`` if missing."""
    d = base_dir or SOPS_DIR
    path = d / f"{sop_name}{SOP_SUFFIX}"
    if not path.is_file():
        return []
    try:
        sop = SOP(sop_name, base_dir=d)
    except (FileNotFoundError, ValueError):
        return []
    return [sop.version]


def resolve_sop(sop_name: str, version: int | None = None) -> SOP:
    """Resolve an SOP by name and optional version."""
    path = SOPS_DIR / f"{sop_name}{SOP_SUFFIX}"
    if not path.is_file():
        raise FileNotFoundError(f"No SOP found for '{sop_name}'")

    sop = SOP(sop_name, version=version)
    if version is not None and sop.version != _coerce_version(version):
        raise ValueError(f"Version '{version}' not found for '{sop_name}'. Available version: {sop.version}")
    return sop

"""Validate SOP document structure.

Checks that a given SOP markdown string has valid frontmatter,
required sections (Overview, Steps), and proper step formatting.

Usage:
    from validate_sop import validate_sop

    result = validate_sop(sop_content)
    if not result["valid"]:
        for error in result["errors"]:
            print(f"ERROR: {error}")
        for warning in result["warnings"]:
            print(f"WARNING: {warning}")
"""

from __future__ import annotations

import re

import yaml

# --- Frontmatter ---

REQUIRED_FRONTMATTER = {"name", "version", "owner", "stage"}
VALID_STAGES = {"preprod", "prod"}
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+){2,}$")

# --- Structure ---

STEP_HEADING_PATTERN = re.compile(r"^### Step \d+:")
RFC2119_KEYWORDS = {"MUST", "MUST NOT", "SHOULD", "SHOULD NOT", "MAY"}


def validate_sop(content: str) -> dict:
    """Validate a complete SOP document.

    Returns a dict with:
        valid: bool — True if no errors (warnings are ok)
        errors: list[str] — blocking issues
        warnings: list[str] — non-blocking suggestions
        frontmatter: dict | None — parsed frontmatter if valid
        steps_found: int — number of steps detected
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- Frontmatter validation ---
    meta = _validate_frontmatter(content, errors)

    # --- Body extraction ---
    body = _extract_body(content)
    if body is None:
        errors.append("No document body found after frontmatter")
        return _result(errors, warnings, meta, 0)

    # --- Section validation ---
    _validate_overview(body, errors)
    _validate_extra_sections(body, warnings)
    steps = _validate_steps(body, errors, warnings)

    return _result(errors, warnings, meta, len(steps))


def _result(errors: list[str], warnings: list[str], meta: dict | None, steps: int) -> dict:
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "frontmatter": meta,
        "steps_found": steps,
    }


# --- Frontmatter ---


def _validate_frontmatter(content: str, errors: list[str]) -> dict | None:
    """Parse and validate YAML frontmatter. Appends to errors list."""
    if not content.startswith("---"):
        errors.append("Missing frontmatter: document must start with '---'")
        return None

    parts = content.split("---", 2)
    if len(parts) < 3:
        errors.append("Malformed frontmatter: missing closing '---'")
        return None

    raw_yaml = parts[1].strip()
    if not raw_yaml:
        errors.append("Empty frontmatter block")
        return None

    try:
        meta = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as e:
        errors.append(f"Invalid YAML in frontmatter: {e}")
        return None

    if not isinstance(meta, dict):
        errors.append("Frontmatter must be a YAML mapping (key: value pairs)")
        return None

    # Required fields
    missing = REQUIRED_FRONTMATTER - set(meta.keys())
    if missing:
        errors.append(f"Missing required frontmatter fields: {', '.join(sorted(missing))}")

    # Name format
    name = meta.get("name")
    if isinstance(name, str) and not NAME_PATTERN.match(name):
        errors.append(f"'name' must be snake_case with >=3 segments (e.g. 'my_sop_name'), got '{name}'")

    # Version
    version = meta.get("version")
    if version is not None and (not isinstance(version, int) or version < 1):
        errors.append(f"'version' must be a positive integer, got {version!r}")

    # Owner
    owner = meta.get("owner")
    if owner is not None and (not isinstance(owner, str) or not owner.strip()):
        errors.append("'owner' must be a non-empty string")

    # Stage
    stage = meta.get("stage")
    if stage is not None and (not isinstance(stage, str) or stage not in VALID_STAGES):
        errors.append(f"'stage' must be one of {sorted(VALID_STAGES)}, got '{stage}'")

    return meta


# --- Body sections ---


def _extract_body(content: str) -> str | None:
    """Extract the markdown body after frontmatter."""
    if not content.startswith("---"):
        return content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    body = parts[2].strip()
    return body or None


def _validate_overview(body: str, errors: list[str]) -> None:
    """Check that an Overview section exists."""
    if not re.search(r"^##\s+Overview", body, re.MULTILINE):
        errors.append("Missing '## Overview' section")


# Sections that are delivered to the agent (visible at runtime)
_RELEVANT_SECTIONS = {"Overview", "Steps", "Procedure"}

# Sections that are never shown to the executing agent
_IRRELEVANT_PATTERN = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def _validate_extra_sections(body: str, warnings: list[str]) -> None:
    """Warn about sections that won't be shown to the agent at runtime.

    Only Overview and Steps/Procedure matter — everything else (Prerequisites,
    Scope, Definitions, References, etc.) is invisible to the agent during
    step-by-step execution.
    """
    all_h2 = _IRRELEVANT_PATTERN.findall(body)
    extra = [s.strip() for s in all_h2 if s.strip() not in _RELEVANT_SECTIONS]
    if extra:
        warnings.append(
            f"Sections not shown to agent during execution (consider moving content into steps): {', '.join(extra)}"
        )


def _validate_steps(body: str, errors: list[str], warnings: list[str]) -> list[str]:
    """Validate step headings and their content."""
    # Find all step sections
    step_matches = list(re.finditer(r"^### Step (\d+): (.+)$", body, re.MULTILINE))

    if not step_matches:
        errors.append("No steps found — SOP must have at least one '### Step N: Title' section")
        return []

    # Check sequential numbering
    numbers = [int(m.group(1)) for m in step_matches]
    expected = list(range(1, len(numbers) + 1))
    if numbers != expected:
        errors.append(f"Steps are not sequential: found {numbers}, expected {expected}")

    # Validate each step's content
    for i, match in enumerate(step_matches):
        step_num = int(match.group(1))
        # Extract step body (until next step or end)
        start = match.end()
        end = step_matches[i + 1].start() if i + 1 < len(step_matches) else len(body)
        step_body = body[start:end]

        _validate_step_content(step_num, step_body, errors, warnings)

    return [m.group(0) for m in step_matches]


def _validate_step_content(step_num: int, step_body: str, errors: list[str], warnings: list[str]) -> None:
    """Validate the content of a single step."""
    prefix = f"Step {step_num}"

    # Check for required sub-sections
    if "**Objective**" not in step_body:
        warnings.append(f"{prefix}: missing **Objective** section")

    if "**Actions**" not in step_body and "**Action" not in step_body:
        warnings.append(f"{prefix}: missing **Actions** section")

    if "**Expected Output**" not in step_body:
        warnings.append(f"{prefix}: missing **Expected Output** section")

    if "**Time Estimate**" not in step_body:
        warnings.append(f"{prefix}: missing **Time Estimate** section")

    # Check for RFC 2119 keywords (at least one MUST or SHOULD)
    has_rfc_keyword = any(kw in step_body for kw in RFC2119_KEYWORDS)
    if not has_rfc_keyword:
        warnings.append(f"{prefix}: no RFC 2119 keywords found (MUST/SHOULD/MAY)")

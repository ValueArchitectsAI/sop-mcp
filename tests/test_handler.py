"""Unit tests for the SOP MCP Server tools.

Tests the server.py implementation including:
- Dynamic SOP tool registration (tool names derived from folder name)
- SOP tool functionality (start, continue, and version selection)
"""

from __future__ import annotations

import json
import shutil
import string

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.server import mcp
from src.utils.storage_local import BUNDLED_SOPS_DIR


async def call_tool(name: str, arguments: dict | None = None) -> dict:
    """Helper: call a FastMCP tool and return the structured result dict."""
    result = await mcp.call_tool(name, arguments or {})
    if isinstance(result, tuple):
        return result[1]
    return json.loads(result[0].text)


class TestDynamicToolRegistration:
    """Tests for dynamic SOP tool registration."""

    @pytest.mark.asyncio
    async def test_sop_tools_registered_with_descriptive_names(self):
        tools = await mcp.list_tools()
        tool_names = [t.name for t in tools]
        assert "run_sop_creation_guide" in tool_names

    @pytest.mark.asyncio
    async def test_no_old_style_tool_names(self):
        tools = await mcp.list_tools()
        tool_names = [t.name for t in tools]
        assert "run_sop_create_001" not in tool_names
        assert "run_sop_create" not in tool_names
        # No hyphenated folder names
        assert "run_authoring-new-sop" not in tool_names

    @pytest.mark.asyncio
    async def test_tool_names_have_at_least_two_words(self):
        tools = await mcp.list_tools()
        for t in tools:
            if t.name.startswith("run_"):
                suffix = t.name[4:]
                assert "_" in suffix, f"Tool '{t.name}' suffix '{suffix}' has fewer than 2 words"


class TestSopToolStart:
    """Tests for starting an SOP (no current_step provided)."""

    @pytest.mark.asyncio
    async def test_returns_dict(self):
        result = await call_tool("run_sop_creation_guide")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_returns_sop_name(self):
        result = await call_tool("run_sop_creation_guide")
        assert result["sop_name"] == "sop_creation_guide"

    @pytest.mark.asyncio
    async def test_returns_sop_version(self):
        result = await call_tool("run_sop_creation_guide")
        assert "sop_version" in result
        assert isinstance(result["sop_version"], str)

    @pytest.mark.asyncio
    async def test_returns_title(self):
        result = await call_tool("run_sop_creation_guide")
        assert "title" in result
        assert isinstance(result["title"], str)

    @pytest.mark.asyncio
    async def test_returns_overview(self):
        result = await call_tool("run_sop_creation_guide")
        assert "overview" in result
        assert isinstance(result["overview"], str)

    @pytest.mark.asyncio
    async def test_returns_current_step_as_one(self):
        result = await call_tool("run_sop_creation_guide")
        assert result["current_step"] == 1

    @pytest.mark.asyncio
    async def test_returns_total_steps(self):
        result = await call_tool("run_sop_creation_guide")
        assert "total_steps" in result
        assert isinstance(result["total_steps"], int)
        assert result["total_steps"] > 0

    @pytest.mark.asyncio
    async def test_returns_step_content(self):
        result = await call_tool("run_sop_creation_guide")
        assert "step_content" in result
        assert isinstance(result["step_content"], str)


class TestSopToolContinue:
    """Tests for continuing an SOP (current_step provided)."""

    @pytest.mark.asyncio
    async def test_returns_next_step_number(self):
        result = await call_tool("run_sop_creation_guide", {"current_step": 1})
        assert result["current_step"] == 2

    @pytest.mark.asyncio
    async def test_returns_step_content(self):
        result = await call_tool("run_sop_creation_guide", {"current_step": 1})
        assert "step_content" in result
        assert isinstance(result["step_content"], str)

    @pytest.mark.asyncio
    async def test_returns_is_complete_false_for_mid_steps(self):
        result = await call_tool("run_sop_creation_guide", {"current_step": 1})
        assert result["is_complete"] is False

    @pytest.mark.asyncio
    async def test_returns_is_complete_true_for_last_step(self):
        start = await call_tool("run_sop_creation_guide")
        total = start["total_steps"]
        result = await call_tool("run_sop_creation_guide", {"current_step": total})
        assert result["is_complete"] is True

    @pytest.mark.asyncio
    async def test_returns_completion_message_on_last_step(self):
        start = await call_tool("run_sop_creation_guide")
        total = start["total_steps"]
        result = await call_tool("run_sop_creation_guide", {"current_step": total})
        assert "message" in result
        assert "completed" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_error_for_step_beyond_total(self):
        start = await call_tool("run_sop_creation_guide")
        total = start["total_steps"]
        result = await call_tool("run_sop_creation_guide", {"current_step": total + 1})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_error_for_invalid_step_zero(self):
        result = await call_tool("run_sop_creation_guide", {"current_step": 0})
        assert "error" in result


class TestSopToolVersionParameter:
    """Tests for the optional version parameter."""

    @pytest.mark.asyncio
    async def test_defaults_to_latest_version(self):
        result = await call_tool("run_sop_creation_guide")
        assert "sop_version" in result
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_explicit_version_returns_matching_sop(self):
        result = await call_tool("run_sop_creation_guide", {"version": "1.0"})
        assert result["sop_version"] == "1.0"

    @pytest.mark.asyncio
    async def test_invalid_version_returns_error(self):
        result = await call_tool("run_sop_creation_guide", {"version": "99.99.99"})
        assert "error" in result
        assert "99.99.99" in result["error"]

    @pytest.mark.asyncio
    async def test_version_with_step_navigation(self):
        result = await call_tool("run_sop_creation_guide", {"version": "1.0", "current_step": 1})
        assert result["sop_version"] == "1.0"
        assert result["current_step"] == 2


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis)
# ---------------------------------------------------------------------------

# --- Strategies ---

# Segment for SOP Document IDs: lowercase alpha start, then lowercase alphanumeric
_id_segment = st.text(
    alphabet=string.ascii_lowercase + string.digits,
    min_size=1,
    max_size=8,
).filter(lambda s: s[0].isalpha())

# Document ID: at least 3 underscore-separated segments (matches [a-z][a-z0-9]*(?:_[a-z0-9]+){2,})
sop_doc_id = st.tuples(
    _id_segment,
    _id_segment,
    _id_segment,
    st.lists(_id_segment, min_size=0, max_size=2),
).map(lambda t: "_".join([t[0], t[1], t[2]] + t[3]))

# Random tool names for step content
_tool_name = st.text(
    alphabet=string.ascii_lowercase + "_",
    min_size=2,
    max_size=15,
).filter(lambda s: s[0].isalpha() and not s.endswith("_"))


def _build_sop_with_tool_refs_no_prereqs(doc_id: str, tool_name: str) -> str:
    """Build valid SOP content with a tool reference in a step but NO Required MCP Servers field."""
    return (
        "# Test SOP With Tool Refs\n\n"
        "## Document Information\n"
        f"- **Document ID**: {doc_id}\n\n"
        "## Overview\n\nThis SOP tests tool reference detection.\n\n"
        f"### Step 1: Use the tool\n\n"
        f"Use the `{tool_name}` tool to perform the action.\n"
    )


# Feature: sop-prerequisites-mcp-servers, Property 2: Missing MCP Server Prerequisites Produces Warning
# Validates: Requirements 2.1, 2.3
@settings(max_examples=100, deadline=None)
@given(
    doc_id=sop_doc_id,
    tool_name=_tool_name,
)
@pytest.mark.asyncio
async def test_property_missing_mcp_server_prerequisites_produces_warning(
    doc_id: str,
    tool_name: str,
) -> None:
    """For any valid SOP content that contains tool-referencing patterns in its
    steps but does not contain a **Required MCP Servers** field, publishing via
    publish_sop should return success: True with a warning mentioning
    'Required MCP Servers'.

    **Validates: Requirements 2.1, 2.3**
    """
    content = _build_sop_with_tool_refs_no_prereqs(doc_id, tool_name)
    sop_dir = BUNDLED_SOPS_DIR / doc_id
    try:
        result = await call_tool("publish_sop", {"content": content})
        # SHOULD-level: publish succeeds (Req 2.3)
        assert result.get("success") is True, f"Expected success=True, got {result}"
        # Warning about missing MCP server prerequisites is present (Req 2.1)
        warning = result.get("warning", "")
        assert "Required MCP Servers" in warning, (
            f"Expected warning mentioning 'Required MCP Servers', got: {warning!r}"
        )
    finally:
        # Clean up the created SOP files
        if sop_dir.exists():
            shutil.rmtree(sop_dir)

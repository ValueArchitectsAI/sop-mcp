"""Unit tests for the SOP MCP Server tools.

Tests the server.py implementation including:
- Dynamic SOP tool registration (tool names derived from folder name)
- SOP tool functionality (start, continue, and version selection)
"""

from __future__ import annotations

import json

import pytest

from src.server import mcp


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

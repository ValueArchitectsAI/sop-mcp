"""End-to-end tests for the SOP MCP server via direct MCP calls.

Exercises the full MCP server object — tools, resources, and workflows.
"""

from __future__ import annotations

import json

import pytest

from src.sop_mcp.server import backend, mcp
from src.sop_mcp.utils import SOP

pytestmark = pytest.mark.asyncio

SOP_NAME = "sop_creation_guide"


async def _call_tool(tool_name: str, arguments: dict | None = None) -> dict:
    """Call a tool on the mcp server and return the parsed JSON result."""
    result = await mcp.call_tool(tool_name, arguments or {})
    return json.loads(result) if isinstance(result, str) else result


def _get_total_steps(sop_name: str = SOP_NAME) -> int:
    content = backend.read_sop(sop_name)
    return SOP.from_content(content).total_steps


# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------


class TestToolDiscovery:
    async def test_lists_core_tools(self):
        tools = await mcp.list_tools()
        names = [t.name for t in tools]
        assert "run_sop" in names
        assert "publish_sop" in names
        assert "submit_sop_feedback" in names

    async def test_no_per_sop_run_tools(self):
        tools = await mcp.list_tools()
        names = [t.name for t in tools]
        per_sop = [n for n in names if n.startswith("run_") and n != "run_sop"]
        assert per_sop == []


# ---------------------------------------------------------------------------
# Resource discovery and reading
# ---------------------------------------------------------------------------


class TestResourceDiscovery:
    async def test_list_resources_includes_sop_creation_guide(self):
        resources = await mcp.list_resources()
        uris = [str(r.uri) for r in resources]
        assert f"sop://{SOP_NAME}" in uris

    async def test_list_resources_has_markdown_mime_type(self):
        resources = await mcp.list_resources()
        sop_res = next(r for r in resources if str(r.uri) == f"sop://{SOP_NAME}")
        assert sop_res.mimeType == "text/markdown"

    async def test_list_resources_description_contains_overview(self):
        resources = await mcp.list_resources()
        sop_res = next(r for r in resources if str(r.uri) == f"sop://{SOP_NAME}")
        assert "RFC 2119" in sop_res.description


class TestReadResource:
    async def test_read_sop_creation_guide_latest(self):
        content = await mcp.read_resource(f"sop://{SOP_NAME}")
        assert "# Standard Operating Procedure" in str(content)
        assert "Step 1" in str(content)


# ---------------------------------------------------------------------------
# submit_sop_feedback
# ---------------------------------------------------------------------------


class TestSubmitFeedback:
    async def test_submit_feedback_success(self):
        data = await _call_tool(
            "submit_sop_feedback",
            {"sop_name": SOP_NAME, "feedback": "E2E test feedback — please ignore."},
        )
        assert data["success"] is True
        assert data["sop_name"] == SOP_NAME
        assert "timestamp" in data

    async def test_submit_feedback_unknown_sop(self):
        with pytest.raises(Exception):
            await _call_tool(
                "submit_sop_feedback",
                {"sop_name": "nonexistent_sop", "feedback": "should fail"},
            )


# ---------------------------------------------------------------------------
# Full SOP workflow run-through
# ---------------------------------------------------------------------------


class TestSopWorkflowRunThrough:
    async def test_full_walkthrough(self):
        total = _get_total_steps()
        assert total > 1

        data = await _call_tool("run_sop", {"sop_name": SOP_NAME})
        assert "instruction" in data

        for step in range(1, total):
            data = await _call_tool(
                "run_sop",
                {"sop_name": SOP_NAME, "current_step": step, "step_output": f"Output for step {step}"},
            )
            assert "instruction" in data

        data = await _call_tool(
            "run_sop",
            {"sop_name": SOP_NAME, "current_step": total, "step_output": f"Output for step {total}"},
        )
        assert "complete" in data["instruction"].lower()

    async def test_walkthrough_with_explicit_version(self):
        data = await _call_tool("run_sop", {"sop_name": SOP_NAME, "version": 1})
        assert data["sop_version"] == 1

        total = _get_total_steps()
        data = await _call_tool(
            "run_sop",
            {"sop_name": SOP_NAME, "version": 1, "current_step": total, "step_output": "Final"},
        )
        assert "complete" in data["instruction"].lower()
        assert data["sop_version"] == 1

    async def test_invalid_step_returns_error(self):
        with pytest.raises(Exception):
            await _call_tool("run_sop", {"sop_name": SOP_NAME, "current_step": -1, "step_output": "test"})

    async def test_step_beyond_total_returns_error(self):
        total = _get_total_steps()
        with pytest.raises(Exception):
            await _call_tool("run_sop", {"sop_name": SOP_NAME, "current_step": total + 1, "step_output": "test"})

    async def test_unknown_sop_returns_error(self):
        with pytest.raises(Exception):
            await _call_tool("run_sop", {"sop_name": "nonexistent_sop"})

    async def test_run_sop_start_without_step_output(self):
        data = await _call_tool("run_sop", {"sop_name": SOP_NAME})
        assert data["current_step"] == 0
        assert "instruction" in data

    async def test_run_sop_continue_requires_step_output(self):
        with pytest.raises(Exception):
            await _call_tool("run_sop", {"sop_name": SOP_NAME, "current_step": 1})

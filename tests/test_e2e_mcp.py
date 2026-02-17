"""End-to-end tests for the SOP MCP server via in-memory transport.

Uses FastMCP's in-memory Client to exercise the full MCP protocol stack
against the real server object — no subprocess, no network, same coverage.
"""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from fastmcp import Client

from src.server import mcp

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client():
    """Yield an in-memory MCP client connected to the real server."""
    async with Client(mcp) as c:
        yield c


async def _call(client: Client, tool_name: str, arguments: dict | None = None) -> dict:
    """Call a tool and return the parsed JSON result."""
    result = await client.call_tool(tool_name, arguments or {})
    assert not result.is_error, f"Tool {tool_name} returned an error: {result}"
    return json.loads(result.content[0].text)


# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------


class TestToolDiscovery:
    async def test_lists_core_tools(self, client):
        tools = await client.list_tools()
        names = [t.name for t in tools]
        assert "explain_sop" in names
        assert "publish_sop" in names
        assert "submit_sop_feedback" in names

    async def test_lists_dynamic_run_tools(self, client):
        tools = await client.list_tools()
        names = [t.name for t in tools]
        run_tools = [n for n in names if n.startswith("run_")]
        assert len(run_tools) > 0, "Expected at least one dynamic run_ tool"
        assert "run_sop_creation_guide" in names


# ---------------------------------------------------------------------------
# explain_sop
# ---------------------------------------------------------------------------


class TestExplainSop:
    async def test_list_all_sops(self, client):
        data = await _call(client, "explain_sop")
        assert "available_sops" in data
        assert data["total"] > 0
        names = [s["name"] for s in data["available_sops"]]
        assert "sop_creation_guide" in names

    async def test_explain_specific_sop(self, client):
        data = await _call(client, "explain_sop", {"sop_name": "sop_creation_guide"})
        assert data["sop_name"] == "sop_creation_guide"
        assert "title" in data
        assert "overview" in data
        assert data["total_steps"] > 0
        assert isinstance(data["steps"], list)

    async def test_explain_unknown_sop_returns_error(self, client):
        data = await _call(client, "explain_sop", {"sop_name": "does_not_exist"})
        assert "error" in data


# ---------------------------------------------------------------------------
# submit_sop_feedback
# ---------------------------------------------------------------------------


class TestSubmitFeedback:
    async def test_submit_feedback_success(self, client):
        data = await _call(
            client,
            "submit_sop_feedback",
            {"sop_name": "sop_creation_guide", "feedback": "E2E test feedback — please ignore."},
        )
        assert data["success"] is True
        assert data["sop_name"] == "sop_creation_guide"
        assert "timestamp" in data

    async def test_submit_feedback_unknown_sop(self, client):
        data = await _call(
            client,
            "submit_sop_feedback",
            {"sop_name": "nonexistent_sop", "feedback": "should fail"},
        )
        assert "error" in data


# ---------------------------------------------------------------------------
# Full SOP workflow run-through
# ---------------------------------------------------------------------------


class TestSopWorkflowRunThrough:
    async def test_full_walkthrough(self, client):
        info = await _call(client, "explain_sop", {"sop_name": "sop_creation_guide"})
        total = info["total_steps"]
        assert total > 1, "SOP should have multiple steps"

        data = await _call(client, "run_sop_creation_guide")
        assert "instruction" in data
        assert "Step 1" in data["instruction"]

        for step in range(1, total):
            data = await _call(client, "run_sop_creation_guide", {"current_step": step})
            assert "instruction" in data

        data = await _call(client, "run_sop_creation_guide", {"current_step": total})
        assert "All steps complete" in data["instruction"]

    async def test_walkthrough_with_explicit_version(self, client):
        data = await _call(client, "run_sop_creation_guide", {"version": "1.0"})
        assert data["sop_version"] == "1.0"
        assert "instruction" in data

        info = await _call(client, "explain_sop", {"sop_name": "sop_creation_guide"})
        total = info["total_steps"]
        data = await _call(client, "run_sop_creation_guide", {"version": "1.0", "current_step": total})
        assert "All steps complete" in data["instruction"]
        assert data["sop_version"] == "1.0"

    async def test_invalid_step_returns_error(self, client):
        data = await _call(client, "run_sop_creation_guide", {"current_step": 0})
        assert "error" in data

    async def test_step_beyond_total_returns_error(self, client):
        info = await _call(client, "explain_sop", {"sop_name": "sop_creation_guide"})
        total = info["total_steps"]
        data = await _call(client, "run_sop_creation_guide", {"current_step": total + 1})
        assert "error" in data

    async def test_invalid_version_returns_error(self, client):
        data = await _call(client, "run_sop_creation_guide", {"version": "99.99"})
        assert "error" in data

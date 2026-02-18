"""End-to-end tests for the SOP MCP server via in-memory transport.

Uses FastMCP's in-memory Client to exercise the full MCP protocol stack
against the real server object — no subprocess, no network, same coverage.
"""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from fastmcp import Client

from src.server import backend, mcp
from src.utils import SOP

pytestmark = pytest.mark.asyncio

SOP_NAME = "sop_creation_guide"


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


def _get_total_steps(sop_name: str = SOP_NAME) -> int:
    """Get total steps for an SOP directly from the backend."""
    content = backend.read_sop(sop_name)
    return SOP.from_content(content).total_steps


# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------


class TestToolDiscovery:
    async def test_lists_core_tools(self, client):
        tools = await client.list_tools()
        names = [t.name for t in tools]
        assert "run_sop" in names
        assert "publish_sop" in names
        assert "submit_sop_feedback" in names

    async def test_no_per_sop_run_tools(self, client):
        tools = await client.list_tools()
        names = [t.name for t in tools]
        per_sop = [
            n for n in names if n.startswith("run_") and n not in ("run_sop", "run_sop_with_context", "run_sop_strict")
        ]
        assert per_sop == [], f"Expected no per-SOP run_ tools, found: {per_sop}"


# ---------------------------------------------------------------------------
# Resource discovery and reading
# ---------------------------------------------------------------------------


class TestResourceDiscovery:
    async def test_list_resources_includes_sop_creation_guide(self, client):
        resources = await client.list_resources()
        uris = [str(r.uri) for r in resources]
        assert f"sop://{SOP_NAME}" in uris

    async def test_list_resources_has_markdown_mime_type(self, client):
        resources = await client.list_resources()
        sop_res = next(r for r in resources if str(r.uri) == f"sop://{SOP_NAME}")
        assert sop_res.mimeType == "text/markdown"

    async def test_list_resources_description_contains_overview(self, client):
        resources = await client.list_resources()
        sop_res = next(r for r in resources if str(r.uri) == f"sop://{SOP_NAME}")
        assert "Standard Operating Procedure" in sop_res.description

    async def test_list_resource_templates_includes_versioned(self, client):
        templates = await client.list_resource_templates()
        uri_templates = [str(t.uriTemplate) for t in templates]
        assert any("sop_name" in t for t in uri_templates)


class TestReadResource:
    async def test_read_sop_creation_guide_latest(self, client):
        content = await client.read_resource(f"sop://{SOP_NAME}")
        text = content[0].content if hasattr(content[0], "content") else str(content[0])
        assert "# Standard Operating Procedure" in text
        assert "Step 1" in text

    async def test_read_sop_creation_guide_specific_version(self, client):
        content = await client.read_resource(f"sop://{SOP_NAME}?version=1.0")
        text = content[0].content if hasattr(content[0], "content") else str(content[0])
        assert "# Standard Operating Procedure" in text
        assert "Version**: 1.0" in text

    async def test_read_sop_creation_guide_invalid_version(self, client):
        with pytest.raises(Exception):
            await client.read_resource(f"sop://{SOP_NAME}?version=99.99")


# ---------------------------------------------------------------------------
# submit_sop_feedback
# ---------------------------------------------------------------------------


class TestSubmitFeedback:
    async def test_submit_feedback_success(self, client):
        data = await _call(
            client,
            "submit_sop_feedback",
            {"sop_name": SOP_NAME, "feedback": "E2E test feedback — please ignore."},
        )
        assert data["success"] is True
        assert data["sop_name"] == SOP_NAME
        assert "timestamp" in data

    async def test_submit_feedback_unknown_sop(self, client):
        result = await client.call_tool(
            "submit_sop_feedback",
            {"sop_name": "nonexistent_sop", "feedback": "should fail"},
            raise_on_error=False,
        )
        assert result.is_error


# ---------------------------------------------------------------------------
# Full SOP workflow run-through
# ---------------------------------------------------------------------------


class TestSopWorkflowRunThrough:
    async def test_full_walkthrough(self, client):
        total = _get_total_steps()
        assert total > 1, "SOP should have multiple steps"

        # Start with run_sop
        data = await _call(client, "run_sop", {"sop_name": SOP_NAME})
        assert "instruction" in data

        # Continue with run_sop_strict
        for step in range(1, total):
            data = await _call(
                client,
                "run_sop_strict",
                {
                    "sop_name": SOP_NAME,
                    "current_step": step,
                    "step_output": f"Output for step {step}",
                    "previous_outputs": data.get("previous_outputs", {}),
                },
            )
            assert "instruction" in data

        # Complete
        data = await _call(
            client,
            "run_sop_strict",
            {
                "sop_name": SOP_NAME,
                "current_step": total,
                "step_output": f"Output for step {total}",
                "previous_outputs": data.get("previous_outputs", {}),
            },
        )
        assert "instruction" in data
        assert "complete" in data["instruction"].lower()
        assert "previous_outputs" in data

    async def test_walkthrough_with_explicit_version(self, client):
        data = await _call(client, "run_sop", {"sop_name": SOP_NAME, "version": "1.0"})
        assert data["sop_version"] == "1.0"
        assert "instruction" in data

        total = _get_total_steps()
        data = await _call(
            client,
            "run_sop_strict",
            {
                "sop_name": SOP_NAME,
                "version": "1.0",
                "current_step": total,
                "step_output": "Final output",
                "previous_outputs": {},
            },
        )
        assert "instruction" in data
        assert "complete" in data["instruction"].lower()
        assert data["sop_version"] == "1.0"

    async def test_invalid_step_returns_error(self, client):
        result = await client.call_tool(
            "run_sop_strict",
            {
                "sop_name": SOP_NAME,
                "current_step": -1,
                "step_output": "test",
                "previous_outputs": {},
            },
            raise_on_error=False,
        )
        assert result.is_error

    async def test_step_beyond_total_returns_error(self, client):
        total = _get_total_steps()
        result = await client.call_tool(
            "run_sop_with_context",
            {
                "sop_name": SOP_NAME,
                "current_step": total + 1,
                "step_output": "test",
                "previous_outputs": {},
            },
            raise_on_error=False,
        )
        assert result.is_error

    async def test_invalid_version_returns_error(self, client):
        result = await client.call_tool("run_sop", {"sop_name": SOP_NAME, "version": "99.99"}, raise_on_error=False)
        assert result.is_error

    async def test_unknown_sop_returns_error(self, client):
        result = await client.call_tool("run_sop", {"sop_name": "nonexistent_sop"}, raise_on_error=False)
        assert result.is_error

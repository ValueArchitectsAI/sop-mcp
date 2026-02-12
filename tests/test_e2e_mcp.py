"""End-to-end tests for the SOP MCP server over stdio transport.

Spawns the real MCP server as a subprocess via `uv run sop-mcp`,
connects an MCP ClientSession, and exercises the tools through the
full protocol stack: explain, feedback, and a complete SOP run-through.
"""

import json
import shutil

import pytest
import pytest_asyncio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# All tests in this module share one event loop + one server process.
pytestmark = pytest.mark.asyncio(loop_scope="module")

UV_BIN = shutil.which("uv")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def session():
    """Start the MCP server subprocess and yield an initialised ClientSession.

    The outer try/except suppresses a harmless RuntimeError raised by anyio
    during fixture teardown — the cancel-scope that ``stdio_client`` creates
    is torn down in a different task than the one pytest-asyncio uses for
    cleanup.  All actual test assertions are unaffected.
    """
    assert UV_BIN is not None, "uv binary not found on PATH"

    server_params = StdioServerParameters(
        command=UV_BIN,
        args=["run", "sop-mcp"],
    )

    try:
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as client:
                await client.initialize()
                yield client
    except (RuntimeError, BaseExceptionGroup):
        # anyio raises "Attempted to exit cancel scope in a different task"
        # during teardown — safe to ignore, the subprocess is already gone.
        pass


async def _call(client: ClientSession, tool_name: str, arguments: dict | None = None) -> dict:
    """Call a tool and return the parsed JSON result."""
    result = await client.call_tool(tool_name, arguments or {})
    assert not result.isError, f"Tool {tool_name} returned an error: {result.content}"
    return json.loads(result.content[0].text)


# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------


class TestToolDiscovery:
    """Verify the server exposes the expected tools over the wire."""

    async def test_lists_core_tools(self, session):
        result = await session.list_tools()
        names = [t.name for t in result.tools]
        assert "explain_sop" in names
        assert "publish_sop" in names
        assert "submit_sop_feedback" in names

    async def test_lists_dynamic_run_tools(self, session):
        result = await session.list_tools()
        names = [t.name for t in result.tools]
        run_tools = [n for n in names if n.startswith("run_")]
        assert len(run_tools) > 0, "Expected at least one dynamic run_ tool"
        assert "run_authoring_new_sop" in names


# ---------------------------------------------------------------------------
# explain_sop
# ---------------------------------------------------------------------------


class TestExplainSop:
    """E2E tests for the explain_sop tool."""

    async def test_list_all_sops(self, session):
        data = await _call(session, "explain_sop")
        assert "available_sops" in data
        assert data["total"] > 0
        names = [s["name"] for s in data["available_sops"]]
        assert "authoring_new_sop" in names

    async def test_explain_specific_sop(self, session):
        data = await _call(session, "explain_sop", {"sop_name": "authoring_new_sop"})
        assert data["sop_name"] == "authoring_new_sop"
        assert "title" in data
        assert "overview" in data
        assert data["total_steps"] > 0
        assert isinstance(data["steps"], list)

    async def test_explain_unknown_sop_returns_error(self, session):
        data = await _call(session, "explain_sop", {"sop_name": "does_not_exist"})
        assert "error" in data


# ---------------------------------------------------------------------------
# submit_sop_feedback
# ---------------------------------------------------------------------------


class TestSubmitFeedback:
    """E2E tests for the submit_sop_feedback tool."""

    async def test_submit_feedback_success(self, session):
        data = await _call(
            session,
            "submit_sop_feedback",
            {"sop_name": "authoring_new_sop", "feedback": "E2E test feedback — please ignore."},
        )
        assert data["success"] is True
        assert data["sop_name"] == "authoring_new_sop"
        assert "timestamp" in data

    async def test_submit_feedback_unknown_sop(self, session):
        data = await _call(
            session,
            "submit_sop_feedback",
            {"sop_name": "nonexistent_sop", "feedback": "should fail"},
        )
        assert "error" in data


# ---------------------------------------------------------------------------
# Full SOP workflow run-through
# ---------------------------------------------------------------------------


class TestSopWorkflowRunThrough:
    """Walk through an entire SOP from start to completion over the wire."""

    async def test_full_walkthrough(self, session):
        """Start the authoring SOP, step through every step, and verify completion."""
        # Start (returns step 1)
        data = await _call(session, "run_authoring_new_sop")
        assert data["current_step"] == 1
        assert "step_content" in data
        total = data["total_steps"]
        assert total > 1, "SOP should have multiple steps"

        # Walk through remaining steps
        for step in range(1, total):
            data = await _call(session, "run_authoring_new_sop", {"current_step": step})
            assert data["current_step"] == step + 1
            assert "step_content" in data

            if step + 1 < total:
                assert data["is_complete"] is False

        # Final step should be marked complete
        assert data["is_complete"] is True
        assert "message" in data
        assert "completed" in data["message"].lower()

    async def test_walkthrough_with_explicit_version(self, session):
        """Run through the SOP while pinning a specific version."""
        data = await _call(session, "run_authoring_new_sop", {"version": "1.0"})
        assert data["sop_version"] == "1.0"
        assert data["current_step"] == 1

        total = data["total_steps"]
        # Jump straight to the last step
        data = await _call(session, "run_authoring_new_sop", {"version": "1.0", "current_step": total})
        assert data["is_complete"] is True
        assert data["sop_version"] == "1.0"

    async def test_invalid_step_returns_error(self, session):
        data = await _call(session, "run_authoring_new_sop", {"current_step": 0})
        assert "error" in data

    async def test_step_beyond_total_returns_error(self, session):
        start = await _call(session, "run_authoring_new_sop")
        total = start["total_steps"]
        data = await _call(session, "run_authoring_new_sop", {"current_step": total + 1})
        assert "error" in data

    async def test_invalid_version_returns_error(self, session):
        data = await _call(session, "run_authoring_new_sop", {"version": "99.99"})
        assert "error" in data

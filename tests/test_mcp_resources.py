"""Tests for MCP resource discovery and reading.

Each test spawns sop-mcp as a subprocess and connects via FastMCP Client.
Full MCP protocol over stdio — no mocking, no in-process shortcuts.

Best practices:
- Single behavior per test
- Self-contained — each test opens its own client
- Clear intent — test name describes the verified behavior
"""

from __future__ import annotations

import json

from fastmcp import Client

# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------


async def test_core_tools_registered(mcp_transport):
    """Server exposes run_sop, publish_sop, submit_sop_feedback tools."""
    async with Client(mcp_transport) as client:
        tools = await client.list_tools()
        names = [t.name for t in tools]
        assert "run_sop" in names
        assert "publish_sop" in names
        assert "submit_sop_feedback" in names


async def test_list_resources_tool_registered(mcp_transport):
    """Server exposes list_resources and read_resource as tools."""
    async with Client(mcp_transport) as client:
        tools = await client.list_tools()
        names = [t.name for t in tools]
        assert "list_resources" in names
        assert "read_resource" in names


# ---------------------------------------------------------------------------
# Resource discovery
# ---------------------------------------------------------------------------


async def test_list_resources_includes_bundled_sop(mcp_transport):
    """Bundled sop_creation_guide appears in resource list."""
    async with Client(mcp_transport) as client:
        resources = await client.list_resources()
        uris = [str(r.uri) for r in resources]
        assert "sop://sop_creation_guide" in uris


async def test_resources_have_markdown_mime(mcp_transport):
    """SOP resources have text/markdown MIME type."""
    async with Client(mcp_transport) as client:
        resources = await client.list_resources()
        sop = next(
            r for r in resources if "sop_creation_guide" in str(r.uri) and "/" not in str(r.uri).replace("sop://", "")
        )
        assert sop.mimeType == "text/markdown"


async def test_resources_have_description(mcp_transport):
    """SOP resources have a non-empty description."""
    async with Client(mcp_transport) as client:
        resources = await client.list_resources()
        sop = next(r for r in resources if str(r.uri) == "sop://sop_creation_guide")
        assert len(sop.description) > 0


async def test_resources_description_includes_parameters(mcp_transport):
    """SOP resources expose the `## Parameters` block inside the MCP description.

    The agent browses `resources/list` when deciding which SOP to read.
    Serving the parameters alongside the overview lets the agent see
    both "what this SOP does" and "what inputs it takes" without
    opening the resource first.
    """
    async with Client(mcp_transport) as client:
        resources = await client.list_resources()
        sop = next(r for r in resources if str(r.uri) == "sop://sop_creation_guide")
        assert "## Parameters" in sop.description
        # sop_creation_guide declares process_name and process_owner.
        assert "process_name" in sop.description
        assert "process_owner" in sop.description


# ---------------------------------------------------------------------------
# Resource reading
# ---------------------------------------------------------------------------


async def test_read_resource_returns_sop_content(mcp_transport):
    """Reading an SOP resource returns its markdown content."""
    async with Client(mcp_transport) as client:
        content = await client.read_resource("sop://sop_creation_guide")
        text = str(content)
        assert "### 1." in text


# ---------------------------------------------------------------------------
# Resource tools (list_resources / read_resource as tools)
# ---------------------------------------------------------------------------


async def test_list_resources_tool_returns_sops(mcp_transport):
    """The list_resources tool returns SOP URIs."""
    async with Client(mcp_transport) as client:
        result = await client.call_tool("list_resources", {})
        data = json.loads(result.content[0].text)
        uris = [r["uri"] for r in data["resources"]]
        assert "sop://sop_creation_guide" in uris


async def test_read_resource_tool_returns_content(mcp_transport):
    """The read_resource tool returns SOP content."""
    async with Client(mcp_transport) as client:
        result = await client.call_tool("read_resource", {"uri": "sop://sop_creation_guide"})
        data = json.loads(result.content[0].text)
        assert "### 1." in data["content"]


async def test_read_resource_tool_unknown_uri_errors(mcp_transport):
    """The read_resource tool errors with a message about using list_resources."""
    import pytest
    from fastmcp.exceptions import ToolError

    async with Client(mcp_transport) as client:
        with pytest.raises(ToolError, match="Unknown resource URI"):
            await client.call_tool("read_resource", {"uri": "sop://nonexistent"})


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------


async def test_feedback_not_listed_as_resource(mcp_transport):
    """Feedback files are hidden from list_resources."""
    async with Client(mcp_transport) as client:
        content = (
            "---\n"
            "name: hidden_fb_sop\n"
            "version: 1\n"
            "owner: tests\n"
            "stage: preprod\n"
            "---\n\n"
            "# Hidden FB\n\n"
            "## Overview\n\nTest fixture for resource listing.\n\n"
            "## Parameters\n\n- **x** (required): x.\n\n"
            "## Steps\n\n"
            "### 1. Do\n\n"
            "Action body.\n\n"
            "**Constraints:**\n"
            "- You MUST act\n\n"
            "**Expected Output:** Action completed.\n"
        )
        await client.call_tool("publish_sop", {"content": content, "stage": "preprod"})
        await client.call_tool(
            "submit_sop_feedback",
            {"sop_name": "hidden_fb_sop", "feedback": "Should not appear."},
        )
        # Re-publish to trigger resource refresh.
        await client.call_tool("publish_sop", {"content": content, "stage": "preprod"})

        result = await client.call_tool("list_resources", {})
        data = json.loads(result.content[0].text)
        uris = [r["uri"] for r in data["resources"]]
        assert not any("feedback.jsonl" in uri for uri in uris), "feedback.jsonl should be hidden"

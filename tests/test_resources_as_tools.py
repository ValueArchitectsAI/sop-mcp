"""Tests that SOP resources are available both as MCP resources AND as tools.

Validates that clients without resource protocol support can still
discover and read SOPs via the list_resources and read_resource tools.
"""

from __future__ import annotations

import json

import pytest

from src.sop_mcp.server import mcp

pytestmark = pytest.mark.asyncio

SOP_NAME = "sop_creation_guide"


async def _call_tool(name: str, arguments: dict | None = None) -> dict:
    result = await mcp.call_tool(name, arguments or {})
    return json.loads(result) if isinstance(result, str) else result


# ---------------------------------------------------------------------------
# Resources available via resource protocol
# ---------------------------------------------------------------------------


class TestResourceProtocol:
    async def test_sop_available_as_resource(self):
        resources = await mcp.list_resources()
        uris = [str(r.uri) for r in resources]
        assert f"sop://{SOP_NAME}" in uris

    async def test_resource_readable(self):
        content = await mcp.read_resource(f"sop://{SOP_NAME}")
        assert "Step 1" in str(content)


# ---------------------------------------------------------------------------
# Resources available via tool protocol (for clients without resource support)
# ---------------------------------------------------------------------------


class TestListResourcesTool:
    async def test_list_resources_tool_registered(self):
        tools = await mcp.list_tools()
        names = [t.name for t in tools]
        assert "list_resources" in names

    async def test_list_resources_tool_returns_sops(self):
        data = await _call_tool("list_resources")
        assert "resources" in data
        uris = [r["uri"] for r in data["resources"]]
        assert f"sop://{SOP_NAME}" in uris

    async def test_list_resources_tool_has_description(self):
        data = await _call_tool("list_resources")
        sop = next(r for r in data["resources"] if r["uri"] == f"sop://{SOP_NAME}")
        assert len(sop["description"]) > 0

    async def test_list_resources_tool_has_mime_type(self):
        data = await _call_tool("list_resources")
        sop = next(r for r in data["resources"] if r["uri"] == f"sop://{SOP_NAME}")
        assert sop["mimeType"] == "text/markdown"


class TestReadResourceTool:
    async def test_read_resource_tool_registered(self):
        tools = await mcp.list_tools()
        names = [t.name for t in tools]
        assert "read_resource" in names

    async def test_read_resource_tool_returns_content(self):
        data = await _call_tool("read_resource", {"uri": f"sop://{SOP_NAME}"})
        assert "content" in data
        assert "Step 1" in data["content"]
        assert data["mimeType"] == "text/markdown"

    async def test_read_resource_tool_unknown_uri_raises(self):
        with pytest.raises(Exception):
            await _call_tool("read_resource", {"uri": "sop://nonexistent"})


# ---------------------------------------------------------------------------
# Consistency: tool and resource return same data
# ---------------------------------------------------------------------------


class TestConsistency:
    async def test_tool_and_resource_list_same_sops(self):
        resources = await mcp.list_resources()
        resource_uris = sorted(str(r.uri) for r in resources)

        tool_data = await _call_tool("list_resources")
        tool_uris = sorted(r["uri"] for r in tool_data["resources"])

        assert resource_uris == tool_uris

    async def test_tool_and_resource_read_same_content(self):
        resource_content = await mcp.read_resource(f"sop://{SOP_NAME}")
        tool_data = await _call_tool("read_resource", {"uri": f"sop://{SOP_NAME}"})

        assert str(resource_content) in tool_data["content"] or tool_data["content"] in str(resource_content)

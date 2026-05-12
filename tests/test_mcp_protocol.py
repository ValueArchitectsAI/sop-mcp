"""MCP protocol conformance tests.

Starts the server as a real subprocess over stdio and validates
that it speaks valid JSON-RPC 2.0 / MCP protocol.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

PROTOCOL_VERSION = "2025-06-18"


def _send_receive(messages: list[dict]) -> list[dict]:
    """Send JSON-RPC messages to the server via stdin, collect responses from stdout.

    Uses an isolated temp storage dir so stale or user-specific SOPs in
    ``~/.sop_mcp`` don't leak into the protocol conformance tests.
    """
    input_lines = "\n".join(json.dumps(m) for m in messages) + "\n"
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "SOP_STORAGE_DIR": tmp}
        result = subprocess.run(
            [sys.executable, "-c", "from src.sop_mcp.server import run; run()"],
            input=input_lines,
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
    responses = []
    for line in result.stdout.strip().splitlines():
        if line.strip():
            responses.append(json.loads(line))
    return responses


def _init_and_send(requests: list[dict]) -> list[dict]:
    """Send initialize + initialized + requests, return only request responses."""
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        *requests,
    ]
    responses = _send_receive(messages)
    # First response is initialize, skip it
    return responses[1:] if len(responses) > 1 else responses


class TestMCPInitialize:
    def test_initialize_returns_protocol_version(self):
        responses = _send_receive(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1.0"},
                    },
                },
            ]
        )
        assert len(responses) == 1
        r = responses[0]
        assert r["jsonrpc"] == "2.0"
        assert r["id"] == 1
        assert "result" in r
        assert r["result"]["protocolVersion"] == PROTOCOL_VERSION

    def test_initialize_returns_capabilities(self):
        responses = _send_receive(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1.0"},
                    },
                },
            ]
        )
        caps = responses[0]["result"]["capabilities"]
        assert "tools" in caps

    def test_initialize_returns_server_info(self):
        responses = _send_receive(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1.0"},
                    },
                },
            ]
        )
        info = responses[0]["result"]["serverInfo"]
        assert "name" in info
        assert info["name"] == "SOP MCP Server"


class TestMCPToolsList:
    def test_tools_list_returns_tools_array(self):
        responses = _init_and_send(
            [
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            ]
        )
        assert len(responses) >= 1
        r = responses[0]
        assert "result" in r
        assert "tools" in r["result"]
        assert isinstance(r["result"]["tools"], list)

    def test_tools_have_required_fields(self):
        responses = _init_and_send(
            [
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            ]
        )
        tools = responses[0]["result"]["tools"]
        assert len(tools) >= 3  # run_sop, publish_sop, submit_sop_feedback
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    def test_core_tools_present(self):
        responses = _init_and_send(
            [
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            ]
        )
        names = [t["name"] for t in responses[0]["result"]["tools"]]
        assert "run_sop" in names
        assert "publish_sop" in names
        assert "submit_sop_feedback" in names


class TestMCPToolsCall:
    def test_tools_call_returns_content(self):
        responses = _init_and_send(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "run_sop",
                        "arguments": {"sop_name": "sop_creation_guide"},
                    },
                },
            ]
        )
        r = responses[0]
        assert "result" in r
        assert "content" in r["result"]
        content = r["result"]["content"]
        assert isinstance(content, list)
        assert content[0]["type"] == "text"
        data = json.loads(content[0]["text"])
        assert "sop_name" in data
        assert "instruction" in data

    def test_tools_call_error_returns_is_error(self):
        responses = _init_and_send(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "run_sop",
                        "arguments": {"sop_name": "nonexistent_sop_xyz"},
                    },
                },
            ]
        )
        r = responses[0]
        assert "result" in r
        assert r["result"].get("isError") is True

    def test_unknown_tool_returns_error(self):
        responses = _init_and_send(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "nonexistent_tool",
                        "arguments": {},
                    },
                },
            ]
        )
        r = responses[0]
        assert "error" in r


class TestMCPResourcesList:
    def test_resources_list_returns_array(self):
        responses = _init_and_send(
            [
                {"jsonrpc": "2.0", "id": 4, "method": "resources/list"},
            ]
        )
        r = responses[0]
        assert "result" in r
        assert "resources" in r["result"]
        assert isinstance(r["result"]["resources"], list)

    def test_resources_have_required_fields(self):
        responses = _init_and_send(
            [
                {"jsonrpc": "2.0", "id": 4, "method": "resources/list"},
            ]
        )
        resources = responses[0]["result"]["resources"]
        assert len(resources) >= 1
        for res in resources:
            assert "uri" in res
            assert "name" in res
            assert "mimeType" in res


class TestMCPResourcesRead:
    def test_resources_read_returns_contents(self):
        responses = _init_and_send(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "resources/read",
                    "params": {
                        "uri": "sop://sop_creation_guide",
                    },
                },
            ]
        )
        r = responses[0]
        assert "result" in r
        assert "contents" in r["result"]
        contents = r["result"]["contents"]
        assert len(contents) == 1
        assert contents[0]["mimeType"] == "text/markdown"
        assert "### 1." in contents[0]["text"]


class TestMCPPing:
    def test_ping_returns_empty_result(self):
        responses = _init_and_send(
            [
                {"jsonrpc": "2.0", "id": 99, "method": "ping"},
            ]
        )
        r = responses[0]
        assert r["id"] == 99
        assert r["result"] == {}


class TestMCPUnknownMethod:
    def test_unknown_method_returns_error(self):
        responses = _init_and_send(
            [
                {"jsonrpc": "2.0", "id": 100, "method": "foo/bar"},
            ]
        )
        r = responses[0]
        assert "error" in r
        assert r["error"]["code"] == -32601


class TestMCPPagination:
    """Pagination conformance for tools/list, resources/list, resources/templates/list.

    Per the spec (https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/pagination):
    - Cursors are opaque tokens; clients don't parse them
    - Missing ``nextCursor`` means last page
    - Invalid cursors SHOULD return -32602 (Invalid params)
    - Cursor + remaining-list must reconstruct the full set with no duplicates
    """

    def _list_with_cursor(self, method: str, cursor: str | None = None) -> dict:
        params = {"cursor": cursor} if cursor is not None else {}
        responses = _init_and_send(
            [
                {"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            ]
        )
        return responses[0]

    def test_invalid_cursor_rejected_with_invalid_params(self):
        """Bogus cursors surface as -32602 on every paginated endpoint."""
        for method in ("tools/list", "resources/list", "resources/templates/list"):
            r = self._list_with_cursor(method, cursor="not-a-real-cursor")
            assert "error" in r, f"{method} accepted invalid cursor: {r}"
            assert r["error"]["code"] == -32602, f"{method} wrong error code: {r['error']}"

    def test_tiny_page_exposes_next_cursor(self, monkeypatch):
        """Drop the page size to 1 to exercise a real cursor round-trip.

        The page size is read from ``SOP_MCP_PAGE_SIZE`` at request time
        on the server side. Setting the env var here propagates into the
        subprocess via ``_send_receive``'s ``{**os.environ, ...}`` copy.
        """
        monkeypatch.setenv("SOP_MCP_PAGE_SIZE", "1")

        # Page 1
        r1 = self._list_with_cursor("resources/list")
        assert "nextCursor" in r1["result"], "first page should advertise nextCursor"
        assert len(r1["result"]["resources"]) == 1
        uris_seen = {r["uri"] for r in r1["result"]["resources"]}

        # Walk subsequent pages
        cursor = r1["result"]["nextCursor"]
        pages = 1
        while cursor is not None and pages < 50:  # safety bound
            r = self._list_with_cursor("resources/list", cursor=cursor)
            items = r["result"]["resources"]
            for item in items:
                assert item["uri"] not in uris_seen, "duplicate URI across pages"
                uris_seen.add(item["uri"])
            cursor = r["result"].get("nextCursor")
            pages += 1

        # Final page MUST omit nextCursor
        assert cursor is None, "pagination never terminated"
        assert len(uris_seen) > 1, "only one page materialised"

    def test_empty_list_has_no_cursor(self):
        """resources/templates/list is empty — must not emit a cursor."""
        r = self._list_with_cursor("resources/templates/list")
        assert "nextCursor" not in r["result"]
        assert r["result"]["resourceTemplates"] == []

    def test_single_page_has_no_cursor(self):
        """When the full set fits in one page, no cursor is emitted."""
        # Default page size is 50; we have 5 resources — fits comfortably.
        r = self._list_with_cursor("resources/list")
        assert "nextCursor" not in r["result"]

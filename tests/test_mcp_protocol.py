"""MCP protocol conformance tests.

Starts the server as a real subprocess over stdio and validates
that it speaks valid JSON-RPC 2.0 / MCP protocol.
"""

from __future__ import annotations

import json
import subprocess
import sys

PROTOCOL_VERSION = "2024-11-05"


def _send_receive(messages: list[dict]) -> list[dict]:
    """Send JSON-RPC messages to the server via stdin, collect responses from stdout."""
    input_lines = "\n".join(json.dumps(m) for m in messages) + "\n"
    result = subprocess.run(
        [sys.executable, "-c", "from src.sop_mcp.server import run; run()"],
        input=input_lines,
        capture_output=True,
        text=True,
        timeout=10,
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
        assert "Step 1" in contents[0]["text"]


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

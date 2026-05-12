"""End-to-end tests for the hook system via MCP client.

Each test spawns sop-mcp with SOP_HOOK_CONFIG set, then verifies
hook side effects through real MCP tool calls over stdio.

Covers:
- Shell hooks: write a marker file, verify it exists after tool call
- LLM suggestion hooks: verify suggested_actions in tool response
- Hook triggers: run_sop, sop_completed, submit_sop_feedback, publish_sop
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_transport(tmp_path: Path, hook_config: str) -> StdioTransport:
    """Create a StdioTransport with SOP_HOOK_CONFIG and isolated storage."""
    return StdioTransport(
        command=sys.executable,
        args=["-c", "from src.sop_mcp.server import run; run()"],
        env={
            **os.environ,
            "SOP_STORAGE_DIR": str(tmp_path),
            "SOP_HOOK_CONFIG": hook_config,
            "SOP_HOOKS_SECURE": "false",  # allow touch commands in tests
        },
    )


def _shell_hook_config(marker_file: Path, event_type: str) -> str:
    """Build a shell hook config that creates a marker file on the given event.

    Uses /tmp for the marker to avoid security filter false positives
    from test function names in pytest tmp_path.
    """
    config = [
        {
            "event_type": event_type,
            "action_type": "shell",
            "payload": {
                "command": f"/usr/bin/touch {marker_file}",
                "timeout_seconds": 5,
            },
        }
    ]
    return json.dumps(config)


def _llm_hook_config(event_type: str) -> str:
    """Build an LLM suggestion hook config for the given event."""
    config = [
        {
            "event_type": event_type,
            "action_type": "llm",
            "payload": {
                "title": "Test Suggestion",
                "description": "Hook fired for {sop_name}.",
                "action_command": "echo done",
            },
        }
    ]
    return json.dumps(config)


# ---------------------------------------------------------------------------
# Shell hooks: verify file creation as side effect
# ---------------------------------------------------------------------------


async def test_shell_hook_fires_on_run_sop(tmp_path):
    """Shell hook on run_sop creates a marker file when tool is called."""
    marker = Path(f"/tmp/sop_hook_test_{uuid.uuid4().hex}")
    transport = _make_transport(tmp_path, _shell_hook_config(marker, "run_sop"))

    try:
        async with Client(transport) as client:
            result = await client.call_tool("run_sop", {"sop_name": "sop_creation_guide"})
            data = json.loads(result.content[0].text)
            assert "instruction" in data

        assert marker.exists(), f"Hook did not create {marker}"
    finally:
        marker.unlink(missing_ok=True)


async def test_shell_hook_fires_on_submit_feedback(tmp_path):
    """Shell hook on submit_sop_feedback creates a marker file."""
    marker = Path(f"/tmp/sop_hook_test_{uuid.uuid4().hex}")
    transport = _make_transport(tmp_path, _shell_hook_config(marker, "submit_sop_feedback"))

    try:
        async with Client(transport) as client:
            result = await client.call_tool(
                "submit_sop_feedback",
                {"sop_name": "sop_creation_guide", "feedback": "Hook test."},
            )
            data = json.loads(result.content[0].text)
            assert data["success"] is True

        assert marker.exists(), f"Hook did not create {marker}"
    finally:
        marker.unlink(missing_ok=True)


async def test_shell_hook_fires_on_publish_sop(tmp_path):
    """Shell hook on publish_sop creates a marker file."""
    marker = Path(f"/tmp/sop_hook_test_{uuid.uuid4().hex}")
    transport = _make_transport(tmp_path, _shell_hook_config(marker, "publish_sop"))

    content = (
        "---\n"
        "name: hook_pub_test_sop\n"
        "version: 1\n"
        "owner: tests\n"
        "stage: preprod\n"
        "---\n\n"
        "# Hook Pub Test\n\n"
        "## Overview\n\nHook test fixture.\n\n"
        "## Parameters\n\n- **x** (required): x.\n\n"
        "## Steps\n\n"
        "### 1. Do\n\n"
        "Action body.\n\n"
        "**Constraints:**\n"
        "- You MUST act\n\n"
        "**Expected Output:** Action completed.\n"
    )
    try:
        async with Client(transport) as client:
            result = await client.call_tool("publish_sop", {"content": content, "stage": "preprod"})
            data = json.loads(result.content[0].text)
            assert data["success"] is True

        assert marker.exists(), f"Hook did not create {marker}"
    finally:
        marker.unlink(missing_ok=True)


async def test_shell_hook_fires_on_sop_completed(tmp_path):
    """Shell hook on sop_completed fires when the last step is reached."""
    marker = Path(f"/tmp/sop_hook_test_{uuid.uuid4().hex}")
    transport = _make_transport(tmp_path, _shell_hook_config(marker, "sop_completed"))

    try:
        async with Client(transport) as client:
            start = await client.call_tool("run_sop", {"sop_name": "sop_creation_guide"})
            total = json.loads(start.content[0].text)["total_steps"]

            for step in range(1, total):
                await client.call_tool(
                    "run_sop",
                    {"sop_name": "sop_creation_guide", "current_step": step, "step_output": f"Step {step}"},
                )
            await client.call_tool(
                "run_sop",
                {"sop_name": "sop_creation_guide", "current_step": total, "step_output": "Final"},
            )

        assert marker.exists(), f"Hook did not create {marker} on sop_completed"
    finally:
        marker.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# LLM suggestion hooks: verify suggested_actions in response
# ---------------------------------------------------------------------------


async def test_llm_hook_adds_suggestions_on_run_sop(tmp_path):
    """LLM hook on run_sop adds suggested_actions to the response."""
    transport = _make_transport(tmp_path, _llm_hook_config("run_sop"))

    async with Client(transport) as client:
        result = await client.call_tool("run_sop", {"sop_name": "sop_creation_guide"})
        data = json.loads(result.content[0].text)

        assert "suggested_actions" in data
        assert len(data["suggested_actions"]) >= 1
        assert data["suggested_actions"][0]["title"] == "Test Suggestion"
        assert "sop_creation_guide" in data["suggested_actions"][0]["description"]


async def test_llm_hook_adds_suggestions_on_feedback(tmp_path):
    """LLM hook on submit_sop_feedback adds suggested_actions to the response."""
    transport = _make_transport(tmp_path, _llm_hook_config("submit_sop_feedback"))

    async with Client(transport) as client:
        result = await client.call_tool(
            "submit_sop_feedback",
            {"sop_name": "sop_creation_guide", "feedback": "LLM hook test."},
        )
        data = json.loads(result.content[0].text)

        assert "suggested_actions" in data
        assert data["suggested_actions"][0]["title"] == "Test Suggestion"


async def test_llm_hook_adds_suggestions_on_publish(tmp_path):
    """LLM hook on publish_sop adds suggested_actions to the response."""
    transport = _make_transport(tmp_path, _llm_hook_config("publish_sop"))

    content = (
        "---\n"
        "name: llm_hook_pub_sop\n"
        "version: 1\n"
        "owner: tests\n"
        "stage: preprod\n"
        "---\n\n"
        "# LLM Hook Pub\n\n"
        "## Overview\n\nLLM hook test fixture.\n\n"
        "## Parameters\n\n- **x** (required): x.\n\n"
        "## Steps\n\n"
        "### 1. Do\n\n"
        "Action body.\n\n"
        "**Constraints:**\n"
        "- You MUST act\n\n"
        "**Expected Output:** Action completed.\n"
    )
    async with Client(transport) as client:
        result = await client.call_tool("publish_sop", {"content": content, "stage": "preprod"})
        data = json.loads(result.content[0].text)

        assert "suggested_actions" in data
        assert data["suggested_actions"][0]["title"] == "Test Suggestion"


# ---------------------------------------------------------------------------
# Multiple hooks on same event
# ---------------------------------------------------------------------------


async def test_multiple_hooks_same_event(tmp_path):
    """Multiple hooks on the same event all fire."""
    marker1 = Path(f"/tmp/sop_hook_test_1_{uuid.uuid4().hex}")
    marker2 = Path(f"/tmp/sop_hook_test_2_{uuid.uuid4().hex}")

    config = json.dumps(
        [
            {
                "event_type": "run_sop",
                "action_type": "shell",
                "payload": {"command": f"/usr/bin/touch {marker1}", "timeout_seconds": 5},
            },
            {
                "event_type": "run_sop",
                "action_type": "shell",
                "payload": {"command": f"/usr/bin/touch {marker2}", "timeout_seconds": 5},
            },
        ]
    )
    transport = _make_transport(tmp_path, config)

    try:
        async with Client(transport) as client:
            await client.call_tool("run_sop", {"sop_name": "sop_creation_guide"})

        assert marker1.exists(), "First hook should have fired"
        assert marker2.exists(), "Second hook should have fired"
    finally:
        marker1.unlink(missing_ok=True)
        marker2.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Webhook hooks: spin up a local HTTP server, verify it receives the POST
# ---------------------------------------------------------------------------


class _WebhookReceiver:
    """Context manager that runs a local HTTP server to capture webhook POSTs."""

    def __init__(self):
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        self.received: list[dict] = []
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                parent.received.append(json.loads(body))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

            def log_message(self, *args):
                pass

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._server.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}/hook"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *args):
        self._server.shutdown()


def _webhook_hook_config(url: str, event_type: str) -> str:
    """Build a webhook hook config that POSTs to the given URL on the event."""
    config = [
        {
            "event_type": event_type,
            "action_type": "webhook",
            "payload": {
                "url": url,
                "timeout_seconds": 5,
            },
        }
    ]
    return json.dumps(config)


async def test_webhook_hook_fires_on_run_sop(tmp_path):
    """Webhook hook on run_sop POSTs to the configured URL."""
    with _WebhookReceiver() as receiver:
        transport = _make_transport(tmp_path, _webhook_hook_config(receiver.url, "run_sop"))

        async with Client(transport) as client:
            await client.call_tool("run_sop", {"sop_name": "sop_creation_guide"})

        assert len(receiver.received) == 1, f"Expected 1 POST, got {len(receiver.received)}"
        assert receiver.received[0]["event_type"] == "run_sop"
        assert "timestamp" in receiver.received[0]


async def test_webhook_hook_fires_on_feedback(tmp_path):
    """Webhook hook on submit_sop_feedback POSTs to the configured URL."""
    with _WebhookReceiver() as receiver:
        transport = _make_transport(tmp_path, _webhook_hook_config(receiver.url, "submit_sop_feedback"))

        async with Client(transport) as client:
            await client.call_tool(
                "submit_sop_feedback",
                {"sop_name": "sop_creation_guide", "feedback": "Webhook test."},
            )

        assert len(receiver.received) == 1, f"Expected 1 POST, got {len(receiver.received)}"
        assert receiver.received[0]["event_type"] == "submit_sop_feedback"

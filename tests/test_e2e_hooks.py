"""End-to-end tests for the hook system via FastMCP middleware.

Tests the full hook lifecycle: configure hooks, trigger them through
real MCP tool calls via in-memory transport, and verify handlers fired.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastmcp import Client

from src.mcp.hooks import (
    HookExecutor,
    HookRegistry,
    LLMSuggestionHandler,
    ShellHandler,
    WebhookHandler,
    parse_hook_config,
)
from src.server import _hook_middleware, mcp

pytestmark = pytest.mark.asyncio

SOP_NAME = "sop_creation_guide"


async def _call(client: Client, tool_name: str, arguments: dict | None = None) -> dict:
    result = await client.call_tool(tool_name, arguments or {})
    assert not result.is_error, f"Tool {tool_name} returned an error: {result}"
    return json.loads(result.content[0].text)


def _setup_executor(config_json: str) -> HookExecutor:
    """Parse config, build registry + executor with all handlers wired up."""
    callbacks = parse_hook_config(config_json)
    registry = HookRegistry()
    for cb in callbacks:
        registry.register(cb.event_type, cb)
    executor = HookExecutor(registry)
    executor.register_handler("shell", ShellHandler())
    executor.register_handler("webhook", WebhookHandler())
    executor.register_handler("llm", LLMSuggestionHandler(executor))
    return executor


async def _walk_sop_to_completion(client: Client) -> dict:
    """Walk through the SOP to completion, returning the final response."""
    data = await _call(client, "run_sop", {"sop_name": SOP_NAME})
    total = data["total_steps"]
    for step in range(1, total):
        data = await _call(
            client,
            "run_sop",
            {
                "sop_name": SOP_NAME,
                "current_step": step,
                "step_output": f"output {step}",
            },
        )
    return await _call(
        client,
        "run_sop",
        {
            "sop_name": SOP_NAME,
            "current_step": total,
            "step_output": "final output",
        },
    )


class TestE2EShellHook:
    """Shell hook fires via middleware on every run_sop call + sop_completed."""

    async def test_shell_hook_fires_on_every_run_sop_call(self):
        config = json.dumps(
            [
                {
                    "event_type": "run_sop",
                    "action_type": "shell",
                    "payload": {
                        "command": "echo STEP:{sop_name}:{current_step}",
                        "timeout_seconds": 5,
                    },
                },
                {
                    "event_type": "sop_completed",
                    "action_type": "shell",
                    "payload": {
                        "command": "echo COMPLETED:{sop_name}:v{sop_version}",
                        "timeout_seconds": 5,
                    },
                },
            ]
        )
        executor = _setup_executor(config)
        original = _hook_middleware.executor

        try:
            _hook_middleware.executor = executor

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout="ok",
                    stderr="",
                    returncode=0,
                )

                async with Client(mcp) as client:
                    data = await _walk_sop_to_completion(client)

                    assert "complete" in data["instruction"].lower()
                    total_steps = data["total_steps"]
                    # run_sop fires on every call (total_steps + 1 calls)
                    # sop_completed fires once on the final call
                    expected_calls = (total_steps + 1) + 1
                    assert mock_run.call_count == expected_calls
        finally:
            _hook_middleware.executor = original


class TestE2EWebhookHook:
    """Webhook hook fires via middleware on submit_sop_feedback."""

    async def test_webhook_hook_posts_on_feedback(self):
        config = json.dumps(
            [
                {
                    "event_type": "submit_sop_feedback",
                    "action_type": "webhook",
                    "payload": {
                        "url": "https://hooks.example.com/feedback",
                        "sop_name": "{sop_name}",
                        "timeout_seconds": 3,
                    },
                }
            ]
        )
        executor = _setup_executor(config)
        original = _hook_middleware.executor

        try:
            _hook_middleware.executor = executor

            with patch("requests.post") as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.text = '{"ok":true}'
                mock_response.raise_for_status = MagicMock()
                mock_post.return_value = mock_response

                async with Client(mcp) as client:
                    data = await _call(
                        client,
                        "submit_sop_feedback",
                        {
                            "sop_name": SOP_NAME,
                            "feedback": "E2E webhook hook test feedback",
                        },
                    )

                    assert data["success"] is True
                    mock_post.assert_called_once()
                    call_args, call_kwargs = mock_post.call_args
                    assert call_args[0] == "https://hooks.example.com/feedback"
                    payload = call_kwargs["json"]
                    assert payload["event_type"] == "submit_sop_feedback"
                    assert payload["sop_name"] == SOP_NAME
                    assert "timestamp" in payload
        finally:
            _hook_middleware.executor = original


class TestE2ELLMHook:
    """LLM hook adds suggestion via middleware on sop_completed."""

    async def test_llm_hook_adds_suggestion_on_sop_complete(self):
        config = json.dumps(
            [
                {
                    "event_type": "sop_completed",
                    "action_type": "llm",
                    "payload": {
                        "title": "Review {sop_name} output",
                        "description": "SOP {sop_name} v{sop_version} completed {total_steps} steps.",
                        "action_command": 'publish_sop(change_type="minor")',
                    },
                }
            ]
        )
        executor = _setup_executor(config)
        original = _hook_middleware.executor

        try:
            _hook_middleware.executor = executor

            async with Client(mcp) as client:
                data = await _walk_sop_to_completion(client)

                assert "complete" in data["instruction"].lower()
                assert len(executor.suggested_actions) == 1
                suggestion = executor.suggested_actions[0]
                assert suggestion["title"] == "Review sop_creation_guide output"
                assert "sop_creation_guide" in suggestion["description"]
                assert suggestion["action_command"] == 'publish_sop(change_type="minor")'
        finally:
            _hook_middleware.executor = original

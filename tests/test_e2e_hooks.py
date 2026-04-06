"""End-to-end tests for the hook system via FastMCP middleware.

Tests the full hook lifecycle: configure hooks, trigger them through
real MCP tool calls via in-memory transport, and verify handlers fired.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastmcp import Client

from src.sop_mcp.hooks import (
    HookExecutor,
    HookRegistry,
    LLMSuggestionHandler,
    ShellHandler,
    WebhookHandler,
    parse_hook_config,
)
from src.sop_mcp.server import _hook_middleware, mcp

pytestmark = pytest.mark.asyncio

SOP_NAME = "sop_creation_guide"
EXAMPLES_DIR = Path(__file__).parent.parent / "skills" / "sop-mcp-configuration" / "examples"


async def _call(client: Client, tool_name: str, arguments: dict | None = None) -> dict:
    result = await client.call_tool(tool_name, arguments or {})
    assert not result.is_error, f"Tool {tool_name} returned an error: {result}"
    return json.loads(result.content[0].text)


def _setup_executor(config: str) -> HookExecutor:
    """Parse config from a JSON file path or raw JSON string, build registry + executor."""
    callbacks = parse_hook_config(config)
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
    """Shell hook fires via middleware on every run_sop call."""

    async def test_shell_hook_fires_on_every_run_sop_call(self):
        executor = _setup_executor(str(EXAMPLES_DIR / "shell.hook.json"))
        original = _hook_middleware.executor

        try:
            _hook_middleware.executor = executor

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)

                async with Client(mcp) as client:
                    data = await _walk_sop_to_completion(client)

                    assert "complete" in data["instruction"].lower()
                    total_steps = data["total_steps"]
                    # shell.hook.json has a run_sop hook — fires on every call (total_steps + 1)
                    # sop_completed hook is filtered by security (command contains 'sh')
                    assert mock_run.call_count == total_steps + 1
        finally:
            _hook_middleware.executor = original


class TestE2EWebhookHook:
    """Webhook hook fires via middleware on submit_sop_feedback."""

    async def test_webhook_hook_posts_on_feedback(self):
        executor = _setup_executor(str(EXAMPLES_DIR / "webhook.hook.json"))
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
                        {"sop_name": SOP_NAME, "feedback": "E2E webhook hook test feedback"},
                    )

                    assert data["success"] is True
                    mock_post.assert_called_once()
                    call_args, call_kwargs = mock_post.call_args
                    # webhook.hook.json posts feedback to hooks.example.com/feedback
                    assert call_args[0] == "https://hooks.example.com/feedback"
                    payload = call_kwargs["json"]
                    assert payload["event_type"] == "submit_sop_feedback"
                    assert payload["sop_name"] == SOP_NAME
                    assert "timestamp" in payload
        finally:
            _hook_middleware.executor = original


class TestE2ELLMHook:
    """LLM suggestions are injected into the MCP response payload."""

    async def test_llm_suggestions_forwarded_in_response(self):
        executor = _setup_executor(str(EXAMPLES_DIR / "llm.hook.json"))
        original = _hook_middleware.executor

        try:
            _hook_middleware.executor = executor

            async with Client(mcp) as client:
                # Walk to the final step — sop_completed fires and adds an LLM suggestion
                data = await _walk_sop_to_completion(client)

                # The suggestion must be present in the actual MCP response, not just on the executor
                assert "suggested_actions" in data, "suggested_actions missing from MCP response"
                suggestions = data["suggested_actions"]
                assert len(suggestions) >= 1

                # The sop_completed hook in llm.hook.json suggests publishing
                sop_suggestion = next((s for s in suggestions if "publish_sop" in s.get("action_command", "")), None)
                assert sop_suggestion is not None
                assert SOP_NAME in sop_suggestion["description"]
                assert sop_suggestion["action_command"] == 'publish_sop(change_type="minor")'
        finally:
            _hook_middleware.executor = original

    async def test_llm_suggestion_on_feedback_forwarded_in_response(self):
        executor = _setup_executor(str(EXAMPLES_DIR / "llm.hook.json"))
        original = _hook_middleware.executor

        try:
            _hook_middleware.executor = executor

            async with Client(mcp) as client:
                data = await _call(
                    client,
                    "submit_sop_feedback",
                    {"sop_name": SOP_NAME, "feedback": "great SOP"},
                )

                assert "suggested_actions" in data, "suggested_actions missing from MCP response"
                suggestions = data["suggested_actions"]
                patch_suggestion = next((s for s in suggestions if "patch" in s.get("action_command", "")), None)
                assert patch_suggestion is not None
                assert SOP_NAME in patch_suggestion["description"]
        finally:
            _hook_middleware.executor = original


class TestE2ELLMHookYAML:
    """Same LLM hook behaviour, but loaded from llm.hook.yaml instead of llm.hook.json."""

    async def test_llm_suggestions_forwarded_in_response_yaml(self):
        executor = _setup_executor(str(EXAMPLES_DIR / "llm.hook.yaml"))
        original = _hook_middleware.executor

        try:
            _hook_middleware.executor = executor

            async with Client(mcp) as client:
                data = await _walk_sop_to_completion(client)

                assert "suggested_actions" in data, "suggested_actions missing from MCP response"
                suggestions = data["suggested_actions"]
                assert len(suggestions) >= 1

                sop_suggestion = next((s for s in suggestions if "publish_sop" in s.get("action_command", "")), None)
                assert sop_suggestion is not None
                assert SOP_NAME in sop_suggestion["description"]
                assert sop_suggestion["action_command"] == 'publish_sop(change_type="minor")'
        finally:
            _hook_middleware.executor = original

    async def test_llm_suggestion_on_feedback_forwarded_in_response_yaml(self):
        executor = _setup_executor(str(EXAMPLES_DIR / "llm.hook.yaml"))
        original = _hook_middleware.executor

        try:
            _hook_middleware.executor = executor

            async with Client(mcp) as client:
                data = await _call(
                    client,
                    "submit_sop_feedback",
                    {"sop_name": SOP_NAME, "feedback": "great SOP"},
                )

                assert "suggested_actions" in data, "suggested_actions missing from MCP response"
                suggestions = data["suggested_actions"]
                patch_suggestion = next((s for s in suggestions if "patch" in s.get("action_command", "")), None)
                assert patch_suggestion is not None
                assert SOP_NAME in patch_suggestion["description"]
        finally:
            _hook_middleware.executor = original


class TestE2EMultipleLLMHooks:
    """Multiple LLM hooks for the same event should all appear in the response."""

    async def test_multiple_llm_hooks_same_event_in_response(self):
        """Two LLM hooks for run_sop should both appear in suggested_actions."""
        # Create a custom config with two LLM hooks for run_sop
        config = """
- event_type: run_sop
  action_type: llm
  payload:
    title: "First Suggestion"
    description: "First suggestion for {sop_name}"

- event_type: run_sop
  action_type: llm
  payload:
    title: "Second Suggestion"
    description: "Second suggestion for {sop_name}"
    action_command: "publish_sop(change_type=\\"minor\\")"
"""
        executor = _setup_executor(config)
        original = _hook_middleware.executor

        try:
            _hook_middleware.executor = executor

            async with Client(mcp) as client:
                data = await _call(client, "run_sop", {"sop_name": SOP_NAME})

                assert "suggested_actions" in data, "suggested_actions missing from MCP response"
                suggestions = data["suggested_actions"]
                assert len(suggestions) == 2, f"Expected 2 suggestions, got {len(suggestions)}"

                titles = {s["title"] for s in suggestions}
                assert "First Suggestion" in titles
                assert "Second Suggestion" in titles

                # Check context substitution
                for suggestion in suggestions:
                    assert SOP_NAME in suggestion["description"]
        finally:
            _hook_middleware.executor = original

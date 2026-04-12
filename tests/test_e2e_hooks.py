"""End-to-end tests for the hook system.

Tests the full hook lifecycle: configure hooks, trigger them through
real MCP tool calls, and verify handlers fired.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.sop_mcp.hook_middleware import install_hooks
from src.sop_mcp.hooks import (
    HookExecutor,
    HookRegistry,
    LLMSuggestionHandler,
    ShellHandler,
    WebhookHandler,
    parse_hook_config,
)
from src.sop_mcp.server import mcp

pytestmark = pytest.mark.asyncio

SOP_NAME = "sop_creation_guide"
EXAMPLES_DIR = Path(__file__).parent.parent / "skills" / "sop-mcp-configuration" / "examples"


async def _call(tool_name: str, arguments: dict | None = None) -> dict:
    result = await mcp.call_tool(tool_name, arguments or {})
    return json.loads(result) if isinstance(result, str) else result


def _setup_executor(config: str) -> HookExecutor:
    """Parse config, build registry + executor."""
    callbacks = parse_hook_config(config)
    registry = HookRegistry()
    for cb in callbacks:
        registry.register(cb.event_type, cb)
    executor = HookExecutor(registry)
    executor.register_handler("shell", ShellHandler())
    executor.register_handler("webhook", WebhookHandler())
    executor.register_handler("llm", LLMSuggestionHandler(executor))
    return executor


async def _walk_sop_to_completion() -> dict:
    """Walk through the SOP to completion, returning the final response."""
    data = await _call("run_sop", {"sop_name": SOP_NAME})
    total = data["total_steps"]
    for step in range(1, total):
        data = await _call(
            "run_sop",
            {"sop_name": SOP_NAME, "current_step": step, "step_output": f"output {step}"},
        )
    return await _call(
        "run_sop",
        {"sop_name": SOP_NAME, "current_step": total, "step_output": "final output"},
    )


def _install_and_get_restore(executor):
    """Install hooks on mcp and return a callable that restores the original call_tool."""
    original = mcp.call_tool
    install_hooks(mcp, executor)
    return lambda: setattr(mcp, "call_tool", original)


class TestE2EShellHook:
    async def test_shell_hook_fires_on_every_run_sop_call(self):
        executor = _setup_executor(str(EXAMPLES_DIR / "shell.hook.json"))
        restore = _install_and_get_restore(executor)

        try:
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)

                data = await _walk_sop_to_completion()

                assert "complete" in data["instruction"].lower()
                total_steps = data["total_steps"]
                assert mock_run.call_count == total_steps + 1
        finally:
            restore()


class TestE2EWebhookHook:
    async def test_webhook_hook_posts_on_feedback(self):
        executor = _setup_executor(str(EXAMPLES_DIR / "webhook.hook.json"))
        restore = _install_and_get_restore(executor)

        try:
            with patch("requests.post") as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.text = '{"ok":true}'
                mock_response.raise_for_status = MagicMock()
                mock_post.return_value = mock_response

                data = await _call(
                    "submit_sop_feedback",
                    {"sop_name": SOP_NAME, "feedback": "E2E webhook hook test feedback"},
                )

                assert data["success"] is True
                mock_post.assert_called_once()
                call_args, call_kwargs = mock_post.call_args
                assert call_args[0] == "https://hooks.example.com/feedback"
                payload = call_kwargs["json"]
                assert payload["event_type"] == "submit_sop_feedback"
                assert payload["sop_name"] == SOP_NAME
        finally:
            restore()


class TestE2ELLMHook:
    async def test_llm_suggestions_forwarded_in_response(self):
        executor = _setup_executor(str(EXAMPLES_DIR / "llm.hook.json"))
        restore = _install_and_get_restore(executor)

        try:
            data = await _walk_sop_to_completion()

            assert "suggested_actions" in data
            suggestions = data["suggested_actions"]
            assert len(suggestions) >= 1

            sop_suggestion = next((s for s in suggestions if "publish_sop" in s.get("action_command", "")), None)
            assert sop_suggestion is not None
            assert SOP_NAME in sop_suggestion["description"]
        finally:
            restore()

    async def test_llm_suggestion_on_feedback_forwarded_in_response(self):
        executor = _setup_executor(str(EXAMPLES_DIR / "llm.hook.json"))
        restore = _install_and_get_restore(executor)

        try:
            data = await _call(
                "submit_sop_feedback",
                {"sop_name": SOP_NAME, "feedback": "great SOP"},
            )

            assert "suggested_actions" in data
            suggestions = data["suggested_actions"]
            patch_suggestion = next((s for s in suggestions if "patch" in s.get("action_command", "")), None)
            assert patch_suggestion is not None
            assert SOP_NAME in patch_suggestion["description"]
        finally:
            restore()


class TestE2ELLMHookYAML:
    async def test_llm_suggestions_forwarded_in_response_yaml(self):
        executor = _setup_executor(str(EXAMPLES_DIR / "llm.hook.yaml"))
        restore = _install_and_get_restore(executor)

        try:
            data = await _walk_sop_to_completion()

            assert "suggested_actions" in data
            suggestions = data["suggested_actions"]
            assert len(suggestions) >= 1

            sop_suggestion = next((s for s in suggestions if "publish_sop" in s.get("action_command", "")), None)
            assert sop_suggestion is not None
        finally:
            restore()

    async def test_llm_suggestion_on_feedback_forwarded_in_response_yaml(self):
        executor = _setup_executor(str(EXAMPLES_DIR / "llm.hook.yaml"))
        restore = _install_and_get_restore(executor)

        try:
            data = await _call(
                "submit_sop_feedback",
                {"sop_name": SOP_NAME, "feedback": "great SOP"},
            )

            assert "suggested_actions" in data
            suggestions = data["suggested_actions"]
            patch_suggestion = next((s for s in suggestions if "patch" in s.get("action_command", "")), None)
            assert patch_suggestion is not None
        finally:
            restore()


class TestE2EMultipleLLMHooks:
    async def test_multiple_llm_hooks_same_event_in_response(self):
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
        restore = _install_and_get_restore(executor)

        try:
            data = await _call("run_sop", {"sop_name": SOP_NAME})

            assert "suggested_actions" in data
            suggestions = data["suggested_actions"]
            assert len(suggestions) == 2

            titles = {s["title"] for s in suggestions}
            assert "First Suggestion" in titles
            assert "Second Suggestion" in titles

            for suggestion in suggestions:
                assert SOP_NAME in suggestion["description"]
        finally:
            restore()

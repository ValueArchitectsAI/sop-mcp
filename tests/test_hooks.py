import json
import os
from unittest.mock import MagicMock, patch

from hypothesis import given
from hypothesis import strategies as st

from src.mcp.hooks import (
    CallbackDefinition,
    HookRegistry,
    ShellHandler,
    WebhookHandler,
    parse_hook_config,
)

# ── Registry unit tests ──────────────────────────────────────────────


def test_hook_registry_register_single() -> None:
    """Validates: Requirements 1.1"""
    registry = HookRegistry()
    cb = CallbackDefinition("evt", "shell", {"command": "echo hello"})
    registry.register("evt", cb)

    retrieved = registry.get_callbacks("evt")
    assert len(retrieved) == 1
    assert retrieved[0] == cb

    # deep-copy check
    retrieved[0].payload["command"] = "changed"
    assert registry.get_callbacks("evt")[0].payload["command"] == "echo hello"


def test_hook_registry_register_multiple() -> None:
    """Validates: Requirements 1.1"""
    registry = HookRegistry()
    cb1 = CallbackDefinition("evt", "shell", {"command": "cmd1"})
    cb2 = CallbackDefinition("evt", "webhook", {"url": "http://example.com"})
    registry.register("evt", cb1)
    registry.register("evt", cb2)

    retrieved = registry.get_callbacks("evt")
    assert len(retrieved) == 2
    assert retrieved[0] == cb1
    assert retrieved[1] == cb2


def test_hook_registry_get_nonexistent() -> None:
    """Validates: Requirements 1.1"""
    assert HookRegistry().get_callbacks("unknown") == []


# ── Config parser unit tests ─────────────────────────────────────────


def test_parse_hook_config_valid() -> None:
    """Validates: Requirements 2.2"""
    cfg = json.dumps(
        [
            {
                "event_type": "sop_executed",
                "action_type": "shell",
                "payload": {"command": "/bin/true", "timeout_seconds": 30},
            },
            {
                "event_type": "feedback_submitted",
                "action_type": "webhook",
                "payload": {"url": "https://example.com/webhook"},
            },
        ]
    )
    result = parse_hook_config(cfg)
    assert len(result) == 2
    assert result[0].event_type == "sop_executed"
    assert result[1].action_type == "webhook"


def test_parse_hook_config_invalid_json() -> None:
    assert parse_hook_config("{ bad json") == []


def test_parse_hook_config_non_list() -> None:
    assert parse_hook_config(json.dumps({"event_type": "x"})) == []


def test_parse_hook_config_missing_fields() -> None:
    cfg = json.dumps(
        [
            {"event_type": "t", "action_type": "shell"},  # no payload
            {"event_type": "t", "payload": {}},  # no action_type
            {"action_type": "webhook", "payload": {"url": "x"}},  # no event_type
        ]
    )
    assert parse_hook_config(cfg) == []


def test_parse_hook_config_invalid_action_type() -> None:
    cfg = json.dumps([{"event_type": "t", "action_type": "bad", "payload": {}}])
    assert parse_hook_config(cfg) == []


def test_parse_hook_config_payload_not_dict() -> None:
    cfg = json.dumps([{"event_type": "t", "action_type": "shell", "payload": "str"}])
    assert parse_hook_config(cfg) == []


def test_parse_hook_config_empty_string() -> None:
    assert parse_hook_config("") == []


# ── File-based config tests ──────────────────────────────────────────

EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "examples")


def test_parse_hook_config_from_shell_file() -> None:
    """parse_hook_config accepts a .json file path — shell example."""
    path = os.path.join(EXAMPLES_DIR, "shell.hook.json")
    result = parse_hook_config(path)
    assert len(result) > 0
    action_types = {cb.action_type for cb in result}
    assert action_types == {"shell"}


def test_parse_hook_config_from_webhook_file() -> None:
    """parse_hook_config accepts a .json file path — webhook example."""
    path = os.path.join(EXAMPLES_DIR, "webhook.hook.json")
    result = parse_hook_config(path)
    assert len(result) > 0
    action_types = {cb.action_type for cb in result}
    assert action_types == {"webhook"}


def test_parse_hook_config_from_llm_file() -> None:
    """parse_hook_config accepts a .json file path — llm example."""
    path = os.path.join(EXAMPLES_DIR, "llm.hook.json")
    result = parse_hook_config(path)
    assert len(result) > 0
    action_types = {cb.action_type for cb in result}
    assert action_types == {"llm"}


def test_parse_hook_config_from_mixed_file() -> None:
    """parse_hook_config accepts a .json file path — mixed example."""
    path = os.path.join(EXAMPLES_DIR, "mixed.hook.json")
    result = parse_hook_config(path)
    assert len(result) > 0
    action_types = {cb.action_type for cb in result}
    assert "shell" in action_types
    assert "webhook" in action_types


def test_parse_hook_config_missing_file() -> None:
    """parse_hook_config returns empty list for a non-existent file path."""
    result = parse_hook_config("/nonexistent/path/hooks.json")
    assert result == []


def test_parse_hook_config_partial_valid_entries() -> None:
    cfg = json.dumps(
        [
            {"event_type": "v1", "action_type": "shell", "payload": {"command": "true"}},
            {"event_type": "bad", "action_type": "nope", "payload": {}},
            {"event_type": "v2", "action_type": "webhook", "payload": {"url": "https://t.com"}},
        ]
    )
    result = parse_hook_config(cfg)
    assert len(result) == 2
    assert result[0].event_type == "v1"
    assert result[1].event_type == "v2"


# ── Shell handler tests ──────────────────────────────────────────────


@given(
    st.sampled_from(["echo hello", "ls -la", "pwd", "date", "whoami"]),
    st.integers(min_value=1, max_value=60),
)
def test_shell_handler_secure_execution(command: str, timeout: int) -> None:
    """
    // Feature: add-hook-system, Property 5: Shell Command Secure Execution
    Validates: Requirements 3.1
    """
    handler = ShellHandler()
    cb = CallbackDefinition("test", "shell", {"command": command, "timeout_seconds": timeout})

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = type("CP", (), {"stdout": "ok", "stderr": "", "returncode": 0})()
        result = handler.execute(cb)

        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs.get("shell", False) is False
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert result["success"] is True


# ── Webhook handler tests ────────────────────────────────────────────


@given(
    st.sampled_from(["http://a.com", "https://b.com", "http://localhost:8080"]),
    st.integers(min_value=1, max_value=30),
)
def test_webhook_post_transmission(url: str, timeout: int) -> None:
    """
    // Feature: add-hook-system, Property 8: Webhook POST Transmission
    Validates: Requirements 4.1
    """
    payload = {"url": url, "timeout_seconds": timeout, "sop_name": "test_sop"}
    cb = CallbackDefinition("test_event", "webhook", payload)
    handler = WebhookHandler()

    with patch("requests.post") as mock_post:
        mock_resp = type(
            "R",
            (),
            {
                "status_code": 200,
                "text": "OK",
                "raise_for_status": lambda self: None,
            },
        )()
        mock_post.return_value = mock_resp
        result = handler.execute(cb)

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["event_type"] == "test_event"
        assert kwargs["json"]["sop_name"] == "test_sop"
        assert isinstance(kwargs["json"]["timestamp"], str)
        assert kwargs["timeout"] == timeout
        assert result["success"] is True


def test_webhook_handler_success() -> None:
    """Validates: Requirements 4.1, 4.2"""
    cb = CallbackDefinition(
        "sop_executed",
        "webhook",
        {
            "url": "https://api.example.com/webhook",
            "sop_name": "test_sop",
            "extra": "val",
        },
    )
    with patch("requests.post") as mock_post:
        mock_post.return_value = type(
            "R",
            (),
            {
                "status_code": 201,
                "text": '{"ok":true}',
                "raise_for_status": lambda self: None,
            },
        )()
        result = WebhookHandler().execute(cb)
        assert result["success"] is True
        assert result["status_code"] == 201


def test_webhook_handler_timeout() -> None:
    """Validates: Requirements 4.2"""
    import requests as req_lib

    cb = CallbackDefinition("fb", "webhook", {"url": "https://slow.api.com/wh", "timeout_seconds": 1})
    with patch("requests.post", side_effect=req_lib.exceptions.Timeout("timeout")):
        result = WebhookHandler().execute(cb)
        assert result["success"] is False
        assert result["error"] == "timeout"


def test_webhook_handler_http_error() -> None:
    """Validates: Requirements 4.2"""
    import requests as req_lib

    cb = CallbackDefinition("test", "webhook", {"url": "https://api.example.com/wh"})

    with patch("requests.post") as mock_post:
        # Build a proper HTTPError with a response attribute
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "Not Found"
        exc = req_lib.exceptions.HTTPError("404 Client Error", response=mock_resp)
        mock_resp.raise_for_status.side_effect = exc
        mock_post.return_value = mock_resp

        result = WebhookHandler().execute(cb)
        assert result["success"] is False
        assert result["error"] == "http_error"
        assert result["status_code"] == 404


def test_webhook_handler_missing_sop_name() -> None:
    """Validates: Requirements 4.2"""
    cb = CallbackDefinition("test", "webhook", {"url": "https://api.example.com/wh"})
    with patch("requests.post") as mock_post, patch("logging.warning"):
        mock_post.return_value = type(
            "R",
            (),
            {
                "status_code": 200,
                "text": "OK",
                "raise_for_status": lambda self: None,
            },
        )()
        result = WebhookHandler().execute(cb)
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["sop_name"] == "unknown"
        assert result["success"] is True


# ── LLM suggestion handler tests ─────────────────────────────────────

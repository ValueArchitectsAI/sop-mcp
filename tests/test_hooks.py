import json
import os
from unittest.mock import MagicMock, patch

from hypothesis import given
from hypothesis import strategies as st

from src.sop_mcp.hooks import (
    CallbackDefinition,
    HookExecutor,
    HookRegistry,
    LLMSuggestionHandler,
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

EXAMPLES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "skills", "sop-mcp-configuration", "examples"
)


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


# ── YAML config tests ────────────────────────────────────────────────


def test_parse_hook_config_yaml_string() -> None:
    """parse_hook_config accepts a YAML string."""
    cfg = """
- event_type: sop_executed
  action_type: shell
  payload:
    command: /bin/true
    timeout_seconds: 30
- event_type: feedback_submitted
  action_type: webhook
  payload:
    url: https://example.com/webhook
"""
    result = parse_hook_config(cfg)
    assert len(result) == 2
    assert result[0].event_type == "sop_executed"
    assert result[1].action_type == "webhook"


def test_parse_hook_config_from_yaml_file() -> None:
    """parse_hook_config accepts a .yaml file path — llm example."""
    path = os.path.join(EXAMPLES_DIR, "llm.hook.yaml")
    result = parse_hook_config(path)
    assert len(result) > 0
    assert all(cb.action_type == "llm" for cb in result)


def test_parse_hook_config_yaml_multiline_string() -> None:
    """parse_hook_config handles multiline YAML block scalars — sourced from llm.hook.yaml."""
    path = os.path.join(EXAMPLES_DIR, "llm.hook.yaml")
    result = parse_hook_config(path)
    assert len(result) == 4
    assert all(cb.action_type == "llm" for cb in result)

    # Each description should be a multiline string (contains newlines)
    for cb in result:
        assert "\n" in cb.payload["description"], f"Expected multiline description in {cb.event_type}"

    # Spot-check sop_completed entry
    completed = next(cb for cb in result if cb.event_type == "sop_completed")
    assert "publish_sop" in completed.payload["action_command"]
    assert "{sop_name}" in completed.payload["description"]
    assert "{total_steps}" in completed.payload["description"]


def test_parse_hook_config_from_llm_yaml_file() -> None:
    """parse_hook_config accepts a .yaml file path — llm example."""
    path = os.path.join(EXAMPLES_DIR, "llm.hook.yaml")
    result = parse_hook_config(path)
    assert len(result) > 0
    assert all(cb.action_type == "llm" for cb in result)
    event_types = {cb.event_type for cb in result}
    assert event_types == {"run_sop", "sop_completed", "submit_sop_feedback", "publish_sop"}


def test_parse_hook_config_from_yml_file() -> None:
    """parse_hook_config accepts a .yml file extension."""
    import tempfile

    cfg = [{"event_type": "run_sop", "action_type": "shell", "payload": {"command": "echo hi", "timeout_seconds": 5}}]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False, encoding="utf-8") as f:
        import yaml as _yaml

        _yaml.dump(cfg, f)
        tmp_path = f.name

    try:
        result = parse_hook_config(tmp_path)
        assert len(result) == 1
        assert result[0].event_type == "run_sop"
    finally:
        os.unlink(tmp_path)


def test_parse_hook_config_from_mixed_yaml_file() -> None:
    """parse_hook_config returns empty list for a non-existent mixed yaml file (file removed)."""
    result = parse_hook_config("/nonexistent/path/mixed.hook.yaml")
    assert result == []


def test_parse_hook_config_invalid_yaml() -> None:
    """parse_hook_config returns empty list for invalid YAML that is also invalid JSON."""
    result = parse_hook_config("{ bad: yaml: [unclosed")
    assert result == []


def test_parse_hook_config_missing_yaml_file() -> None:
    """parse_hook_config returns empty list for a non-existent .yaml file."""
    result = parse_hook_config("/nonexistent/path/hooks.yaml")
    assert result == []


def test_multiple_hooks_same_event() -> None:
    """Multiple callbacks for the same event should all fire."""
    registry = HookRegistry()

    # Create two callbacks for the same event
    shell_cb = CallbackDefinition("test_event", "shell", {"command": "echo test"})
    webhook_cb = CallbackDefinition("test_event", "webhook", {"url": "https://example.com"})

    registry.register("test_event", shell_cb)
    registry.register("test_event", webhook_cb)

    # Simulate execution
    callbacks = registry.get_callbacks("test_event")
    assert len(callbacks) == 2

    # Check both callbacks are present
    action_types = {cb.action_type for cb in callbacks}
    assert "shell" in action_types
    assert "webhook" in action_types


def test_multiple_llm_hooks_same_event() -> None:
    """Multiple LLM callbacks for the same event should all be added to suggested_actions."""
    registry = HookRegistry()

    # Create two LLM callbacks for the same event
    cb1 = CallbackDefinition(
        "run_sop", "llm", {"title": "First Suggestion", "description": "First suggestion for {sop_name}"}
    )
    cb2 = CallbackDefinition(
        "run_sop",
        "llm",
        {
            "title": "Second Suggestion",
            "description": "Second suggestion for {sop_name}",
            "action_command": 'publish_sop(stage="preprod")',
        },
    )

    registry.register("run_sop", cb1)
    registry.register("run_sop", cb2)

    # Create executor with LLM handler
    executor = HookExecutor(registry)
    llm_handler = LLMSuggestionHandler(executor)
    executor.register_handler("llm", llm_handler)

    # Execute the event
    executor.execute_event("run_sop", context={"sop_name": "test_sop"})

    # Both suggestions should be in suggested_actions
    assert len(executor.suggested_actions) == 2

    # Verify both suggestions are present
    titles = {s["title"] for s in executor.suggested_actions}
    assert "First Suggestion" in titles
    assert "Second Suggestion" in titles

    # Verify context substitution worked
    for suggestion in executor.suggested_actions:
        assert "test_sop" in suggestion["description"]

import json
import logging
import os
import shlex
import subprocess
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Any, Literal

import requests
import yaml


class SecurityError(Exception):
    """Exception raised when security validation fails for a callback."""


@dataclass
class CallbackDefinition:
    """Definition of a callback for hook system.

    Attributes:
        event_type: Type of event that triggers this callback
        action_type: Type of action to execute (shell, webhook, llm)
        payload: Action-specific configuration payload
    """

    event_type: str
    action_type: Literal["shell", "webhook", "llm"]
    payload: dict[str, Any]


def hooks_enabled() -> bool:
    """Check whether the hook system should be active.

    Hooks are enabled when `SOP_HOOK_CONFIG` is set to a non-empty value.
    """
    config = os.environ.get("SOP_HOOK_CONFIG", "").strip()
    return len(config) > 0


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------

_MAX_CONFIG_BYTES = 64 * 1024


def _read_config_file(path: str) -> str | None:
    """Read a hook config file from disk. Returns None on failure."""
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        logging.warning(f"Failed to read hook config file '{path}': {e}")
        return None

    if len(raw) > _MAX_CONFIG_BYTES:
        logging.warning("Hook configuration exceeds 64KB limit. Discarding.")
        return None
    return raw


def _parse_raw_config(raw: str, *, is_yaml: bool = False) -> list | None:
    """Parse a raw string as JSON or YAML into a list. Returns None on failure."""
    if is_yaml:
        try:
            config = yaml.safe_load(raw)
        except yaml.YAMLError:
            return None
    else:
        try:
            config = json.loads(raw)
        except json.JSONDecodeError:
            return None

    return config if isinstance(config, list) else None


def _load_config(config_str: str) -> list | None:
    """Load hook config from a file path or inline string."""
    stripped = config_str.strip()
    is_yaml_file = stripped.endswith((".yaml", ".yml"))
    is_json_file = stripped.endswith(".json")

    if is_json_file or is_yaml_file:
        raw = _read_config_file(stripped)
        if raw is None:
            return None
        return _parse_raw_config(raw, is_yaml=is_yaml_file)

    # Inline string — enforce size limit
    if len(stripped) > _MAX_CONFIG_BYTES:
        logging.warning("Hook configuration exceeds 64KB limit. Discarding.")
        return None

    # Try JSON first, fall back to YAML
    result = _parse_raw_config(stripped, is_yaml=False)
    if result is None:
        result = _parse_raw_config(stripped, is_yaml=True)
    return result


def _validate_item(item: dict) -> CallbackDefinition | None:
    """Validate a single config item and return a CallbackDefinition or None."""
    if not isinstance(item, dict):
        return None

    required_keys = {"event_type", "action_type", "payload"}
    if not required_keys.issubset(item.keys()):
        return None

    action_type = item["action_type"]
    if action_type not in ("shell", "webhook", "llm"):
        return None

    payload = item["payload"]
    if not isinstance(payload, dict):
        return None

    return CallbackDefinition(
        event_type=item["event_type"],
        action_type=action_type,  # type: ignore[arg-type]
        payload=payload,
    )


def parse_hook_config(config_str: str) -> list[CallbackDefinition]:
    """Parse hook configuration from a JSON/YAML string or file path.

    Returns a list of valid CallbackDefinition objects, or empty list on failure.
    """
    config = _load_config(config_str)
    if config is None:
        return []

    secure_mode = os.environ.get("SOP_HOOKS_SECURE", "true").lower() != "false"
    results: list[CallbackDefinition] = []

    for item in config:
        callback = _validate_item(item)
        if callback is None:
            continue
        try:
            validate_callback_security(callback, secure_mode)
        except SecurityError as e:
            logging.warning(f"Skipping insecure callback: {e}")
            continue
        results.append(callback)

    return results


# ---------------------------------------------------------------------------
# Security validation
# ---------------------------------------------------------------------------

_DANGEROUS_SHELL_PATTERNS = [
    ";",
    "|",
    "&",
    ">",
    "<",
    "`",
    "$(",
    "${",
    "||",
    "&&",
    "curl",
    "wget",
    "nc",
    "bash",
    "sh",
    "python",
    "perl",
    "php",
]


def validate_callback_security(callback: CallbackDefinition, secure_mode: bool) -> None:
    """Validate callback for security risks.

    Raises:
        SecurityError: If callback is deemed insecure
    """
    if callback.action_type == "shell":
        command = callback.payload.get("command", "")
        for pattern in _DANGEROUS_SHELL_PATTERNS:
            if pattern in command:
                raise SecurityError(f"Shell command contains prohibited pattern '{pattern}': {command}")

    elif callback.action_type == "webhook" and secure_mode:
        url = callback.payload.get("url", "")
        if not url.startswith("https://"):
            raise SecurityError(f"Webhook URL must use HTTPS when security is enabled: {url}")


# ---------------------------------------------------------------------------
# Context substitution
# ---------------------------------------------------------------------------


def _substitute_context(callback: CallbackDefinition, context: dict[str, str]) -> CallbackDefinition:
    """Substitute {variable_name} placeholders in callback payload string values."""
    safe_context = {k: str(v).replace("{", "{{").replace("}", "}}") for k, v in context.items()}

    new_payload: dict[str, Any] = {}
    for key, value in callback.payload.items():
        if isinstance(value, str):
            for ctx_key, ctx_value in safe_context.items():
                value = value.replace(f"{{{ctx_key}}}", ctx_value)
            value = value.replace("{{", "{").replace("}}", "}")
        new_payload[key] = value

    return CallbackDefinition(
        event_type=callback.event_type,
        action_type=callback.action_type,
        payload=new_payload,
    )


# ---------------------------------------------------------------------------
# Registry & Executor
# ---------------------------------------------------------------------------


class HookRegistry:
    """Thread-safe registry for managing callbacks keyed by event type."""

    def __init__(self) -> None:
        """Initialize the hook registry with thread-safe storage."""
        self._locks = defaultdict(RLock)
        self.callbacks = defaultdict(list)

    def register(self, event_type: str, callback: CallbackDefinition) -> None:
        """Register a callback for a specific event type."""
        with self._locks[event_type]:
            self.callbacks[event_type].append(callback)

    def get_callbacks(self, event_type: str) -> list[CallbackDefinition]:
        """Get a deep copy of all callbacks registered for a specific event type."""
        with self._locks[event_type]:
            return [deepcopy(cb) for cb in self.callbacks[event_type]]


class HookExecutor:
    """Executes registered callbacks for events."""

    def __init__(self, registry: HookRegistry) -> None:
        """Initialize the hook executor."""
        self.registry = registry
        self._handlers: dict[str, Any] = {}
        self.suggested_actions: list[dict[str, Any]] = []

    def register_handler(self, action_type: str, handler: Any) -> None:
        """Register a handler for a specific action type."""
        self._handlers[action_type] = handler

    def execute_event(self, event_type: str, context: dict[str, str] | None = None) -> None:
        """Execute all callbacks registered for the specified event type."""
        callbacks = self.registry.get_callbacks(event_type)
        if not callbacks:
            return

        if context:
            callbacks = [_substitute_context(cb, context) for cb in callbacks]

        for callback in callbacks:
            handler = self._handlers.get(callback.action_type)
            if handler is None:
                logging.warning(f"No handler registered for action_type: {callback.action_type}")
                continue
            self._execute_callback(callback, handler)

    def _execute_callback(self, callback: CallbackDefinition, handler: Any) -> None:
        """Execute a single callback using the appropriate handler."""
        try:
            handler.execute(callback)
        except Exception as e:
            logging.error(f"Handler failed for {callback.action_type} callback: {e}")


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


class ShellHandler:
    """Handler for executing shell commands securely."""

    def execute(self, callback: CallbackDefinition) -> dict[str, Any]:
        """Execute a shell command defined in the callback payload."""
        payload = callback.payload
        command = payload["command"]
        timeout = payload.get("timeout_seconds", 30)
        working_dir = payload.get("working_directory", ".")

        try:
            args = shlex.split(command)
            result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=working_dir)
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            logging.error(f"Shell command timed out after {timeout}s: {command}")
            return {
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds",
                "returncode": -1,
                "success": False,
                "error": "timeout",
            }
        except Exception as e:
            logging.error(f"Shell command execution failed: {e}")
            return {"stdout": "", "stderr": str(e), "returncode": -1, "success": False, "error": str(e)}


class WebhookHandler:
    """Handler for sending webhook notifications."""

    def execute(self, callback: CallbackDefinition) -> dict[str, Any]:
        """Execute a webhook notification defined in the callback payload."""
        payload = callback.payload.copy()

        url = payload.pop("url")
        method = payload.pop("method", "POST")
        headers = payload.pop("headers", {})
        timeout = payload.pop("timeout_seconds", 5)

        data_to_send = self._build_payload(callback.event_type, payload)
        return self._send_request(url, method, headers, timeout, data_to_send)

    def _build_payload(self, event_type: str, extra: dict[str, Any]) -> dict[str, Any]:
        """Build the webhook payload with required fields."""
        data = {
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            **extra,
        }
        if "sop_name" not in data:
            logging.warning("Webhook payload missing required 'sop_name' field. Adding 'unknown'.")
            data["sop_name"] = "unknown"
        return data

    def _send_request(self, url: str, method: str, headers: dict, timeout: int, data: dict) -> dict[str, Any]:
        """Send the HTTP request and handle errors."""
        try:
            if method.upper() == "POST":
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method.upper() == "PUT":
                response = requests.put(url, json=data, headers=headers, timeout=timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            response.raise_for_status()
            return {"success": True, "status_code": response.status_code, "response": response.text}
        except requests.exceptions.Timeout as e:
            logging.error(f"Webhook timeout after {timeout}s for {url}: {e}")
            return {"success": False, "error": "timeout", "details": f"Request timed out after {timeout} seconds"}
        except requests.exceptions.HTTPError as e:
            logging.error(f"Webhook HTTP error {e.response.status_code} for {url}: {e}")
            return {"success": False, "error": "http_error", "status_code": e.response.status_code, "details": str(e)}
        except requests.exceptions.RequestException as e:
            logging.error(f"Webhook request failed for {url}: {e}")
            return {"success": False, "error": "request_failed", "details": str(e)}
        except Exception as e:
            logging.error(f"Unexpected error in webhook handler: {e}")
            return {"success": False, "error": "unexpected", "details": str(e)}


_MAX_SUGGESTION_BYTES = 4096


class LLMSuggestionHandler:
    """Handler for adding LLM-suggested actions to tool responses."""

    def __init__(self, executor: HookExecutor) -> None:
        """Initialize with reference to HookExecutor to store suggestions."""
        self.executor = executor

    def execute(self, callback: CallbackDefinition) -> dict[str, Any]:
        """Add LLM suggestion to suggested_actions in HookExecutor."""
        payload = callback.payload

        if "title" not in payload:
            logging.error("LLM suggestion missing required 'title' field")
            return {"success": False, "error": "missing_title"}
        if "description" not in payload:
            logging.error("LLM suggestion missing required 'description' field")
            return {"success": False, "error": "missing_description"}

        suggestion = self._build_suggestion(payload)
        suggestion = self._truncate_if_needed(suggestion)
        self.executor.suggested_actions.append(suggestion)
        return {"success": True}

    def _build_suggestion(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Build the suggestion dict from payload."""
        suggestion: dict[str, Any] = {"title": payload["title"], "description": payload["description"]}
        if "action_command" in payload:
            suggestion["action_command"] = payload["action_command"]
        return suggestion

    def _truncate_if_needed(self, suggestion: dict[str, Any]) -> dict[str, Any]:
        """Truncate suggestion to fit within 4KB limit."""
        suggestion_json = json.dumps(suggestion)
        if len(suggestion_json) <= _MAX_SUGGESTION_BYTES:
            return suggestion

        original_size = len(suggestion_json)

        # Try truncating description
        base_size = len(json.dumps({"title": suggestion["title"], "description": ""}))
        available = _MAX_SUGGESTION_BYTES - base_size
        if available > 0:
            suggestion["description"] = suggestion["description"][:available]

        # Drop action_command if still too large
        if "action_command" in suggestion and len(json.dumps(suggestion)) > _MAX_SUGGESTION_BYTES:
            del suggestion["action_command"]

        # Ultimate fallback
        if len(json.dumps(suggestion)) > _MAX_SUGGESTION_BYTES:
            suggestion = {"title": suggestion["title"][:100], "description": ""}

        logging.warning(f"LLM suggestion truncated from {original_size} to {len(json.dumps(suggestion))} bytes")
        return suggestion


# ---------------------------------------------------------------------------
# MCP Server Integration (monkey-patches call_tool to fire hook events)
# ---------------------------------------------------------------------------


def _extract_context(tool_name: str, arguments: dict[str, Any], result_data: dict[str, Any]) -> dict[str, str]:
    """Build context variables from tool arguments and result."""
    ctx: dict[str, str] = {}
    for k, v in result_data.items():
        ctx[k] = str(v) if v is not None else ""
    for k, v in arguments.items():
        if v is not None:
            ctx[k] = str(v)
    return ctx


def _parse_result(result: Any) -> dict[str, Any]:
    """Parse a tool result into a dict for context extraction."""
    try:
        if isinstance(result, str):
            return json.loads(result)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, TypeError):
        pass
    return {}


def _fire_tool_event(executor: Any, name: str, ctx: dict[str, str]) -> None:
    """Fire the hook event for a tool call."""
    try:
        executor.execute_event(name, context=ctx)
        logging.info("Hook event '%s' fired", name)
    except Exception as e:
        logging.warning("Hook execution failed for '%s' event: %s", name, e)


def _fire_sop_completed(executor: Any, result_data: dict[str, Any], ctx: dict[str, str]) -> None:
    """Fire sop_completed event when run_sop reaches the last step."""
    try:
        current = result_data.get("current_step")
        total = result_data.get("total_steps")
        if current is not None and total is not None and int(current) == int(total):
            executor.execute_event("sop_completed", context=ctx)
            logging.info("Hook event 'sop_completed' fired")
    except Exception as e:
        logging.warning("Hook execution failed for 'sop_completed' event: %s", e)


def _inject_suggestions(executor: Any, result_data: dict[str, Any]) -> str | None:
    """Inject LLM suggestions into the result. Returns new JSON or None."""
    if not executor.suggested_actions:
        return None
    suggestions = list(executor.suggested_actions)
    executor.suggested_actions.clear()
    try:
        result_data["suggested_actions"] = suggestions
        logging.info("Injected %d suggested_action(s) into response", len(suggestions))
        return json.dumps(result_data)
    except Exception as e:
        logging.warning("Failed to inject suggested_actions: %s", e)
        return None


def install_hooks(mcp_server: Any, executor: Any | None) -> None:
    """Monkey-patch ``mcp_server.call_tool`` to fire hook events after each call.

    If *executor* is ``None`` this is a no-op.
    """
    if executor is None:
        return

    original_call_tool = mcp_server.call_tool

    async def _hooked_call_tool(name: str, arguments: dict[str, Any]) -> str:
        result = await original_call_tool(name, arguments)
        result_data = _parse_result(result)
        ctx = _extract_context(name, arguments, result_data)

        _fire_tool_event(executor, name, ctx)

        if name == "run_sop":
            _fire_sop_completed(executor, result_data, ctx)

        injected = _inject_suggestions(executor, result_data)
        if injected is not None:
            result = injected

        return result

    mcp_server.call_tool = _hooked_call_tool

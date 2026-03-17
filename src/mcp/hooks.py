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
from typing import Any, Dict, List, Literal, Optional

import requests


class SecurityError(Exception):
    """Exception raised when security validation fails for a callback."""

    pass


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
    payload: Dict[str, Any]


def hooks_enabled() -> bool:
    """Check whether the hook system should be active.

    Hooks are enabled when `SOP_HOOK_CONFIG` is set to a non-empty value.
    The value can be either a JSON string or a file path ending with '.json'.
    `SOP_HOOKS_ENABLED` is no longer required — having a config is sufficient.

    Returns:
        True if hooks should be active, False otherwise.
    """
    config = os.environ.get("SOP_HOOK_CONFIG", "").strip()
    return len(config) > 0


def parse_hook_config(config_str: str) -> List[CallbackDefinition]:
    """Parse hook configuration from JSON string or file path into CallbackDefinition objects.

    If config_str ends with '.json', it's treated as a file path and read from disk.
    Otherwise, it's parsed as a JSON string.

    Validates JSON structure and required fields (`event_type`, `action_type`, `payload`).
    Handles malformed JSON gracefully by returning an empty list.
    Performs security validation on callbacks.

    Args:
        config_str: JSON string or file path ending with '.json' containing hook configuration

    Returns:
        List of valid CallbackDefinition objects. Returns empty list if JSON is malformed
        or contains no valid definitions.
    """
    # Check if config_str is a file path (ends with .json)
    if config_str.strip().endswith('.json'):
        try:
            with open(config_str.strip(), 'r', encoding='utf-8') as f:
                config_str = f.read()
        except (OSError, IOError) as e:
            logging.warning(f"Failed to read hook config file '{config_str}': {e}")
            return []
    
    # Enforce 64KB maximum for hook configuration (Requirement 4.2)
    if len(config_str) > 64 * 1024:
        logging.warning("Hook configuration exceeds 64KB limit. Discarding.")
        return []

    try:
        config = json.loads(config_str)
    except json.JSONDecodeError:
        # Malformed JSON - return empty list per requirements
        return []

    if not isinstance(config, list):
        return []

    results: List[CallbackDefinition] = []

    # Check if security mode is enabled (default: true)
    secure_mode = os.environ.get("SOP_HOOKS_SECURE", "true").lower() != "false"

    for item in config:
        if not isinstance(item, dict):
            continue

        required_keys = {"event_type", "action_type", "payload"}
        if not required_keys.issubset(item.keys()):
            continue

        event_type = item["event_type"]
        action_type = item["action_type"]
        payload = item["payload"]

        # Validate action_type is one of the supported literals
        if action_type not in ("shell", "webhook", "llm"):
            continue

        # Ensure payload is a dict as expected by CallbackDefinition
        if not isinstance(payload, dict):
            continue

        # Create callback definition temporarily for security validation
        temp_callback = CallbackDefinition(
            event_type=event_type,
            action_type=action_type,  # type: ignore[arg-type] - validated above
            payload=payload,
        )

        # Perform security scanning (Requirement 6.3)
        try:
            validate_callback_security(temp_callback, secure_mode)
        except SecurityError as e:
            logging.warning(f"Skipping insecure callback: {e}")
            continue

        results.append(temp_callback)

    return results


def validate_callback_security(callback: CallbackDefinition, secure_mode: bool) -> None:
    """Validate callback for security risks.

    Implements Requirements: 6.3

    Args:
        callback: The callback definition to validate
        secure_mode: Whether strict security checks are enabled

    Raises:
        SecurityError: If callback is deemed insecure
    """
    if callback.action_type == "shell":
        # Validate shell command for dangerous patterns (Requirement 4.1)
        command = callback.payload.get("command", "")
        dangerous_patterns = [
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

        for pattern in dangerous_patterns:
            if pattern in command:
                raise SecurityError(f"Shell command contains prohibited pattern '{pattern}': {command}")

        # Additionally check for suspicious arguments
        if ">" in command or "<" in command:
            raise SecurityError(f"Shell command contains file redirection: {command}")

    elif callback.action_type == "webhook" and secure_mode:
        # Validate webhook URLs use HTTPS when security enabled (Requirement 4.1)
        url = callback.payload.get("url", "")
        if not url.startswith("https://"):
            raise SecurityError(f"Webhook URL must use HTTPS when security is enabled: {url}")


def _substitute_context(callback: CallbackDefinition, context: Dict[str, str]) -> CallbackDefinition:
    """Substitute {variable_name} placeholders in callback payload string values.

    Only string values in the payload dict are processed. Non-string values
    and nested dicts/lists are left unchanged. Unknown placeholders are left as-is.

    Context values are sanitized so that curly braces in user-provided content
    (e.g. feedback text, SOP content) cannot trigger further substitution.

    Args:
        callback: The callback definition to process
        context: Dict mapping variable names to their values

    Returns:
        New CallbackDefinition with substituted payload values
    """
    # Sanitize context values: escape braces so user content can't inject placeholders
    safe_context = {k: str(v).replace("{", "{{").replace("}", "}}") for k, v in context.items()}

    new_payload: Dict[str, Any] = {}
    for key, value in callback.payload.items():
        if isinstance(value, str):
            for ctx_key, ctx_value in safe_context.items():
                value = value.replace(f"{{{ctx_key}}}", ctx_value)
            # Unescape doubled braces back to single braces
            value = value.replace("{{", "{").replace("}}", "}")
        new_payload[key] = value

    return CallbackDefinition(
        event_type=callback.event_type,
        action_type=callback.action_type,
        payload=new_payload,
    )


class HookRegistry:
    """Thread-safe registry for managing callbacks keyed by event type.

    Uses per-event-type RLocks to allow concurrent access to different event types
    while ensuring thread safety for operations on the same event type.

    Implements Requirements: 1.1
    """

    def __init__(self):
        """Initialize the hook registry with thread-safe storage."""
        self._locks = defaultdict(RLock)
        self.callbacks = defaultdict(list)

    def register(self, event_type: str, callback: CallbackDefinition) -> None:
        """Register a callback for a specific event type.

        Args:
            event_type: The event type to register the callback for
            callback: The callback definition to register
        """
        with self._locks[event_type]:
            self.callbacks[event_type].append(callback)

    def get_callbacks(self, event_type: str) -> List[CallbackDefinition]:
        """Get a deep copy of all callbacks registered for a specific event type.

        Returns deep copies to prevent external modification of internal state.

        Args:
            event_type: The event type to retrieve callbacks for

        Returns:
            List of deep-copied callback definitions for the specified event type
        """
        with self._locks[event_type]:
            return [deepcopy(cb) for cb in self.callbacks[event_type]]


class HookExecutor:
    """Asynchronous hook execution framework with thread pool support.

    Executes registered callbacks concurrently using a thread pool.
    Continues execution after individual callback failures.

    Implements Requirements: 1.2, 1.3
    """

    def __init__(self, registry: HookRegistry):
        """Initialize the hook executor.

        Args:
            registry: HookRegistry instance to retrieve callbacks from
        """
        self.registry = registry
        self._handlers: Dict[str, Any] = {}
        self.suggested_actions: List[Dict[str, Any]] = []

    def register_handler(self, action_type: str, handler: Any) -> None:
        """Register a handler for a specific action type.

        Args:
            action_type: The action type (shell, webhook, llm) to register handler for
            handler: Handler object with execute(callback) method
        """
        self._handlers[action_type] = handler

    def execute_event(self, event_type: str, context: Optional[Dict[str, str]] = None) -> None:
        """Execute all callbacks registered for the specified event type.

        Runs each callback sequentially. Individual callback failures are logged
        but do not stop execution of other callbacks.

        Context variables are substituted into string values in callback payloads
        using {variable_name} syntax. For example, if context={"sop_name": "my_sop"},
        then a payload value of "echo {sop_name}" becomes "echo my_sop".

        Args:
            event_type: Event type to execute callbacks for
            context: Optional dict of variables to substitute into callback payloads
        """
        callbacks = self.registry.get_callbacks(event_type)
        if not callbacks:
            return

        # Substitute context variables into callback payloads
        if context:
            callbacks = [_substitute_context(cb, context) for cb in callbacks]

        for callback in callbacks:
            handler = self._handlers.get(callback.action_type)
            if handler is None:
                logging.warning(f"No handler registered for action_type: {callback.action_type}")
                continue

            self._execute_callback(callback, handler)

    def _execute_callback(self, callback: CallbackDefinition, handler: Any) -> None:
        """Execute a single callback using the appropriate handler.

        Args:
            callback: The callback definition to execute
            handler: The handler to use for execution

        Raises:
            Exception: Propagates only for logging purposes, does not stop overall execution
        """
        try:
            handler.execute(callback)
        except Exception as e:
            logging.error(f"Handler failed for {callback.action_type} callback: {e}")
            # Re-raise only for logging in execute_event; overall execution continues


class ShellHandler:
    """Handler for executing shell commands securely.

    Uses subprocess.run with shell=False to prevent command injection.
    Captures stdout, stderr, and return code. Enforces timeout handling.

    Implements Requirements: 3.1, 3.2, 3.3
    """

    def execute(self, callback: CallbackDefinition) -> Dict[str, Any]:
        """Execute a shell command defined in the callback payload.

        Args:
            callback: CallbackDefinition with action_type="shell" and payload
                     containing "command", optional "timeout_seconds",
                     optional "working_directory"

        Returns:
            Dict containing:
                - stdout: Captured standard output
                - stderr: Captured standard error
                - returncode: Process exit code
                - success: True if returncode == 0
                - error: Optional error message if execution failed
        """
        payload = callback.payload
        command = payload["command"]
        timeout = payload.get("timeout_seconds", 30)
        working_dir = payload.get("working_directory", ".")

        try:
            # Use shlex to properly split command into arguments
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
    """Handler for sending webhook notifications.

    Sends HTTP POST requests to configured URLs with enriched payload.
    Handles HTTP errors and network failures gracefully.

    Implements Requirements: 4.1, 4.2
    """

    def execute(self, callback: CallbackDefinition) -> Dict[str, Any]:
        """Execute a webhook notification defined in the callback payload.

        Args:
            callback: CallbackDefinition with action_type="webhook" and payload
                     containing "url", optional "method", "headers",
                     "timeout_seconds", and other data fields

        Returns:
            Dict containing:
                - success: bool indicating if request succeeded
                - status_code: HTTP status code (if successful)
                - response: response text (if successful)
                - error: error type if failed
                - details: error details
        """
        payload = callback.payload.copy()  # avoid modifying original

        # Extract handler configuration, removing from data to send
        url = payload.pop("url")
        method = payload.pop("method", "POST")
        headers = payload.pop("headers", {})
        timeout = payload.pop("timeout_seconds", 5)

        # Enrich data with required fields
        data_to_send = {
            "event_type": callback.event_type,
            "timestamp": datetime.now().isoformat(),
            **payload,  # includes sop_name if present, plus other fields
        }

        # Check if sop_name is present as required by requirements
        if "sop_name" not in data_to_send:
            logging.warning("Webhook payload missing required 'sop_name' field. Adding 'unknown'.")
            data_to_send["sop_name"] = "unknown"

        try:
            if method.upper() == "POST":
                response = requests.post(url, json=data_to_send, headers=headers, timeout=timeout)
            elif method.upper() == "PUT":
                response = requests.put(url, json=data_to_send, headers=headers, timeout=timeout)
            # Add support for other methods if needed, but requirement says POST
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


class LLMSuggestionHandler:
    """Handler for adding LLM-suggested actions to tool responses.

    Adds payload as structured recommendations to suggested_actions.
    Validates required fields (title, description).

    Implements Requirements: 5.1, 5.2, 5.3
    """

    def __init__(self, executor: HookExecutor):
        """Initialize with reference to HookExecutor to store suggestions.

        Args:
            executor: HookExecutor instance to store suggested actions
        """
        self.executor = executor

    def execute(self, callback: CallbackDefinition) -> Dict[str, Any]:
        """Add LLM suggestion to suggested_actions in HookExecutor.

        Args:
            callback: CallbackDefinition with action_type="llm" and payload
                     containing required "title" and "description", optional "action_command"

        Returns:
            Dict with success status
        """
        payload = callback.payload

        # Validate required fields
        if "title" not in payload:
            logging.error("LLM suggestion missing required 'title' field")
            return {"success": False, "error": "missing_title"}
        if "description" not in payload:
            logging.error("LLM suggestion missing required 'description' field")
            return {"success": False, "error": "missing_description"}

        # Create suggestion object
        suggestion = {"title": payload["title"], "description": payload["description"]}

        # Add optional action_command if present
        if "action_command" in payload:
            suggestion["action_command"] = payload["action_command"]

        # Add to executor's suggested_actions
        # Truncate oversized LLM suggestions to 4KB (Requirement 4.2)
        suggestion_json = json.dumps(suggestion)
        if len(suggestion_json) > 4 * 1024:
            # Truncate description to reduce size while keeping title
            # Calculate space available for description (title + base structure)
            base_size = len(json.dumps({"title": suggestion["title"], "description": ""}))
            available = 4096 - base_size
            if available > 0:
                truncated_desc = suggestion["description"][:available]
                suggestion["description"] = truncated_desc
                if "action_command" in suggestion:
                    # Remove action_command to save space if still over
                    suggestion_str = json.dumps(suggestion)
                    if len(suggestion_str) > 4096:
                        del suggestion["action_command"]
                        suggestion_str = json.dumps(suggestion)
                        if len(suggestion_str) > 4096:
                            # Ultimate fallback: minimal suggestion
                            suggestion = {"title": suggestion["title"][:100], "description": ""}
            else:
                # Even title takes too much (unlikely), minimal suggestion
                suggestion = {"title": suggestion["title"][:100], "description": ""}

            new_size = len(json.dumps(suggestion))
            logging.warning(f"LLM suggestion truncated from {len(suggestion_json)} to {new_size} bytes")

        self.executor.suggested_actions.append(suggestion)

        return {"success": True}

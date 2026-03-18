# Hook System Documentation

## Overview

The hook system enables external actions to be automatically triggered when any MCP tool is called. This allows integration with external tools, notifications, and automated responses without modifying core functionality.

## Available Events

Event names match tool names directly. Hooks fire on **every** tool call, not just successful completions.

| Event Name | Triggered When | Description |
|------------|----------------|-------------|
| `run_sop` | Every `run_sop()` call | Fires on every step, not just completion |
| `publish_sop` | Every `publish_sop()` call | Fires when SOP publishing is attempted |
| `submit_sop_feedback` | Every `submit_sop_feedback()` call | Fires when feedback submission is attempted |
| `sop_completed` | `run_sop()` reaches final step | Bonus event: fires only when `current_step == total_steps` |

## Context Variables

Each event provides context variables from both the tool arguments and the tool result. You can use any field with `{variable_name}` syntax in your hook payloads.

### `run_sop`

| Variable | Source | Description |
|----------|--------|-------------|
| `{sop_name}` | arg + result | Name of the SOP |
| `{sop_version}` | result | Version that was executed |
| `{total_steps}` | result | Total number of steps |
| `{current_step}` | result | Current step number |
| `{step_output}` | arg | Output from the completed step (braces escaped) |
| `{instruction}` | result | Step instruction text |

### `sop_completed`

Same variables as `run_sop` — fires only when `current_step == total_steps`.

### `publish_sop`

| Variable | Source | Description |
|----------|--------|-------------|
| `{sop_name}` | result | Name of the published SOP |
| `{version}` | result | New version number |
| `{change_type}` | arg + result | Semver bump type (`major`, `minor`, `patch`) |
| `{total_steps}` | result | Total number of steps |
| `{title}` | result | SOP title |
| `{content}` | arg | Full SOP markdown content (braces escaped) |

### `submit_sop_feedback`

| Variable | Source | Description |
|----------|--------|-------------|
| `{sop_name}` | arg + result | Name of the SOP |
| `{sop_version}` | result | Version of the SOP |
| `{timestamp}` | result | UTC timestamp of submission |
| `{feedback}` | arg | Full feedback text (braces escaped) |

### Usage Example

```yaml
- event_type: run_sop
  action_type: shell
  payload:
    command: "echo SOP {sop_name} v{sop_version} step {current_step}/{total_steps}"
```

Or in JSON:

```json
{
  "event_type": "run_sop",
  "action_type": "shell",
  "payload": {
    "command": "echo SOP {sop_name} v{sop_version} step {current_step}/{total_steps}"
  }
}
```

Unknown placeholders like `{unknown_var}` are left as-is.

## Action Types

### 1. Shell Actions

Execute shell commands securely with output capture.

**Payload Structure:**
```json
{
  "command": "string",
  "timeout_seconds": 30,
  "working_directory": "."
}
```

**Security Features:**
- `shell=False` prevents command injection
- Dangerous patterns blocked (`;`, `|`, `curl`, `wget`, etc.)
- File redirection (`>`, `<`) prohibited

### 2. Webhook Actions

Send HTTP POST/PUT requests to external endpoints.

**Payload Structure:**
```json
{
  "url": "string",
  "method": "POST",
  "headers": { "key": "value" },
  "timeout_seconds": 5
}
```

Automatically enriches payload with `event_type`, `timestamp`, and `sop_name`.

When `SOP_HOOKS_SECURE=true` (default), URLs must use `https://`.

### 3. LLM Suggestion Actions

Add suggested actions to tool responses for AI assistance.

**Payload Structure:**
```json
{
  "title": "string",
  "description": "string",
  "action_command": "string"
}
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SOP_HOOK_CONFIG` | Yes | — | Path to a `.json`, `.yaml`, or `.yml` file containing hook definitions, or an inline JSON/YAML string. Hooks are enabled when this is set. |
| `SOP_HOOKS_SECURE` | No | `true` | HTTPS-only webhooks, shell command validation. Set to `false` to disable. |

### Hook Configuration Format

YAML (recommended for readability):

```yaml
- event_type: run_sop
  action_type: shell
  payload:
    command: "echo {sop_name}"
```

JSON equivalent:

```json
[
  {
    "event_type": "run_sop",
    "action_type": "shell",
    "payload": { "command": "echo {sop_name}" }
  }
]
```

## Complete Examples

Example hook configurations are available in [`examples/`](../examples/):

| File | Description |
|------|-------------|
| [`shell.hook.json`](../examples/shell.hook.json) | Shell commands that log event details |
| [`webhook.hook.json`](../examples/webhook.hook.json) | Webhook POSTs to external endpoints |
| [`llm.hook.json`](../examples/llm.hook.json) | LLM suggestions surfaced in tool responses (JSON) |
| [`llm.hook.yaml`](../examples/llm.hook.yaml) | LLM suggestions surfaced in tool responses (YAML) |
| [`mixed.hook.json`](../examples/mixed.hook.json) | Combines shell + webhook + llm on the same events |

### Quick Start

```bash
# YAML
export SOP_HOOK_CONFIG=/path/to/skills/sop-mcp-configuration/examples/llm.hook.yaml

# JSON
export SOP_HOOK_CONFIG=/path/to/skills/sop-mcp-configuration/examples/llm.hook.json
```

## Error Handling

- Hook failures never stop core operations — errors are logged
- Malformed JSON/YAML config returns empty hook list (system stays disabled)
- Insecure hooks are skipped with warnings

## Security Best Practices

1. Security is on by default (`SOP_HOOKS_SECURE=true`)
2. Only HTTPS webhook endpoints allowed when security enabled
3. Shell commands are validated against dangerous patterns
4. Monitor logs for hook execution errors

## Testing Hooks

```bash
export SOP_HOOK_CONFIG=/path/to/skills/sop-mcp-configuration/examples/shell.hook.json
```

All hook functionality is covered by property-based tests in `test_hooks.py` and e2e tests in `test_e2e_hooks.py`.

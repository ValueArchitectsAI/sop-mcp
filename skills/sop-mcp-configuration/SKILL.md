---
name: sop-mcp-configuration
description: Configure SOP-MCP server for step-by-step SOP execution in any MCP client
version: 1.0.0
author: Value Architects
tags: [mcp, automation, sop, configuration]
activation: manual
---

# SOP-MCP Configuration Skill

## When to Use This Skill
Use this skill when you need to:
- Configure SOP-MCP server in any MCP client
- Set up custom SOP storage locations
- Configure automation hooks for SOP execution
- Troubleshoot MCP server configuration

## Quick Start

### Basic Configuration
Add this to your MCP client's configuration file:

```json
{
  "mcpServers": {
    "sop-mcp": {
      "command": "uvx",
      "args": ["sop-mcp"]
    }
  }
}
```

### With Custom Storage
```json
{
  "mcpServers": {
    "sop-mcp": {
      "command": "uvx",
      "args": ["sop-mcp"],
      "env": {
        "SOP_STORAGE_DIR": "/path/to/your/sops"
      }
    }
  }
}
```

### With Hooks Enabled
```json
{
  "mcpServers": {
    "sop-mcp": {
      "command": "uvx",
      "args": ["sop-mcp"],
      "env": {
        "SOP_STORAGE_DIR": "/path/to/your/sops",
        "SOP_HOOK_CONFIG": "/path/to/your/hooks.yaml"
      }
    }
  }
}
```

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `SOP_STORAGE_DIR` | Directory for SOP storage | Bundled directory (ephemeral) |
| `SOP_HOOK_CONFIG` | Path to a `.json`, `.yaml`, or `.yml` file containing hook definitions | `null` (hooks disabled) |
| `SOP_HOOKS_SECURE` | Enforce HTTPS webhooks and command validation | `"true"` |

---

## Hook Examples

Pre-built hook configurations for common workflows:

| File | Purpose |
|------|---------|
| [`examples/shell.hook.json`](examples/shell.hook.json) | Log SOP execution to terminal |
| [`examples/webhook.hook.json`](examples/webhook.hook.json) | Send HTTP notifications on completion |
| [`examples/llm.hook.json`](examples/llm.hook.json) | Surface AI suggestions during execution (JSON) |
| [`examples/llm.hook.yaml`](examples/llm.hook.yaml) | Surface AI suggestions during execution (YAML) |
| [`examples/mixed.hook.json`](examples/mixed.hook.json) | Combine shell + webhook + llm hooks |

For full hook system documentation, see [`documentation/hooks.md`](docs/hooks-system.md).

---

## Verification

After configuring, test with:
```
run_sop(sop_name="sop_creation_guide")
```

Expected output:
```
Step 1 of 8: [instructions...]
```

---

## Troubleshooting

### Server won't start
- Check `uvx` is installed: `which uvx`
- Verify Python 3.10+: `python --version`

### Tools not appearing
- Verify JSON syntax in your configuration
- Restart your MCP client after config changes

### Hooks not firing
- Verify `SOP_HOOK_CONFIG` points to a valid `.json`, `.yaml`, or `.yml` file path
- Ensure the file exists and is readable
- Check server logs for hook errors

---

## References
- [Project README](../../README.md)
- [Hook System Documentation](docs/hooks-system.md)
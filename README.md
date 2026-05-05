# sop-mcp

[![PyPI](https://img.shields.io/pypi/v/sop-mcp?style=flat-square)](https://pypi.org/project/sop-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/sop-mcp?style=flat-square)](https://pypi.org/project/sop-mcp/)
[![License](https://img.shields.io/pypi/l/sop-mcp?style=flat-square)](https://github.com/ValueArchitectsAI/sop-mcp/blob/main/LICENSE)

An MCP server that brings process automation to AI agents through Standard Operating Procedures.

LLMs are powerful but unpredictable when executing multi-step processes — they skip steps, summarize instead of act, and lose track of where they are. sop-mcp solves this by delivering procedures one step at a time, forcing the agent to execute each step and provide concrete output before advancing. This turns SOPs into a control mechanism that makes LLM behavior predictable and auditable.

The result: agents that follow processes the way humans do — step by step, with reasoning enforced at each level.

This approach aligns with [Agent SOPs](https://github.com/strands-agents/agent-sop) — a standardized markdown format for defining AI agent workflows using RFC 2119 requirement levels (MUST, SHOULD, MAY). sop-mcp adds the execution layer: an MCP server that delivers these procedures one step at a time and enforces completion before advancing.

## Install

|                                                                                            Kiro                                                                                            |                                                                                         Cursor                                                                                         |                                                                                                                                                      VS Code                                                                                                                                                      |
| :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------: | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------: | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------: |
| [![Add to Kiro](https://kiro.dev/images/add-to-kiro.svg)](https://kiro.dev/launch/mcp/add?name=sop-mcp&config=%7B%22command%22%3A%20%22uvx%22%2C%20%22args%22%3A%20%5B%22sop-mcp%22%5D%7D) | [![Install MCP Server](https://cursor.com/deeplink/mcp-install-light.svg)](https://cursor.com/en/install-mcp?name=sop-mcp&config=eyJjb21tYW5kIjogInV2eCIsICJhcmdzIjogWyJzb3AtbWNwIl19) | [![Install on VS Code](https://img.shields.io/badge/Install_on-VS_Code-007ACC?style=flat-square&logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=sop-mcp&config=%7B%22type%22%3A%20%22stdio%22%2C%20%22command%22%3A%20%22uvx%22%2C%20%22args%22%3A%20%5B%22sop-mcp%22%5D%7D) |

Or add manually:

```json
{
  "mcpServers": {
    "sop-mcp": {
      "command": "uvx",
      "args": ["sop-mcp"],
      "env": { "SOP_STORAGE_DIR": "/path/to/your/sops" }
    }
  }
}
```

## How It Works

Every session starts the same way — discover what's available, then execute.

```
list_resources()                                     → catalog of sop:// URIs
run_sop(sop_name="sop_creation_guide")               → Step 1 + instructions
run_sop(..., current_step=1, step_output="...")      → Step 2
run_sop(..., current_step=2, step_output="...")      → Step 3
  ...
run_sop(..., current_step=N, step_output="...")      → Completion
```

Each response tells the agent to *execute* the step — not just read it.

## Bundled SOPs

Four SOPs ship with the server so new users can try `run_sop` immediately:

| SOP                         | What it does                                                             |
| --------------------------- | ------------------------------------------------------------------------ |
| `sop_creation_guide`        | Step-by-step guide for authoring new SOPs with RFC 2119 requirements     |
| `code_review_process`       | Standard code review workflow — prepare, review, address feedback, merge |
| `employee_onboarding_setup` | IT setup for a new hire — alias, email, hardware selection               |
| `user_onboarding_process`   | Provision identity, application access, and welcome package              |

Storage default: `~/.sop_mcp` (seeded from the bundled SOPs on first run). Override with `SOP_STORAGE_DIR`.

## Tools

| Tool                  | Purpose                                                |
| --------------------- | ------------------------------------------------------ |
| `list_resources`      | Discover available SOPs (built in to every MCP client) |
| `read_resource`       | Read an SOP's full content before executing it         |
| `run_sop`             | Execute an SOP step by step                            |
| `publish_sop`         | Create or update an SOP                                |
| `submit_sop_feedback` | Record improvement suggestions                         |

Full parameter reference: [docs/mcp-reference.md](docs/mcp-reference.md)

## Documentation

| Audience   | Resource                                                                                             |
| ---------- | ---------------------------------------------------------------------------------------------------- |
| AI tools   | [`llms.txt`](llms.txt) — auto-discovered server description                                          |
| Users      | [`skills/sop-mcp-usage/`](skills/sop-mcp-usage/SKILL.md) — how to use                                |
| Operators  | [`skills/sop-mcp-configuration/`](skills/sop-mcp-configuration/SKILL.md) — install, configure, hooks |
| Developers | [`CONTRIBUTING.md`](CONTRIBUTING.md) — build, test, design decisions                                 |
| Reference  | [`docs/mcp-reference.md`](docs/mcp-reference.md) — full tool schemas                                 |

## Development

```bash
uv sync              # install dependencies
uv run pytest        # run tests
uv run sop-mcp       # start server locally
uv run python scripts/generate_docs.py  # regenerate docs
```

## License

MIT

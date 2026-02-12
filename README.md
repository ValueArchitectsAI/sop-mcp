# sop-mcp

An MCP server that guides AI agents through Standard Operating Procedures (SOPs) step by step using RFC 2119 requirement levels.

## Architecture

```mermaid
sequenceDiagram
    participant Agent as AI Agent<br/>(Claude/Kiro)
    participant Server as sop-mcp<br/>Server
    participant Storage as Storage Backend<br/>(configurable)

    Note over Agent,Storage: Initialize
    Agent->>Server: run_sop_creation_guide()
    Note right of Agent: No args = start from beginning
    Server->>Storage: Load latest version
    Storage-->>Server: SOP content
    Server-->>Agent: Step 1 + overview<br/>+ instruction to execute

    Note over Agent,Storage: Execute Steps
    loop For each step
        Agent->>Agent: Execute step actions<br/>(file ops, shell, code gen)
        Agent->>Server: run_sop_creation_guide(current_step=N)
        Server-->>Agent: Step N+1 content<br/>+ instruction to execute
    end

    Note over Agent,Storage: Complete
    Agent->>Server: run_sop_creation_guide(current_step=last)
    Server-->>Agent: is_complete: true<br/>"SOP completed!"
    Agent->>Agent: Summarize results
```

## Tools

| Tool | Description |
|------|-------------|
| `explain_sop` | List all available SOPs, or get details about a specific one |
| `publish_sop` | Publish a new or updated SOP with automatic semver bumping |
| `submit_sop_feedback` | Submit improvement feedback for a specific SOP |
| `run_<sop_name>` | Step-by-step execution of an SOP (one tool per SOP, registered dynamically) |

## How It Works

1. SOPs are stored as versioned markdown files in `<storage_dir>/<sop_name>/v<version>.md`
2. On startup, the server initializes the configured storage backend and registers a `run_<sop_name>` tool for each discovered SOP
3. New SOPs can be published at runtime via `publish_sop` (server restart needed to register the new tool)

## Creating New SOPs

The server ships with a built-in `run_sop_creation_guide` tool that walks agents (and humans) through the full SOP authoring process. Here's how it works:

1. The agent calls `run_sop_creation_guide()` with no arguments to start from step 1
2. The server returns the first step's content along with an instruction telling the agent to execute the actions described (not just read them)
3. The agent performs the step's actions — gathering information, drafting sections, applying RFC 2119 keywords, etc.
4. Once done, the agent calls `run_sop_creation_guide(current_step=1)` to advance to step 2
5. This continues until all steps are complete (`is_complete: true`)
6. At the final step, the agent publishes the finished SOP using `publish_sop`

The creation guide covers:

- **Step 1**: Prepare — gather process info, identify stakeholders, collect existing docs
- **Step 2**: Structure — define metadata, scope, parameters, and document skeleton
- **Step 3**: Document — write detailed step-by-step instructions with decision points
- **Step 4**: Apply RFC 2119 — classify each action as MUST, SHOULD, or MAY
- **Step 5**: Enrich — add troubleshooting, best practices, examples, and references
- **Step 6**: Review — validate with SMEs and end users, run through the checklist
- **Step 7**: Finalize — incorporate feedback, publish via `publish_sop`, notify stakeholders
- **Step 8**: Maintain — schedule reviews, collect feedback, keep the SOP current

After publishing, restart the server to register the new `run_<sop_name>` tool for the freshly created SOP.

### Tool Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `current_step` | int | no | Step to advance from. Omit to start from step 1. |
| `version` | string | no | Semver version to use (e.g. `"1.0"`). Defaults to latest. |

The response includes an `instruction` field that tells the agent to execute the step content using its available tools, not just summarize it.

## SOP Naming Convention

| Element | Format | Example |
|---------|--------|---------|
| Folder name | lowercase, underscores | `sop_creation_guide` |
| Document ID | same as folder name | `sop_creation_guide` |
| Tool name | `run_` + folder name | `run_sop_creation_guide` |
| Version file | `v` + semver | `v1.0.0.md` |

The Document ID is specified in the markdown via `**Document ID**: sop_creation_guide` and must contain at least 3 words.

## Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Usage

### With an MCP client

Add to your MCP client configuration:

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

### Local development

```bash
uv run sop-mcp
```

### Running tests

```bash
uv run pytest
```

## Storage Configuration

By default, SOPs are stored in the bundled `src/sops/` directory. This storage is marked as ephemeral — the server will warn you when publishing SOPs or submitting feedback that data may be lost if the package cache is refreshed (e.g. when running via `uvx`).

To persist SOPs across cache refreshes, set the `SOP_STORAGE_DIR` environment variable to a durable path. When set, bundled SOPs are automatically seeded into that directory on first run.

| Variable | Description | Default |
|---|---|---|
| `SOP_STORAGE_DIR` | Persistent storage directory path | Bundled `src/sops/` (ephemeral) |

### Example: Custom Storage Directory

```json
{
  "mcpServers": {
    "sop-mcp": {
      "command": "uvx",
      "args": ["sop-mcp"],
      "env": {
        "SOP_STORAGE_DIR": "/path/to/my/sops"
      }
    }
  }
}
```

## Writing an SOP

Every SOP markdown file must include:

- A level-1 heading (`# Title`)
- A `**Document ID**:` field with a lowercase underscore-separated name (min 3 words)
- A `**Version:**` field
- An `## Overview` section
- One or more `### Step N:` sections

Use RFC 2119 keywords (MUST, SHOULD, MAY) to define requirement levels. Each step SHOULD include a `**Time Estimate:**` field with the expected duration in minutes (e.g. `**Time Estimate:** 30 minutes`). Run the built-in `run_sop_creation_guide` tool for guided SOP creation.

## Publishing an SOP

Call the `publish_sop` tool with the full markdown content and a `change_type`:

- `major` — breaking change (1.2.0 → 2.0.0)
- `minor` — new feature (1.2.0 → 1.3.0)
- `patch` — bugfix (1.2.0 → 1.2.1)

New SOPs start at v1.0.0 regardless of change_type.

## License

MIT

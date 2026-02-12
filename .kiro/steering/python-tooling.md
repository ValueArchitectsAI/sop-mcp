---
title: Project Tooling Requirements
inclusion: always
---

# Project Tooling Requirements

## Python Tooling (uv)

This project MUST use `uv` for all Python-related commands.

### Requirements

- **MUST** use `uv run` to execute Python scripts and tools
- **MUST** use `uv pip` for package management
- **MUST NOT** use bare `pip` or `python` commands directly
- **SHOULD** use `uv sync` to synchronize dependencies

### Examples

```bash
# Running tests
uv run pytest

# Running a specific test file
uv run pytest tests/test_storage.py

# Installing dependencies
uv pip install -e .

# Syncing dependencies
uv sync
```

## Running the MCP Server

This project is an MCP server that runs via stdio transport using uvx.

### Local Development

```bash
# Run the MCP server locally
uv run sop-mcp
```

### Usage with uvx

The server can be run via uvx once published:

```bash
uvx sop-mcp
```

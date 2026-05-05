# Contributing to sop-mcp

## Project Layout

```
src/sop_mcp/
├── server.py              # MCP server entrypoint, tool registration
├── hooks.py               # Hook system (shell, webhook, LLM suggestions)
├── tools/
│   ├── run_sop.py         # Step-by-step SOP execution
│   ├── publish_sop.py     # Create/update SOPs
│   └── submit_sop_feedback.py  # Append feedback
├── utils/
│   ├── sop_parser.py      # SOP markdown parsing (frontmatter + steps)
│   ├── storage.py         # LocalFilesystemBackend (recursive scan)
│   ├── resource_registration.py  # sop:// MCP resource mapping
│   └── stdiomcp/          # Lightweight JSON-RPC stdio server
└── resources/             # Bundled SOPs (seeded into new storage dirs)

tests/                     # All E2E via FastMCP Client over stdio
scripts/
└── generate_docs.py       # Auto-generates docs/mcp-reference.md + llms.txt
```

## Build & Run

```bash
uv sync                        # install dependencies
uv run pre-commit install      # wire up lint + doc-regen hooks
uv run pytest                  # run tests (80 tests, ~9s)
uv run sop-mcp                 # start server (stdio transport)
uv run ruff check src/         # lint
uv run ruff format src/        # format
uv run python scripts/generate_docs.py  # regenerate docs
```

The pre-commit hook regenerates `docs/mcp-reference.md` and `llms.txt`
whenever `src/sop_mcp/**/*.py` or `scripts/generate_docs.py` changes, so
the auto-generated docs can't drift from the server.

## Testing

All tool tests use FastMCP Client over stdio subprocess — real MCP protocol, isolated storage per test via `SOP_STORAGE_DIR` pointing to `tmp_path`.

```bash
uv run pytest tests/test_mcp_run_sop.py      # run_sop tool
uv run pytest tests/test_mcp_publish_sop.py  # publish_sop tool
uv run pytest tests/test_hook_system.py      # hooks (shell, webhook, LLM)
```

Pattern for writing tests:
```python
async def test_something(mcp_transport):
    """Single behavior, clear intent."""
    async with Client(mcp_transport) as client:
        result = await client.call_tool("run_sop", {"sop_name": "..."})
        data = json.loads(result.content[0].text)
        assert data["sop_name"] == "..."
```

## Adding Parameter Descriptions

Use `typing.Annotated` — descriptions flow into the MCP JSON Schema automatically:

```python
from typing import Annotated

def handler(
    sop_name: Annotated[str, "Name of the SOP to execute"],
) -> dict[str, Any]:
```

## Commit Conventions

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new tool           → minor version bump
fix: handle edge case        → patch version bump
feat!: breaking change       → major version bump
docs/test/chore/refactor     → no version bump
```

## Key Design Decisions

1. **Step-at-a-time** — Agents see one step, must execute it, then advance. Prevents skipping.
2. **Version is informational** — Stored in frontmatter, returned in responses, but not selectable by callers.
3. **Storage is config** — `SOP_STORAGE_DIR` determines where SOPs live. No path parameter on tools.
4. **Hooks via call_tool** — All tool calls route through `call_tool` so hooks fire for both in-process and stdio clients.
5. **Feedback is hidden** — `.feedback.jsonl` lives in the SOP folder but isn't exposed as a resource.

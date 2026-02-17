# AGENT.md — sop-mcp

You are working on `sop-mcp`, an MCP server that walks AI agents through Standard Operating Procedures one step at a time.

## What This Project Does

SOPs are markdown documents with numbered steps. This server exposes each SOP as an MCP tool. When an agent calls the tool, it gets one step back. It must execute that step, then call the tool again to advance. The agent cannot skip ahead or see the full document at once.

This matters because agents tend to summarize or skip steps when given a full procedure. Feeding steps one at a time forces actual execution.

## Project Layout

```
src/
├── server.py                  # MCP server, tool handlers, dynamic registration
├── sops/                      # SOP storage (one folder per SOP)
│   └── sop_creation_guide/
│       ├── v1.0.md            # versioned SOP document
│       └── feedback.md        # collected user feedback
└── utils/
    ├── __init__.py            # re-exports
    ├── sop_parser.py          # SOP class, markdown parsing, versioning
    ├── storage_backend.py     # StorageBackend protocol (interface)
    └── storage_local.py       # LocalFilesystemBackend implementation

tests/
├── test_handler.py            # server tool tests (async, FastMCP)
├── test_parser.py             # parser unit tests
└── test_storage_backend.py    # property-based storage tests (hypothesis)
```

## Naming Convention

Everything derives from the folder name. No mapping logic, no transformations.

| Element | Rule | Example |
|---------|------|---------|
| Folder | lowercase, underscores, min 3 words | `sop_creation_guide` |
| Document ID | same as folder | `sop_creation_guide` |
| Tool name | `run_` + folder | `run_sop_creation_guide` |
| Version file | `v` + semver + `.md` | `v1.0.md`, `v2.1.0.md` |

The Document ID is declared in the markdown: `**Document ID**: sop_creation_guide`

The regex enforcing this: `[a-z][a-z0-9]*(?:_[a-z0-9]+){2,}` — starts with a letter, at least 3 underscore-separated segments.

## Tools

### Static tools (always registered)

`publish_sop(content, change_type)` — Validates markdown, auto-bumps version, writes to storage. Returns a reminder to restart the server. `change_type` is `major`, `minor`, or `patch`.

`submit_sop_feedback(sop_name, feedback)` — Appends timestamped feedback to `{sop_name}/feedback.md`. Intended to be offered to the user after completing an SOP run.

### Dynamic tools (one per SOP, registered at startup)

`run_{folder_name}(current_step?, version?)` — Step-by-step execution.

- No args → returns step 1 + overview
- `current_step=N` → returns step N+1 (meaning: "I finished step N, give me the next one")
- `current_step=total` → returns last step with `is_complete: true`
- `version="1.0"` → pins to a specific version instead of latest

Every response includes an `instruction` field that explicitly tells the agent to execute the step content, not just read it.

## Step Execution Flow

```
Agent calls run_sop_creation_guide()
  → Server returns step 1 + overview + instruction
Agent executes step 1 actions
Agent calls run_sop_creation_guide(current_step=1)
  → Server returns step 2 + instruction
Agent executes step 2 actions
  ... repeats ...
Agent calls run_sop_creation_guide(current_step=8)
  → Server returns step 8 with is_complete=true
Agent summarizes, optionally asks user for feedback
```

The `instruction` field contains:
```
You are now executing Step N of M. You MUST perform ALL actions described below.
Do NOT just summarize or describe them — actually carry them out using your
available tools...
```

On the final step, it also prompts the agent to offer the user a chance to submit feedback via `submit_sop_feedback`.

## Storage Architecture

The server uses a `StorageBackend` protocol (defined in `storage_backend.py`) with a single implementation: `LocalFilesystemBackend` (in `storage_local.py`).

### Resolution order

1. If `SOP_STORAGE_DIR` env var is set → use that path, seed bundled SOPs into it, not ephemeral
2. Otherwise → use the bundled `src/sops/` directory, marked as ephemeral

### Ephemeral warning

When the backend is ephemeral (no `SOP_STORAGE_DIR`), `publish_sop` and `submit_sop_feedback` responses include a warning that data may be lost on package cache refresh.

### Seeding

When using a custom `SOP_STORAGE_DIR`, the backend copies bundled SOPs into it on first use (only if the target directory has no SOPs yet). Only versioned files are copied, not feedback files.

## SOP Markdown Structure

Required elements for a valid SOP:

```markdown
# Title                                    ← level-1 heading (required)

## Document Information
- **Document ID**: my_sop_name             ← lowercase, underscores, 3+ words (required)
- **Version**: 1.0.0                       ← semver (required)

## Overview                                ← required section
Description of what this SOP does.

## Prerequisites                           ← optional section
- Any general prerequisites...

**Required MCP Servers** (should):         ← SHOULD-level field
- server_name
- another_server — optional description

### Step 1: First Step Title               ← at least one step required
Step content with RFC 2119 keywords...

### Step 2: Second Step Title
More content...
```

Each step SHOULD include a `**Time Estimate:**` field.

The `## Prerequisites` section SHOULD include a `**Required MCP Servers**` field listing MCP servers needed for execution.

RFC 2119 keywords define requirement levels within steps.

## RFC 2119 Requirement Levels

All SOPs use these keywords. Use them with care and sparingly.

| Keyword | Meaning |
|---------|---------|
| **MUST** / **REQUIRED** / **SHALL** | Absolute requirement. Non-negotiable. |
| **MUST NOT** / **SHALL NOT** | Absolute prohibition. Never allowed. |
| **SHOULD** / **RECOMMENDED** | Strong recommendation. Valid reasons may exist to deviate, but full implications must be understood first. |
| **SHOULD NOT** / **NOT RECOMMENDED** | Discouraged. Valid reasons may exist when the behavior is acceptable, but weigh carefully. |
| **MAY** / **OPTIONAL** | Truly optional. Implementations with or without the option must interoperate. |

Guidelines:
- MUST only be used where required for interoperation or to limit harmful behavior
- Do not use MUST to impose a particular method where not required for interoperability
- Consider security implications when not following MUST/SHOULD requirements
- Each step SHOULD include a `**Time Estimate:**` field with expected duration in minutes
- The `## Prerequisites` section SHOULD include a `**Required MCP Servers**` field listing required MCP servers

Reference: [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119)

## Versioning

Versions are stored as separate files: `v1.0.0.md`, `v1.1.0.md`, etc. Publishing never overwrites — it creates a new file.

- New SOP → always `v1.0.0`
- `major` → X+1.0.0
- `minor` → X.Y+1.0
- `patch` → X.Y.Z+1

Latest version is resolved by comparing semver tuples, not by file modification time.

## Parsing

All parsing is regex-based in `sop_parser.py`:

- Title: first `# ` heading
- Overview: content between `## Overview` and the next `##`
- Steps: all `### Step N: ...` blocks
- Version: `**Version:** X.Y.Z` or `**Version**: X.Y.Z` (also supports table format)
- Document ID: `**Document ID**: lowercase_name`

If any required element is missing, a `ValueError` is raised with a descriptive message.

## Testing

```bash
uv run pytest                          # all tests
uv run pytest tests/test_handler.py    # server/tool tests
uv run pytest tests/test_parser.py     # parser tests
uv run pytest tests/test_storage_backend.py  # property-based storage tests
```

- `test_handler.py` — async tests using `mcp.call_tool()` directly. Covers tool registration, step navigation, version handling, error cases.
- `test_parser.py` — synchronous tests for `SOP` class, `from_content()`, `list_available_sops()`.
- `test_storage_backend.py` — hypothesis property-based tests for write-read round trips, listing correctness, ephemeral warnings, path validation.

## Build & Run

This project MUST use `uv` for all Python-related commands. MUST NOT use bare `python` or `pip`.

```bash
uv sync                    # install/sync dependencies
uv run pytest              # run tests
uv run sop-mcp             # start server locally (stdio transport)
uv run ruff check src/     # lint
uvx sop-mcp                # run via uvx (once published)
```

## Key Design Decisions

1. **One tool per SOP** — SOPs appear in the agent's tool list, making them discoverable. No generic "run any SOP" tool that requires knowing names upfront.

2. **Step-at-a-time** — Prevents agents from skipping or summarizing. The `instruction` field explicitly tells the agent to act, not read.

3. **Folder = ID = tool suffix** — Zero mapping logic. Predictable: see folder `my_sop`, tool is `run_my_sop`.

4. **Versions as files** — Git-friendly, no database, easy to inspect. Semver sorting by filename.

5. **Storage abstraction** — `StorageBackend` protocol allows swapping implementations. Currently only local filesystem, but the protocol is ready for S3, DynamoDB, etc.

6. **Ephemeral awareness** — When running from package cache (no `SOP_STORAGE_DIR`), the server warns that published data may be lost. This prevents silent data loss.

7. **Feedback loop** — After completing an SOP, the agent offers to collect feedback. Stored per-SOP in `feedback.md` for use in future revisions.

8. **RFC 2119** — Industry standard for requirement levels. MUST/SHOULD/MAY give agents clear priority signals.

## Commit Messages

All commits MUST follow [Conventional Commits](https://www.conventionalcommits.org/). This is not optional — Release Please reads these to determine version bumps and generate changelogs.

Format:
```
<type>[optional scope]: <description>

[optional body]
```

Types and their effect on versioning:

| Type | Version Bump | When to use |
|------|-------------|-------------|
| `feat` | minor | New feature or capability |
| `fix` | patch | Bug fix |
| `feat!` or `BREAKING CHANGE:` in body | major | Breaking change |
| `docs` | none | Documentation only |
| `style` | none | Formatting, no logic change |
| `refactor` | none | Code change, no new feature or fix |
| `perf` | patch | Performance improvement |
| `test` | none | Adding or fixing tests |
| `chore` | none | Build process, tooling |
| `ci` | none | CI/CD changes |

Rules:
- Use imperative mood: "add" not "added" or "adds"
- No period at end of subject line
- Keep subject under 50 characters
- Capitalize the subject line
- Use body to explain what and why, not how

Examples:
```
feat: add SOP export tool
fix: handle missing version field in parser
feat!: rename all tool prefixes from exec_ to run_
docs: update AGENT.md with commit conventions
ci: add Python 3.10 to test matrix
refactor(parser): simplify step extraction regex
```

## Release Flow

Releases are fully automated via [Release Please](https://github.com/googleapis/release-please).

1. You merge commits to `main` (via PR from `dev`)
2. Release Please reads the commit messages and opens/updates a "Release PR"
   - Bumps version in `pyproject.toml`
   - Generates/updates `CHANGELOG.md`
   - Title: `chore(main): release X.Y.Z`
3. When you're ready to release, merge that Release PR
4. Release Please creates a GitHub Release + git tag
5. The `publish.yml` workflow triggers → publishes to PyPI

You never manually edit the version or write release notes. Just write good commit messages.

### TestPyPI dev builds

On every PR to `main` (from within the repo), a dev build is published to TestPyPI with a version like `0.2.0.dev118498230` (commit SHA as decimal). This lets you test the package before merging.

## Common Patterns When Modifying This Project

**Adding a new tool**: Define it in `server.py` with `@mcp.tool()`. Use the `backend` module-level instance for storage operations.

**Changing SOP parsing**: Edit `sop_parser.py`. The `_parse_content()` function is the entry point. Each field has its own `_extract_*` function.

**Adding a storage backend**: Implement the `StorageBackend` protocol from `storage_backend.py`. Update `get_storage_backend()` in `storage_local.py` to select it.

**Renaming an SOP**: Rename the folder in `src/sops/`, update the `**Document ID**:` field in the markdown to match. The tool name updates automatically on restart.

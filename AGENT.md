# AGENT.md — sop-mcp

You are working on `sop-mcp`, an MCP server that walks AI agents through Standard Operating Procedures one step at a time.

## What This Project Does

SOPs are markdown documents with numbered steps. This server exposes a single `run_sop` tool that accepts a `sop_name` parameter. When an agent calls the tool, it gets one step back. It must execute that step, then call the tool again with `step_output` to advance. The agent cannot skip ahead or see the full document at once.

This matters because agents tend to summarize or skip steps when given a full procedure. Feeding steps one at a time forces actual execution.

## Project Layout

```
src/sop_mcp/
├── server.py                  # MCP server entrypoint, tool + resource registration
├── resources/                 # bundled SOPs (each a flat `{name}.sop.md` file)
│   ├── sop_creation_guide.sop.md
│   ├── code_review_process.sop.md
│   └── …
├── tools/
│   ├── publish_sop.py         # write/bump an SOP
│   ├── run_sop.py             # advance through a specific SOP
│   └── submit_sop_feedback.py # append feedback alongside the SOP
├── utils/
│   ├── __init__.py            # re-exports
│   ├── sop_parser.py          # SOP dataclass, frontmatter + markdown parsing
│   ├── storage.py             # LocalFilesystemBackend (recursive scan)
│   ├── storage_backend.py     # backend factory
│   ├── resource_registration.py  # registers sop://{name} MCP resources
│   └── stdiomcp/              # lightweight JSON-RPC stdio MCP server
├── hook_middleware.py         # hook-system middleware
└── hooks.py                   # HookRegistry, HookExecutor, handlers

tests/
├── test_publish_sop.py        # publish_sop contract tests (MCP client)
├── test_run_sop.py            # run_sop contract tests (MCP client)
├── test_submit_sop_feedback.py  # feedback tool contract tests (MCP client)
├── test_sop_parser.py         # parser unit tests
├── test_storage_*.py          # storage backend unit + property tests
└── test_e2e_hooks.py          # end-to-end hook tests
```

## Naming Convention

Everything derives from the frontmatter `name:` field.

| Element      | Rule                                | Example                                  |
| ------------ | ----------------------------------- | ---------------------------------------- |
| Frontmatter  | lowercase, underscores, min 3 words | `sop_creation_guide`                     |
| File         | `{name}.sop.md`                     | `sop_creation_guide.sop.md`              |
| Tool call    | `run_sop` with `sop_name=` name     | `run_sop(sop_name="sop_creation_guide")` |
| Resource URI | `sop://{name}`                      | `sop://sop_creation_guide`               |

The regex enforcing this: `[a-z][a-z0-9]*(?:_[a-z0-9]+){2,}` — starts with a letter, at least 3 underscore-separated segments.

## Tools

### Static tools (always registered)

`publish_sop(content, scope?, path?)` — Validates markdown, auto-bumps the integer version, writes the flat `{name}.sop.md` file, and re-registers the `sop://{name}` MCP resource. No restart required.

`submit_sop_feedback(sop_name, feedback)` — Appends timestamped feedback to `{sop_name}/feedback.md`. Intended to be offered to the user after completing an SOP run.

### Single unified tool

`run_sop(sop_name, current_step?, version?, step_output?)` — Step-by-step execution.

- `sop_name` + no other args → returns step 1 + overview
- `current_step=N` + `step_output="..."` → returns step N+1 (meaning: "I finished step N, here's my output, give me the next one")
- `current_step=total` + `step_output="..."` → returns completion signal
- `version=1` → pins to a specific version instead of latest
- `step_output` is required when `current_step >= 1`, omit when starting

Every response includes an `instruction` field that explicitly tells the agent to execute the step content, not just read it.

## Step Execution Flow

```
Agent calls run_sop(sop_name="sop_creation_guide")
  → Server returns step 1 + overview + instruction
Agent executes step 1 actions
Agent calls run_sop(sop_name="sop_creation_guide", current_step=1, step_output="...")
  → Server returns step 2 + instruction
Agent executes step 2 actions
  ... repeats ...
Agent calls run_sop(sop_name="sop_creation_guide", current_step=8, step_output="...")
  → Server returns completion signal
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

The server uses a `StorageBackend` protocol (defined in `storage_backend.py`) with a single implementation: `LocalFilesystemBackend` (in `storage.py`).

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
---
name: my_sop_name          ← lowercase, underscores, 3+ words (required)
owner: my-team             ← non-empty string; team, alias, or email (required)
stage: preprod             ← preprod | prod (set by publish_sop; overwritten on write)
version: 1                 ← positive integer (set by publish_sop; overwritten on write)
description: One-liner.    ← optional; falls back to the Overview section
---

# Title                    ← level-1 heading (required)

## Overview                ← required section
Description of what this SOP does.

## Prerequisites           ← optional section
- Any general prerequisites...

**Required MCP Servers** (should):   ← SHOULD-level field
- server_name
- another_server — optional description

### Step 1: First Step Title         ← at least one step required
Step content with RFC 2119 keywords...

### Step 2: Second Step Title
More content...
```

Each step SHOULD include a `**Time Estimate:**` field.

The `## Prerequisites` section SHOULD include a `**Required MCP Servers**` field listing MCP servers needed for execution.

RFC 2119 keywords define requirement levels within steps.

## RFC 2119 Requirement Levels

All SOPs use these keywords. Use them with care and sparingly.

| Keyword                              | Meaning                                                                                                    |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| **MUST** / **REQUIRED** / **SHALL**  | Absolute requirement. Non-negotiable.                                                                      |
| **MUST NOT** / **SHALL NOT**         | Absolute prohibition. Never allowed.                                                                       |
| **SHOULD** / **RECOMMENDED**         | Strong recommendation. Valid reasons may exist to deviate, but full implications must be understood first. |
| **SHOULD NOT** / **NOT RECOMMENDED** | Discouraged. Valid reasons may exist when the behavior is acceptable, but weigh carefully.                 |
| **MAY** / **OPTIONAL**               | Truly optional. Implementations with or without the option must interoperate.                              |

Guidelines:
- MUST only be used where required for interoperation or to limit harmful behavior
- Do not use MUST to impose a particular method where not required for interoperability
- Consider security implications when not following MUST/SHOULD requirements
- Each step SHOULD include a `**Time Estimate:**` field with expected duration in minutes
- The `## Prerequisites` section SHOULD include a `**Required MCP Servers**` field listing required MCP servers

Reference: [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119)

## Versioning

Versions are plain positive integers: `1`, `2`, `3`, … — no semver.  New
SOPs start at `1`; each `publish_sop` call bumps by one.  The frontmatter
is stored inside the single ``{name}.sop.md`` file and ``publish_sop``
overwrites the ``version:`` field on every write, so authors don't have
to hand-manage it.

## Parsing

All parsing is regex + PyYAML-based in `sop_parser.py`:

- Title: first `# ` heading
- Overview: content between `## Overview` and the next `##`
- Steps: all `### Step N: ...` blocks
- Frontmatter: YAML block at the top of the file; ``name`` / ``version``
  / ``owner`` / ``stage`` / optional ``description``

If any required element is missing, a `ValueError` is raised with a
descriptive message.

## Testing

```bash
uv run pytest                                  # all tests
uv run pytest tests/test_publish_sop.py        # publish_sop contract tests
uv run pytest tests/test_run_sop.py            # run_sop contract tests
uv run pytest tests/test_sop_parser.py         # parser unit tests
```

- `test_publish_sop.py`, `test_run_sop.py`, `test_submit_sop_feedback.py` — contract tests against the MCP tools, driven via a subprocess MCP client harness.
- `test_sop_parser.py` — synchronous unit tests for `SOP`, `from_content()`, `list_available_sops()`.
- `test_storage_*.py` — LocalFilesystemBackend edge-case + property-based tests for write-read round trips, listing correctness, ephemeral warnings, path validation.

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

1. **Single `run_sop` tool** — A unified tool with a `sop_name` parameter. SOPs are discoverable via MCP resources.

2. **Step-at-a-time** — Prevents agents from skipping or summarizing. The `instruction` field explicitly tells the agent to act, not read.

3. **Folder = ID** — Zero mapping logic. Predictable: see folder `my_sop`, use `sop_name="my_sop"`.

4. **`step_output` forces concrete work** — When continuing (`current_step >= 1`), the agent must provide `step_output` with its concrete work product. The server doesn't store it — it exists to force detailed output into the conversation history.

4. **Versions as integers** — `1`, `2`, `3`, … stored in frontmatter. Git-friendly, no database, trivial to bump.

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

| Type                                  | Version Bump | When to use                        |
| ------------------------------------- | ------------ | ---------------------------------- |
| `feat`                                | minor        | New feature or capability          |
| `fix`                                 | patch        | Bug fix                            |
| `feat!` or `BREAKING CHANGE:` in body | major        | Breaking change                    |
| `docs`                                | none         | Documentation only                 |
| `style`                               | none         | Formatting, no logic change        |
| `refactor`                            | none         | Code change, no new feature or fix |
| `perf`                                | patch        | Performance improvement            |
| `test`                                | none         | Adding or fixing tests             |
| `chore`                               | none         | Build process, tooling             |
| `ci`                                  | none         | CI/CD changes                      |

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

**Adding a storage backend**: Implement the `StorageBackend` protocol from `storage_backend.py`. Update `get_storage_backend()` in `storage.py` to select it.

**Renaming an SOP**: Rename the file in `src/sop_mcp/resources/` (or your `SOP_STORAGE_DIR`) to match, and update the frontmatter `name:` field. The next publish picks up the new identity automatically.

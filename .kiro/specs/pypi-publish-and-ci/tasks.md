# Implementation Plan: PyPI Publishing & CI/CD

## Overview

Enhance the `sop-mcp` project for PyPI publishing readiness, add GitHub Actions CI/CD workflows, configure ruff linting, and add structured logging to MCP tool invocations. All changes build incrementally on the existing codebase.

## Tasks

- [x] 1. Enhance pyproject.toml with PyPI metadata and ruff configuration
  - [x] 1.1 Add full PyPI metadata fields to `pyproject.toml`
    - Add `readme`, `license`, `authors`, `keywords`, `classifiers`, and `[project.urls]` section
    - Authors: use `ValueArchitectsAI` as org name with placeholder email
    - URLs: `https://github.com/ValueArchitectsAI/sop-mcp` for Homepage, Repository, and Issues
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
  - [x] 1.2 Add ruff configuration to `pyproject.toml`
    - Add `[tool.ruff]` with `target-version = "py312"` and `line-length = 120`
    - Add `[tool.ruff.lint]` with `select = ["E", "F", "I", "W"]`
    - Add `ruff>=0.8.0` to `[tool.uv]` dev-dependencies
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  - [x] 1.3 Write example tests for pyproject.toml metadata validation
    - Create `tests/test_pyproject.py`
    - Parse `pyproject.toml` and assert required metadata fields exist (authors, readme, license, urls, classifiers, keywords)
    - Assert ruff config has correct target-version, line-length, and lint select rules
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 5.1, 5.2, 5.3_

- [x] 2. Fix existing code to pass ruff linting
  - Run `uv run ruff check .` and `uv run ruff format --check .` and fix any issues in `src/` and `tests/`
  - _Requirements: 5.1, 5.2, 5.3_

- [ ] 3. Checkpoint - Verify metadata and linting
  - Ensure `uv run pytest` passes, `uv run ruff check .` passes, and `uv run ruff format --check .` passes. Ask the user if questions arise.

- [ ] 4. Add structured logging to MCP server
  - [ ] 4.1 Add module-level logger and tool invocation logging in `src/server.py`
    - Add `import logging` and `logger = logging.getLogger(__name__)`
    - Add INFO log on tool entry (tool name + args) in `_create_sop_handler`, `publish_sop`, `submit_sop_feedback`, and `explain_sop`
    - Add INFO log on successful completion
    - Add WARNING log on error paths
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  - [ ] 4.2 Add feedback-specific logging in `submit_sop_feedback`
    - Log SOP name, version, and timestamp on successful feedback submission
    - Wrap feedback file writing in try/except, log WARNING on write failure, return error response
    - _Requirements: 8.1, 8.2_
  - [ ]* 4.3 Write property tests for logging behavior
    - Create `tests/test_logging.py`
    - Add `hypothesis` to dev-dependencies in `pyproject.toml`
    - **Property 1: Tool invocation entry logging** — For any tool name and arguments, the log output contains both the tool name and arguments
    - **Validates: Requirements 7.1**
    - **Property 2: Tool invocation success logging** — For any tool name on successful completion, the log output contains the tool name and success indicator
    - **Validates: Requirements 7.2**
    - **Property 3: Tool invocation error logging** — For any tool name and error message, the WARNING log contains both the tool name and error details
    - **Validates: Requirements 7.3**
    - **Property 4: Feedback submission logging includes SOP metadata** — For any SOP name and version, the log contains the SOP name, version, and timestamp pattern
    - **Validates: Requirements 8.1**

- [ ] 5. Checkpoint - Verify logging
  - Ensure all tests pass with `uv run pytest`. Ask the user if questions arise.

- [ ] 6. Create GitHub Actions CI workflow
  - [ ] 6.1 Create `.github/workflows/ci.yml`
    - Trigger on `push` to `main` and `pull_request` targeting `main`
    - Use `actions/checkout@v4`, `actions/setup-python@v5` (with python-version-file), `astral-sh/setup-uv@v4`
    - Steps: `uv sync`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`, `uv build`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 6.1, 6.2_

- [ ] 7. Create GitHub Actions CD workflow
  - [ ] 7.1 Create `.github/workflows/workflow.yaml`
    - Trigger on `release` type `published`
    - Use `actions/checkout@v4`, `actions/setup-python@v5`, `astral-sh/setup-uv@v4`
    - Steps: `uv build`, then `pypa/gh-action-pypi-publish@release/v1`
    - Set `permissions: id-token: write` for trusted publishing
    - Set `environment: pypi`
    - Filename MUST be `workflow.yaml` to match PyPI trusted publisher configuration
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  - [ ]* 7.2 Write example tests for workflow YAML validation
    - Create `tests/test_workflows.py`
    - Parse CI and CD workflow YAML files and verify triggers, action references, and key steps
    - _Requirements: 3.1, 3.2, 3.4, 4.1, 4.4_

- [ ] 8. Final checkpoint - Full validation
  - Ensure all tests pass with `uv run pytest`, linting passes with `uv run ruff check .` and `uv run ruff format --check .`, and `uv build` succeeds. Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal logging correctness properties
- Unit tests validate specific configuration examples and edge cases
- The CD workflow filename `workflow.yaml` is dictated by the existing PyPI trusted publisher configuration

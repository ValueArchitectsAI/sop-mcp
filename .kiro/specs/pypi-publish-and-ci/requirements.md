# Requirements Document

## Introduction

This feature brings the `sop-mcp` MCP server project to PyPI publishing readiness and adds GitHub Actions CI/CD workflows. The goal is to make the package installable via `pip install sop-mcp` and runnable via `uvx sop-mcp`, while automating testing, linting, and release publishing through GitHub Actions.

## Glossary

- **Package**: The `sop-mcp` Python distribution built and published to PyPI.
- **PyPI**: The Python Package Index, the official third-party software repository for Python.
- **CI_Pipeline**: The GitHub Actions workflow that runs on pull requests and pushes to validate code quality.
- **CD_Pipeline**: The GitHub Actions workflow that publishes the Package to PyPI when a release is created.
- **Trusted_Publishing**: PyPI's OIDC-based authentication mechanism that allows GitHub Actions to publish packages without API tokens.
- **SOP_Files**: The markdown files stored in `src/sops/` that are bundled with the Package.
- **Entry_Point**: The console script `sop-mcp` defined in `pyproject.toml` that starts the MCP server via stdio transport.
- **Linter**: The `ruff` tool used for Python linting and formatting checks.
- **Logger**: A Python `logging.Logger` instance used to emit structured log messages from the server.

## Requirements

### Requirement 1: PyPI Package Metadata

**User Story:** As a package maintainer, I want complete and accurate PyPI metadata in `pyproject.toml`, so that the package is discoverable and informative on PyPI.

#### Acceptance Criteria

1. THE Package SHALL include `author` or `authors` field with name and email placeholders in `pyproject.toml`
2. THE Package SHALL include a `readme` field pointing to `README.md` in `pyproject.toml`
3. THE Package SHALL include a `license` field referencing the MIT license in `pyproject.toml`
4. THE Package SHALL include a `urls` section with at minimum `Homepage` and `Repository` links in `pyproject.toml`
5. THE Package SHALL include PyPI classifiers for development status, license, Python version, and intended audience in `pyproject.toml`
6. THE Package SHALL include a `keywords` field with relevant search terms in `pyproject.toml`

### Requirement 2: Package Distribution Completeness

**User Story:** As a user installing via `uvx sop-mcp`, I want all SOP markdown files bundled in the package, so that the server works out of the box without missing data.

#### Acceptance Criteria

1. WHEN the Package is built, THE build system SHALL include all SOP_Files from `src/sops/` in the wheel and sdist distributions
2. WHEN the Package is installed via `pip install sop-mcp` or `uvx sop-mcp`, THE Entry_Point SHALL be available as the `sop-mcp` console command
3. WHEN the `sop-mcp` command is executed, THE server SHALL locate and load SOP_Files relative to the installed package path

### Requirement 3: CI Pipeline for Testing and Linting

**User Story:** As a developer, I want automated checks on every pull request and push to the main branch, so that code quality is maintained.

#### Acceptance Criteria

1. WHEN a pull request is opened or updated targeting the main branch, THE CI_Pipeline SHALL run the full test suite using `uv run pytest`
2. WHEN code is pushed to the main branch, THE CI_Pipeline SHALL run the full test suite using `uv run pytest`
3. THE CI_Pipeline SHALL run Linter checks using `ruff check` and `ruff format --check`
4. THE CI_Pipeline SHALL use prebuilt GitHub Actions (`actions/checkout`, `actions/setup-python`, `astral-sh/setup-uv`) for environment setup
5. IF any test fails, THEN THE CI_Pipeline SHALL report the failure and block the pull request from merging
6. IF any Linter check fails, THEN THE CI_Pipeline SHALL report the failure and block the pull request from merging

### Requirement 4: CD Pipeline for PyPI Publishing

**User Story:** As a package maintainer, I want the package automatically published to PyPI when I create a GitHub release, so that the release process is streamlined and repeatable.

#### Acceptance Criteria

1. WHEN a GitHub release is published, THE CD_Pipeline SHALL build the Package using `uv build`
2. WHEN the Package is built successfully, THE CD_Pipeline SHALL publish it to PyPI using the `pypa/gh-action-pypi-publish` action
3. THE CD_Pipeline SHALL use Trusted_Publishing for authentication with PyPI, requiring no stored API tokens
4. THE CD_Pipeline SHALL use prebuilt GitHub Actions (`actions/checkout`, `actions/setup-python`, `astral-sh/setup-uv`) for environment setup
5. IF the build step fails, THEN THE CD_Pipeline SHALL halt and not attempt to publish

### Requirement 5: Linter Configuration

**User Story:** As a developer, I want a consistent linting and formatting configuration, so that the codebase follows a uniform style.

#### Acceptance Criteria

1. THE Package SHALL include `ruff` configuration in `pyproject.toml` with a target Python version matching the project's `requires-python`
2. THE Package SHALL configure `ruff` with a line length of 120 characters
3. THE Package SHALL configure `ruff` to select a reasonable default rule set (at minimum `E` and `F` rules)
4. THE Package SHALL add `ruff` to the dev-dependencies in `pyproject.toml`

### Requirement 6: Package Build Validation

**User Story:** As a developer, I want to verify that the package builds correctly before publishing, so that broken packages are never uploaded to PyPI.

#### Acceptance Criteria

1. WHEN the CI_Pipeline runs, THE CI_Pipeline SHALL build the Package and verify the build succeeds
2. WHEN the Package is built, THE build output SHALL produce both a wheel (`.whl`) and a source distribution (`.tar.gz`)

### Requirement 7: MCP Logging on Tool Invocation

**User Story:** As a developer debugging the MCP server, I want structured logging emitted on every tool invocation, so that I can trace tool calls and diagnose issues.

#### Acceptance Criteria

1. WHEN any MCP tool is invoked, THE server SHALL emit a log message containing the tool name and input arguments using Python's `logging` module
2. WHEN a tool invocation completes successfully, THE server SHALL emit a log message indicating success and the tool name
3. WHEN a tool invocation results in an error, THE server SHALL emit a warning-level log message containing the tool name and error details
4. THE server SHALL configure a module-level logger using `logging.getLogger(__name__)` in each module that performs logging

### Requirement 8: Feedback Logging

**User Story:** As a developer, I want SOP feedback submissions logged, so that feedback activity is observable in server logs alongside the file-based storage.

#### Acceptance Criteria

1. WHEN feedback is submitted via `submit_sop_feedback`, THE server SHALL emit a log message containing the SOP name, version, and timestamp
2. WHEN feedback file writing fails, THE server SHALL emit a warning-level log message with the error details and return an error response

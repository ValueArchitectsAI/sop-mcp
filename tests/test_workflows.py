"""Tests for GitHub Actions workflow YAML validation.

Parses CI and CD workflow files and verifies triggers, action references,
and key steps match the design specification.

Requirements: 3.1, 3.2, 3.4, 4.1, 4.4
"""

from pathlib import Path

import yaml

WORKFLOWS_DIR = Path(__file__).parent.parent / ".github" / "workflows"


def _load_workflow(filename: str) -> dict:
    path = WORKFLOWS_DIR / filename
    with open(path) as f:
        return yaml.safe_load(f)


class TestCIWorkflow:
    """Validate CI workflow triggers, actions, and steps."""

    def test_triggers_on_push_to_any_branch(self):
        """Requirement 3.2: CI runs on push to any branch."""
        wf = _load_workflow("ci.yml")
        triggers = wf[True]  # PyYAML parses 'on' as boolean True
        # push with no branches filter means all branches
        assert "push" in triggers

    def test_triggers_on_pull_request_to_any_branch(self):
        """Requirement 3.1: CI runs on PR targeting any branch."""
        wf = _load_workflow("ci.yml")
        triggers = wf[True]
        # pull_request with no branches filter means all branches
        assert "pull_request" in triggers

    def test_uses_prebuilt_actions(self):
        """Requirement 3.4: CI uses prebuilt GitHub Actions for setup."""
        wf = _load_workflow("ci.yml")
        steps = wf["jobs"]["test"]["steps"]
        action_refs = [s.get("uses", "") for s in steps]
        assert any("actions/checkout@" in a for a in action_refs)
        assert any("actions/setup-python@" in a for a in action_refs)
        assert any("astral-sh/setup-uv@" in a for a in action_refs)

    def test_runs_pytest(self):
        """Requirement 3.1/3.2: CI runs the test suite."""
        wf = _load_workflow("ci.yml")
        steps = wf["jobs"]["test"]["steps"]
        run_cmds = [s.get("run", "") for s in steps]
        assert any("uv run pytest" in cmd for cmd in run_cmds)

    def test_runs_ruff_checks(self):
        """Requirement 3.3: CI runs ruff lint and format checks."""
        wf = _load_workflow("ci.yml")
        steps = wf["jobs"]["test"]["steps"]
        run_cmds = [s.get("run", "") for s in steps]
        assert any("ruff check" in cmd for cmd in run_cmds)
        assert any("ruff format --check" in cmd for cmd in run_cmds)


class TestCDWorkflow:
    """Validate CD workflow triggers, actions, and steps."""

    def test_triggers_on_release_published(self):
        """Requirement 4.1: CD triggers on GitHub release published."""
        wf = _load_workflow("workflow.yaml")
        triggers = wf[True]  # PyYAML parses 'on' as boolean True
        assert "published" in triggers["release"]["types"]

    def test_uses_prebuilt_actions(self):
        """Requirement 4.4: CD uses prebuilt GitHub Actions for setup."""
        wf = _load_workflow("workflow.yaml")
        steps = wf["jobs"]["publish"]["steps"]
        action_refs = [s.get("uses", "") for s in steps]
        assert any("actions/checkout@" in a for a in action_refs)
        assert any("actions/setup-python@" in a for a in action_refs)
        assert any("astral-sh/setup-uv@" in a for a in action_refs)

    def test_builds_package(self):
        """Requirement 4.1: CD builds the package."""
        wf = _load_workflow("workflow.yaml")
        steps = wf["jobs"]["publish"]["steps"]
        run_cmds = [s.get("run", "") for s in steps]
        assert any("uv build" in cmd for cmd in run_cmds)

    def test_publishes_with_pypi_action(self):
        """Requirement 4.2: CD publishes via pypa/gh-action-pypi-publish."""
        wf = _load_workflow("workflow.yaml")
        steps = wf["jobs"]["publish"]["steps"]
        action_refs = [s.get("uses", "") for s in steps]
        assert any("pypa/gh-action-pypi-publish@" in a for a in action_refs)

    def test_uses_trusted_publishing(self):
        """Requirement 4.3: CD uses OIDC trusted publishing."""
        wf = _load_workflow("workflow.yaml")
        assert wf["permissions"]["id-token"] == "write"

    def test_uses_pypi_environment(self):
        """CD job uses the 'pypi' environment."""
        wf = _load_workflow("workflow.yaml")
        assert wf["jobs"]["publish"]["environment"] == "pypi"

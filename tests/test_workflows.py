"""Tests for GitHub Actions workflow YAML validation.

Parses CI and Publish workflow files and verifies triggers, action references,
and key steps match the project requirements.
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
        wf = _load_workflow("ci.yml")
        triggers = wf[True]  # PyYAML parses 'on' as boolean True
        assert "push" in triggers

    def test_triggers_on_pull_request(self):
        wf = _load_workflow("ci.yml")
        triggers = wf[True]
        assert "pull_request" in triggers

    def test_lint_job_exists(self):
        wf = _load_workflow("ci.yml")
        assert "lint" in wf["jobs"]

    def test_test_job_exists(self):
        wf = _load_workflow("ci.yml")
        assert "test" in wf["jobs"]

    def test_build_job_exists(self):
        wf = _load_workflow("ci.yml")
        assert "build" in wf["jobs"]

    def test_uses_checkout_and_uv(self):
        wf = _load_workflow("ci.yml")
        steps = wf["jobs"]["test"]["steps"]
        action_refs = [s.get("uses", "") for s in steps]
        assert any("actions/checkout@" in a for a in action_refs)
        assert any("astral-sh/setup-uv@" in a for a in action_refs)

    def test_runs_pytest(self):
        wf = _load_workflow("ci.yml")
        steps = wf["jobs"]["test"]["steps"]
        run_cmds = [s.get("run", "") for s in steps]
        assert any("uv run pytest" in cmd for cmd in run_cmds)

    def test_runs_ruff_checks(self):
        wf = _load_workflow("ci.yml")
        steps = wf["jobs"]["lint"]["steps"]
        run_cmds = [s.get("run", "") for s in steps]
        assert any("ruff check" in cmd for cmd in run_cmds)
        assert any("ruff format --check" in cmd for cmd in run_cmds)


class TestPublishWorkflow:
    """Validate Publish workflow triggers, actions, and steps."""

    def test_triggers_on_tag_push(self):
        wf = _load_workflow("publish.yml")
        triggers = wf[True]
        assert "push" in triggers
        assert "v*" in triggers["push"]["tags"]

    def test_triggers_on_release_published(self):
        wf = _load_workflow("publish.yml")
        triggers = wf[True]
        assert "published" in triggers["release"]["types"]

    def test_triggers_on_pr_closed(self):
        wf = _load_workflow("publish.yml")
        triggers = wf[True]
        assert "closed" in triggers["pull_request"]["types"]

    def test_testpypi_job_exists(self):
        wf = _load_workflow("publish.yml")
        assert "publish-testpypi" in wf["jobs"]

    def test_pypi_job_exists(self):
        wf = _load_workflow("publish.yml")
        assert "publish-pypi" in wf["jobs"]

    def test_pypi_job_uses_pypi_environment(self):
        wf = _load_workflow("publish.yml")
        assert wf["jobs"]["publish-pypi"]["environment"] == "pypi"

    def test_testpypi_job_uses_testpypi_environment(self):
        wf = _load_workflow("publish.yml")
        assert wf["jobs"]["publish-testpypi"]["environment"] == "testpypi"

    def test_pypi_job_uses_trusted_publishing(self):
        wf = _load_workflow("publish.yml")
        assert wf["jobs"]["publish-pypi"]["permissions"]["id-token"] == "write"

    def test_pypi_job_builds_and_publishes(self):
        wf = _load_workflow("publish.yml")
        steps = wf["jobs"]["publish-pypi"]["steps"]
        run_cmds = [s.get("run", "") for s in steps]
        action_refs = [s.get("uses", "") for s in steps]
        assert any("uv build" in cmd for cmd in run_cmds)
        assert any("pypa/gh-action-pypi-publish@" in a for a in action_refs)

    def test_testpypi_job_publishes_to_test_registry(self):
        wf = _load_workflow("publish.yml")
        steps = wf["jobs"]["publish-testpypi"]["steps"]
        pypi_steps = [s for s in steps if "pypa/gh-action-pypi-publish@" in s.get("uses", "")]
        assert len(pypi_steps) == 1
        assert "test.pypi.org" in pypi_steps[0]["with"]["repository-url"]

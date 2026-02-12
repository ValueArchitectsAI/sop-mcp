"""Tests for pyproject.toml metadata and ruff configuration.

Validates that pyproject.toml contains all required PyPI metadata fields
and correct ruff linter configuration.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 5.1, 5.2, 5.3
"""

import tomllib
from pathlib import Path


def _load_pyproject() -> dict:
    path = Path(__file__).parent.parent / "pyproject.toml"
    with open(path, "rb") as f:
        return tomllib.load(f)


class TestPyPIMetadata:
    """Validate required PyPI metadata fields exist in pyproject.toml."""

    def test_authors_field_exists(self):
        data = _load_pyproject()
        authors = data["project"]["authors"]
        assert isinstance(authors, list)
        assert len(authors) > 0
        assert "name" in authors[0]
        assert "email" in authors[0]

    def test_readme_field_exists(self):
        data = _load_pyproject()
        assert data["project"]["readme"] == "README.md"

    def test_license_field_exists(self):
        data = _load_pyproject()
        license_val = data["project"]["license"]
        assert "MIT" in license_val.get("text", "")

    def test_urls_section_exists(self):
        data = _load_pyproject()
        urls = data["project"]["urls"]
        assert "Homepage" in urls
        assert "Repository" in urls

    def test_classifiers_field_exists(self):
        data = _load_pyproject()
        classifiers = data["project"]["classifiers"]
        assert isinstance(classifiers, list)
        assert len(classifiers) > 0
        # Check for required classifier categories
        joined = "\n".join(classifiers)
        assert "Development Status" in joined
        assert "License" in joined
        assert "Programming Language :: Python" in joined
        assert "Intended Audience" in joined

    def test_keywords_field_exists(self):
        data = _load_pyproject()
        keywords = data["project"]["keywords"]
        assert isinstance(keywords, list)
        assert len(keywords) > 0


class TestRuffConfig:
    """Validate ruff configuration in pyproject.toml."""

    def test_target_version(self):
        data = _load_pyproject()
        assert data["tool"]["ruff"]["target-version"] == "py312"

    def test_line_length(self):
        data = _load_pyproject()
        assert data["tool"]["ruff"]["line-length"] == 120

    def test_lint_select_rules(self):
        data = _load_pyproject()
        selected = data["tool"]["ruff"]["lint"]["select"]
        assert "E" in selected
        assert "F" in selected

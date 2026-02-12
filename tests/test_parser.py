"""Unit tests for SOP parser module.

Tests cover:
- SOP class: title, overview, steps extraction
- SOP.from_content() classmethod
- Error handling for missing files and invalid content
- list_available_sops() function
"""

import pytest

from src.utils.sop_parser import SOP, list_available_sops


class TestSopTitleExtraction:
    """Test that SOP extracts the correct title."""

    def test_extracts_title_from_sop(self):
        sop = SOP("authoring_new_sop")
        assert sop.title == "Standard Operating Procedure: Creating Standard Operating Procedures"

    def test_title_is_string(self):
        sop = SOP("authoring_new_sop")
        assert isinstance(sop.title, str)
        assert len(sop.title) > 0


class TestSopOverviewExtraction:
    """Test that SOP extracts the overview content."""

    def test_extracts_overview_from_sop(self):
        sop = SOP("authoring_new_sop")
        assert isinstance(sop.overview, str)
        assert len(sop.overview) > 0

    def test_overview_contains_expected_content(self):
        sop = SOP("authoring_new_sop")
        assert "Standard Operating Procedure" in sop.overview
        assert "RFC 2119" in sop.overview


class TestSopStepExtraction:
    """Test that SOP extracts all steps correctly."""

    def test_extracts_all_eight_steps(self):
        sop = SOP("authoring_new_sop")
        assert isinstance(sop.steps, list)
        assert len(sop.steps) == 8

    def test_steps_are_strings(self):
        sop = SOP("authoring_new_sop")
        for step in sop.steps:
            assert isinstance(step, str)
            assert len(step) > 0

    def test_steps_contain_step_headings(self):
        sop = SOP("authoring_new_sop")
        assert "Step 1:" in sop.steps[0]
        assert "Step 2:" in sop.steps[1]
        assert "Step 8:" in sop.steps[7]

    def test_first_step_is_prepare_for_sop_creation(self):
        sop = SOP("authoring_new_sop")
        assert "Prepare for SOP Creation" in sop.steps[0]

    def test_total_steps_property(self):
        sop = SOP("authoring_new_sop")
        assert sop.total_steps == 8


class TestSopProperties:
    """Test SOP convenience properties."""

    def test_path_is_set(self):
        sop = SOP("authoring_new_sop")
        assert sop.path is not None
        assert sop.path.exists()

    def test_truncated_overview_short(self):
        sop = SOP("authoring_new_sop")
        assert len(sop.truncated_overview) <= 150

    def test_name_is_set(self):
        sop = SOP("authoring_new_sop")
        assert sop.name == "authoring_new_sop"

    def test_tool_name_derived_from_folder(self):
        sop = SOP("authoring_new_sop")
        assert sop.tool_name == "authoring_new_sop"


class TestSopFromContent:
    """Test SOP.from_content() classmethod."""

    def test_parses_valid_content(self):
        content = (
            "# Test SOP\n\n"
            "## Document Information\n"
            "- **Document ID**: my_test_sop\n\n"
            "## Overview\n\nThis is a test SOP.\n\n"
            "### Step 1: Do something\n\nDo the thing.\n"
        )
        sop = SOP.from_content(content)
        assert sop.name == "my_test_sop"
        assert sop.tool_name == "my_test_sop"
        assert sop.total_steps == 1
        assert sop.path is None

    def test_raises_for_missing_sop_name(self):
        content = "# Some Title\n\n## Overview\n\nHello\n\n### Step 1: Do\n\nStuff\n"
        with pytest.raises(ValueError, match="Could not extract SOP name"):
            SOP.from_content(content)

    def test_raises_for_missing_title(self):
        content = "no heading\n\n- **Document ID**: bad_test_sop\n\n## Overview\n\nHello\n\n### Step 1: Do\n\nStuff\n"
        with pytest.raises(ValueError, match="missing a title"):
            SOP.from_content(content)


class TestSopErrorHandling:
    """Test error handling for missing or invalid files."""

    def test_raises_file_not_found_for_missing_sop(self):
        with pytest.raises(FileNotFoundError):
            SOP("nonexistent-sop-name")

    def test_error_message_includes_path(self):
        with pytest.raises(FileNotFoundError, match="SOP file not found"):
            SOP("nonexistent-sop-name")


class TestListAvailableSops:
    """Test the list_available_sops function."""

    def test_returns_list(self):
        result = list_available_sops()
        assert isinstance(result, list)

    def test_returns_sop_name(self):
        result = list_available_sops()
        assert "authoring_new_sop" in result

    def test_returns_names_without_md_extension(self):
        result = list_available_sops()
        for name in result:
            assert not name.endswith(".md")

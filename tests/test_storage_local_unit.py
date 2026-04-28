"""Unit tests for LocalFilesystemBackend edge cases.

Covers: seeding edge cases, directory creation, sop_exists,
read_sop errors, and feedback operations.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.sop_mcp.utils.storage import LocalFilesystemBackend


def _valid_sop(name: str, version: int = 1) -> str:
    """Minimal SOP content that parses cleanly under the current parser."""
    return (
        "---\n"
        f"name: {name}\n"
        f"version: {version}\n"
        "owner: tests\n"
        "stage: preprod\n"
        "---\n\n"
        f"# Test SOP {name}\n\n"
        "## Overview\n\nA minimal SOP used for unit tests.\n\n"
        "### Step 1: Do the thing\n\nJust do it.\n"
    )


class TestSeedingEdgeCases:
    def test_empty_seed_directory_skips_seeding(self, tmp_path: Path) -> None:
        base = tmp_path / "store"
        seed = tmp_path / "seed"
        seed.mkdir()  # exists but empty

        backend = LocalFilesystemBackend(base_dir=base, seed_dir=seed)

        assert backend.list_sops() == []

    def test_missing_seed_directory_skips_seeding(self, tmp_path: Path) -> None:
        base = tmp_path / "store"
        seed = tmp_path / "nonexistent_seed"

        backend = LocalFilesystemBackend(base_dir=base, seed_dir=seed)

        assert backend.list_sops() == []


class TestDirectoryCreation:
    def test_creates_base_dir_on_init(self, tmp_path: Path) -> None:
        base = tmp_path / "deep" / "nested" / "store"
        assert not base.exists()

        LocalFilesystemBackend(base_dir=base)

        assert base.is_dir()


class TestSopExists:
    def test_returns_true_for_existing_sop(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.write_sop("my_sop", 1, _valid_sop("my_sop"))

        assert backend.sop_exists("my_sop") is True

    def test_returns_true_for_existing_version(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.write_sop("my_sop", 1, _valid_sop("my_sop"))

        assert backend.sop_exists("my_sop", 1) is True

    def test_returns_false_for_missing_sop(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)

        assert backend.sop_exists("no_such_sop") is False

    def test_returns_false_for_missing_version(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.write_sop("my_sop", 1, _valid_sop("my_sop"))

        assert backend.sop_exists("my_sop", 99) is False


class TestReadSopErrors:
    def test_raises_for_missing_sop(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)

        with pytest.raises(FileNotFoundError, match="not found"):
            backend.read_sop("nonexistent")

    def test_raises_for_missing_version(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.write_sop("my_sop", 1, _valid_sop("my_sop"))

        with pytest.raises(FileNotFoundError, match="Version.*not found"):
            backend.read_sop("my_sop", 99)


class TestFeedbackOperations:
    def test_read_feedback_returns_none_when_absent(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)

        assert backend.read_feedback("my_sop") is None

    def test_write_and_read_feedback(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.write_feedback("my_sop", "Great SOP!")

        assert backend.read_feedback("my_sop") == "Great SOP!"

    def test_write_feedback_overwrites(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.write_feedback("my_sop", "First")
        backend.write_feedback("my_sop", "Second")

        assert backend.read_feedback("my_sop") == "Second"

    def test_append_feedback_creates_file(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.append_feedback("my_sop", {"feedback": "Entry 1"})

        content = backend.read_feedback("my_sop")
        assert content is not None
        assert "Entry 1" in content

    def test_append_feedback_appends_to_existing(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.append_feedback("my_sop", {"feedback": "Entry 1"})
        backend.append_feedback("my_sop", {"feedback": "Entry 2"})

        entries = backend.read_feedback_entries("my_sop")
        assert [e["feedback"] for e in entries] == ["Entry 1", "Entry 2"]

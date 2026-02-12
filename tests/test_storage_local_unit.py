"""Unit tests for LocalFilesystemBackend edge cases.

Covers: seeding edge cases, directory creation, sop_exists,
read_sop errors, and feedback operations.
Requirements: 2.4, 3.2
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.utils.storage_local import LocalFilesystemBackend


class TestSeedingEdgeCases:
    """Requirement 3.2: seeding is skipped when seed_dir is empty or missing."""

    def test_empty_seed_directory_skips_seeding(self, tmp_path: Path) -> None:
        base = tmp_path / "store"
        seed = tmp_path / "seed"
        seed.mkdir()  # exists but empty

        backend = LocalFilesystemBackend(base_dir=base, seed_dir=seed)

        assert backend.list_sops() == []

    def test_missing_seed_directory_skips_seeding(self, tmp_path: Path) -> None:
        base = tmp_path / "store"
        seed = tmp_path / "nonexistent_seed"  # does not exist

        backend = LocalFilesystemBackend(base_dir=base, seed_dir=seed)

        assert backend.list_sops() == []


class TestDirectoryCreation:
    """Requirement 2.4: storage directory is created on init."""

    def test_creates_base_dir_on_init(self, tmp_path: Path) -> None:
        base = tmp_path / "deep" / "nested" / "store"
        assert not base.exists()

        LocalFilesystemBackend(base_dir=base)

        assert base.is_dir()


class TestSopExists:
    def test_returns_true_for_existing_sop(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.write_sop("my_sop", "1.0.0", "# content")

        assert backend.sop_exists("my_sop") is True

    def test_returns_true_for_existing_version(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.write_sop("my_sop", "1.0.0", "# content")

        assert backend.sop_exists("my_sop", "1.0.0") is True

    def test_returns_false_for_missing_sop(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)

        assert backend.sop_exists("no_such_sop") is False

    def test_returns_false_for_missing_version(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.write_sop("my_sop", "1.0.0", "# content")

        assert backend.sop_exists("my_sop", "9.9.9") is False


class TestReadSopErrors:
    def test_raises_for_missing_sop(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)

        with pytest.raises(FileNotFoundError, match="not found"):
            backend.read_sop("nonexistent")

    def test_raises_for_missing_version(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.write_sop("my_sop", "1.0.0", "# v1")

        with pytest.raises(FileNotFoundError, match="Version.*not found"):
            backend.read_sop("my_sop", "9.9.9")


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

    def test_append_feedback_creates_file_with_header(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.append_feedback("my_sop", "Entry 1\n")

        content = backend.read_feedback("my_sop")
        assert content is not None
        assert "Feedback Log" in content
        assert "Entry 1" in content

    def test_append_feedback_appends_to_existing(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.append_feedback("my_sop", "Entry 1\n")
        backend.append_feedback("my_sop", "Entry 2\n")

        content = backend.read_feedback("my_sop")
        assert content is not None
        assert "Entry 1" in content
        assert "Entry 2" in content

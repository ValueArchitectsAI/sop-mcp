"""Unit tests for LocalFilesystemBackend edge cases.

Covers: seeding edge cases, directory creation, sop_exists,
read_sop errors, and feedback operations.
"""

from __future__ import annotations

import json
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

        with pytest.raises(FileNotFoundError, match=r"Version.*not found"):
            backend.read_sop("my_sop", 99)


class TestFeedbackOperations:
    """Feedback is write-only — only the append path is part of the public API."""

    def test_append_feedback_creates_file_in_sop_folder(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.write_sop("my_sop", 1, _valid_sop("my_sop"))
        backend.append_feedback("my_sop", {"feedback": "Entry 1"})

        # Feedback lives inside the SOP folder (nested layout).
        feedback_file = tmp_path / "my_sop" / "my_sop.feedback.jsonl"
        assert feedback_file.is_file()
        assert "Entry 1" in feedback_file.read_text(encoding="utf-8")

    def test_append_feedback_appends_to_existing(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.write_sop("my_sop", 1, _valid_sop("my_sop"))
        backend.append_feedback("my_sop", {"feedback": "Entry 1"})
        backend.append_feedback("my_sop", {"feedback": "Entry 2"})

        feedback_file = tmp_path / "my_sop" / "my_sop.feedback.jsonl"
        lines = [line for line in feedback_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) == 2
        parsed = [json.loads(line) for line in lines]
        assert [e["feedback"] for e in parsed] == ["Entry 1", "Entry 2"]

    def test_append_feedback_fallback_when_sop_missing(self, tmp_path: Path) -> None:
        """When no SOP file exists, feedback falls back to base_dir."""
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.append_feedback("my_sop", {"feedback": "Entry 1"})

        feedback_file = tmp_path / "my_sop.feedback.jsonl"
        assert feedback_file.is_file()
        assert "Entry 1" in feedback_file.read_text(encoding="utf-8")

    def test_backend_does_not_expose_read_api(self, tmp_path: Path) -> None:
        """Enforce the write-only contract — no accidental read helper re-appears."""
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        for attr in ("read_feedback", "read_feedback_entries", "write_feedback"):
            assert not hasattr(backend, attr), (
                f"LocalFilesystemBackend must not expose '{attr}' — feedback is write-only."
            )

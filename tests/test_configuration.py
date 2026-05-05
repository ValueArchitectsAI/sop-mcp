"""Tests for storage configuration, backend selection, seeding, and path validation.

Covers: SOP_STORAGE_DIR env var, bundled fallback, seeding edge cases,
directory creation, sop_exists, read_sop errors, and property-based
storage correctness.
"""

from __future__ import annotations

import string
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.sop_mcp.utils.storage import BUNDLED_SOPS_DIR, LocalFilesystemBackend, _validate_storage_path
from src.sop_mcp.utils.storage_backend import get_storage_backend

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_sop(name: str, version: int = 1) -> str:
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


# ---------------------------------------------------------------------------
# Backend selection via environment
# ---------------------------------------------------------------------------


class TestBackendSelection:
    def test_sop_storage_dir_env_sets_path(self, tmp_path: Path, monkeypatch) -> None:
        custom_dir = tmp_path / "custom_sops"
        monkeypatch.setenv("SOP_STORAGE_DIR", str(custom_dir))
        monkeypatch.delenv("SOP_STORAGE_BACKEND", raising=False)

        backend = get_storage_backend()
        assert backend.base_dir == custom_dir

    def test_no_env_defaults_to_bundled(self, monkeypatch) -> None:
        monkeypatch.delenv("SOP_STORAGE_DIR", raising=False)
        monkeypatch.delenv("SOP_STORAGE_BACKEND", raising=False)

        backend = get_storage_backend()
        assert backend.base_dir == BUNDLED_SOPS_DIR

    def test_bundled_backend_env(self, monkeypatch) -> None:
        monkeypatch.setenv("SOP_STORAGE_BACKEND", "bundled")
        monkeypatch.delenv("SOP_STORAGE_DIR", raising=False)

        backend = get_storage_backend()
        assert backend.base_dir == BUNDLED_SOPS_DIR


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


class TestSeeding:
    def test_empty_seed_directory_skips(self, tmp_path: Path) -> None:
        base = tmp_path / "store"
        seed = tmp_path / "seed"
        seed.mkdir()

        backend = LocalFilesystemBackend(base_dir=base, seed_dir=seed)
        assert backend.list_sops() == []

    def test_missing_seed_directory_skips(self, tmp_path: Path) -> None:
        base = tmp_path / "store"
        seed = tmp_path / "nonexistent_seed"

        backend = LocalFilesystemBackend(base_dir=base, seed_dir=seed)
        assert backend.list_sops() == []


# ---------------------------------------------------------------------------
# Directory creation
# ---------------------------------------------------------------------------


class TestDirectoryCreation:
    def test_creates_base_dir_on_init(self, tmp_path: Path) -> None:
        base = tmp_path / "deep" / "nested" / "store"
        assert not base.exists()

        LocalFilesystemBackend(base_dir=base)
        assert base.is_dir()


# ---------------------------------------------------------------------------
# sop_exists
# ---------------------------------------------------------------------------


class TestSopExists:
    def test_true_for_existing(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.write_sop("my_sop", 1, _valid_sop("my_sop"))
        assert backend.sop_exists("my_sop") is True

    def test_true_for_existing_version(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.write_sop("my_sop", 1, _valid_sop("my_sop"))
        assert backend.sop_exists("my_sop", 1) is True

    def test_false_for_missing(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        assert backend.sop_exists("no_such_sop") is False

    def test_false_for_wrong_version(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.write_sop("my_sop", 1, _valid_sop("my_sop"))
        assert backend.sop_exists("my_sop", 99) is False


# ---------------------------------------------------------------------------
# read_sop errors
# ---------------------------------------------------------------------------


class TestReadSopErrors:
    def test_raises_for_missing(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        with pytest.raises(FileNotFoundError, match="not found"):
            backend.read_sop("nonexistent")

    def test_raises_for_wrong_version(self, tmp_path: Path) -> None:
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        backend.write_sop("my_sop", 1, _valid_sop("my_sop"))
        with pytest.raises(FileNotFoundError, match=r"Version.*not found"):
            backend.read_sop("my_sop", 99)


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------


class TestPathValidation:
    @settings(max_examples=100, deadline=None)
    @given(
        path_str=st.one_of(
            st.just(""),
            st.text(min_size=1, max_size=100).map(lambda s: s + "\x00"),
            st.text(min_size=1, max_size=100).map(lambda s: "\x00" + s),
            st.text(min_size=0, max_size=50).flatmap(
                lambda prefix: st.text(min_size=0, max_size=50).map(lambda suffix: prefix + "\x00" + suffix)
            ),
        )
    )
    def test_rejects_invalid_paths(self, path_str: str) -> None:
        with pytest.raises(ValueError):
            _validate_storage_path(path_str)


# ---------------------------------------------------------------------------
# Property-based: write-read round trip
# ---------------------------------------------------------------------------

sop_name_segment = st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8)
sop_names = st.lists(sop_name_segment, min_size=2, max_size=4).map(lambda parts: "_".join(parts))
integer_versions = st.integers(min_value=1, max_value=99)
sop_overview = st.text(
    alphabet=st.characters(categories=("L", "N", "Z")),
    min_size=1,
    max_size=60,
).filter(lambda s: s.strip() and "\n" not in s)


@settings(max_examples=100, deadline=None)
@given(name=sop_names, version=integer_versions, overview=sop_overview)
def test_property_write_read_round_trip(tmp_path_factory, name: str, version: int, overview: str) -> None:
    """Writing then reading back returns the same content."""
    base_dir = tmp_path_factory.mktemp("sops")
    backend = LocalFilesystemBackend(base_dir=base_dir)

    content = _valid_sop(name, version).replace("A minimal SOP used for unit tests.", overview)
    backend.write_sop(name, version, content)
    result = backend.read_sop(name, version)
    assert result == content


@settings(max_examples=50, deadline=None)
@given(data=st.data(), num_sops=st.integers(min_value=1, max_value=5))
def test_property_listing_reflects_writes(tmp_path_factory, data: st.DataObject, num_sops: int) -> None:
    """list_sops returns exactly the names written."""
    base_dir = tmp_path_factory.mktemp("sops")
    backend = LocalFilesystemBackend(base_dir=base_dir)

    names = data.draw(st.lists(sop_names, min_size=num_sops, max_size=num_sops, unique=True))

    for name in names:
        version = data.draw(integer_versions)
        backend.write_sop(name, version, _valid_sop(name, version))

    assert backend.list_sops() == sorted(names)

"""Unit tests for get_storage_backend configuration scenarios.

Requirements: 5.1, 5.2, 5.3
"""

from __future__ import annotations

from pathlib import Path

from src.utils.storage_local import BUNDLED_SOPS_DIR, get_storage_backend


class TestStorageConfiguration:
    def test_sop_storage_dir_env_sets_backend_path(self, tmp_path: Path, monkeypatch) -> None:
        """Requirement 5.1: SOP_STORAGE_DIR env var sets the backend path."""
        custom_dir = tmp_path / "custom_sops"
        monkeypatch.setenv("SOP_STORAGE_DIR", str(custom_dir))
        monkeypatch.delenv("SOP_STORAGE_BACKEND", raising=False)

        backend = get_storage_backend()

        assert backend.base_dir == custom_dir
        assert backend.is_ephemeral is False

    def test_no_env_vars_defaults_to_bundled_dir_ephemeral(self, monkeypatch) -> None:
        """No env vars defaults to bundled src/sops/ directory, marked ephemeral."""
        monkeypatch.delenv("SOP_STORAGE_DIR", raising=False)
        monkeypatch.delenv("SOP_STORAGE_BACKEND", raising=False)

        backend = get_storage_backend()

        assert backend.base_dir == BUNDLED_SOPS_DIR
        assert backend.is_ephemeral is True

    def test_bundled_backend_env_still_defaults_ephemeral(self, monkeypatch) -> None:
        """SOP_STORAGE_BACKEND=bundled still results in ephemeral bundled dir."""
        monkeypatch.setenv("SOP_STORAGE_BACKEND", "bundled")
        monkeypatch.delenv("SOP_STORAGE_DIR", raising=False)

        backend = get_storage_backend()

        assert backend.base_dir == BUNDLED_SOPS_DIR
        assert backend.is_ephemeral is True

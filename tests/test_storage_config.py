"""Unit tests for get_storage_backend configuration scenarios.

Requirements: 5.1, 5.2, 5.3
"""

from __future__ import annotations

from pathlib import Path

from src.sop_mcp.utils.storage import BUNDLED_SOPS_DIR
from src.sop_mcp.utils.storage_backend import get_storage_backend


class TestStorageConfiguration:
    def test_sop_storage_dir_env_sets_backend_path(self, tmp_path: Path, monkeypatch) -> None:
        """SOP_STORAGE_DIR env var sets the backend path."""
        custom_dir = tmp_path / "custom_sops"
        monkeypatch.setenv("SOP_STORAGE_DIR", str(custom_dir))
        monkeypatch.delenv("SOP_STORAGE_BACKEND", raising=False)

        backend = get_storage_backend()

        assert backend.base_dir == custom_dir

    def test_no_env_vars_defaults_to_bundled_dir(self, monkeypatch) -> None:
        """No env vars defaults to bundled src/sops/ directory."""
        monkeypatch.delenv("SOP_STORAGE_DIR", raising=False)
        monkeypatch.delenv("SOP_STORAGE_BACKEND", raising=False)

        backend = get_storage_backend()

        assert backend.base_dir == BUNDLED_SOPS_DIR

    def test_bundled_backend_env_defaults_to_bundled_dir(self, monkeypatch) -> None:
        """SOP_STORAGE_BACKEND=bundled uses bundled dir."""
        monkeypatch.setenv("SOP_STORAGE_BACKEND", "bundled")
        monkeypatch.delenv("SOP_STORAGE_DIR", raising=False)

        backend = get_storage_backend()

        assert backend.base_dir == BUNDLED_SOPS_DIR

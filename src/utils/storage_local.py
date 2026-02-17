"""Local filesystem storage backend for SOP files.

Implements the StorageBackend protocol using pathlib.Path operations
against a configurable directory on the local filesystem.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .sop_parser import _parse_semver

# Directory containing the SOPs bundled with the package.
BUNDLED_SOPS_DIR = Path(__file__).parent.parent / "mcp" / "resources"


class LocalFilesystemBackend:
    """Storage backend that reads/writes SOP files on the local filesystem.

    Directory layout::

        {base_dir}/{sop_name}/v{version}.md
        {base_dir}/{sop_name}/feedback.md

    Attributes:
        base_dir: The root directory for SOP storage.
        is_ephemeral: Whether this directory is considered ephemeral.
    """

    def __init__(
        self,
        base_dir: Path,
        is_ephemeral: bool = False,
        seed_dir: Path | None = None,
    ) -> None:
        self._base_dir = base_dir
        self._is_ephemeral = is_ephemeral

        # Ensure the storage directory exists (Requirement 2.4)
        self._base_dir.mkdir(parents=True, exist_ok=True)

        # Seed from bundled directory if base_dir has no SOPs (Requirements 3.1-3.3)
        if seed_dir is not None:
            self._seed(seed_dir)

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    @property
    def is_ephemeral(self) -> bool:
        return self._is_ephemeral

    # --- SOP read/write ---

    def read_sop(self, name: str, version: str | None = None) -> str:
        """Read SOP file content by name and optional version.

        When *version* is ``None`` the latest version (highest semver) is
        returned.  Raises ``FileNotFoundError`` when the SOP or requested
        version does not exist.
        """
        sop_dir = self._base_dir / name
        if not sop_dir.is_dir():
            raise FileNotFoundError(f"SOP '{name}' not found")

        if version is not None:
            path = sop_dir / f"v{version}.md"
            if not path.is_file():
                available = self.list_versions(name)
                raise FileNotFoundError(
                    f"Version '{version}' not found for '{name}'. Available versions: {', '.join(available)}"
                )
            return path.read_text(encoding="utf-8")

        # Resolve latest
        path = self._resolve_latest(sop_dir)
        return path.read_text(encoding="utf-8")

    def write_sop(self, name: str, version: str, content: str) -> None:
        """Write SOP content to a versioned file within the SOP's subdirectory."""
        sop_dir = self._base_dir / name
        sop_dir.mkdir(parents=True, exist_ok=True)
        (sop_dir / f"v{version}.md").write_text(content, encoding="utf-8")

    # --- Listing ---

    def list_sops(self) -> list[str]:
        """Return sorted list of SOP names that have at least one versioned file."""
        if not self._base_dir.exists():
            return []
        names: list[str] = []
        for d in self._base_dir.iterdir():
            if d.is_dir() and list(d.glob("v*.md")):
                names.append(d.name)
        return sorted(names)

    def list_versions(self, name: str) -> list[str]:
        """Return sorted list of versions for a given SOP."""
        sop_dir = self._base_dir / name
        if not sop_dir.is_dir():
            return []
        versions = [f.stem[1:] for f in sop_dir.glob("v*.md")]
        versions.sort(key=_parse_semver)
        return versions

    def sop_exists(self, name: str, version: str | None = None) -> bool:
        """Check whether a specific SOP (and optionally version) exists."""
        sop_dir = self._base_dir / name
        if not sop_dir.is_dir():
            return False
        if version is None:
            return bool(list(sop_dir.glob("v*.md")))
        return (sop_dir / f"v{version}.md").is_file()

    # --- Feedback ---

    def read_feedback(self, name: str) -> str | None:
        """Read feedback file content for an SOP, or None if none exists."""
        path = self._base_dir / name / "feedback.md"
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def write_feedback(self, name: str, content: str) -> None:
        """Write or overwrite the feedback file for an SOP."""
        sop_dir = self._base_dir / name
        sop_dir.mkdir(parents=True, exist_ok=True)
        (sop_dir / "feedback.md").write_text(content, encoding="utf-8")

    def append_feedback(self, name: str, entry: str) -> None:
        """Append a feedback entry to the SOP's feedback file.

        Creates the file with a header if it doesn't exist yet.
        """
        sop_dir = self._base_dir / name
        sop_dir.mkdir(parents=True, exist_ok=True)
        feedback_path = sop_dir / "feedback.md"

        if feedback_path.is_file():
            with feedback_path.open("a", encoding="utf-8") as f:
                f.write(entry)
        else:
            header = (
                f"# Feedback Log — {name}\n\n"
                "This file collects improvement feedback for future SOP revisions.\n\n---\n\n"
            )
            feedback_path.write_text(header + entry, encoding="utf-8")

    # --- Internal helpers ---

    def _resolve_latest(self, sop_dir: Path) -> Path:
        """Find the highest semver v*.md file in an SOP directory."""
        versioned = list(sop_dir.glob("v*.md"))
        if not versioned:
            raise FileNotFoundError(f"No versioned files found in {sop_dir}")
        versioned.sort(key=lambda f: _parse_semver(f.stem[1:]), reverse=True)
        return versioned[0]

    def _has_sops(self, directory: Path) -> bool:
        """Check whether a directory contains any SOP subdirectories with v*.md files."""
        if not directory.is_dir():
            return False
        for d in directory.iterdir():
            if d.is_dir() and list(d.glob("v*.md")):
                return True
        return False

    def _seed(self, seed_dir: Path) -> None:
        """Copy SOP files from seed_dir into base_dir when base_dir has no SOPs.

        Only versioned files (v*.md) are copied — feedback files are not.
        Seeding is skipped when:
        - base_dir already contains SOP subdirectories
        - seed_dir does not exist or is empty
        """
        # Skip if base already has SOPs
        if self._has_sops(self._base_dir):
            return

        # Skip if seed dir is missing or has no SOPs (Requirement 3.2)
        if not self._has_sops(seed_dir):
            return

        for src_sop_dir in seed_dir.iterdir():
            if not src_sop_dir.is_dir():
                continue
            version_files = list(src_sop_dir.glob("v*.md"))
            if not version_files:
                continue
            dest_sop_dir = self._base_dir / src_sop_dir.name
            dest_sop_dir.mkdir(parents=True, exist_ok=True)
            for vf in version_files:
                shutil.copy2(vf, dest_sop_dir / vf.name)


# --- Factory ---


def _validate_storage_path(path_str: str) -> Path:
    """Validate that a storage directory path string is usable.

    Raises ``ValueError`` for empty strings or strings containing null bytes.
    """
    if not path_str:
        raise ValueError("Storage directory path must not be empty")
    if "\x00" in path_str:
        raise ValueError("Storage directory path must not contain null bytes")
    return Path(path_str)


def get_storage_backend() -> LocalFilesystemBackend:
    """Create and return the appropriate storage backend based on configuration.

    Resolution order:

    1. ``SOP_STORAGE_DIR`` is set  →  use that path, seed from bundled,
       not ephemeral.
    2. Otherwise  →  use the bundled ``src/sops/`` directory directly,
       marked as ephemeral (data may be lost on package cache refresh).
    """
    storage_dir_env = os.environ.get("SOP_STORAGE_DIR", "").strip()

    if storage_dir_env:
        base_dir = _validate_storage_path(storage_dir_env)
        return LocalFilesystemBackend(
            base_dir=base_dir,
            is_ephemeral=False,
            seed_dir=BUNDLED_SOPS_DIR,
        )

    # Default: bundled directory, always ephemeral until a persistent path is configured
    return LocalFilesystemBackend(
        base_dir=BUNDLED_SOPS_DIR,
        is_ephemeral=True,
    )

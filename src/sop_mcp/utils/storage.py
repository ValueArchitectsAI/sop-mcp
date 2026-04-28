"""Local filesystem storage backend for SOP files.

SOPs are stored as ``*.sop.md`` markdown files with YAML frontmatter.
The layout is flat by default — one file per SOP directly in ``base_dir`` —
but nesting is supported: callers may pass a relative ``path`` to
``write_sop`` to group SOPs under subdirectories (e.g. ``generated/``,
``teams/eng/``).

Discovery is recursive: any ``*.sop.md`` under ``base_dir`` at any depth is
picked up.  SOP identity is the frontmatter ``name`` — path is ignored for
lookup.  When two files declare the same ``name``, the first one discovered
wins and the duplicates are reported through ``duplicate_name_warnings`` so
callers can surface the problem without crashing the server.

Feedback for each SOP lives alongside it:

    {base_dir}/{sub}/{name}.sop.md          # SOP document
    {base_dir}/{sub}/{name}.feedback.jsonl  # append-only feedback log
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path

from .sop_parser import SOP, SOP_SUFFIX, set_version_in_content

logger = logging.getLogger(__name__)

# Directory containing the SOPs bundled with the package.
BUNDLED_SOPS_DIR = Path(__file__).parent.parent / "resources"

FEEDBACK_SUFFIX = ".feedback.jsonl"


class LocalFilesystemBackend:
    """Storage backend that reads/writes SOP files on the local filesystem.

    Discovery is recursive — ``*.sop.md`` files at any depth under
    ``base_dir`` are included.  SOP identity is the frontmatter ``name``
    field; path information is ignored for lookup so two files sharing a
    name would collide.  Collisions are reported (not raised) — first file
    discovered wins, others are logged and exposed via
    ``duplicate_name_warnings``.
    """

    def __init__(
        self,
        base_dir: Path,
        is_ephemeral: bool = False,
        seed_dir: Path | None = None,
    ) -> None:
        self._base_dir = base_dir
        self._is_ephemeral = is_ephemeral
        self._duplicate_warnings: list[str] = []

        self._base_dir.mkdir(parents=True, exist_ok=True)

        if seed_dir is not None:
            self._seed(seed_dir)

    @classmethod
    def from_env(cls) -> LocalFilesystemBackend:
        """Create from environment variables.

        ``SOP_STORAGE_DIR`` → use that path, seed from bundled, not ephemeral.
        Otherwise → use bundled directory, marked ephemeral.
        """
        storage_dir = os.environ.get("SOP_STORAGE_DIR", "").strip()
        if storage_dir:
            base_dir = _validate_storage_path(storage_dir)
            return cls(base_dir=base_dir, is_ephemeral=False, seed_dir=BUNDLED_SOPS_DIR)
        return cls(base_dir=BUNDLED_SOPS_DIR, is_ephemeral=True)

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    @property
    def is_ephemeral(self) -> bool:
        return self._is_ephemeral

    @property
    def duplicate_name_warnings(self) -> list[str]:
        """Warnings produced by the last ``list_sops`` scan for collisions."""
        return list(self._duplicate_warnings)

    # --- SOP discovery ---

    def _scan(self) -> dict[str, Path]:
        """Walk ``base_dir`` recursively and return ``{name: path}``.

        The frontmatter ``name`` field is the key.  When two files declare
        the same name, the lexicographically earlier path wins and the
        collision is recorded in ``_duplicate_warnings``.
        """
        self._duplicate_warnings = []
        if not self._base_dir.exists():
            return {}

        name_to_path: dict[str, Path] = {}
        for path in sorted(self._base_dir.rglob(f"*{SOP_SUFFIX}")):
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8")
                sop = SOP.from_content(content)
            except (ValueError, OSError) as exc:
                logger.warning("Skipping unreadable SOP at %s: %s", path, exc)
                continue

            if sop.name in name_to_path:
                existing = name_to_path[sop.name]
                msg = (
                    f"Duplicate SOP name '{sop.name}': "
                    f"'{path.relative_to(self._base_dir)}' "
                    f"collides with '{existing.relative_to(self._base_dir)}' "
                    "— first wins, later duplicates are ignored."
                )
                logger.error(msg)
                self._duplicate_warnings.append(msg)
                continue

            name_to_path[sop.name] = path
        return name_to_path

    def _sop_path(self, name: str) -> Path | None:
        """Return the on-disk path of an SOP by name, or ``None`` if absent."""
        return self._scan().get(name)

    def _feedback_path_for(self, sop_path: Path) -> Path:
        """Compute the feedback path next to an SOP file."""
        name = sop_path.name[: -len(SOP_SUFFIX)]
        return sop_path.parent / f"{name}{FEEDBACK_SUFFIX}"

    # --- SOP read/write ---

    def read_sop(self, name: str, version: str | None = None) -> str:
        """Read SOP file content. ``version`` must match the file's version if given."""
        path = self._sop_path(name)
        if path is None:
            raise FileNotFoundError(f"SOP '{name}' not found")

        content = path.read_text(encoding="utf-8")
        if version is not None:
            file_version = SOP.from_content(content).version
            if file_version != version:
                raise FileNotFoundError(
                    f"Version '{version}' not found for '{name}'. Available version: {file_version}"
                )
        return content

    def write_sop(
        self,
        name: str,
        version: str,
        content: str,
        path: str | None = None,
    ) -> Path:
        """Write SOP content and return the absolute path written to.

        When ``path`` is given it is interpreted relative to ``base_dir`` and
        used as the target directory (parents are created as needed).  When
        the SOP already exists, the write updates the existing file in place
        — ``path`` is ignored in that case to prevent accidental moves.

        Raises ``ValueError`` when ``path`` resolves outside ``base_dir`` or
        when the SOP already exists at a different path than the one given.
        """
        content = set_version_in_content(content, version)

        existing = self._sop_path(name)
        if existing is not None:
            # Update in place — path parameter is informational at best.
            if path is not None:
                requested = self._resolve_subdir(path) / f"{name}{SOP_SUFFIX}"
                if requested.resolve() != existing.resolve():
                    raise ValueError(
                        f"SOP '{name}' already exists at "
                        f"'{existing.relative_to(self._base_dir)}'. "
                        "Omit 'path' to update in place, or rename the SOP."
                    )
            existing.parent.mkdir(parents=True, exist_ok=True)
            existing.write_text(content, encoding="utf-8")
            return existing

        target_dir = self._resolve_subdir(path) if path else self._base_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{name}{SOP_SUFFIX}"
        target.write_text(content, encoding="utf-8")
        return target

    def _resolve_subdir(self, path: str) -> Path:
        """Resolve a user-supplied subdirectory path inside ``base_dir``."""
        candidate = (self._base_dir / path).resolve()
        base_resolved = self._base_dir.resolve()
        try:
            candidate.relative_to(base_resolved)
        except ValueError as exc:
            raise ValueError(f"Path '{path}' resolves outside the storage directory") from exc
        return candidate

    def list_sops(self) -> list[str]:
        """Return a sorted list of SOP names discovered recursively."""
        return sorted(self._scan().keys())

    def list_versions(self, name: str) -> list[str]:
        """Return the single version carried in the file, or ``[]`` if missing."""
        path = self._sop_path(name)
        if path is None:
            return []
        try:
            sop = SOP.from_content(path.read_text(encoding="utf-8"))
        except (ValueError, FileNotFoundError):
            return []
        return [sop.version]

    def sop_exists(self, name: str, version: str | None = None) -> bool:
        path = self._sop_path(name)
        if path is None:
            return False
        if version is None:
            return True
        try:
            sop = SOP.from_content(path.read_text(encoding="utf-8"))
        except (ValueError, FileNotFoundError):
            return False
        return sop.version == version

    def sop_path_for(self, name: str) -> Path | None:
        """Public helper — return the on-disk path of an SOP by name."""
        return self._sop_path(name)

    # --- Feedback (JSONL) ---

    def _feedback_path(self, name: str) -> Path:
        """Feedback path for a named SOP — defaults to base_dir when absent."""
        sop_path = self._sop_path(name)
        if sop_path is not None:
            return self._feedback_path_for(sop_path)
        return self._base_dir / f"{name}{FEEDBACK_SUFFIX}"

    def read_feedback(self, name: str) -> str | None:
        """Return the raw JSONL feedback file content, or ``None`` if absent."""
        path = self._feedback_path(name)
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def read_feedback_entries(self, name: str) -> list[dict]:
        """Return feedback entries parsed from the JSONL file."""
        raw = self.read_feedback(name)
        if not raw:
            return []
        entries: list[dict] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("Skipping malformed feedback line for %s: %s", name, line[:80])
        return entries

    def append_feedback(self, name: str, entry: dict) -> None:
        """Append a single JSON object as a line to the feedback file."""
        path = self._feedback_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def write_feedback(self, name: str, content: str) -> None:
        """Overwrite the feedback file with raw JSONL content."""
        path = self._feedback_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    # --- Seeding ---

    def _has_sops(self, directory: Path) -> bool:
        if not directory.is_dir():
            return False
        return any(directory.rglob(f"*{SOP_SUFFIX}"))

    def _seed(self, seed_dir: Path) -> None:
        """Copy SOP files from seed_dir into base_dir when base_dir has no SOPs."""
        if self._has_sops(self._base_dir):
            return
        if not self._has_sops(seed_dir):
            return

        for src in seed_dir.rglob(f"*{SOP_SUFFIX}"):
            if not src.is_file():
                continue
            rel = src.relative_to(seed_dir)
            dest = self._base_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def _validate_storage_path(path_str: str) -> Path:
    """Validate that a storage directory path string is usable."""
    if not path_str:
        raise ValueError("Storage directory path must not be empty")
    if "\x00" in path_str:
        raise ValueError("Storage directory path must not contain null bytes")
    return Path(path_str)

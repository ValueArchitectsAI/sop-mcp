"""Storage backend protocol for SOP file operations."""

from __future__ import annotations

from typing import Protocol


class StorageBackend(Protocol):
    """Protocol defining the interface for SOP storage backends.

    Implementations provide read, write, list, and existence-check
    operations for SOP files and their associated feedback, regardless
    of the underlying storage mechanism.
    """

    @property
    def is_ephemeral(self) -> bool:
        """Whether this storage backend is ephemeral (data may be lost)."""
        ...

    def read_sop(self, name: str, version: str | None = None) -> str:
        """Read SOP file content by name and optional version.

        Returns the raw markdown content string.
        Raises FileNotFoundError if the SOP or version doesn't exist.
        """
        ...

    def write_sop(self, name: str, version: str, content: str) -> None:
        """Write SOP content to storage.

        Creates the SOP directory if needed.
        """
        ...

    def list_sops(self) -> list[str]:
        """Return sorted list of available SOP names."""
        ...

    def list_versions(self, name: str) -> list[str]:
        """Return sorted list of versions for a given SOP."""
        ...

    def sop_exists(self, name: str, version: str | None = None) -> bool:
        """Check whether a specific SOP (and optionally version) exists."""
        ...

    def read_feedback(self, name: str) -> str | None:
        """Read feedback file content for an SOP, or None if no feedback exists."""
        ...

    def write_feedback(self, name: str, content: str) -> None:
        """Write or overwrite the feedback file for an SOP."""
        ...

    def append_feedback(self, name: str, entry: str) -> None:
        """Append a feedback entry to the SOP's feedback file."""
        ...

"""Storage backend factory for SOP file operations."""

from __future__ import annotations


def get_storage_backend():
    """Create and return the local filesystem storage backend.

    Returns a LocalFilesystemBackend configured from environment variables.
    """
    from .storage import LocalFilesystemBackend

    return LocalFilesystemBackend.from_env()

"""Utility modules for SOP MCP Server."""

from .sop_parser import SOP, SOPS_DIR, ChangeType, list_available_sops, list_versions, resolve_sop
from .storage_backend import StorageBackend, get_storage_backend
from .storage_local import LocalFilesystemBackend

__all__ = [
    "SOP",
    "SOPS_DIR",
    "ChangeType",
    "LocalFilesystemBackend",
    "StorageBackend",
    "get_storage_backend",
    "list_available_sops",
    "resolve_sop",
    "list_versions",
]

# Conditionally import S3StorageBackend only if boto3 is available
try:
    from .storage_s3 import S3StorageBackend  # noqa: F401

    __all__.append("S3StorageBackend")
except ImportError:
    pass

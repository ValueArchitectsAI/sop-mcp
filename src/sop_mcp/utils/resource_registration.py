"""SOP → MCP resource registration.

Walks the storage backend, maps every discovered SOP to an
``sop://{name}`` MCP resource, and surfaces any duplicate-name collisions
found during the scan.
"""

from __future__ import annotations

import logging
import mimetypes
from typing import Any

from .storage import LocalFilesystemBackend

logger = logging.getLogger(__name__)


SOP_URI_SCHEME = "sop://"

_TEXT_MIME_PREFIXES = ("text/",)
_TEXT_MIME_TYPES = {
    "application/json",
    "application/xml",
    "application/yaml",
    "application/x-yaml",
    "application/toml",
    "application/javascript",
    "image/svg+xml",
}


def _is_text_mime(mime: str) -> bool:
    if mime.startswith(_TEXT_MIME_PREFIXES):
        return True
    return mime in _TEXT_MIME_TYPES


def _guess_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


# ---------------------------------------------------------------------------
# Reader factories
# ---------------------------------------------------------------------------


def _make_sop_reader(backend: Any, name: str) -> callable:
    """Create a reader function for an SOP document."""

    def read() -> str:
        return backend.read_sop(name)

    read.__name__ = f"read_{name}"
    read.__doc__ = f"Read the {name} SOP."
    return read


def _make_attachment_reader(backend: Any, name: str, rel: str, binary: bool) -> callable:
    """Create a reader function for an SOP attachment."""
    if binary:

        def read() -> bytes:
            return backend.read_attachment(name, rel)
    else:

        def read() -> str:
            return backend.read_attachment(name, rel).decode("utf-8")

    read.__name__ = f"read_{name}_{rel}".replace("/", "_").replace(".", "_")
    read.__doc__ = f"Read attachment '{rel}' of the {name} SOP."
    return read


# ---------------------------------------------------------------------------
# Registration helpers
# ---------------------------------------------------------------------------


def _clear_sop_resources(mcp: Any) -> None:
    """Clear prior sop:// registrations."""
    registry = getattr(mcp, "_resources", None)
    if isinstance(registry, dict):
        for uri in list(registry):
            if uri.startswith(SOP_URI_SCHEME):
                registry.pop(uri, None)


def _register_sop(mcp: Any, backend: Any, sop_name: str, sop: Any) -> None:
    """Register a single SOP and its attachments as MCP resources."""
    description = sop.description or sop.truncated_overview

    mcp.resource(
        f"{SOP_URI_SCHEME}{sop_name}",
        name=sop_name,
        description=description,
        mime_type="text/markdown",
    )(_make_sop_reader(backend, sop_name))

    _register_attachments(mcp, backend, sop_name)


def _register_attachments(mcp: Any, backend: Any, sop_name: str) -> None:
    """Register sidecar attachments for an SOP."""
    try:
        attachments = backend.list_attachments(sop_name)
    except AttributeError:
        return  # backend predates sidecar support

    for rel_path in attachments:
        mime = _guess_mime(rel_path)
        is_binary = not _is_text_mime(mime)
        uri = f"{SOP_URI_SCHEME}{sop_name}/{rel_path}"

        mcp.resource(
            uri,
            name=f"{sop_name}/{rel_path}",
            description=f"Attachment '{rel_path}' for SOP '{sop_name}'",
            mime_type=mime,
            is_binary=is_binary,
        )(_make_attachment_reader(backend, sop_name, rel_path, is_binary))


def _emit_notifications(mcp: Any) -> None:
    """Emit resource change notifications to subscribed clients."""
    notifier = getattr(mcp, "notify_resources_list_changed", None)
    if callable(notifier):
        try:
            notifier()
        except Exception as exc:
            logger.warning("Failed to emit resources/list_changed: %s", exc)

    registry = getattr(mcp, "_resources", None)
    updated_notifier = getattr(mcp, "notify_resource_updated", None)
    if callable(updated_notifier) and isinstance(registry, dict):
        for uri in list(registry):
            if uri.startswith(SOP_URI_SCHEME):
                try:
                    updated_notifier(uri)
                except Exception as exc:
                    logger.warning("Failed to emit resources/updated for %s: %s", uri, exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def register_sop_resources(
    mcp: Any,
    *,
    backend: Any = None,
    notify: bool = False,
) -> list[str]:
    """Register one MCP resource per discovered SOP plus its attachments.

    Returns duplicate-name warnings produced by the scan.
    """
    from .sop_parser import SOP

    if backend is None:
        backend = LocalFilesystemBackend.from_env()

    _clear_sop_resources(mcp)

    for sop_name in backend.list_sops():
        try:
            content = backend.read_sop(sop_name)
            sop = SOP.from_content(content)
        except (FileNotFoundError, ValueError) as exc:
            logger.warning("Skipping SOP '%s' during registration: %s", sop_name, exc)
            continue

        _register_sop(mcp, backend, sop_name, sop)

    warnings = backend.duplicate_name_warnings
    for msg in warnings:
        logger.error(msg)

    if notify:
        _emit_notifications(mcp)

    return warnings

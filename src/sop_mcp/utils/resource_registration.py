"""SOP → MCP resource registration.

Walks the storage backend, maps every discovered SOP to an
``sop://{name}`` MCP resource, and surfaces any duplicate-name collisions
found during the scan.  Safe to call repeatedly — the previous
``sop://*`` registrations are cleared before re-scanning so callers can
trigger a refresh after ``publish_sop`` without restarting the server.

In addition to the SOP document itself, any files dropped into the
sidecar folder next to the SOP are exposed as ``sop://{name}/{rel_path}``
resources so MCP clients can read attachments (checklists, rubrics,
images, …) alongside the main markdown.
"""

from __future__ import annotations

import logging
import mimetypes
from typing import Any

from .storage_backend import get_storage_backend

logger = logging.getLogger(__name__)


SOP_URI_SCHEME = "sop://"


# MIME types that should be treated as text (base64 is unnecessary and
# hurts readability).  Anything else falls back to a binary blob.
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


def register_sop_resources(
    mcp: Any,
    *,
    backend: Any = None,
    notify: bool = False,
) -> list[str]:
    """Register one MCP resource per discovered SOP plus its attachments.

    Returns the duplicate-name warnings produced by the scan (empty list
    when the tree is clean).  When ``notify`` is true and the MCP server
    exposes the corresponding notifiers, ``resources/list_changed`` is
    emitted once and ``resources/updated`` is emitted per registered URI
    so subscribed clients observe both structural and content changes.

    ``backend`` is an optional storage backend — when omitted the
    process-wide default from ``get_storage_backend()`` is used.  Callers
    that mutate a specific backend (like ``publish_sop``) should pass
    theirs in so the freshly-written SOP is part of the scan.
    """
    from .sop_parser import SOP

    if backend is None:
        backend = get_storage_backend()

    # Clear prior sop:// registrations so repeat calls don't leak stale entries.
    registry = getattr(mcp, "_resources", None)
    if isinstance(registry, dict):
        for uri in list(registry):
            if uri.startswith(SOP_URI_SCHEME):
                registry.pop(uri, None)

    for sop_name in backend.list_sops():
        try:
            content = backend.read_sop(sop_name)
            sop = SOP.from_content(content)
        except (FileNotFoundError, ValueError) as exc:
            logger.warning("Skipping SOP '%s' during registration: %s", sop_name, exc)
            continue

        description = sop.description or sop.truncated_overview

        def _make_sop_reader(name: str):
            def read() -> str:
                return backend.read_sop(name)

            read.__name__ = f"read_{name}"
            read.__doc__ = f"Read the {name} SOP."
            return read

        mcp.resource(
            f"{SOP_URI_SCHEME}{sop_name}",
            name=sop_name,
            description=description,
            mime_type="text/markdown",
        )(_make_sop_reader(sop_name))

        # Register any attachments dropped into the sidecar folder.
        try:
            attachments = backend.list_attachments(sop_name)
        except AttributeError:
            attachments = []  # backend predates sidecar support
        for rel_path in attachments:
            mime = _guess_mime(rel_path)
            is_binary = not _is_text_mime(mime)
            uri = f"{SOP_URI_SCHEME}{sop_name}/{rel_path}"

            def _make_attachment_reader(name: str, rel: str, binary: bool):
                if binary:

                    def read() -> bytes:
                        return backend.read_attachment(name, rel)
                else:

                    def read() -> str:
                        return backend.read_attachment(name, rel).decode("utf-8")

                read.__name__ = f"read_{name}_{rel}".replace("/", "_").replace(".", "_")
                read.__doc__ = f"Read attachment '{rel}' of the {name} SOP."
                return read

            mcp.resource(
                uri,
                name=f"{sop_name}/{rel_path}",
                description=f"Attachment '{rel_path}' for SOP '{sop_name}'",
                mime_type=mime,
                is_binary=is_binary,
            )(_make_attachment_reader(sop_name, rel_path, is_binary))

    warnings = backend.duplicate_name_warnings
    for msg in warnings:
        logger.error(msg)

    if notify:
        notifier = getattr(mcp, "notify_resources_list_changed", None)
        if callable(notifier):
            try:
                notifier()
            except Exception as exc:  # best-effort — never break publish on notify failure
                logger.warning("Failed to emit resources/list_changed: %s", exc)

        # Emit a per-URI updated notification for every registered SOP.  The
        # MCP server suppresses URIs that nobody subscribed to, so this is
        # cheap on the quiet path and correct on the subscribed path.
        updated_notifier = getattr(mcp, "notify_resource_updated", None)
        if callable(updated_notifier):
            for uri in list(registry or ()):
                if uri.startswith(SOP_URI_SCHEME):
                    try:
                        updated_notifier(uri)
                    except Exception as exc:
                        logger.warning("Failed to emit resources/updated for %s: %s", uri, exc)

    return warnings

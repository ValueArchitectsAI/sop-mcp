"""SOP → MCP resource registration.

Walks the storage backend, maps every discovered SOP to an
``sop://{name}`` MCP resource, and surfaces any duplicate-name collisions
found during the scan.  Safe to call repeatedly — the previous
``sop://*`` registrations are cleared before re-scanning so callers can
trigger a refresh after ``publish_sop`` without restarting the server.
"""

from __future__ import annotations

import logging
from typing import Any

from .storage_backend import get_storage_backend

logger = logging.getLogger(__name__)


SOP_URI_SCHEME = "sop://"


def register_sop_resources(
    mcp: Any,
    *,
    backend: Any = None,
    notify: bool = False,
) -> list[str]:
    """Register one MCP resource per discovered SOP.

    Returns the duplicate-name warnings produced by the scan (empty list
    when the tree is clean).  When ``notify`` is true and the MCP server
    exposes a ``notify_resources_list_changed`` helper, the notification
    is emitted after registration so clients can refresh their view.

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

        def _make_reader(name: str):
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
        )(_make_reader(sop_name))

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

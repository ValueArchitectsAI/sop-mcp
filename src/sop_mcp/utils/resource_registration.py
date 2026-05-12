"""SOP → MCP resource registration.

Walks the storage backend, maps every discovered SOP to an
``sop://{name}`` MCP resource, and surfaces any duplicate-name collisions
found during the scan.
"""

from __future__ import annotations

import logging
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .storage import LocalFilesystemBackend

logger = logging.getLogger(__name__)


SOP_URI_SCHEME = "sop://"
TEMPLATE_URI_SCHEME = "template://"

# Root of the packaged template directory. Kept outside the seeded
# SOP catalog so ``template://`` resources are never confused with
# user-authored SOPs.
_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

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

# Priority weights applied to the MCP ``annotations.priority`` field. The
# spec defines the range as 0.0 (least important) → 1.0 (most important).
# Production SOPs rank higher so clients that auto-include high-priority
# resources pick the battle-tested versions first.
_STAGE_PRIORITY = {"prod": 0.8, "preprod": 0.4}


def _is_text_mime(mime: str) -> bool:
    if mime.startswith(_TEXT_MIME_PREFIXES):
        return True
    return mime in _TEXT_MIME_TYPES


def _guess_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


def _file_size(path: Path | None) -> int | None:
    """Return the byte size of a file on disk, or ``None`` if unavailable."""
    if path is None:
        return None
    try:
        return path.stat().st_size
    except OSError:
        return None


def _file_mtime_iso(path: Path | None) -> str | None:
    """Return the file's last-modified time as an ISO 8601 UTC string."""
    if path is None:
        return None
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    # Trim microseconds and stamp with Z for the canonical UTC form the
    # MCP spec shows in its examples.
    return datetime.fromtimestamp(mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sop_annotations(sop: Any, path: Path | None) -> dict[str, Any]:
    """Compose MCP ``annotations`` for an SOP resource.

    - ``audience``: SOPs are agent-executed playbooks — flag them for the
      assistant audience so hosts know to feed them to the model rather
      than surface them in a user-facing browser by default.
    - ``priority``: derived from the SOP stage; prod > preprod.
    - ``lastModified``: file mtime when available.
    """
    annotations: dict[str, Any] = {"audience": ["assistant"]}
    stage = getattr(sop, "stage", None)
    if stage in _STAGE_PRIORITY:
        annotations["priority"] = _STAGE_PRIORITY[stage]
    mtime = _file_mtime_iso(path)
    if mtime:
        annotations["lastModified"] = mtime
    return annotations


def _attachment_annotations(path: Path | None) -> dict[str, Any]:
    """Annotations for sidecar attachments.

    Attachments are typically reference material (diagrams, checklists)
    a human reviewer might consult — mark both audiences so hosts don't
    hide them from users by default. Attachments inherit no priority;
    the client can fall back to their parent SOP's priority.
    """
    annotations: dict[str, Any] = {"audience": ["user", "assistant"]}
    mtime = _file_mtime_iso(path)
    if mtime:
        annotations["lastModified"] = mtime
    return annotations


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


def _make_file_reader(path: Path, label: str) -> callable:
    """Create a reader that returns the UTF-8 contents of a packaged file.

    Used for ``template://`` resources that ship with the package rather
    than living in the user's SOP storage directory.
    """

    def read() -> str:
        return path.read_text(encoding="utf-8")

    read.__name__ = f"read_template_{label}".replace("/", "_").replace(".", "_").replace("-", "_")
    read.__doc__ = f"Read packaged template '{label}'."
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


def _clear_template_resources(mcp: Any) -> None:
    """Clear prior template:// registrations."""
    registry = getattr(mcp, "_resources", None)
    if isinstance(registry, dict):
        for uri in list(registry):
            if uri.startswith(TEMPLATE_URI_SCHEME):
                registry.pop(uri, None)


def _register_sop(mcp: Any, backend: Any, sop_name: str, sop: Any) -> None:
    """Register a single SOP and its attachments as MCP resources."""
    description = _build_description(sop)
    sop_path = backend.sop_path_for(sop_name)

    mcp.resource(
        f"{SOP_URI_SCHEME}{sop_name}",
        name=sop_name,
        description=description,
        mime_type="text/markdown",
        meta={
            "title": getattr(sop, "title", None) or None,
            "size": _file_size(sop_path),
            "annotations": _sop_annotations(sop, sop_path),
        },
    )(_make_sop_reader(backend, sop_name))

    _register_attachments(mcp, backend, sop_name)


def _build_description(sop: Any) -> str:
    """Compose the MCP resource description.

    The agent sees this string when browsing ``resources/list`` and
    deciding which SOP to read. We serve the Overview summary plus the
    SOP's ``## Parameters`` block verbatim so the agent knows *what*
    the SOP does *and* what inputs it takes at selection time.

    The Parameters block passes through unchanged because SOP109 in
    the sop-lint rule engine enforces a consistent schema on every
    parameter bullet — no runtime transformation or summarisation is
    required.
    """
    summary = sop.description or sop.truncated_overview
    params = getattr(sop, "parameters", "") or ""
    if params:
        return f"{summary}\n\n## Parameters\n\n{params}"
    return summary


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

        attachment_path: Path | None = None
        path_lookup = getattr(backend, "attachment_path_for", None)
        if callable(path_lookup):
            attachment_path = path_lookup(sop_name, rel_path)

        mcp.resource(
            uri,
            name=f"{sop_name}/{rel_path}",
            description=f"Attachment '{rel_path}' for SOP '{sop_name}'",
            mime_type=mime,
            is_binary=is_binary,
            meta={
                "size": _file_size(attachment_path),
                "annotations": _attachment_annotations(attachment_path),
            },
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


# ---------------------------------------------------------------------------
# Template resources
# ---------------------------------------------------------------------------


def _template_annotations(path: Path) -> dict[str, Any]:
    """Annotations for packaged template resources.

    Templates are authoring aids: useful to both humans writing SOPs and
    agents helping to draft them. Mark both audiences. Priority is kept
    below a production SOP's (0.8) so auto-inclusion heuristics don't
    favour the template over real playbooks.
    """
    annotations: dict[str, Any] = {
        "audience": ["user", "assistant"],
        "priority": 0.5,
    }
    mtime = _file_mtime_iso(path)
    if mtime:
        annotations["lastModified"] = mtime
    return annotations


def register_template_resources(mcp: Any, *, notify: bool = False) -> list[str]:
    """Register every ``*.sop.md`` file under ``templates/`` as a template.

    The URI is derived from the filename stem (minus the ``.sop`` suffix):
    ``sop.sop.md`` → ``template://sop``. Dropping a new file into the
    templates directory is enough to expose it — no registry update
    required.

    Returns the list of URIs registered so callers can log it.
    """
    _clear_template_resources(mcp)

    if not _TEMPLATES_DIR.is_dir():
        return []

    registered: list[str] = []
    for path in sorted(_TEMPLATES_DIR.glob("*.sop.md")):
        # Strip both the ``.md`` and the ``.sop`` part to get the URI stem.
        identifier = path.name.removesuffix(".sop.md")
        uri = f"{TEMPLATE_URI_SCHEME}{identifier}"
        # Short stems (≤3 chars) are almost always acronyms — "sop",
        # "api", "cdk" — so keep them uppercase. Longer stems are
        # human-readable words; title-case them with separators
        # normalised to spaces.
        display = identifier.upper() if len(identifier) <= 3 else identifier.replace("-", " ").replace("_", " ").title()
        title = f"{display} Template"
        description = (
            f"Lint-clean scaffold for authoring a new {display}. Every section is a "
            "TODO placeholder that already satisfies the sop-lint rules — copy the "
            "body, replace each TODO, and the result will lint clean without "
            "structural fixes."
        )

        mcp.resource(
            uri,
            name=identifier,
            description=description,
            mime_type="text/markdown",
            meta={
                "title": title,
                "size": _file_size(path),
                "annotations": _template_annotations(path),
            },
        )(_make_file_reader(path, identifier))
        registered.append(uri)

    if notify:
        _emit_notifications(mcp)

    return registered

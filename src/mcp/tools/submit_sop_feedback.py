"""Submit SOP feedback tool — discovered by FileSystemProvider."""

import logging
from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from fastmcp.tools import tool
from pydantic import Field

from src.utils import SOP, get_storage_backend

logger = logging.getLogger(__name__)


def _get_backend():
    """Lazy import to use the same backend instance as src.server (supports test patching)."""
    import src.server

    return src.server.backend


EPHEMERAL_WARNING = (
    "⚠️ WARNING: This data was written to ephemeral storage and may be lost "
    "when the package cache is refreshed. Set the SOP_STORAGE_DIR environment "
    "variable to a persistent path to avoid data loss."
)

# Use get_storage_backend() directly for schema generation (avoids circular import)
_available_sops = get_storage_backend().list_sops()
_SopNameType = Literal[tuple(_available_sops)] if _available_sops else str


@tool()
def submit_sop_feedback(
    sop_name: Annotated[_SopNameType, Field(description=f"Name of the SOP. Available: {', '.join(_available_sops)}.")],
    feedback: Annotated[str, Field(min_length=1, description="The improvement suggestion or feedback text.")],
) -> dict[str, Any]:
    """Submit improvement feedback for a specific SOP.

    Collects user feedback about an SOP and stores it in a feedback.md file
    inside the SOP's folder. This feedback will be used to optimize the SOP
    in its next revision.
    """
    logger.info("Invoking submit_sop_feedback with args: sop_name=%s, feedback=<%s chars>", sop_name, len(feedback))

    content = _get_backend().read_sop(sop_name)
    sop = SOP.from_content(content)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = f"## Feedback — {timestamp}\n\n**SOP Version:** v{sop.version}\n\n{feedback}\n\n---\n\n"

    try:
        _get_backend().append_feedback(sop_name, entry)
    except OSError as e:
        logger.warning("Failed to write feedback for %s: %s", sop_name, e)
        return {"error": f"Failed to write feedback file: {e}"}

    logger.info("Feedback submitted for %s v%s at %s", sop_name, sop.version, timestamp)
    result: dict[str, Any] = {
        "success": True,
        "sop_name": sop_name,
        "sop_version": sop.version,
        "timestamp": timestamp,
        "message": f"Feedback recorded for '{sop_name}' (v{sop.version}). It will be considered in the next revision.",
    }
    if _get_backend().is_ephemeral:
        result["warning"] = EPHEMERAL_WARNING
    return result

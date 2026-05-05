"""Submit SOP feedback tool."""

import logging
from datetime import datetime, timezone
from typing import Any

from src.sop_mcp.utils import SOP
from src.sop_mcp.utils.storage import LocalFilesystemBackend

logger = logging.getLogger(__name__)


backend = LocalFilesystemBackend.from_env()

NAME = "submit_sop_feedback"
DESCRIPTION = (
    "Submit improvement feedback for a specific SOP.\n\n"
    "Feedback is appended as a single JSON line to\n"
    "{sop_name}.feedback.jsonl inside the SOP's folder. Each entry\n"
    "captures the SOP version, a UTC timestamp, and the feedback text — ready\n"
    "for review when the SOP is next revised."
)


def handler(
    sop_name: str,
    feedback: str,
) -> dict[str, Any]:
    """Record feedback for an SOP as a JSON line in the feedback log."""
    logger.info("Invoking submit_sop_feedback: sop_name=%s, feedback=<%s chars>", sop_name, len(feedback))

    if not backend.sop_exists(sop_name):
        raise ValueError(f"SOP '{sop_name}' not found. Available: {', '.join(backend.list_sops())}")

    sop = SOP.from_content(backend.read_sop(sop_name))
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    entry = {
        "timestamp": timestamp,
        "sop_version": sop.version,
        "stage": sop.stage,
        "feedback": feedback,
    }

    try:
        backend.append_feedback(sop_name, entry)
    except OSError as e:
        logger.warning("Failed to write feedback for %s: %s", sop_name, e)
        return {"error": f"Failed to write feedback file: {e}"}

    logger.info("Feedback recorded for %s v%s at %s", sop_name, sop.version, timestamp)
    return {
        "success": True,
        "sop_name": sop_name,
        "sop_version": sop.version,
        "timestamp": timestamp,
        "message": f"Feedback recorded for '{sop_name}'.",
    }

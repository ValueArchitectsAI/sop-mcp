"""SOP content resources — expose SOP documents and metadata for reading."""

from __future__ import annotations

from typing import Any

from src.sop_mcp.utils import get_storage_backend

backend = get_storage_backend()


def register_sop_resources(mcp: Any) -> None:
    """Register concrete resources per SOP for discoverability in list_resources."""
    from src.sop_mcp.utils import SOP

    for sop_name in backend.list_sops():
        versions = backend.list_versions(sop_name)
        if not versions:
            continue

        try:
            content = backend.read_sop(sop_name)
            sop = SOP.from_content(content)
        except (FileNotFoundError, ValueError):
            continue

        def _make_latest_reader(name: str):
            def read_latest() -> str:
                return backend.read_sop(name)

            read_latest.__name__ = f"read_{name}_latest"
            read_latest.__doc__ = f"Read the latest version of {name} SOP."
            return read_latest

        mcp.resource(
            f"sop://{sop_name}",
            name=f"{sop_name}",
            description=sop.truncated_overview,
            mime_type="text/markdown",
        )(_make_latest_reader(sop_name))

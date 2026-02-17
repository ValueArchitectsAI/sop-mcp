"""SOP content resources — expose SOP documents and metadata for reading."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastmcp.resources import resource

from src.utils import get_storage_backend

if TYPE_CHECKING:
    from fastmcp import FastMCP

backend = get_storage_backend()


# Resource template for reading SOPs — version is optional (defaults to latest)
@resource(
    "sop://{sop_name}{?version}",
    name="SOP",
    description="Read an SOP document. Defaults to latest version unless a specific version is provided via ?version=.",
    mime_type="text/markdown",
    annotations={"readOnlyHint": True},
)
def read_sop_resource(sop_name: str, version: str = None) -> str:
    """Read an SOP, optionally at a specific version."""
    return backend.read_sop(sop_name, version)


def register_sop_resources(mcp: FastMCP) -> None:
    """Register concrete resources per SOP for discoverability in list_resources."""
    from src.utils import SOP

    for sop_name in backend.list_sops():
        versions = backend.list_versions(sop_name)
        if not versions:
            continue

        try:
            content = backend.read_sop(sop_name)
            sop = SOP.from_content(content)
        except (FileNotFoundError, ValueError):
            continue

        # Concrete resource: sop://{name}/versions
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
            annotations={"readOnlyHint": True},
            meta={"version": sop.version, "total_steps": sop.total_steps},
        )(_make_latest_reader(sop_name))

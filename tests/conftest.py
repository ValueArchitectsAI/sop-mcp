"""Shared pytest fixtures for sop-mcp tests.

The most important one — ``_isolate_bundled_sops_dir`` — is autouse and
session-scoped.  It snapshots the contents of ``src/sop_mcp/resources/``
at session start and wipes any extra files at session end.  This protects
the bundled SOP catalogue from leaking test-generated markdown files
produced by hypothesis round-trips, e2e publish calls, and anything else
that forgets to tidy up after itself.

The fixture does **not** mask leaks during a test run — it runs cleanup
at teardown, not between tests — because some tests depend on files
persisting across multiple hypothesis examples inside the same function.
It does ensure the repository is never left polluted after a pytest run.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from src.sop_mcp.utils.storage import BUNDLED_SOPS_DIR


@pytest.fixture(scope="session", autouse=True)
def _isolate_bundled_sops_dir() -> None:
    """Wipe any test-generated files from the bundled SOPs dir at teardown."""
    snapshot = _snapshot(BUNDLED_SOPS_DIR)
    yield
    _restore(BUNDLED_SOPS_DIR, snapshot)


def _snapshot(root: Path) -> dict[Path, bytes]:
    """Return a {relative_path: bytes} map of the directory contents."""
    if not root.is_dir():
        return {}
    out: dict[Path, bytes] = {}
    for path in root.rglob("*"):
        if path.is_file():
            out[path.relative_to(root)] = path.read_bytes()
    return out


def _restore(root: Path, snapshot: dict[Path, bytes]) -> None:
    """Delete anything not in ``snapshot`` and rewrite anything that drifted."""
    if not root.is_dir():
        return

    kept = set(snapshot.keys())
    # Drop files that weren't there at session start.
    for path in list(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if rel not in kept:
            with contextlib.suppress(OSError):
                path.unlink()

    # Rewrite any file whose contents changed during the session.
    for rel, original in snapshot.items():
        target = root / rel
        if not target.exists() or target.read_bytes() != original:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original)

    # Clean up any now-empty directories created by nested test writes.
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            with contextlib.suppress(OSError):
                path.rmdir()

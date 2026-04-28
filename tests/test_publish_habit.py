"""Publish-time habits: flat + nested writes, collision protection, and
live MCP resource re-registration after publish.

These tests exercise the contract added alongside recursive SOP
discovery:

1. A fresh publish writes the file and registers an ``sop://{name}``
   resource immediately — no restart required.
2. Re-publishing the same ``name`` updates the file in place and bumps
   the version.
3. An optional ``path`` argument routes the file under a subdirectory;
   identity is still the frontmatter ``name``.
4. Publishing a new SOP whose ``name`` collides with one already on disk
   at a different path is rejected.
5. Paths that try to escape the storage root (``../..``) are rejected.
6. Nested SOPs are discoverable via ``list_sops`` / ``read_sop`` / the
   MCP resource URI by name, regardless of their on-disk location.
7. Two files on disk with the same frontmatter ``name`` do not crash the
   server — the first wins and the duplicate is surfaced as a warning.
8. Live resource list refresh: calling ``register_sop_resources`` after a
   publish replaces any stale ``sop://`` entries and keeps the list in
   sync with what's on disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import src.sop_mcp.server as server_module
import src.sop_mcp.tools.publish_sop as publish_module
from src.sop_mcp.utils import register_sop_resources
from src.sop_mcp.utils.stdiomcp import StdioMCP
from src.sop_mcp.utils.storage import LocalFilesystemBackend

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sop_content(name: str, overview: str = "Overview text for the test SOP.") -> str:
    return (
        "---\n"
        f"name: {name}\n"
        "version: 1\n"
        "owner: tests\n"
        "stage: preprod\n"
        "---\n\n"
        f"# Test SOP: {name}\n\n"
        f"## Overview\n\n{overview}\n\n"
        "### Step 1: Do the thing\n\n"
        "Perform the action. **Time Estimate:** 1 minute\n"
    )


def _publish(content: str, *, stage: str = "preprod", **kwargs):
    """Thin wrapper: publish_sop.handler with stage defaulted to 'preprod'."""
    return publish_module.handler(content, stage=stage, **kwargs)


@pytest.fixture
def isolated_publish(tmp_path: Path, monkeypatch):
    """Wire publish_sop (and the server's resource registry) to a tmp backend.

    Yields a ``(backend, mcp)`` tuple.  The MCP server is a fresh
    ``StdioMCP`` instance so the ``sop://`` resource list starts empty
    and we can observe exactly what each publish registers.
    """
    backend = LocalFilesystemBackend(base_dir=tmp_path, is_ephemeral=False)
    mcp = StdioMCP("test-mcp")

    monkeypatch.setattr(publish_module, "backend", backend)
    monkeypatch.setattr(server_module, "backend", backend)
    monkeypatch.setattr(server_module, "mcp", mcp)

    yield backend, mcp


def _resource_uris(mcp: StdioMCP) -> set[str]:
    return {uri for uri in mcp._resources if uri.startswith("sop://")}


# ---------------------------------------------------------------------------
# 1. Fresh publish + immediate MCP resource registration
# ---------------------------------------------------------------------------


class TestFreshPublish:
    def test_publish_writes_file_at_root(self, isolated_publish):
        backend, _ = isolated_publish
        result = _publish(_sop_content("alpha_sop_one"))

        assert result["success"] is True
        assert result["sop_name"] == "alpha_sop_one"
        assert (backend.base_dir / "alpha_sop_one.sop.md").is_file()
        assert result["path"] == "alpha_sop_one.sop.md"

    def test_publish_registers_mcp_resource_without_restart(self, isolated_publish):
        _, mcp = isolated_publish
        assert "sop://alpha_sop_two" not in _resource_uris(mcp)

        _publish(_sop_content("alpha_sop_two"))

        assert "sop://alpha_sop_two" in _resource_uris(mcp)


# ---------------------------------------------------------------------------
# 2. In-place updates bump the version
# ---------------------------------------------------------------------------


class TestInPlaceUpdate:
    def test_republish_same_name_bumps_version(self, isolated_publish):
        backend, _ = isolated_publish
        r1 = _publish(_sop_content("bump_sop"))
        r2 = _publish(_sop_content("bump_sop"))

        assert r1["version"] == 1
        assert r2["version"] == 2

        # Only one file on disk — the update is in-place.
        hits = list(backend.base_dir.rglob("bump_sop.sop.md"))
        assert len(hits) == 1


# ---------------------------------------------------------------------------
# 3. Optional path parameter routes to a subdirectory
# ---------------------------------------------------------------------------


class TestNestedPath:
    def test_publish_with_path_writes_under_subdir(self, isolated_publish):
        backend, _ = isolated_publish
        result = _publish(
            _sop_content("nested_sop_one"),
            path="generated/",
        )

        assert result["success"] is True
        assert (backend.base_dir / "generated" / "nested_sop_one.sop.md").is_file()
        assert result["path"].replace("\\", "/") == "generated/nested_sop_one.sop.md"

    def test_publish_with_deep_path_creates_parents(self, isolated_publish):
        backend, _ = isolated_publish
        _publish(
            _sop_content("deep_sop"),
            path="teams/platform/playbooks",
        )
        assert (backend.base_dir / "teams" / "platform" / "playbooks" / "deep_sop.sop.md").is_file()


# ---------------------------------------------------------------------------
# 4. Collision: name already exists at a different path
# ---------------------------------------------------------------------------


class TestCollisionProtection:
    def test_publish_rejects_same_name_at_different_path(self, isolated_publish):
        backend, _ = isolated_publish
        r1 = _publish(_sop_content("collide_sop"), path="teamA/")
        assert r1["success"] is True

        r2 = _publish(_sop_content("collide_sop"), path="teamB/")

        assert "error" in r2
        assert "already exists" in r2["error"]
        # Original file is untouched; no new file created under teamB.
        assert (backend.base_dir / "teamA" / "collide_sop.sop.md").is_file()
        assert not (backend.base_dir / "teamB" / "collide_sop.sop.md").exists()

    def test_republish_without_path_updates_even_when_nested(self, isolated_publish):
        backend, _ = isolated_publish
        _publish(_sop_content("nested_update_sop"), path="generated/")

        # Republishing without a path should find and update the nested file.
        r2 = _publish(_sop_content("nested_update_sop"))

        assert r2["success"] is True
        assert r2["version"] == 2
        # Still only one file; still in generated/.
        assert (backend.base_dir / "generated" / "nested_update_sop.sop.md").is_file()
        assert not (backend.base_dir / "nested_update_sop.sop.md").exists()


# ---------------------------------------------------------------------------
# 5. Path traversal is rejected
# ---------------------------------------------------------------------------


class TestPathTraversal:
    def test_publish_rejects_parent_escape(self, isolated_publish):
        backend, _ = isolated_publish
        result = _publish(
            _sop_content("escape_sop"),
            path="../../../etc",
        )
        assert "error" in result
        assert "outside" in result["error"].lower()
        # No file written anywhere inside the storage dir.
        assert list(backend.base_dir.rglob("escape_sop.sop.md")) == []


# ---------------------------------------------------------------------------
# 6. Recursive discovery: nested SOPs are findable by name
# ---------------------------------------------------------------------------


class TestRecursiveDiscovery:
    def test_nested_sop_appears_in_list_sops(self, isolated_publish):
        backend, _ = isolated_publish
        _publish(_sop_content("flat_sop"))
        _publish(_sop_content("deeply_nested_sop"), path="a/b/c/")

        names = backend.list_sops()
        assert "flat_sop" in names
        assert "deeply_nested_sop" in names

    def test_nested_sop_readable_by_name(self, isolated_publish):
        backend, _ = isolated_publish
        _publish(_sop_content("readable_nested"), path="generated/")

        content = backend.read_sop("readable_nested")
        assert "name: readable_nested" in content

    def test_nested_sop_registered_under_flat_uri(self, isolated_publish):
        _, mcp = isolated_publish
        _publish(_sop_content("uri_nested"), path="subdir/")

        # URI is always sop://{name} — path stays organizational only.
        assert "sop://uri_nested" in _resource_uris(mcp)


# ---------------------------------------------------------------------------
# 7. Duplicate frontmatter names on disk: first wins, warning is exposed
# ---------------------------------------------------------------------------


class TestDuplicateOnDisk:
    def test_duplicate_files_do_not_crash_scan(self, tmp_path: Path):
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        (tmp_path / "one").mkdir()
        (tmp_path / "two").mkdir()
        (tmp_path / "one" / "dupe.sop.md").write_text(_sop_content("dupe"))
        (tmp_path / "two" / "dupe.sop.md").write_text(_sop_content("dupe"))

        names = backend.list_sops()
        assert names == ["dupe"]

        warnings = backend.duplicate_name_warnings
        assert len(warnings) == 1
        assert "dupe" in warnings[0]
        assert "one/dupe.sop.md" in warnings[0].replace("\\", "/")
        assert "two/dupe.sop.md" in warnings[0].replace("\\", "/")


# ---------------------------------------------------------------------------
# 8. Live re-registration keeps the resource list in sync
# ---------------------------------------------------------------------------


class TestLiveReRegistration:
    def test_register_clears_stale_uris(self, isolated_publish):
        backend, mcp = isolated_publish

        _publish(_sop_content("temp_sop"))
        assert "sop://temp_sop" in _resource_uris(mcp)

        # Simulate external deletion of the underlying file.
        (backend.base_dir / "temp_sop.sop.md").unlink()

        # Re-registration should drop the now-missing URI.
        register_sop_resources(mcp, backend=backend)
        assert "sop://temp_sop" not in _resource_uris(mcp)

    def test_publish_keeps_other_sops_registered(self, isolated_publish):
        _, mcp = isolated_publish

        _publish(_sop_content("keep_one"))
        _publish(_sop_content("keep_two"))

        uris = _resource_uris(mcp)
        assert {"sop://keep_one", "sop://keep_two"}.issubset(uris)

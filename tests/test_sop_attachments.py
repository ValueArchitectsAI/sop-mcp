"""Sidecar attachments: files placed in ``{base}/{path}/{name}/`` alongside
``{base}/{path}/{name}.sop.md`` are exposed as MCP resources at
``sop://{name}/{relative_path}``.

Covers:
- Backend discovery (``list_attachments`` + ``read_attachment``)
- Blacklist (dotfiles, ``__pycache__``) is honored
- Path traversal out of the sidecar is rejected
- ``register_sop_resources`` registers attachments alongside the SOP
- Text vs binary MIME detection round-trips correctly
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from src.sop_mcp.utils import register_sop_resources
from src.sop_mcp.utils.stdiomcp import StdioMCP
from src.sop_mcp.utils.storage import LocalFilesystemBackend

SOP_CONTENT = (
    "---\n"
    "name: attach_sop_one\n"
    "version: 1\n"
    "owner: tests\n"
    "stage: preprod\n"
    "---\n\n"
    "# Attach SOP One\n\n"
    "## Overview\n\nWith friends.\n\n"
    "### Step 1: Go\n\nAction. **Time Estimate:** 1 minute\n"
)


@pytest.fixture
def backend_with_attachments(tmp_path: Path):
    """Fresh backend holding one SOP and a sidecar folder with
    several attachments."""
    base = tmp_path
    backend = LocalFilesystemBackend(base_dir=base, is_ephemeral=False)

    # The SOP markdown.
    (base / "attach_sop_one.sop.md").write_text(SOP_CONTENT)

    # Sidecar folder with mixed attachments.
    sidecar = base / "attach_sop_one"
    sidecar.mkdir()
    (sidecar / "rubric.md").write_text("# Rubric\n\nKeep it simple.\n")
    (sidecar / "checklist.json").write_text('{"items": ["a", "b"]}')
    (sidecar / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\nfake-png-bytes")

    # Nested attachment + blacklist noise that should be ignored.
    nested = sidecar / "examples"
    nested.mkdir()
    (nested / "flow.md").write_text("flow text")

    (sidecar / ".DS_Store").write_bytes(b"mac noise")
    (sidecar / ".hidden_file").write_text("hidden")
    cache = sidecar / "__pycache__"
    cache.mkdir()
    (cache / "cached.pyc").write_bytes(b"bytecode")

    return backend


class TestListAttachments:
    def test_lists_only_visible_files(self, backend_with_attachments):
        names = backend_with_attachments.list_attachments("attach_sop_one")
        assert names == sorted(
            [
                "checklist.json",
                "examples/flow.md",
                "logo.png",
                "rubric.md",
            ]
        )

    def test_returns_empty_for_sop_without_sidecar(self, tmp_path: Path):
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        (tmp_path / "solo.sop.md").write_text(SOP_CONTENT.replace("attach_sop_one", "solo_sop"))
        assert backend.list_attachments("solo_sop") == []

    def test_returns_empty_for_unknown_sop(self, backend_with_attachments):
        assert backend_with_attachments.list_attachments("nope") == []


class TestReadAttachment:
    def test_reads_text_attachment_as_bytes(self, backend_with_attachments):
        data = backend_with_attachments.read_attachment("attach_sop_one", "rubric.md")
        assert data == b"# Rubric\n\nKeep it simple.\n"

    def test_reads_binary_attachment(self, backend_with_attachments):
        data = backend_with_attachments.read_attachment("attach_sop_one", "logo.png")
        assert data.startswith(b"\x89PNG")

    def test_reads_nested_attachment(self, backend_with_attachments):
        data = backend_with_attachments.read_attachment("attach_sop_one", "examples/flow.md")
        assert data == b"flow text"

    def test_rejects_path_traversal(self, backend_with_attachments):
        with pytest.raises(ValueError, match="escapes"):
            backend_with_attachments.read_attachment("attach_sop_one", "../outside.txt")

    def test_raises_for_missing_attachment(self, backend_with_attachments):
        with pytest.raises(FileNotFoundError):
            backend_with_attachments.read_attachment("attach_sop_one", "missing.md")

    def test_raises_for_sop_without_sidecar(self, tmp_path: Path):
        backend = LocalFilesystemBackend(base_dir=tmp_path)
        (tmp_path / "solo.sop.md").write_text(SOP_CONTENT.replace("attach_sop_one", "solo_sop"))
        with pytest.raises(FileNotFoundError, match="No sidecar"):
            backend.read_attachment("solo_sop", "any.md")


class TestResourceRegistration:
    def test_registers_sop_and_attachments(self, backend_with_attachments):
        mcp = StdioMCP("test")
        register_sop_resources(mcp, backend=backend_with_attachments)

        uris = {uri for uri in mcp._resources if uri.startswith("sop://")}
        assert "sop://attach_sop_one" in uris
        assert "sop://attach_sop_one/rubric.md" in uris
        assert "sop://attach_sop_one/checklist.json" in uris
        assert "sop://attach_sop_one/logo.png" in uris
        assert "sop://attach_sop_one/examples/flow.md" in uris

    def test_infers_markdown_mime_for_md_attachment(self, backend_with_attachments):
        mcp = StdioMCP("test")
        register_sop_resources(mcp, backend=backend_with_attachments)
        resource = mcp._resources["sop://attach_sop_one/rubric.md"]
        assert resource.mime_type == "text/markdown"
        assert resource.is_binary is False

    def test_infers_json_mime_as_text(self, backend_with_attachments):
        mcp = StdioMCP("test")
        register_sop_resources(mcp, backend=backend_with_attachments)
        resource = mcp._resources["sop://attach_sop_one/checklist.json"]
        assert resource.mime_type == "application/json"
        assert resource.is_binary is False

    def test_png_is_registered_as_binary(self, backend_with_attachments):
        mcp = StdioMCP("test")
        register_sop_resources(mcp, backend=backend_with_attachments)
        resource = mcp._resources["sop://attach_sop_one/logo.png"]
        assert resource.mime_type == "image/png"
        assert resource.is_binary is True

    def test_read_resource_returns_text_for_md(self, backend_with_attachments):
        mcp = StdioMCP("test")
        register_sop_resources(mcp, backend=backend_with_attachments)

        response = mcp._handle_request("resources/read", {"uri": "sop://attach_sop_one/rubric.md"}, 1)
        contents = response["result"]["contents"][0]
        assert contents["mimeType"] == "text/markdown"
        assert "text" in contents
        assert "Keep it simple" in contents["text"]

    def test_read_resource_returns_blob_for_binary(self, backend_with_attachments):
        mcp = StdioMCP("test")
        register_sop_resources(mcp, backend=backend_with_attachments)

        response = mcp._handle_request("resources/read", {"uri": "sop://attach_sop_one/logo.png"}, 1)
        contents = response["result"]["contents"][0]
        assert contents["mimeType"] == "image/png"
        assert "blob" in contents
        assert base64.b64decode(contents["blob"]).startswith(b"\x89PNG")

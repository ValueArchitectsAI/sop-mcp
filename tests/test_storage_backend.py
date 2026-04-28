"""Property-based tests for LocalFilesystemBackend.

Uses hypothesis to verify correctness properties of the storage layer
under the integer-version + YAML-frontmatter contract.
"""

from __future__ import annotations

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from src.sop_mcp.utils.storage import LocalFilesystemBackend

# --- Strategies ---

sop_name_segment = st.text(
    alphabet=string.ascii_lowercase,
    min_size=1,
    max_size=8,
)

sop_names = st.lists(sop_name_segment, min_size=2, max_size=4).map(lambda parts: "_".join(parts))

# Integer versions — 1, 2, 3, … (bounded for test tractability).
integer_versions = st.integers(min_value=1, max_value=99)


def _valid_content(name: str, version: int, body: str = "Overview text.") -> str:
    """Build a minimal SOP markdown that parses under the current parser."""
    return (
        "---\n"
        f"name: {name}\n"
        f"version: {version}\n"
        "owner: tests\n"
        "stage: preprod\n"
        "---\n\n"
        f"# Test SOP {name}\n\n"
        f"## Overview\n\n{body}\n\n"
        "### Step 1: Do\n\nDo the thing.\n"
    )


# Strategy for SOP markdown content with an injectable overview.
sop_content = st.text(
    alphabet=st.characters(categories=("L", "N", "Z")),
    min_size=1,
    max_size=60,
).filter(lambda s: s.strip() and "\n" not in s)


# Property 1: Write-read round trip.
@settings(max_examples=100, deadline=None)
@given(name=sop_names, version=integer_versions, overview=sop_content)
def test_write_read_round_trip(tmp_path_factory, name: str, version: int, overview: str) -> None:
    """For any valid SOP name, integer version, and overview body, writing
    then reading back should return the same content."""
    base_dir = tmp_path_factory.mktemp("sops")
    backend = LocalFilesystemBackend(base_dir=base_dir)

    content = _valid_content(name, version, overview)
    backend.write_sop(name, version, content)
    result = backend.read_sop(name, version)

    assert result == content


# Property 2: Listing reflects written SOPs.
@settings(max_examples=50, deadline=None)
@given(
    data=st.data(),
    num_sops=st.integers(min_value=1, max_value=5),
)
def test_listing_reflects_written_sops(tmp_path_factory, data: st.DataObject, num_sops: int) -> None:
    """For any set of distinct SOP names written to a fresh backend,
    list_sops() returns exactly those names sorted, and list_versions(name)
    returns exactly the single integer version written for that name."""
    base_dir = tmp_path_factory.mktemp("sops")
    backend = LocalFilesystemBackend(base_dir=base_dir)

    names = data.draw(st.lists(sop_names, min_size=num_sops, max_size=num_sops, unique=True))

    expected_versions: dict[str, int] = {}
    for name in names:
        version = data.draw(integer_versions)
        expected_versions[name] = version
        overview = data.draw(sop_content)
        backend.write_sop(name, version, _valid_content(name, version, overview))

    assert backend.list_sops() == sorted(names)
    for name, version in expected_versions.items():
        assert backend.list_versions(name) == [version]


# Property 3: Path validation rejects invalid paths.
@settings(max_examples=100, deadline=None)
@given(
    path_str=st.one_of(
        st.just(""),
        st.text(min_size=1, max_size=100).map(lambda s: s + "\x00"),
        st.text(min_size=1, max_size=100).map(lambda s: "\x00" + s),
        st.text(min_size=0, max_size=50).flatmap(
            lambda prefix: st.text(min_size=0, max_size=50).map(lambda suffix: prefix + "\x00" + suffix)
        ),
    )
)
def test_path_validation_rejects_invalid_paths(path_str: str) -> None:
    """For any string that is empty or contains null bytes,
    _validate_storage_path should raise ValueError."""
    import pytest

    from src.sop_mcp.utils.storage import _validate_storage_path

    with pytest.raises(ValueError):
        _validate_storage_path(path_str)


# Property 4: Ephemeral warning if and only if the backend is ephemeral.
# Strategy for SOP doc IDs: 3+ underscore-separated lowercase segments.
sop_doc_ids = st.lists(
    st.text(alphabet=string.ascii_lowercase, min_size=2, max_size=6),
    min_size=3,
    max_size=5,
).map(lambda parts: "_".join(parts))

non_empty_text = st.text(
    alphabet=st.characters(categories=("L", "N", "Z")),
    min_size=1,
    max_size=80,
)


@settings(max_examples=50, deadline=None)
@given(
    is_ephemeral=st.booleans(),
    doc_id=sop_doc_ids,
    overview=non_empty_text,
    feedback_text=non_empty_text,
)
def test_ephemeral_warning_iff_ephemeral_backend(
    tmp_path_factory,
    is_ephemeral: bool,
    doc_id: str,
    overview: str,
    feedback_text: str,
) -> None:
    """publish_sop and submit_sop_feedback return an ephemeral storage
    warning if and only if the backend is ephemeral."""
    import src.sop_mcp.server as server_module
    import src.sop_mcp.tools.publish_sop as publish_module
    import src.sop_mcp.tools.submit_sop_feedback as feedback_module

    base_dir = tmp_path_factory.mktemp("sops")
    test_backend = LocalFilesystemBackend(base_dir=base_dir, is_ephemeral=is_ephemeral)

    original_server_backend = server_module.backend
    original_feedback_backend = feedback_module.backend
    original_publish_backend = publish_module.backend
    server_module.backend = test_backend
    feedback_module.backend = test_backend
    publish_module.backend = test_backend
    try:
        content = _valid_content(doc_id, 1, overview)

        publish_result = publish_module.handler(content)
        assert publish_result.get("success") is True, f"publish_sop failed: {publish_result}"

        if is_ephemeral:
            assert "warning" in publish_result, "Expected ephemeral warning in publish result"
            assert publish_module.EPHEMERAL_WARNING in publish_result["warning"]
        else:
            assert publish_module.EPHEMERAL_WARNING not in publish_result.get("warning", "")

        feedback_result = feedback_module.handler(doc_id, feedback_text)
        assert feedback_result.get("success") is True, f"submit_sop_feedback failed: {feedback_result}"

        if is_ephemeral:
            assert "warning" in feedback_result, "Expected ephemeral warning in feedback result"
            assert feedback_module.EPHEMERAL_WARNING in feedback_result["warning"]
        else:
            assert feedback_module.EPHEMERAL_WARNING not in feedback_result.get("warning", "")
    finally:
        server_module.backend = original_server_backend
        feedback_module.backend = original_feedback_backend
        publish_module.backend = original_publish_backend

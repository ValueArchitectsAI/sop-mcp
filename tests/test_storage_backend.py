"""Property-based tests for LocalFilesystemBackend.

Uses hypothesis to verify correctness properties defined in the design document.
"""

from __future__ import annotations

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from src.utils.storage_local import LocalFilesystemBackend


# --- Strategies ---

sop_name_segment = st.text(
    alphabet=string.ascii_lowercase,
    min_size=1,
    max_size=8,
)

sop_names = st.lists(sop_name_segment, min_size=2, max_size=4).map(lambda parts: "_".join(parts))

semver_versions = st.builds(
    lambda ma, mi, pa: f"{ma}.{mi}.{pa}",
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
)

sop_content = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "Z", "S")),
    min_size=1,
    max_size=500,
)


# Feature: sop-storage-abstraction, Property 1: Write-read round trip
# Validates: Requirements 2.5, 2.6
@settings(max_examples=100)
@given(name=sop_names, version=semver_versions, content=sop_content)
def test_write_read_round_trip(tmp_path_factory, name: str, version: str, content: str) -> None:
    """For any valid SOP name, version, and content, writing then reading
    back should return the original content."""
    base_dir = tmp_path_factory.mktemp("sops")
    backend = LocalFilesystemBackend(base_dir=base_dir)

    backend.write_sop(name, version, content)
    result = backend.read_sop(name, version)

    assert result == content


# Feature: sop-storage-abstraction, Property 2: Listing reflects written SOPs
# Validates: Requirements 2.3, 2.7
@settings(max_examples=100)
@given(
    data=st.data(),
    num_sops=st.integers(min_value=1, max_value=5),
)
def test_listing_reflects_written_sops(
    tmp_path_factory, data: st.DataObject, num_sops: int
) -> None:
    """For any set of distinct SOP names and versions written to a fresh
    backend, list_sops() returns a sorted list containing exactly those
    names, and list_versions(name) returns exactly the versions written
    for that name."""
    base_dir = tmp_path_factory.mktemp("sops")
    backend = LocalFilesystemBackend(base_dir=base_dir)

    # Generate distinct SOP names
    names = data.draw(
        st.lists(sop_names, min_size=num_sops, max_size=num_sops, unique=True)
    )

    expected_versions: dict[str, list[str]] = {}
    for name in names:
        # Each SOP gets 1-3 distinct versions
        versions = data.draw(
            st.lists(semver_versions, min_size=1, max_size=3, unique=True)
        )
        expected_versions[name] = versions
        for ver in versions:
            content = data.draw(sop_content)
            backend.write_sop(name, ver, content)

    # list_sops should return exactly the written names, sorted
    assert backend.list_sops() == sorted(names)

    # list_versions should return exactly the written versions for each name, sorted by semver
    for name, versions in expected_versions.items():
        from src.utils.sop_parser import _parse_semver

        expected_sorted = sorted(versions, key=_parse_semver)
        assert backend.list_versions(name) == expected_sorted


# Feature: sop-storage-abstraction, Property 5: Path validation rejects invalid paths
# Validates: Requirements 5.4
@settings(max_examples=100)
@given(
    path_str=st.one_of(
        # Empty strings
        st.just(""),
        # Strings containing null bytes
        st.text(min_size=1, max_size=100).map(lambda s: s + "\x00"),
        st.text(min_size=1, max_size=100).map(lambda s: "\x00" + s),
        st.text(min_size=0, max_size=50).flatmap(
            lambda prefix: st.text(min_size=0, max_size=50).map(
                lambda suffix: prefix + "\x00" + suffix
            )
        ),
    )
)
def test_path_validation_rejects_invalid_paths(path_str: str) -> None:
    """For any string that is empty or contains null bytes,
    _validate_storage_path should raise ValueError."""
    import pytest

    from src.utils.storage_local import _validate_storage_path

    with pytest.raises(ValueError):
        _validate_storage_path(path_str)


# --- Strategy: valid SOP markdown content ---

_VALID_SOP_TEMPLATE = """\
# SOP-{title}

**Document ID**: {doc_id}

**Version:** 1.0.0

## Overview

{overview}

### Step 1: Do something

{step_body}
"""


def _build_sop_content(doc_id: str, overview: str, step_body: str) -> str:
    """Build a minimal valid SOP markdown string."""
    title = doc_id.upper().replace("_", "-")
    return _VALID_SOP_TEMPLATE.format(
        title=title,
        doc_id=doc_id,
        overview=overview or "Overview text.",
        step_body=step_body or "Step body text.",
    )


# Strategy for SOP doc IDs: 3+ underscore-separated lowercase segments
sop_doc_ids = (
    st.lists(
        st.text(alphabet=string.ascii_lowercase, min_size=2, max_size=6),
        min_size=3,
        max_size=5,
    )
    .map(lambda parts: "_".join(parts))
)

non_empty_text = st.text(
    alphabet=st.characters(categories=("L", "N", "Z")),
    min_size=1,
    max_size=80,
)


# Feature: sop-storage-abstraction, Property 4: Ephemeral warning if and only if ephemeral backend
# Validates: Requirements 4.1, 4.2, 4.3, 4.4
@settings(max_examples=100)
@given(
    is_ephemeral=st.booleans(),
    doc_id=sop_doc_ids,
    overview=non_empty_text,
    step_body=non_empty_text,
    feedback_text=non_empty_text,
)
def test_ephemeral_warning_iff_ephemeral_backend(
    tmp_path_factory,
    is_ephemeral: bool,
    doc_id: str,
    overview: str,
    step_body: str,
    feedback_text: str,
) -> None:
    """For any SOP content published or feedback submitted, the response
    contains an ephemeral storage warning if and only if the underlying
    StorageBackend.is_ephemeral is True."""
    import src.server as server_module

    base_dir = tmp_path_factory.mktemp("sops")
    test_backend = LocalFilesystemBackend(base_dir=base_dir, is_ephemeral=is_ephemeral)

    original_backend = server_module.backend
    server_module.backend = test_backend
    try:
        content = _build_sop_content(doc_id, overview, step_body)

        # --- publish_sop ---
        publish_result = server_module.publish_sop(content)
        assert publish_result.get("success") is True, f"publish_sop failed: {publish_result}"

        if is_ephemeral:
            assert "warning" in publish_result, "Expected ephemeral warning in publish result"
        else:
            assert "warning" not in publish_result, "Unexpected ephemeral warning in publish result"

        # --- submit_sop_feedback ---
        feedback_result = server_module.submit_sop_feedback(doc_id, feedback_text)
        assert feedback_result.get("success") is True, f"submit_sop_feedback failed: {feedback_result}"

        if is_ephemeral:
            assert "warning" in feedback_result, "Expected ephemeral warning in feedback result"
        else:
            assert "warning" not in feedback_result, "Unexpected ephemeral warning in feedback result"
    finally:
        server_module.backend = original_backend

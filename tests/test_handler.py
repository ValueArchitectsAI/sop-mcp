"""Unit tests for the SOP MCP Server tools.

Tests the server.py implementation including:
- Single run_sop tool with sop_name parameter
- SOP tool functionality (start, continue, and version selection)
"""

from __future__ import annotations

import json
import shutil
import string

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.server import backend, mcp
from src.utils.storage_local import BUNDLED_SOPS_DIR

SOP_NAME = "sop_creation_guide"


async def call_tool(name: str, arguments: dict | None = None) -> dict:
    """Helper: call a FastMCP tool and return the structured result dict."""
    result = await mcp.call_tool(name, arguments or {})
    return json.loads(result.content[0].text)


async def call_run_sop(sop_name: str = SOP_NAME, **kwargs) -> dict:
    """Helper: call run_sop to start an SOP."""
    args = {"sop_name": sop_name, **kwargs}
    return await call_tool("run_sop", args)


async def call_run_sop_strict(sop_name: str = SOP_NAME, **kwargs) -> dict:
    """Helper: call run_sop_strict to continue an SOP."""
    args = {"sop_name": sop_name, **kwargs}
    return await call_tool("run_sop_strict", args)


# Alias used throughout the test suite
call_run_sop_with_context = call_run_sop_strict


def get_sop_info(sop_name: str = SOP_NAME) -> dict:
    """Helper: get SOP metadata directly from the backend."""
    from src.utils import SOP

    content = backend.read_sop(sop_name)
    sop = SOP.from_content(content)
    return {
        "sop_name": sop.name,
        "title": sop.title,
        "version": sop.version,
        "overview": sop.overview,
        "total_steps": sop.total_steps,
        "steps": [step.splitlines()[0].replace("### ", "") for step in sop.steps],
    }


class TestToolRegistration:
    """Tests for tool registration."""

    @pytest.mark.asyncio
    async def test_run_sop_tool_registered(self):
        tools = await mcp.list_tools()
        names = [t.name for t in tools]
        assert "run_sop" in names
        assert "run_sop_strict" in names

    @pytest.mark.asyncio
    async def test_no_per_sop_run_tools(self):
        tools = await mcp.list_tools()
        names = [t.name for t in tools]
        per_sop = [n for n in names if n.startswith("run_") and n not in ("run_sop", "run_sop_strict")]
        assert per_sop == [], f"Expected no per-SOP run_ tools, found: {per_sop}"

    @pytest.mark.asyncio
    async def test_core_tools_registered(self):
        tools = await mcp.list_tools()
        names = [t.name for t in tools]
        assert "publish_sop" in names
        assert "submit_sop_feedback" in names


class TestSopToolStart:
    """Tests for starting an SOP."""

    @pytest.mark.asyncio
    async def test_returns_dict(self):
        result = await call_run_sop()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_returns_sop_name(self):
        result = await call_run_sop()
        assert result["sop_name"] == SOP_NAME

    @pytest.mark.asyncio
    async def test_returns_sop_version(self):
        result = await call_run_sop()
        assert "sop_version" in result
        assert isinstance(result["sop_version"], str)

    @pytest.mark.asyncio
    async def test_returns_instruction(self):
        result = await call_run_sop()
        assert "instruction" in result
        assert len(result["instruction"]) > 0


class TestSopToolContinue:
    """Tests for continuing an SOP."""

    @pytest.mark.asyncio
    async def test_returns_instruction_for_next_step(self):
        result = await call_run_sop_with_context(current_step=1, step_output="step 1 output", previous_outputs={})
        assert "Step 2" in result["instruction"]

    @pytest.mark.asyncio
    async def test_returns_completion_signal_on_last_step(self):
        info = get_sop_info()
        total = info["total_steps"]
        result = await call_run_sop_with_context(current_step=total, step_output="final", previous_outputs={})
        assert "instruction" in result
        assert "complete" in result["instruction"].lower()

    @pytest.mark.asyncio
    async def test_error_for_step_beyond_total(self):
        info = get_sop_info()
        total = info["total_steps"]
        with pytest.raises(Exception):
            await call_run_sop_with_context(current_step=total + 1, step_output="x", previous_outputs={})

    @pytest.mark.asyncio
    async def test_error_for_invalid_step_negative(self):
        with pytest.raises(Exception):
            await call_run_sop_with_context(current_step=-1, step_output="x", previous_outputs={})


class TestSopToolVersionParameter:
    """Tests for the optional version parameter."""

    @pytest.mark.asyncio
    async def test_defaults_to_latest_version(self):
        result = await call_run_sop()
        assert "sop_version" in result
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_explicit_version_returns_matching_sop(self):
        result = await call_run_sop(version="1.0")
        assert result["sop_version"] == "1.0"

    @pytest.mark.asyncio
    async def test_invalid_version_returns_error(self):
        with pytest.raises(Exception):
            await call_run_sop(version="99.99.99")

    @pytest.mark.asyncio
    async def test_version_with_step_navigation(self):
        result = await call_run_sop_with_context(
            version="1.0", current_step=1, step_output="v1 output", previous_outputs={}
        )
        assert result["sop_version"] == "1.0"
        assert "Step 2" in result["instruction"]

    @pytest.mark.asyncio
    async def test_unknown_sop_returns_error(self):
        with pytest.raises(Exception):
            await call_run_sop(sop_name="nonexistent_sop")


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis)
# ---------------------------------------------------------------------------

# --- Strategies ---

_id_segment = st.text(
    alphabet=string.ascii_lowercase + string.digits,
    min_size=1,
    max_size=8,
).filter(lambda s: s[0].isalpha())

sop_doc_id = st.tuples(
    _id_segment,
    _id_segment,
    _id_segment,
    st.lists(_id_segment, min_size=0, max_size=2),
).map(lambda t: "_".join([t[0], t[1], t[2]] + t[3]))

_tool_name = st.text(
    alphabet=string.ascii_lowercase + "_",
    min_size=2,
    max_size=15,
).filter(lambda s: s[0].isalpha() and not s.endswith("_"))

# Available SOP names for property tests
_available_sops = st.sampled_from(backend.list_sops())


def _build_sop_with_tool_refs_no_prereqs(doc_id: str, tool_name: str) -> str:
    """Build valid SOP content with a tool reference but NO Required MCP Servers field."""
    return (
        "# Test SOP With Tool Refs\n\n"
        "## Document Information\n"
        f"- **Document ID**: {doc_id}\n\n"
        "## Overview\n\nThis SOP tests tool reference detection.\n\n"
        f"### Step 1: Use the tool\n\n"
        f"Use the `{tool_name}` tool to perform the action.\n"
    )


@settings(max_examples=100, deadline=None)
@given(doc_id=sop_doc_id, tool_name=_tool_name)
@pytest.mark.asyncio
async def test_property_missing_mcp_server_prerequisites_produces_warning(
    doc_id: str,
    tool_name: str,
) -> None:
    """Publishing SOP with tool refs but no Required MCP Servers should warn."""
    content = _build_sop_with_tool_refs_no_prereqs(doc_id, tool_name)
    sop_dir = BUNDLED_SOPS_DIR / doc_id
    try:
        result = await call_tool("publish_sop", {"content": content})
        assert result.get("success") is True
        warning = result.get("warning", "")
        assert "Required MCP Servers" in warning
    finally:
        if sop_dir.exists():
            shutil.rmtree(sop_dir)


@settings(max_examples=100, deadline=None)
@given(data=st.data(), sop_name=_available_sops)
@pytest.mark.asyncio
async def test_property_completion_returns_complete_message(
    data: st.DataObject,
    sop_name: str,
) -> None:
    """Completion SHALL return completion message."""
    info = get_sop_info(sop_name)
    total_steps = info["total_steps"]
    step_output_value = data.draw(st.text(min_size=0, max_size=50))

    result = await call_run_sop_with_context(
        sop_name, current_step=total_steps, step_output=step_output_value, previous_outputs={}
    )
    assert "instruction" in result
    assert "complete" in result["instruction"].lower()


@settings(max_examples=100, deadline=None)
@given(sop_name=_available_sops)
@pytest.mark.asyncio
async def test_property_step_output_is_required_in_context_schema(sop_name: str) -> None:
    """run_sop_strict schema SHALL include required step_output of type string."""
    tools = await mcp.list_tools()
    tool = next(t for t in tools if t.name == "run_sop_strict")
    schema = tool.parameters
    properties = schema.get("properties", {})

    assert "step_output" in properties
    step_output_prop = properties["step_output"]
    allowed_types = set()
    if "type" in step_output_prop:
        allowed_types.add(step_output_prop["type"])
    for variant in step_output_prop.get("anyOf", []):
        if "type" in variant:
            allowed_types.add(variant["type"])
    assert "string" in allowed_types

    required = schema.get("required", [])
    assert "step_output" in required


@settings(max_examples=100, deadline=None)
@given(sop_name=_available_sops)
@pytest.mark.asyncio
async def test_property_previous_outputs_is_required_in_context_schema(sop_name: str) -> None:
    """run_sop_strict schema SHALL include required previous_outputs of type object."""
    tools = await mcp.list_tools()
    tool = next(t for t in tools if t.name == "run_sop_strict")
    schema = tool.parameters
    properties = schema.get("properties", {})

    assert "previous_outputs" in properties
    prev_prop = properties["previous_outputs"]
    allowed_types = set()
    if "type" in prev_prop:
        allowed_types.add(prev_prop["type"])
    for variant in prev_prop.get("anyOf", []):
        if "type" in variant:
            allowed_types.add(variant["type"])
    assert "object" in allowed_types

    required = schema.get("required", [])
    assert "previous_outputs" in required


@settings(max_examples=100, deadline=None)
@given(data=st.data(), sop_name=_available_sops)
@pytest.mark.asyncio
async def test_property_non_final_steps_return_step_content(
    data: st.DataObject,
    sop_name: str,
) -> None:
    """Non-final steps SHALL return instruction with step number and SOP content."""
    info = get_sop_info(sop_name)
    total_steps = info["total_steps"]
    if total_steps <= 1:
        return

    step_k = data.draw(st.integers(min_value=1, max_value=total_steps - 1))
    if step_k == 1:
        result = await call_run_sop(sop_name)
    else:
        result = await call_run_sop_with_context(
            sop_name, current_step=step_k - 1, step_output="output", previous_outputs={}
        )

    assert "instruction" in result
    assert f"Step {step_k}" in result["instruction"]


@settings(max_examples=100, deadline=None)
@given(data=st.data(), sop_name=_available_sops)
@pytest.mark.asyncio
async def test_property_first_step_contains_sop_overview_header(
    data: st.DataObject,
    sop_name: str,
) -> None:
    """First step SHALL contain SOP title, total steps, and overview."""
    result = await call_run_sop(sop_name)
    instruction = result["instruction"]
    info = get_sop_info(sop_name)

    assert "You are executing:" in instruction
    assert info["title"] in instruction
    assert f"Total steps: {info['total_steps']}" in instruction
    assert info["overview"] in instruction


# --- previous_outputs property tests ---

previous_outputs_strategy = st.dictionaries(
    keys=st.integers(min_value=1, max_value=20).map(str),
    values=st.text(min_size=1, max_size=100),
    min_size=0,
    max_size=10,
)
step_output_strategy = st.text(min_size=1, max_size=200)


@settings(max_examples=100, deadline=None)
@given(
    data=st.data(),
    sop_name=_available_sops,
    previous_outputs=previous_outputs_strategy,
    step_output=step_output_strategy,
)
@pytest.mark.asyncio
async def test_property_merge_step_output_into_previous_outputs(
    data: st.DataObject,
    sop_name: str,
    previous_outputs: dict[str, str],
    step_output: str,
) -> None:
    """Response previous_outputs SHALL contain merged step_output."""
    info = get_sop_info(sop_name)
    total_steps = info["total_steps"]
    if total_steps <= 1:
        return

    step_k = data.draw(st.integers(min_value=1, max_value=total_steps - 1))
    result = await call_run_sop_with_context(
        sop_name, current_step=step_k, step_output=step_output, previous_outputs=previous_outputs
    )
    resp_prev = result.get("previous_outputs", {})

    assert str(step_k) in resp_prev
    assert resp_prev[str(step_k)] == step_output
    for key, value in previous_outputs.items():
        assert key in resp_prev
        if key != str(step_k):
            assert resp_prev[key] == value


@settings(max_examples=100, deadline=None)
@given(
    data=st.data(),
    sop_name=_available_sops,
    previous_outputs=previous_outputs_strategy,
    step_output=step_output_strategy,
)
@pytest.mark.asyncio
async def test_property_existing_entries_unchanged_after_merge(
    data: st.DataObject,
    sop_name: str,
    previous_outputs: dict[str, str],
    step_output: str,
) -> None:
    """Entries in previous_outputs with keys != str(K) SHALL be unchanged."""
    info = get_sop_info(sop_name)
    total_steps = info["total_steps"]
    if total_steps <= 1:
        return

    step_k = data.draw(st.integers(min_value=1, max_value=total_steps - 1))
    result = await call_run_sop_with_context(
        sop_name, current_step=step_k, step_output=step_output, previous_outputs=previous_outputs
    )
    resp_prev = result.get("previous_outputs", {})

    for key, value in previous_outputs.items():
        if key != str(step_k):
            assert key in resp_prev
            assert resp_prev[key] == value


@settings(max_examples=100, deadline=None)
@given(
    data=st.data(),
    sop_name=_available_sops,
    previous_outputs=previous_outputs_strategy,
    step_output=step_output_strategy,
)
@pytest.mark.asyncio
async def test_property_completion_includes_accumulated_outputs(
    data: st.DataObject,
    sop_name: str,
    previous_outputs: dict[str, str],
    step_output: str,
) -> None:
    """Completion response SHALL include accumulated previous_outputs."""
    info = get_sop_info(sop_name)
    total_steps = info["total_steps"]

    result = await call_run_sop_with_context(
        sop_name,
        current_step=total_steps,
        step_output=step_output,
        previous_outputs=previous_outputs,
    )
    assert "instruction" in result
    assert "complete" in result["instruction"].lower()

    resp_prev = result.get("previous_outputs", {})
    expected = dict(previous_outputs)
    expected[str(total_steps)] = step_output
    assert resp_prev == expected

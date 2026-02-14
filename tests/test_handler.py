"""Unit tests for the SOP MCP Server tools.

Tests the server.py implementation including:
- Dynamic SOP tool registration (tool names derived from folder name)
- SOP tool functionality (start, continue, and version selection)
"""

from __future__ import annotations

import json
import shutil
import string

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.server import mcp
from src.utils.storage_local import BUNDLED_SOPS_DIR


async def call_tool(name: str, arguments: dict | None = None) -> dict:
    """Helper: call a FastMCP tool and return the structured result dict."""
    result = await mcp.call_tool(name, arguments or {})
    if isinstance(result, tuple):
        return result[1]
    return json.loads(result[0].text)


class TestDynamicToolRegistration:
    """Tests for dynamic SOP tool registration."""

    @pytest.mark.asyncio
    async def test_sop_tools_registered_with_descriptive_names(self):
        tools = await mcp.list_tools()
        tool_names = [t.name for t in tools]
        assert "run_sop_creation_guide" in tool_names

    @pytest.mark.asyncio
    async def test_no_old_style_tool_names(self):
        tools = await mcp.list_tools()
        tool_names = [t.name for t in tools]
        assert "run_sop_create_001" not in tool_names
        assert "run_sop_create" not in tool_names
        # No hyphenated folder names
        assert "run_authoring-new-sop" not in tool_names

    @pytest.mark.asyncio
    async def test_tool_names_have_at_least_two_words(self):
        tools = await mcp.list_tools()
        for t in tools:
            if t.name.startswith("run_"):
                suffix = t.name[4:]
                assert "_" in suffix, f"Tool '{t.name}' suffix '{suffix}' has fewer than 2 words"


class TestSopToolStart:
    """Tests for starting an SOP (no current_step provided)."""

    @pytest.mark.asyncio
    async def test_returns_dict(self):
        result = await call_tool("run_sop_creation_guide")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_returns_sop_name(self):
        result = await call_tool("run_sop_creation_guide")
        assert result["sop_name"] == "sop_creation_guide"

    @pytest.mark.asyncio
    async def test_returns_sop_version(self):
        result = await call_tool("run_sop_creation_guide")
        assert "sop_version" in result
        assert isinstance(result["sop_version"], str)

    @pytest.mark.asyncio
    async def test_returns_title(self):
        result = await call_tool("run_sop_creation_guide")
        assert "title" in result
        assert isinstance(result["title"], str)

    @pytest.mark.asyncio
    async def test_returns_overview(self):
        result = await call_tool("run_sop_creation_guide")
        assert "overview" in result
        assert isinstance(result["overview"], str)

    @pytest.mark.asyncio
    async def test_returns_current_step_as_one(self):
        result = await call_tool("run_sop_creation_guide")
        assert result["current_step"] == 1

    @pytest.mark.asyncio
    async def test_returns_total_steps(self):
        result = await call_tool("run_sop_creation_guide")
        assert "total_steps" in result
        assert isinstance(result["total_steps"], int)
        assert result["total_steps"] > 0

    @pytest.mark.asyncio
    async def test_returns_step_content(self):
        result = await call_tool("run_sop_creation_guide")
        assert "step_content" in result
        assert isinstance(result["step_content"], str)


class TestSopToolContinue:
    """Tests for continuing an SOP (current_step provided)."""

    @pytest.mark.asyncio
    async def test_returns_next_step_number(self):
        result = await call_tool("run_sop_creation_guide", {"current_step": 1})
        assert result["current_step"] == 2

    @pytest.mark.asyncio
    async def test_returns_step_content(self):
        result = await call_tool("run_sop_creation_guide", {"current_step": 1})
        assert "step_content" in result
        assert isinstance(result["step_content"], str)

    @pytest.mark.asyncio
    async def test_returns_is_complete_false_for_mid_steps(self):
        result = await call_tool("run_sop_creation_guide", {"current_step": 1})
        assert result["is_complete"] is False

    @pytest.mark.asyncio
    async def test_returns_is_complete_true_for_last_step(self):
        start = await call_tool("run_sop_creation_guide")
        total = start["total_steps"]
        result = await call_tool("run_sop_creation_guide", {"current_step": total})
        assert result["is_complete"] is True

    @pytest.mark.asyncio
    async def test_returns_completion_message_on_last_step(self):
        start = await call_tool("run_sop_creation_guide")
        total = start["total_steps"]
        result = await call_tool("run_sop_creation_guide", {"current_step": total})
        assert "message" in result
        assert "completed" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_error_for_step_beyond_total(self):
        start = await call_tool("run_sop_creation_guide")
        total = start["total_steps"]
        result = await call_tool("run_sop_creation_guide", {"current_step": total + 1})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_error_for_invalid_step_zero(self):
        result = await call_tool("run_sop_creation_guide", {"current_step": 0})
        assert "error" in result


class TestSopToolVersionParameter:
    """Tests for the optional version parameter."""

    @pytest.mark.asyncio
    async def test_defaults_to_latest_version(self):
        result = await call_tool("run_sop_creation_guide")
        assert "sop_version" in result
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_explicit_version_returns_matching_sop(self):
        result = await call_tool("run_sop_creation_guide", {"version": "1.0"})
        assert result["sop_version"] == "1.0"

    @pytest.mark.asyncio
    async def test_invalid_version_returns_error(self):
        result = await call_tool("run_sop_creation_guide", {"version": "99.99.99"})
        assert "error" in result
        assert "99.99.99" in result["error"]

    @pytest.mark.asyncio
    async def test_version_with_step_navigation(self):
        result = await call_tool("run_sop_creation_guide", {"version": "1.0", "current_step": 1})
        assert result["sop_version"] == "1.0"
        assert result["current_step"] == 2


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis)
# ---------------------------------------------------------------------------

# --- Strategies ---

# Segment for SOP Document IDs: lowercase alpha start, then lowercase alphanumeric
_id_segment = st.text(
    alphabet=string.ascii_lowercase + string.digits,
    min_size=1,
    max_size=8,
).filter(lambda s: s[0].isalpha())

# Document ID: at least 3 underscore-separated segments (matches [a-z][a-z0-9]*(?:_[a-z0-9]+){2,})
sop_doc_id = st.tuples(
    _id_segment,
    _id_segment,
    _id_segment,
    st.lists(_id_segment, min_size=0, max_size=2),
).map(lambda t: "_".join([t[0], t[1], t[2]] + t[3]))

# Random tool names for step content
_tool_name = st.text(
    alphabet=string.ascii_lowercase + "_",
    min_size=2,
    max_size=15,
).filter(lambda s: s[0].isalpha() and not s.endswith("_"))


def _build_sop_with_tool_refs_no_prereqs(doc_id: str, tool_name: str) -> str:
    """Build valid SOP content with a tool reference in a step but NO Required MCP Servers field."""
    return (
        "# Test SOP With Tool Refs\n\n"
        "## Document Information\n"
        f"- **Document ID**: {doc_id}\n\n"
        "## Overview\n\nThis SOP tests tool reference detection.\n\n"
        f"### Step 1: Use the tool\n\n"
        f"Use the `{tool_name}` tool to perform the action.\n"
    )


# Feature: sop-prerequisites-mcp-servers, Property 2: Missing MCP Server Prerequisites Produces Warning
# Validates: Requirements 2.1, 2.3
@settings(max_examples=100, deadline=None)
@given(
    doc_id=sop_doc_id,
    tool_name=_tool_name,
)
@pytest.mark.asyncio
async def test_property_missing_mcp_server_prerequisites_produces_warning(
    doc_id: str,
    tool_name: str,
) -> None:
    """For any valid SOP content that contains tool-referencing patterns in its
    steps but does not contain a **Required MCP Servers** field, publishing via
    publish_sop should return success: True with a warning mentioning
    'Required MCP Servers'.

    **Validates: Requirements 2.1, 2.3**
    """
    content = _build_sop_with_tool_refs_no_prereqs(doc_id, tool_name)
    sop_dir = BUNDLED_SOPS_DIR / doc_id
    try:
        result = await call_tool("publish_sop", {"content": content})
        # SHOULD-level: publish succeeds (Req 2.3)
        assert result.get("success") is True, f"Expected success=True, got {result}"
        # Warning about missing MCP server prerequisites is present (Req 2.1)
        warning = result.get("warning", "")
        assert "Required MCP Servers" in warning, (
            f"Expected warning mentioning 'Required MCP Servers', got: {warning!r}"
        )
    finally:
        # Clean up the created SOP files
        if sop_dir.exists():
            shutil.rmtree(sop_dir)


# Feature: sop-mcp-llm-output-quality, Property 6: Completion signal contains compilation instructions
# Validates: Requirements 3.1, 3.2, 3.3, 3.4
@settings(max_examples=100, deadline=None)
@given(data=st.data())
@pytest.mark.asyncio
async def test_property_completion_signal_contains_compilation_instructions(
    data: st.DataObject,
) -> None:
    """For any SOP, when all steps are complete, the returned message SHALL
    instruct the LLM to review step_output submissions, compile a comprehensive
    document, include all concrete values, and not summarize.

    **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
    """
    # Discover all registered SOP tools
    tools = await mcp.list_tools()
    sop_tools = [t.name for t in tools if t.name.startswith("run_sop_")]
    assert len(sop_tools) > 0, "No SOP tools registered"

    tool_name = data.draw(st.sampled_from(sop_tools))

    # Get total steps for this SOP
    start_result = await call_tool(tool_name)
    assert "error" not in start_result, f"Unexpected error starting {tool_name}: {start_result}"
    total_steps = start_result["total_steps"]

    # Call with current_step=total_steps to trigger completion signal
    step_output_value = data.draw(st.text(min_size=0, max_size=50))
    result = await call_tool(tool_name, {"current_step": total_steps, "step_output": step_output_value})

    assert "error" not in result, f"Unexpected error: {result}"
    assert result["is_complete"] is True

    instruction = result["instruction"]

    # Req 3.1: instructs LLM to produce a final comprehensive document
    assert "final" in instruction.lower() and "document" in instruction.lower(), (
        f"Completion signal should instruct producing a final document, got: {instruction!r}"
    )
    # Req 3.2: instructs LLM to review step_output
    assert "step_output" in instruction, f"Completion signal should mention reviewing step_output, got: {instruction!r}"
    # Req 3.3: instructs to include all concrete values
    assert "concrete" in instruction.lower() or "specific" in instruction.lower(), (
        f"Completion signal should mention concrete/specific values, got: {instruction!r}"
    )
    # Req 3.4: instructs not to summarize
    assert "not summarize" in instruction.lower() or "do not summarize" in instruction.lower(), (
        f"Completion signal should instruct not to summarize, got: {instruction!r}"
    )


# Feature: sop-mcp-llm-output-quality, Property 1: step_output is an optional schema parameter
# Validates: Requirements 1.1, 1.3
@settings(max_examples=100, deadline=None)
@given(data=st.data())
@pytest.mark.asyncio
async def test_property_step_output_is_optional_schema_parameter(
    data: st.DataObject,
) -> None:
    """For any registered SOP tool (run_sop_*), the tool's input schema SHALL
    include a step_output property of type string, and step_output SHALL NOT
    appear in the schema's required array.

    **Validates: Requirements 1.1, 1.3**
    """
    # Discover all registered SOP tools
    tools = await mcp.list_tools()
    sop_tools = [t for t in tools if t.name.startswith("run_sop_")]
    assert len(sop_tools) > 0, "No SOP tools registered"

    tool = data.draw(st.sampled_from(sop_tools))
    schema = tool.inputSchema

    # Req 1.1: schema includes a step_output property of type string
    properties = schema.get("properties", {})
    assert "step_output" in properties, (
        f"Tool '{tool.name}' schema is missing 'step_output' property. Properties: {list(properties.keys())}"
    )

    step_output_prop = properties["step_output"]
    # FastMCP represents `str | None` as anyOf: [{type: string}, {type: null}]
    allowed_types = set()
    if "type" in step_output_prop:
        allowed_types.add(step_output_prop["type"])
    for variant in step_output_prop.get("anyOf", []):
        if "type" in variant:
            allowed_types.add(variant["type"])
    assert "string" in allowed_types, (
        f"Tool '{tool.name}' step_output must accept type string, got types: {allowed_types}"
    )

    # Req 1.3: step_output is NOT in the required array
    required = schema.get("required", [])
    assert "step_output" not in required, f"Tool '{tool.name}' schema has 'step_output' in required array: {required}"


# Feature: sop-mcp-llm-output-quality, Property 3:
# Non-final steps contain execution instruction with correct step number
# Validates: Requirements 2.1, 2.3, 2.4
@settings(max_examples=100, deadline=None)
@given(data=st.data())
@pytest.mark.asyncio
async def test_property_non_final_steps_contain_execution_instruction_with_correct_step_number(
    data: st.DataObject,
) -> None:
    """For any SOP with N steps (N > 1) and any step K where 1 ≤ K < N,
    the returned instruction SHALL contain an execution instruction block
    that references completed_step_id={K} and mentions step_output.

    **Validates: Requirements 2.1, 2.3, 2.4**
    """
    # Discover all registered SOP tools
    tools = await mcp.list_tools()
    sop_tools = [t.name for t in tools if t.name.startswith("run_sop_")]
    assert len(sop_tools) > 0, "No SOP tools registered"

    tool_name = data.draw(st.sampled_from(sop_tools))

    # Get total steps for this SOP
    start_result = await call_tool(tool_name)
    assert "error" not in start_result, f"Unexpected error starting {tool_name}: {start_result}"
    total_steps = start_result["total_steps"]

    # Only test SOPs with more than 1 step (need at least one non-final step)
    if total_steps <= 1:
        return

    # Pick a random non-final step K where 1 ≤ K < N
    step_k = data.draw(st.integers(min_value=1, max_value=total_steps - 1))

    # Request step K: step 1 comes from current_step=None, step K>1 from current_step=K-1
    if step_k == 1:
        result = await call_tool(tool_name)
    else:
        result = await call_tool(tool_name, {"current_step": step_k - 1})

    assert "error" not in result, f"Unexpected error for step {step_k}: {result}"
    assert result["current_step"] == step_k

    instruction = result["instruction"]

    # Req 2.1: non-final step instruction contains an execution instruction block
    assert "EXECUTION INSTRUCTION" in instruction, (
        f"Step {step_k}/{total_steps} should contain an EXECUTION INSTRUCTION block, got: {instruction!r}"
    )

    # Req 2.3 & 2.4: execution instruction references completed_step_id={K}
    expected_ref = f"completed_step_id={step_k}"
    assert expected_ref in instruction, (
        f"Step {step_k}/{total_steps} should reference '{expected_ref}', got: {instruction!r}"
    )

    # Req 2.3: execution instruction mentions step_output
    # Check only the execution instruction portion (after the --- separator)
    exec_parts = instruction.split("---")
    exec_instruction = exec_parts[-1] if len(exec_parts) > 1 else instruction
    assert "step_output" in exec_instruction, (
        f"Execution instruction for step {step_k}/{total_steps} should mention 'step_output', got: {exec_instruction!r}"
    )


# Feature: sop-mcp-llm-output-quality, Property 4: Execution instruction is SOP-agnostic
# Validates: Requirements 2.5
@settings(max_examples=100, deadline=None)
@given(data=st.data())
@pytest.mark.asyncio
async def test_property_execution_instruction_is_sop_agnostic(
    data: st.DataObject,
) -> None:
    """For any two distinct SOPs and any valid non-final step, the execution
    instruction portion (after the --- separator) SHALL follow the same template
    structure, differing only in the step number.

    When only one SOP is registered, we verify the property across two distinct
    non-final steps of that SOP instead.

    **Validates: Requirements 2.5**
    """
    import re

    tools = await mcp.list_tools()
    sop_tools = [t.name for t in tools if t.name.startswith("run_sop_")]
    assert len(sop_tools) > 0, "No SOP tools registered"

    def extract_exec_instruction(instruction: str) -> str | None:
        """Extract the execution instruction block after the last '---' separator."""
        parts = instruction.split("---")
        if len(parts) < 2:
            return None
        return parts[-1].strip()

    def normalize_step_number(exec_instr: str) -> str:
        """Replace completed_step_id=N with a placeholder so templates can be compared."""
        return re.sub(r"completed_step_id=\d+", "completed_step_id={N}", exec_instr)

    # Collect two (tool_name, step_k) pairs that yield non-final steps
    # Try to pick from two distinct SOPs if possible; otherwise two distinct steps
    candidates: list[tuple[str, int]] = []

    tool_name_1 = data.draw(st.sampled_from(sop_tools))
    start_1 = await call_tool(tool_name_1)
    assert "error" not in start_1, f"Unexpected error starting {tool_name_1}: {start_1}"
    total_1 = start_1["total_steps"]

    if total_1 <= 1:
        # Single-step SOP has no non-final steps; skip
        return

    step_k1 = data.draw(st.integers(min_value=1, max_value=total_1 - 1))
    candidates.append((tool_name_1, step_k1))

    # Try to pick a second distinct SOP; fall back to a different step of the same SOP
    other_sop_tools = [t for t in sop_tools if t != tool_name_1]
    if other_sop_tools:
        tool_name_2 = data.draw(st.sampled_from(other_sop_tools))
        start_2 = await call_tool(tool_name_2)
        assert "error" not in start_2, f"Unexpected error starting {tool_name_2}: {start_2}"
        total_2 = start_2["total_steps"]
        if total_2 > 1:
            step_k2 = data.draw(st.integers(min_value=1, max_value=total_2 - 1))
            candidates.append((tool_name_2, step_k2))

    # If we still need a second candidate, pick a different step from the same SOP
    if len(candidates) < 2:
        remaining_steps = [s for s in range(1, total_1) if s != step_k1]
        if not remaining_steps:
            # Only one non-final step exists; can't compare two distinct steps
            return
        step_k2 = data.draw(st.sampled_from(remaining_steps))
        candidates.append((tool_name_1, step_k2))

    # Fetch execution instructions for both candidates
    normalized_templates: list[str] = []
    for tool_name, step_k in candidates:
        if step_k == 1:
            result = await call_tool(tool_name)
        else:
            result = await call_tool(tool_name, {"current_step": step_k - 1})

        assert "error" not in result, f"Unexpected error for {tool_name} step {step_k}: {result}"
        instruction = result["instruction"]

        exec_instr = extract_exec_instruction(instruction)
        assert exec_instr is not None, (
            f"No execution instruction found (no '---' separator) for {tool_name} step {step_k}"
        )
        normalized_templates.append(normalize_step_number(exec_instr))

    # The normalized templates must be identical — same structure, only step number differs
    assert normalized_templates[0] == normalized_templates[1], (
        f"Execution instruction templates differ between "
        f"{candidates[0]} and {candidates[1]}:\n"
        f"  Template 1: {normalized_templates[0]!r}\n"
        f"  Template 2: {normalized_templates[1]!r}"
    )


# Feature: sop-mcp-llm-output-quality, Property 5: Final step instruction indicates last step
# Validates: Requirements 2.6
@settings(max_examples=100, deadline=None)
@given(data=st.data())
@pytest.mark.asyncio
async def test_property_final_step_instruction_indicates_last_step(
    data: st.DataObject,
) -> None:
    """For any SOP, the instruction returned for the final step SHALL contain
    text indicating this is the last step, distinct from the instruction for
    non-final steps.

    **Validates: Requirements 2.6**
    """
    # Discover all registered SOP tools
    tools = await mcp.list_tools()
    sop_tools = [t.name for t in tools if t.name.startswith("run_sop_")]
    assert len(sop_tools) > 0, "No SOP tools registered"

    tool_name = data.draw(st.sampled_from(sop_tools))

    # Get total steps for this SOP
    start_result = await call_tool(tool_name)
    assert "error" not in start_result, f"Unexpected error starting {tool_name}: {start_result}"
    total_steps = start_result["total_steps"]

    # Request the final step: current_step = total_steps - 1 advances to the last step
    if total_steps == 1:
        # Single-step SOP: the first (and only) step is the final step
        final_result = start_result
    else:
        final_result = await call_tool(tool_name, {"current_step": total_steps - 1})

    assert "error" not in final_result, f"Unexpected error: {final_result}"
    assert final_result["current_step"] == total_steps

    final_instruction = final_result["instruction"]

    # The final step instruction must indicate this is the last step
    assert "last step" in final_instruction.lower(), (
        f"Final step instruction for {tool_name} should indicate this is the last step, got: {final_instruction!r}"
    )

    # The final step must still contain an execution instruction block
    assert "EXECUTION INSTRUCTION" in final_instruction, (
        f"Final step instruction for {tool_name} should contain an EXECUTION INSTRUCTION block, "
        f"got: {final_instruction!r}"
    )

    # For multi-step SOPs, verify the "last step" indicator is distinct from non-final steps
    if total_steps > 1:
        # Get a non-final step for comparison
        non_final_result = start_result  # step 1 is always non-final in multi-step SOPs
        non_final_instruction = non_final_result["instruction"]

        # Extract execution instruction portions (after the last --- separator)
        def extract_exec_block(instr: str) -> str:
            parts = instr.split("---")
            return parts[-1].strip() if len(parts) >= 2 else ""

        final_exec = extract_exec_block(final_instruction)
        non_final_exec = extract_exec_block(non_final_instruction)

        # The final exec instruction should mention "last step" but non-final should not
        assert "last step" in final_exec.lower(), (
            f"Final step execution instruction should mention 'last step', got: {final_exec!r}"
        )
        assert "last step" not in non_final_exec.lower(), (
            f"Non-final step execution instruction should NOT mention 'last step', got: {non_final_exec!r}"
        )


# Feature: sop-mcp-llm-output-quality, Property 7: First step contains SOP overview header
# Validates: Requirements 4.1, 4.2, 4.3, 4.4
@settings(max_examples=100, deadline=None)
@given(data=st.data())
@pytest.mark.asyncio
async def test_property_first_step_contains_sop_overview_header(
    data: st.DataObject,
) -> None:
    """For any SOP, the instruction returned for the first step (current_step
    omitted) SHALL contain the SOP title, the total number of steps, and the
    SOP overview text.

    **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
    """
    # Discover all registered SOP tools
    tools = await mcp.list_tools()
    sop_tools = [t.name for t in tools if t.name.startswith("run_sop_")]
    assert len(sop_tools) > 0, "No SOP tools registered"

    tool_name = data.draw(st.sampled_from(sop_tools))

    # Request the first step (current_step omitted)
    result = await call_tool(tool_name)
    assert "error" not in result, f"Unexpected error starting {tool_name}: {result}"

    instruction = result["instruction"]
    title = result["title"]
    total_steps = result["total_steps"]
    overview = result["overview"]

    # Req 4.1: first step includes SOP overview header before step content
    assert "You are executing:" in instruction, (
        f"First step instruction for {tool_name} should contain 'You are executing:' header, got: {instruction!r}"
    )

    # Req 4.2: overview header contains the SOP title
    assert title in instruction, (
        f"First step instruction for {tool_name} should contain the SOP title '{title}', got: {instruction!r}"
    )

    # Req 4.3: overview header contains the total number of steps
    assert f"Total steps: {total_steps}" in instruction, (
        f"First step instruction for {tool_name} should contain 'Total steps: {total_steps}', got: {instruction!r}"
    )

    # Req 4.4: overview header contains the SOP overview text
    assert overview in instruction, (
        f"First step instruction for {tool_name} should contain the overview text, got: {instruction!r}"
    )

    # Verify the overview header appears before the step execution content
    header_pos = instruction.index("You are executing:")
    # The step execution content starts after the overview header's --- separator
    # Find the first --- separator (which ends the overview header)
    first_separator = instruction.index("---", header_pos)
    assert header_pos < first_separator, f"Overview header should appear before the --- separator in {tool_name}"

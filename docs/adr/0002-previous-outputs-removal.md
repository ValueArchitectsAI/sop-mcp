# ADR-0002: Remove previous_outputs from SOP-MCP Server

## Status

Accepted

## Date

2026-02-18

## Context

### What was previous_outputs?

When the SOP-MCP server delivered an SOP step by step, it maintained a stateful accumulation of all work the model had produced so far. This accumulation was called `previous_outputs` — a dictionary that mapped step numbers to the model's output for that step.

The flow worked like this:

1. Model completes Step 1, calls `run_sop` with `step_output="Registration: VALID, DE-123456789..."`
2. Server stores this in `previous_outputs: {"1": "Registration: VALID, DE-123456789..."}`
3. Server returns Step 2 instruction + the full `previous_outputs` dict
4. Model completes Step 2, calls `run_sop` with its new `step_output` AND passes back the `previous_outputs` dict it received
5. Server appends Step 2's output, now `previous_outputs` has both steps
6. This continues — by Step 57, `previous_outputs` contains all 56 prior step outputs

The design intent was to give the model context about what it has already done, enabling it to reference prior work (e.g., "use the risk level from Step 3 to determine the approver in Step 4"). The model received the full history at every step.

### The problem

Returning `previous_outputs` to the model degrades performance as task complexity increases. The accumulated context competes with the current step instruction for the model's attention and context window budget.

## Decision

Remove `previous_outputs` from the `run_sop` tool entirely. The server no longer accumulates, stores, or returns prior step outputs. The model receives only the current step instruction. The model's own conversation history (including its `step_output` submissions via tool calls) serves as the record of prior work.

## Evidence

Comparative testing across multiple models on tasks of varying complexity (6, 16, and 57 steps) showed consistent results:

- Models complete significantly more steps on complex tasks without the accumulated context (e.g., 23 → 76 steps on a 57-step SOP)
- Per-step output is richer without the growing context blob consuming token budget (+30-89% more content per step)
- Input token consumption grows quadratically with step count when previous_outputs is included, as each step adds to the payload and the full payload is sent every step
- Latency per step is lower without the accumulated context (1.5-3.5x faster)
- Final response quality improves on simple and moderate tasks

On simple tasks (6 steps), both variants perform similarly — the accumulated context is small enough to fit. The degradation is proportional to task complexity.

## Consequences

### Positive

- Models complete significantly more steps on complex tasks
- Per-step output is richer without context competition
- Lower latency and input token cost per step
- Simpler API surface — `run_sop` has fewer parameters
- Server is fully stateless — no accumulation logic needed

### Negative

- The model cannot explicitly reference prior step outputs when executing the current step (e.g., "use the risk level from Step 3"). If inter-step dependencies are critical, this could reduce correctness on dependent steps.

### Mitigations

- For SOPs with strong inter-step dependencies, the step instruction itself should include the necessary context (e.g., "Based on the risk level you determined, route to the appropriate approver"). The SOP author controls this, not the delivery mechanism.
- The model's conversation history still contains all prior `step_output` submissions via tool calls, so models with sufficient context windows can reference them naturally.
- A future optimization could selectively include only outputs from steps that the current step depends on, rather than all prior outputs.

# ADR-0001: Enforce step_output in SOP-MCP Step-by-Step Delivery

## Status

Accepted

## Date

2026-02-18

## Context

The SOP-MCP server delivers Standard Operating Procedures to LLMs step by step via tool calls. Without requiring the model to provide output for the completed step, models advance through steps without performing the work described in each step. They optimize for protocol completion (calling the tool to get the next instruction) rather than task execution (actually doing the work each step describes).

Three symptoms confirm this behavior: near-zero latency per step (just tool call overhead, no reasoning), minimal output tokens per step (just the tool call JSON, no content), and response content that echoes the SOP instruction back rather than executing it.

## Decision

We enforce `step_output` as a required parameter for step advancement. The server rejects advancement requests that do not include a non-empty `step_output` string. The parameter is conditionally required: omit when starting (`current_step=0`), required when continuing (`current_step>=1`).

## Consequences

### Positive

- Models produce verifiable work product at each step instead of empty outputs
- Per-step latency and token usage confirm genuine execution, not protocol speed-running
- Final response quality improves significantly
- Per-step outputs create an audit trail enabling step-level quality assessment

### Negative

- Models that cannot follow the tool-use protocol are not helped
- Enforcement adds latency per step as the model must generate content before advancing
- Higher token consumption per trial
- Enforcement guarantees non-empty output, not correct output

### Neutral

- The enforcement is server-side, requiring no changes to the model or client API
- Starting a new SOP run remains frictionless since `step_output` is only required when continuing

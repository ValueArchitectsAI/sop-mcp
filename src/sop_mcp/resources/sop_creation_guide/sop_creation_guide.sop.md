---
name: sop_creation_guide
description: Step-by-step guide for authoring Agent SOPs using the upstream strands-agents/agent-sop format, validated with sop-lint, and published via publish_sop.
version: 2
owner: value-architects
stage: preprod
---

# Standard Operating Procedure: Creating Standard Operating Procedures

## Overview

Step-by-step guide for authoring Agent SOPs. Follow the upstream [agent-sop format](https://github.com/strands-agents/agent-sop/blob/main/rules/agent-sop-format.md) and validate with the `sop-lint` CLI before publishing via `publish_sop`.

## Parameters

- **process_name** (required): Short descriptive name of the process the SOP describes. Used to derive the SOP's `name` frontmatter field.
- **process_owner** (required): Team or alias that owns the process. Populates the `owner` frontmatter field.

## Steps

### 1. Gather Process Information

Collect everything needed before writing. Identify the process, its owner, its target audience, and its scope boundaries. Collect existing documentation and interview subject-matter experts who actually perform the process.

**Constraints:**
- You MUST identify the process owner before writing
- You MUST collect any existing documentation that describes the process
- You SHOULD interview at least two people who perform the process
- You SHOULD define explicit scope boundaries (what's in, what's out)
- You MAY record the interview transcripts for future reference

**Expected Output:** A process summary covering: process name, owner, audience, frequency, scope boundaries (in-scope / out-of-scope), and key findings from interviews.

### 2. Write the SOP Document

Produce the complete SOP markdown file against the agent-sop format. The document opens with `# Title`, has `## Overview`, `## Parameters`, and `## Steps` sections, and uses `### N. Step Name` headings under `## Steps`. Each step has a description paragraph followed by a `**Constraints:**` bullet list using RFC 2119 keywords (MUST, MUST NOT, SHOULD, SHOULD NOT, MAY) and an `**Expected Output:**` marker.

**Constraints:**
- You MUST use `### N. Step Name` heading syntax (number-dot-space, no "Step" keyword)
- You MUST include `## Overview`, `## Parameters`, and `## Steps` sections
- You MUST give every step a description paragraph, a `**Constraints:**` block, and an `**Expected Output:**` marker because a step without any one of these is unusable
- You MUST use RFC 2119 keywords in every constraint bullet (MUST / MUST NOT / SHOULD / SHOULD NOT / MAY)
- You MUST provide context for negative constraints using `because …`, `since …`, or similar so readers understand why the restriction exists
- You MUST write each step as self-contained — the executor sees only one step at a time
- You SHOULD keep 3–7 constraints per step
- You SHOULD include `## Examples` and `## Troubleshooting` when they add value
- You MAY include per-step `**Example Input:**` / `**Example Output:**` blocks to document the step's contract

**Expected Output:** A complete SOP markdown file with frontmatter, `## Overview`, `## Parameters`, `## Steps`, and every step carrying a description, `**Constraints:**` block, and `**Expected Output:**` marker.

### 3. Lint the Draft

Run the `sop-lint` CLI against the draft and resolve every finding. The linter encodes the agent-sop format rules plus sop-mcp strict extras (required YAML frontmatter, snake_case naming, per-step `**Expected Output:**` markers, etc.). Errors block publishing; warnings are recommendations worth resolving.

**Constraints:**
- You MUST run `sop-lint path/to/your.sop.md` and resolve every error before proceeding
- You MUST NOT ignore SOP204 negative-constraint-context findings because missing context makes constraints harder to audit and justify
- You SHOULD resolve warnings as well — they indicate drift from conventions
- You MAY use `--ignore` flags for specific rules only when you have a documented reason

**Expected Output:** `sop-lint` exit code 0 against the draft, with the full run summary showing 0 errors and the agreed-upon number of warnings and info messages.

### 4. Review with Humans

Have at least one subject-matter expert review for technical accuracy and one end-user review for clarity. Conduct a dry run using only the SOP as guidance to check whether the executor can follow it standalone.

**Constraints:**
- You MUST have at least one SME review for technical accuracy
- You MUST have at least one end-user review for clarity
- You SHOULD conduct a dry run using only the SOP as guidance
- You SHOULD incorporate critical feedback before publishing

**Expected Output:** Documented reviewer approvals (SME + end user), a list of feedback items resolved, and a note on any dry-run issues discovered and fixed.

### 5. Publish

Publish the reviewed SOP via the `publish_sop` MCP tool. The server runs the same `sop-lint` engine at publish time; if the draft has any lint errors the call will be rejected.

**Constraints:**
- You MUST publish using the `publish_sop` MCP tool
- You MUST incorporate critical review feedback before publishing
- You SHOULD set a review cadence (quarterly for new processes, annually for stable ones)
- You MAY notify stakeholders via Slack or email after publishing

**Expected Output:** The published SOP's name, assigned version number, stage, and storage path returned by `publish_sop`.

### 6. Collect Feedback

Reflect on the authoring experience and submit feedback via `submit_sop_feedback`. Feedback accumulates in a JSONL log next to the SOP and informs future revisions.

**Constraints:**
- You SHOULD call `submit_sop_feedback` with specific observations
- You SHOULD include both what worked well and what needs improvement
- You MAY include links to downstream artefacts (e.g. wiki pages that reference the SOP)

**Expected Output:** Confirmation that `submit_sop_feedback` accepted the entry, with the SOP name and version the feedback was submitted against.

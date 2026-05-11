---
name: sop_creation_guide
description: Step-by-step guide for creating SOPs using RFC 2119 requirement levels.
  SOPs are delivered one step at a time to LLMs via MCP tool calls — each step MUST
  be self-contained and describe what concrete…
version: 1
owner: value-architects
stage: preprod
---

# Standard Operating Procedure: Creating Standard Operating Procedures

## Overview
Step-by-step guide for creating SOPs using RFC 2119 requirement levels. SOPs are delivered one step at a time to LLMs via MCP tool calls — each step MUST be self-contained and describe what concrete output is expected.

## Steps

### Step 1: Gather Process Information

**Objective**: Collect everything needed before writing.

**Actions**:
1. Identify the process, its owner, and target audience
2. Collect existing documentation
3. Interview subject matter experts who perform the process
4. Define scope boundaries (what's included, what's not)

**Requirements**:
- You MUST identify the process owner
- You MUST collect existing documentation
- You SHOULD interview at least two people who perform the process

**Expected Output**: A brief summary covering: process name, owner, audience, frequency, scope boundaries, and key findings from interviews.

**Time Estimate**: 1-2 hours

---

### Step 2: Write the SOP Document

**Objective**: Create the complete SOP markdown document.

**Actions**:
1. Create the document header:
   - `# title`, `## Document Information` (Document ID, Version), `## Overview`,
2. Break the process into sequential steps using `### Step N: Title`
3. For each step include: Objective, Actions, Requirements (using RFC 2119), Expected Output, Time Estimate
4. Add a final feedback step using `submit_sop_feedback`
5. (Optional) Add a `## References` section at the end linking to source documents, standards, or related material the SOP draws from. This section is served via `read_resource` but is deliberately NOT delivered by `run_sop` — treat it as read-only metadata for humans reviewing the SOP.

**Requirements**:
- You MUST use `### Step N:` heading syntax for each step
- You MUST use RFC 2119 keywords correctly:
  - **MUST**: absolute requirements (safety, legal, essential for success)
  - **SHOULD**: recommended practice with valid alternatives
  - **MAY**: truly optional enhancements
- You MUST write each step as self-contained — the executor sees only one step at a time
- You MUST describe concrete expected output for each step
- You MUST use active voice ("Click Submit" not "Submit should be clicked")
- You SHOULD keep 3-7 requirements per step
- You SHOULD group requirements: MUST first, then SHOULD, then MAY
- You SHOULD include time estimates per step
- You MAY add a `## References` section for source links and related material — it's read-only context, not part of execution

**Step writing principles**:
- Each step = one action or closely related actions
- Describe what "done" looks like, not just what to do
- Specify formats when relevant (dates as YYYY-MM-DD, status as VALID/EXPIRED/PENDING)
- Allow flexibility — guide the output without being overly prescriptive

**Expected Output**: A complete SOP markdown document with frontmatter, Overview, and sequential steps — each step containing Objective, Actions, Requirements (RFC 2119), Expected Output, and Time Estimate. Optionally, a trailing `## References` section with links to source documents.

**Time Estimate**: 1-3 hours

---

### Step 3: Review and Validate

**Objective**: Verify the SOP is accurate, complete, and usable.

**Actions**:
1. Read the validation script from `sop://sop_creation_guide/validate_sop.py` using `read_resource`
2. Run `validate_sop(your_sop_content)` against your draft — fix all errors, review warnings
3. Read each step in isolation — does it make sense without context from other steps?
4. Verify RFC 2119 keywords are used correctly (MUST = truly mandatory?)
5. Check that every step has an Expected Output section
6. Have a subject matter expert review for technical accuracy
7. Have an end user review for clarity
8. Conduct a test run using only the SOP as guidance

**Requirements**:
- You MUST read `sop://sop_creation_guide/validate_sop.py` and run it against your draft
- You MUST resolve all errors reported by the validator before publishing
- You MUST have at least one SME review for accuracy
- You MUST have at least one end user review for clarity
- You MUST verify all MUST requirements are truly mandatory
- You SHOULD read each step in isolation to verify it's self-contained
- You SHOULD resolve warnings from the validator (missing Expected Output, Time Estimate)
- You SHOULD conduct a test run of the full process

**Review checklist**:
- [ ] Each step is self-contained and actionable
- [ ] Expected Output is concrete for every step
- [ ] RFC 2119 keywords are correct and capitalized
- [ ] Markdown renders correctly
- [ ] No missing steps or decision points

**Expected Output**: Validation passing with zero errors, all warnings addressed, and confirmation from at least one SME and one end user that the SOP is accurate and clear.

**Time Estimate**: 1-2 hours

---

### Step 4: Publish

**Objective**: Publish the SOP via MCP.

**Actions**:
1. Incorporate review feedback
2. Publish using the `publish_sop` tool with the full markdown content
3. Notify stakeholders

**Requirements**:
- You MUST publish using the `publish_sop` MCP tool
- You MUST incorporate critical review feedback before publishing
- You SHOULD set a review date (quarterly for new processes, annually for stable ones)

**Expected Output**: SOP published via `publish_sop` tool with confirmation of success, version number, and stakeholders notified.

**Time Estimate**: 15-30 minutes

---

### Step 5: Collect Feedback

**Objective**: Gather feedback for continuous improvement.

**Actions**:
1. Reflect on the SOP creation experience
2. Note what was clear, what was confusing, what's missing
3. Submit feedback using `submit_sop_feedback`

**Requirements**:
- You SHOULD call `submit_sop_feedback` with specific observations
- You SHOULD include both what worked well and what needs improvement

**Expected Output**: Feedback submitted via `submit_sop_feedback` tool with specific observations on what worked and what needs improvement.

**Time Estimate**: 5-10 minutes

## References

The `## References` section is an optional, read-only metadata block for linking source material an SOP draws from — standards, design docs, wikis, related SOPs. It appears in the file when an SOP is fetched via `read_resource`, but `run_sop` deliberately skips it so the executing agent only sees `Overview` + the current `### Step N:`.

Use it for citations like:

- [RFC 2119 — Key words for use in RFCs](https://www.rfc-editor.org/rfc/rfc2119)
- [Agent SOPs — standardized markdown format for agent workflows](https://github.com/strands-agents/agent-sop)

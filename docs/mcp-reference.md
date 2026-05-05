# SOP-MCP Server Reference

Auto-generated from the running server's tool and resource schemas.

## Tools

### `list_resources`

List all available resources with their URIs and descriptions.

---

### `publish_sop`

Publish a new or updated Standard Operating Procedure document.

The content parameter MUST contain the complete SOP markdown string with YAML frontmatter declaring:
  - name   (required, snake_case, ≥3 underscore segments)
  - owner  (required, non-empty string — team, alias, or email)
  - stage  (required, 'preprod' or 'prod')
  - version (auto-managed by this tool; set to 1 for new SOPs)
  - description (optional — when omitted, the SOP's `## Overview` section is used for short summaries)

Example call: {"content": "---\nname: my_sop_name\nversion: 1\nowner: my-team\nstage: preprod\n---\n\n# My SOP\n\n## Overview\nOverview text.\n\n### Step 1: First step\nDo the thing."}

Versioning: plain positive integers — 1, 2, 3, 4, … New SOPs start at 1; each subsequent publish increments by one. No semver.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `content` | string | ✓ | Complete SOP markdown with YAML frontmatter (name, owner, stage, version) |
| `stage` | string | ✓ | Deployment stage: 'preprod' or 'prod' |

---

### `read_resource`

Read a resource by its URI.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `uri` | string | ✓ |  |

---

### `run_sop`

Start or advance a Standard Operating Procedure step by step. Use list_resources to discover available SOPs, then call this tool with the SOP name.

Each call returns one step. Execute the step, then call again with current_step incremented to advance.

IMPORTANT: You MUST execute ALL actions described in the returned step content. Do NOT just read or summarize the step — perform the actions using your available tools.

When continuing (current_step >= 1), you MUST provide step_output with the concrete output you produced for the completed step.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `sop_name` | string | ✓ | Name of the SOP to execute (use list_resources to discover available SOPs) |
| `current_step` | integer |  | Step number to advance from. 0 to start, N to advance past step N |
| `step_output` | string |  | Concrete output you produced for the completed step. Required when current_step >= 1 |

---

### `submit_sop_feedback`

Submit improvement feedback for a specific SOP.

Feedback is appended as a single JSON line to
{sop_name}.feedback.jsonl inside the SOP's folder. Each entry
captures the SOP version, a UTC timestamp, and the feedback text — ready
for review when the SOP is next revised.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `sop_name` | string | ✓ | Name of the SOP to submit feedback for |
| `feedback` | string | ✓ | Improvement feedback text — what worked, what needs fixing |

---

## Resources

| URI | Name | MIME Type | Description |
|-----|------|----------|-------------|
| `sop://code_review_process` | code_review_process | text/markdown | This SOP defines the standard process for conducting code reviews to ensure code |
| `sop://employee_onboarding_setup` | employee_onboarding_setup | text/markdown | This SOP defines the steps for onboarding a new employee, covering the initial s |
| `sop://sop_creation_guide` | sop_creation_guide | text/markdown | Step-by-step guide for creating SOPs using RFC 2119 requirement levels. SOPs are |
| `sop://sop_creation_guide/validate_sop.py` | sop_creation_guide/validate_sop.py | text/x-python | Attachment 'validate_sop.py' for SOP 'sop_creation_guide' |
| `sop://user_onboarding_process` | user_onboarding_process | text/markdown | This SOP defines the standard process for onboarding new users to the organizati |


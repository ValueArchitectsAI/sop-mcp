---
name: code_review_process
description: This SOP defines the standard process for conducting code reviews to
  ensure code quality, consistency, and knowledge sharing across the team.
version: 1
owner: Engineering Team
stage: preprod
---

# Standard Operating Procedure: Code Review Process

## Overview
This SOP defines the standard process for conducting code reviews to ensure code quality, consistency, and knowledge sharing across the team.

## Scope
This SOP applies to:
- All software engineers submitting code changes
- Code reviewers providing feedback
- Team leads overseeing code quality

## Definitions
- **CR**: Code Review — a peer review of source code changes
- **Author**: The engineer who wrote the code changes
- **Reviewer**: The engineer reviewing the code changes

## Prerequisites
- Access to the code review tool
- Familiarity with the team's coding standards

---

## Procedure

### Step 1: Prepare Changes for Review

**Objective**: Ensure code changes are ready for peer review.

**Actions**:
1. Run all unit tests locally and verify they pass
2. Run the linter and fix any issues
3. Write a clear commit message following conventional commits
4. Create a code review with a descriptive title and summary

**Requirements**:
- You MUST run all tests before submitting for review
- You MUST include a description of what changed and why
- You SHOULD keep changes focused on a single concern
- You MAY include screenshots for UI changes

**Expected Output**:
- All tests passing locally
- A code review created with title, description, and assigned reviewers

---

### Step 2: Conduct the Review

**Objective**: Review code changes for correctness, readability, and adherence to standards.

**Actions**:
1. Read the CR description to understand the context
2. Review each file for correctness and style
3. Check for edge cases and error handling
4. Verify test coverage for new functionality
5. Leave constructive comments with specific suggestions

**Requirements**:
- You MUST review within 24 hours of being assigned
- You MUST provide actionable feedback with specific suggestions
- You SHOULD approve only when all critical issues are resolved
- You MAY suggest improvements that are not blocking

**Expected Output**:
- Review comments posted on the CR
- Clear approval or request-for-changes status

---

### Step 3: Address Feedback and Merge

**Objective**: Resolve review feedback and merge the changes.

**Actions**:
1. Address all critical feedback from reviewers
2. Respond to each comment explaining the resolution
3. Request re-review if significant changes were made
4. Merge once approved

**Requirements**:
- You MUST address all blocking comments before merging
- You MUST obtain at least one approval before merging
- You SHOULD squash commits for a clean history
- You MAY merge without re-review for minor fixes

**Expected Output**:
- All review comments resolved
- Code merged to the target branch

---

## References
- Team coding standards document
- Conventional Commits specification (https://www.conventionalcommits.org/)

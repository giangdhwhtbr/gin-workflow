---
name: requesting-code-review
description: Self-contained — request provider-backed code review with structured findings, durable evidence, and review capability initialization.
---

# Requesting Code Review

Dispatch an independent reviewer through the worker capability to catch issues before they cascade. The reviewer gets precisely crafted context for evaluation — never your session's history. This keeps the reviewer focused on the work product, not your thought process, and preserves your own context for continued work.

**Core principle:** Review early, review often.

## Required Inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="review")`
- native-harness `ApprovalDecision`

## When to Request Review

**Mandatory:**
- After an implementation pass has local validation evidence
- After each task during plan execution
- After completing a major feature
- Before merge to main

**Optional but valuable:**
- When stuck (fresh perspective)
- Before refactoring (baseline check)
- After fixing a complex bug

## How to Request

**1. Initialize Review State:**
Call `review.initialize` with a `ReviewInitRequest` declaring the task, actor, repository id/role, repository path relative to the configured repository root (the nested implementation worktree when the reviewed source lives in one), base ref, a review ref unique to this task, and the approved source scope. Initialization is idempotent and never re-initializes or overwrites an existing ledger. 

*Note: Never hand-write `review.json`, copy another task's ledger, or invoke the ledger adapter script directly. A task whose ledger has never been created has no review state to transition: `review.request` reports `unavailable` rather than bootstrapping one.*

**2. Prepare the Review Manifest:**
The review manifest contains only the reviewed tree/diff, confirmed requirement, acceptance criteria, and test evidence. It explicitly excludes private reasoning, self-assessment, persuasive summaries, unrelated history, and secrets.

**3. Dispatch Reviewer and Update Status:**
Dispatch an independent reviewer through the worker capability. 
Update the durable status through the task-tracking capability. 

**4. Route and Record Findings:**
Record structured findings, reviewer identity, terminal state, and repository identity through the evidence capability. Route returned findings through the `receiving-code-review` skill. 

Record the implementation's original provider/model route as runtime affinity metadata. Do not copy concrete aliases into the portable plan or durable task fields.

**5. Act on Feedback:**
- Fix Critical issues immediately
- Fix Important issues before proceeding
- Note Minor issues for later
- Push back if the reviewer is wrong (with reasoning)

*Rule: A completed implementation result starts review; it is not evidence that the task may close.*

## Integration with Workflows

**Worker Dispatch:**
- Review after EACH task execution
- Catch issues before they compound
- Fix before moving to the next task

**Executing Plans:**
- Review after each task or at natural checkpoints
- Get feedback, apply, continue

**Ad-Hoc Development:**
- Review before merge
- Review when stuck

## Red Flags

**Never:**
- Skip review because "it's simple"
- Ignore Critical issues
- Proceed with unfixed Important issues
- Argue with valid technical feedback
- Manufacture approval or close work from notification delivery

**If reviewer is wrong:**
- Route findings appropriately
- Push back with technical reasoning
- Show code/tests that prove it works
- Request clarification

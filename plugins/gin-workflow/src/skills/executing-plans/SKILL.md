---
name: executing-plans
description: Self-contained — load, review, and execute implementation plans with provider-backed status tracking and close-out evidence.
---

# Executing Plans

## Overview

Load plan, review critically, execute the assigned work unit, and record validation evidence when complete.

## Required Inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="execute")`
- native-harness `ApprovalDecision`

## The Process

### Step 1: Load and Review Plan
1. Read the plan artifact to resolve approved scope and validation intent.
2. Review critically - identify any questions or concerns about the plan.
3. If concerns: Raise them before starting.
4. If no concerns: Read durable ownership and status for the assigned work unit through task-tracking capabilities (never plan checkboxes) and proceed.

### Step 2: Execute Assigned Work Unit

For the assigned work unit:
1. Update durable status to in-progress via task-tracking.
2. Follow each step exactly (plan has bite-sized steps).
3. Keep changes minimal and strictly in scope; discover related symbols, tests, and project knowledge on demand.
4. Validate immediately after completing implementation and record the evidence.
5. Do not proceed while tests fail, acceptance criteria remain unmet, or close-out evidence is incomplete.
6. Mark work unit status in task-tracking.

### Step 3: Complete Work Unit

After the work unit implementation is complete and validated:
- Follow the canonical verification-and-handoff workflow for task-level evidence logging.
- Invoke the code review capability (`requesting-code-review`) to coordinate code review and achieve terminal review evidence.
- Record terminal review evidence and return state showing `implementation_complete=true`.
- Do not invoke `verify` or `finishing-a-development-branch` directly from `execute`; the workflow router will route to `verify` once implementation and review evidence are complete.

## When to Stop and Ask for Help

**STOP executing immediately when:**
- Hit a blocker (missing dependency, test fails, instruction unclear).
- Plan has critical gaps preventing starting.
- You don't understand an instruction.
- Verification fails repeatedly.

**Ask for clarification rather than guessing.** Use the task-tracking capability to keep incomplete work active or blocked with durable notes.

## When to Revisit Earlier Steps

**Return to Review (Step 1) when:**
- The plan is updated based on your feedback.
- Fundamental approach needs rethinking.

**Don't force through blockers** - stop and ask.

## Remember
- Review plan critically first.
- Follow plan steps exactly.
- Keep changes minimal and in scope.
- Don't skip verifications or evidence recording.
- Reference skills when plan says to.
- Stop when blocked, don't guess.
- Never start implementation on main/master branch without explicit user consent.

## Integration

**Required workflow skills:**
- **using-git-worktrees** - Ensures isolated workspace (creates one or verifies existing).
- **writing-plans** - Creates the plan this skill executes.

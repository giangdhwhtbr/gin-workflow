# Plan: Simulated Workflow Smoke Task

## Objective
Run a tiny docs-only task through the redesigned `gin-workflow` lifecycle so the workflow can be validated with real Beads state transitions, a real plan artifact, a real implementation artifact, and a real close-out sequence.

## Requirement Analysis
- Problem statement: The redesigned workflow needs a concrete end-to-end check that proves the documented lifecycle is executable rather than merely described.
- Success criteria: A small docs artifact is created, the simulation bead is claimed and closed through the documented lifecycle, and the parent validation task records what worked and what still feels rough.
- Constraints: Keep the task deliberately small, docs-only, and non-destructive; use Beads as the durable status system throughout.
- Non-goals: Multi-track orchestration, worktree isolation, branch integration, or platform-specific execution features.

## Approach Options
### Option 1: Real miniature task using the full lifecycle
- Summary: Create a tiny docs-only bead, claim it, write a small plan, implement a small artifact, verify it, and close it.
- Pros: Exercises the real lifecycle surfaces with minimal complexity.
- Cons: Adds a small amount of Beads and docs churn.

### Option 2: Narrative walkthrough only
- Summary: Describe how the lifecycle would work without creating a real bead or artifact.
- Pros: Fastest.
- Cons: Too weak for validation because it does not prove the workflow actually holds up in practice.

### Recommended Approach
- Selected option: Option 1
- Reasoning: It validates the real workflow with the least possible scope while still producing durable evidence.

## Scope
- In scope: one simulation bead, one small docs artifact, one validation report for the parent task
- Out of scope: code changes, subagents, worktrees, merges, or platform-specific hook execution

## Tasks
### Track 1: Plan and implement the smoke-task artifact
- **Dependencies**: none
- **Files**: `docs/simulated-workflow-smoke-task.md`
- **Acceptance criteria**: The artifact states that the task was executed as a Beads-first smoke test and records the lifecycle phases exercised.
- **Estimated complexity**: low

### Track 2: Record validation findings for the parent workflow task
- **Dependencies**: Track 1
- **Files**: `docs/workflow-validation-simulation-2026-07-09.md`
- **Acceptance criteria**: The report documents the actual commands and phase transitions used, what worked cleanly, what friction remained, and any follow-up work if needed.
- **Estimated complexity**: low

## Integration
- **Branch**: current working branch
- **Merge strategy**: sequential

## Validation
- [ ] Confirm the simulation artifact exists and reflects the lifecycle that was exercised
- [ ] Confirm the validation report documents discover, claim, plan, implement, verify, handoff, and close
- [ ] Confirm the smoke-task bead is closed only after the artifact and report exist

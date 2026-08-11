# Agent Task Lifecycle

This document defines the canonical lifecycle for agent work in `gin-workflow`.

## Purpose

The lifecycle exists to make one thing unambiguous:

- The user starts with a requirement, not an implementation task ledger.
- The agent owns the end-to-end workflow from discussion through planning, orchestration, execution, verification, and ship.
- Beads owns durable execution state internally, but it should not be a required manual interface during normal chat-driven workflow.
- Plan files own approved implementation decomposition.
- Worktrees, branches, and temporary orchestration artifacts are implementation details.

If any command, skill, or helper document conflicts with this document, this lifecycle spec wins.

State ownership within this lifecycle is defined in `docs/orchestration-state-model.md`.

Before any lifecycle stage, repository setup resolves `.agent-workflow/generated/effective-config.yaml`. That generated file is the sole lifecycle configuration input. Human-authored configuration remains setup input; plans, Beads, and runtime evidence retain the distinct ownership described below.

## Lifecycle

The required lifecycle is:

1. Requirement Discovery / Discussion
2. Plan Creation
3. Beads Orchestration
4. Implementation
5. Code Review
6. Verification
7. Ship

Not every task needs every optional mechanism, but every task must pass through these phase boundaries in order.

## Phase Definitions

### 1. Requirement Discovery / Discussion

Goal:
Understand the requirement deeply enough to align on what should be built before creating a plan or any Beads tasks.

Required actions:

- Start from the `discuss` or `discover` skill. Use `/discuss` or `/discover` only as optional command aliases on hosts that surface them.
- Explore the relevant repository context before proposing solutions.
- Ask clarifying questions to remove ambiguity.
- Identify missing information, edge cases, risks, assumptions, and constraints.
- Suggest improvements, alternatives, or better approaches when appropriate.
- Challenge assumptions when they appear risky or inconsistent.
- Summarize the final understanding and wait for explicit user confirmation.

Not allowed:

- Do not create the implementation plan yet.
- Do not create, claim, or update Beads tasks yet unless durable project memory is explicitly needed for a blocker or follow-up outside the current requirement discussion.
- Do not begin implementation.

Exit criteria:

- The agent has a clear, reviewable understanding of the requirement.
- The user has explicitly confirmed that understanding.

### 2. Plan Creation

Goal:
Convert the confirmed understanding into a durable implementation plan.

Required actions:

- Use the planning workflow only after the user confirms the summarized understanding.
- Write or update a plan in `.planning/plans/`.
- Include goals, scope, technical approach, required changes, implementation steps, testing strategy, and risks or mitigations.
- Ensure acceptance criteria and verification intent are explicit.

Source of truth:

- Plan files are the source of truth for approved decomposition, file scope, and validation intent.

Exit criteria:

- An approved implementation plan exists, or there is a documented reason why a separate plan is unnecessary.

### 3. Orchestration

Goal:
Translate the approved plan into durable execution state without requiring manual provider commands.

Required actions:

- Create the required durable tasks from the approved plan through the task-tracking capability.
- Break down large work into smaller actionable beads.
- Define dependencies between beads.
- Establish correct execution order and readiness.
- Prepare the work so `bead-worker` execution can begin.

Source of truth:

- Beads for task identity, dependencies, readiness, blockers, ownership, progress, and closure.
- Plan files for approved scope and decomposition.

Exit criteria:

- The plan has been represented as executable Beads work with correct dependency structure.

### 4. Implementation

Goal:
Implement the approved work through Beads-backed worker execution.

Required actions:

- Start implementation using `bead-worker` or equivalent worker execution.
- Implement each bead according to its declared scope.
- Keep durable progress updated through the task-tracking capability as work advances.
- Run local validation as part of each worker’s execution loop.

Blocked-work handling:

- If implementation reveals missing requirements, ambiguity, or blockers that require product or design clarification, return to Requirement Discovery / Discussion instead of making assumptions.
- If newly discovered work is durable, record it in Beads as follow-up work.

Exit criteria:

- Implementation is complete enough for verification, or blockers are recorded clearly and routed back to discussion when needed.

### 5. Verification

Goal:
Demonstrate that the implementation satisfies the original requirement, approved plan, and acceptance criteria.

Required actions:

- Run the relevant tests, checks, or manual validation steps.
- Verify the implementation against the original requirement, not just the code diff.
- Record failures honestly and fix them before claiming completion.
- Identify any issues, gaps, or residual risks.

Exit criteria:

- Verification passed, or the work remains active or blocked with failures documented.

### 6. Ship

Goal:
Complete the delivery workflow once implementation and verification are complete.

Required actions:

- Prepare the changes for delivery only after verification passes.
- Follow `docs/verification-and-handoff-workflow.md` before treating the work as complete.
- Ensure the implementation is complete, tested, and ready for delivery.
- Close the relevant Beads work only after verification and handoff evidence are complete.

Session-close behavior:

- Follow the repo session-close protocol from `AGENTS.md`.
- Do not commit or push unless explicitly authorized by the active instructions or the user.

Exit criteria:

- The work is ready for delivery and the durable execution state reflects the final outcome correctly.

## Ownership Model

### Beads owns durable task state

- task identity
- priority
- dependencies
- claim/assignee state
- in-progress versus closed state
- blocked reasons and follow-up work
- final closure

### Plan files own

- approved approach
- task decomposition
- declared file scope
- validation intent
- model guidance metadata

### Runtime artifacts own supplemental evidence and cache

- temporary isolation details only

They must be reconstructible or disposable. They are not authoritative workflow state.

Worker result, event, context, review, knowledge, evidence, and secret-reference rules are canonical in [context-and-evidence-policy.md](context-and-evidence-policy.md). Capability boundaries are canonical in [capability-provider-contracts.md](capability-provider-contracts.md); lifecycle documents do not prescribe provider commands or implementation methodology.

## Primary Interface By Phase

| Phase | Primary skills | Optional command aliases |
| --- | --- | --- |
| Requirement Discovery / Discussion | `discuss` | `/discuss` |
| Plan Creation | `plan` | `/plan` |
| Orchestration | `orchestrate` | `/orchestrate` |
| Implementation | `execute` | `/execute` |
| Code Review | `cross-agent-code-review` / `receiving-code-review` | `/review` |
| Verification | `verify` | `/verify` |
| Ship | `ship` | `/ship` |

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

Repository setup is a one-time prerequisite outside this lifecycle. It creates
`.agent-workflow/generated/effective-config.yaml`, the sole lifecycle
configuration input. Each lifecycle entry point loads that existing generated
file; it never invokes setup automatically. If the file is absent, stop and
instruct the user to run `setup` once. Human-authored configuration remains
setup input; plans, Beads, and runtime evidence retain the distinct ownership
described below.

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

- Plan files are the source of truth for approved decomposition, file scope, and validation intent. For standalone or pre-existing beads where a separate plan is unnecessary, the task itself supplies the approved file scope and validation intent.

Exit criteria:

- An approved implementation plan exists, or there is a documented reason why a separate plan is unnecessary (with process gates waived accordingly).

### 3. Orchestration

Goal:
Translate the approved plan into durable execution state without requiring manual provider commands.

Required actions:

- Create the required durable tasks from the approved plan through the task-tracking capability.
- Distinguish the Parent Bead (deliverable/epic) from Track Beads (technical work units). Never attach parent deliverable merge-hold restrictions ("remain open until human-confirmed merge") to child track beads.
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
- Implement each bead according to its declared scope (from plan file, or derived from task metadata for standalone work units).
- Keep durable progress updated through the task-tracking capability as work advances.
- Run local validation as part of each worker’s execution loop.
- When a track bead completes its technical scope, passes tests, and satisfies code review, it must be closed in Beads to unblock downstream dependent tracks.
- Commit and push the feature branch; never claim "waiting for PR merge" without a real PR link, and prompt the user with clear options (request approval to create a PR, or keep the pushed branch and continue to the next track).

Blocked-work handling:

- If implementation reveals missing requirements, ambiguity, or blockers that require product or design clarification, return to Requirement Discovery / Discussion instead of making assumptions.
- If newly discovered work is durable, record it in Beads as follow-up work.

Exit criteria:

- Implementation is complete enough for verification, or blockers are recorded clearly and routed back to discussion when needed. Track beads that pass tests and review are closed to release dependencies.

### 5. Code Review

Goal:
Obtain an independent, terminal review decision over the approved scope before verification.

Required actions:

- Coordinate review through the configured review capability after implementation is complete.
- Review the bounded checkpoint, acceptance criteria, tests, and evidence with an active lease.
- Record structured findings and resolve or explicitly disposition them.
- Require terminal approval evidence before verification can treat review as complete.

Code Review is a separately coordinated provider-backed activity between
Implementation and Verification. It is not a router lifecycle stage and does not
add a `review_approved` router gate; the router continues to expose only its
implemented stages (`discuss`, `plan`, `orchestrate`, `execute`, `verify`, `ship`,
and `progress`).

Exit criteria:

- A terminal review approval and its verification evidence are persisted, or
  findings/blockers remain active and verification cannot pass.

### 6. Verification

Goal:
Demonstrate that the implementation satisfies the original requirement, approved plan, and acceptance criteria.

Required actions:

- Run the relevant tests, checks, or manual validation steps.
- Verify the implementation against the original requirement, not just the code diff.
- Record failures honestly and fix them before claiming completion.
- Identify any issues, gaps, or residual risks.

Exit criteria:

- Verification passed, or the work remains active or blocked with failures documented.

### 7. Ship

Goal:
Complete the delivery workflow once implementation and verification are complete.

Required actions:

- Prepare the changes for delivery only after verification passes.
- Follow `docs/verification-and-handoff-workflow.md` before treating the work as complete.
- Ensure the implementation is complete, tested, and ready for delivery.
- Close the relevant Beads work only after verification and handoff evidence are complete.

Session-close behavior:

- Follow the repo session-close protocol from `AGENTS.md`.
- Commit and push freely on feature/worktree branches; never commit directly to `main`/`master`. Creating a PR, merging into the base branch, or force-pushing requires explicit user approval.

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

For standalone or pre-existing beads executed without a separate plan, the task description and acceptance criteria own declared file scope and validation intent.

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

## Gates and evidence

Each router stage has a durable gate: requirement confirmation precedes planning;
plan approval precedes orchestration; orchestration readiness precedes execution;
implementation completion precedes the separately coordinated Code Review and
Verification activities; and verification passes before ship. The router evaluates
one implemented next stage only and holds at `progress` when the task is blocked,
a capability is disabled, or a protected action lacks fresh persisted approval and
audit evidence. Code Review approval is represented by terminal review/evidence
records consumed by Verification, not by a new router gate.

### Gate Classification and Waivers

Gates evaluate to tri-state values (`satisfied`, `waived`, or `unmet`). When a gate is not directly satisfied by recorded state, it may be waived via an append-only `gate.waived` event in the `WorkflowEventStore` matching the active scope hash:

| Gate Class | Gates | Waiver Rules |
| --- | --- | --- |
| **Process** | `requirement_confirmed`, `plan_approved`, `orchestration_ready` | May be waived by the agent with a mandatory recorded reason. |
| **Safety** | `verification_passed`, `review_approved` | Requires human approval and a mandatory follow-up task ID. |
| **Non-waivable** | `implementation_complete`, `shipped` | Cannot be waived under any circumstances; statements of fact or terminal state. |

Whenever the router evaluates a hold decision, it is structurally required to return at least one concrete remedy. Diagnostic inspection is available via `gin-workflow state`, and process/safety gate holds can be acted on using `gin-workflow unblock`.

### Scope-Bound Approval Validity

Approval validity is bound to the target scope hash (`scope_hash`) and a configurable policy TTL (`policy.approval.ttl_seconds`, defaulting to 86,400 seconds / 24 hours) rather than a rigid wall-clock window. As long as the approved scope hash remains unchanged and the decision falls within the configured TTL (with up to 60 seconds of clock-skew tolerance), an approval obtained before dispatch remains valid even for long-running worker tasks.

Identity-bound worker, checkpoint, review, and verification evidence supports the
gates but never replaces Beads status or plan-owned scope. A lease conflict,
identity mismatch, unavailable provider, or evidence-integrity failure is a hold
with a diagnostic and safe next action, not permission to bypass the gate.


# Stage Contract

Shared rules for every lifecycle stage skill. One stage invocation performs one action, then stops.

## Configuration
If `.agent-workflow/generated/effective-config.yaml` is missing from the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`; linked worktrees have none), stop and tell the user to run `/setup` once. `capabilities: {}` is valid (all capabilities enabled). Never run setup from a lifecycle stage.

## State and gates
- Read: `gin-workflow state --format json [--workflow-id ID]`
- Record: `gin-workflow record <requirement-confirmed|plan-approved|orchestration-ready|shipped> --evidence <path|ids|output> --actor <id> [--workflow-id ID]` (`orchestration-ready` also takes `--epic <parent-bead>`)
- Waive: `gin-workflow unblock --gate GATE --reason TEXT --actor ID [--follow-up TASK_ID]`
`implementation_complete` is derived: every child of the recorded epic is closed in Beads. `shipped` is derived: the epic itself is closed. Neither can be waived.
Quality checks (lint, typecheck, tests, build) run in git hooks, not in a stage: `gin-workflow hooks install` (pre-commit and pre-push).
Standalone bead (no plan): use `--workflow-id <bead>` on every `state` and `record` call for it. `record orchestration-ready --workflow-id <bead> --epic <bead>` makes the bead its own epic; its description stands in for the spec and plan, so `requirement_confirmed` and `plan_approved` count as satisfied while it has no child beads. `implementation_complete` is then the bead closed, and `record shipped --workflow-id <bead> --evidence <merge commit> --actor <id>` marks it shipped after the merge.

## Evidence
Valid: test/command output, review-ledger state, bead IDs, spec/plan paths. Never: self-assessment, summaries, or notification delivery.

## Approvals
Get explicit user confirmation in the harness before each action below, and record it where the table says before acting. A notification is never approval.

| Action | Recorded as |
|---|---|
| Approve a plan | `gin-workflow record plan-approved` |
| Production-impacting parallel work | bead notes (`gin-workflow task update <id> --notes`) |
| Disable worktree isolation, work in place, or run on the current branch | bead notes |
| Change the execution strategy or scope | bead notes, and the plan when it changes |
| Create a pull request | the PR link in the handoff |
| Merge into the base branch | the merge commit in the handoff |
| Force-push (only when the user asks) | the handoff |
| Discard work (the user types `discard`) | the handoff |

## Notifications
Before stopping to wait for the user (a confirmation, an approval, a choice, `human_decision_required`, a blocker), run `gin-workflow notify --event needs_input "<what you need>"`. It does nothing unless `notifications.telegram` is on, and a message is never approval.

## Context
Load only the requirement, file scope, and validation intent. Look up symbols, tests, and knowledge on demand: `codegraph explore "<query>"` when `.codegraph/` exists, else grep/read. Build an artifact from `gin-workflow specs template <name>` when one exists; never invent its structure.

## Git
Commit only on a feature or worktree branch, never on `main`/`master`. `discuss` and `plan` commit on `feat/<topic>` (`<topic>` from `.planning/specs/<date>-<topic>-design.md`); SDD and team modes use their own `spec/...` branch. `execute` commits and pushes its track branch. `quick` commits on the current feature branch, or on a new `quick/<slug>` when started on `main`/`master`, and does not push. Pull requests, merges, and force-pushes follow Approvals.

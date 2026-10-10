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

## Approval
Get explicit user confirmation in the harness before `plan-approved`, production-impacting parallel work, disabling worktree isolation, or execution-strategy/scope changes. Record it before acting.

## Context
Load only the requirement, file scope, and validation intent. Look up symbols, tests, and knowledge on demand: `codegraph explore "<query>"` when `.codegraph/` exists, else grep/read. Build an artifact from `gin-workflow specs template <name>` when one exists; never invent its structure.

## Git
Commit and push freely on feature/worktree branches; never commit directly to `main`/`master`. Creating a PR, merging into the base branch, or force-pushing requires explicit user approval.

# Stage Contract

Shared rules for every lifecycle stage skill. One stage invocation performs one action, then stops.

## Configuration
If `.agent-workflow/generated/effective-config.yaml` is missing, stop and tell the user to run `/setup` once. `capabilities: {}` is valid (all capabilities enabled). Never run setup from a lifecycle stage.

## State and gates
- Read: `gin-workflow state --format json [--workflow-id ID]`
- Record: `gin-workflow record <requirement-confirmed|plan-approved|orchestration-ready|verification-passed> --evidence <path|ids|output> --actor <id> [--workflow-id ID]` (`orchestration-ready` also takes `--epic <parent-bead>`)
- Waive: `gin-workflow unblock --gate GATE --reason TEXT --actor ID [--follow-up TASK_ID]`
`implementation_complete` is derived: every child of the recorded epic is closed in Beads. `shipped` is derived: the epic itself is closed. Neither can be recorded or waived.

## Evidence
Valid: test/command output, review-ledger state, bead IDs, spec/plan paths. Never: self-assessment, summaries, or notification delivery.

## Approval
Get explicit user confirmation in the harness before `plan-approved`, production-impacting parallel work, disabling worktree isolation, or execution-strategy/scope changes. Record it before acting.

## Context
Load only the requirement, file scope, and validation intent. Look up symbols, tests, and knowledge on demand: `codegraph explore "<query>"` when `.codegraph/` exists, else grep/read.

## Git
Commit and push freely on feature/worktree branches; never commit directly to `main`/`master`. Creating a PR, merging into the base branch, or force-pushing requires explicit user approval.

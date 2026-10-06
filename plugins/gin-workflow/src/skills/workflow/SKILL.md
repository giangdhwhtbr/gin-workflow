---
name: workflow
description: Route current durable state to exactly one guarded lifecycle stage, or diagnose a held workflow.
---

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`; linked worktrees have none), stop: tell the user to run `/setup` once and do nothing else. (`capabilities: {}` is a valid config.)
2. Read [references/stage-contract.md](../../references/stage-contract.md) now: it defines the gate CLI, valid evidence, approval, and git rules this stage relies on.

# Workflow

Evaluate state and invoke one stage only.

## Routing
1. Run `gin-workflow state --format json [--workflow-id ID]`. It replays the persisted event stream, applies waivers and approval TTL (`policy.approval.ttl_seconds`, default 86,400 s), and returns the stage, decision, gates, evidence, and remedies.
2. Gates are evaluated in order: `requirement_confirmed`, `plan_approved`, `orchestration_ready`, `implementation_complete`, `verification_passed`, `shipped`. Each is `satisfied`, `waived`, or `unmet`. Blocked state routes to `progress`.
3. Keep the returned stage, decision, evidence, and remedies, then invoke exactly that stage's skill with a fresh context limited to that stage, and stop.

Never invoke a second stage based on the first stage's result, never loop, and never treat notifications as approval evidence.

## Held or blocked workflows
- Inspect: `gin-workflow state` (gate table, decision, evidence, remedies).
- Waive a gate: `gin-workflow unblock --gate GATE --reason TEXT --actor ID [--follow-up TASK_ID]`. Safety gates (`verification_passed`, `review_approved`) require `--follow-up`; `implementation_complete` and `shipped` cannot be waived.
- Clear a blocker: `gin-workflow unblock --clear-blocker --reason TEXT --actor ID` (audited `blocker.cleared` event).

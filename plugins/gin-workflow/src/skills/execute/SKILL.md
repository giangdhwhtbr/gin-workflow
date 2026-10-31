---
name: execute
description: Implement and validate exactly one ready work unit at its manifest route.
---

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`; linked worktrees have none), stop: tell the user to run `/setup` once and do nothing else. (`capabilities: {}` is a valid config.)
2. Read [references/stage-contract.md](../../references/stage-contract.md) now: it defines the gate CLI, valid evidence, approval, and git rules this stage relies on.

# Execute

Implement one ready work unit inside its approved scope and record evidence.

## 1. Select and review
1. Require `orchestration_ready`. For a standalone or pre-existing bead, record it as its own epic instead of a plan cycle: `gin-workflow record orchestration-ready --workflow-id <bead> --epic <bead> --evidence <bead> --actor <id>`, and pass `--workflow-id <bead>` to every later `state`/`record` call for it. An epic labelled `roadmap` with no confirmed spec: refuse and recommend `/discuss <epic-id>`; never record it as its own epic.
2. Resume first: `gin-workflow task list --parent <epic> --status in_progress`; if empty, use `task ready`. Claim with `task update <id> --claim`.
   With `project.team.enabled`, add `--assignee <git user.email>` to that list; `team ready` and `team claim <id>` (`gin-team` skill) replace `task ready` and `--claim`.
3. Resolve file scope and validation intent from the plan track, or from the task description and acceptance criteria for a standalone unit. Review critically and raise concerns before starting.
4. Work in the isolated worktree. Never implement on main/master without explicit consent.

## 2. Implement
- Follow the plan steps exactly, test first. Keep changes minimal and in scope.
- Read the shape appendix for `project.shape` from `gin-workflow state --format json` (plugin `references/shape-<shape>.md`) before editing.
- With `project.layout: sdd`, tests carry the track's REQ-IDs (the `gin-sdd` skill).
- Run `gin-workflow rules --files <scope files>` and give its output to the `developer` agent. Rules never widen the scope.
- On a `greenfield` project, a task that sets up lint, typecheck, or test starts from the `suggest` snippets of the missing checks in `checks_details.rules.tool_checks` of `gin-workflow setup doctor --format json`.
- Validate immediately and keep the command output as evidence. Do not proceed while tests fail or acceptance criteria are unmet.
- **Stop and ask** on a blocker, a plan gap, an unclear instruction, or repeated validation failure. Leave the bead in progress with a `gin-workflow task update <id> --notes` entry; do not guess. Failures route to the `gin-debugging` skill.
- Scope or execution-strategy changes and production-impacting parallel work need explicit approval first.
- Record notable decisions or risks per `gin-knowledge`.

## 3. Worker dispatch
Dispatch each track using this loop:
1. `gin-workflow routes dispatch --workflow-id <w> --task-id <id> --json` gives the route.
2. When `provider` is the main harness, spawn `gin-workflow:developer` with that `model` and `effort` and a bounded context: track text, file scope, `gin-workflow rules` output, worktree path, validation commands. Never the parent transcript or secrets. When `provider` is a provider other than the main harness, dispatch through gin-orchestrator as [worker lifecycle](references/worker-lifecycle.md) describes, with the same route.
3. On `done`, check the commits and command output, then request review.
4. On `needs_clarification`, answer from the spec or plan and re-dispatch at the same route with the excerpt; otherwise `gin-workflow notify --event needs_input "<track>: <question>"` and leave the bead `in_progress` with a note.
5. On `failed`, `gin-workflow routes dispatch --workflow-id <w> --task-id <id> --escalate "<reason>" --json` and re-dispatch in the same worktree; on exit 2, ask the user.
6. On `blocked`, ask the user.
Read [delegation policy](references/delegation-policy.md) and [result contract](references/result-contract.md) before dispatching.

## 4. Complete
1. Request review through the `review` skill and wait for a terminal review state.
2. Once tests and review pass, run `gin-workflow usage collect --bead <id> --best-effort`, then close the track bead (`gin-workflow task close <id> --reason "<evidence>"`); this unblocks dependents and needs no PR or merge. If `gin-workflow state --workflow-id <id>` now shows `implementation_complete` satisfied, run `gin-workflow notify --event run_finished "<epic>: all tracks closed"`.
3. Commit and push the feature branch, then `python3 review-ledger.py push-refs --bead-id <id>` (squash-merge checks fetch the refs). Never report "waiting for PR merge" without a real PR link. Stop at handoff and offer two options:
   1. Xin lệnh tạo PR từ nhánh feature đã push.
   2. Giữ nhánh feature đã push và tiếp tục chuyển sang track tiếp theo sử dụng artifact vừa sinh.
4. Return `implementation_complete`. Do not invoke `ship`.

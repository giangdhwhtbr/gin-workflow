---
name: execute
description: Implement and validate exactly one ready Beads work unit, directly or through a routed worker.
---

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the repository, stop: tell the user to run `/setup` once and do nothing else. (`capabilities: {}` is a valid config.)
2. Read [references/stage-contract.md](../../references/stage-contract.md) now: it defines the gate CLI, valid evidence, approval, and git rules this stage relies on.

# Execute

Implement one ready work unit inside its approved scope and record evidence.

## 1. Select and review
1. Require `orchestration_ready`. For a standalone or pre-existing bead, record it as its own epic instead of a plan cycle: `gin-workflow record orchestration-ready --workflow-id <bead> --epic <bead> --evidence <bead> --actor <id>`, and pass `--workflow-id <bead>` to every later `state`/`record` call for it.
2. Pick one unit from `bd ready`; read it with `bd show <id> --json`; claim it with `bd update <id> --status in_progress`.
   With `project.team.enabled`, pick with `gin-workflow team ready` and claim with `gin-workflow team claim <id>` (the `gin-team` skill).
3. Resolve file scope and validation intent from the plan track, or from the task description and acceptance criteria for a standalone unit. Review critically and raise concerns before starting.
4. Work in the isolated worktree. Never implement on main/master without explicit consent.

## 2. Implement
- Follow the plan steps exactly, test first. Keep changes minimal and in scope.
- Read the shape appendix for `project.shape` from `gin-workflow state --format json` (plugin `references/shape-<shape>.md`) before editing.
- With `project.layout: sdd`, tests carry the track's REQ-IDs (the `gin-sdd` skill).
- Run `gin-workflow rules --files <scope files>` and give its output to the `developer` agent (or follow it when executing directly). Rules never widen the scope.
- On a `greenfield` project, a task that sets up lint, typecheck, or test starts from the `suggest` snippets of the missing checks in `checks_details.rules.tool_checks` of `gin-workflow setup doctor --format json`.
- Validate immediately and keep the command output as evidence. Do not proceed while tests fail or acceptance criteria are unmet.
- **Stop and ask** on a blocker, a plan gap, an unclear instruction, or repeated validation failure. Leave the bead in progress with a `bd update <id> --notes` entry; do not guess. Failures route to the `gin-debugging` skill.
- Scope or execution-strategy changes and production-impacting parallel work need explicit approval first.
- Record notable decisions or risks per `gin-knowledge`.

## 3. Direct vs worker dispatch
Execute directly for sequential work, a single agent, three or fewer tasks, or no explicit worker condition. Use a worker only for parallelizable work with more than three tasks, long-running or specialized work, or independent review. When dispatching:
- Send a bounded context (unit, scope, validation intent); never the parent transcript, model names, secrets, or private reasoning. Fail with `context_unavailable` if required context is missing.
- Re-resolve the provider role and reasoning at dispatch time; recheck circuit, health, and capacity. Keep the preferred/fallback order and never downgrade the requested reasoning tier. Record the actual route and any fallback in runtime events only.
- One task claim and one isolated workspace per worker; reuse the retry identity; never redispatch a completed task. If every route is unavailable, return `worker_routes_unavailable`.
- When dispatching an implementer, use the `developer` agent.
- Read [worker lifecycle](references/worker-lifecycle.md), [delegation policy](references/delegation-policy.md), and [result contract](references/result-contract.md) before dispatching.

## 4. Complete
1. Request review through the `review` skill and wait for a terminal review state.
2. Once tests and review pass, run `gin-workflow usage collect --bead <id> --best-effort`, then close the track bead (`bd close <id> --reason "<evidence>"`); this unblocks dependents and needs no PR or merge.
3. Commit and push the feature branch. Never report "waiting for PR merge" without a real PR link. Stop at handoff and offer two options:
   1. Xin lệnh tạo PR từ nhánh feature đã push.
   2. Giữ nhánh feature đã push và tiếp tục chuyển sang track tiếp theo sử dụng artifact vừa sinh.
4. Return `implementation_complete`. Do not invoke `verify` or `ship`.

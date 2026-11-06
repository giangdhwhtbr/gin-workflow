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
1. Require `orchestration_ready`. For a standalone bead, claim it first (`gin task update <bead> --claim`; with Beads, `record` sets it `in_progress` and a later claim is refused). Then record it as its own epic: `gin record orchestration-ready --workflow-id <bead> --epic <bead> --evidence <bead> --actor <id>`, and pass `--workflow-id <bead>` to every later `state`/`record` call. An epic labelled `roadmap` with no confirmed spec: refuse and recommend `/discuss <epic-id>`; never record it as its own epic.
2. Resume first: `gin task list --parent <epic> --status in_progress`; if empty, use `task ready`. Claim with `task update <id> --claim`.
   With `project.team.enabled`, add `--assignee <git user.email>` to that list; `team ready` and `team claim <id>` (`team` skill) replace `task ready` and `--claim`.
3. Resolve file scope and validation intent from the plan track, or from the task description and acceptance criteria for a standalone unit. Review critically and raise concerns before starting.
4. Work in the isolated worktree. Never implement on main/master without explicit consent.

## 2. Implement
- Follow the plan steps exactly, test first. Keep changes minimal and in scope.
- Read the shape appendix for `project.shape` from `gin state --format json` (plugin `references/shape-<shape>.md`) before editing.
- With `project.layout: sdd`, tests carry the track's REQ-IDs (the `sdd` skill).
- Run `gin rules --files <scope files>` and give its output to the `developer` agent. Rules never widen the scope.
- On a `greenfield` project, a task that sets up lint, typecheck, or test starts from the `suggest` snippets of the missing checks in `checks_details.rules.tool_checks` of `gin setup doctor --format json`.
- Validate immediately and keep the command output as evidence. Do not proceed while tests fail or acceptance criteria are unmet.
- **Stop and ask** on a blocker, a plan gap, an unclear instruction, or repeated validation failure. Leave the bead in progress with a `gin task update <id> --notes` entry; do not guess. Failures route to the `debugging` skill.
- Scope or execution-strategy changes and production-impacting parallel work need approval (stage-contract Approvals).
- Record notable decisions or risks per `learn`.

## 3. Worker dispatch
Dispatch each track using this loop:
1. `gin routes dispatch --workflow-id <w> --task-id <id> --json` gives the route.
2. When `provider` is the main harness and its native subagent supports the route (`claude` `Agent` with `model`, or `antigravity` `invoke_subagent(TypeName="developer", Model="inherit")` when `model` is `provider_default` and `effort` is null), spawn `gin:developer` with a bounded context: track text, file scope, `gin rules` output, worktree path, validation commands (never the parent transcript or secrets). Otherwise (a provider other than the main harness, `codex`/`opencode`/`copilot`, or `antigravity` with an explicit model/effort), dispatch via `gin-orchestrator dispatch` per [worker lifecycle](references/worker-lifecycle.md).
3. After each worker result, run `gin usage collect --bead <epic> --best-effort`. If `routes dispatch` exits 3 (`over_budget`), `gin notify --event needs_input "<epic>: over budget"`, leave the bead `in_progress` with a note, and ask the user to raise `usage.budget_usd` or stop.
4. On `done`, check the commits and command output, then request review.
5. On `needs_clarification`, answer from the spec or plan and re-dispatch at the same route with the excerpt; otherwise `gin notify --event needs_input "<track>: <question>"` and leave the bead `in_progress` with a note.
6. On `failed`, `gin routes dispatch --workflow-id <w> --task-id <id> --escalate "<reason>" --json` and re-dispatch in the same worktree; on exit 2, ask the user.
7. On `blocked`, ask the user.
Read [delegation policy](references/delegation-policy.md) and [result contract](references/result-contract.md) before dispatching.

## 4. Complete
1. Request review through the `review` skill and wait for a terminal review state. This session is the implementer there: it runs `init`, `checkpoint`, and `transition-requested --to review-requested --actor-role worker`.
2. Once tests and review pass, run `gin usage collect --bead <id> --best-effort`, then close the track bead (`gin task close <id> --reason "<evidence>"`); this unblocks dependents and needs no PR or merge. If `gin state --workflow-id <id>` now shows `implementation_complete` satisfied, run `gin notify --event run_finished "<epic>: all tracks closed"`.
3. Commit and push the track branch (stage-contract Git), then `python3 review-ledger.py push-refs --bead-id <id>` (squash-merge checks fetch the refs). Never report "waiting for PR merge" without a real PR link. Stop at handoff and offer two options:
   1. Ask for the command to create a PR from the pushed feature branch.
   2. Keep the pushed feature branch and continue with the next track, using the artifact just produced.
4. Return `implementation_complete`. Do not invoke `ship`.

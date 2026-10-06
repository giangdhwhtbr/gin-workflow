---
name: quick
description: Small, low-risk change without plan or beads: confirm, implement, verify per rigor, report.
---

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`; linked worktrees have none), stop: tell the user to run `/setup` once and do nothing else. (`capabilities: {}` is a valid config.)
2. Read [references/stage-contract.md](../../references/stage-contract.md) now: it defines the gate CLI, valid evidence, approval, and git rules this stage relies on.

# Quick

A fast path for a small, low-risk change. No plan, no beads, no lifecycle gates.

1. Restate the requirement in 1–3 lines and get the user's confirmation. With `project.layout: sdd`, a change to behavior a living-spec REQ describes escalates (the `gin-sdd` skill).
2. Estimate the changed files and top-level modules, then run `gin-workflow quick-check --changed-files N --modules M --format json`:
   - `refused`: stop and point to `/gin-workflow:discuss` (strict rigor needs a `requirement_confirmed` waiver first).
   - `escalate`: stop and recommend the full lifecycle.
   - `allowed`: continue with the returned `verify_commands` and `review` mode.
3. Run `gin-workflow rules --files <files to change>` and follow its output. Implement the change. Write a failing test first when behavior changes.
4. Run every returned `verify_commands` entry fresh and keep its output. Under `easy` rigor, scope tests to the changed files when the runner supports it.
5. Review:
   - `review: independent`: one review per the `review` skill, with a fresh session or subagent.
   - `review: self_check`: re-read the diff; no debug leftovers, no secrets, and tests cover the change.
6. If the change grew beyond the estimate, re-run `quick-check`; on `escalate`, stop and recommend the full lifecycle.
7. `gin-workflow record quick-completed --evidence "<files>; <verify results>" --actor <id>`.
8. Report a summary of the change and the verify output.

Never create plans, beads, or gates. Never commit or push; the user commits.

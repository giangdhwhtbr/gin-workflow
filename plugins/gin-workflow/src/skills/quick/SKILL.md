---
name: quick
description: 'Small, low-risk change without plan or beads: confirm, implement, verify per rigor, report.'
---

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`; linked worktrees have none), stop: tell the user to run `/setup` once and do nothing else. (`capabilities: {}` is a valid config.)
2. Read [references/stage-contract.md](../../references/stage-contract.md) now: it defines the gate CLI, valid evidence, approval, and git rules this stage relies on.

# Quick

A fast path for a small, low-risk change. No plan, no beads, no lifecycle gates. Usage: `/gin:quick [--epic <id> | --milestone <id>]`; the option only names where team mode records the run.

1. Restate the requirement in 1–3 lines and get the user's confirmation. With `project.layout: sdd`, a change to behavior a living-spec REQ describes escalates (the `sdd` skill).
2. Estimate the changed files and the source modules they touch (a changed module's tests and docs count as that module), then run `gin quick-check --changed-files N --modules M --format json`:
   - `refused`: stop and point to `/gin:discuss` (strict rigor needs a `requirement_confirmed` waiver first).
   - `escalate`: stop and recommend the full lifecycle.
   - `allowed`: continue with the returned `verify_commands`, `run_at`, and `review` mode.
   In a workspace, run `/gin:quick` from the repository you change; `quick-check` returns that repository's checks.
3. Run `gin rules --files <files to change>` and follow its output. Implement the change. Write a failing test first when behavior changes.
4. Run every returned `verify_commands` entry fresh and keep its output. Scope tests to the changed files, when the runner supports it, if `run_at` (`project.run_at`) is `push`, or under `easy` rigor with `track`. With `host`, `verify_commands` holds only lint and typecheck.
5. Review:
   - `review: independent`: one review per the `review` skill, with a fresh session or subagent.
   - `review: self_check`: re-read the diff; no debug leftovers, no secrets, and tests cover the change.
6. If the change grew beyond the estimate, re-run `quick-check`; on `escalate`, stop and recommend the full lifecycle.
7. Commit per stage-contract Git: on `main`/`master`, first `git switch -c quick/<slug>`. In solo mode, or on an existing feature branch, do not push. With `project.team.enabled` on a new `quick/<slug>`:
   1. Propose the capabilities the changed files touch (the Capability Map of `13-CAPABILITIES.md`, else the folders of `docs/specs/`) and let the member confirm them. List the covering cases per the Covering cases section of the `qa-track` skill.
   2. Push `quick/<slug>` to `origin`, then open the pull request with the `team.host` command of `team/references/hosts.md` (in a workspace child, against its default branch). The description holds the summary, each verify command with its result, the covering cases, and `Needs ship approval: run gin team check --gate ship <pr-url> before merging.` A failed push or pull request stops here: report it; the commit stays.
   3. Record the run with `gin task comment <id> "<text>"` on the `--epic` or `--milestone` id, else the only milestone whose `status` is `active` in `gin milestone list --json` (none or several: no comment; say so). A failed comment is reported and the run continues. The text, labels never translated:
      ```
      [gin quick] <branch> <pr-url>
      Summary: <one line>
      Files: <count>
      Author: <git email>
      Cases: <case-id>, <case-id> | none
      ```
   4. With `team.beads_sync` set, `gin team sync`.
8. `gin record quick-completed --evidence "<files>; <verify results>[; <pr-url>]" --actor <id>`.
9. Report a summary of the change, the verify output, and, in team mode, the pull request URL and where the run was recorded.

Never create plans, beads, or gates.

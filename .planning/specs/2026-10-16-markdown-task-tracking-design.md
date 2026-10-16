# Markdown task tracking (gin-workflow without Beads)

Status: draft for user review.

## Goal and scope

Some environments cannot install Beads (`bd`). gin-workflow must still run the full lifecycle there. Add a `markdown` task-tracking mode to the same plugin: same skills, same gates, tasks stored as Markdown files inside the repository. Beads stays the default and must keep working exactly as it does today.

In scope:
- A `markdown` task-tracking provider next to the existing `beads` provider.
- A neutral `gin-workflow task <verb>` CLI that skills and agents call instead of `bd`, routed to the configured provider.
- Delivery gates (`implementation_complete`, `shipped`) derived through the provider instead of calling `bd` directly.
- `/setup` proposing `markdown` when `bd` is not installed.
- The safety hook falling back to `python3` when `jq` is missing, so a missing `jq` no longer blocks every shell command.

Out of scope:
- A separate `gin-workflow-light` plugin or a reduced skill set.
- Migrating tasks between `beads` and `markdown`.
- Team mode with `markdown` (team mode keeps requiring Beads).
- Windows file locking beyond what the event store supports today (POSIX `fcntl`).

## Requirements

1. **Beads non-regression.** With `task_tracking: beads` (the default), every existing lifecycle behavior, gate result, and test outcome is unchanged. `gin-workflow task <verb>` under `beads` delegates to `bd` with equivalent arguments and returns `bd`'s JSON. The existing beads test suites pass unmodified, apart from parameterization that adds the markdown provider.
2. **Provider.** `MarkdownTaskTrackingProvider` in `workflow_providers/` implements the same task-tracking interface and capabilities as `BeadsTaskTrackingProvider` (create, read, update, close, dependency, readiness), and `registry.py` registers it under the name `markdown`.
3. **Storage.** One file per task at `.planning/tasks/<epic-id>/<task-id>.md`, YAML frontmatter (`id`, `title`, `status`, `parent`, `deps`, `labels`, `acceptance`) plus a Markdown body (description, then notes). The epic itself is `.planning/tasks/<epic-id>/<epic-id>.md`. Epic IDs are `<repo-name>-<n>`, increasing across `.planning/tasks/`. Child IDs are `<epic-id>.<n>`, increasing within the epic directory, matching the Beads child-ID shape. Paths always resolve to the main checkout (the parent of `git-common-dir`), so every worktree reads and writes the same files.
4. **Closure provenance.** Closing a task records acceptance evidence and closure reason with the same `gin:acceptance-evidence=` and `gin:closure-reason=` note markers the beads provider uses.
5. **CLI.** `gin-workflow task create|show|update|close|reopen|list|ready|blocked|dep add|remember|memories`, with flags and `--json` output keys (`id`, `title`, `status`, `dependencies`, …) covering the subset the skills use today. Under `markdown`, `remember`/`memories` read and write `.planning/memory.md`.
6. **Gates.** `lifecycle_cli.py` derives `implementation_complete` and `shipped` through the configured provider instead of `_beads_json`. Under `beads` the results are identical to today's.
7. **Skills and agents.** Every direct `bd …` instruction in skills and agents becomes `gin-workflow task …`, except Beads-only material: `beads-migration`, `team-setup`, and the shared-Beads parts of `gin-team`.
8. **Concurrency.** Writes take an exclusive lock on `.planning/tasks/.lock`, reusing the `fcntl` lock pattern of `workflow_core/events.py`, and write files with `workflow_core/atomic.py`.
9. **Commits.** The CLI never commits. `orchestrate` commits task files after creating them, and `ship` commits the final task state before integration, both from the main checkout on the epic's feature branch. `execute` does not commit task files.
10. **Setup.** When `bd` is not on `PATH`, `/setup` proposes `task_tracking: markdown` and records it only after the user confirms. If `bd` is present, the default remains `beads`.
11. **Safety hook.** `safety-check.sh` parses the hook payload with `jq` when present, otherwise with `python3`. It errors only when neither is available.

## User Stories

### US-1: Run the workflow without Beads
As a developer whose environment forbids installing `bd`, I want gin-workflow to track tasks as Markdown in my repo, so that I can use the full lifecycle anyway.

Acceptance criteria:
- With `bd` absent, `/setup` proposes `markdown`, and after confirmation discuss → plan → orchestrate → execute → ship completes.
- Task files appear under `.planning/tasks/<epic-id>/` and are committed on the epic branch by orchestrate and ship.
- `gin-workflow state` reports `implementation_complete` once every child task file is `closed`, and `shipped` once the epic is closed.

### US-2: Keep Beads users unaffected
As an existing Beads user, I want nothing to change for me, so that the new mode carries no risk to my workflow.

Acceptance criteria:
- A repository configured with `beads` (or no `task_tracking` entry) behaves as before: same gates, same task IDs, same `bd` data.
- The existing beads provider, end-to-end, and registry tests pass.
- `gin-workflow task <verb>` under `beads` produces the same result as the `bd` command it replaces.

### US-3: Edit tasks by hand safely
As a developer, I want to read and edit task files directly, so that tasks are reviewable in diffs and editable without tools.

Acceptance criteria:
- A hand edit with valid frontmatter is picked up by the next `task show`/`ready`/`state`.
- A malformed file makes `task` commands exit non-zero, naming the file, and gates report unavailable rather than satisfied.

### US-4: Missing jq does not block the shell
As a developer without `jq`, I want the safety hook to keep working, so that I am not blocked from every shell command.

Acceptance criteria:
- With `jq` absent and `python3` present, the hook still parses the payload and still blocks dangerous commands.

## Errors and compatibility

| Case | Behavior |
|---|---|
| Malformed frontmatter or missing `id`/`title` | Command exits non-zero, naming the file. Gates fail closed (unavailable, never satisfied). |
| `dep add` would create a cycle | Rejected; the cycle is printed. |
| Dependency on a nonexistent task | Rejected at `dep add`; treated as blocked by `ready`. |
| Invalid `status` | Rejected through the existing `validate_task_status`. |
| `--workflow-id` with no epic directory | Error "no tasks for epic X". |
| `team.enabled` with `markdown` | `/setup` and `gin-workflow state` report that team mode requires Beads. |
| `markdown` configured but `bd` also installed | `markdown` is used; `bd` is ignored. |

Known risk: during execute, task file changes sit uncommitted in the main checkout until orchestrate/ship commit them. If the main checkout is on `master`, those changes are dirty working-tree files there until the epic branch is checked out to commit them. This is intended, and ship's commit step must handle it.

Compatibility: `task_tracking` defaults to `beads`. No config migration. Existing `.beads/` data is untouched.

## Testing

- **Shared contract tests:** parameterize `tests/workflow_providers/test_task_tracking_compatibility.py` so the same cases (create, dep, ready, close with evidence, reopen) run against beads (fake runner) and markdown (temp directory) with identical results. Add markdown-only cases: malformed file fails closed, cycle rejected, dangling dependency rejected.
- **Beads non-regression:** the existing beads provider, registry, and end-to-end suites run unchanged and pass. Add a test asserting `gin-workflow task <verb>` under beads invokes `bd` with the expected argv.
- **Gates end to end:** extend `tests/workflow_core/test_end_to_end.py` with a markdown run (orchestrate → close all tasks → `implementation_complete` → close epic → `shipped`), next to the existing beads run.
- **CLI:** `--json` output keys match what skills read; `remember`/`memories` round-trip through `.planning/memory.md`.
- **No direct bd:** a test that greps skills and agents for `` `bd `` outside the Beads-only allowlist.
- **Safety hook:** extend `tests/test_safety_check.py` to run with `jq` removed from `PATH`.
- **Setup:** `bd` absent proposes `markdown`; `team.enabled` with `markdown` errors.

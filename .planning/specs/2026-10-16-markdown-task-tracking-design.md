# Markdown task tracking (gin-workflow without Beads)

Status: draft for user review.

## Goal and scope

Some environments cannot install Beads (`bd`). gin-workflow must still run the full lifecycle there. Add a `markdown` task-tracking mode to the same plugin: same skills, same gates, tasks stored as local Markdown files inside the repository directory. Beads stays the default and must keep working exactly as it does today.

This is the solo, local-only half of the work. Task files are not tracked by git, just as Beads' local database is not, so the mode never needs a commit on `master` or a feature branch. Sharing tasks across a team through a dedicated `gin-tasks` git branch is a separate follow-up epic that builds on this store.

In scope:
- A `markdown` task-tracking provider next to the existing `beads` provider.
- A neutral `gin-workflow task <verb>` CLI that skills and agents call instead of `bd`, routed to the configured backend.
- Delivery gates (`implementation_complete`, `shipped`) derived through the configured backend instead of calling `bd` directly.
- `/setup` proposing `markdown` when `bd` is not installed.
- The safety hook falling back to `python3` when `jq` is missing, so a missing `jq` no longer blocks every shell command.

Out of scope:
- A separate `gin-workflow-light` plugin or a reduced skill set.
- Tracking task files in git, and sharing them across machines or teammates (follow-up epic: `gin-tasks` branch plus team mode on markdown).
- Team mode with `markdown` (team mode keeps requiring Beads).
- AI usage tracking (`gin-workflow usage`) with `markdown`; it keeps requiring Beads.
- Migrating tasks between `beads` and `markdown`.
- Windows file locking beyond what the event store supports today (POSIX `fcntl`).

## Requirements

1. **Beads non-regression.** With `task_tracking: beads` (the default), every existing lifecycle behavior, gate result, and test outcome is unchanged. `gin-workflow task <args>` under `beads` runs `bd <args>` with the arguments unchanged and returns its exit code and output. The existing test suites pass unmodified.
2. **Provider.** `MarkdownTaskTrackingProvider` in `workflow_providers/` implements the task-tracking interface (create, read, update, close, dependency, readiness, preflight; `sync` reports unavailable), and `registry.py` registers it under the name `markdown`.
3. **Storage.** One file per task, YAML frontmatter (`id`, `title`, `issue_type`, `status`, `parent`, `deps`, `labels`, `acceptance_criteria`, `close_reason`, …) plus a Markdown body (description, then a `## Notes` section). A task without a parent (an epic, or a standalone task) is `.planning/tasks/<id>/<id>.md`; a child lives in its parent's directory as `<parent-id>.<n>.md`. Top-level IDs are `<repo-name>-<n>` unless `--id` is given; child IDs are `<parent-id>.<n>`, matching the Beads child-ID shape. Paths always resolve to the main checkout (the parent of `git-common-dir`), so every worktree reads and writes the same files.
4. **Local only.** The store writes `.planning/tasks/.gitignore` containing `*` on its first write, so task files are never committed and never make a checkout dirty. Nothing in this mode commits task files.
5. **Closure provenance.** Closing a task through the provider records acceptance evidence and closure reason with the same `gin:acceptance-evidence=` and `gin:closure-reason=` note markers the beads provider uses.
6. **CLI.** `gin-workflow task create|show|update|close|reopen|list|ready|blocked|dep add|dep remove|dep list|config get issue_prefix|remember|memories`, accepting the `bd` flags the skills use today and printing `bd`-shaped JSON with `--json` (`id`, `title`, `status`, `issue_type`, `labels`, `dependencies`, `close_reason`, …). Under `markdown`, `remember`/`memories` use `.planning/tasks/memory.md`.
7. **Gates.** `lifecycle_cli.py` derives `implementation_complete` and `shipped` through the configured backend. Under `beads` the query is the same `bd` call as today.
8. **Skills and agents.** Every direct `bd …` instruction in skills and agents becomes `gin-workflow task …`, except Beads-only material: `beads-migration`, `team-setup`, and `gin-team`.
9. **Concurrency.** Writes take an exclusive lock on `.agent-workflow/runtime/tasks.lock` in the main checkout, reusing `_file_lock` from `workflow_core/events.py`, and write files with `workflow_core/atomic.py`.
10. **Setup.** `gin-workflow setup detect` reports `beads_installed`. When it is false, `/setup` proposes `--set providers.task_tracking=markdown` and records it only after the user confirms. If `bd` is present, the default remains `beads` and setup does not ask.
11. **Safety hook.** `safety-check.sh` parses the hook payload with `jq` when present, otherwise with `python3`. It errors only when neither is available.

## User Stories

### US-1: Run the workflow without Beads
As a developer whose environment forbids installing `bd`, I want gin-workflow to track tasks as Markdown in my repo, so that I can use the full lifecycle anyway.

Acceptance criteria:
- With `bd` absent, `/setup` proposes `markdown`, and after confirmation discuss → plan → orchestrate → execute → ship completes.
- Task files appear under `.planning/tasks/` and `git status` stays clean.
- `gin-workflow state` reports `implementation_complete` once every child task is `closed`, and `shipped` once the epic is closed.
- `/progress` lists open, ready, and blocked tasks from the Markdown files.

### US-2: Keep Beads users unaffected
As an existing Beads user, I want nothing to change for me, so that the new mode carries no risk to my workflow.

Acceptance criteria:
- A repository configured with `beads` (or with no `task_tracking` entry) behaves as before: same gates, same task IDs, same `bd` data.
- The existing test suites pass unmodified.
- `gin-workflow task <args>` under `beads` runs `bd <args>` unchanged and returns its exit code.

### US-3: Edit tasks by hand safely
As a developer, I want to read and edit task files directly, so that I can fix or inspect tasks without tools.

Acceptance criteria:
- A hand edit with valid frontmatter is picked up by the next `task show`/`ready`/`state`.
- A malformed file makes `task` commands exit non-zero, naming the file, and gates report unmet rather than satisfied.

### US-4: Missing jq does not block the shell
As a developer without `jq`, I want the safety hook to keep working, so that I am not blocked from every shell command.

Acceptance criteria:
- With `jq` absent and `python3` present, the hook still parses the payload and still blocks dangerous commands.

## Errors and compatibility

| Case | Behavior |
|---|---|
| Malformed frontmatter, missing `id`/`title`, or unsupported `status` | Command exits 1, naming the file. Gate queries return nothing, so gates stay unmet (fail closed). |
| `dep add` would create a cycle | Rejected; the cycle is printed. |
| `dep add` to itself or to an unknown task | Rejected. |
| Unknown task id | Exit 1, "no such task: <id>". |
| `create --id` of an existing id | Rejected; never overwrites. |
| Team mode (`team` block) with `markdown` | Config validation fails: "team mode requires Beads". |
| `gin-workflow usage` with `markdown` | Error "AI usage tracking requires Beads"; `collect --best-effort` turns it into a warning. |
| `beads` configured but `bd` missing | `gin-workflow task` exits 127 and names the `markdown` option. |
| `markdown` configured and `bd` also installed | `markdown` is used; `bd` is ignored. |

Compatibility: `task_tracking` defaults to `beads`. No config migration. Existing `.beads/` data is untouched. Task data in `markdown` mode lives only on this machine; back it up or move to the follow-up `gin-tasks` mode to share it.

## Testing

- **Store and CLI:** create (epic, child, explicit id), show, update, labels, list filters, ready, blocked, close, reopen, dep add/remove/list, cycle, self and dangling dependency rejection, malformed file failing closed, hand edit, worktree writes to the main checkout, concurrent creates getting distinct ids, `.gitignore` keeping `git status` clean, memory, issue prefix, text output.
- **Provider:** the fake provider's contract scenario (notes, acceptance, dependency, readiness, closure with evidence, idempotent replay) runs against markdown; closed provenance survives a new provider instance; registry selects `markdown`.
- **Beads non-regression:** the existing suites run unchanged. New tests assert `gin-workflow task` under beads calls `bd` with argv unchanged, the gate query calls `bd` exactly as before, and a missing `bd` exits 127 naming the markdown option.
- **Gates end to end:** with `markdown` configured, orchestrate-ready → close all children → `implementation_complete` → close epic → `shipped`, through the real CLI.
- **No direct bd:** a test that greps skills and agents for `` `bd `` outside the Beads-only allowlist.
- **Safety hook:** run the hook with a `PATH` that has no `jq`; it still parses the payload and blocks `--no-verify`.
- **Setup and config:** `detect` reports `beads_installed`; a team block with `markdown` fails validation.

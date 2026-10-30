# Reliability core: state that never lies

Epic: gin-workflow-rm-reliability-core
Status: draft for user review.

## Goal and scope

`state` and `record` distinguish "not done" from "unknown", never hang on a lock, never lose a waiver silently, and a fresh session resumes the track it left in progress.

In scope:
- Tracker failure yields an `unknown` gate value, a `hold` decision, and a warning that names the cause.
- A corrupt event log yields a warning instead of an empty waiver set.
- `file_lock` times out on POSIX as it already does on Windows.
- The `record` guards run inside the event-store lock.
- Events carry `schema_version`; readers ignore unknown fields.
- `state` reads the event log once and queries the tracker once per command.
- `execute` resumes `in_progress` beads first; a SessionStart hook reports them.
- `task close` on a track needs an approved review ledger or an explicit waiver when `project.review_ledger` is on.
- `ship` warns when git hooks are not installed or `verify_commands` is empty.

Out of scope: event-log rotation or compaction; claim lease or TTL (team hardening epic); the `.beads.gate.lock` doc line (process hygiene epic); guarding a direct `bd close` call.

Current behavior this changes (paths under `plugins/gin-workflow/src/scripts/workflow_core/`):
- `tasks.py:135-158` `query()` returns `None` for a missing `bd`, a timeout, a non-zero exit, and bad JSON alike. `lifecycle_cli.py:111-141` reads `None` as "not closed" or "not standalone", so `state` reports `unmet` and `record shipped` says "recordable only for a standalone bead".
- `waivers.py:141-144` returns `{}` when the log cannot be read; one bad JSONL line hides every waiver.
- `locking.py:31-37` takes a blocking `flock` with no timeout; Windows already stops after 60 s.
- `lifecycle_cli.py:161-170` runs the already-shipped and shipped guards before `store.append` takes its lock, so two `record` calls can both pass the guard.
- `schemas.py:268-283` sets `additionalProperties: False` on events and has no `schema_version`.
- One `state` call reads the log 6 to 8 times and runs `bd list --parent` twice.
- `skills/execute/SKILL.md:16` picks only from `task ready`; nothing resumes an `in_progress` bead. `hooks/hooks.json` has no SessionStart hook.
- `tasks.py:196` forwards `task close` to `bd` without checking the review ledger.
- `hooks.py` has no `status` subcommand; `setup_service.py:463` skips the hook check when `verify_commands` is empty, and `hooks run` then exits 0 silently.

## Requirements

### State snapshot and the `unknown` gate value
- `tasks.query_result(root, argv)` returns `(data, cause)`. `cause` is `None` on success, else one of `bd not found`, `bd timed out after <n>s`, `bd exited <code>: <first stderr line>`, `invalid JSON from bd`, `invalid backend config`. `query()` keeps its signature and returns only `data`.
- `_state_command` builds one snapshot per call: the events (or the read error), and the results of `bd list --parent <epic>` and `bd show <epic>`, each run once. Every gate helper and `collect_waivers` takes the snapshot instead of reading the store or calling `bd`.
- Gate values are `satisfied`, `waived(<reason>)`, `unmet`, and the new `unknown`:
  - tracker failure: `implementation_complete` and `shipped` are `unknown`; `requirement_confirmed` and `plan_approved` are `unknown` when they are not recorded and only the standalone-bead check could satisfy them.
  - unreadable event log: every gate is `unknown`.
- When any gate the router evaluates is `unknown`, the decision is `hold` and the remedy names the cause.
- `warnings` gains `tracker unavailable: <cause>` and `event log unreadable: <cause>; waivers not applied`.
- `record shipped` with a tracker failure fails with exit 2 and `tracker unavailable: <cause>`; the standalone-bead message stays for an epic that has children.

### Locking and events
- `file_lock(path, exclusive, timeout=LOCK_TIMEOUT)` polls `LOCK_NB` every 0.05 s on POSIX and raises `TimeoutError` at the deadline. `LOCK_TIMEOUT = 60` replaces `WINDOWS_LOCK_TIMEOUT` for both platforms.
- `WorkflowEventStore.transaction()` holds the exclusive lock, yields the current events, and lets the caller append while it holds the lock. `flock` locks taken through two file descriptors conflict within one process, so `append` inside a transaction must not lock again.
- `_record_command` runs the already-shipped guard, the shipped standalone guard, and the append inside one transaction. The guards' `bd` calls run under the lock; their 30 s timeout stays below `LOCK_TIMEOUT`.
- New events carry `schema_version: 1`. The field is not part of the `event_id` hash, so existing ids are unchanged. The event schema drops `additionalProperties: False` and still requires the existing fields. An event without `schema_version` reads as version 1.

### Resume
- `gin-workflow resume` prints nothing and exits 0 when the main checkout has no `effective-config.yaml`, or when there is no warning and no `in_progress` bead. Otherwise it prints at most 10 lines: the stage of the default workflow, the warnings, and one line per `in_progress` bead as `<id> <title> (<assignee>)`. Its `bd` calls use a 5 s timeout. It exits 0 on every error.
- `hooks/hooks.json` adds a `SessionStart` hook that runs `gin-workflow resume` directly, without a shell.
- `skills/execute/SKILL.md` gains a first step: `gin-workflow task list --status in_progress`, then resume a child of the current epic; in team mode only a bead assigned to the current member. `task ready` is used only when there is nothing to resume. The claim step becomes `gin-workflow task update <id> --claim`.
- The markdown task backend accepts `update --claim` (status `in_progress`, assignee from git `user.email`) and `list --assignee`, so both backends take the flags the skill uses.

### Close guard
- When `project.review_ledger` is true, `gin-workflow task close <id>...` checks every id that has a parent epic before forwarding to the backend. It reads the ledger in-process with `review_ledger.cli.get_review_identity_record`.
  - Approved and terminal: the close proceeds.
  - Otherwise: exit 2 with `<id>: review ledger not approved (<state>); pass --waive-review "<reason>" --actor <id>`, and nothing is closed.
  - `--waive-review <reason> --actor <id>`: appends a `review.waived` event (`task_id` = bead, payload `{reason}`) to the workflow event log, then closes.
- A bead without a parent is not checked. With `project.review_ledger` false, `task close` behaves as today.

### Hook status and ship
- `gin-workflow hooks status` prints `{"hooks": {"pre-commit": "ok|missing|occupied", "pre-push": "..."}, "verify_commands": [...], "ok": <bool>}` and exits 1 when a hook is not `ok` or `verify_commands` is empty, else 0.
- `skills/ship/SKILL.md` step 1 runs `gin-workflow hooks status` and warns, without blocking, when it exits 1. Ship lists the tracks of the epic that carry a `review.waived` event.

### Documentation
- `docs/concepts/lifecycle.md`: resume step, `hold` on `unknown`, close guard, ship warning.
- `docs/concepts/state-model.md`: the `unknown` gate value, `schema_version`, `review.waived`.
- `docs/reference/cli.md`: `resume`, `hooks status`, `task close --waive-review --actor`, `task update --claim`, `task list --assignee` (markdown backend).

## User Stories

### US-1: State says when it does not know
As a developer, I want `gin-workflow state` to say "unknown" with the reason when `bd` fails, so that I never act on a gate that only looks unmet.

Acceptance criteria:
- With `bd` missing from `PATH`, `state` reports `implementation_complete: unknown`, `decision: hold`, and the warning `tracker unavailable: bd not found`.
- With `bd` timing out, the warning names the timeout.
- With `bd` failing, `record shipped` exits 2 with `tracker unavailable: <cause>` and does not mention a standalone bead.
- With `bd` working, gate values and decisions match today's output.

### US-2: A corrupt event log is visible
As a developer, I want a corrupt event log reported, so that waivers are not dropped without notice.

Acceptance criteria:
- With one invalid JSONL line in the log, `state` exits 0, every gate is `unknown`, the decision is `hold`, and the warning `event log unreadable: ...; waivers not applied` is present.

### US-3: Commands never hang on a lock
As a developer, I want every event-store command to stop after a bounded wait, so that a stuck process cannot hang my session.

Acceptance criteria:
- While another process holds the event-log lock, `record` fails with a lock-timeout error after `LOCK_TIMEOUT` instead of blocking.
- Two concurrent `record shipped` calls for the same standalone bead leave exactly one `delivery.shipped` event.
- Two concurrent process-gate records after shipment both refuse with "already shipped".

### US-4: Events can grow fields
As a maintainer, I want events versioned and readers tolerant of new fields, so that a later event change does not make the log unreadable.

Acceptance criteria:
- New events contain `schema_version: 1`; their `event_id` equals the id the same event had before this change.
- A log mixing events without `schema_version` and events with an unknown extra field reads without error.

### US-5: One read per command
As a developer, I want `state` to read the log once and call `bd list --parent` once, so that it stays fast on large logs.

Acceptance criteria:
- One `state` call invokes `WorkflowEventStore.read_all` once and `bd list --parent` at most once.

### US-6: A new session resumes work in progress
As a developer, I want a new session to show and resume the track I left in progress, so that work is not started twice or forgotten.

Acceptance criteria:
- In a repo without `effective-config.yaml`, `gin-workflow resume` prints nothing and exits 0.
- With an `in_progress` bead, `resume` prints its id, title, and assignee in at most 10 lines.
- With `bd` failing, `resume` prints the tracker warning and exits 0.
- `hooks.json` has a `SessionStart` entry that runs `gin-workflow resume`.
- `execute/SKILL.md` resumes an `in_progress` child of the epic before calling `task ready`, and claims with `--claim`.
- On the markdown backend, `task update <id> --claim` sets `in_progress` and the assignee, and `task list --status in_progress --assignee <me>` returns it.

### US-7: A track cannot close unreviewed by accident
As a reviewer, I want `task close` to refuse an unreviewed track when the review ledger is on, so that review is skipped only on purpose and on record.

Acceptance criteria:
- With `project.review_ledger: true` and no approved ledger, `task close <track>` exits 2, names the ledger state, and leaves the bead open.
- With an approved, terminal ledger, the close proceeds.
- With `--waive-review "<reason>" --actor <id>`, a `review.waived` event is recorded and the bead closes.
- A standalone bead, or any bead with `project.review_ledger: false`, closes as today.

### US-8: Ship warns about missing quality gates
As a developer, I want `ship` to warn when git hooks or verify commands are missing, so that I know checks did not run before integration.

Acceptance criteria:
- `gin-workflow hooks status` exits 1 and reports `"ok": false` when a hook is missing or `verify_commands` is empty; it exits 0 when both are in place.
- `ship/SKILL.md` runs `hooks status` and warns without blocking on exit 1, and lists tracks with a `review.waived` event.

## Errors and compatibility

- gin-console reads `gates` as `dict[str, str]` (`gin-console/backend/src/gin_console/projects/models.py:11`); `ProjectCard.tsx:6` renders any value other than `satisfied` or `waived…` as `outline`. `unknown` therefore needs no gin-console change, and reaches it after `install.sh` runs again.
- A gin-workflow install older than this change rejects events with `schema_version`. One install serves a machine and gin-console runs that install, so both upgrade together.
- A lock timeout surfaces as `EventPersistenceError`, which `state` reports as an unreadable log (`unknown`, `hold`) and `record` reports as an error with exit 2.
- `review.waived` is written to the workflow event log with the existing event shape; waivers and gate computation ignore it.
- `resume` never fails a session: every exception is caught and it exits 0.
- A direct `bd close` bypasses the close guard; the docs say so.

## Testing

`python -m unittest` cases, one or more per story:
- US-1: `bd` absent, timing out, and exiting non-zero (stub executable on `PATH`) give `unknown`, `hold`, and the cause; `record shipped` names the cause; a passing `bd` keeps current output.
- US-2: a log with one invalid line gives the warning and `unknown` gates without a traceback.
- US-3: a child process holding the lock makes `file_lock` raise `TimeoutError` with a short test timeout; two processes recording `shipped` leave one event.
- US-4: the `event_id` of a fixed event is unchanged; a mixed log reads.
- US-5: a patched `read_all` and `bd` stub count one call each.
- US-6: `resume` output in the three cases; markdown backend `--claim` and `--assignee`.
- US-7: close refused, approved, and waived, with ledger fixtures.
- US-8: `hooks status` exit codes for missing hook, empty `verify_commands`, and both present.
- Existing suites (`tests/`) stay green; `install_smoke_test` still passes with the new `hooks.json` entry.

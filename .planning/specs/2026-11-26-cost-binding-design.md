# Session binding for the cost view

Epic: gin-workflow-cost-binding
Kind: technical
Points: 3 (one event type written from four commands, one JSON key, two docs pages; the roadmap scored 2 before `gin state` became a writer)
Status: confirmed by the user on 2026-11-26.

## Goal and scope

Nothing ties a Claude Code session to the workflow it worked on. gin 3.4.0 removed usage tracking because it attributed transcript usage to a bead by time span, took about a minute per epic, and missed most of the work (`.planning/knowledge/retire-ai-usage.md`). A cost view needs only the missing link: which sessions belong to which workflow. The transcripts already hold the usage of every request, the skill of every turn, and the type and model of every subagent.

This epic makes every `gin` command that names a workflow record, once, that the current session worked on it. gin-console reads the link through `gin state --format json` and joins it with the transcripts in an epic of its own.

In scope:

- A `session.bound` event in `.agent-workflow/runtime/events.jsonl`.
- The four commands that write it: `gin state`, `gin record`, `gin unblock`, and `gin routes dispatch`.
- A `sessions` key in the output of `gin state --format json`.
- `docs/concepts/state-model.md`, `docs/reference/cli.md`, and the tests.

Out of scope:

- Reading transcripts and computing tokens or cost. That is gin-console's work (PM decision, 2026-11-26).
- A `gin cost` command, budgets, or any check that blocks work.
- Session ids of Codex, OpenCode, Copilot, and Antigravity. The roadmap is Claude Code only.
- The stage of a session. gin-console derives it from the transcript's skill attribution and from the gate events.
- Skill text and the configuration schema. Neither changes.

Assumptions:

- Claude Code sets `CLAUDE_CODE_SESSION_ID` in the subprocesses of its Bash and PowerShell tools and of its hooks. The value is the session id of the transcript and changes after `/clear` (Claude Code documentation, environment variables).
- Checked on 2026-11-26 with Claude Code 2.1.322: the value equals the transcript file name of the session, and the shell of a subagent sees the id of the parent session.
- Subagent transcripts are stored under the parent session, so one binding covers a session and its subagents.
- `.agent-workflow/runtime/` is git-ignored and local to the machine, as the transcripts are. A cost view is therefore per machine.
- A `/gin:quick` run under `default-workflow` stays unbound and counts as work outside an epic.
- A session that serves several workflows gets one event per workflow. gin-console splits such a session by the gate and dispatch events, which carry a workflow id and a time.

## Approach

### Event

The event type is `session.bound`. Its `workflow_id` is the workflow of the command, its `payload` is `{"session_id": "<id>"}`, its `idempotency_key` is `session:<id>`, and it has no `task_id` and no `actor`. It is built with `WorkflowEvent.create` (`plugins/gin-workflow/src/scripts/workflow_core/events.py:98`).

The event id is a hash of the type, the workflow, the key, and the payload (`events.py:35-52`). The same session and workflow therefore give the same id, and the store skips an event whose id it already holds (`events.py:213-216`). A workflow has one `session.bound` event per session, and no code compares bindings.

### One function

A new function, in a module of its own under `workflow_core`, does the whole job:

- It reads `CLAUDE_CODE_SESSION_ID` from the environment.
- It writes nothing when the variable is unset or empty, when the value does not match `[A-Za-z0-9_.-]{1,128}`, or when the workflow is `default-workflow`.
- It appends the event through the event store of the main checkout, under the lock of the store.
- It never changes the result of the command that calls it. When the store cannot be read or written (`EventPersistenceError`, `OSError`), it prints `gin: session not bound: <cause>` on stderr and returns.

### Callers

Four commands call the function with their resolved workflow id:

- `gin state` (`_state_command`, `lifecycle_cli.py:518`)
- `gin record` (`_record_command`, `lifecycle_cli.py:325`)
- `gin unblock` (`_unblock_command`, `lifecycle_cli.py:628`)
- `gin routes dispatch` (`routes.py:116`, which appends `route.dispatched` at `routes.py:240-243`)

`gin routes resolve` and `gin quick-check` do not bind. Resolve runs in the orchestrate session next to `gin record`, and quick-check has no workflow.

### Output

`gin state --format json` adds `sessions`: a list of `{"session_id", "bound_at"}` for the requested workflow, oldest first. `bound_at` is the timestamp of the event. The list is empty when the workflow has no binding, and it includes the binding that the same call wrote. The text format does not change.

gin-console already runs `gin state --workflow-id <epic> --format json` for each epic (`gin-console/backend/src/gin_console/projects/collect.py:156`), so it gets the link from a call it already makes.

### Compatibility

- A gin built before this change reads a log that holds the new event. The schema accepts any non-empty event type (`schemas.py:344`), and readers select the types they know (`lifecycle_cli.py:82-97`).
- The gates of a workflow do not depend on `session.bound`.
- The JSON gains one key. No key is renamed or removed, which the roadmap requires for gin-console.
- The log holds 1,796 events and 0.9 MB in this repository. A new binding rewrites it once, as every append does. A repeated binding writes nothing.

## Risks and rollback

- `gin state` becomes a writer. For a new binding it takes the exclusive lock of the store and can wait up to 60 seconds for it, as `gin record` does. A failed write is a warning and never changes the gates it reports.
- A process started inside a Claude Code session inherits the variable. A gin-console backend started that way would bind that session to every epic it polls. gin-console must drop `CLAUDE_CODE_SESSION_ID` from the environment it gives `gin`. This belongs to its cost view epic. Until that epic nothing reads the bindings.
- Attribution inside a session that serves several workflows is gin-console's job. This epic records which workflows a session touched, not how its turns divide.
- Rollback: revert the commit. Events already written stay in the log, and every reader ignores them.

## Testing

Unit tests under `tests/workflow_core/`:

- Each of the four commands writes one `session.bound` event with the session id when the variable is set and the workflow is explicit.
- A second call with the same session and workflow adds no event. Another session, or another workflow, adds one.
- No event is written when the variable is unset or empty, when its value has other characters, or when the workflow is `default-workflow`.
- `gin state --format json` lists the bindings of the requested workflow in `sessions`, oldest first, including the one the call wrote, and an empty list when there is none.
- A store that cannot be written leaves the output and exit code of `gin state` unchanged, and the warning is printed.
- The gates of a workflow are the same with and without `session.bound` events in the log.

`gin docs check` runs on the two docs pages. The full suite runs once before the push (`verify.run_at: push`).

## Open Technical Questions

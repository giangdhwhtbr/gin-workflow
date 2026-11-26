# Plan: Session binding for the cost view

Epic: gin-workflow-cost-binding
Spec: `.planning/specs/2026-11-26-cost-binding-design.md`

## Objective

Every `gin` command that names a workflow records, once, that the running Claude Code session worked on it: a `session.bound` event in `.agent-workflow/runtime/events.jsonl`, written by `gin state`, `gin record`, `gin unblock`, and `gin routes dispatch`. `gin state --format json` lists the bindings of the workflow as `sessions`. gin-console reads that key in an epic of its own.

## Global Constraints

Copied from the spec:

- Claude Code sets `CLAUDE_CODE_SESSION_ID` in the subprocesses of its Bash and PowerShell tools and of its hooks. The value is the session id of the transcript and changes after `/clear`.
- Subagent transcripts are stored under the parent session, so one binding covers a session and its subagents.
- `.agent-workflow/runtime/` is git-ignored and local to the machine, as the transcripts are.
- A `/gin:quick` run under `default-workflow` stays unbound and counts as work outside an epic.
- A session that serves several workflows gets one event per workflow.
- Out of scope: reading transcripts and computing tokens or cost; a `gin cost` command, budgets, or any check that blocks work; session ids of Codex, OpenCode, Copilot, and Antigravity; the stage of a session; skill text and the configuration schema.
- The binding never changes the result of the command that calls it. A store that cannot be read or written is a warning on stderr.
- The JSON gains one key. No key is renamed or removed.

## Route Rubric
- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis
- Problem statement: nothing ties a Claude Code session to the workflow it worked on, so transcript usage cannot be attributed to an epic without the time-span guess that gin 3.4.0 removed (`.planning/knowledge/retire-ai-usage.md`).
- Success criteria: the six test groups of the spec's Testing section pass; `gin docs check` passes on the two docs pages; the existing lifecycle, routes, events, and docs tests stay green.
- Constraints: the Global Constraints above. No stage skill changes, so the stage-chain budgets are untouched.
- Non-goals: see Global Constraints.

## Approach Options
### Option 1: one function, called by the four commands
- Summary: a new module `workflow_core/session_binding.py` holds `binding_event`, `bind_session`, and `bound_sessions`. Each of the four commands calls `bind_session` with its event store and workflow id. `gin state` passes the events it already read, so a binding that exists costs no lock and no second read.
- Pros: one place for the rules; `gin state` adds no I/O on its normal path; the store's own duplicate check makes the write idempotent.
- Cons: four call sites.

### Option 2: bind inside `WorkflowEventStore.append`
- Summary: every appended event also ensures a binding for its workflow.
- Pros: no call site in the writers.
- Cons: `checks.passed` events carry a constant workflow id, so the store would need a list of event types; `gin state` appends nothing and still needs its own call; the store would read the environment.

### Recommended Approach
- Selected option: Option 1, the design confirmed in discuss.
- Rationale: the rules sit in one function with no knowledge inside the store, and `gin state` stays a reader whenever the binding already exists.

Decisions this plan takes against the spec text, for the user to confirm with the plan:
- `bind_session` also catches `ValueError`, as `_read_events` does (`lifecycle_cli.py:68-72`). The spec named `EventPersistenceError` and `OSError`.
- `gin state` does not write to a log it could not read: it binds only when `_read_events` returned events.
- The dispatch test lives in `tests/workflow_core/test_routes_cli.py`, which owns the manifest fixture. The other tests are in a new `tests/workflow_core/test_session_binding.py`.
- `docs/changelog.md` is not edited: the changelog is written at release time.

## Scope
- In scope: `workflow_core/session_binding.py` (new), `workflow_core/lifecycle_cli.py`, `workflow_core/routes.py`, `tests/workflow_core/test_session_binding.py` (new), `tests/workflow_core/test_routes_cli.py`, `docs/concepts/state-model.md`, `docs/reference/cli.md`.
- Out of scope: `docs/changelog.md`; `plugins/gin-workflow/dist/` (built by `install.sh`, not tracked); every skill and reference file; gin-console.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: One track on one branch; the module, its four callers, and the docs form one reviewable change.
```

## Tasks

### Track 1: `session.bound` from the four commands and `sessions` in `gin state`
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/session_binding.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:23` (import)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:419-420` (`_record_command` binds after its transaction)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:531` (`_state_command` binds after it read the events)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:616-621` (`sessions` key)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:659` (`_unblock_command`, cleared blocker)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:701` (`_unblock_command`, waiver)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/routes.py:25` (import)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/routes.py:255` (`dispatch` binds after `route.dispatched`)
  - Modify `docs/concepts/state-model.md:34` (the event and its writers)
  - Modify `docs/reference/cli.md:63-65` (`gin state`: the binding and the `sessions` key)
  - Create `tests/workflow_core/test_session_binding.py`
  - Test `tests/workflow_core/test_routes_cli.py`
  - Test `tests/workflow_core/test_lifecycle_cli.py`
- **Interfaces**:
  - Produced: `session_binding.binding_event(workflow_id: str, environ: Mapping[str, str] | None = None) -> WorkflowEvent | None`; `session_binding.bind_session(store: WorkflowEventStore, workflow_id: str, events: Sequence[WorkflowEvent] | None = None) -> WorkflowEvent | None`; `session_binding.bound_sessions(events: Iterable[WorkflowEvent], workflow_id: str) -> list[dict[str, str]]`; the constants `EVENT_TYPE = "session.bound"`, `SESSION_VARIABLE = "CLAUDE_CODE_SESSION_ID"`, `UNBOUND_WORKFLOW = "default-workflow"`; the key `sessions` in `gin state --format json`.
  - Consumed: `events.WorkflowEvent.create`, `events.WorkflowEventStore.append`, `events.EventPersistenceError`, `lifecycle_cli._get_event_store`, `lifecycle_cli._read_events`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change to two modules of one package with the code given below; the edge cases are listed in the spec and each has a test.
- **Acceptance criteria**: the tests of step 1 pass; `python3 -m pytest tests/workflow_core/test_session_binding.py tests/workflow_core/test_lifecycle_cli.py tests/workflow_core/test_routes_cli.py tests/workflow_core/test_events.py tests/workflow_core/test_docs_coverage.py -q -n auto` reports no failure; `gin docs check docs/concepts/state-model.md docs/reference/cli.md` prints `ok`; no file outside the list above changes.
- **Estimated complexity**: medium

Steps:

1. Write the failing tests.

   Create `tests/workflow_core/test_session_binding.py`:

   ```python
   """`session.bound`: gin records once which Claude Code session worked on which workflow."""

   from __future__ import annotations

   import contextlib
   import io
   import json
   import os
   from pathlib import Path
   import sys
   import tempfile
   import unittest
   from unittest import mock

   SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
   sys.path.insert(0, str(SCRIPTS))

   from workflow_core import session_binding  # noqa: E402
   from workflow_core.events import WorkflowEventStore  # noqa: E402
   from workflow_core.lifecycle_cli import main as lifecycle_main  # noqa: E402

   SESSION = "0a1b2c3d-1111-2222-3333-444455556666"


   def session(value=SESSION):
       """The environment of a command run by a Claude Code session; None removes the variable."""
       env = {key: item for key, item in os.environ.items() if key != session_binding.SESSION_VARIABLE}
       if value is not None:
           env[session_binding.SESSION_VARIABLE] = value
       return mock.patch.dict(os.environ, env, clear=True)


   class SessionBindingTests(unittest.TestCase):
       def setUp(self):
           directory = tempfile.TemporaryDirectory()
           self.addCleanup(directory.cleanup)
           self.root = Path(directory.name)
           (self.root / ".agent-workflow").mkdir()
           (self.root / ".agent-workflow/config.yaml").write_text("schema_version: '2.3'\n", encoding="utf-8")
           self.log = self.root / ".agent-workflow/runtime/events.jsonl"

       def bindings(self):
           events = WorkflowEventStore(self.log).read_all() if self.log.is_file() else []
           return [(event.workflow_id, event.payload["session_id"]) for event in events
                   if event.event_type == "session.bound"]

       def run_cli(self, *argv):
           out, err = io.StringIO(), io.StringIO()
           with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
               code = lifecycle_main([argv[0], "--repository", str(self.root), *argv[1:]])
           return code, out.getvalue(), err.getvalue()

       def state(self, *argv):
           code, out, err = self.run_cli("state", "--format", "json", *argv)
           return code, json.loads(out), err

       def test_state_binds_the_session_once_and_lists_it(self):
           with session():
               code, payload, _ = self.state("--workflow-id", "wf-1")
               again = self.state("--workflow-id", "wf-1")[1]
           self.assertEqual(0, code)
           self.assertEqual([("wf-1", SESSION)], self.bindings())
           self.assertEqual([SESSION], [row["session_id"] for row in payload["sessions"]])
           self.assertTrue(payload["sessions"][0]["bound_at"])
           self.assertEqual(payload["sessions"], again["sessions"])

       def test_another_session_or_workflow_adds_a_binding(self):
           with session():
               self.state("--workflow-id", "wf-1")
               self.state("--workflow-id", "wf-2")
           with session("second-session"):
               payload = self.state("--workflow-id", "wf-1")[1]
           self.assertEqual([("wf-1", SESSION), ("wf-2", SESSION), ("wf-1", "second-session")], self.bindings())
           self.assertEqual([SESSION, "second-session"], [row["session_id"] for row in payload["sessions"]])

       def test_nothing_is_bound_without_a_usable_session_or_an_explicit_workflow(self):
           named = ("--workflow-id", "wf-1")
           for value, argv in ((None, named), ("", named), ("bad id; rm", named), ("x" * 129, named),
                               (SESSION, ()), (SESSION, ("--workflow-id", "default-workflow"))):
               with self.subTest(value=value, argv=argv), session(value):
                   payload = self.state(*argv)[1]
                   self.assertEqual([], self.bindings())
                   self.assertEqual([], payload["sessions"])

       def test_record_and_unblock_bind_the_session(self):
           with session():
               self.assertEqual(0, self.run_cli("record", "requirement-confirmed", "--workflow-id", "wf-r",
                                                "--evidence", ".planning/specs/x.md", "--actor", "user")[0])
               self.assertEqual(0, self.run_cli("unblock", "--workflow-id", "wf-u", "--gate",
                                                "requirement_confirmed", "--reason", "hotfix", "--actor", "user")[0])
               self.assertEqual(0, self.run_cli("unblock", "--workflow-id", "wf-b", "--clear-blocker",
                                                "--reason", "done", "--actor", "user")[0])
           self.assertEqual([("wf-r", SESSION), ("wf-u", SESSION), ("wf-b", SESSION)], self.bindings())

       def test_a_failed_write_warns_and_leaves_state_unchanged(self):
           with session(None):
               expected = self.state("--workflow-id", "wf-1")[:2]
           with session(), mock.patch.object(WorkflowEventStore, "append", side_effect=OSError("read-only")):
               code, payload, err = self.state("--workflow-id", "wf-1")
           self.assertEqual(expected, (code, payload))
           self.assertIn("gin: session not bound: read-only", err)
           self.assertEqual([], self.bindings())

       def test_an_unreadable_log_is_not_written_to(self):
           self.log.parent.mkdir(parents=True)
           self.log.write_text("not json\n", encoding="utf-8")
           with session():
               payload = self.state("--workflow-id", "wf-1")[1]
           self.assertEqual("not json\n", self.log.read_text(encoding="utf-8"))
           self.assertEqual([], payload["sessions"])

       def test_gates_are_the_same_with_a_binding_in_the_log(self):
           with session(None):
               before = self.state("--workflow-id", "wf-1")[1]["gates"]
           with session():
               after = self.state("--workflow-id", "wf-1")[1]["gates"]
           self.assertEqual([("wf-1", SESSION)], self.bindings())
           self.assertEqual(before, after)


   if __name__ == "__main__":
       unittest.main()
   ```

   In `tests/workflow_core/test_routes_cli.py`, class `TestRoutesCLI`, after `test_dispatch_prints_route_and_appends_dispatched_event`:

   ```python
       def test_dispatch_binds_the_claude_code_session_to_the_workflow(self):
           import os
           entry = {
               "task_id": "t1",
               "requested": {"provider_role": "backend", "model": "sonnet", "effort": "medium"},
               "resolved": {"provider": "claude", "model": "sonnet", "effort": "medium", "selection_mode": "explicit"},
               "fallback": [],
               "escalations": [],
           }
           self._write_manifest("wf-bind", [entry])
           argv = ["dispatch", "--workflow-id", "wf-bind", "--task-id", "t1", "--repository", str(self.root), "--json"]
           with patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": "session-a"}), patch("sys.stdout", io.StringIO()):
               self.assertEqual(0, routes.main(argv))
               self.assertEqual(0, routes.main(argv))
           events_file = self.root / ".agent-workflow/runtime/events.jsonl"
           events = [json.loads(line) for line in events_file.read_text(encoding="utf-8").splitlines() if line.strip()]
           bound = [event for event in events if event["event_type"] == "session.bound"]
           self.assertEqual([("wf-bind", {"session_id": "session-a"})],
                            [(event["workflow_id"], event["payload"]) for event in bound])
   ```

2. Run them and watch them fail.

   Run: `python3 -m pytest tests/workflow_core/test_session_binding.py tests/workflow_core/test_routes_cli.py -q -k "binding or binds or Session"`
   Expected: an import error for `workflow_core.session_binding` in the new file, and one failure in `test_routes_cli.py` (no `session.bound` event).

3. Create `plugins/gin-workflow/src/scripts/workflow_core/session_binding.py`:

   ```python
   """Tie the running Claude Code session to a workflow: one `session.bound` event per session and workflow."""

   from __future__ import annotations

   from collections.abc import Iterable, Mapping, Sequence
   import os
   import re
   import sys

   from .events import EventPersistenceError, WorkflowEvent, WorkflowEventStore

   EVENT_TYPE = "session.bound"
   SESSION_VARIABLE = "CLAUDE_CODE_SESSION_ID"
   UNBOUND_WORKFLOW = "default-workflow"
   _SESSION_ID = re.compile(r"[A-Za-z0-9_.-]{1,128}")


   def binding_event(workflow_id: str, environ: Mapping[str, str] | None = None) -> WorkflowEvent | None:
       """The event that binds the session named by the environment to `workflow_id`.

       None when there is nothing to bind: no session id, an id with other characters, or the default workflow."""
       session_id = (os.environ if environ is None else environ).get(SESSION_VARIABLE, "")
       if workflow_id == UNBOUND_WORKFLOW or not _SESSION_ID.fullmatch(session_id):
           return None
       return WorkflowEvent.create(event_type=EVENT_TYPE, workflow_id=workflow_id,
                                   payload={"session_id": session_id}, idempotency_key=f"session:{session_id}")


   def bind_session(store: WorkflowEventStore, workflow_id: str,
                    events: Sequence[WorkflowEvent] | None = None) -> WorkflowEvent | None:
       """Record once that the running session worked on `workflow_id`; the event when this call wrote it.

       `events` is the log as the caller already read it: a binding found there costs no lock and no write.
       The binding is bookkeeping, so a store that cannot be read or written is reported on stderr, never raised."""
       event = binding_event(workflow_id)
       if event is None or any(item.event_id == event.event_id for item in events or ()):
           return None
       try:
           return event if store.append(event) else None
       except (EventPersistenceError, OSError, ValueError) as error:
           print(f"gin: session not bound: {error}", file=sys.stderr)
           return None


   def bound_sessions(events: Iterable[WorkflowEvent], workflow_id: str) -> list[dict[str, str]]:
       """The `sessions` key of `gin state`: the bindings of `workflow_id` in log order, oldest first."""
       return [{"session_id": str(event.payload.get("session_id", "")), "bound_at": event.timestamp}
               for event in events if event.workflow_id == workflow_id and event.event_type == EVENT_TYPE]
   ```

4. Call it from the three lifecycle commands, in `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py`.

   After line 23 (`from .events import EventPersistenceError, WorkflowEvent, WorkflowEventStore`):

   ```python
   from .session_binding import bind_session, bound_sessions
   ```

   In `_state_command`, right after `events, log_error = _read_events(event_store)` (line 531):

   ```python
       if events is not None:
           bound = bind_session(event_store, workflow_id, events)
           if bound is not None:
               events = [*events, bound]
   ```

   In the payload dict of `_state_command`, after the `"review_waivers": [...]` entry (it ends at line 620) and before the closing brace:

   ```python
           "sessions": bound_sessions(events or (), workflow_id),
   ```

   In `_record_command`, between the `except (EventPersistenceError, RuntimeError, OSError) as error:` block (lines 418-419) and `warning = None` (line 420). It runs after the transaction has released the lock, because the store's lock is not re-entrant:

   ```python
       bind_session(store, args.workflow_id)
   ```

   In `_unblock_command`, after each of its two `event_store.append(event)` calls (lines 659 and 701), with the indentation of that call:

   ```python
           bind_session(event_store, workflow_id)
   ```

   Run: `python3 -m pytest tests/workflow_core/test_session_binding.py -q`
   Expected: `7 passed`.

5. Call it from dispatch, in `plugins/gin-workflow/src/scripts/workflow_core/routes.py`.

   After line 25 (`from .events import WorkflowEvent, WorkflowEventStore`):

   ```python
   from .session_binding import bind_session
   ```

   After `store.append(event)` (line 255), with the same indentation:

   ```python
       bind_session(store, workflow_id)
   ```

   Run: `python3 -m pytest tests/workflow_core/test_routes_cli.py -q -k dispatch`
   Expected: every selected test passes, the new one included.

6. Document it.

   In `docs/concepts/state-model.md`, line 34, replace

   `` and `review.waived` (written by `task close --waive-review`). Events are append-only ``

   with

   `` and `review.waived` (written by `task close --waive-review`). `gin state`, `record`, `unblock`, and `routes dispatch` also append `session.bound`, once per Claude Code session and workflow ([`gin state`](../reference/cli.md#gin-state)). Events are append-only ``

   In `docs/reference/cli.md`, after the paragraph that starts `A gate reads `unknown`` (line 65), add this paragraph:

   ```markdown
   Inside a Claude Code session, `state` also records which session worked on the workflow. It reads `CLAUDE_CODE_SESSION_ID`, which Claude Code sets for the commands it runs, and appends one `session.bound` event per session and workflow to the event log. `gin record`, `gin unblock`, and `gin routes dispatch` do the same. Nothing is recorded for `default-workflow`, without the variable, or when its value has a character other than a letter, a digit, `_`, `.`, or `-`. JSON lists the bindings of the workflow as `sessions` (`session_id`, `bound_at`), oldest first. A binding that cannot be written prints `gin: session not bound: <cause>` on stderr and changes neither the output nor the exit code.
   ```

   Run: `gin docs check docs/concepts/state-model.md docs/reference/cli.md`
   Expected: `ok`.

7. Run the tests of the changed code.

   Run: `python3 -m pytest tests/workflow_core/test_session_binding.py tests/workflow_core/test_lifecycle_cli.py tests/workflow_core/test_routes_cli.py tests/workflow_core/test_events.py tests/workflow_core/test_docs_coverage.py -q -n auto`
   Expected: no failure. A test in `test_lifecycle_cli.py` that compares the whole JSON of `gin state` with a fixed dict gains the key `"sessions": []`; update only such a comparison.

8. Commit on `feat/cost-binding`:

   ```bash
   git add plugins/gin-workflow/src/scripts/workflow_core/session_binding.py plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py plugins/gin-workflow/src/scripts/workflow_core/routes.py tests/workflow_core/test_session_binding.py tests/workflow_core/test_routes_cli.py docs/concepts/state-model.md docs/reference/cli.md
   git commit -m "feat(state): record which Claude Code session worked on a workflow (gin-workflow-cost-binding)"
   ```

## Integration
- **Branch**: `feat/cost-binding`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest tests/workflow_core/test_session_binding.py tests/workflow_core/test_lifecycle_cli.py tests/workflow_core/test_routes_cli.py tests/workflow_core/test_events.py tests/workflow_core/test_docs_coverage.py -q -n auto` passes
- [ ] `gin docs check docs/concepts/state-model.md docs/reference/cli.md` prints `ok`
- [ ] The full suite passes once at ship (`verify.run_at: push`)
- [ ] Manual: in a Claude Code session, `gin state --format json --workflow-id gin-workflow-cost-binding` lists the session under `sessions`, and a second call adds no line to `.agent-workflow/runtime/events.jsonl`

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- The track bead closes after its tests and review pass. The epic stays open until the merge is confirmed.
- gin-console must drop `CLAUDE_CODE_SESSION_ID` from the environment it gives `gin`; that belongs to its cost view epic (spec, Risks and rollback).

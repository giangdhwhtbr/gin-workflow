# Plan: Fresh context per stage with a state card

Epic: gin-workflow-context-boundaries
Spec: `.planning/specs/2026-11-28-context-boundaries-design.md`

## Objective

`gin prime` prints a state card of at most 9,500 characters: the workflow, its stage and gates, the spec and plan, the ready tracks, the open questions, review cycles, the next command, the other open workflows, team lines in team mode, and the Beads memories. The Claude Code hooks file runs it on `startup`, `resume`, `clear`, and `compact`, and runs `gin prime --pre-compact` before a compaction, on Linux, macOS, and Windows. Each stage ends with `Next: /clear, then <command>`. `/gin:setup` offers `autoCompactWindow: 200000`. `session.bound` events carry `cwd`, so a cleared session finds the workflow last worked on in its folder.

## Global Constraints

Copied from the spec:

- Platform check: Claude Code already re-injects the project CLAUDE.md, auto memory, and invoked skill bodies after compaction, and it adds a `SessionStart` hook's stdout to the context. It shows no workflow state of its own. Its `PreCompact` hook stdout becomes instructions for the compaction summary, and `autoCompactWindow` sets the compaction point. This epic writes the glue to those features.
- Out of scope: the stage preflight and mode text (`gin-workflow-stage-brief`); moving to the next stage without a typed command (`gin-workflow-one-entry`); a status line or pane; hooks for the Codex, Copilot, Antigravity, and OpenCode builds.
- `gin prime` replaces `bd prime` at session start. The card carries the Beads memories, trimmed to fit the output cap, and one line that points to `bd prime --no-memories` for the Beads command reference. gin installs no Beads hook, and `bd setup claude` is not needed beside it. `bd prime` prints 13,961 characters in this repository (memories 8,246), above Claude Code's 10,000-character cap for hook output.
- A session that is not bound to a workflow gets the workflow bound most recently in the same folder (the git top level).
- In team mode the card asks the host for the waiting pull requests, within a time cap.
- The card is computed when asked, on a lean read path; it is not cached.
- Errors and compatibility: a failed or timed-out Beads call marks only its line `unknown (<cause>)`; the hook still exits 0. A missing `gin`, a version pin refusal, or a folder without gin configuration prints nothing. If Claude Code drops a hook that runs past its timeout, the session starts without a card; nothing else changes. `gin state --format json` keeps every key; gin-console reads nothing new. The `cwd` key on `session.bound` is additive; an older gin reads the event log unchanged. Team mode, workspaces, and the SDD layout keep working; no mode is frozen or removed.

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
- Problem statement: the main session holds 81% of prompt tokens at a median context of 293K. `/clear` between stages is a convention, and nothing shows the workflow state after a start, clear, resume, or compaction, so sessions stay long.
- Success criteria: the tests of the spec's Testing section pass; `python3 -m pytest -n auto` passes; `bash tests/install_smoke_test.sh` passes; `gin docs check` passes on every changed page; the ship note records the card size, the `gin prime --hook` time before and after (target under 3 s), the median main-session context against the 293K baseline, and the team-project check of requirement 20.
- Constraints: the Global Constraints above. Every stage chain stays within its 12,000-character cap (quick: 8,000) without changing a cap or its test; measured on master today: plan 11,846, ship 11,827, discuss 11,549.
- Non-goals: see Global Constraints.

## Approach Options

### Option 1: one `gin prime` module that reuses the `gin state` computation
- Summary: extract the body of `_state_command` into `state_payload(..., bind=False, warnings=False)`; `prime.py` resolves the workflow from the event log, runs `state_payload` and the card's own Beads calls one after another on one daemon thread within one time budget, and renders the card under the size cap.
- Pros: the card's gates equal `gin state`'s, team shared gates included (requirement 19), with no second gate model; no cache to go stale; the hook adds no Python dependency.
- Cons: a card costs about two rounds of Beads calls (0.7–2.7 s each here); the 3-second target is measured, not enforced.

### Option 2: a cache written by every `gin state` and `gin record`, read by the hook
- Summary: write the card to `.agent-workflow/runtime/card.json` on each state change; the hook prints the file.
- Pros: the hook is fast.
- Cons: the spec decided against a cache; a card goes stale when a bead closes outside gin; team gates written by a teammate are missed.

### Recommended Approach
- Selected option: Option 1.
- Rationale: the spec decided on a computed card on a lean read path. Two decisions made in this plan:
  - Shipped (requirements 2.3 and 2.4, user's choice on 2026-11-28, written into the spec): a workflow is shipped when it has a `delivery.shipped` event or the epic of its `orchestration.ready` event is closed. One `bd show <epic> <epic> ...` call checks every candidate.
  - `Other open workflows:` shows the stage the local event log gives (`discuss`, `plan`, `orchestrate`, or `execute or ship`), not a full `gin state` per workflow: a full state costs two Beads calls per workflow and would double the hook time. The card's own workflow and the no-workflow list use the full state.

## Scope
- In scope: requirements 1–20 of the spec.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: worker
  workers:
    mode: parallel
  rationale: Tracks 1, 5, and 6 touch disjoint files and start together; tracks 2, 3, and 4 build `prime.py` in sequence after track 1; track 7 documents the result last.
```

## Change during execute (2026-11-28, user decision)

Concurrent `bd` calls in one repository finish later than the same calls in a row (track 2 trace: 4 calls ended about 7.5 s after start against 5.1 s serially), so the card hit its 8 s round and lines read `unknown` on about half the runs. Spec requirement 6 now reads: the Beads calls run one after another in one background job within one budget, most important line first, and the kind comes from the spec's `Kind:` line without a Beads call when the spec has one. For the code below this means:

- `bounded(jobs, timeout)` keeps its signature but runs the jobs in dict order on one daemon thread; a job not finished when the budget ends reads `timed out after <budget>s`. Jobs are listed in priority order: `state`, `ready`, `shipped`, then track 3's `comments`, `cycles`, and `memories`.
- `ROUND_TIMEOUT` is 10 s; the folder check before the round keeps `CALL_TIMEOUT` (4 s), so the worst case is 14 s, under the hook's 15 s.
- Track 3: `memories` is the last job of the round (both card forms), not a separate `_Background` in `render`; `tq` reads a local file and stays a job of the round.
- Track 4: the host call (`team_pending`) still runs beside the round on its own `_Background` with `TEAM_TIMEOUT`; the member and lane jobs, which call Beads, join the round just before `memories`.

## Tasks

### Track 1: `session.bound` records the folder
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/session_binding.py:1-48` (add `is_session_id`, `folder_key`, the `cwd` key, `start=` parameters, one `sessions` entry per session)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:465,579,718,761` (pass `start=` to `bind_session`)
  - Modify `docs/reference/cli.md:67` (the `cwd` key)
  - Modify `docs/concepts/state-model.md:34` (the `cwd` key)
  - Test `tests/workflow_core/test_session_binding.py`
- **Interfaces**:
  - Produces `session_binding.is_session_id(value: str) -> bool`.
  - Produces `session_binding.folder_key(start: Path | None = None) -> str`: the resolved git top level of `start` (default: the current directory), else `start` resolved.
  - Changes `binding_event(workflow_id, environ=None, *, start: Path | None = None)` and `bind_session(store, workflow_id, events=None, *, start: Path | None = None)`; the payload is `{"session_id": ..., "cwd": folder_key(start)}`.
  - `bound_sessions(events, workflow_id)` returns one entry per `session_id`, at its first binding.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one small module and four call sites, with an event-id subtlety (the id covers the payload, so `sessions` must deduplicate); code given below.
- **Acceptance criteria**: the three new tests and `python3 -m pytest tests/workflow_core/test_session_binding.py tests/workflow_core/test_lifecycle_cli.py -q` pass; `gin docs check docs/reference/cli.md docs/concepts/state-model.md` prints `ok`.
- **Estimated complexity**: low

Steps:

1. Add the failing tests to `tests/workflow_core/test_session_binding.py`, inside `SessionBindingTests` (add `import shutil`, `import subprocess`, and `from workflow_core.events import WorkflowEvent` at the top):

```python
    def test_binding_records_the_folder_it_ran_in(self):
        with session():
            self.state("--workflow-id", "wf-1")
        bound = [event for event in WorkflowEventStore(self.log).read_all() if event.event_type == "session.bound"]
        self.assertEqual(str(self.root.resolve()), bound[0].payload["cwd"])

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_the_folder_is_the_git_top_level(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        inner = self.root / "a/b"
        inner.mkdir(parents=True)
        self.assertEqual(str(self.root.resolve()), session_binding.folder_key(inner))

    def test_a_session_bound_before_the_cwd_key_is_listed_once(self):
        old = WorkflowEvent.create(event_type="session.bound", workflow_id="wf-1",
                                   payload={"session_id": SESSION}, idempotency_key=f"session:{SESSION}")
        self.log.parent.mkdir(parents=True, exist_ok=True)
        WorkflowEventStore(self.log).append(old)
        with session():
            _, payload, _ = self.state("--workflow-id", "wf-1")
        self.assertEqual([("wf-1", SESSION), ("wf-1", SESSION)], self.bindings())
        self.assertEqual([{"session_id": SESSION, "bound_at": old.timestamp}], payload["sessions"])
```

2. Run `python3 -m pytest tests/workflow_core/test_session_binding.py -q`. Expected: the three tests fail (`KeyError: 'cwd'`, `AttributeError: ... folder_key`, two `sessions` entries).

3. In `session_binding.py`, add `from pathlib import Path` and `import subprocess` to the imports, then replace `binding_event`, `bind_session`, and `bound_sessions` and add the two helpers:

```python
def is_session_id(value: str) -> bool:
    """True for a Claude Code session id gin records: 1 to 128 letters, digits, `_`, `.`, or `-`."""
    return bool(_SESSION_ID.fullmatch(value or ""))


def folder_key(start: Path | None = None) -> str:
    """The folder a binding names: the git top level of `start` (default: the current directory), else `start`."""
    path = Path(start or Path.cwd()).resolve()
    try:
        done = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path, capture_output=True, text=True,
                              timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return str(path)
    top = done.stdout.strip()
    return str(Path(top).resolve()) if done.returncode == 0 and top else str(path)


def binding_event(workflow_id: str, environ: Mapping[str, str] | None = None, *,
                  start: Path | None = None) -> WorkflowEvent | None:
    """The event that binds the session named by the environment to `workflow_id`, made in the folder of `start`.

    None when there is nothing to bind: no session id, an id with other characters, or the default workflow."""
    session_id = (os.environ if environ is None else environ).get(SESSION_VARIABLE, "")
    if workflow_id == UNBOUND_WORKFLOW or not is_session_id(session_id):
        return None
    return WorkflowEvent.create(event_type=EVENT_TYPE, workflow_id=workflow_id,
                                payload={"session_id": session_id, "cwd": folder_key(start)},
                                idempotency_key=f"session:{session_id}")


def bind_session(store: WorkflowEventStore, workflow_id: str,
                 events: Sequence[WorkflowEvent] | None = None, *, start: Path | None = None) -> WorkflowEvent | None:
    """Record once per folder that the running session worked on `workflow_id`; the event when this call wrote it.

    `events` is the log as the caller already read it: a binding found there costs no lock and no write.
    The binding is bookkeeping, so a store that cannot be read or written is reported on stderr, never raised."""
    event = binding_event(workflow_id, start=start)
    if event is None or any(item.event_id == event.event_id for item in events or ()):
        return None
    try:
        return event if store.append(event) else None
    except (EventPersistenceError, OSError, ValueError) as error:
        print(f"gin: session not bound: {error}", file=sys.stderr)
        return None


def bound_sessions(events: Iterable[WorkflowEvent], workflow_id: str) -> list[dict[str, str]]:
    """The `sessions` key of `gin state`: one entry per session of `workflow_id`, at its first binding, oldest first.
    A session bound from two folders, or before `cwd` was recorded, has several events."""
    first: dict[str, dict[str, str]] = {}
    for event in events:
        if event.workflow_id == workflow_id and event.event_type == EVENT_TYPE:
            session_id = str(event.payload.get("session_id", ""))
            first.setdefault(session_id, {"session_id": session_id, "bound_at": event.timestamp})
    return list(first.values())
```

4. In `lifecycle_cli.py` pass the folder the command ran in: line 465 `bind_session(store, args.workflow_id, start=getattr(args, "start", None))`; line 579 `bound = bind_session(event_store, workflow_id, events, start=getattr(args, "start", None))`; lines 718 and 761 `bind_session(event_store, workflow_id, start=getattr(args, "start", None))`. `routes.py:257` keeps its call: its folder is the current directory.

5. Docs. In `docs/reference/cli.md:67`, after "appends one `session.bound` event per session and workflow to the event log." insert: "Its payload holds `session_id` and `cwd`, the git top level of the folder the command ran in (the folder itself outside git); a session bound from another folder adds one more event. [`gin prime`](#gin-prime) reads `cwd` to find the workflow last worked on in a folder." Change "JSON lists the bindings of the workflow as `sessions` (`session_id`, `bound_at`), oldest first." to "JSON lists the sessions of the workflow as `sessions` (`session_id`, `bound_at` of its first binding), oldest first." In `docs/concepts/state-model.md:34`, change "also append `session.bound`, once per Claude Code session and workflow" to "also append `session.bound` (`session_id`, `cwd`), once per Claude Code session, workflow, and folder".

6. Run `python3 -m pytest tests/workflow_core/test_session_binding.py tests/workflow_core/test_lifecycle_cli.py -q`. Expected: all pass. Run `gin docs check docs/reference/cli.md docs/concepts/state-model.md`. Expected: `ok`. (The `#gin-prime` anchor resolves once track 2 adds the heading; if `docs check` flags it now, keep the link and note it in the bead.)

7. Commit: `gin commit -m "feat(session): session.bound records the folder (gin-workflow-context-boundaries)"` with the five files.

### Track 2: `gin prime` resolves the workflow and prints the core card
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:564-682` (extract `state_payload`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/tasks.py:157-176` (`timeout` parameter)
  - Create `plugins/gin-workflow/src/scripts/workflow_core/prime.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/cli.py:13-16,150-205` (register `prime`)
  - Modify `docs/reference/cli.md:72` (new `## \`gin prime\`` section before `## \`gin record\``)
  - Test `tests/workflow_core/test_prime.py`
- **Interfaces**:
  - Produces `lifecycle_cli.state_payload(repo_path: Path, workflow_id: str, *, start: Path | None = None, scope_hash: str | None = None, bind: bool = True, warnings: bool = True) -> tuple[dict[str, Any], int]`; `_state_command` calls it, so `gin state` output does not change.
  - Produces `tasks.query_result(root, argv, timeout: float = 30) -> tuple[Any, str | None]`.
  - Produces in `prime.py`: `main(argv) -> int`, `bounded(jobs, timeout, timeouts=None) -> dict[str, tuple[Any, str | None]]`, `_Background(job)` with `.result(timeout)`, `query(root, argv) -> Any` (raises `SourceError`), `Context`, `Found`, `resolve`, `recent_workflows`, `folder_workflows`, `local_shipped`, `shipped_among`, `local_stage`, `next_command`, `artifact_paths`, `ready_tracks`, `workflow_lines`, `no_workflow_lines`, `render`, `finish(lines) -> str`, `pre_compact_text`, and the constants `CARD_CAP = 9_500`, `PRE_COMPACT_CAP = 1_500`, `LIST_CAP = 10`, `OPEN_CAP = 5`, `OPEN_DAYS = 14`, `CALL_TIMEOUT = 4.0`, `ROUND_TIMEOUT = 8.0`, `TEXT_CAP = 160`.
  - Consumes `session_binding.folder_key`, `is_session_id`, `EVENT_TYPE`, `SESSION_VARIABLE`, `UNBOUND_WORKFLOW` (track 1); `lifecycle_cli._recorded_epic`, `_process_gate_state`, `_read_events`; `epic_kind.lookup`; `prep.is_prep`; `version_pin.verdict`, `version_pin.message`; `cli.CLI_VERSION`.
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** a cross-module change: it refactors the `gin state` path every stage uses, adds a CLI command under the version pin, and runs Beads calls on threads with timeouts that must never hang the hook.
- **Acceptance criteria**: `python3 -m pytest tests/workflow_core/test_prime.py tests/workflow_core/test_lifecycle_cli.py tests/workflow_core/test_session_binding.py tests/workflow_core/test_docs_coverage.py -q` passes; `gin prime` in this worktree prints a card whose `Gates:` line equals `gin state --format json`'s `gates`; `gin prime --hook < /dev/null` in `/tmp` prints nothing and exits 0.
- **Estimated complexity**: high

Steps:

1. Write `tests/workflow_core/test_prime.py`:

```python
"""`gin prime`: the state card a Claude Code session sees at start, after /clear, on resume, and after compaction."""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from workflow_core import prime
from workflow_core.events import WorkflowEvent, WorkflowEventStore
from workflow_core.session_binding import SESSION_VARIABLE

SESSION = "0a1b2c3d-1111-2222-3333-444455556666"
OTHER = "0a1b2c3d-1111-2222-3333-777788889999"
THIRD = "0a1b2c3d-1111-2222-3333-aaaabbbbcccc"


class PrimeCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        (self.root / ".agent-workflow/runtime").mkdir(parents=True)
        (self.root / ".agent-workflow/config.yaml").write_text("schema_version: '2.3'\n", encoding="utf-8")
        self.log = self.root / ".agent-workflow/runtime/events.jsonl"
        env = {key: value for key, value in os.environ.items() if key != SESSION_VARIABLE}
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def add(self, event_type, workflow_id, payload=None, days_ago=0):
        stamp = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")
        WorkflowEventStore(self.log).append(WorkflowEvent.create(
            event_type=event_type, workflow_id=workflow_id, payload=payload or {}, timestamp=stamp,
            idempotency_key=f"{event_type}:{workflow_id}:{stamp}"))

    def bind(self, workflow_id, session_id, cwd=None):
        self.add("session.bound", workflow_id, {"session_id": session_id, "cwd": cwd or str(self.root)})

    def prime(self, *argv, stdin=""):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(stdin)), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            code = prime.main(["--repository", str(self.root), *argv])
        return code, out.getvalue(), err.getvalue()


class ResolveTests(PrimeCase):
    def test_prints_nothing_outside_a_gin_project(self):
        (self.root / ".agent-workflow/config.yaml").unlink()
        self.assertEqual((0, ""), self.prime("--hook", stdin="{}")[:2])

    def test_the_flag_comes_first(self):
        self.bind("wf-session", SESSION)
        code, out, _ = self.prime("--workflow-id", "wf-flag")
        self.assertEqual(0, code)
        self.assertIn("gin state card (workflow found by: flag)", out)
        self.assertIn("Workflow: wf-flag", out)
        self.assertIn("Next: /gin:discuss wf-flag", out)

    def test_the_hook_input_session_comes_next(self):
        self.bind("wf-folder", OTHER)
        self.bind("wf-session", SESSION, cwd="/elsewhere")
        out = self.prime("--hook", stdin=json.dumps({"session_id": SESSION, "source": "compact"}))[1]
        self.assertIn("workflow found by: this session", out)
        self.assertIn("Workflow: wf-session", out)

    def test_without_hook_the_session_comes_from_the_environment(self):
        self.bind("wf-session", SESSION, cwd="/elsewhere")
        with mock.patch.dict(os.environ, {SESSION_VARIABLE: SESSION}):
            out = self.prime()[1]
        self.assertIn("Workflow: wf-session", out)

    def test_a_cleared_session_gets_the_last_workflow_of_its_folder(self):
        self.bind("wf-old", OTHER)
        self.bind("wf-new", THIRD)
        out = self.prime("--hook", stdin=json.dumps({"session_id": SESSION, "source": "clear"}))[1]
        self.assertIn("workflow found by: last session in this folder", out)
        self.assertIn("Workflow: wf-new", out)

    def test_a_shipped_workflow_is_skipped_and_the_open_ones_are_listed(self):
        self.bind("wf-done", OTHER)
        self.add("delivery.shipped", "wf-done", {"evidence": "abc123"})
        self.add("requirement.confirmed", "wf-open", {"evidence": "spec.md"})
        out = self.prime("--hook", stdin=json.dumps({"session_id": SESSION}))[1]
        self.assertIn("no workflow is bound to this session or this folder", out)
        self.assertIn("  - wf-open: plan, next: /gin:plan wf-open", out)
        self.assertNotIn("wf-done", out)

    def test_a_workflow_whose_epic_is_closed_is_shipped(self):
        self.bind("wf-epic", OTHER)
        self.add("orchestration.ready", "wf-epic", {"epic": "ep-1", "evidence": "plan.md"})

        def answer(root, argv, timeout=30):
            return ([{"id": "ep-1", "status": "closed"}], None) if argv[0] == "show" else ([], None)

        with mock.patch("workflow_core.tasks.query_result", side_effect=answer):
            out = self.prime("--hook", stdin=json.dumps({"session_id": SESSION}))[1]
        self.assertIn("no workflow is bound", out)
        self.assertNotIn("wf-epic", out)

    def test_a_workflow_idle_for_more_than_14_days_is_not_listed(self):
        self.add("requirement.confirmed", "wf-stale", {"evidence": "spec.md"}, days_ago=30)
        out = self.prime("--hook", stdin="{}")[1]
        self.assertIn("Open workflows: none; start one with /gin:discuss", out)

    def test_bad_hook_input_is_ignored(self):
        self.assertEqual(0, self.prime("--hook", stdin="not json")[0])


class CardTests(PrimeCase):
    def test_spec_and_plan_come_from_the_gate_events(self):
        self.add("requirement.confirmed", "wf-1", {"evidence": ".planning/specs/x-design.md"})
        self.add("approval.recorded", "wf-1", {"action": "plan_approved", "decision": {"status": "approved"},
                                               "evidence": ".planning/plans/x.md"})
        out = self.prime("--workflow-id", "wf-1")[1]
        self.assertIn("Spec: .planning/specs/x-design.md", out)
        self.assertIn("Plan: .planning/plans/x.md", out)
        self.assertIn("Gates: requirement_confirmed=satisfied, plan_approved=satisfied, orchestration_ready=unmet", out)
        self.assertIn("Next: /gin:orchestrate wf-1", out)

    def test_next_command(self):
        cases = [
            ({"decision": "route", "stage": "plan"}, [], "/gin:plan wf"),
            ({"decision": "route", "stage": "execute"}, ["t-1", "t-2"], "/gin:execute t-1 t-2"),
            ({"decision": "route", "stage": "execute"}, [], "/gin:workflow wf"),
            ({"decision": "hold", "stage": "progress"}, [], "/gin:workflow wf"),
            ({"decision": "complete", "stage": "progress"}, [], None),
        ]
        for state, ready, expected in cases:
            with self.subTest(state=state, ready=ready):
                self.assertEqual(expected, prime.next_command("wf", state, ready))

    def test_the_card_writes_nothing(self):
        self.bind("wf-1", OTHER)
        before = self.log.read_bytes()
        with mock.patch.dict(os.environ, {SESSION_VARIABLE: SESSION}):
            self.prime("--workflow-id", "wf-2")
        self.assertEqual(before, self.log.read_bytes())

    def test_a_timed_out_state_marks_only_its_lines(self):
        def slow(*args, **kwargs):
            time.sleep(1)
            return {}, 0

        with mock.patch.object(prime, "ROUND_TIMEOUT", 0.1), \
                mock.patch("workflow_core.lifecycle_cli.state_payload", side_effect=slow):
            code, out, _ = self.prime("--workflow-id", "wf-1")
        self.assertEqual(0, code)
        self.assertIn("Stage: unknown (timed out after 0.1s)", out)
        self.assertIn("Workflow: wf-1", out)
        self.assertNotIn("Next:", out)

    def test_a_failed_ready_call_marks_only_its_line(self):
        self.add("orchestration.ready", "wf-1", {"epic": "ep-1", "evidence": "plan.md"})
        with mock.patch("workflow_core.tasks.query_result", return_value=(None, "bd exited 1")):
            out = self.prime("--workflow-id", "wf-1")[1]
        self.assertIn("Ready tracks: unknown (bd exited 1)", out)
        self.assertIn("Workflow: wf-1 (epic ep-1", out)


class HookModeTests(PrimeCase):
    def test_pre_compact_makes_no_beads_call_and_fits(self):
        self.bind("wf-1", SESSION)
        with mock.patch("workflow_core.tasks.query_result", side_effect=AssertionError("no Beads call")), \
                mock.patch.dict(os.environ, {SESSION_VARIABLE: SESSION}):
            code, out, err = self.prime("--pre-compact")
        self.assertEqual((0, ""), (code, err))
        self.assertLessEqual(len(out.rstrip("\n")), prime.PRE_COMPACT_CAP)
        self.assertIn("wf-1", out)
        self.assertIn("word for word", out)

    def test_a_refusing_version_pin_is_silent_in_the_hook_and_an_error_otherwise(self):
        (self.root / ".ginrc").write_text("99.0.0\n", encoding="utf-8")
        self.assertEqual((0, "", ""), self.prime("--hook", stdin="{}"))
        code, out, err = self.prime()
        self.assertEqual((2, ""), (code, out))
        self.assertIn("error:", err)


if __name__ == "__main__":
    unittest.main()
```

2. Run `python3 -m pytest tests/workflow_core/test_prime.py -q`. Expected: collection fails with `ImportError: cannot import name 'prime'`.

3. In `tasks.py`, give `query_result` a timeout: change the signature to `def query_result(root: Path, argv: Sequence[str], timeout: float = 30) -> tuple[Any, str | None]:`, pass `timeout=timeout` to `subprocess.run`, and change the message to `return None, f"bd timed out after {timeout:g}s"` (30 still prints `30s`).

4. In `lifecycle_cli.py`, rename the body of `_state_command` (lines 564-682) into `state_payload` and make `_state_command` call it:

```python
def state_payload(repo_path: Path, workflow_id: str, *, start: Path | None = None, scope_hash: str | None = None,
                  bind: bool = True, warnings: bool = True) -> tuple[dict[str, Any], int]:
    """The payload of `gin state` and its exit code. `gin prime` passes bind=False, because it never writes, and
    warnings=False, which skips the knowledge and learn-comment checks."""
```

   Inside, make exactly these changes to the moved body: drop the first two lines that read `args` (`repo_path = ...`, the `workflow_id = getattr(...)` line); `scope_hash = scope_hash or _resolve_scope_hash(repo_path)`; `if events is not None and bind:` around the `bind_session(..., start=start)` block; in `"warnings"` replace the `_knowledge_warning(...)` item with `(_knowledge_warning(repo_path, config, events, workflow_id, gates_state, epic=warn_epic) if warnings else None)`; `"workspace": workspace.summary(workspace.locate(start or repo_path))`. Then:

```python
def _state_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return state_payload(Path(args.repository).resolve(), getattr(args, "workflow_id", None) or "default-workflow",
                         start=getattr(args, "start", None), scope_hash=getattr(args, "scope_hash", None))
```

5. Create `prime.py`:

```python
"""`gin prime`: the state card Claude Code shows at session start, after `/clear`, on resume, and after compaction.

It reads and never writes: no session binding, no gate, no event."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any, Callable, Mapping, Sequence

from . import epic_kind, lifecycle_cli, tasks
from .checkout import main_checkout
from .events import WorkflowEvent, WorkflowEventStore
from .prep import is_prep
from .session_binding import EVENT_TYPE as BOUND, SESSION_VARIABLE, UNBOUND_WORKFLOW, folder_key, is_session_id

CARD_CAP = 9_500
PRE_COMPACT_CAP = 1_500
LIST_CAP = 10
OPEN_CAP = 5
OPEN_DAYS = 14
CALL_TIMEOUT = 4.0  # one Beads call
ROUND_TIMEOUT = 8.0  # the concurrent sources of one card; with the folder check first, under the hook's 15 s
TEXT_CAP = 160  # one list item, cut with "..." beyond it
_GATE_EVENTS = frozenset({"requirement.confirmed", "approval.recorded", "orchestration.ready"})
_LOCAL_STAGES = (("discuss", "requirement_confirmed"), ("plan", "plan_approved"), ("orchestrate", "orchestration_ready"))
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


class SourceError(Exception):
    """One source of the card failed; only its line reads `unknown (<cause>)`."""


@dataclass(frozen=True)
class Found:
    workflow_id: str | None
    how: str = ""


@dataclass(frozen=True)
class Context:
    root: Path
    start: Path
    events: list[WorkflowEvent]
    settings: Any  # project.ProjectSettings
    team: Any  # team.TeamConfig | None
    beads: bool


class _Background:
    """One job on a daemon thread, joined later. A daemon thread, not an executor: the process exits without
    waiting for a stuck call."""

    def __init__(self, job: Callable[[], Any]):
        self._out: tuple[Any, str | None] | None = None
        self._started = time.monotonic()
        self._thread = threading.Thread(target=self._run, args=(job,), daemon=True)
        self._thread.start()

    def _run(self, job: Callable[[], Any]) -> None:
        try:
            self._out = (job(), None)
        except Exception as error:  # broad on purpose: a failed source marks only its own line
            self._out = (None, str(error) or type(error).__name__)

    def result(self, timeout: float) -> tuple[Any, str | None]:
        """(value, None), or (None, cause) when the job raised or ran past `timeout` seconds from its start."""
        self._thread.join(max(0.0, self._started + timeout - time.monotonic()))
        return self._out or (None, f"timed out after {timeout:g}s")


def bounded(jobs: Mapping[str, Callable[[], Any]], timeout: float,
            timeouts: Mapping[str, float] | None = None) -> dict[str, tuple[Any, str | None]]:
    """Run every job at once; each result as `_Background.result` gives it, with its own timeout when named."""
    started = {name: _Background(job) for name, job in jobs.items()}
    return {name: job.result((timeouts or {}).get(name, timeout)) for name, job in started.items()}


def query(root: Path, argv: Sequence[str]) -> Any:
    """One read-only task query within CALL_TIMEOUT; raises SourceError with the cause when it fails."""
    data, cause = tasks.query_result(root, list(argv), timeout=CALL_TIMEOUT)
    if cause:
        raise SourceError(cause)
    return data


def _when(timestamp: str) -> datetime:
    try:
        moment = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return _EPOCH
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def recent_workflows(events: Sequence[WorkflowEvent], now: datetime) -> list[str]:
    """Workflows with a gate event and an event in the last OPEN_DAYS days, the most recently active first."""
    latest: dict[str, datetime] = {}
    gated: set[str] = set()
    for event in events:
        if event.workflow_id == UNBOUND_WORKFLOW:
            continue
        latest[event.workflow_id] = max(latest.get(event.workflow_id, _EPOCH), _when(event.timestamp))
        if event.event_type in _GATE_EVENTS:
            gated.add(event.workflow_id)
    since = now - timedelta(days=OPEN_DAYS)
    return sorted((wf for wf in gated if latest[wf] >= since), key=lambda wf: latest[wf], reverse=True)


def folder_workflows(events: Sequence[WorkflowEvent], folder: str) -> list[WorkflowEvent]:
    """The `session.bound` events made in `folder`, newest first."""
    return [event for event in reversed(events) if event.event_type == BOUND
            and event.workflow_id != UNBOUND_WORKFLOW and event.payload.get("cwd") == folder]


def local_shipped(events: Sequence[WorkflowEvent], workflow_ids: Sequence[str]) -> set[str]:
    """The workflows of `workflow_ids` with a `delivery.shipped` event."""
    wanted = set(workflow_ids)
    return {event.workflow_id for event in events
            if event.workflow_id in wanted and event.event_type == "delivery.shipped"}


def shipped_among(root: Path, events: Sequence[WorkflowEvent], workflow_ids: Sequence[str]) -> set[str]:
    """The shipped workflows of `workflow_ids`: a `delivery.shipped` event, or the epic of their
    `orchestration.ready` event closed. One `bd show` call for all the epics; when it fails, only the events count."""
    done = local_shipped(events, workflow_ids)
    epics = {wf: lifecycle_cli._recorded_epic(events, wf) for wf in workflow_ids if wf not in done}
    epics = {wf: epic for wf, epic in epics.items() if epic}
    if not epics:
        return done
    data, cause = tasks.query_result(root, ["show", *dict.fromkeys(epics.values())], timeout=CALL_TIMEOUT)
    if cause or not isinstance(data, list):
        return done
    closed = {str(row.get("id")) for row in data if isinstance(row, Mapping) and row.get("status") == "closed"}
    return done | {wf for wf, epic in epics.items() if epic in closed}


def resolve(events: Sequence[WorkflowEvent], *, flag: str | None, session_id: str, folder: str,
            shipped: set[str] | None) -> Found:
    """The card's workflow: the flag; the newest binding of the session; with `shipped` known, the newest binding
    made in the folder whose workflow is not shipped."""
    if flag:
        return Found(flag, "flag")
    if session_id:
        for event in reversed(events):
            if (event.event_type == BOUND and event.workflow_id != UNBOUND_WORKFLOW
                    and event.payload.get("session_id") == session_id):
                return Found(event.workflow_id, "this session")
    if shipped is not None:
        for event in folder_workflows(events, folder):
            if event.workflow_id not in shipped:
                return Found(event.workflow_id, f"last session in this folder, {event.timestamp}")
    return Found(None)


def local_stage(events: Sequence[WorkflowEvent], workflow_id: str) -> str:
    """The stage the local event log alone gives; Beads decides between execute and ship."""
    gates = lifecycle_cli._process_gate_state(events, workflow_id)
    return next((stage for stage, gate in _LOCAL_STAGES if not gates[gate]), "execute or ship")


def next_command(workflow_id: str, state: Mapping[str, Any], ready_ids: Sequence[str]) -> str | None:
    """The command that runs the next stage; None for a complete workflow."""
    if state["decision"] == "complete":
        return None
    if state["decision"] == "hold":
        return f"/gin:workflow {workflow_id}"
    if state["stage"] == "execute":
        return "/gin:execute " + " ".join(ready_ids) if ready_ids else f"/gin:workflow {workflow_id}"
    return f"/gin:{state['stage']} {workflow_id}"


def artifact_paths(events: Sequence[WorkflowEvent], workflow_id: str) -> tuple[str, str]:
    """(spec, plan): the evidence of the workflow's newest requirement and plan-approval events."""
    spec = plan = ""
    for event in events:
        if event.workflow_id != workflow_id:
            continue
        if event.event_type == "requirement.confirmed":
            spec = str(event.payload.get("evidence") or "")
        elif event.event_type == "approval.recorded" and event.payload.get("action") == "plan_approved":
            plan = str(event.payload.get("evidence") or "")
    return spec, plan


def ready_tracks(root: Path, epic: str) -> list[Mapping[str, Any]]:
    if not epic:
        return []
    data = query(root, ["ready", "--parent", epic])
    return [row for row in data or () if isinstance(row, Mapping) and not is_prep(row)]


def _cut(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= TEXT_CAP else text[:TEXT_CAP - 3] + "..."


def _items(texts: Sequence[str]) -> list[str]:
    lines = [f"  - {_cut(text)}" for text in texts[:LIST_CAP]]
    return lines + ([f"  +{len(texts) - LIST_CAP} more"] if len(texts) > LIST_CAP else [])


def _inline(texts: Sequence[str]) -> str:
    shown = ", ".join(_cut(text) for text in texts[:LIST_CAP])
    return shown + (f", +{len(texts) - LIST_CAP} more" if len(texts) > LIST_CAP else "")


def _state(ctx: Context, workflow_id: str) -> dict[str, Any]:
    return lifecycle_cli.state_payload(ctx.root, workflow_id, start=ctx.start, bind=False, warnings=False)[0]


def workflow_lines(ctx: Context, found: Found, recent: Sequence[str], shipped: set[str] | None) -> list[str]:
    wf = found.workflow_id or ""
    epic = lifecycle_cli._recorded_epic(ctx.events, wf)
    spec, plan = artifact_paths(ctx.events, wf)
    others = [other for other in recent if other != wf]
    jobs: dict[str, Callable[[], Any]] = {
        "state": lambda: _state(ctx, wf),
        "kind": lambda: epic_kind.lookup(ctx.root, wf, spec or None),
        "ready": lambda: ready_tracks(ctx.root, epic),
    }
    if shipped is None and others:
        jobs["shipped"] = lambda: shipped_among(ctx.root, ctx.events, others)
    got = bounded(jobs, ROUND_TIMEOUT)
    state, state_cause = got["state"]
    kind, kind_error = got["kind"][0] or (None, None)
    detail = [f"epic {epic}"] if epic else []
    if kind and not kind_error:
        detail.append(f"kind {kind}")
    lines = [f"gin state card (workflow found by: {found.how})",
             f"Workflow: {wf}" + (f" ({', '.join(detail)})" if detail else "")]
    if state_cause:
        lines += [f"Stage: unknown ({state_cause})", f"Gates: unknown ({state_cause})"]
    else:
        remedies = "; ".join(state["remedies"])
        lines.append(f"Stage: {state['stage']} ({state['decision']})" + (f"; remedies: {remedies}" if remedies else ""))
        lines.append("Gates: " + ", ".join(f"{gate}={status}" for gate, status in state["gates"].items()))
    if spec:
        lines.append(f"Spec: {spec}")
    if plan:
        lines.append(f"Plan: {plan}")
    ready, ready_cause = got["ready"]
    if ready_cause:
        lines.append(f"Ready tracks: unknown ({ready_cause})")
    elif ready:
        lines += ["Ready tracks:", *_items([f"{row.get('id')} {row.get('title', '')}" for row in ready])]
    if state is not None:
        command = next_command(wf, state, [str(row.get("id")) for row in ready or ()])
        if command:
            lines.append(f"Next: {command}")
    done = shipped if shipped is not None else (got.get("shipped", (None, None))[0] or local_shipped(ctx.events, others))
    still_open = [other for other in others if other not in done]
    if still_open:
        lines.append("Other open workflows: " + _inline([f"{other} ({local_stage(ctx.events, other)})"
                                                          for other in still_open]))
    return lines


def no_workflow_lines(ctx: Context, open_ids: Sequence[str]) -> list[str]:
    lines = ["gin state card: no workflow is bound to this session or this folder"]
    if not open_ids:
        return [*lines, "Open workflows: none; start one with /gin:discuss"]
    shown = list(open_ids[:OPEN_CAP])
    got = bounded({wf: (lambda wf=wf: _state(ctx, wf)) for wf in shown}, ROUND_TIMEOUT)
    lines.append("Open workflows:")
    for wf in shown:
        state, cause = got[wf]
        if cause:
            lines.append(f"  - {wf}: unknown ({cause})")
            continue
        command = next_command(wf, state, [])
        lines.append(f"  - {wf}: {state['stage']}" + (f", next: {command}" if command else ""))
    if len(open_ids) > OPEN_CAP:
        lines.append(f"  +{len(open_ids) - OPEN_CAP} more")
    return lines


def finish(lines: Sequence[str]) -> str:
    return "\n".join(lines)[:CARD_CAP]


def render(ctx: Context, found: Found, recent: Sequence[str], shipped: set[str] | None) -> str:
    if found.workflow_id is None:
        lines = no_workflow_lines(ctx, [wf for wf in recent if wf not in (shipped or set())])
    else:
        lines = workflow_lines(ctx, found, recent, shipped)
    return finish(lines)


def pre_compact_text(events: Sequence[WorkflowEvent], flag: str | None, session_id: str, folder: str) -> str:
    """What the compaction summary keeps. Local reads only: no Beads call."""
    shipped = local_shipped(events, [event.workflow_id for event in folder_workflows(events, folder)])
    found = resolve(events, flag=flag, session_id=session_id, folder=folder, shipped=shipped)
    if found.workflow_id:
        keep = (f"- keep the workflow id {found.workflow_id} and its stage "
                f"({local_stage(events, found.workflow_id)} by the local event log)")
    else:
        keep = "- keep the gin workflow id and the stage being worked on"
    lines = [
        "gin: in the compaction summary,",
        keep,
        "- keep, word for word, each decision and answer the user gave in this chat that is not yet in the spec, "
        "the plan, or a bead",
        "- keep, word for word, the question waiting for the user's answer",
        "- keep the files being changed and why",
        "- drop tool output and file contents; they can be read again",
        "- the gin state card returns after compaction by itself; do not copy it",
    ]
    return "\n".join(lines)[:PRE_COMPACT_CAP]


def _hook_input(stream: Any) -> dict[str, Any]:
    try:
        value = json.loads(stream.read() or "{}")
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _session_id(hook_input: Mapping[str, Any]) -> str:
    value = str(hook_input.get("session_id") or os.environ.get(SESSION_VARIABLE, ""))
    return value if is_session_id(value) else ""


def _events(root: Path) -> tuple[list[WorkflowEvent], str | None]:
    path = main_checkout(root) / ".agent-workflow/runtime/events.jsonl"
    if not path.is_file():
        return [], None
    events, cause = lifecycle_cli._read_events(WorkflowEventStore(path))
    return events or [], cause


def _uses_beads(root: Path) -> bool:
    from .configuration import ConfigValidationError

    try:
        return tasks.backend(root) == "beads"
    except ConfigValidationError:
        return False


def _run(args: argparse.Namespace, start: Path) -> str:
    from .configuration import resolve_effective_config
    from .project import project_settings
    from .team import load_team
    from .workspace import repository_root

    root = repository_root(args.repository)
    if not (root / ".agent-workflow/config.yaml").is_file():
        return ""
    session_id = _session_id(_hook_input(sys.stdin) if args.hook else {})
    events, cause = _events(root)
    if cause:
        return f"gin state card: {cause}"
    folder = folder_key(start)
    if args.pre_compact:
        return pre_compact_text(events, args.workflow_id, session_id, folder)
    config = resolve_effective_config(root, write=False).config.to_dict()
    ctx = Context(root, start, events, project_settings(config), load_team(config), _uses_beads(root))
    recent = recent_workflows(events, datetime.now(timezone.utc))
    found = resolve(events, flag=args.workflow_id, session_id=session_id, folder=folder, shipped=None)
    shipped = None
    if found.workflow_id is None:
        candidates = [*(event.workflow_id for event in folder_workflows(events, folder)), *recent]
        shipped = shipped_among(root, events, list(dict.fromkeys(candidates)))
        found = resolve(events, flag=None, session_id="", folder=folder, shipped=shipped)
    return render(ctx, found, recent, shipped)


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="gin prime", description="print the workflow state card")
    parser.add_argument("--repository", type=Path, default=None)
    parser.add_argument("--workflow-id", default=None)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--hook", action="store_true", help="read the hook input JSON on stdin; always exit 0")
    mode.add_argument("--pre-compact", action="store_true",
                      help="print what the compaction summary keeps; no Beads call")
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    quiet = args.hook or args.pre_compact
    start = Path(args.repository) if args.repository is not None else Path.cwd()
    try:
        from . import version_pin
        from .cli import CLI_VERSION

        pin = version_pin.verdict(CLI_VERSION, start)
        if pin.status in ("older", "invalid", "newer_major"):
            if quiet:
                return 0  # `gin version --hook` already warns
            print(f"error: {version_pin.message(pin, CLI_VERSION)}", file=sys.stderr)
            return 2
        text = _run(args, start)
    except Exception as error:  # broad on purpose: a hook never fails the session start
        if not quiet:
            raise
        print(f"gin prime: {error}", file=sys.stderr)
        return 0
    if text:
        print(text)
    return 0
```

6. In `cli.py`, add `"prime"` to `TOP_COMMANDS` (after `"version"`) and to `UNPINNED` (`prime` checks the pin itself, silent in hook modes): `UNPINNED = ("paths", "version", "prime")`. Inside the `try:` of `main`, before `if argv[0] == "routes":`, add:

```python
        if argv[0] == "prime":
            from .prime import main as prime_main
            return prime_main(argv[1:])
```

7. In `docs/reference/cli.md`, insert before `## \`gin record\`` (line 73):

````markdown
## `gin prime`

```
gin prime [--workflow-id ID] [--hook] [--pre-compact]
```

Prints the state card of one workflow for a Claude Code session. The Claude Code hooks file that `install.sh` or `install.ps1` writes runs `gin prime --hook` on `startup`, `resume`, `clear`, and `compact`, and `gin prime --pre-compact` before a compaction.

The workflow is the first that applies: `--workflow-id`; the workflow bound most recently to the running session (the `session_id` of the hook input with `--hook`, else `CLAUDE_CODE_SESSION_ID`); the newest `session.bound` event whose `cwd` is this folder's git top level and whose workflow is not shipped. A workflow is shipped when it has a `delivery.shipped` event or the epic of its `orchestration.ready` event is closed. With none of these, the card lists up to five open workflows (a gate event, not shipped, an event in the last 14 days) with their stage and next command.

The first line says how the workflow was found: `flag`, `this session`, or `last session in this folder` with its time. Then, each line left out when empty: `Workflow:` (id, epic, kind), `Stage:` (with the remedies when it holds), `Gates:` (the values of `gin state`), `Spec:` and `Plan:` (the evidence of the workflow's requirement and plan-approval events), `Ready tracks:`, `Next:`, and `Other open workflows:`. `Next:` is `/gin:<stage> <id>`, `/gin:execute` with the ready track ids, or `/gin:workflow <id>` when the workflow holds or is at `execute` with no ready track; a complete workflow has none. `Other open workflows:` shows the stage the local event log gives, `execute or ship` once orchestration is recorded.

The Beads calls run concurrently, each with a timeout; a call that fails or times out turns only its line into `unknown (<cause>)`. The card skips the knowledge and learn-comment warnings of `gin state`, never binds the session, and writes nothing.

In a folder without `.agent-workflow/config.yaml`, it prints nothing. With `--hook` it reads the hook input JSON on stdin and always exits 0; when the `.ginrc` pin refuses this gin, it prints nothing, because `gin version --hook` already warns. Without `--hook` or `--pre-compact`, a refusing pin prints the usual error and exits 2.

`--pre-compact` makes no Beads call and prints at most 1,500 characters for the compaction summary: keep the workflow id and stage; keep, word for word, the decisions and answers given in the chat that are not yet in the spec, the plan, or a bead; keep the question waiting for the user and the files being changed; drop tool output and file contents.
````

8. Run `python3 -m pytest tests/workflow_core/test_prime.py tests/workflow_core/test_lifecycle_cli.py tests/workflow_core/test_session_binding.py tests/workflow_core/test_docs_coverage.py -q`. Expected: all pass. Then run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.cli prime` in this worktree and compare its `Gates:` line with `gin state --format json --workflow-id gin-workflow-context-boundaries`; run it from `/tmp` with `--hook < /dev/null`: no output, exit 0.

9. Commit: `gin commit -m "feat(prime): gin prime state card (gin-workflow-context-boundaries)"` with the six files.

### Track 3: Open questions, review cycles, Beads memories, and the size cap
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/prime.py` (`epic_comments`, `open_questions`, `technical_questions`, `review_cycles`, `memories`, `REFERENCE`; extend `workflow_lines`, `render`, `finish`)
  - Modify `docs/reference/cli.md` (one paragraph in the `gin prime` section)
  - Test `tests/workflow_core/test_prime.py`
- **Interfaces**:
  - Produces `open_questions(comments: Sequence[Mapping]) -> list[str]`, `review_cycles(root, epic, default_max: int) -> list[str]`, `memories(root) -> dict[str, str]`, `finish(lines, memo: tuple[dict | None, str | None] | None = None) -> str`, `REFERENCE = "Beads command reference: bd prime --no-memories"`.
  - Consumes `lifecycle_cli._open_questions(repo_path, workflow_id) -> list[tuple[str, str]]`, `review_ledger.cli.load_ledger(bead, base_dir)` (projection fields `active_approval`, `cycles`, `max_cycles`), `ProjectSettings.review_ledger`, `ProjectSettings.max_cycles`, and track 2's `_Background`, `query`, `_items`, `_inline`, `Context`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded additions to one module, with the parsing rules and the cap arithmetic given below.
- **Acceptance criteria**: `python3 -m pytest tests/workflow_core/test_prime.py -q` passes; in this worktree `gin prime | wc -c` prints at most 9,501 and the output ends with `Beads command reference: bd prime --no-memories`.
- **Estimated complexity**: medium

Steps:

1. Add to `tests/workflow_core/test_prime.py`:

```python
def beads(**answers):
    """Patches for a Beads project whose bd answers each subcommand from `answers` (default: an empty list)."""
    def answer(root, argv, timeout=30):
        value = answers.get(argv[0], [])
        return (None, value[1]) if isinstance(value, tuple) else (value, None)

    return (mock.patch("workflow_core.tasks.backend", return_value="beads"),
            mock.patch("workflow_core.tasks.query_result", side_effect=answer))


class BeadsLinesTests(PrimeCase):
    def run_with(self, *argv, **answers):
        backend, query = beads(**answers)
        with backend, query:
            return self.prime(*argv)[1]

    def test_open_questions_without_a_newer_answer(self):
        comments = [
            {"text": "[gin question] t-1: which port?", "created_at": "2026-11-01T00:00:00Z"},
            {"text": "[gin answer] t-1: 8080", "created_at": "2026-11-02T00:00:00Z"},
            {"text": "[gin question] t-2: keep the old flag?", "created_at": "2026-11-03T00:00:00Z"},
            {"text": "[gin learn] something", "created_at": "2026-11-04T00:00:00Z"},
        ]
        self.assertEqual(["t-2: keep the old flag?"], prime.open_questions(comments))

    def test_the_card_lists_bead_questions_and_open_design_questions(self):
        with mock.patch("workflow_core.lifecycle_cli._open_questions",
                        return_value=[(".planning/specs/x-design.md:40: TQ-1", "")]):
            out = self.run_with("--workflow-id", "wf-1",
                                comments=[{"text": "[gin question] t-2: keep it?", "created_at": "2026-11-03T00:00:00Z"}])
        self.assertIn("Open questions:\n  - .planning/specs/x-design.md:40: TQ-1\n  - t-2: keep it?", out)

    def test_memories_that_fit_are_all_shown_and_the_reference_ends_the_card(self):
        out = self.run_with("--workflow-id", "wf-1", memories={"a": "first", "b": "second\nline"})
        self.assertIn("Beads memories\n- a: first\n- b: second line\n", out)
        self.assertNotIn("more: bd memories", out)
        self.assertTrue(out.rstrip("\n").endswith(prime.REFERENCE))

    def test_memories_that_do_not_fit_end_with_more(self):
        many = {f"m{index:03d}": "x" * 100 for index in range(200)}
        out = self.run_with("--workflow-id", "wf-1", memories=many)
        self.assertLessEqual(len(out.rstrip("\n")), prime.CARD_CAP)
        self.assertRegex(out, r"\+\d+ more: bd memories\n")
        self.assertTrue(out.rstrip("\n").endswith(prime.REFERENCE))

    def test_failed_memories_mark_only_their_line(self):
        out = self.run_with("--workflow-id", "wf-1", memories=(None, "bd timed out after 4s"))
        self.assertIn("Beads memories: unknown (bd timed out after 4s)", out)
        self.assertIn("Workflow: wf-1", out)

    def test_review_cycles_only_with_the_review_ledger(self):
        self.add("orchestration.ready", "wf-1", {"epic": "ep-1", "evidence": "plan.md"})
        with mock.patch.object(prime, "review_cycles", return_value=["t-1 1/2"]):
            self.assertNotIn("Review cycles:", self.run_with("--workflow-id", "wf-1"))
            (self.root / ".agent-workflow/config.yaml").write_text(
                "schema_version: '2.3'\nproject:\n  review_ledger: true\n", encoding="utf-8")
            self.assertIn("Review cycles: t-1 1/2", self.run_with("--workflow-id", "wf-1"))

    def test_a_markdown_project_has_no_memories_section(self):
        out = self.prime("--workflow-id", "wf-1")[1]
        self.assertNotIn("Beads memories", out)
        self.assertNotIn(prime.REFERENCE, out)
```

2. Run `python3 -m pytest tests/workflow_core/test_prime.py -q`. Expected: the seven new tests fail (`AttributeError: ... open_questions`, missing lines).

3. In `prime.py`, add after `ready_tracks`:

```python
REFERENCE = "Beads command reference: bd prime --no-memories"
_QUESTION, _ANSWER = "[gin question]", "[gin answer]"


def epic_comments(root: Path, target: str) -> list[Mapping[str, Any]]:
    """The comments on `target`; none when it names no bead (a workflow id that is not a bead id)."""
    data, cause = tasks.query_result(root, ["comments", target], timeout=CALL_TIMEOUT)
    if cause:
        if "not found" in cause.lower() and cause != "bd not found":
            return []
        raise SourceError(cause)
    return [item for item in data or () if isinstance(item, Mapping)]


def open_questions(comments: Sequence[Mapping[str, Any]]) -> list[str]:
    """`<track>: <question>` for each `[gin question] <track>:` comment with no newer `[gin answer] <track>:` one."""
    asked: dict[str, str] = {}
    for item in sorted(comments, key=lambda item: str(item.get("created_at") or "")):
        text = str(item.get("text") or "").strip()
        for marker in (_QUESTION, _ANSWER):
            if text.startswith(marker):
                rest = text[len(marker):].strip()
                track = rest.split(":", 1)[0].strip()
                if marker == _QUESTION:
                    asked[track] = rest
                else:
                    asked.pop(track, None)
    return list(asked.values())


def technical_questions(root: Path, workflow_id: str) -> list[str]:
    return [label for label, _ in lifecycle_cli._open_questions(root, workflow_id)]


def review_cycles(root: Path, epic: str, default_max: int) -> list[str]:
    """`<bead> <cycles>/<max>` for each in-progress track of `epic` whose review ledger holds no live approval."""
    from review_ledger.cli import load_ledger
    from review_ledger.events import WorkflowIntegrityError

    rows = query(root, ["list", "--parent", epic, "--status", "in_progress"])
    found: list[str] = []
    for row in rows if isinstance(rows, list) else ():
        bead = str(row.get("id") or "") if isinstance(row, Mapping) else ""
        if not bead:
            continue
        try:
            _, projection = load_ledger(bead, str(root))
        except FileNotFoundError:
            continue
        except (WorkflowIntegrityError, OSError, ValueError) as error:
            found.append(f"{bead} ledger unreadable ({error})")
            continue
        if projection.active_approval is None:
            found.append(f"{bead} {projection.cycles}/{projection.max_cycles or default_max}")
    return found


def memories(root: Path) -> dict[str, str]:
    data = query(root, ["memories"])
    return {str(key): str(value) for key, value in data.items()} if isinstance(data, Mapping) else {}
```

4. In `workflow_lines`, add to `jobs` (after `"ready"`):

```python
        "tq": lambda: technical_questions(ctx.root, wf),
    }
    if ctx.beads:
        jobs["comments"] = lambda: open_questions(epic_comments(ctx.root, epic or wf))
    if ctx.beads and epic and ctx.settings.review_ledger:
        jobs["cycles"] = lambda: review_cycles(ctx.root, epic, ctx.settings.max_cycles)
```

   (the closing `}` of the dict moves after `"tq"`), and insert before `if state is not None:`:

```python
    tq, tq_cause = got["tq"]
    comments, comments_cause = got.get("comments", ([], None))
    questions = [*(tq or ()), *(comments or ())]
    if tq_cause:
        questions.append(f"design doc unknown ({tq_cause})")
    if comments_cause:
        questions.append(f"bead comments unknown ({comments_cause})")
    if questions:
        lines += ["Open questions:", *_items(questions)]
    if "cycles" in got:
        cycles, cycles_cause = got["cycles"]
        if cycles_cause:
            lines.append(f"Review cycles: unknown ({cycles_cause})")
        elif cycles:
            lines.append("Review cycles: " + _inline(cycles))
```

5. Replace `finish` and `render`:

```python
def finish(lines: Sequence[str], memo: tuple[dict[str, str] | None, str | None] | None = None) -> str:
    """The card within CARD_CAP. `memo` is the memories result, None outside Beads: the memories fill the room the
    card leaves, then `+N more: bd memories`, and REFERENCE ends the card."""
    head = "\n".join(lines) + "\n"
    if memo is None:
        return head.rstrip("\n")[:CARD_CAP]
    found, cause = memo
    if cause:
        return (head + f"\nBeads memories: unknown ({cause})\n" + REFERENCE)[:CARD_CAP]
    items = [f"- {key}: {' '.join(value.split())}" for key, value in (found or {}).items()]
    if not items:
        return (head + "\n" + REFERENCE)[:CARD_CAP]
    head += "\nBeads memories\n"
    room = CARD_CAP - len(head) - len(REFERENCE) - len(f"+{len(items)} more: bd memories\n")
    kept: list[str] = []
    for item in items:
        if len(item) + 1 > room:
            break
        kept.append(item)
        room -= len(item) + 1
    rest = len(items) - len(kept)
    more = f"+{rest} more: bd memories\n" if rest else ""
    return (head + "".join(f"{item}\n" for item in kept) + more + REFERENCE)[:CARD_CAP]


def render(ctx: Context, found: Found, recent: Sequence[str], shipped: set[str] | None) -> str:
    memo = _Background(lambda: memories(ctx.root)) if ctx.beads else None
    if found.workflow_id is None:
        lines = no_workflow_lines(ctx, [wf for wf in recent if wf not in (shipped or set())])
    else:
        lines = workflow_lines(ctx, found, recent, shipped)
    return finish(lines, memo.result(ROUND_TIMEOUT) if memo else None)
```

6. In `docs/reference/cli.md`, in the `gin prime` section, add after the paragraph that ends "and `Other open workflows:`.":

```markdown
Between `Ready tracks:` and `Next:` come `Open questions:` (the `[gin question] <track>:` comments on the epic with no newer `[gin answer] <track>:`, and the open `TQ-<n>` of the design doc) and, with `project.review_ledger: true`, `Review cycles:` (cycles used against `max_cycles` for each in-progress track whose ledger is not approved). With Beads, a `Beads memories` section follows, then the line `Beads command reference: bd prime --no-memories`. The whole card is at most 9,500 characters, under Claude Code's 10,000-character cap for hook output: each list shows at most 10 items, then `+N more`, and the memories fill the room left, then `+N more: bd memories`.
```

7. Run `python3 -m pytest tests/workflow_core/test_prime.py -q`. Expected: all pass. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.cli prime | wc -c`. Expected: at most 9501.

8. Commit: `gin commit -m "feat(prime): questions, review cycles, memories, and the 9,500-character cap (gin-workflow-context-boundaries)"`.

### Track 4: Team lines on the card
- **Dependencies**: Track 3
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/prime.py` (`TEAM_TIMEOUT`, `team_jobs`, `team_lines`; extend `render`)
  - Modify `docs/reference/cli.md` (one paragraph in the `gin prime` section)
  - Test `tests/workflow_core/test_prime_team.py`
- **Interfaces**:
  - Produces `TEAM_TIMEOUT = 4.0`, `team_jobs(ctx) -> dict[str, Callable[[], Any]]` (keys `team_member`, `team_lanes`, `team_pending`), `team_lines(got) -> list[str]`.
  - Consumes `team.require_member(root, team) -> Member` (`login`, `email`, `roles`), `team_beads.ready(root, team, member) -> list[dict]` (`assignee`, `lane`, `branch`), `team_pending.pending(root, team) -> list[dict]` (`gate`, `url`, `branch`, `missing`).
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded: three team sources joined on track 2's runner with their own timeout, code given below.
- **Acceptance criteria**: `python3 -m pytest tests/workflow_core/test_prime_team.py tests/workflow_core/test_prime.py -q` passes.
- **Estimated complexity**: medium

Steps:

1. Create `tests/workflow_core/test_prime_team.py`:

```python
"""`gin prime` in team mode: member, claimed lane, waiting pull requests, and the shared gates."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from workflow_core import lifecycle_cli, prime
from workflow_core.team import Member
from tests.workflow_core.team_fixtures import make_team_repo

MEMBER = Member("binh@corp.com", ("dev",), "binh", "")


class PrimeTeamTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = make_team_repo(Path(directory.name).resolve() / "app")
        for target, value in (("workflow_core.team.require_member", mock.DEFAULT),
                              ("workflow_core.team_beads.ready", mock.DEFAULT),
                              ("workflow_core.team_pending.pending", mock.DEFAULT)):
            patcher = mock.patch(target)
            setattr(self, target.rsplit(".", 1)[1], patcher.start())
            self.addCleanup(patcher.stop)
        self.require_member.return_value = MEMBER
        self.ready.return_value = [
            {"id": "t-1", "title": "API", "assignee": "binh@corp.com", "lane": "api", "branch": "feat/x-api"},
            {"id": "t-2", "title": "UI", "assignee": "", "lane": "ui", "branch": "feat/x-ui"},
        ]
        self.pending.return_value = [{"gate": "plan_approved", "url": "https://github.com/org/app/pull/7",
                                      "branch": "plan/x", "missing": ["1 approval"]}]

    def prime(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch("sys.stdin", io.StringIO("{}")):
            code = prime.main(["--repository", str(self.root), *argv])
        return code, out.getvalue()

    def test_member_lane_and_pull_requests(self):
        code, out = self.prime("--workflow-id", "wf-1")
        self.assertEqual(0, code)
        self.assertIn("Member: binh (roles: dev)", out)
        self.assertIn("Claimed lane: api (feat/x-api)", out)
        self.assertNotIn("ui (feat/x-ui)", out)
        self.assertIn("Pull requests waiting:\n  - plan_approved https://github.com/org/app/pull/7 missing: 1 approval",
                      out)

    def test_a_slow_host_does_not_hold_the_card(self):
        def slow(*args, **kwargs):
            time.sleep(1)
            return []

        self.pending.side_effect = slow
        with mock.patch.object(prime, "TEAM_TIMEOUT", 0.1):
            code, out = self.prime("--workflow-id", "wf-1")
        self.assertEqual(0, code)
        self.assertIn("Pull requests waiting: not checked (timed out after 0.1s); run gin team pending", out)
        self.assertIn("Member: binh", out)

    def test_a_host_failure_names_its_cause(self):
        self.pending.side_effect = RuntimeError("gh: not logged in")
        self.assertIn("Pull requests waiting: not checked (gh: not logged in); run gin team pending",
                      self.prime("--workflow-id", "wf-1")[1])

    def test_the_card_gates_are_the_shared_gates_of_gin_state(self):
        shared = ("ep-1", {"requirement_confirmed": {"pr_url": "u", "actor": "a", "at": "t"},
                           "plan_approved": {"pr_url": "u", "actor": "a", "at": "t"}}, None)
        with mock.patch("workflow_core.team_beads.shared_gates", return_value=shared), \
                mock.patch("workflow_core.lifecycle_cli.tasks_backend", return_value="beads"), \
                mock.patch("workflow_core.lifecycle_cli._delivery_state",
                           return_value=({"implementation_complete": False, "shipped": False}, False, None)):
            card = self.prime("--workflow-id", "wf-1")[1]
            gates = lifecycle_cli.state_payload(self.root, "wf-1", bind=False)[0]["gates"]
        line = "Gates: " + ", ".join(f"{gate}={status}" for gate, status in gates.items())
        self.assertIn("requirement_confirmed=satisfied, plan_approved=satisfied", line)
        self.assertIn(line, card)


if __name__ == "__main__":
    unittest.main()
```

2. Run `python3 -m pytest tests/workflow_core/test_prime_team.py -q`. Expected: the first three fail (no team lines); the fourth passes already (requirement 19 holds through `state_payload`).

3. In `prime.py`, add after `memories`:

```python
TEAM_TIMEOUT = 4.0  # the host's answer for the waiting pull requests, in all


def team_jobs(ctx: Context) -> dict[str, Callable[[], Any]]:
    from . import team as team_core, team_beads, team_pending

    def lanes() -> tuple[Any, list[dict[str, Any]]]:
        member = team_core.require_member(ctx.root, ctx.team)
        return member, team_beads.ready(ctx.root, ctx.team, member)

    return {"team_member": lambda: team_core.require_member(ctx.root, ctx.team), "team_lanes": lanes,
            "team_pending": lambda: team_pending.pending(ctx.root, ctx.team)}


def team_lines(got: Mapping[str, tuple[Any, str | None]]) -> list[str]:
    member, cause = got["team_member"]
    if cause:
        lines = [f"Member: unknown ({cause})"]
    else:
        lines = [f"Member: {member.login or member.email} (roles: {', '.join(member.roles) or '-'})"]
    found, cause = got["team_lanes"]
    if cause:
        lines.append(f"Claimed lane: unknown ({cause})")
    else:
        mine, rows = found
        claimed = [f"{row['lane']} ({row['branch']})" if row.get("lane") and row.get("branch")
                   else str(row.get("lane") or row.get("branch"))
                   for row in rows if row.get("assignee") == mine.email and (row.get("lane") or row.get("branch"))]
        if claimed:
            lines.append("Claimed lane: " + _inline(list(dict.fromkeys(claimed))))
    rows, cause = got["team_pending"]
    if cause:
        lines.append(f"Pull requests waiting: not checked ({cause}); run gin team pending")
    elif rows:
        lines += ["Pull requests waiting:", *_items([
            f"{row.get('gate') or 'track'} {row.get('url') or row.get('branch')}"
            + (f" missing: {', '.join(row['missing'])}" if row.get("missing") else "") for row in rows])]
    return lines
```

4. Replace `render`:

```python
def render(ctx: Context, found: Found, recent: Sequence[str], shipped: set[str] | None) -> str:
    memo = _Background(lambda: memories(ctx.root)) if ctx.beads else None
    team = {name: _Background(job) for name, job in team_jobs(ctx).items()} if ctx.team is not None else {}
    if found.workflow_id is None:
        lines = no_workflow_lines(ctx, [wf for wf in recent if wf not in (shipped or set())])
    else:
        lines = workflow_lines(ctx, found, recent, shipped)
    if team:
        lines += team_lines({name: job.result(TEAM_TIMEOUT if name == "team_pending" else ROUND_TIMEOUT)
                             for name, job in team.items()})
    return finish(lines, memo.result(ROUND_TIMEOUT) if memo else None)
```

5. In `docs/reference/cli.md`, `gin prime` section, add as the section's last paragraph:

```markdown
With `project.team.enabled`, the card adds `Member:` (login and roles, as `gin team whoami`), `Claimed lane:` (lane and branch of the `gin team ready` rows assigned to the member), and `Pull requests waiting:` (the rows of `gin team pending`). The host gets 4 seconds in all; on a timeout or a host failure the line reads `not checked (<cause>); run gin team pending` and the card still prints. The gates come from the same shared-gate read as `gin state`.
```

6. Run `python3 -m pytest tests/workflow_core/test_prime_team.py tests/workflow_core/test_prime.py -q`. Expected: all pass.

7. Commit: `gin commit -m "feat(prime): team lines on the state card (gin-workflow-context-boundaries)"`.

### Track 5: Claude Code hooks run the card
- **Dependencies**: none
- **Files**:
  - Modify `install.sh:323-352` (`template_hooks_for_claude`)
  - Modify `install.ps1:167-180` (`New-HooksFile`, claude block)
  - Test `tests/workflow_core/test_harness_packaging.py:170-177`
  - Test `tests/install_smoke_test.sh:269,320,344-346`
  - Test `tests/install_smoke_test.ps1:166-168`
- **Interfaces**:
  - Produces in the Claude Code hooks file: `hooks.SessionStart[0]` unchanged (the version hook, no matcher); `hooks.SessionStart[1]` = matcher `startup|resume|clear|compact`, one command hook running `gin prime --hook`, timeout 15; `hooks.PreCompact[0]` = one command hook running `gin prime --pre-compact`, timeout 15. Windows entries carry `shell: powershell` and call `gin.cmd`.
  - Consumes the `gin prime --hook` and `--pre-compact` flags (track 2); until track 2 lands, the hook prints a usage error on stderr and still exits 0.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** mechanical additions next to existing entries in two installers and their tests; quoting rules given below.
- **Acceptance criteria**: `python3 -m pytest tests/workflow_core/test_harness_packaging.py -q` and `bash tests/install_smoke_test.sh` pass; `install_smoke_test.ps1` assertions written (run on Windows CI by request).
- **Estimated complexity**: low

Steps:

1. In `tests/workflow_core/test_harness_packaging.py`, replace the test at lines 170-177 with:

```python
    def test_only_the_claude_hooks_file_has_session_start_and_pre_compact_hooks(self):
        claude = json.loads((self.dist / "claude-code/hooks/hooks.json").read_text(encoding="utf-8"))
        self.assertEqual({"PreToolUse", "SessionStart", "PreCompact"}, set(claude["hooks"]))
        version, card = claude["hooks"]["SessionStart"]
        self.assertIn("gin version --hook", version["hooks"][0]["command"])
        self.assertNotIn("matcher", version)
        self.assertEqual("startup|resume|clear|compact", card["matcher"])
        self.assertEqual("if command -v gin >/dev/null 2>&1; then gin prime --hook; fi; exit 0",
                         card["hooks"][0]["command"])
        self.assertEqual(15, card["hooks"][0]["timeout"])
        compact = claude["hooks"]["PreCompact"][0]["hooks"][0]
        self.assertEqual("if command -v gin >/dev/null 2>&1; then gin prime --pre-compact; fi; exit 0",
                         compact["command"])
        self.assertEqual(15, compact["timeout"])
        for relative in ("codex/hooks/hooks.json", "antigravity/hooks/hooks.json", "copilot/gin/hooks/hooks.json"):
            with self.subTest(file=relative):
                text = (self.dist / relative).read_text(encoding="utf-8")
                self.assertNotIn("SessionStart", text)
                self.assertNotIn("PreCompact", text)
```

2. Run `python3 -m pytest tests/workflow_core/test_harness_packaging.py -q`. Expected: the new test fails (`{"PreToolUse", "SessionStart"}` lacks `PreCompact`).

3. In `install.sh`, in `template_hooks_for_claude`, replace the `"SessionStart": [ ... ]` array (keep the heredoc unquoted; these commands hold no `$`) with:

```json
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "if command -v gin >/dev/null 2>&1; then gin version --hook; fi; exit 0",
            "timeout": 10
          }
        ]
      },
      {
        "matcher": "startup|resume|clear|compact",
        "hooks": [
          {
            "type": "command",
            "command": "if command -v gin >/dev/null 2>&1; then gin prime --hook; fi; exit 0",
            "timeout": 15
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "if command -v gin >/dev/null 2>&1; then gin prime --pre-compact; fi; exit 0",
            "timeout": 15
          }
        ]
      }
    ]
```

4. In `install.ps1`, inside `if ($Harness -eq 'claude') { ... }`, replace the `$hooks.hooks['SessionStart'] = ...` assignment with:

```powershell
            $hooks.hooks['SessionStart'] = @(
                [ordered]@{
                    hooks = @([ordered]@{
                        type = 'command'
                        shell = 'powershell'
                        command = 'if (Get-Command gin.cmd -ErrorAction SilentlyContinue) { gin.cmd version --hook }; exit 0'
                        timeout = 10
                    })
                },
                [ordered]@{
                    matcher = 'startup|resume|clear|compact'
                    hooks = @([ordered]@{
                        type = 'command'
                        shell = 'powershell'
                        command = 'if (Get-Command gin.cmd -ErrorAction SilentlyContinue) { gin.cmd prime --hook }; exit 0'
                        timeout = 15
                    })
                }
            )
            $hooks.hooks['PreCompact'] = @([ordered]@{
                hooks = @([ordered]@{
                    type = 'command'
                    shell = 'powershell'
                    command = 'if (Get-Command gin.cmd -ErrorAction SilentlyContinue) { gin.cmd prime --pre-compact }; exit 0'
                    timeout = 15
                })
            })
```

5. Smoke tests. In `tests/install_smoke_test.sh`, after line 269 add `assert_not_contains "plugins/gin-workflow/dist/codex/hooks/hooks.json" "PreCompact"`; after line 320 add `assert_not_contains "plugins/gin-workflow/dist/copilot/gin/hooks/hooks.json" "PreCompact"`; after line 346 add:

```bash
assert_contains "$MOCK_HOME/.claude/skills/gin/hooks/hooks.json" '"matcher": "startup|resume|clear|compact"'
assert_contains "$MOCK_HOME/.claude/skills/gin/hooks/hooks.json" 'gin prime --hook'
assert_contains "$MOCK_HOME/.claude/skills/gin/hooks/hooks.json" '"PreCompact"'
assert_contains "$MOCK_HOME/.claude/skills/gin/hooks/hooks.json" 'gin prime --pre-compact'
```

   In `tests/install_smoke_test.ps1`, after line 168 add:

```powershell
    Assert-Contains $claudeHooksText 'gin.cmd prime --hook'
    Assert-Contains $claudeHooksText 'gin.cmd prime --pre-compact'
    Assert-Contains $claudeHooksText '"PreCompact"'
    Assert-Contains $claudeHooksText 'startup|resume|clear|compact'
```

6. Run `python3 -m pytest tests/workflow_core/test_harness_packaging.py -q` and `bash tests/install_smoke_test.sh`. Expected: both pass.

7. Commit: `gin commit -m "feat(hooks): SessionStart and PreCompact hooks run gin prime (gin-workflow-context-boundaries)"`.

### Track 6: Handoff line and the compaction-point proposal
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/references/stage-contract.md:11,33-35` (shorter standalone-bead sentence, new `## Handoff`)
  - Modify `plugins/gin-workflow/src/skills/orchestrate/SKILL.md:32`
  - Modify `plugins/gin-workflow/src/skills/ship/SKILL.md:41`
  - Modify `plugins/gin-workflow/src/skills/setup/SKILL.md:29-30` (new apply step 6)
  - Test `tests/workflow_core/test_stage_handoff.py`
- **Interfaces**:
  - Produces the line form `Next: /clear, then <command>` that `gin prime`'s `Next:` matches; no code interface.
- **Provider role**: `general`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** exact text edits given below; the middle model checks the measured budgets, since the plan chain keeps only about 24 characters of room.
- **Acceptance criteria**: `python3 -m pytest tests/workflow_core/test_stage_handoff.py tests/workflow_core/test_token_budget.py -q` passes; the plan chain measures at most 11,980 and the ship chain at most 11,950 (step 6).
- **Estimated complexity**: low

Steps:

1. Create `tests/workflow_core/test_stage_handoff.py`:

```python
"""Every stage ends with one handoff line; setup offers the Claude Code compaction point."""

from __future__ import annotations

from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src"


def read(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


class StageHandoffTests(unittest.TestCase):
    def test_the_contract_holds_the_handoff_rule(self):
        text = read("references/stage-contract.md")
        self.assertIn("## Handoff", text)
        self.assertIn("`Next: /clear, then <command>`", text)
        self.assertIn("`Next: /clear` if none", text)

    def test_orchestrate_and_ship_end_with_the_handoff_line(self):
        for skill in ("orchestrate", "ship"):
            with self.subTest(skill=skill):
                text = read(f"skills/{skill}/SKILL.md")
                self.assertIn("`Next: /clear, then /gin:execute <id-1> <id-2>`", text)
                self.assertNotIn("Next commands:", text)

    def test_orchestrate_keeps_the_goal_text(self):
        self.assertIn("`gin goal --workflow-id <workflow>`", read("skills/orchestrate/SKILL.md"))

    def test_setup_offers_the_compaction_point_only_when_unset(self):
        text = read("skills/setup/SKILL.md")
        self.assertIn("`autoCompactWindow`", text)
        self.assertIn("`200000`", text)
        self.assertIn("never change an existing value", text)
        self.assertIn("never write project settings", text)


if __name__ == "__main__":
    unittest.main()
```

2. Run `python3 -m pytest tests/workflow_core/test_stage_handoff.py -q`. Expected: three of the four fail.

3. `references/stage-contract.md`:
   - Line 11: replace "and `record shipped --workflow-id <bead> --evidence <merge commit> --actor <id>` marks it shipped after the merge." with "and `record shipped --evidence <merge commit>` marks it shipped after the merge." (the line already says to pass `--workflow-id <bead>` on every `record` call, and the Record line names `--actor`; 34 characters fewer).
   - Append at the end of the file:

```markdown

## Handoff
End the last message with one line, `Next: /clear, then <command>`: the next stage's command, as the `gin prime` card shows it; `Next: /clear` if none.
```

4. `skills/orchestrate/SKILL.md:32`: replace the line with:

```markdown
Show what `gin goal --workflow-id <workflow>` prints, verbatim: a Claude Code `/goal` (suggest auto mode) over only the tracks the agent can finish unattended, or why there is none. End with `Next: /clear, then /gin:execute <id-1> <id-2>` for the ready tracks.
```

5. `skills/ship/SKILL.md:41`: replace "and end with `Next commands:` (for example `/gin:execute <id-1> <id-2>`)." with "and end with `Next: /clear, then /gin:execute <id-1> <id-2>`."

6. `skills/setup/SKILL.md`, under "Then:", insert after step 5 (`gin hooks install`) and renumber "Report the structured result and stop." to 7:

```markdown
6. Claude Code main harness only: when `~/.claude/settings.json` has no `autoCompactWindow`, propose `200000` in one sentence: a session then compacts near 200K tokens instead of near its 1M window, and the `gin prime` card brings the workflow state back after it. Write the key only on yes, keep the file's other keys, never change an existing value, and never write project settings.
```

7. Measure: `cd plugins/gin-workflow/src/scripts && python3 -c "from pathlib import Path; from workflow_core import budget; [print(s, budget.stage_chars(Path('..').resolve(), s)) for s in budget.STAGES]"`. Expected: plan ≤ 11,980, ship ≤ 11,950, discuss ≤ 11,690, every stage ≤ 12,000 and quick ≤ 8,000. If a chain is over, shorten the Handoff sentence, never another rule, and keep the three phrases the test asserts.

8. Run `python3 -m pytest tests/workflow_core/test_stage_handoff.py tests/workflow_core/test_token_budget.py -q`. Expected: all pass.

9. Commit: `gin commit -m "feat(stages): handoff line and the autoCompactWindow proposal (gin-workflow-context-boundaries)"`.

### Track 7: Guides, changelog, and AGENTS.md
- **Dependencies**: Track 2, Track 5, Track 6
- **Files**:
  - Modify `docs/guides/claude-workflow.md:46` (session-habit bullets)
  - Modify `docs/guides/claude-workflow.vi.md:46` (the same, in Vietnamese)
  - Modify `docs/changelog.md:3-5` (an `## [Unreleased]` section above `## [3.5.4]`)
  - Modify `AGENTS.md:3` (the `bd prime` line)
- **Interfaces**:
  - Consumes the behaviour of tracks 2–6; the release renames `[Unreleased]` to the version it ships (`docs/contributing.md` Releasing, step 2).
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** documentation from the text below; the middle model writes the Vietnamese twin to the repository's register.
- **Acceptance criteria**: `gin docs check docs/guides/claude-workflow.md docs/guides/claude-workflow.vi.md docs/changelog.md` prints `ok`; `python3 -m pytest tests/workflow_core/test_docs_coverage.py tests/test_release_notes.py -q` passes; `mkdocs build --strict` passes when `mkdocs` is installed.
- **Estimated complexity**: low

Steps:

1. `docs/guides/claude-workflow.md`: replace the bullet at line 46 with these bullets:

```markdown
- Run `/clear` between stages such as `discuss`, `plan`, and `execute`. Each stage reads the spec, plan, or beads from disk, so it loses nothing, and ends with one line, `Next: /clear, then <command>`, that says what to type after the clear.
- After a start, `/clear`, a resume, or a compaction, the hooks file that `install.sh` or `install.ps1` writes runs `gin prime --hook`, which adds the state card to the context: the workflow, its stage and gates, the spec and plan, the ready tracks, the open questions, the next command, and the Beads memories. A session not yet bound to a workflow gets the one last worked on in the same folder, or a list of the open ones. See [`gin prime`](../reference/cli.md#gin-prime). A plugin installed only from the marketplace has no such hook.
- Before a compaction, the `PreCompact` hook runs `gin prime --pre-compact`, which tells the summary to keep the decisions and answers given in chat word for word.
- The card carries the Beads memories, so neither `bd prime` nor a `bd setup claude` hook is needed at session start; `bd prime --no-memories` prints the Beads command reference.
- `/gin:setup` offers `autoCompactWindow: 200000` in `~/.claude/settings.json` when the key is not set, so a session compacts near 200K tokens instead of near its 1M window.
```

2. `docs/guides/claude-workflow.vi.md`: replace the bullet at line 46 with:

```markdown
- Chạy `/clear` giữa các stage như `discuss`, `plan`, và `execute`. Mỗi stage đọc spec, plan, hoặc bead từ đĩa, nên không mất gì, và kết thúc bằng một dòng `Next: /clear, then <command>` cho biết cần gõ gì sau khi clear.
- Sau khi bắt đầu phiên, `/clear`, resume, hoặc compaction, file hooks do `install.sh` hoặc `install.ps1` tạo chạy `gin prime --hook`, lệnh này đưa state card vào context: workflow, stage và các gate, spec và plan, các track sẵn sàng, câu hỏi còn mở, lệnh tiếp theo, và Beads memories. Một session chưa gắn với workflow nào sẽ nhận workflow làm gần nhất trong cùng thư mục, hoặc danh sách các workflow đang mở. Xem [`gin prime`](../reference/cli.md#gin-prime). Plugin chỉ cài từ marketplace không có hook này.
- Trước khi compaction, hook `PreCompact` chạy `gin prime --pre-compact`, yêu cầu bản tóm tắt giữ nguyên văn các quyết định và câu trả lời đã đưa ra trong chat.
- Card đã mang Beads memories, nên không cần `bd prime` hay hook của `bd setup claude` khi bắt đầu phiên; `bd prime --no-memories` in phần tham chiếu lệnh Beads.
- `/gin:setup` đề xuất `autoCompactWindow: 200000` trong `~/.claude/settings.json` khi key này chưa có, để session compact ở khoảng 200K token thay vì gần cửa sổ 1M.
```

3. `docs/changelog.md`: insert above `## [3.5.4] - 2026-11-27`:

```markdown
## [Unreleased]

### Upgrade notes

- Run `./install.sh` (or `install.ps1` on Windows) again on each machine: the Claude Code hooks file gains the `SessionStart` and `PreCompact` entries that run `gin prime`.
- A `bd prime` hook installed by `bd setup claude` can go: the card already carries the Beads memories.

### Added

- `gin prime` prints a state card of at most 9,500 characters: workflow, stage, gates, spec and plan, ready tracks, open questions, review cycles, the next command, other open workflows, the Beads memories, and in team mode the member, claimed lane, and waiting pull requests.
- The Claude Code hooks file runs `gin prime --hook` on start, `/clear`, resume, and compaction, and `gin prime --pre-compact` before a compaction, on Linux, macOS, and Windows.
- Each stage ends with `Next: /clear, then <command>`.
- `/gin:setup` offers `autoCompactWindow: 200000` for Claude Code.
- `session.bound` events carry `cwd`, the git top level the command ran in.
```

4. `AGENTS.md:3`: replace "Run `bd prime` at session start when Beads context is missing or stale." with "On Claude Code, the `gin prime` card at session start carries the Beads memories; run `bd prime --no-memories` for the Beads command reference, or `bd prime` when Beads context is missing or stale elsewhere."

5. Run `gin docs check docs/guides/claude-workflow.md docs/guides/claude-workflow.vi.md docs/changelog.md` and `python3 -m pytest tests/workflow_core/test_docs_coverage.py tests/test_release_notes.py -q`. Expected: `ok` and all pass.

6. Commit: `gin commit -m "docs: state card, handoff line, and autoCompactWindow (gin-workflow-context-boundaries)"`.

## Integration
- **Branch**: `feat/context-boundaries`
- **Merge strategy**: parallel-then-merge (tracks 1, 5, and 6 in parallel worktrees; 2 → 3 → 4 in sequence; 7 last)

## Validation
- [ ] `python3 -m pytest -n auto` passes.
- [ ] `bash tests/install_smoke_test.sh` passes; the Windows smoke test runs on CI by request (`gh workflow run test.yml --ref feat/context-boundaries`).
- [ ] `gin docs check` passes on every changed page.
- [ ] After `./install.sh --platform claude`: a new session in this worktree shows the card; `/clear` shows the card of `gin-workflow-context-boundaries`; a session in `/tmp` adds nothing.
- [ ] Ship note: card size and `gin prime --hook` time on this repository before and after (target under 3 s); the median main-session context of the first sessions with the hooks against the 293K baseline.
- [ ] Ship note: team behaviour checked on the team's project before the release that carries it (requirement 20).

## Notes
- The Parent Bead `gin-workflow-context-boundaries` stays open until the human-confirmed merge; track beads close once their tests and review pass.
- The user may override `Model:` and `Effort:` before plan approval.

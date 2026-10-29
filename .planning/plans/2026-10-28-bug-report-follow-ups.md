# Plan: gin-workflow 2.8 bug report follow-ups

Epic: gin-workflow-5c4y
Spec: `.planning/specs/2026-10-28-bug-report-follow-ups-design.md`

## Objective

Items 5–7 of the gin-workflow 2.8 bug report are fixed. In team mode, `gin-workflow task close` accepts the bead its member claimed. `team check-plan` checks exactly the files in each track's Files block. A failed `gin-workflow record` says that the gate was not recorded. The `orchestrate` skill creates track beads before it writes the routes file.

## Goal

Fix three independent defects, one track each, mapped to the existing child beads of epic `gin-workflow-5c4y`: Track 1 → `gin-workflow-4nj0`, Track 2 → `gin-workflow-83nh`, Track 3 → `gin-workflow-1zos`.

## Architecture

- `workflow_core/tasks.py::main` passes `gin-workflow task …` to `bd`. A new helper `_bd_env` sets `BD_ACTOR` to the team member's email in team mode, the identity `team claim` already uses (`team_beads._bd`).
- `workflow_core/team.py::plan_tracks` collects files only from a track's Files block, through a new helper `_listed_paths`. `check_plan` is unchanged and consumes `Track.files`.
- `workflow_core/lifecycle_cli.py::_record_command` turns a failed event append into an error payload with exit 1.
- `skills/orchestrate/SKILL.md` swaps its routes step and its bead-creation step.

## Tech Stack

Python 3 stdlib (`os`, `re`, `subprocess`, `contextlib`, `io`), unittest, Markdown skill and docs files.

## Global Constraints

Copied from the spec:
- R1 only adds an environment variable for bd; an explicit `--actor` wins in bd, and an existing `BD_ACTOR` is kept.
- R2 can make `team check-plan` report area violations that the old parser missed in plan-schema-format plans. That is the intended fix; existing fixture-format plans parse the same.
- R3 changes a traceback into exit 1 with a message; successful records are unchanged.
- Out of scope: the two `stage` keys of `gin-workflow state --format json`; the bd error text "reclaim or use --force to override"; the markdown task backend.

Repository rules: Python stdlib only; follow existing patterns; no commits on `master`.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `implement`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: Use `high_reasoning` for planning only when execution boundaries, dependency sequencing, or major tradeoffs are still unresolved.

## Requirement Analysis
- Problem statement: see the spec's R1–R3.
- Success criteria: the spec's US-1 to US-3 acceptance criteria, proven by the tests in each track and the full suite.
- Constraints: Global Constraints above.
- Non-goals: the spec's out-of-scope list.

## Approach Options
### Option 1: one track per requirement
- Summary: three independent tracks with disjoint files.
- Pros: each track is reviewed and closed on its own; any order works.
- Cons: three review cycles.

### Option 2: one track for everything
- Summary: a single track for R1–R3.
- Pros: one review.
- Cons: three unrelated changes in one review; one rejection blocks all.

### Recommended Approach
- Selected option: Option 1.
- Reasoning: the beads already exist one per requirement, and the files do not overlap.

## Scope
- In scope: R1, R2, R3 of the spec.
- Out of scope: the spec's out-of-scope list.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Three small independent tracks with disjoint files; one session runs them in order.
```

## Tasks

### Track 1: `gin-workflow task` runs bd as the team member
- **Dependencies**: none
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Model guidance**: `standard_impl`
- **Estimated complexity**: low
- **Bead**: `gin-workflow-4nj0`
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/tasks.py:159-175` (`main`; new `_bd_env` above it)
  - Test `tests/workflow_core/test_tasks.py:53-60` (`test_beads_passes_argv_through_to_bd_unchanged`; new class `TeamActorTests` before `if __name__`)
- **Interfaces produced**: `workflow_core.tasks._bd_env(root: Path, argv: Sequence[str]) -> dict[str, str] | None`, the environment for bd, or None to keep the current one.
- **Interfaces consumed**: `workflow_core.team.team_for_repo(root: Path) -> TeamConfig | None`, `workflow_core.team.current_member(root: Path, team: TeamConfig) -> Member | None`, `Member.email: str`.
- **Acceptance criteria**: US-1 of the spec; the new and updated tests pass; the full suite passes.
- **Steps**:
  1. In `tests/workflow_core/test_tasks.py`, add `from tests.workflow_core.team_fixtures import make_team_repo  # noqa: E402` after the `from workflow_core.configuration import …` line. `test_beads_passes_argv_through_to_bd_unchanged` mocks `subprocess.run` process-wide, which `team_for_repo` also reaches (through `checkout.main_checkout`), so the test pins it outside team mode. Replace its body with:
     ```python
             argv = ["update", "x-1", "--status", "in_progress", "--json"]
             with mock.patch("workflow_core.tasks.backend", return_value="beads"), \
                     mock.patch("workflow_core.team.team_for_repo", return_value=None), \
                     mock.patch("workflow_core.tasks.shutil.which", return_value="/opt/bd"), \
                     mock.patch("workflow_core.tasks.subprocess.run",
                                return_value=subprocess.CompletedProcess([], 7)) as run:
                 self.assertEqual(7, tasks.main(argv))
             run.assert_called_once_with(["/opt/bd", *argv], check=False, env=None)
     ```
     Then add before `if __name__ == "__main__":`:
     ```python
     class TeamActorTests(unittest.TestCase):
         """In team mode bd acts as the member's email, the identity `team claim` assigns."""

         def setUp(self):
             directory = tempfile.TemporaryDirectory()
             self.addCleanup(directory.cleanup)
             self.base = Path(directory.name)
             self.bd = self.base / "bd"
             self.bd.write_text(f"#!{sys.executable}\nimport os, pathlib\n"
                                "pathlib.Path(__file__).with_name('actor.txt').write_text("
                                "os.environ.get('BD_ACTOR', '<unset>'))\n", encoding="utf-8")
             self.bd.chmod(0o755)
             cwd = os.getcwd()
             self.addCleanup(os.chdir, cwd)

         def actor(self, argv, *, team=None, email="binh@corp.com", preset=None):
             root = make_team_repo(self.base / f"repo-{len(list(self.base.glob('repo-*')))}", email=email, team=team)
             os.chdir(root)
             environ = {key: value for key, value in os.environ.items() if key != "BD_ACTOR"}
             if preset is not None:
                 environ["BD_ACTOR"] = preset
             with mock.patch.dict(os.environ, environ, clear=True), \
                     mock.patch("workflow_core.tasks.backend", return_value="beads"), \
                     mock.patch("workflow_core.tasks.shutil.which", return_value=str(self.bd)):
                 self.assertEqual(0, tasks.main(argv))
             return (self.base / "actor.txt").read_text(encoding="utf-8")

         def test_member_email_is_the_bd_actor(self):
             self.assertEqual("binh@corp.com", self.actor(["close", "x-1", "--reason", "done"]))

         def test_explicit_actor_is_kept(self):
             self.assertEqual("<unset>", self.actor(["close", "x-1", "--actor", "someone"]))
             self.assertEqual("<unset>", self.actor(["close", "x-1", "--actor=someone"]))
             self.assertEqual("preset", self.actor(["close", "x-1"], preset="preset"))

         def test_non_member_or_no_team_leaves_bd_alone(self):
             self.assertEqual("<unset>", self.actor(["close", "x-1"], email="outsider@corp.com"))
             self.assertEqual("<unset>", self.actor(["close", "x-1"], team="providers:\n  task_tracking: beads\n"))
     ```
  2. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_tasks`. Expected: failures in `test_beads_passes_argv_through_to_bd_unchanged` (no `env` keyword) and `test_member_email_is_the_bd_actor` (`<unset>`).
  3. In `tasks.py`, add above `def main`:
     ```python
     def _bd_env(root: Path, argv: Sequence[str]) -> dict[str, str] | None:
         """In team mode bd acts as the member's email, as `team claim` does, unless an actor is already given."""
         if "BD_ACTOR" in os.environ or any(arg == "--actor" or arg.startswith("--actor=") for arg in argv):
             return None
         from .team import current_member, team_for_repo

         team = team_for_repo(root)
         member = current_member(root, team) if team is not None else None
         return None if member is None else {**os.environ, "BD_ACTOR": member.email}
     ```
     and change the last line of `main` to:
     ```python
         return subprocess.run([executable, *argv], check=False, env=_bd_env(root, argv)).returncode
     ```
  4. Run the command of step 2. Expected: `OK`.
  5. Commit: `fix(tasks): run bd as the team member so task close accepts the claimed bead` with `Refs: gin-workflow-4nj0`.

### Track 2: `team check-plan` reads files only from the Files block
- **Dependencies**: none
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Model guidance**: `standard_impl`
- **Estimated complexity**: medium
- **Bead**: `gin-workflow-83nh`
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py:177-220` (`_FILES_LINE`, `_BACKTICK`, `plan_tracks`)
  - Modify `plugins/gin-workflow/src/skills/plan/plan-schema.md:60` (the `**Files**` line)
  - Modify `docs/reference/cli.md:157` (the `check-plan PLAN` row)
  - Test `tests/workflow_core/test_team_gates.py:366-420` (class `TestPlanChecks`)
- **Interfaces produced**: `workflow_core.team._listed_paths(text: str) -> list[str]`; `plan_tracks(path: Path) -> list[Track]` keeps its signature.
- **Interfaces consumed**: `Track`, `_TRACK`, `_META`, `_FENCE` in `team.py`.
- **Acceptance criteria**: US-2 of the spec; existing `TestPlanChecks` tests unchanged and passing; the full suite passes.
- **Steps**:
  1. In `tests/workflow_core/test_team_gates.py`, add to class `TestPlanChecks` after `test_fenced_code_is_not_a_track`:
     ```python
         def test_behavior_bullets_outside_files_are_not_files(self):
             plan = PLAN.replace("- Modify: `web/login.tsx:10-20`\n",
                                 "- Modify: `web/login.tsx:10-20`\n\n**Steps:**\n"
                                 "   - **Modify:** the row's button opens \"...\" filled from `GET /:id`, then saves\n")
             path = write(self.root, PLAN_PATH, plan)
             self.assertEqual(("web/login.tsx",), plan_tracks(path)[1].files)
             self.assertEqual([], check_plan(self.team, path))

         def test_plan_schema_files_block_ignores_notes(self):
             plan = ("# Plan: Login\n\n## Tasks\n\n### Track 1: API\n- **Area**: backend\n- **Owner**: em@corp.com\n"
                     "- **Files**:\n  - Create `services/auth/login.py`\n"
                     "  - Modify `services/auth/session.py:10-20` (the `refresh` helper next to `web/shared.ts`)\n"
                     "  - Test `tests/services/test_login.py`, `tests/services/test_session.py`\n"
                     "- **Acceptance criteria**: `web/login.tsx` is untouched\n\n## Integration\n")
             path = write(self.root, PLAN_PATH, plan)
             self.assertEqual(("services/auth/login.py", "services/auth/session.py",
                               "tests/services/test_login.py", "tests/services/test_session.py"),
                              plan_tracks(path)[0].files)
             self.assertEqual([], check_plan(self.team, path))
     ```
  2. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_team_gates`. Expected: the two new tests fail (the first lists `GET /:id`, the second lists only the `Test` paths or none).
  3. In `team.py`, replace the `_FILES_LINE` and `_BACKTICK` definitions with:
     ```python
     _FILES_LABEL = re.compile(r"^(-\s*)?(?:\*\*)?Files(?:\*\*)?:(?:\*\*)?\s*(.*)$")
     _VERB = re.compile(r"^(?:Create|Modify|Test|Delete)\b:?\s*")
     _PATH = re.compile(r"`([^`\s]+)`")
     ```
     keep `_FENCE`, and add after it:
     ```python
     def _listed_paths(text: str) -> list[str]:
         """The leading comma-separated backticked paths of a Files entry, after an optional verb; line ranges dropped."""
         rest = _VERB.sub("", text.strip(), count=1)
         paths: list[str] = []
         while token := _PATH.match(rest):
             paths.append(re.sub(r":\d[\d,-]*$", "", token.group(1)))
             rest = rest[token.end():].lstrip()
             if not rest.startswith(","):
                 break
             rest = rest[1:].lstrip()
         return paths
     ```
     Replace `plan_tracks` with:
     ```python
     def plan_tracks(path: Path) -> list[Track]:
         """`### Track N:` sections with their Area, Owner, and the paths listed in their Files block; fenced code is
         skipped."""
         tracks: list[Track] = []
         current: dict[str, Any] | None = None
         fence = ""
         files_indent: int | None = None  # indent of the open Files label; -1 when the label is not a list item

         def close() -> None:
             if current is not None:
                 tracks.append(Track(current["number"], current["title"], current["area"], current["owner"],
                                     tuple(dict.fromkeys(current["files"]))))

         for line in Path(path).read_text(encoding="utf-8").splitlines():
             opener = _FENCE.match(line)
             if fence:
                 fence = "" if line.strip() == fence else fence
                 continue
             if opener:
                 fence, files_indent = opener.group(1), None
                 continue
             heading = _TRACK.match(line)
             if heading or (current is not None and line.startswith("## ")):
                 close()
                 current = None if not heading else {"number": int(heading.group(1)), "title": heading.group(2).strip(),
                                                      "area": "", "owner": "", "files": []}
                 files_indent = None
                 continue
             if current is None:
                 continue
             stripped = line.strip()
             indent = len(line) - len(line.lstrip())
             if files_indent is not None and stripped.startswith("- ") and indent > files_indent:
                 current["files"] += _listed_paths(stripped[2:])
                 continue
             files_indent = None
             meta = _META.match(stripped)
             if meta:
                 current[meta.group(1).lower()] = meta.group(2)
                 continue
             label = _FILES_LABEL.match(stripped)
             if label:
                 files_indent = indent if label.group(1) else -1
                 current["files"] += _listed_paths(label.group(2))
         close()
         return tracks
     ```
  4. Run the command of step 2. Expected: `OK` (the existing `test_plan_tracks_reads_area_owner_and_files` and `test_check_plan_findings` still pass).
  5. In `plan-schema.md`, replace line `- **Files**: list of files to modify` with:
     ```markdown
     - **Files**: one entry per file, indented under this label. `team check-plan` reads files only from this block: the leading backticked paths of each entry (comma-separated), after an optional `Create`, `Modify`, `Test`, or `Delete`; notes after them are ignored.
       - Create `path/to/new_file.py`
       - Modify `path/to/existing.py:10-40` (what changes)
       - Test `tests/path/test_file.py`
     ```
  6. In `docs/reference/cli.md`, replace the row `` | `check-plan PLAN` | Check a plan's `Area:` and `Owner:` fields | `` with:
     ```markdown
     | `check-plan PLAN` | Check a plan's `Area:` and `Owner:` fields, and that the paths in each track's `Files` block stay inside its area |
     ```
  7. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_team_gates tests.workflow_core.test_assignments`. Expected: `OK` (`test_assignments` reads `plan-schema.md`).
  8. Commit: `fix(team): check-plan reads files only from each track's Files block` with `Refs: gin-workflow-83nh`.

### Track 3: `record` reports an unwritten gate; `orchestrate` creates beads before routes
- **Dependencies**: none
- **Provider role**: `backend`
- **Reasoning**: `low`
- **Model guidance**: `cheap_simple`
- **Estimated complexity**: low
- **Bead**: `gin-workflow-1zos`
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:13` (events import) and `:196` (`store.append`)
  - Modify `plugins/gin-workflow/src/skills/orchestrate/SKILL.md:19-22` (steps 3 and 4)
  - Test `tests/workflow_core/test_lifecycle_cli.py:3-14` (imports; new test after `test_record_is_idempotent_for_same_evidence`)
  - Test `tests/workflow_core/test_assignments.py:53-57` (step-order assertion)
- **Interfaces produced**: record error payload `{"status": "error", "message": "<gate> not recorded for <workflow-id>: <error>"}`, exit code 1.
- **Interfaces consumed**: `workflow_core.events.EventPersistenceError`, `WorkflowEventStore.append(event) -> bool`.
- **Acceptance criteria**: US-3 of the spec; the new and updated tests pass; the full suite passes.
- **Steps**:
  1. In `tests/workflow_core/test_lifecycle_cli.py`, add `import contextlib` and `import io` to the stdlib imports and `from unittest import mock` after `import unittest`, change the events import to `from workflow_core.events import EventPersistenceError, WorkflowEvent, WorkflowEventStore`, and add after `test_record_is_idempotent_for_same_evidence`:
     ```python
         def test_record_reports_an_unwritten_gate(self):
             args = ["record", "plan-approved", "--repository", str(self.repo_path),
                     "--evidence", "plan.md", "--actor", "user"]
             for error in (EventPersistenceError("cannot lock events"), RuntimeError("atomic write failed"),
                           PermissionError(13, "denied")):
                 with self.subTest(error=type(error).__name__), \
                         mock.patch("workflow_core.lifecycle_cli.WorkflowEventStore.append", side_effect=error), \
                         contextlib.redirect_stderr(io.StringIO()) as stderr:
                     self.assertEqual(1, cli_main(args))
                 self.assertIn("error: plan-approved not recorded for default-workflow: ", stderr.getvalue())
             self.assertEqual("unmet", self._state_gates()["plan_approved"])
     ```
  2. In `tests/workflow_core/test_assignments.py`, replace the comment and assertion
     ```python
             # Verify route resolution step comes before task creation in orchestrate skill
             route_token = "routes resolve" if "routes resolve" in orchestrate else "resolve_all_assignments"
             self.assertLess(
                 orchestrate.index(route_token),
                 orchestrate.index("gin-workflow task create"),
             )
     ```
     with
     ```python
             # Track beads are created before routes resolve, so the routes file is keyed by their real ids
             self.assertLess(
                 orchestrate.index("gin-workflow task create"),
                 orchestrate.index("routes resolve"),
             )
     ```
  3. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_lifecycle_cli tests.workflow_core.test_assignments`. Expected: `test_record_reports_an_unwritten_gate` fails with an uncaught error, and the step-order test fails.
  4. In `lifecycle_cli.py`, change line 13 to `from .events import EventPersistenceError, WorkflowEvent, WorkflowEventStore` and replace `    appended = store.append(event)` with:
     ```python
         try:
             appended = store.append(event)
         except (EventPersistenceError, RuntimeError, OSError) as error:
             return {"status": "error", "message": f"{args.gate} not recorded for {args.workflow_id}: {error}"}, 1
     ```
  5. In `skills/orchestrate/SKILL.md`, replace steps 3 and 4 (lines 19–22) with:
     ```markdown
     3. Distinguish Parent Bead (Deliverable) vs Track Beads (Work Units), and create the track beads now; their ids key the routes in step 4:
        - **Parent Bead (Deliverable / Epic)**: the overall deliverable. Merge holds such as "remain open until human-confirmed merge" belong only here.
        - **Track Beads (Work Units)**: one per plan track (`gin-workflow task create --parent <epic>`). Acceptance criteria are strictly technical (in-scope code, tests, review approval). Never copy parent merge holds into tracks. A track whose plan entry has a `Human gate:` line gets `--labels human-gate`.
     4. Write the tracks as a JSON list of `{"task_id", "provider_role", "reasoning"}`, with `task_id` the track bead id created in step 3, to `.agent-workflow/runtime/routes-<workflow>.json` and run `gin-workflow routes resolve --workflow-id <workflow> --tracks <file> --json`. Exit 2 lists every diagnostic; report them all and stop (after fixing the configuration, run it again; the beads stay). It writes the assignment manifest only when every track resolves. Concrete provider/model names never enter Beads or the plan.
     ```
  6. Run the command of step 3. Expected: `OK`.
  7. Commit: `fix(record): say when a gate was not recorded; orchestrate creates beads before routes` with `Refs: gin-workflow-1zos`.

## Integration
- **Branch**: `fix/bug-report-follow-ups`
- **Merge strategy**: sequential

## Validation
- [ ] Each track's focused test command passes.
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all` passes.
- [ ] `git grep -n "_FILES_LINE\|_BACKTICK"` matches nothing.

## Notes
- Model guidance is planning metadata, not Beads state.
- Tracks close after tests and review pass. The parent epic `gin-workflow-5c4y` stays open until a human-confirmed merge.

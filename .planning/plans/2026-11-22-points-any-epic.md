# Plan: Story points for every epic through `gin points`

Epic: gin-workflow-05e5
Spec: `.planning/specs/2026-11-22-points-any-epic-design.md`

## Objective

`gin points EPIC N --reason TEXT [--stage roadmap|discuss|close]` sets the story points of any open epic; `gin milestone points` forwards to it. `/discuss` scores every workflow into a `Points:` line of its spec, reviewed with the spec, and the score reaches the epic once the gate is recorded and the epic exists (`/orchestrate` copies it for an epic it creates). `days_per_point` and the malformed-points warning cover every epic.

## Global Constraints

Copied from the spec:

- The `--stage` values stay `roadmap|discuss|close` and the default stays `roadmap`, so `gin milestone points` without `--stage` writes the same history as today.
- `story-points.md` stays under `skills/roadmap/references/`; `/orchestrate` links it the way `/discuss` does (`../roadmap/references/story-points.md`).
- The `Points:` line is read by the agent, as the roadmap's `Points:` lines are; no code parses it and `gin specs lint` does not check it.
- In team mode `gin points` follows `team.permissions.milestone`, as `gin milestone points` does today; no new permission key.
- Out of scope: points on tracks or tasks; the forecast and the `unassigned roadmap epics` count of `gin milestone list`; `velocity`; gin-console; the `/discuss` paragraph headed **Roadmap epic**.
- The JSON of `gin milestone list` and `show` keeps its keys and `schema: 1`.
- A refusal by `gin points` inside `/discuss` or `/orchestrate` never blocks the stage.

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
- Problem statement: `gin milestone points` refuses an epic without the `roadmap` label (`milestone_cli.py:397-398`), so `/discuss <epic>` cannot record a score for 90 of the 129 epics in this repository, and epics created by `/orchestrate` or the SDD discuss are never scored.
- Success criteria: US-1 and US-3 of the spec pass as tests; US-2 holds by the skill text tests and the manual runs under Validation; the existing milestone, specs, skill routing, token budget, and docs tests stay green.
- Constraints: the Global Constraints above. Size budgets (`tests/workflow_core/test_token_budget.py`), measured today: the `discuss` stage chain 11,277 of 12,000 characters, `orchestrate` 8,610 of 12,000, `skills/roadmap/SKILL.md` 11,794 of 12,000, `story-points.md` 2,315 of 4,000, `milestone-plan.md` 3,540 of 4,000, `skills/sdd/SKILL.md` 5,990 of 6,000. A stage `SKILL.md` keeps at most 2 lines containing `sdd` and exactly 1 containing `project.team` (`test_token_budget.py:150-175`).
- Non-goals: see Global Constraints.

## Approach Options
### Option 1: `points_cli.py` reusing the milestone write path
- Summary: a new module holds the `gin points` parser, `_points`, and `_trace_points` (moved from `milestone_cli.py`, with the label check replaced by an epic check). `milestone_cli._write` gains an optional `write` callable so `gin points` reuses its role guard, pull, push, and print. `milestone_cli.main` forwards `points ...` to `points_cli.main` before parsing.
- Pros: one implementation of the guard and push; `gin points` has its own usage and `points error:` prefix; no import cycle (the forward is a lazy import).
- Cons: `points_cli` calls three private helpers of `milestone_cli` (`_bd`, `_config`, `_write`).

### Option 2: route `gin points` to `gin milestone points` in `cli.py`
- Summary: five lines in `cli.py`; drop the label check in `_points`.
- Pros: the smallest diff.
- Cons: usage and errors read `gin milestone` and `milestone error:`; rejected at discuss (the user chose a module of its own).

### Recommended Approach
- Selected option: Option 1, as confirmed in discuss.
- Rationale: the guard, pull, and push stay in one place, and `milestone_cli._bd` is looked up at call time, so existing `mock.patch.object(milestone_cli, "_bd")` patches keep working.

Decisions this plan takes against the spec text, for the user to confirm with the plan:
- `docs/changelog.md` is not edited. `docs/contributing.md:115` writes the changelog at release time from the closed epics, and the epics closed after 3.4.0 (gin-workflow-6yoq, gin-workflow-bryf) did not touch it. Spec R5 listed it.
- The points tests stay in `tests/workflow_core/test_milestone_cli.py` instead of a new `test_points_cli.py` (spec Testing). Their bd fixtures (`seed_writes`, `refused`, `beads_store`, the cached `.beads`) live in that file's classes; a new file would copy them.
- `skills/sdd/SKILL.md` is not edited: it has 10 characters of budget left. The rule reaches the SDD layout through a `/discuss` paragraph that applies to every layout and through `story-points.md`.

## Scope
- In scope: `workflow_core/points_cli.py` (new), `milestone_cli.py`, `milestone.py`, `cli.py`; the skills `discuss`, `orchestrate`, `roadmap` (`SKILL.md`, `references/story-points.md`, `references/milestone-plan.md`), `milestone-close`; the templates `design-spec.md`, `technical-design.md`, `proposal.md`; `docs/reference/cli.md`, `docs/reference/config.md`, `docs/guides/team.md`, `docs/concepts/lifecycle.md`, `docs/starters/brownfield.md`, `docs/starters/brownfield.vi.md`; tests `test_milestone.py`, `test_milestone_cli.py`, `test_skill_routing.py`, `test_specs.py`.
- Out of scope: `docs/changelog.md` (release time); `.planning/knowledge/story-points.md` (updated at ship by `learn`); `plugins/gin-workflow/dist/` (built by `install.sh`, not tracked); `skills/sdd/SKILL.md`, `skills/team/SKILL.md`.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 names the command Track 1 adds; two tracks on one branch, solo work.
```

## Tasks

### Track 1: `gin points`, the alias, and the pace over every epic
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/points_cli.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:13` (import `Callable`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:59-63` (remove the `points` subparser)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:170-179` (warning for every open epic)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:371` (`estimate` message names `gin points`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:376-409` (remove `_trace_points` and `_points`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:421-422` (remove `"points"` from `WRITES`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:445-457` (`_write` takes `write`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:486-492` (`main` forwards `points`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:117-122` (`measure_pace` without the label filter)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/cli.py:13-15` (`points` in `TOP_COMMANDS`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/cli.py:191-193` (dispatch `points`)
  - Modify `docs/reference/cli.md:216-254` (new gin points section, alias row, days_per_point text, estimate row)
  - Modify `docs/reference/config.md:181` (`permissions.milestone` also governs `gin points`)
  - Modify `docs/guides/team.md:101` (same)
  - Test `tests/workflow_core/test_milestone.py`
  - Test `tests/workflow_core/test_milestone_cli.py`
- **Interfaces**:
  - Produced: `gin points EPIC N --reason TEXT [--stage roadmap|discuss|close] [--repository PATH]` printing `points of <epic> set to <n>`; `points_cli.main(arguments: Sequence[str]) -> int`; `points_cli._points(root, args, beads, actor) -> tuple[str, str]`; `points_cli._trace_points(root, bead, epic, to: int, stage: str, actor: str) -> None`; `milestone_cli._write(root, config, args, write: Callable[..., tuple[str, str]] | None = None) -> int`.
  - Consumed: `milestone_cli._bd`, `milestone_cli._config`, `milestone_cli.MilestoneError`, `milestone_cli.Denied`, `milestone.POINT_SCALE`, `milestone.points_of`, `workspace.repository_root`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change to three modules of one package with the code given below; the edge cases are the existing refusals, which keep their messages.
- **Acceptance criteria**: US-1 and US-3 of the spec pass as the tests below; `python3 -m pytest tests/workflow_core/test_milestone.py tests/workflow_core/test_milestone_cli.py tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_rename_sweep.py -q` passes.
- **Estimated complexity**: medium

Steps:

1. Write the failing tests.

   In `tests/workflow_core/test_milestone.py`, class `PointsTests`, after `test_us2_pace_assumed_from_the_roadmap_then_one`:

   ```python
       def test_pace_counts_epics_without_the_roadmap_label(self):
           plain = bead("A", status="closed", meta={"points": 5}, started_at="2026-11-02T09:00:00Z",
                        closed_at="2026-11-13T17:00:00Z")
           beads = world(plain, done("B", 5, "2026-11-16", "2026-11-20"))
           self.assertEqual(milestone.Pace(1.5, 2, False), milestone.measure_pace(beads, None, TODAY))

       def test_forecast_leaves_out_open_epics_without_the_roadmap_label(self):
           beads = world(bead("X", meta={"points": 3}))
           self.assertIsNone(milestone.forecast(beads, TODAY, milestone.Roadmap(), 1))
           self.assertEqual(0, milestone.list_payload(beads, TODAY, False, milestone.Roadmap(), 1)["unassigned_epics"])
   ```

   In `tests/workflow_core/test_milestone_cli.py`:
   - line 19: `from workflow_core import milestone, milestone_cli, points_cli, team_beads  # noqa: E402`
   - in `MilestoneCliTests`, after `run_cli`:

     ```python
         def run_points(self, *argv):
             out, err = io.StringIO(), io.StringIO()
             with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                 code = points_cli.main([*argv, "--repository", str(self.root)])
             return code, out.getvalue(), err.getvalue()

         def history(self, bead_id):
             stored = self.metadata(bead_id)["points_history"]
             stored = json.loads(stored) if isinstance(stored, str) else stored
             return [[entry["from"], entry["to"], entry["stage"]] for entry in stored]
     ```
   - in `test_us1_points_refusals_write_nothing`, delete the line `self.refused("points", "t-ac", "5", "--reason", "x")`: `t-ac` has no `roadmap` label and is now accepted.
   - in `test_us2_estimate_refused_once_points_exist`, replace `"gin milestone points"` with `"gin points"`.
   - after `test_show_and_list_report_points_and_pace`:

     ```python
         def test_points_accept_any_open_epic(self):
             self.seed_writes()
             code, out, err = self.run_points("t-e0", "5", "--reason", "3 stories")
             self.assertEqual(0, code, err)
             self.assertIn("points of t-e0 set to 5", out)
             meta = self.metadata("t-e0")
             self.assertEqual(("5", "3 stories"), (str(meta["points"]), meta["points_reason"]))
             self.assertEqual(0, self.run_points("t-e0", "8", "--reason", "x", "--stage", "discuss")[0])
             self.assertEqual([[None, 5, "roadmap"], [5, 8, "discuss"]], self.history("t-e0"))
             self.assertEqual(0, self.run_points("t-ac", "3", "--reason", "x")[0])

         def test_points_refuse_a_bead_that_is_not_an_epic(self):
             self.seed_writes()
             before = beads_store(self.root)
             code, _, err = self.run_points("t-task", "5", "--reason", "x")
             self.assertEqual(1, code)
             self.assertIn("points error: t-task is not an epic", err)
             self.assertEqual(before, beads_store(self.root))

         def test_milestone_points_is_an_alias_of_gin_points(self):
             self.seed_writes()
             self.assertEqual((0, "points of t-e0 set to 5\n"),
                              self.run_points("t-e0", "5", "--reason", "x", "--stage", "discuss")[:2])
             self.assertEqual((0, "points of t-x set to 5\n"),
                              self.run_cli("points", "t-x", "5", "--reason", "x", "--stage", "discuss")[:2])
             for epic in ("t-e0", "t-x"):
                 meta = self.metadata(epic)
                 self.assertEqual(("5", "x", [[None, 5, "discuss"]]),
                                  (str(meta["points"]), meta["points_reason"], self.history(epic)))
             self.assertIn("points error: t-task is not an epic", self.refused("points", "t-task", "5", "--reason", "x"))

         def test_gin_points_is_a_top_command(self):
             self.seed_writes()
             done = gw(self.root, "points", "t-e0", "3", "--reason", "x")
             self.assertEqual(0, done.returncode, done.stderr)
             self.assertIn("points of t-e0 set to 3", done.stdout)
     ```
   - in `MilestoneTeamTests`, after `test_req_012_milestone_writes_need_a_permitted_role`:

     ```python
         def test_points_need_a_permitted_role(self):
             root = self.repo("dev", "em@corp.com")
             self.bd(root, "create", "E", "--id", "t-e", "--type", "epic")
             err = io.StringIO()
             with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                 code = points_cli.main(["t-e", "5", "--reason", "x", "--repository", str(root)])
             self.assertEqual(2, code)
             self.assertIn("ba", err.getvalue())
             self.assertNotIn("points", self.metadata(root, "t-e") or {})
     ```
   - a new class after `ShowTextTests` (no bd needed, so no skip guard):

     ```python
     class MalformedPointsWarningTests(unittest.TestCase):
         def test_open_epic_without_the_roadmap_label_is_warned(self):
             err = io.StringIO()
             with contextlib.redirect_stderr(err):
                 milestone_cli._warn_malformed_metadata([
                     {"id": "e1", "issue_type": "epic", "status": "open", "labels": [], "metadata": {"points": "4"}},
                     {"id": "e2", "issue_type": "epic", "status": "closed", "labels": [], "metadata": {"points": "4"}}])
             self.assertEqual("warning: e1: malformed points metadata ignored\n", err.getvalue())
     ```

2. Run `python3 -m pytest tests/workflow_core/test_milestone.py tests/workflow_core/test_milestone_cli.py -q`. Expected: `test_milestone_cli.py` fails to import (`cannot import name 'points_cli'`); in `test_milestone.py`, `test_pace_counts_epics_without_the_roadmap_label` fails with `Pace(value=1.0, measured_epics=1, ...)`, and `test_forecast_leaves_out_open_epics_without_the_roadmap_label` passes (it guards behaviour that must not change).

3. Create `plugins/gin-workflow/src/scripts/workflow_core/points_cli.py`:

   ```python
   """`gin points`: story points of any open epic. Exit 0 ok, 1 refused or failed, 2 usage or role."""

   from __future__ import annotations

   import argparse
   from datetime import datetime, timezone
   import json
   from pathlib import Path
   import sys
   from typing import Any, Mapping, Sequence

   from . import milestone as core, milestone_cli, workspace
   from .milestone_cli import Denied, MilestoneError


   def _parser() -> argparse.ArgumentParser:
       parser = argparse.ArgumentParser(prog="gin points")
       parser.add_argument("epic")
       parser.add_argument("n")
       parser.add_argument("--reason", required=True)
       parser.add_argument("--stage", choices=("roadmap", "discuss", "close"), default="roadmap")
       parser.add_argument("--repository", type=Path, default=None)
       return parser


   def _trace_points(root: Path, bead: Mapping[str, Any], epic: str, to: int, stage: str, actor: str) -> None:
       """Append {from, to, at, actor, stage} to the epic's `points_history`; a failure warns, never rolls back."""
       try:
           metadata = bead.get("metadata")
           stored = metadata.get("points_history") if isinstance(metadata, Mapping) else None
           history = json.loads(stored) if isinstance(stored, str) else list(stored or [])
           history.append({"from": core.points_of(bead), "to": to, "stage": stage,
                           "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "actor": actor or "unknown"})
           milestone_cli._bd(root, ["update", epic, "--set-metadata", f"points_history={json.dumps(history)}"], actor)
       except (MilestoneError, ValueError, TypeError, AttributeError) as error:
           print(f"warning: points of {epic} set but points_history not recorded: {error}", file=sys.stderr)


   def _points(root: Path, args: argparse.Namespace, beads: dict[str, dict[str, Any]], actor: str) -> tuple[str, str]:
       if not (args.n.isascii() and args.n.isdigit()) or int(args.n) not in core.POINT_SCALE:
           raise MilestoneError("points must be one of " + ", ".join(map(str, core.POINT_SCALE)))
       if not args.reason.strip():
           raise MilestoneError("--reason must not be empty")
       bead = beads.get(args.epic)
       if bead is None:
           raise MilestoneError(f"{args.epic} not found")
       if bead.get("issue_type") != "epic":
           raise MilestoneError(f"{args.epic} is not an epic")
       if bead.get("status") == "closed":
           raise MilestoneError(f"{args.epic} is closed")
       parent = beads.get(bead.get("parent") or "") or {}
       meta = parent.get("metadata") if isinstance(parent.get("metadata"), Mapping) else {}
       if parent.get("issue_type") == "milestone" and meta.get("kickoff") and args.stage != "close":
           raise MilestoneError(f"points of {args.epic} are locked since the kick-start of {parent['id']}; "
                                "change them through /milestone-close")
       milestone_cli._bd(root, ["update", args.epic, "--set-metadata", f"points={int(args.n)}",
                                "--set-metadata", f"points_reason={args.reason}"], actor)
       _trace_points(root, bead, args.epic, int(args.n), args.stage, actor)
       return f"points of {args.epic} set to {int(args.n)}", "points"


   def main(arguments: Sequence[str]) -> int:
       from .configuration import ConfigValidationError

       try:
           args = _parser().parse_args(list(arguments))
       except SystemExit as error:
           return error.code if isinstance(error.code, int) else 2
       args.repository = workspace.repository_root(args.repository)
       try:
           root = args.repository.resolve()
           return milestone_cli._write(root, milestone_cli._config(root), args, _points)
       except Denied as error:
           print(f"points error: {error}", file=sys.stderr)
           return 2
       except (MilestoneError, ConfigValidationError, ValueError) as error:
           print(f"points error: {error}", file=sys.stderr)
           return 1
   ```

4. Edit `milestone_cli.py`:
   - line 13: `from typing import Any, Callable, Mapping, Sequence`.
   - delete the `points` subparser (lines 59-63, from `item = sub.add_parser("points", parents=[common])` to the `--stage` line).
   - `_warn_malformed_metadata` becomes:

     ```python
     def _warn_malformed_metadata(milestones: Sequence[Mapping[str, Any]]) -> None:
         """One stderr warning per open milestone key (`away`, `integration`) and per open epic's `points`
         that is unreadable; it is ignored."""
         for bead in milestones:
             if bead.get("issue_type") == "milestone" and bead.get("status") != "closed":
                 for key in core.metadata_problems(bead):
                     print(f"warning: {bead['id']}: malformed {key} metadata ignored", file=sys.stderr)
             if bead.get("issue_type") == "epic" and bead.get("status") != "closed" and core.points_problem(bead):
                 print(f"warning: {bead['id']}: malformed points metadata ignored", file=sys.stderr)
     ```
   - `_estimate` (line 371): `raise MilestoneError(f"{args.epic} has story points; change them with gin points")`.
   - delete `_trace_points` and `_points` (lines 376-409) and the `"points": _points` entry of `WRITES`: `WRITES = {"create": _create, "update": _update, "kickstart": _kickstart, "move": _move, "estimate": _estimate, "close": _close}`.
   - `_write`:

     ```python
     def _write(root: Path, config: dict[str, Any], args: argparse.Namespace,
                write: Callable[..., tuple[str, str]] | None = None) -> int:
         from . import team as team_core
         from . import team_beads

         team, actor = _guard(root, config)
         text, change = (write or WRITES[args.command])(root, args, _beads(root), actor)
     ```
     (the rest of the function is unchanged).
   - `main`, before `try: args = _parser()...`:

     ```python
         if arguments and arguments[0] == "points":  # `gin milestone points` is an alias of `gin points`
             from .points_cli import main as points_main
             return points_main(arguments[1:])
     ```
   The imports `datetime`, `timezone`, and `json` stay: `_trace_move` and the JSON output still use them.

5. Edit `milestone.py` `measure_pace`: the docstring's first line reads `"""Days per point over the MEASURED_EPICS most recently closed epics with points and actual days;`, and the filter drops `and "roadmap" in (bead.get("labels") or [])`:

   ```python
       closed = [bead for bead in beads.values()
                 if bead.get("issue_type") == "epic" and bead.get("status") == "closed"
                 and points_of(bead) is not None and actual_days(bead, today) is not None]
   ```

6. Edit `cli.py`: add `"points"` after `"milestone"` in `TOP_COMMANDS`, and after the `milestone` dispatch block:

   ```python
           if argv[0] == "points":
               from .points_cli import main as points_main
               return points_main(argv[1:])
   ```

7. Edit the docs. Each replacement below gives the old text, then the new text, exactly as they appear in the file.
   - `docs/reference/cli.md`, usage block of the gin milestone section:

     ```text
     gin milestone points EPIC N --reason TEXT [--stage roadmap|discuss|close]
     ```
     →
     ```text
     gin milestone points EPIC N --reason TEXT [--stage roadmap|discuss|close]   # alias of gin points
     ```
   - same section, paragraph that starts "An epic with story points" (two replacements):

     ```text
     the 10 most recently closed `roadmap` epics with points
     ```
     →
     ```text
     the 10 most recently closed epics with points
     ```
     and
     ```text
     ignore a malformed `points` value on an open roadmap epic
     ```
     →
     ```text
     ignore a malformed `points` value on an open epic
     ```
   - the `estimate` row of the write commands table:

     ```text
     (480 minutes each); refused for an epic with story points |
     ```
     →
     ```text
     (480 minutes each); refused for an epic with story points, which `gin points` changes |
     ```
   - the whole `points` row of that table becomes:

     ```text
     | `points` | Alias of [`gin points`](#gin-points), with the same arguments, output, and exit codes |
     ```
   - a new section between the end of the gin milestone section (after the paragraph that starts "A malformed `Deadline:` line") and the heading of the gin attach section:

     ````markdown
     ## `gin points`

     ```
     gin points EPIC N --reason TEXT [--stage roadmap|discuss|close]
     ```

     Set the story points of an open epic on the scale 1, 2, 3, 5, 8, 13, 21 with a one-line reason. Any epic is accepted, with or without the `roadmap` label. The command writes `points` and `points_reason`, appends `{from, to, at, actor, stage}` to `points_history`, and prints `points of <epic> set to <n>`. A failed append prints a warning and keeps the points. `--stage` names the step that set them: `roadmap` (default), `discuss`, or `close`. It needs `providers.task_tracking: beads`.

     It refuses, writing nothing, an off-scale value, an empty `--reason`, an unknown id, a bead that is not an epic, a closed epic, and an epic of a kicked-off milestone unless `--stage close`; that message names `/milestone-close`. `gin milestone points` is an alias. In team mode it follows the role, pull, and push rules of the [milestone writes](#gin-milestone). Errors start with `points error:`.

     Exit codes: 0 ok; 1 a refused value, non-Beads tracking, a failed pull or push, or a `bd` error; 2 usage error or a role that may not write.
     ````
   - `docs/reference/config.md:181`:

     ```text
     lists the roles allowed to run `gin milestone` writes; unset means any member.
     ```
     →
     ```text
     lists the roles allowed to run `gin milestone` writes and `gin points`; unset means any member.
     ```
   - `docs/guides/team.md:101`:

     ```text
     Milestone writes follow `team.permissions.milestone`
     ```
     →
     ```text
     Milestone writes and `gin points` follow `team.permissions.milestone`
     ```

8. Run `python3 -m pytest tests/workflow_core/test_milestone.py tests/workflow_core/test_milestone_cli.py tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_rename_sweep.py -q`. Expected: all pass.

9. Commit: `git add plugins/gin-workflow/src/scripts/workflow_core/points_cli.py plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py plugins/gin-workflow/src/scripts/workflow_core/milestone.py plugins/gin-workflow/src/scripts/workflow_core/cli.py docs/reference/cli.md docs/reference/config.md docs/guides/team.md tests/workflow_core/test_milestone.py tests/workflow_core/test_milestone_cli.py && git commit -m "feat(points): gin points for any open epic; milestone points is an alias (gin-workflow-05e5)"` with the attribution trailer.

### Track 2: Score every workflow in /discuss; skills, templates, and docs call `gin points`
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/discuss/SKILL.md:30-32` (step 8 and a **Points** paragraph before `## Exit`)
  - Modify `plugins/gin-workflow/src/skills/orchestrate/SKILL.md:20` (the Parent Bead bullet)
  - Modify `plugins/gin-workflow/src/skills/roadmap/references/story-points.md` (Read on, Score, Write, Score in /discuss)
  - Modify `plugins/gin-workflow/src/skills/roadmap/SKILL.md:20` (`gin points`)
  - Modify `plugins/gin-workflow/src/skills/roadmap/references/milestone-plan.md:27` (`gin points`)
  - Modify `plugins/gin-workflow/src/skills/milestone-close/SKILL.md:60` (`gin points`)
  - Modify `plugins/gin-workflow/src/templates/design-spec.md:1-9`, `plugins/gin-workflow/src/templates/technical-design.md:1-7`, `plugins/gin-workflow/src/templates/proposal.md:1-7` (`Points:` line)
  - Modify `docs/concepts/lifecycle.md:23`, `docs/starters/brownfield.md:227`, `docs/starters/brownfield.vi.md:227`
  - Test `tests/workflow_core/test_skill_routing.py`
  - Test `tests/workflow_core/test_specs.py`
- **Interfaces**:
  - Consumed: `gin points EPIC N --reason TEXT [--stage roadmap|discuss|close]` (Track 1).
  - Produced: the header line `Points: <n> (<reason>)` under `Kind:` in a design spec, a technical design, and `01-proposal.md`.
- **Provider role**: `docs`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** mechanical text edits with the exact wording given below; the size budgets and needles are checked by existing tests.
- **Acceptance criteria**: the US-2 skill text of the spec is in place; `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_specs.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_coverage.py -q` passes; no file under `plugins/gin-workflow/src` or `docs` (other than `docs/changelog.md`) contains `gin milestone points` except the alias lines of `docs/reference/cli.md`.
- **Estimated complexity**: low

Steps:

1. Write the failing tests.

   In `tests/workflow_core/test_skill_routing.py`:
   - lines 118 and 124: replace `"gin milestone points"` with `"gin points"`.
   - line 136: replace `"gin milestone points"` with `"gin points"` and add the needles `"Points: <n> (<reason>)"`, `"gin task list --type epic --status closed --json"`, and `"Epic:"`; after the loop add `self.assertNotIn("--label roadmap", points)`.
   - replace `test_discuss_rescores_a_roadmap_epic` with:

     ```python
         def test_discuss_scores_every_workflow(self):
             text = (SRC / "skills/discuss/SKILL.md").read_text(encoding="utf-8")
             for needle in ("../roadmap/references/story-points.md", "`Points:`", "--stage discuss", "gin points",
                            "every layout"):
                 with self.subTest(needle=needle):
                     self.assertIn(needle, text)
             self.assertNotIn("For a roadmap epic, re-score", text)

         def test_orchestrate_copies_the_points_line(self):
             text = (SRC / "skills/orchestrate/SKILL.md").read_text(encoding="utf-8")
             for needle in ("`Points:`", "../roadmap/references/story-points.md"):
                 with self.subTest(needle=needle):
                     self.assertIn(needle, text)
     ```

   In `tests/workflow_core/test_specs.py`, `test_pm_and_ba_templates_ship_and_can_be_overridden`, after the `proposal.md` assertion:

   ```python
               for name, kind in (("design-spec.md", "capability"), ("technical-design.md", "technical"),
                                  ("proposal.md", "capability")):
                   with self.subTest(template=name):
                       self.assertIn(f"\nKind: {kind}\nPoints: {{{{points}}}} ({{{{points_reason}}}})\n",
                                     run_specs(root, "template", name).stdout)
   ```

2. Run `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_specs.py -q`. Expected: the new and changed assertions fail (`gin points`, `Points:` not found).

Each replacement in steps 3-7 gives the old text, then the new text, exactly as they appear in the file.

3. Templates: in each of `plugins/gin-workflow/src/templates/design-spec.md`, `technical-design.md`, and `proposal.md`, insert this line right after the `Kind:` line:

   ```text
   Points: {{points}} ({{points_reason}})
   ```
   In `design-spec.md`, the last line of the comment:

   ```text
        User Stories come from `gin specs template user-story.md`. -->
   ```
   →
   ```text
        User Stories come from `gin specs template user-story.md`. Points is the confirmed score (roadmap skill, references/story-points.md). -->
   ```

4. `plugins/gin-workflow/src/skills/roadmap/references/story-points.md`:
   - the line under the title:

     ```text
     Read on `/roadmap` (step 4 and `--milestone` step 2) and on `/discuss <epic>` for a roadmap epic.
     ```
     →
     ```text
     Read on `/roadmap` (step 4 and `--milestone` step 2), on `/discuss`, and on `/orchestrate` when it creates the epic.
     ```
   - `## Score` step 1:

     ```text
     the user stories and their acceptance criteria of the confirmed spec in `/discuss`),
     ```
     →
     ```text
     the user stories and their acceptance criteria of the confirmed spec in `/discuss`, or the components of the design for a `technical` epic),
     ```
   - `## Score` step 2:

     ```text
     2. Anchors: from `gin task list --label roadmap --type epic --status closed --json`, pick
     ```
     →
     ```text
     2. Anchors: from `gin task list --type epic --status closed --json`, pick
     ```
   - `## Write`:

     ```text
     Run `gin milestone points <epic> <n> --reason "<reason>"`
     ```
     →
     ```text
     Run `gin points <epic> <n> --reason "<reason>"`
     ```
   - replace the heading `## Re-score in /discuss` and its paragraph with:

     ```markdown
     ## Score in /discuss
     In every layout and in team mode, `/discuss` scores the workflow before the spec goes to review and writes `Points: <n> (<reason>)` under `Kind:` of the design spec, or of `01-proposal.md` with the SDD layout. When the epic has points in Beads, show the old and new points with the reason. The line is reviewed with the spec, in chat or in its pull request; a member without a technical role keeps it and never turns it into a `TQ-<n>` question.

     Once `requirement-confirmed` is recorded (with spec review `pr`, by the run that records it after the merge) and the workflow has an epic, run `gin points <epic> <n> --stage discuss --reason "<reason>"` with the values of the `Points:` line, unless Beads already holds them. `/orchestrate` does the same right after it creates the epic for a spec without an `Epic:` line: it copies the line, scores nothing, and asks nothing; a spec without the line leaves the epic without points, and it says so.

     When `gin points` refuses because the milestone has kicked off, or exits 2 for a missing role, show the score, its reason, and the exact command, name who can run it (`/milestone-close` for a lock, a member holding a `team.permissions.milestone` role), and continue the stage. Beads wins over the `Points:` line.
     ```

5. `plugins/gin-workflow/src/skills/discuss/SKILL.md`:
   - step 8, delete this sentence (and the space before it), keeping the rest of the step:

     ```text
      For a roadmap epic, re-score its points per `../roadmap/references/story-points.md` (`--stage discuss`).
     ```
   - insert before `## Exit`, separated by blank lines:

     ```markdown
     **Points**, in every layout and in team mode: score the workflow per `../roadmap/references/story-points.md` into the `Points:` line of the spec before review; once `requirement-confirmed` is recorded and the workflow has an epic, write it with `gin points ... --stage discuss` as that file says. A refusal never blocks this stage.
     ```

6. `plugins/gin-workflow/src/skills/orchestrate/SKILL.md:20`:

   ```text
   belong only here.
   ```
   →
   ```text
   belong only here. When the spec has no `Epic:` line and orchestrate creates the epic, write the spec's `Points:` line to it per `../roadmap/references/story-points.md`.
   ```

7. Callers of the old name:
   - `plugins/gin-workflow/src/skills/roadmap/SKILL.md:20` (two replacements):

     ```text
     and points with `gin milestone points`.
     ```
     →
     ```text
     and points with `gin points`.
     ```
     and
     ```text
     When a `gin milestone move` or `points` call exits non-zero
     ```
     →
     ```text
     When a `gin milestone move` or `gin points` call exits non-zero
     ```
   - `plugins/gin-workflow/src/skills/roadmap/references/milestone-plan.md:27`:

     ```text
     then `gin milestone points` under the points rule of step 6
     ```
     →
     ```text
     then `gin points` under the points rule of step 6
     ```
   - `plugins/gin-workflow/src/skills/milestone-close/SKILL.md:60`:

     ```text
     3. `gin milestone points <epic> <n> --stage close
     ```
     →
     ```text
     3. `gin points <epic> <n> --stage close
     ```
   - `docs/starters/brownfield.md:227` and `docs/starters/brownfield.vi.md:227`:

     ```text
     `gin milestone points`
     ```
     →
     ```text
     `gin points`
     ```
   - `docs/concepts/lifecycle.md:23`:

     ```text
     `/discuss <epic>` re-scores a roadmap epic's points once its spec is confirmed;
     ```
     →
     ```text
     `/discuss` scores every workflow in a `Points:` line of its spec, written to the epic once the spec is confirmed, or by `/orchestrate` when it creates the epic;
     ```

8. Run `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_specs.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_coverage.py -q`. Expected: all pass. Then `grep -rn "gin milestone points" plugins/gin-workflow/src docs --include=*.md | grep -v changelog.md` prints only the two alias lines of `docs/reference/cli.md`.

9. Commit: `git add plugins/gin-workflow/src/skills plugins/gin-workflow/src/templates docs/concepts/lifecycle.md docs/starters/brownfield.md docs/starters/brownfield.vi.md tests/workflow_core/test_skill_routing.py tests/workflow_core/test_specs.py && git commit -m "feat(points): /discuss scores every workflow into the spec; skills call gin points (gin-workflow-05e5)"` with the attribution trailer.

## Integration
- **Branch**: `feat/points-any-epic` (worktree `.claude/worktrees/points-any-epic`)
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes (the pre-push hook runs it once, at ship).
- [ ] Manual, in a scratch repository with `providers.task_tracking: beads`: `gin points <epic-without-roadmap-label> 5 --reason x` prints `points of <epic> set to 5`; `gin milestone points` on another epic writes the same keys; `gin milestone list --json` shows `days_per_point.measured_epics` counting a closed epic without the label.
- [ ] Manual (US-2), one `/discuss` run per path, checking `points_history` after each: legacy with `/discuss <epic-id>`; legacy without an epic, then `/orchestrate` (entry with stage `discuss`, no scoring question); SDD layout.
- [ ] After ship: `gin points gin-workflow-05e5 5 --stage discuss --reason "<reason>"` records this epic's score, which discuss could not write.

## Notes
- The Parent Bead `gin-workflow-05e5` stays open until the merge into `master` is confirmed; Track 1 and Track 2 close when their tests and review pass.
- `docs/changelog.md` gets its entry at the next release (`docs/contributing.md:115`).
- The user may override `Model:` and `Effort:` before plan approval.

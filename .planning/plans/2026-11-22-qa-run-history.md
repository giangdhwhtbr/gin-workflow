# Plan: gin-qa keeps a run history per case

Epic: gin-workflow-g2gx
Spec: `.planning/specs/2026-11-22-qa-run-history-design.md`

## Objective

Every result that reaches a case file through `record_result` (`cases result`, `cases bug`, `e2e run`, `tests run`) also appends one JSON line to `qa/runs/<yyyy-mm>/<actor>.jsonl`, which merges without conflicts; `gin-qa runs export --format json` returns the records with filters, as the contract `gin-console-rm-test-trends` reads. The case file keeps the latest result as today.

## Global Constraints

Copied from the spec:

- Out of scope: backfilling history from existing case files or git log; trends, flaky detection, or history in `gin-qa report`; gin-console itself; pruning or rotating old run files; `docs/changelog.md`, written at release time.
- The actor defaults to `git config user.email`, the identity gin team mode already uses (`plugins/gin-workflow/src/scripts/workflow_core/team.py:191`); `unknown` when it is unset.
- `cases to-manual` writes `Result: not run` without a run (`cases.py:480`) and appends no record.
- `runs export` reads the working tree only, not other branches or git history.
- The record adds `capability` to the keys the epic lists, so a per-capability trend still works after a case is deleted or renamed.
- The case file format, `cases export`, `cases due`, `e2e export`, and `report` are unchanged; existing callers without `--actor` or `--evidence` keep working.
- Record keys are only ever added, never renamed or removed.

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
- Problem statement: `record_result` (`plugins/gin-qa/src/scripts/gin_qa/cases.py:431`) overwrites `Result`, `Run`, `Bug`, `Checked`; e2e and tests runs keep per-run data only in the gitignored `qa/evidence/` (`e2e.py:199`). No earlier result survives.
- Success criteria: US-1 to US-3 of the spec pass as tests; the existing `tests/gin_qa/` suite stays green (it pins the case file lines and the `cases export` JSON); `tests/workflow_core/test_docs_coverage.py` and `tests/gin_qa/test_packaging.py` (6,000-character skill budget) pass.
- Constraints: the Global Constraints above. `skills/e2e/SKILL.md` has 5,163 of 6,000 characters; the edit adds under 200.
- Non-goals: see Global Constraints.

## Approach Options
### Option 1: append inside `record_result`
- Summary: a new `gin_qa/runs.py` owns the run directory, the file name, the append, the `.gitattributes` entry, and the export. `record_result` appends under the lock it already holds, before it writes the case file. The four callers pass `actor` and `evidence`.
- Pros: one writer, so the history and the case file never disagree; `e2e run` and `tests run` get history without skill steps.
- Cons: `record_result` gains two keyword arguments.

### Option 2: a `gin-qa runs add` step in the skills
- Summary: the skills call a new command after each result.
- Pros: `record_result` unchanged.
- Cons: `e2e run` and `tests run` from the CLI record no history; two writers can drift.

### Option 3: derive history from `git log` of the case files
- Summary: no new file; export walks git history.
- Pros: nothing to write.
- Cons: no actor or evidence; uncommitted runs between commits are lost.

### Recommended Approach
- Selected option: Option 1, confirmed in `/discuss`.
- Rationale: `record_result` is already "the only writer of Result/Run/Bug/Checked" (`cases.py:433`); the root-cause rule puts the append in the shared code every caller goes through (`lean#root-cause`).

Decisions this plan takes against the spec text, for the user to confirm with the plan:
- `gin-qa cases renumber` leaves run records unchanged: a record keeps the case id it had when it ran. Rewriting other testers' lines would break append-only and the conflict-free merge. The guide says so.
- The `tests` skill also commits the run files, like `run` and `e2e` (the spec named only those two); `tests run` appends records too (R1).
- The merge test records the same result on both branches: two branches that record different results for one case still conflict in the case file, as today; only the run files are conflict-free.
- `runs export` text output prints `no runs` when there is nothing to list, as other commands print `nothing to do`.

## Scope
- In scope: `plugins/gin-qa/src/scripts/gin_qa/runs.py` (new), `cases.py`, `cli.py`, `bugs.py`, `e2e.py`, `tests.py`; skills `run`, `e2e`, `tests`; `docs/reference/cli.md`, `docs/guides/qa.md`, `docs/guides/qa.vi.md`; tests `tests/gin_qa/test_runs_cli.py` (new), `test_cases_bug.py`, `test_e2e_cli.py`, `test_tests_cli.py`.
- Out of scope: `plugins/gin-qa/dist/` (built by `install.sh`); `numbering.py`; `report.py`; gin-workflow core; `docs/changelog.md`; the gin-qa version.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks 2 and 3 build on the runs module and record_result of Track 1, and all three edit cli.py and docs/reference/cli.md; one session, solo work.
```

## Tasks

### Track 1: Run record on every manual result, and the union merge
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-qa/src/scripts/gin_qa/runs.py`
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cases.py:1-15` (import `runs`, `Sequence`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cases.py:431-452` (`record_result` takes `actor`, `evidence`; appends)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:30-41` (`--actor`, `--evidence` on `result`; `--actor` on `bug`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:237-246` (pass them on)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/bugs.py:185-245` (`file_bug` takes `actor`; both `record_result` calls pass `actor` and `evidence`)
  - Modify `plugins/gin-qa/src/skills/run/SKILL.md:21` (commit the run files)
  - Modify `docs/reference/cli.md:528-540` (`cases result` and `cases bug` flags)
  - Create `tests/gin_qa/test_runs_cli.py`
  - Test `tests/gin_qa/test_cases_bug.py`
  - Test `tests/gin_qa/test_cases_cli.py`
- **Interfaces** (produced):
  - `runs.KEYS: tuple[str, ...]` = `("actor", "at", "bug", "capability", "case", "evidence", "hash8", "result", "run")`
  - `runs.runs_dir(cases_dir: str) -> str`; `runs.default_actor(root: Path) -> str`; `runs.now() -> str`; `runs.file_for(cases_dir: str, actor: str, at: str) -> str`; `runs.append(root: Path, cases_dir: str, record: dict[str, Any]) -> str` (raises `ValueError` naming the run file)
  - `cases.record_result(root, cases_dir, case_id, status, run=None, bug=None, *, actor: str | None = None, evidence: Sequence[str] = ()) -> dict[str, str]` (return value unchanged)
  - `bugs.file_bug(..., run=None, actor: str | None = None)`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change to one writer with the code below; the edge cases (default actor, failed append, `.gitattributes` once, union merge of the same file) are listed and tested.
- **Acceptance criteria**: US-1 (manual and bug parts) and US-2 of the spec pass as tests; `python3 -m pytest tests/gin_qa/test_runs_cli.py tests/gin_qa/test_cases_cli.py tests/gin_qa/test_cases_bug.py tests/gin_qa/test_packaging.py tests/workflow_core/test_docs_coverage.py -q` passes.
- **Estimated complexity**: medium

Steps:

1. Write the failing tests. Create `tests/gin_qa/test_runs_cli.py`:

   ```python
   """gin-qa run history: a record per result, the union merge, and `gin-qa runs export`."""

   from __future__ import annotations

   import json
   import os
   from pathlib import Path
   import subprocess
   import sys
   import tempfile
   import unittest
   from unittest import mock

   sys.path.insert(0, str(Path(__file__).resolve().parent))

   from qa_fixtures import case_file, commit_all, gin_workflow_bin, make_repo, write  # noqa: E402
   from qa_fixtures import qa as qa_subprocess, qa_in_process as qa  # noqa: E402
   from gin_qa import runs  # noqa: E402

   FILE = "qa/cases/auth/TC-AUTH-001.e2e.md"
   SOURCE = "Source: docs/specs/login.md"


   class RunsCase(unittest.TestCase):
       def setUp(self):
           self.tmp = tempfile.TemporaryDirectory()
           self.base = Path(self.tmp.name)
           self.bin = gin_workflow_bin(self.base)
           self.root = make_repo(self.base / "repo", layout="legacy")
           write(self.root, "docs/specs/login.md", "# Login\n")
           write(self.root, FILE, case_file("TC-AUTH-001", SOURCE))

       def tearDown(self):
           self.tmp.cleanup()

       def result(self, *args: str):
           return qa(self.root, self.bin, "result", "TC-AUTH-001", *args)

       def records(self, relative: str) -> list[dict]:
           text = (self.root / relative).read_text(encoding="utf-8")
           return [json.loads(line) for line in text.splitlines()]

       def exported_case(self) -> dict:
           return json.loads(qa(self.root, self.bin, "export", "--format", "json").stdout)["cases"][0]


   class TestRecord(RunsCase):
       def test_each_result_appends_a_record_and_the_case_keeps_the_latest(self):
           with mock.patch.object(runs, "now", side_effect=["2026-11-22T10:15:03Z", "2026-11-22T11:00:00Z"]):
               first = self.result("failed", "--run", "manual 2026-11-22", "--bug", "gw-7", "--actor", "a@x.com",
                                   "--evidence", "shots/1.png", "--evidence", "https://logs.example/42")
               second = self.result("passed", "--run", "manual 2026-11-22", "--actor", "a@x.com")
           self.assertEqual((0, 0), (first.returncode, second.returncode), first.stderr + second.stderr)
           exported = self.exported_case()
           common = {"actor": "a@x.com", "bug": "gw-7", "capability": "auth", "case": "TC-AUTH-001",
                     "hash8": exported["hash8"], "run": "manual 2026-11-22"}
           self.assertEqual([{**common, "at": "2026-11-22T10:15:03Z", "result": "failed",
                              "evidence": ["shots/1.png", "https://logs.example/42"]},
                             {**common, "at": "2026-11-22T11:00:00Z", "result": "passed", "evidence": []}],
                            self.records("qa/runs/2026-11/a-x.com.jsonl"))
           line = (self.root / "qa/runs/2026-11/a-x.com.jsonl").read_text(encoding="utf-8").splitlines()[0]
           self.assertTrue(line.startswith('{"actor":"a@x.com","at":"2026-11-22T10:15:03Z","bug":"gw-7",'), line)
           self.assertEqual(("passed", "manual 2026-11-22", "gw-7"),
                            (exported["result"], exported["run"], exported["bug"]))

       def test_the_actor_defaults_to_the_git_email_then_unknown(self):
           with mock.patch.object(runs, "now", return_value="2026-11-22T10:15:03Z"):
               self.assertEqual(0, self.result("passed").returncode)
               subprocess.run(["git", "config", "--unset", "user.email"], cwd=self.root, check=True)
               with mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}):
                   self.assertEqual(0, self.result("passed").returncode)
           self.assertEqual(["t@example.com"], [row["actor"] for row in self.records("qa/runs/2026-11/t-example.com.jsonl")])
           self.assertEqual(["unknown"], [row["actor"] for row in self.records("qa/runs/2026-11/unknown.jsonl")])

       def test_a_bad_actor_or_evidence_exits_2_and_writes_nothing(self):
           before = (self.root / FILE).read_text(encoding="utf-8")
           for args in (("--actor", "a\nb"), ("--actor", ""), ("--evidence", "")):
               with self.subTest(args=args):
                   result = self.result("passed", *args)
                   self.assertEqual(2, result.returncode)
                   self.assertIn("values are one non-empty line", result.stderr)
           self.assertEqual(before, (self.root / FILE).read_text(encoding="utf-8"))
           self.assertFalse((self.root / "qa/runs").exists())

       def test_a_failed_append_exits_2_and_leaves_the_case_file_unchanged(self):
           before = (self.root / FILE).read_text(encoding="utf-8")
           write(self.root, "qa/runs", "a file where the folder should be\n")
           result = self.result("passed", "--actor", "a@x.com")
           self.assertEqual(2, result.returncode)
           self.assertIn("qa/runs/", result.stderr)
           self.assertIn("run record not written", result.stderr)
           self.assertEqual(before, (self.root / FILE).read_text(encoding="utf-8"))

       def test_gitattributes_gets_the_union_entry_once(self):
           write(self.root, ".gitattributes", "* text=auto eol=lf\n")
           for _ in range(2):
               self.assertEqual(0, self.result("passed").returncode)
           self.assertEqual("* text=auto eol=lf\n/qa/runs/** merge=union\n",
                            (self.root / ".gitattributes").read_text(encoding="utf-8"))

       def test_to_manual_appends_no_record(self):
           with mock.patch.object(runs, "now", return_value="2026-11-22T10:15:03Z"):
               self.assertEqual(0, self.result("passed", "--actor", "a@x.com").returncode)
               moved = qa(self.root, self.bin, "to-manual", "TC-AUTH-001", "--reason", "flaky")
           self.assertEqual(0, moved.returncode, moved.stderr)
           self.assertEqual(["a-x.com.jsonl"], [path.name for path in (self.root / "qa/runs").rglob("*.jsonl")])
           self.assertEqual(1, len(self.records("qa/runs/2026-11/a-x.com.jsonl")))


   class TestMerge(RunsCase):
       def setUp(self):
           super().setUp()
           commit_all(self.root, "base")

       def git(self, *args: str) -> subprocess.CompletedProcess[str]:
           return subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True)

       def branch(self, name: str, actor: str) -> None:
           self.assertEqual(0, self.git("checkout", "-q", "-b", name, "main").returncode)
           self.assertEqual(0, self.result("passed", "--run", "manual 2026-11-22", "--actor", actor).returncode)
           # only what gin-qa wrote: a gin run may leave local runtime files that differ per branch
           self.assertEqual(0, self.git("add", "qa", ".gitattributes").returncode)
           self.assertEqual(0, self.git("commit", "-q", "-m", name).returncode)

       def merge(self) -> None:
           self.assertEqual(0, self.git("checkout", "-q", "a").returncode)
           done = self.git("merge", "--no-edit", "b")
           self.assertEqual(0, done.returncode, done.stdout + done.stderr)
           self.assertEqual("", self.git("status", "--porcelain", "--untracked-files=no").stdout)

       def test_two_testers_merge_without_conflicts(self):
           with mock.patch.object(runs, "now", side_effect=["2026-11-22T10:15:03Z", "2026-11-22T11:00:00Z"]):
               self.branch("a", "a@x.com")
               self.branch("b", "b@x.com")
           self.merge()
           self.assertEqual(["a@x.com"], [row["actor"] for row in self.records("qa/runs/2026-11/a-x.com.jsonl")])
           self.assertEqual(["b@x.com"], [row["actor"] for row in self.records("qa/runs/2026-11/b-x.com.jsonl")])

       def test_one_tester_on_two_branches_merges_by_union(self):
           with mock.patch.object(runs, "now", side_effect=["2026-11-22T10:15:03Z", "2026-11-22T11:00:00Z"]):
               self.branch("a", "a@x.com")
               self.branch("b", "a@x.com")
           self.merge()
           self.assertEqual(["2026-11-22T10:15:03Z", "2026-11-22T11:00:00Z"],
                            sorted(row["at"] for row in self.records("qa/runs/2026-11/a-x.com.jsonl")))


   if __name__ == "__main__":
       unittest.main()
   ```

   Add to `class TestLegacy` in `tests/gin_qa/test_cases_bug.py`, after `test_files_a_bug_linked_to_the_spec_epic_and_records_it`:

   ```python
       def test_a_filed_bug_appends_a_failed_record_with_its_evidence(self):
           self.answer({"task show gw-epic": shown("gw-epic", "in_progress"), "task create": CREATED})
           result = self.bug("TC-AUTH-001", "--actual", "An error page is shown", "--evidence", "shots/1.png",
                             "--run", "manual 2026-11-04", "--actor", "a@x.com", "--format", "json")
           self.assertEqual(0, result.returncode, result.stderr)
           files = list((self.root / "qa/runs").glob("*/a-x.com.jsonl"))
           self.assertEqual(1, len(files))
           record = json.loads(files[0].read_text(encoding="utf-8"))
           self.assertEqual(("failed", "gw-bug1", ["shots/1.png"], "manual 2026-11-04", "TC-AUTH-001"),
                            (record["result"], record["bug"], record["evidence"], record["run"], record["case"]))
   ```

2. Run: `python3 -m pytest tests/gin_qa/test_runs_cli.py tests/gin_qa/test_cases_bug.py -q`. Expected: `ImportError: cannot import name 'runs'` for the first file, and `unrecognized arguments: --actor` for the bug test.

3. Create `plugins/gin-qa/src/scripts/gin_qa/runs.py`:

   ```python
   """Run history: each recorded result as one JSON line in `<runs>/<yyyy-mm>/<actor>.jsonl`.

   One file per tester and month, so two testers never write the same file; `.gitattributes` merges one tester's
   appends on two branches by union.
   """

   from __future__ import annotations

   from datetime import datetime, timezone
   import json
   from pathlib import Path, PurePosixPath
   import re
   import subprocess
   from typing import Any

   KEYS = ("actor", "at", "bug", "capability", "case", "evidence", "hash8", "result", "run")
   _UNSAFE = re.compile(r"[^a-z0-9._-]+")


   def runs_dir(cases_dir: str) -> str:
       """The `runs` folder next to the cases folder: `qa/runs` for `qa/cases`."""
       return (PurePosixPath(cases_dir).parent / "runs").as_posix()


   def default_actor(root: Path) -> str:
       """`git config user.email`, the identity gin team mode uses; `unknown` when it is unset."""
       done = subprocess.run(["git", "config", "user.email"], cwd=root, capture_output=True, text=True, check=False)
       return done.stdout.strip() or "unknown"


   def now() -> str:
       """The UTC time of a record, to the second."""
       return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


   def file_for(cases_dir: str, actor: str, at: str) -> str:
       """`<runs>/<yyyy-mm of at>/<actor, lowercased, other characters as ->.jsonl`, repository-relative."""
       return f"{runs_dir(cases_dir)}/{at[:7]}/{_UNSAFE.sub('-', actor.lower())}.jsonl"


   def append(root: Path, cases_dir: str, record: dict[str, Any]) -> str:
       """Appends `record` as one line and returns its file; the caller holds the cases lock."""
       relative = file_for(cases_dir, record["actor"], record["at"])
       try:
           _union(root, cases_dir)
           path = root / relative
           path.parent.mkdir(parents=True, exist_ok=True)
           with path.open("a", encoding="utf-8", newline="\n") as handle:
               handle.write(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
       except OSError as error:
           raise ValueError(f"{relative}: run record not written: {error}") from error
       return relative


   def _union(root: Path, cases_dir: str) -> None:
       """Adds `/<runs>/** merge=union` to `.gitattributes` once, the way `e2e.ignore_evidence` edits `.gitignore`."""
       path = root / ".gitattributes"
       entry = f"/{runs_dir(cases_dir)}/** merge=union"
       lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
       if entry not in lines:
           path.write_text("\n".join([*lines, entry]) + "\n", encoding="utf-8")
   ```

4. In `plugins/gin-qa/src/scripts/gin_qa/cases.py`, change `from typing import Iterable, Mapping` to `from typing import Iterable, Mapping, Sequence`, add `from . import runs` after the standard-library imports, and replace `record_result` with:

   ```python
   def record_result(root: Path, cases_dir: str, case_id: str, status: str, run: str | None = None,
                     bug: str | None = None, *, actor: str | None = None,
                     evidence: Sequence[str] = ()) -> dict[str, str]:
       """The only writer of Result/Run/Bug/Checked: Run is replaced (dropped when None); Bug changes only when given.

       Each call first appends a run record (`runs.append`); when that fails, the case file is not written."""
       if status not in RESULTS:
           raise ValueError(f"status is one of {', '.join(RESULTS)}; got {status!r}")
       for value in (run, bug, actor, *evidence):
           if value is not None:
               one_line(value)
       actor = actor if actor is not None else runs.default_actor(root)
       located = find(root, cases_dir, case_id)
       path = root / located.path
       flat = path.parent == root / cases_dir
       with _lock(root / cases_dir):
           found, errors = parse_path(root, cases_dir, path)
           case = next((item for item in found if item.id == case_id), None)
           # a per-case file holds only this case, so every finding in it is about the case
           problems = [error for error in errors if not flat or re.search(rf"\b{re.escape(case_id)}\b", error)]
           if case is None or problems:
               raise ValueError("; ".join(problems) or f"{case_id}: no longer in {located.path}")
           kept_bug = case.fields.get("Bug") if bug is None else (None if bug == "none" else bug)
           values = [("Result", status), ("Run", run), ("Bug", kept_bug), ("Checked", stamp8(case))]
           text = _with_result(path.read_text(encoding="utf-8"), case, values)
           runs.append(root, cases_dir, {"actor": actor, "at": runs.now(), "bug": kept_bug or "",
                                         "capability": case.cap, "case": case_id, "evidence": list(evidence),
                                         "hash8": hash8(case), "result": status, "run": run or ""})
           write_atomic(path, text)
       return {"tc": case_id, "result": status, "run": run or "", "bug": kept_bug or "", "file": str(located.path)}
   ```

5. In `plugins/gin-qa/src/scripts/gin_qa/cli.py`, add after `item.add_argument("--bug")` of the `result` parser:

   ```python
       item.add_argument("--actor")
       item.add_argument("--evidence", action="append", default=[])
   ```

   and after `item.add_argument("--run")` of the `bug` parser:

   ```python
       item.add_argument("--actor")
   ```

   Change the two handlers to:

   ```python
       if args.command == "result":
           row = tc.record_result(root, eff.cases_dir, args.id, args.status, args.run, args.bug, actor=args.actor,
                                  evidence=args.evidence)
   ```

   ```python
           row = bugs.file_bug(root, eff, args.id, args.actual, args.evidence, external_ref=args.external_ref,
                               discovered_from=args.discovered_from, run=args.run, actor=args.actor)
   ```

6. In `plugins/gin-qa/src/scripts/gin_qa/bugs.py`, `file_bug` takes `run: str | None = None, actor: str | None = None)`, validates it with the others (`for value in (actual, *evidence, *(item for item in (external_ref, discovered_from, run, actor) if item is not None))`), and both calls become:

   ```python
               row = tc.record_result(root, eff.cases_dir, case_id, "failed", run, previous, actor=actor,
                                      evidence=evidence)
   ```

   ```python
           row = tc.record_result(root, eff.cases_dir, case_id, "failed", run, bug, actor=actor, evidence=evidence)
   ```

7. Run: `python3 -m pytest tests/gin_qa/test_runs_cli.py tests/gin_qa/test_cases_bug.py tests/gin_qa/test_cases_cli.py -q`. Expected: all pass (the existing `TestResult` tests pin the case file lines, so they prove the case file is unchanged).

8. Skill: in `plugins/gin-qa/src/skills/run/SKILL.md` step 7, replace `run \`gin commit <case files> -m "<capability>: <what was written>"\`, with the case files whose results changed,` with:

   ```markdown
   run `gin commit <case files> <runs folder> -m "<capability>: <what was written>"`, with the case files whose results changed, the `runs` folder next to the cases folder (`qa/runs` by default) that holds the run history of these results, and `.gitattributes` when `git status` lists it,
   ```

9. Docs, `docs/reference/cli.md`:
   - `### \`gin-qa cases result\``: the synopsis becomes `gin-qa cases result <TC-ID> <status> [--run REF] [--bug ID|none] [--actor ID] [--evidence REF]...`. Add after the first paragraph: `Each call first appends a run record to the run history, then writes the case file. \`--actor\` names who recorded the result (default \`git config user.email\`, else \`unknown\`); the repeatable \`--evidence\` lists its evidence. Both go into the run record only. A run record that cannot be written exits 2 and leaves the case file unchanged.` Add `--actor` and `--evidence` to the exit 2 sentence about empty or non-printable values.
   - `### \`gin-qa cases bug\``: the synopsis gains `[--actor ID]`; add the bullet `- The \`failed\` result appends a run record whose \`evidence\` holds the \`--evidence\` values; \`--actor\` works as in \`gin-qa cases result\`.`

10. Run: `python3 -m pytest tests/gin_qa/test_packaging.py tests/workflow_core/test_docs_coverage.py -q`. Expected: pass. Commit: `git add -A && git commit -m "feat(qa): append a run record on every case result (gin-workflow-g2gx)"`.

### Track 2: Run records from `e2e run` and `tests run`
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-qa/src/scripts/gin_qa/e2e.py:354-369` (`_record` passes `actor` and the per-case folder)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/e2e.py:372-406` (`run` takes `actor`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/tests.py:274-316` (`run` takes `actor`; passes the run folder)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:75-94` (`--actor` on `e2e run` and `tests run`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:309-331` (validate and pass `--actor` in `_run_e2e` and `_run_tests`)
  - Modify `plugins/gin-qa/src/skills/e2e/SKILL.md:21` (commit the run files)
  - Modify `plugins/gin-qa/src/skills/tests/SKILL.md:30` (commit the run files)
  - Modify `docs/reference/cli.md:607-618` (`--actor` and the records of `e2e run` and `tests run`)
  - Test `tests/gin_qa/test_e2e_cli.py`
  - Test `tests/gin_qa/test_tests_cli.py`
- **Interfaces** (consumed): `cases.record_result(..., *, actor, evidence)` from Track 1. (Produced): `e2e.run(root, eff, targets, actor: str | None = None)`; `tests.run(root, eff, kind, targets, actor: str | None = None)`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** threading one argument through two existing call paths, with the tests given below.
- **Acceptance criteria**: US-1 (e2e and tests parts) passes; a failed append in `tests run` shows as a `result not recorded` finding; `python3 -m pytest tests/gin_qa/test_e2e_cli.py tests/gin_qa/test_tests_cli.py tests/gin_qa/test_packaging.py -q` passes.
- **Estimated complexity**: low

Steps:

1. Write the failing tests. Add to `class TestRunAndEvidence` in `tests/gin_qa/test_e2e_cli.py`:

   ```python
       def test_run_appends_a_run_record_per_case(self):
           payload = json.loads(self.run_e2e("--actor", "ci@x.com").stdout)
           files = list((self.root / "qa/runs").glob("*/ci-x.com.jsonl"))
           self.assertEqual(1, len(files))
           record = json.loads(files[0].read_text(encoding="utf-8"))
           self.assertEqual(("TC-AUTH-001", "passed", payload["run"], [f"{payload['run']}/tc-auth-001"], "ci@x.com"),
                            (record["case"], record["result"], record["run"], record["evidence"], record["actor"]))
   ```

   Add to `class TestRun` in `tests/gin_qa/test_tests_cli.py`:

   ```python
       def test_run_appends_a_record_per_case_with_the_run_folder(self):
           write(self.root, ".fake-junit", junit(("test_tc_auth_004", "passed")))
           payload = self.run_json("run", "--type", "api", "TC-AUTH-004", "--actor", "ci@x.com")
           record = json.loads(next((self.root / "qa/runs").glob("*/ci-x.com.jsonl")).read_text(encoding="utf-8"))
           self.assertEqual(("TC-AUTH-004", "passed", payload["run"], [payload["run"]]),
                            (record["case"], record["result"], record["run"], record["evidence"]))

       def test_a_failed_append_is_a_finding_and_the_case_keeps_its_result(self):
           write(self.root, ".fake-junit", junit(("test_tc_auth_004", "passed")))
           write(self.root, "qa/runs", "a file where the folder should be\n")
           payload = self.run_json("run", "--type", "api", "TC-AUTH-004")
           self.assertEqual([], payload["recorded"])
           self.assertEqual(1, len(payload["findings"]))
           self.assertRegex(payload["findings"][0], r"^TC-AUTH-004: result not recorded: qa/runs/.*run record not written")
           self.assertEqual("not run", self.case_fields("TC-AUTH-004")["result"])
   ```

2. Run: `python3 -m pytest tests/gin_qa/test_e2e_cli.py tests/gin_qa/test_tests_cli.py -q -k "record or append"`. Expected: the new tests fail with `unrecognized arguments: --actor`.

3. `plugins/gin-qa/src/scripts/gin_qa/e2e.py`: `_record(root, eff, folder, specs, actor: str | None)` calls

   ```python
               tc.record_result(root, eff.cases_dir, case_id, status, run=folder, actor=actor,
                                evidence=[f"{folder}/{case_id.lower()}"])
   ```

   and `run(root, eff, targets, actor: str | None = None)` calls `_record(root, eff, folder, specs, actor)`.

4. `plugins/gin-qa/src/scripts/gin_qa/tests.py`: `run(root, eff, kind, targets, actor: str | None = None)` calls

   ```python
               tc.record_result(root, eff.cases_dir, case_id, status, run=folder, actor=actor, evidence=[folder])
   ```

5. `plugins/gin-qa/src/scripts/gin_qa/cli.py`: the `e2e` parser line `sub.add_parser("run", parents=[common]).add_argument("targets", ...)` becomes

   ```python
       item = sub.add_parser("run", parents=[common])
       item.add_argument("targets", nargs="*", metavar="TC-ID|capability")
       item.add_argument("--actor")
   ```

   and the `tests` `run` parser gains `item.add_argument("--actor")`. In `_run_e2e` and `_run_tests`, before the run starts (so a bad value exits 2 before Playwright or the test command runs):

   ```python
       if args.actor is not None:
           tc.one_line(args.actor)
       folder, code, errors, recorded = e2e.run(root, eff, args.targets, args.actor)
   ```

   ```python
       if args.actor is not None:
           tc.one_line(args.actor)
       folder, code, errors, recorded = tests.run(root, eff, args.kind, args.targets, args.actor)
   ```

6. Run: `python3 -m pytest tests/gin_qa/test_e2e_cli.py tests/gin_qa/test_tests_cli.py -q`. Expected: all pass, `test_concurrent_runs_keep_separate_complete_evidence` included (appends run under the cases lock).

7. Skills: in `plugins/gin-qa/src/skills/e2e/SKILL.md` step 10, `gin commit <spec files> <case files> -m` becomes `gin commit <spec files> <case files> <runs folder> -m`, and after `the case files whose lines changed` add `, the \`runs\` folder next to the cases folder (\`qa/runs\` by default), and \`.gitattributes\` when \`git status\` lists it`. Same edit in `plugins/gin-qa/src/skills/tests/SKILL.md` step 11 (`<test files> <case files> <runs folder>`).

8. Docs, `docs/reference/cli.md`: after the first sentence of line 607 add `\`--actor ID\` works as in \`gin-qa cases result\`; each recorded case appends a run record whose \`evidence\` is \`<run folder>/<tc-id>\`.` In the `run --type T` bullet (line 618), add `\`--actor ID\` works as in \`gin-qa cases result\`; each recorded case appends a run record whose \`evidence\` is the run folder.`

9. Run: `python3 -m pytest tests/gin_qa/test_packaging.py tests/workflow_core/test_docs_coverage.py -q`. Expected: pass. Commit: `git add -A && git commit -m "feat(qa): e2e and tests runs append run records (gin-workflow-g2gx)"`.

### Track 3: `gin-qa runs export` and the run history docs
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-qa/src/scripts/gin_qa/runs.py` (add `export`, `_parse`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:1-16` (imports, module docstring)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:352-373` (`_since`, `_runs_parser`, `_run_runs` before `main`; the `runs` group and usage line)
  - Modify `docs/reference/cli.md:518-608` (command list, the link from `cases result`, the new `gin-qa runs export` section)
  - Modify `docs/guides/qa.md` (new `## Run history` before `## Moving a flaky e2e case to manual`)
  - Modify `docs/guides/qa.vi.md` (new `## Lịch sử chạy { #run-history }` at the same place)
  - Test `tests/gin_qa/test_runs_cli.py`
- **Interfaces** (produced): `runs.export(root: Path, cases_dir: str, *, capability: str | None = None, case: str | None = None, since: str | None = None) -> dict[str, list[Any]]` returning `{"runs": [...], "problems": [...]}`; CLI `gin-qa runs export [--capability CAP] [--case TC-ID] [--since YYYY-MM-DD] [--format text|json] [--repository PATH]`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** a new read-only command and its JSON contract with the code below; the docs table is the contract gin-console reads.
- **Acceptance criteria**: US-3 passes; `python3 -m pytest tests/gin_qa/ tests/workflow_core/test_docs_coverage.py -q` passes.
- **Estimated complexity**: medium

Steps:

1. Write the failing tests. Add to `tests/gin_qa/test_runs_cli.py`, before `if __name__ == "__main__":`:

   ```python
   def record(case: str = "TC-AUTH-001", at: str = "2026-11-22T10:00:00Z", capability: str = "auth",
              result: str = "passed", actor: str = "a@x.com") -> dict:
       return {"actor": actor, "at": at, "bug": "", "capability": capability, "case": case, "evidence": [],
               "hash8": "1a2b3c4d", "result": result, "run": "manual"}


   def jsonl(*rows) -> str:
       return "".join((row if isinstance(row, str) else json.dumps(row)) + "\n" for row in rows)


   class TestExport(RunsCase):
       def export(self, *args: str):
           return qa(self.root, self.bin, "export", *args, "--format", "json", group="runs")

       def test_two_runs_of_one_case_give_two_records_by_time(self):
           with mock.patch.object(runs, "now", side_effect=["2026-11-22T11:00:00Z", "2026-11-22T10:00:00Z"]):
               self.assertEqual(0, self.result("passed", "--actor", "b@x.com").returncode)
               self.assertEqual(0, self.result("failed", "--actor", "a@x.com").returncode)
           result = qa_subprocess(self.root, self.bin, "export", "--format", "json", group="runs")
           self.assertEqual(0, result.returncode, result.stderr)
           payload = json.loads(result.stdout)
           self.assertEqual([], payload["problems"])
           self.assertEqual([("2026-11-22T10:00:00Z", "failed"), ("2026-11-22T11:00:00Z", "passed")],
                            [(row["at"], row["result"]) for row in payload["runs"]])

       def test_filters_combine(self):
           write(self.root, "qa/runs/2026-11/a-x.com.jsonl", jsonl(
               record(), record(case="TC-AUTH-002", at="2026-11-23T09:00:00Z"),
               record(case="TC-PAY-001", capability="pay", at="2026-11-24T09:00:00Z")))
           write(self.root, "qa/runs/2026-10/a-x.com.jsonl", jsonl(record(at="2026-10-30T09:00:00Z")))
           for args, cases in ((("--capability", "auth"), ["TC-AUTH-001", "TC-AUTH-001", "TC-AUTH-002"]),
                               (("--case", "TC-AUTH-001"), ["TC-AUTH-001", "TC-AUTH-001"]),
                               (("--since", "2026-11-23"), ["TC-AUTH-002", "TC-PAY-001"]),
                               (("--capability", "auth", "--since", "2026-11-01"), ["TC-AUTH-001", "TC-AUTH-002"])):
               with self.subTest(args=args):
                   result = self.export(*args)
                   self.assertEqual(0, result.returncode, result.stderr)
                   self.assertEqual(cases, [row["case"] for row in json.loads(result.stdout)["runs"]])

       def test_a_broken_line_is_a_problem_and_the_rest_is_returned(self):
           write(self.root, "qa/runs/2026-11/a-x.com.jsonl", jsonl(
               record(), "{not json", "[1]", {"case": "TC-AUTH-001"}, {**record(), "at": "yesterday"},
               record(at="2026-11-22T12:00:00Z")))
           result = self.export()
           self.assertEqual(0, result.returncode, result.stderr)
           payload = json.loads(result.stdout)
           self.assertEqual(["2026-11-22T10:00:00Z", "2026-11-22T12:00:00Z"], [row["at"] for row in payload["runs"]])
           self.assertEqual(["qa/runs/2026-11/a-x.com.jsonl:2: not JSON",
                             "qa/runs/2026-11/a-x.com.jsonl:3: not a JSON object",
                             "qa/runs/2026-11/a-x.com.jsonl:4: missing actor, at, bug, capability, evidence, hash8, "
                             "result, run",
                             "qa/runs/2026-11/a-x.com.jsonl:5: at is not YYYY-MM-DDTHH:MM:SSZ"], payload["problems"])

       def test_no_run_history_is_an_empty_export(self):
           result = self.export()
           self.assertEqual((0, {"problems": [], "runs": []}), (result.returncode, json.loads(result.stdout)))
           text = qa(self.root, self.bin, "export", group="runs")
           self.assertEqual((0, "no runs\n"), (text.returncode, text.stdout))

       def test_text_lists_records_then_problems(self):
           write(self.root, "qa/runs/2026-11/a-x.com.jsonl", jsonl(record(), "{"))
           text = qa(self.root, self.bin, "export", group="runs")
           self.assertEqual("2026-11-22T10:00:00Z TC-AUTH-001 passed a@x.com manual\n"
                            "qa/runs/2026-11/a-x.com.jsonl:2: not JSON\n", text.stdout)

       def test_a_bad_since_exits_2(self):
           for value in ("2026-13-01", "20261122", "yesterday"):
               with self.subTest(value=value):
                   self.assertEqual(2, self.export("--since", value).returncode)
   ```

2. Run: `python3 -m pytest tests/gin_qa/test_runs_cli.py -q -k Export`. Expected: failures; the CLI prints the usage line and exits 2 for the unknown group `runs`.

3. Add to `plugins/gin-qa/src/scripts/gin_qa/runs.py`, after `KEYS`:

   ```python
   _AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
   ```

   and at the end:

   ```python
   def export(root: Path, cases_dir: str, *, capability: str | None = None, case: str | None = None,
              since: str | None = None) -> dict[str, list[Any]]:
       """Every record that passes the filters, by time, then file, then line; unreadable lines go to `problems`."""
       found: list[tuple[str, str, int, dict[str, Any]]] = []
       problems: list[str] = []
       for path in sorted((root / runs_dir(cases_dir)).glob("*/*.jsonl")):
           relative = path.relative_to(root).as_posix()
           for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
               row, reason = _parse(line)
               if reason:
                   problems.append(f"{relative}:{number}: {reason}")
               elif ((capability is None or row["capability"] == capability) and (case is None or row["case"] == case)
                     and (since is None or row["at"][:10] >= since)):
                   found.append((row["at"], relative, number, row))
       return {"runs": [row for *_, row in sorted(found, key=lambda item: item[:3])], "problems": problems}


   def _parse(line: str) -> tuple[dict[str, Any], str | None]:
       """A record and None, or the reason the line is not one."""
       try:
           row = json.loads(line)
       except ValueError:
           return {}, "not JSON"
       if not isinstance(row, dict):
           return {}, "not a JSON object"
       missing = [key for key in KEYS if key not in row]
       if missing:
           return row, f"missing {', '.join(missing)}"
       if not isinstance(row["at"], str) or not _AT.match(row["at"]):
           return row, "at is not YYYY-MM-DDTHH:MM:SSZ"
       return row, None
   ```

4. `plugins/gin-qa/src/scripts/gin_qa/cli.py`:
   - Docstring: `"""\`gin-qa cases\`, \`gin-qa e2e\`, \`gin-qa tests\`, \`gin-qa runs\`, and \`gin-qa report\`: exit 0 ok, 1 findings, 2 usage or environment error."""`
   - Imports: add `from datetime import date`; `from . import bugs, e2e, numbering, report, runs, tests`.
   - Before `def main`:

     ```python
     def _since(value: str) -> str:
         """`--since`: a date as YYYY-MM-DD."""
         try:
             parsed = date.fromisoformat(value)
         except ValueError:
             parsed = None
         if parsed is None or parsed.isoformat() != value:
             raise argparse.ArgumentTypeError(f"{value!r} is not a date as YYYY-MM-DD")
         return value


     def _runs_parser() -> argparse.ArgumentParser:
         common = argparse.ArgumentParser(add_help=False)
         common.add_argument("--repository", type=Path, default=None)
         common.add_argument("--format", choices=("text", "json"), default="text")
         parser = argparse.ArgumentParser(prog="gin-qa runs")
         sub = parser.add_subparsers(dest="command", required=True)
         item = sub.add_parser("export", parents=[common])
         item.add_argument("--capability")
         item.add_argument("--case")
         item.add_argument("--since", type=_since)
         return parser


     def _run_runs(args: argparse.Namespace) -> int:
         root, eff = locate(args.repository)
         payload = runs.export(root, eff.cases_dir, capability=args.capability, case=args.case, since=args.since)
         lines = [f"{row['at']} {row['case']} {row['result']} {row['actor']} {row['run']}".rstrip()
                  for row in payload["runs"]]
         _emit(payload, args.format, "\n".join([*lines, *payload["problems"]]) or "no runs")
         return 0
     ```

   - In `main`, add `"runs": (_runs_parser, _run_runs),` to `groups` and the usage line `"       gin-qa runs export [--capability CAP] [--case TC-ID] [--since YYYY-MM-DD]\n"` before the `report` line.

5. Run: `python3 -m pytest tests/gin_qa/test_runs_cli.py -q`. Expected: all pass.

6. Docs, `docs/reference/cli.md`:
   - Line 520: add `gin-qa runs export [--capability CAP] [--case TC-ID] [--since YYYY-MM-DD]` to the command list, before `gin-qa report`.
   - `### \`gin-qa cases result\``: link `run history` in the sentence Track 1 added to `[run history](#gin-qa-runs-export)`.
   - New section after `### \`gin-qa cases export\` and \`gin-qa e2e run\``:

     ```markdown
     ### `gin-qa runs export`

     `gin-qa runs export [--capability CAP] [--case TC-ID] [--since YYYY-MM-DD] [--format text|json]` lists the run history: one record per result that `cases result`, `cases bug`, `e2e run`, and `tests run` recorded. It exits 0 whatever it finds, and 2 on a usage error such as a `--since` that is not a date.

     Each result is appended as one JSON line to `runs/<yyyy-mm>/<actor>.jsonl` next to the cases folder (`qa/runs` by default). The actor is lowercased and each run of other characters than `a-z`, `0-9`, `.`, `_`, `-` becomes `-`. One file per tester and month means two testers never write the same file. The first record adds `/<runs folder>/** merge=union` to `.gitattributes`, so one tester's appends on two branches merge in a local `git merge`. A hosted merge button may not apply that driver. `gin-qa cases renumber` leaves the records unchanged, so a record keeps the case ID it ran under.

     JSON output is `{"runs": [...], "problems": [...]}`. `runs` is sorted by `at`, then file, then line; the filters combine, and `--since` keeps records on or after that UTC date. A line that is not a record adds `<file>:<line>: <reason>` to `problems` and is skipped. Text output prints one line per record, `<at> <case> <result> <actor> <run>`, then the problems, or `no runs`. Keys are added in later versions, never renamed or removed.

     | Key | Meaning |
     |---|---|
     | `actor` | `--actor`, else `git config user.email`, else `unknown` |
     | `at` | UTC time of the record, `YYYY-MM-DDTHH:MM:SSZ` |
     | `bug` | the case's `Bug:` after the result, `""` when none |
     | `capability` | the case's capability, as in `gin-qa cases export` |
     | `case` | the TC-ID |
     | `evidence` | `--evidence` values of `cases result` and `cases bug`; `<run folder>/<tc-id>` for `e2e run`; the run folder for `tests run`; `[]` when none |
     | `hash8` | the case's `hash8` when the result was recorded, as in `gin-qa cases export` |
     | `result` | `passed`, `failed`, `blocked`, or `not run` |
     | `run` | the case's `Run:` after the result, `""` when none |
     ```

7. Docs, `docs/guides/qa.md`, before `## Moving a flaky e2e case to manual`:

   ```markdown
   ## Run history

   Every recorded result is kept, while the case file shows only the latest one. `gin-qa cases result`, `cases bug`, `e2e run`, and `tests run` each append one line per case to `runs/<yyyy-mm>/<actor>.jsonl` in the QA home. The actor is `--actor`, else your `git config user.email`. Commit the `runs` folder with the case files; `/gin-qa:run`, `/gin-qa:e2e`, and `/gin-qa:tests` do so when they save the work.

   Each tester writes their own file, so branches from two testers merge without conflicts. `gin-qa runs export --format json` lists the records, with filters by capability, case, and start date. The [CLI reference](../reference/cli.md#gin-qa-runs-export) lists every key.
   ```

   `docs/guides/qa.vi.md`, before `## Chuyển một case e2e không ổn định sang manual { #moving-a-flaky-e2e-case-to-manual }`:

   ```markdown
   ## Lịch sử chạy { #run-history }

   Mọi kết quả đã ghi đều được giữ lại, còn case file chỉ hiện kết quả mới nhất. `gin-qa cases result`, `cases bug`, `e2e run` và `tests run` mỗi lần ghi thêm một dòng cho mỗi case vào `runs/<yyyy-mm>/<actor>.jsonl` trong QA home. Actor là `--actor`, nếu không có thì là `git config user.email` của bạn. Commit thư mục `runs` cùng các case file; `/gin-qa:run`, `/gin-qa:e2e` và `/gin-qa:tests` làm việc này khi lưu công việc.

   Mỗi tester ghi vào file riêng, nên nhánh của hai tester merge không bị conflict. `gin-qa runs export --format json` liệt kê các record, lọc được theo capability, case và ngày bắt đầu. [CLI reference](../reference/cli.md#gin-qa-runs-export) liệt kê mọi key.
   ```

8. Run: `python3 -m pytest tests/gin_qa/ tests/workflow_core/test_docs_coverage.py -q` and `gin docs check docs/reference/cli.md docs/guides/qa.md docs/guides/qa.vi.md`. Expected: pass and `ok`. Commit: `git add -A && git commit -m "feat(qa): gin-qa runs export and the run history docs (gin-workflow-g2gx)"`.

## Integration
- **Branch**: `feat/qa-run-history` (worktree `.claude/worktrees/qa-run-history`)
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes (the pre-push hook runs it once, at ship).
- [ ] Manual, in a scratch repository after `./install.sh --plugin gin-qa`: two `gin-qa cases result` calls, then `gin-qa runs export --format json` shows both records; `.gitattributes` holds the union entry once.
- [ ] At ship: `bd -C gin-workflow ship qa-run-history` after the epic closes, so `gin-console-rm-test-trends` sees the capability.

## Notes
- The Parent Bead `gin-workflow-g2gx` stays open until the merge into `master` is confirmed; tracks close when their tests and review pass.
- `docs/changelog.md` gets its entry at the next release (`docs/contributing.md:115`).
- The user may override `Model:` and `Effort:` before plan approval.

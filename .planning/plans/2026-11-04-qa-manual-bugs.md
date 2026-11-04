# Plan: gin-qa manual runs and bug logging

Epic: gin-workflow-qa-manual-bugs
Spec: .planning/specs/2026-11-04-qa-manual-bugs-design.md

## Objective

A tester runs `/gin-qa:run <capability>`, walks each `.manual.md` case, and records `passed`, `failed`, or `blocked`. On a failure, `gin-qa cases bug <TC-ID>` files a bug bead through `gin-workflow task create` with `--deps discovered-from:<epic>`, where `<epic>` is the epic the case was written for, and records `failed`, the run, and the bug in the case file. The usage report then counts the bug against that epic (`usage.py` `quality()` counts `discovered-from` dependents).

Goal (from the spec): A tester walks the manual cases of a capability, records `passed`, `failed`, or `blocked` on each, and on a failure files a bug bead linked to the epic the case was written for, so the usage report counts the bug against that work.

Architecture:
- `gin-workflow specs reqs` adds `epic` to each row: the `Epic:` line of the change that holds the REQ (`specs.change_epic`), or `null`.
- `gin-workflow state --format json` adds `epic`: the epic recorded at `orchestration-ready` for the workflow id (`lifecycle_cli._recorded_epic`), or `null`.
- A new module, `plugins/gin-qa/src/scripts/gin_qa/bugs.py`:
  - keeps a case's bug when `task show` reports it still open, without looking for an epic;
  - finds the epic: `Source:` spec → `Epic:` line, else `Workflow:` → `state` epic; or the first REQ row with an `epic`;
  - checks the epic bead with `gin-workflow task show <id> --json`, telling a missing bead from a tracker failure;
  - files the bug with `gin-workflow task create --body-file -`, the description on stdin, run in the repository;
  - records the result through `cases.record_result`.
- `cases.py` gains two shared helpers that `record_result` and `bugs.py` both use: `one_line` (value check) and `find` (case lookup plus its findings).
- `cli.py` adds the `bug` subcommand.
- A new skill, `/gin-qa:run`, drives the tester dialogue through `cases export`, `cases result`, and `cases bug`, and offers the open epics (`gin-workflow task list --type epic --json`) when no epic is found.

Tech Stack:
- Python 3 stdlib (`json`, `re`, `shutil`, `subprocess`) in the gin-qa CLI and in `workflow_core`.
- Tests are `unittest` tests, run with `python3 -m pytest -n auto`.
- The skill and docs are Markdown.

### Global Constraints (verbatim from the spec)

- Out of scope: syncing bugs to Jira or Notion; test cycles or runs as beads; copying evidence files; adding the new actual result or evidence to a bug that is still open; runners for non-manual types.
- Exit codes follow the gin-qa contract: 0 recorded, 2 usage or environment error. Exit 2, with nothing written, for an unknown case, a case whose type is not `manual`, an invalid option value, no epic, or an unreadable spec named in `Source:`.
- When `gin-workflow task create` fails (no Beads, or a task backend without `--deps`), the command exits 2, passes on its stderr, and leaves the case file unchanged.
- When the bug is created but recording the result fails, the command exits 2 and names the new bead on stderr so the tester can run `gin-qa cases result <TC-ID> failed --bug <id>`; the bead is not deleted.
- A `Bug:` value that is not a bead, or that `task show` cannot read, counts as no open bug: a new bug is filed and the old value is named as the previous bug.
- `specs reqs` and `state` only gain a key; `cases export`, `e2e export`, and `report` output stay unchanged, so gin-console is not affected.
- gin-qa `VERSION` becomes `0.8` and the plugin `0.9.0`; gin-workflow gets a patch bump. The gin-workflow core still never mentions gin-qa.

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
- Problem statement:
  - `gin-qa cases result` records a result and a bug id (`cli.py:202-205`, `cases.py:288-314`), but nothing files the bug.
  - Nothing links a bug to the work it came from. The usage report counts bugs only as `discovered-from` dependents of an epic or its children (`usage.py:193-199`).
  - `specs reqs` rows name the change folder (`specs_reqs.py:31-35`) but not its epic. The epic is read only by `specs.change_epic` (`specs.py:250-255`).
- Facts checked against `bd` 1.0.5 while planning (temporary database):
  - `bd create ... --json` prints one JSON object with `id` on stdout.
  - `bd show <id> --json` prints a JSON list and exits 1 for an unknown id.
  - `--deps discovered-from:<unknown>` still creates the bead and only prints a warning. That is why `cases bug` checks that the epic bead exists before it creates anything (see Notes).
- `gin-workflow state --format json` has no epic today; `lifecycle_cli._recorded_epic` already reads it from the `orchestration.ready` event, and the label `workflow:<topic>` exists only in team mode (`lifecycle_cli.py:217`). In this repository 37 of 56 specs carry `Workflow:` and no `Epic:`.
- `bd create` reads the description from stdin with `--body-file -`; `gin-workflow task` passes its stdin to `bd` (`tasks.py` `main`). A missing bead makes `bd show` print `no issue found`; a missing database prints `no beads database found`.
- `gin-workflow task` runs `bd` in the current directory (`tasks.py` `main`: `root = Path.cwd()`), so `bugs.py` runs it with `cwd=<repository>`.
- Success criteria:
  - the acceptance criteria of spec US-1 to US-5;
  - `python3 -m pytest -n auto` is green;
  - `bash tests/install_smoke_test.sh` passes.
- Constraints: the Global Constraints above.
- Non-goals: see Global Constraints, Out of scope.

## Approach Options
### Option 1: `gin-qa cases bug` CLI plus a thin skill
- Summary: the CLI owns epic lookup, bead creation, and recording; the skill only asks the tester and calls the CLI.
- Pros:
  - deterministic and testable with a stub `gin-workflow`;
  - one write path for case files;
  - usable without an agent.
- Cons: one more subcommand to document.

### Option 2: The skill files bugs itself through `gin-workflow task create`
- Summary: the agent builds the description and calls `task create`, then `cases result`.
- Pros: no new CLI code.
- Cons:
  - the epic lookup and the description format live in prose;
  - nothing tests them;
  - the result differs per harness.

### Recommended Approach
- Selected option: Option 1 (chosen in `/discuss`).
- Rationale: gin-qa already keeps every rule that touches a case file in the CLI. The skill stays a dialogue.

## Scope
- In scope:
  - the spec's Requirements (Finding the epic, `gin-qa cases bug`, `/gin-qa:run`);
  - US-1 to US-5;
  - the `epic` key in `specs reqs`;
  - docs, and the gin-qa and gin-workflow version bumps.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2's sdd test reads the `epic` key Track 1 adds to `specs reqs`, and Track 3 documents and bumps the version of the command Track 2 builds, so each track runs after the one before.
```

## Tasks

### Track 1: `epic` in `gin-workflow specs reqs` and `gin-workflow state`
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_reqs.py:8-9` (import `change_epic`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_reqs.py:31-50` (`_row`, `_delta_rows`)
  - Modify `tests/workflow_core/test_specs_reqs.py:41-52` (living row has `"epic": None`) and add one test
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:425` (`epic` in the state payload)
  - Modify `tests/workflow_core/test_lifecycle_cli.py` (one test before `test_state_json_catalog_is_null_without_harness`, line 90)
  - Modify `docs/reference/cli.md:50` (`state` JSON keys) and `docs/reference/cli.md:139` (`reqs` row)
  - Modify version `2.1.1` → `2.1.2`:
    - `plugins/gin-workflow/plugin.meta.json:3`
    - `plugins/gin-workflow/src/.claude-plugin/plugin.json:3`
    - `plugins/gin-workflow/src/.codex-plugin/plugin.json:3`
    - `tests/gin_orchestrator/test_harness_packaging.py:240`
- **Provider role**: `backend`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** two few-line changes with the exact code and tests given below; no design judgement.
- **Acceptance criteria**:
  - Each `specs reqs` row has `epic`:
    - the proposal's `Epic:` value for a REQ in a change;
    - `null` for a living REQ, or for a change whose proposal has no `Epic:` line.
  - `gin-workflow state --format json` has `epic`: the epic recorded at `orchestration-ready` for the workflow id, else `null`.
  - `tests/workflow_core/test_specs_reqs.py`, `tests/workflow_core/test_lifecycle_cli.py`, `tests/gin_orchestrator/test_harness_packaging.py`, and `tests/workflow_core/test_docs_coverage.py` pass.
- **Estimated complexity**: low

Interfaces produced:
- Every row of `gin-workflow specs reqs --format json` has the keys `id`, `title`, `capability`, `section`, `change`, `epic` (`str | null`), `hash`, `source`, and `scenarios`.
- `gin-workflow state --workflow-id <id> --format json` has `epic` (`str | null`), next to `gates`. The exit code stays 0 or 1 by decision; readers parse stdout either way.

Interfaces consumed: `specs.change_epic(change: Path) -> str` (raises `SpecsError` without an `Epic:` line); `lifecycle_cli._recorded_epic(events, workflow_id) -> str` (`""` when none).

#### Step 1.1: Failing tests

In `tests/workflow_core/test_specs_reqs.py`, `test_living_blocks_with_scenarios`, add `"epic": None` to the expected dict right after `"change": None,`:

```python
            {"id": "REQ-AUTH-001", "title": "Sign in with password", "capability": "auth", "section": "LIVING",
             "change": None, "epic": None, "source": "docs/specs/auth/spec.md:9",
```

Add this test to `TestSpecsReqs`, after `test_open_changes_follow_living_and_archive_is_skipped`:

```python
    def test_change_rows_carry_the_epic_of_their_proposal(self):
        make_change(self.root, spec_delta=delta(added=ADDED_BLOCK))
        make_change(self.root, "ep-2-audit", epic="ep-2", spec_delta=delta(added=ADDED_BLOCK.replace("003", "004")))
        proposal = self.root / "docs/changes/ep-2-audit/01-proposal.md"
        proposal.write_text(proposal.read_text(encoding="utf-8").replace("Epic: ep-2\n", ""), encoding="utf-8")
        rows = {row["id"]: row["epic"] for row in self.payload()["requirements"]}
        self.assertEqual({"REQ-AUTH-001": None, "REQ-AUTH-002": None, "REQ-AUTH-003": "ep-1", "REQ-AUTH-004": None},
                         rows)
```

In `tests/workflow_core/test_lifecycle_cli.py`, add to `TestLifecycleCLI`, before `test_state_json_catalog_is_null_without_harness`:

```python
    def test_state_json_names_the_epic_recorded_at_orchestration_ready(self):
        def epic(workflow_id: str):
            with mock.patch("sys.stdout", new=io.StringIO()) as out:
                lifecycle_main(["state", "--workflow-id", workflow_id, "--repository", str(self.repo_path),
                                "--format", "json"])
            return json.loads(out.getvalue())["epic"]

        self.assertIsNone(epic("wf"))
        with mock.patch("sys.stdout", new=io.StringIO()), mock.patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(0, cli_main(["record", "orchestration-ready", "--workflow-id", "wf", "--epic", "ep-9",
                                          "--evidence", "beads", "--actor", "user",
                                          "--repository", str(self.repo_path)]))
        self.assertEqual("ep-9", epic("wf"))
        self.assertIsNone(epic("other"))
```

Run: `python3 -m pytest tests/workflow_core/test_specs_reqs.py tests/workflow_core/test_lifecycle_cli.py -q`
Expected: 3 failures (`KeyError: 'epic'` twice and the dict mismatch).

#### Step 1.2: Implementation

`plugins/gin-workflow/src/scripts/workflow_core/specs_reqs.py`, the import:

```python
from .specs import (Block, SpecsError, block_hash, change_epic, change_file, changes_dir, delta_blocks, living_files,
                    parse_blocks, shown)
```

Replace `_row` and `_delta_rows`:

```python
def _row(root: Path, path: Path, block: Block, change: str | None, epic: str | None = None) -> dict[str, Any]:
    return {"id": block.id, "title": block.title, "capability": block.cap,
            "section": "LIVING" if change is None else block.section, "change": change, "epic": epic,
            "hash": block_hash(block.text), "source": f"{shown(root, path)}:{block.start + 1}",
            "scenarios": scenarios(block)}
```

```python
def _delta_rows(root: Path, change: Path) -> list[dict[str, Any]]:
    blocks, errors = delta_blocks(root, change)
    if errors:
        raise SpecsError("; ".join(errors))
    try:
        epic: str | None = change_epic(change)
    except SpecsError:  # a proposal without an `Epic:` line
        epic = None
    return [_row(root, change_file(change, "spec-delta"), block, change.name, epic) for block in blocks]
```

`plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py`, in the state payload, after `"gates": gates_status,` (line 425):

```python
        "epic": _recorded_epic(events or (), workflow_id) or None,
```

Run: `python3 -m pytest tests/workflow_core/test_specs_reqs.py tests/workflow_core/test_lifecycle_cli.py -q`
Expected: all pass.

#### Step 1.3: Docs and version

`docs/reference/cli.md:139`:

```markdown
| `reqs [--change C]` | List requirements with section, hash, and the epic of the change that holds them |
```

`docs/reference/cli.md:50`, in the `state` paragraph, replace ``the last five `recent_quick` runs, and `review_waivers` `` with:

```markdown
the last five `recent_quick` runs, `epic` (the epic recorded at `orchestration-ready` for the workflow id, or `null`), and `review_waivers`
```

The repository keeps no upgrade notes (`docs/reference/upgrade-*.md` no longer exists), so none is written.

Set `"version": "2.1.2"` in the three gin-workflow manifests. In `tests/gin_orchestrator/test_harness_packaging.py:240`, set the expected version:

```python
                    self.assertEqual("2.1.2", json.load(file)["version"])
```

Run:

```bash
python3 -m pytest tests/workflow_core/test_specs_reqs.py tests/workflow_core/test_lifecycle_cli.py tests/gin_orchestrator/test_harness_packaging.py tests/workflow_core/test_docs_coverage.py -q
```

Expected: all pass.

#### Step 1.4: Commit

```bash
git add plugins/gin-workflow tests/workflow_core/test_specs_reqs.py tests/workflow_core/test_lifecycle_cli.py tests/gin_orchestrator/test_harness_packaging.py docs/reference/cli.md
git commit -m "feat(core): epic on specs reqs rows and in state JSON; gin-workflow 2.1.2 (gin-workflow-qa-manual-bugs)"
```

### Track 2: `gin-qa cases bug`
- **Dependencies**: Track 1
- **Files**:
  - Create `plugins/gin-qa/src/scripts/gin_qa/bugs.py`
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cases.py:288-314` (add `one_line` and `find`; `record_result` uses them)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py`:
    - `:1` (docstring)
    - `:11-13` (import `bugs`)
    - `:30-34` (`bug` parser, after the `result` parser)
    - `:202-205` (dispatch)
    - `:247` (usage text)
  - Test `tests/gin_qa/test_cases_bug.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one new module and CLI wiring with a clear spec. The edge cases are all listed and tested: an open bug kept without an epic, a closed or non-bead `Bug:`, a `Workflow:` spec, an unknown epic bead versus a tracker failure, a `Source:` outside the repository, `task create` failing, and recording failing after creation. The code and tests below were run on a scratch copy of the repository and pass.
- **Acceptance criteria**:
  - spec US-2, US-3, US-4 (CLI part), and US-5;
  - the "Finding the epic", `gin-qa cases bug`, and "Errors and compatibility" requirements;
  - every test in `tests/gin_qa/test_cases_bug.py` passes, and all other tests in `tests/gin_qa/` still pass.
- **Estimated complexity**: medium

Interfaces produced:
- `cases.one_line(value: str) -> str`: returns `value`. Raises `ValueError("<repr>: values are one non-empty line")` when the value is empty, only whitespace, or has a non-printable character (newline, tab).
- `cases.find(root: Path, cases_dir: str, case_id: str) -> Case`: raises `ValueError` for an unknown ID, or when the case files have a finding that names the case.
- `bugs.PRIORITY = {"high": "1", "medium": "2", "low": "3"}` (default `"2"`)
- `bugs.epic_of(root: Path, eff: Effective, case: Case) -> str | None`: `Source:` spec's `Epic:`, else its `Workflow:` id's `epic` from `gin-workflow state --workflow-id <topic> --repository <root> --format json` (exit 0 or 1, stdout parsed either way; no `epic` key → `None`); else the first REQ row with an `epic`.
- `bugs.description(case: Case, run: str | None, previous: str | None, actual: str, evidence: list[str]) -> str`
- `bugs.file_bug(root, eff, case_id, actual, evidence, *, external_ref=None, discovered_from=None, run=None) -> dict`:
  - returns `{"tc", "bug", "epic", "created", "file"}`; `epic` is `null` when an open bug was kept;
  - order: value checks → case → manual type → open previous bug (kept, no epic needed) → epic → epic bead check → `task create` → `record_result`.
  - raises `ValueError` or `QaError` for the exit-2 conditions.
- CLI:
  - `gin-qa cases bug <TC-ID> --actual TEXT [--evidence REF]... [--external-ref REF] [--discovered-from BEAD] [--run REF] [--repository P] [--format text|json]`;
  - text output: `<TC-ID> failed <bug>`.
- Error texts (stderr, prefixed `gin-qa error: ` by `main`):
  - `no epic for <TC-ID>; pass --discovered-from <bead>`
  - `<bead>: no such bead; pass --discovered-from <bead>`
  - `<TC-ID>: is a <type> case; cases bug files bugs for manual cases only`
  - `<TC-ID>: cannot read <path>: <reason>`
  - `<TC-ID>: <path> is outside the repository`
  - any other `task show` failure on the epic: its stderr (for example `Error: no beads database found`)
  - `filed <bug> but could not record it: <reason>; run gin-qa cases result <TC-ID> failed --bug <bug>`

Interfaces consumed:
- `gin-workflow task show <id> --json` (exit 1 with `no issue found` for a missing bead), `gin-workflow task create ... --body-file - --json` (description on stdin), `gin-workflow state ... --format json` (`epic` from Track 1);
- `cases.load`, `cases.record_result`, `cases.Case` (`fields`, `reqs`, `type`, `title`, `path`, `line`, `preconditions`, `test_data`, `steps`, `expected`);
- `reqs.Effective.reqs` (rows now carry `epic`), `reqs.QaError`;
- test helpers from `tests/gin_qa/qa_fixtures.py`: `ADDED_BLOCK`, `AUTH_SPEC`, `LAUNCHER`, `case_file`, `delta`, `hash8`, `make_change`, `make_repo`, `python_stub`, `qa`, `write`.

#### Step 2.1: Failing tests

Create `tests/gin_qa/test_cases_bug.py`:

```python
"""`gin-qa cases bug`: the epic of a manual case, the bug bead filed through `gin-workflow task`, and the result."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qa_fixtures import (ADDED_BLOCK, AUTH_SPEC, LAUNCHER, case_file, delta, hash8, make_change,  # noqa: E402
                         make_repo, python_stub, qa, write)

# `specs` runs this checkout's gin-workflow. Any other call is logged to calls.jsonl with its stdin and answered
# from answers.json, keyed by its first three words, then its first two. No answer: bd's unknown-id failure.
STUB = r'''#!@PYTHON@
import json, pathlib, subprocess, sys
here = pathlib.Path(__file__).resolve().parent
args = sys.argv[1:]
if args[:1] == ["specs"]:
    sys.exit(subprocess.run([sys.executable, @LAUNCHER@, *args]).returncode)
with open(here / "calls.jsonl", "a", encoding="utf-8") as log:
    log.write(json.dumps({"argv": args, "cwd": str(pathlib.Path.cwd()), "stdin": sys.stdin.read()}) + "\n")
answers = json.loads((here / "answers.json").read_text(encoding="utf-8"))
answer = answers.get(" ".join(args[:3]), answers.get(" ".join(args[:2])))
if answer is None:
    sys.stderr.write("Error fetching: no issue found\n")
    sys.exit(1)
if "write" in answer:
    pathlib.Path(answer["write"][0]).write_text(answer["write"][1], encoding="utf-8")
sys.stderr.write(answer.get("stderr", ""))
sys.stdout.write(answer.get("stdout", ""))
sys.exit(answer.get("code", 0))
'''

SPEC = ".planning/specs/2026-01-01-login-design.md"
FILE = "qa/cases/auth/TC-AUTH-001-sign-in.manual.md"
CASE = f"""# TC-AUTH-001: Sign in

- **Source:** {SPEC}#US-1
- **Priority:** low

**Preconditions:**
- a user exists

**Test data:**
- user: alice

**Steps:**
1. Open /login
2. Click "Sign in"

**Expected:**
- The dashboard is shown
"""


def shown(bead: str, status: str) -> dict:
    return {"stdout": json.dumps([{"id": bead, "status": status}])}


CREATED = {"stdout": json.dumps({"id": "gw-bug1", "status": "open"})}


class BugCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.bin = self.base / "bin"
        python_stub(self.bin, "gin-workflow",
                    STUB.replace("@PYTHON@", sys.executable).replace("@LAUNCHER@", repr(str(LAUNCHER))))
        self.answer({})

    def tearDown(self):
        self.tmp.cleanup()

    def answer(self, answers: dict) -> None:
        (self.bin / "answers.json").write_text(json.dumps(answers), encoding="utf-8")

    def calls(self) -> list[dict]:
        log = self.bin / "calls.jsonl"
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []

    def creates(self) -> list[dict]:
        return [call for call in self.calls() if call["argv"][:2] == ["task", "create"]]

    @staticmethod
    def option(argv: list[str], name: str) -> str:
        return argv[argv.index(name) + 1]

    def bug(self, *args: str):
        return qa(self.root, self.bin, "bug", *args)


class TestLegacy(BugCase):
    def setUp(self):
        super().setUp()
        self.root = make_repo(self.base / "repo", layout="legacy")
        write(self.root, SPEC, "# Login\n\nEpic: gw-epic\nStatus: confirmed\n")
        self.path = write(self.root, FILE, CASE)

    def test_files_a_bug_linked_to_the_spec_epic_and_records_it(self):
        self.answer({"task show gw-epic": shown("gw-epic", "in_progress"), "task create": CREATED})
        result = self.bug("TC-AUTH-001", "--actual", "An error page is shown", "--evidence", "shots/1.png",
                          "--evidence", "https://logs.example/42", "--run", "manual 2026-11-04", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"tc": "TC-AUTH-001", "bug": "gw-bug1", "epic": "gw-epic", "created": True, "file": FILE},
                         json.loads(result.stdout))
        [call] = self.creates()
        argv = call["argv"]
        self.assertEqual(["task", "create", "-t", "bug"], argv[:4])
        self.assertEqual("TC-AUTH-001: Sign in", self.option(argv, "--title"))
        self.assertEqual("-", self.option(argv, "--body-file"))
        self.assertEqual("discovered-from:gw-epic", self.option(argv, "--deps"))
        self.assertEqual("3", self.option(argv, "-p"))
        self.assertEqual("--json", argv[-1])
        self.assertNotIn("--external-ref", argv)
        self.assertFalse(any("\n" in arg for arg in argv))
        self.assertEqual(
            f"- Case: {FILE}:1\n- Run: manual 2026-11-04\n\n"
            "## Preconditions\n\n- a user exists\n\n## Test data\n\n- user: alice\n\n"
            "## Steps\n\n1. Open /login\n2. Click \"Sign in\"\n\n## Expected\n\n- The dashboard is shown\n\n"
            "## Actual\n\nAn error page is shown\n\n## Evidence\n\n- shots/1.png\n- https://logs.example/42",
            call["stdin"])
        text = self.path.read_text(encoding="utf-8")
        for line in ("- **Result:** failed\n", "- **Run:** manual 2026-11-04\n", "- **Bug:** gw-bug1\n"):
            self.assertIn(line, text)
        self.assertTrue(all(Path(call["cwd"]).resolve() == self.root.resolve() for call in self.calls()))

    def test_keeps_the_current_run_and_names_a_bug_value_that_is_not_a_bead(self):
        write(self.root, FILE, CASE.replace("- **Priority:** low\n",
                                            "- **Result:** failed\n- **Run:** manual 2026-01-01\n- **Bug:** JIRA-12\n"))
        self.answer({"task show gw-epic": shown("gw-epic", "open"), "task create": CREATED})
        result = self.bug("TC-AUTH-001", "--actual", "Nothing happens")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("TC-AUTH-001 failed gw-bug1", result.stdout.strip())
        [call] = self.creates()
        self.assertEqual("2", self.option(call["argv"], "-p"))
        self.assertIn("- Run: manual 2026-01-01\n- Previous bug: JIRA-12\n\n", call["stdin"])
        self.assertNotIn("## Evidence", call["stdin"])
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("- **Run:** manual 2026-01-01\n", text)
        self.assertIn("- **Bug:** gw-bug1\n", text)

    def test_an_open_bug_is_kept_without_an_epic_and_a_closed_bug_is_replaced(self):
        write(self.root, SPEC, "# Login\n")
        write(self.root, FILE, CASE.replace("- **Priority:** low\n",
                                            "- **Priority:** low\n- **Result:** failed\n- **Bug:** gw-7\n"))
        self.answer({"task show gw-7": shown("gw-7", "in_progress")})
        result = self.bug("TC-AUTH-001", "--actual", "Still broken", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"tc": "TC-AUTH-001", "bug": "gw-7", "epic": None, "created": False, "file": FILE},
                         json.loads(result.stdout))
        self.assertEqual([], self.creates())
        self.assertIn("- **Bug:** gw-7\n", self.path.read_text(encoding="utf-8"))
        write(self.root, SPEC, "# Login\n\nEpic: gw-epic\n")
        self.answer({"task show gw-epic": shown("gw-epic", "open"), "task show gw-7": shown("gw-7", "closed"),
                     "task create": CREATED})
        result = self.bug("TC-AUTH-001", "--actual", "Broken again", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(("gw-bug1", True), (json.loads(result.stdout)["bug"], json.loads(result.stdout)["created"]))
        [call] = self.creates()
        self.assertIn("- Previous bug: gw-7\n", call["stdin"])

    def test_a_workflow_spec_uses_the_epic_recorded_for_its_workflow(self):
        write(self.root, SPEC, "# Login\n\nWorkflow: login\n")
        self.answer({"state --workflow-id login": {"stdout": json.dumps({"epic": "gw-login"}), "code": 1},
                     "task show gw-login": shown("gw-login", "closed"), "task create": CREATED})
        result = self.bug("TC-AUTH-001", "--actual", "Error", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("gw-login", json.loads(result.stdout)["epic"])
        [call] = self.creates()
        self.assertEqual("discovered-from:gw-login", self.option(call["argv"], "--deps"))

    def test_no_epic_exits_2_until_a_bead_is_given(self):
        write(self.root, SPEC, "# Login\n\nWorkflow: login\n")
        before = self.path.read_text(encoding="utf-8")
        result = self.bug("TC-AUTH-001", "--actual", "Error")
        self.assertEqual(2, result.returncode)
        self.assertIn("no epic for TC-AUTH-001; pass --discovered-from <bead>", result.stderr)
        self.assertEqual([], [call for call in self.calls() if call["argv"][0] == "task"])
        self.assertEqual(before, self.path.read_text(encoding="utf-8"))
        self.answer({"task show gw-other": shown("gw-other", "open"), "task create": CREATED})
        result = self.bug("TC-AUTH-001", "--actual", "Error", "--discovered-from", "gw-other",
                          "--external-ref", "JIRA-9")
        self.assertEqual(0, result.returncode, result.stderr)
        [call] = self.creates()
        self.assertEqual("discovered-from:gw-other", self.option(call["argv"], "--deps"))
        self.assertEqual("JIRA-9", self.option(call["argv"], "--external-ref"))

    def test_an_unknown_epic_a_tracker_failure_or_a_failing_create_writes_nothing(self):
        before = self.path.read_text(encoding="utf-8")
        result = self.bug("TC-AUTH-001", "--actual", "Error")
        self.assertEqual(2, result.returncode)
        self.assertIn("gw-epic: no such bead", result.stderr)
        self.answer({"task show gw-epic": {"stderr": "Error: no beads database found\n", "code": 1}})
        result = self.bug("TC-AUTH-001", "--actual", "Error")
        self.assertEqual(2, result.returncode)
        self.assertIn("no beads database found", result.stderr)
        self.assertNotIn("no such bead", result.stderr)
        self.assertEqual([], self.creates())
        self.answer({"task show gw-epic": shown("gw-epic", "open"),
                     "task create": {"stderr": "bd: database is locked\n", "code": 1}})
        result = self.bug("TC-AUTH-001", "--actual", "Error")
        self.assertEqual(2, result.returncode)
        self.assertIn("bd: database is locked", result.stderr)
        self.assertEqual(before, self.path.read_text(encoding="utf-8"))

    def test_a_bead_created_but_not_recorded_is_named(self):
        broken = {**CREATED, "write": [str(self.path), "# not a test case\n"]}
        self.answer({"task show gw-epic": shown("gw-epic", "open"), "task create": broken})
        result = self.bug("TC-AUTH-001", "--actual", "Error")
        self.assertEqual(2, result.returncode)
        self.assertIn("filed gw-bug1 but could not record it", result.stderr)
        self.assertIn("gin-qa cases result TC-AUTH-001 failed --bug gw-bug1", result.stderr)

    def test_usage_errors_exit_2_and_call_nothing(self):
        write(self.root, "qa/cases/auth/TC-AUTH-002.e2e.md", case_file("TC-AUTH-002", f"Source: {SPEC}#US-1"))
        write(self.root, "qa/cases/auth/TC-AUTH-003.manual.md", case_file("TC-AUTH-003", "Source: missing.md#US-1"))
        write(self.root, "qa/cases/auth/TC-AUTH-004.manual.md", case_file("TC-AUTH-004", "Source: ../outside.md#US-1"))
        before = self.path.read_text(encoding="utf-8")
        for args, error in (
                (("TC-AUTH-002", "--actual", "x"), "TC-AUTH-002: is a e2e case; cases bug files bugs for manual"),
                (("TC-AUTH-003", "--actual", "x"), "TC-AUTH-003: cannot read missing.md"),
                (("TC-AUTH-004", "--actual", "x"), "TC-AUTH-004: ../outside.md is outside the repository"),
                (("TC-AUTH-099", "--actual", "x"), "TC-AUTH-099: no such test case"),
                (("TC-AUTH-001", "--actual", " "), "values are one non-empty line"),
                (("TC-AUTH-001", "--actual", "x", "--evidence", "a\nb"), "values are one non-empty line"),
                (("TC-AUTH-001", "--actual", "x", "--run", ""), "values are one non-empty line")):
            with self.subTest(args=args):
                result = self.bug(*args)
                self.assertEqual(2, result.returncode)
                self.assertIn(error, result.stderr)
        self.assertEqual([], self.calls())
        self.assertEqual(before, self.path.read_text(encoding="utf-8"))


class TestSdd(BugCase):
    def setUp(self):
        super().setUp()
        self.root = make_repo(self.base / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        make_change(self.root, spec_delta=delta(added=ADDED_BLOCK))

    def ref(self, *reqs: str) -> str:
        return "REQ: " + ", ".join(f"{req}@{hash8(self.root, self.bin, req)}" for req in reqs)

    def test_the_epic_comes_from_the_first_req_in_a_change(self):
        write(self.root, "qa/cases/auth/TC-AUTH-001.manual.md",
              case_file("TC-AUTH-001", self.ref("REQ-AUTH-001", "REQ-AUTH-003")))
        self.answer({"task show ep-1": shown("ep-1", "in_progress"), "task create": CREATED})
        result = self.bug("TC-AUTH-001", "--actual", "Locked out after 3 tries", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("ep-1", json.loads(result.stdout)["epic"])
        [call] = self.creates()
        self.assertEqual("discovered-from:ep-1", self.option(call["argv"], "--deps"))
        self.assertEqual("1", self.option(call["argv"], "-p"))

    def test_living_reqs_only_have_no_epic(self):
        write(self.root, "qa/cases/auth/TC-AUTH-001.manual.md", case_file("TC-AUTH-001", self.ref("REQ-AUTH-001")))
        result = self.bug("TC-AUTH-001", "--actual", "Error")
        self.assertEqual(2, result.returncode)
        self.assertIn("no epic for TC-AUTH-001", result.stderr)


if __name__ == "__main__":
    unittest.main()
```

Run: `python3 -m pytest tests/gin_qa/test_cases_bug.py -q`
Expected: every test fails. argparse rejects `bug`, so each run exits 2 with `invalid choice: 'bug'`.

#### Step 2.2: Shared helpers in `cases.py`

In `plugins/gin-qa/src/scripts/gin_qa/cases.py`, add before `record_result`:

```python
def one_line(value: str) -> str:
    """A value written into a case file or a bead: one non-empty line of printable characters."""
    if not value.strip() or not value.isprintable():
        raise ValueError(f"{value!r}: values are one non-empty line")
    return value


def find(root: Path, cases_dir: str, case_id: str) -> Case:
    """The case `case_id`; refused when the case files have a finding that names it."""
    cases, findings = load(root, cases_dir)
    located = next((case for case in cases if case.id == case_id), None)
    if located is None:
        raise ValueError(f"{case_id}: no such test case")
    about = [error for error in findings if re.search(rf"\b{re.escape(case_id)}\b", error)]
    if about:
        raise ValueError("; ".join(about))
    return located
```

In `record_result`, replace the value loop and the lookup (from `for value in (run, bug):` through `raise ValueError("; ".join(about))`) with:

```python
    for value in (run, bug):
        if value is not None:
            one_line(value)
    located = find(root, cases_dir, case_id)
```

Run: `python3 -m pytest tests/gin_qa/test_cases_cli.py -q`
Expected: all pass (no behaviour change).

#### Step 2.3: `bugs.py`

Create `plugins/gin-qa/src/scripts/gin_qa/bugs.py`:

```python
"""`gin-qa cases bug`: file a bug bead for a failed manual case, linked to the epic the case was written for."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from . import cases as tc
from .reqs import Effective, QaError

_EPIC = re.compile(r"^Epic: (\S+)$", re.MULTILINE)
_WORKFLOW = re.compile(r"^Workflow: (\S+)$", re.MULTILINE)
PRIORITY = {"high": "1", "medium": "2", "low": "3"}


def _gin_workflow(root: Path, *args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    """`gin-workflow ...` in the repository: `task` runs bd against the current directory's database."""
    executable = shutil.which("gin-workflow")
    if executable is None:
        raise QaError("gin-workflow is not on PATH; install gin-workflow first")
    return subprocess.run([executable, *args], cwd=root, input=stdin, capture_output=True, text=True)


def _record(stdout: str) -> dict[str, Any] | None:
    """The first object of a `--json` answer: bd prints a list for show and one object for create."""
    try:
        data = json.loads(stdout)
    except ValueError:
        return None
    row = data[0] if isinstance(data, list) and data else data
    return row if isinstance(row, dict) else None


def _show(root: Path, bead: str) -> tuple[dict[str, Any] | None, str]:
    """(the bead, "") when found; (None, "") when the tracker has no such bead; (None, <stderr>) on any other failure."""
    shown = _gin_workflow(root, "task", "show", bead, "--json")
    if shown.returncode == 0:
        return _record(shown.stdout), ""
    if "no issue" in shown.stderr + shown.stdout:
        return None, ""
    return None, shown.stderr.strip() or f"gin-workflow task show exited {shown.returncode}"


def _workflow_epic(root: Path, topic: str) -> str | None:
    """The epic recorded at orchestration-ready for a `Workflow: <topic>` spec (`gin-workflow state`)."""
    state = _gin_workflow(root, "state", "--workflow-id", topic, "--repository", str(root), "--format", "json")
    try:
        epic = json.loads(state.stdout).get("epic")
    except (ValueError, AttributeError):
        return None
    return epic if isinstance(epic, str) and epic else None


def epic_of(root: Path, eff: Effective, case: tc.Case) -> str | None:
    """Legacy: the spec named in `Source:` (its `Epic:` line, else the epic of its `Workflow:`).
    SDD: the first REQ whose change has an epic."""
    source = case.fields.get("Source")
    if source:
        relative = source.split("#", 1)[0].strip()
        path = (root / relative).resolve()
        if root.resolve() not in path.parents:
            raise QaError(f"{case.id}: {relative} is outside the repository")
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise QaError(f"{case.id}: cannot read {relative}: {getattr(error, 'strerror', None) or error}") from error
        if found := _EPIC.search(text):
            return found.group(1)
        topic = _WORKFLOW.search(text)
        return _workflow_epic(root, topic.group(1)) if topic else None
    return next((eff.reqs[req]["epic"] for req, _ in case.reqs if eff.reqs.get(req, {}).get("epic")), None)


def description(case: tc.Case, run: str | None, previous: str | None, actual: str, evidence: list[str]) -> str:
    head = [f"- Case: {case.path}:{case.line}", *([f"- Run: {run}"] if run else []),
            *([f"- Previous bug: {previous}"] if previous else [])]
    sections = [("Preconditions", [f"- {item}" for item in case.preconditions]),
                ("Test data", [f"- {item}" for item in case.test_data]),
                ("Steps", [f"{number}. {step}" for number, step in enumerate(case.steps, 1)]),
                ("Expected", [f"- {item}" for item in case.expected]),
                ("Actual", [actual]),
                ("Evidence", [f"- {item}" for item in evidence])]
    return "\n\n".join(["\n".join(head), *(f"## {name}\n\n" + "\n".join(lines) for name, lines in sections if lines)])


def file_bug(root: Path, eff: Effective, case_id: str, actual: str, evidence: list[str], *,
             external_ref: str | None = None, discovered_from: str | None = None,
             run: str | None = None) -> dict[str, Any]:
    """Record `failed` on a manual case with its open bug, or with a new bug bead filed against the case's epic."""
    for value in (actual, *evidence, *(item for item in (external_ref, discovered_from, run) if item is not None)):
        tc.one_line(value)
    case = tc.find(root, eff.cases_dir, case_id)
    if case.type != "manual":
        raise ValueError(f"{case_id}: is a {case.type or 'untyped'} case; cases bug files bugs for manual cases only")
    run = run if run is not None else case.fields.get("Run")
    previous = case.fields.get("Bug")
    if previous:
        old, _ = _show(root, previous)  # a value that is not a readable bead counts as no open bug
        if old is not None and old.get("status") not in (None, "closed"):
            row = tc.record_result(root, eff.cases_dir, case_id, "failed", run, previous)
            return {"tc": case_id, "bug": previous, "epic": None, "created": False, "file": row["file"]}
    epic = discovered_from or epic_of(root, eff, case)
    if epic is None:
        raise QaError(f"no epic for {case_id}; pass --discovered-from <bead>")
    found, failure = _show(root, epic)
    if failure:
        raise QaError(failure)
    if found is None:
        raise QaError(f"{epic}: no such bead; pass --discovered-from <bead>")
    priority = PRIORITY.get(case.fields.get("Priority", "").strip().lower(), "2")
    # the description goes on stdin: a Windows .cmd shim cuts an argument at its first newline
    argv = ["task", "create", "-t", "bug", "--title", f"{case_id}: {case.title}".replace('"', "'"),
            "--body-file", "-", "--deps", f"discovered-from:{epic}", "-p", priority,
            *(["--external-ref", external_ref] if external_ref else []), "--json"]
    created = _gin_workflow(root, *argv, stdin=description(case, run, previous, actual, evidence))
    if created.returncode != 0:
        raise QaError(created.stderr.strip() or f"gin-workflow task create exited {created.returncode}")
    bug = (_record(created.stdout) or {}).get("id")
    if not isinstance(bug, str) or not bug:
        raise QaError(f"gin-workflow task create printed no bead id: {created.stdout.strip()[:200]!r}")
    try:
        row = tc.record_result(root, eff.cases_dir, case_id, "failed", run, bug)
    except (ValueError, OSError) as error:
        raise QaError(f"filed {bug} but could not record it: {error}; "
                      f"run gin-qa cases result {case_id} failed --bug {bug}") from error
    return {"tc": case_id, "bug": bug, "epic": epic, "created": True, "file": row["file"]}
```

#### Step 2.4: CLI wiring

In `plugins/gin-qa/src/scripts/gin_qa/cli.py`:

- Line 11: `from . import cases as tc` stays. Add `bugs` to the next import: `from . import bugs, e2e, report`.
- In `_parser()`, after the `result` parser (after `item.add_argument("--bug")`):

```python
    item = sub.add_parser("bug", parents=[common])
    item.add_argument("id")
    item.add_argument("--actual", required=True)
    item.add_argument("--evidence", action="append", default=[])
    item.add_argument("--external-ref")
    item.add_argument("--discovered-from")
    item.add_argument("--run")
```

- In `_run`, after the `result` branch:

```python
    if args.command == "bug":
        row = bugs.file_bug(root, eff, args.id, args.actual, args.evidence, external_ref=args.external_ref,
                            discovered_from=args.discovered_from, run=args.run)
        _emit(row, args.format, f"{row['tc']} failed {row['bug']}")
        return 0
```

- In `main`, the usage text: `gin-qa cases {plan,next-id,pin,result,bug,split,check,export} ...`.

Run: `python3 -m pytest tests/gin_qa -q`
Expected: all pass.

#### Step 2.5: Commit

```bash
git add plugins/gin-qa/src/scripts/gin_qa tests/gin_qa/test_cases_bug.py
git commit -m "feat(gin-qa): cases bug files a bug bead linked to the case's epic (gin-workflow-qa-manual-bugs)"
```

### Track 3: `/gin-qa:run`, docs, and gin-qa 0.8
- **Dependencies**: Track 2
- **Files**:
  - Create `plugins/gin-qa/src/skills/run/SKILL.md`
  - Modify `plugins/gin-qa/src/skills/cases/SKILL.md` (last line)
  - Modify `tests/gin_qa/test_packaging.py:35` (`expected` adds `"run": []`)
  - Modify `docs/guides/qa.md`:
    - `:3` (intro)
    - new section before `:54` (`## End-to-end specs`)
    - `:117` (Commands)
  - Modify `docs/reference/cli.md`:
    - `:386` (group list)
    - new `### gin-qa cases bug` after the `cases result` section, before `:396`
  - Modify `docs/reference/skills.md:63-65` (add `report` and `run` rows)
  - Modify `docs/roles.md:12` (Tester row)
  - Modify versions:
    - `plugins/gin-qa/src/scripts/gin_qa/cli.py:15` (`VERSION = "0.8"`)
    - `plugins/gin-qa/plugin.meta.json:3`, `plugins/gin-qa/src/.claude-plugin/plugin.json:3`, `plugins/gin-qa/src/.codex-plugin/plugin.json:3` (`0.9.0`)
    - `install.sh:13`, `install.ps1:19` (`0.8`)
    - `tests/install_smoke_test.sh:190,397-400,403,486` and `tests/install_smoke_test.ps1:72,134-138,193` (launcher `0.7` → `0.8`; the `old_version=0.4` / `Old = '0.4'` values stay)
- **Provider role**: `docs`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** a short skill, docs, and version strings, all with the exact text given below.
- **Acceptance criteria**:
  - spec US-1 and US-4 (skill part);
  - `python3 -m pytest -n auto` passes;
  - `bash tests/install_smoke_test.sh` passes;
  - the docs describe the command and the skill as built.
- **Estimated complexity**: low

Interfaces consumed: the CLI and error texts from Track 2. `gin-qa cases export --format json` rows with `id`, `title`, `capability`, `type`, `preconditions`, `test_data`, `steps`, `expected`, `result`, and `bug` (`cases.as_dict`).

#### Step 3.1: Packaging test first

`tests/gin_qa/test_packaging.py:35`, set:

```python
        expected = {"cases": ["../../templates/guidelines.md", "../../templates/qa-readme.md", "../../templates/cases.md"], "e2e": ["references/explore-case.md"] * 2, "report": [], "run": []}
```

Run: `python3 -m pytest tests/gin_qa/test_packaging.py -q`
Expected: `test_skill_budget_and_links` fails (no `run` folder).

#### Step 3.2: The skill

Create `plugins/gin-qa/src/skills/run/SKILL.md`:

```markdown
---
name: run
description: Walk the manual test cases of a capability with a tester, record each result, and file a bug bead linked to the case's epic for each failure.
---

# Manual Run

`/gin-qa:run <capability>`. Results are written by `gin-qa cases result`, bugs by `gin-qa cases bug`; never edit a case file yourself.

1. Preconditions: `gin-workflow` and `gin-qa` are on `PATH`. Otherwise stop and name what to install: `install.sh --plugin gin-qa` (or `--plugin all`) from a gin-workflow clone or through `remote-install.sh`.
2. Run `gin-qa cases export --format json` and keep the cases whose `capability` is the one given and whose `type` is `manual`, sorted by `id`. None: say so and stop.
3. Ask the tester once for a run reference. The default is `manual <YYYY-MM-DD>` with today's UTC date.
4. Show one case at a time: ID and title, preconditions, test data, numbered steps, expected, and its current `result` and `bug`. Ask for `passed`, `failed`, `blocked`, or `skip`.
   - `passed` or `blocked`: run `gin-qa cases result <TC-ID> <status> --run "<ref>"`.
   - `skip`: write nothing.
   - `failed`: ask what happened instead, the evidence references (screenshots, logs, links; none is fine), and an optional external tracker reference. Then run `gin-qa cases bug <TC-ID> --actual "<text>" [--evidence "<ref>"]... [--external-ref "<ref>"] --run "<ref>" --format json`.
   - `cases bug` exits 2 with `no epic for <TC-ID>` or `no such bead`: run `gin-workflow task list --type epic --json` and offer its epics (id and title) as choices, plus another bead id. Run `cases bug` again with `--discovered-from <bead>`. Any other exit 2 (no Beads, no `gin-workflow task`): show stderr and ask whether to go on with the next case.
   Each value is one line; ask again for an empty answer. Quote every value for the shell.
5. End with the number of passed, failed, blocked, and skipped cases, and each bug as `<TC-ID> <bug>`, marked filed (`created: true`) or kept open (`created: false`). A kept bug did not get the new actual result or evidence: say so, so the tester can add them to the bug.
6. Never choose a result or file a bug on your own judgement: the tester gives every answer. Do not commit; the tester reviews and commits the case files.
```

Run: `python3 -m pytest tests/gin_qa/test_packaging.py -q`
Expected: all pass.

#### Step 3.3: Cases skill and docs

`plugins/gin-qa/src/skills/cases/SKILL.md`, last line:

```markdown
An HTML report: `/gin-qa:report`. A manual run that records results and files bugs: `/gin-qa:run`. Other formats: `export --format json` lists every case with its fields, `result`, `run`, `bug`, and `test_data`; build them from that.
```

`docs/guides/qa.md:3`:

```markdown
`gin-qa` is an optional plugin that writes test cases from your specs, walks a tester through the manual cases and files a bug bead for each failure, turns end-to-end cases into Playwright specs with recorded evidence, and reports on both in one offline HTML page. It needs `gin-workflow` and is not installed by default.
```

`docs/guides/qa.md`, insert before `## End-to-end specs: \`/gin-qa:e2e\``:

```markdown
## Manual runs: `/gin-qa:run`

`/gin-qa:run <capability>` shows each `.manual.md` case of the capability in ID order and asks the tester for `passed`, `failed`, `blocked`, or `skip`. It asks for a run reference once, `manual <YYYY-MM-DD>` by default, and writes it on every case it records. `skip` writes nothing.

A failure asks for what happened, evidence references, and an optional external tracker reference, then runs `gin-qa cases bug`:

- The bug is a bead filed through `gin-workflow task create`, linked to the case's epic with `discovered-from`, so the [usage report](../reference/cli.md#gin-workflow-usage) of that epic counts it.
- The epic comes from the spec named in `Source:` (legacy layout): its `Epic:` line, or the epic recorded at `orchestration-ready` for its `Workflow:` id. In the SDD layout it comes from the change that holds the first of the case's REQs that is in a change; a REQ already archived into the living spec has none. With no epic, the skill lists the open epics to pick from.
- The usage report counts the bug under its epic whether QA found it before or after ship.
- The description holds the case file, the run, the preconditions, test data, steps, expected, the actual result, and the evidence.
- When the case's `Bug:` names a bead that is still open, no bug is filed and the case keeps it; the new actual result and evidence are not added to it. A closed bug gets a new bug that names it.
- Teams whose tracker is Jira or Linear still file the ticket there; `--external-ref` only records its key on the bead.
- Priority follows the case: `high` → 1, `medium` → 2, `low` → 3, none → 2.

The skill never edits case files and never commits.
```

The link target `../reference/cli.md#gin-workflow-usage` is the `## \`gin-workflow usage\`` heading (`docs/reference/cli.md:338`).

`docs/guides/qa.md:117` (Commands):

```markdown
`gin-qa cases {plan,next-id,pin,result,bug,split,check,export}`, `gin-qa e2e {init,plan,pin,run,check,export}`, and `gin-qa report [capability] [--out DIR]`; exit 0 ok, 1 findings, 2 usage or environment error. See [CLI](../reference/cli.md#gin-qa) and the [`qa` configuration keys](../reference/config.md#qa).
```

`docs/reference/cli.md:386`: replace `gin-qa cases {plan,next-id,pin,result,split,check,export}` with `gin-qa cases {plan,next-id,pin,result,bug,split,check,export}`.

`docs/reference/cli.md`, insert after the `cases result` section's `Output:` line, before `### \`gin-qa cases split\``:

```markdown
### `gin-qa cases bug`

`gin-qa cases bug <TC-ID> --actual TEXT [--evidence REF]... [--external-ref REF] [--discovered-from BEAD] [--run REF]` records `failed` on a manual case and files a bug bead for it.

- When the case's `Bug:` is a bead that `gin-workflow task show` reports as not closed, no bead is created, the case keeps that bug, and `epic` is `null`. No epic is needed.
- Otherwise the epic is found:
  - from the spec named in `Source:`, which must be inside the repository: its `Epic:` line, or the `epic` of `gin-workflow state --workflow-id <topic>` for its `Workflow: <topic>` line;
  - or, with REQs, the `epic` of the first of the case's REQs that has one in `gin-workflow specs reqs`.
- `--discovered-from` replaces the epic found. The epic must be a bead `gin-workflow task show` can read.
- It then runs `gin-workflow task create -t bug --title "<TC-ID>: <title>" --body-file - --deps discovered-from:<epic> -p <priority> [--external-ref REF] --json` in the repository, with the description on stdin. Then it writes `Result: failed`, the run (`--run`, else the case's current `Run`), and the new bug.

Exit 2, writing nothing, when:

- the ID does not exist, or the case is not `manual`;
- an option value is empty or not one printable line;
- no epic is found (`no epic for <TC-ID>; pass --discovered-from <bead>`), or the epic is not a bead (`<epic>: no such bead`);
- the spec named in `Source:` is outside the repository or cannot be read;
- `task show` on the epic fails for another reason, or `task create` fails (their stderr is passed on).

When the bead is created but the result cannot be recorded, it exits 2 and names the bead and the `cases result` command to run.

Output: text `TC-AUTH-001 failed gw-12`; JSON `{"tc", "bug", "epic", "created", "file"}`.
```

`docs/reference/skills.md`, after the `e2e` row:

```markdown
| `report` | Write an offline HTML report of the test cases, with charts, filters, and per-step e2e screenshots |
| `run` | Walk the manual cases of a capability with a tester, record each result, and file a bug bead linked to the case's epic for each failure |
```

`docs/roles.md:12`, the Tester row:

```markdown
| Tester | `/gin-qa:cases`, `/gin-qa:run`, `/gin-qa:e2e`, `/gin-qa:report`, `/gin-workflow:progress` | `qa/cases/`, `qa/e2e/`, `qa/evidence/` | reviews the developer's pull request | `ship` |
```

#### Step 3.4: Versions

- `plugins/gin-qa/src/scripts/gin_qa/cli.py:15`: `VERSION = "0.8"`.
- `"version": "0.9.0"` in `plugins/gin-qa/plugin.meta.json`, `plugins/gin-qa/src/.claude-plugin/plugin.json`, and `plugins/gin-qa/src/.codex-plugin/plugin.json`.
- `install.sh:13`: `QA_LAUNCHER_VERSION="0.8"`. `install.ps1:19`: `$QaLauncherVersion = '0.8'`.
- `tests/install_smoke_test.sh`: in lines 190, 397-400, and 403, replace `0.7` with `0.8`. Line 486 becomes `gin-qa) old_version=0.4; current_version=0.8 ;;`.
- `tests/install_smoke_test.ps1`: in lines 72 and 134-138, replace `0.7` with `0.8`. Line 193 becomes `@{ Name = 'gin-qa'; Old = '0.4'; Current = '0.8' },`.

Run:

```bash
python3 -m pytest -n auto -q
bash tests/install_smoke_test.sh
```

Expected: pytest is all green; the smoke script exits 0.

#### Step 3.5: Commit

```bash
git add plugins/gin-qa tests/gin_qa/test_packaging.py tests/install_smoke_test.sh tests/install_smoke_test.ps1 install.sh install.ps1 docs/guides/qa.md docs/reference/cli.md docs/reference/skills.md docs/roles.md
git commit -m "docs(gin-qa): /gin-qa:run skill and cases bug docs; gin-qa 0.9.0 (gin-workflow-qa-manual-bugs)"
```

## Integration
- **Branch**: `feat/qa-manual-bugs`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes
- [ ] `bash tests/install_smoke_test.sh` passes
- [ ] End to end on a scratch repository with Beads, after `install.sh --plugin all`:
  - `gin-qa cases bug` on a manual case files a bug;
  - `bd dep list <epic> --direction=up --type discovered-from` lists it;
  - a second run with the bug still open creates nothing;
  - a case whose `Source:` spec has only `Workflow: <topic>` files its bug against the epic recorded for that workflow.

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog (`haiku`, `sonnet`, `opus`; `low` … `max`) using the route rubric.
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- The Parent Bead (`gin-workflow-qa-manual-bugs`) stays open until the human-confirmed merge. Track beads close once their tests and review pass.
- Plan review (2026-11-04): an independent reviewer prototyped the first draft. Its findings are folded in, and the spec was amended with the user's choice of scope:
  - **Description on stdin.** It now goes on stdin (`--body-file -`): a Windows `.cmd` shim cuts an argument at its first newline, which would drop `--deps` and file an unlinked bug. The title's `"` becomes `'`.
  - **Fixtures with `Result:`.** Fixtures that hold `Run:`/`Bug:` carry a `Result:` line; without it the parser refuses the case.
  - **No upgrade note.** The repository has no `docs/reference/upgrade-*.md`.
  - **Missing bead vs tracker failure.** `no such bead` only when the tracker reports no such bead; any other `task show` failure on the epic passes its stderr on, so the skill does not ask for bead ids while Beads is missing.
  - **Open bug first.** The open-bug check runs before the epic lookup, so a re-run with an open bug needs no epic.
  - **Epic of a `Workflow:` spec.** It comes from `gin-workflow state` (user's choice over a team-mode-only label lookup), and the skill offers the open epics when none is found.
  - **`Source:` stays inside the repository.** A path outside it exits 2.
- Spec refinements made while planning (2026-11-04):
  - **Epic must exist.** `cases bug` checks the epic with `gin-workflow task show` before it creates anything, and exits 2 with `<epic>: no such bead` when it is missing. Reason: `bd create --deps discovered-from:<unknown>` creates the bug unlinked and only warns, which would break "every bug filed through gin-qa is linked" (US-4).
  - **No lookup with `--discovered-from`.** With `--discovered-from`, the `Source:` spec is not read, so an unreadable spec does not block a bead the tester named.
  - **Error prefix.** Error lines carry the CLI's usual `gin-qa error: ` prefix, not `gin-qa: `.
  - **New module.** The code lives in a new module, `bugs.py`, rather than in `cases.py`. `cases.py` stays the owner of case files and gains only the shared `one_line` and `find`.
- `docs/reference/skills.md` gains a `report` row too: the table was missing it.

# Plan: gin-qa automated test types beyond e2e

Epic: gin-workflow-qa-test-types
Spec: .planning/specs/2026-11-04-qa-test-types-design.md

## Objective

`api`, `unit`, `integration`, and any other automated case type a project declares get the path e2e cases have. The flow is: `gin-qa tests plan` lists the work, a test is written with a `TC: <TC-ID>@<hash8>` marker, `gin-qa tests pin`/`check` keep it in step with the case, and `gin-qa tests run --type <T>` runs the project's own command and records each case's result from the JUnit XML it writes. `/gin-qa:tests <capability> --type <T>` lets the agent do all of this in the project's own test style.

Goal (from the spec): test cases of type `api`, `integration`, `unit`, or any other type a team automates get the same path e2e cases have: tests are planned from the cases, pinned to a case version, run, checked, and their results recorded in the case files.

Architecture: a new module `plugins/gin-qa/src/scripts/gin_qa/tests.py` holds four parts:
- The parser for the `## Automated types` section of the guidelines file.
- The file walk and marker scan.
- `plan`/`pin`/`check`.
- `run`.

It reuses `cases.load`, `cases.hash8`, `cases.as_dict`, `cases.TC_ID`, `cases.TYPE`, `cases.glob_regex`, `cases.write_atomic`, and `cases.record_result`. `e2e.py` gets one extracted helper, `new_run_folder`, which `e2e.run` and `tests.run` share; e2e behaviour does not change. `cli.py` adds a fourth top-level group, `tests`. `report.py` shows a `tests run` folder as a plain run reference.

Tech Stack: Python 3 stdlib (`shlex`, `subprocess`, `xml.etree.ElementTree`, `os.walk`) in the gin-qa CLI; `unittest` tests run by `python3 -m pytest -n auto`; Markdown skill, template, and docs.

### Global Constraints (verbatim from the spec)

- Out of scope: Playwright and e2e specifics (`gin-qa e2e` is unchanged); performance or load tests; a new agent; selecting tests inside a file by name; declaring gin-console's `api` type (a follow-up in that repository).
- `<type>` matches the case type pattern (`cases.TYPE`). `e2e` and `manual` cannot be declared. A type with no subsection is not automated, and its cases get no findings from `gin-qa tests`.
- The command must contain `{junit}`; `{files}` is optional. It is split with `shlex.split` and run without a shell, from the repository root.
- Declaration errors (missing `Tests:` or `Run:`, no glob, no `{junit}`, a declared `e2e` or `manual`, a duplicate type, `{files}` inside a longer token) are findings of `tests check` and make every other `tests` command exit 2.
- It never edits case files directly; results are written only by `tests run`.
- Exit codes follow the gin-qa convention: 0 ok, 1 findings, 2 usage or environment error.
- `gin-qa e2e`, `gin-qa cases`, and existing case files are unchanged. A `guidelines.md` without `## Automated types` keeps working; `tests plan` returns nothing.
- The run command comes from a file in the repository, with the same trust as a `package.json` script; it runs without a shell, so no shell expansion of case or path text happens.
- `junit.xml` is parsed with the standard library only; no new dependency.
- Windows: no shell, paths passed as arguments, `{junit}` as an absolute path.

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
- Problem statement: tests exist only for e2e cases. `e2e.e2e_cases` (`plugins/gin-qa/src/scripts/gin_qa/e2e.py:43-45`) keeps `type == "e2e"`, and `e2e.plan`/`check_specs` (`e2e.py:58-93`) know only `qa/e2e/<cap>/<tc>.spec.ts`. gin-console's `api` cases (`qa/guidelines.md` there) are backend pytest tests with fakes, and nothing plans, runs, or records them.
- Success criteria: spec US-1 to US-5 acceptance criteria; `python3 -m pytest -n auto` green; `bash tests/install_smoke_test.sh` passes.
- Constraints: Global Constraints above.
- Non-goals: see Global Constraints, Out of scope.

## Approach Options
### Option 1: New `tests.py`, e2e unchanged except one shared helper
- Summary: a module for declared types with its own marker scan; `e2e.py` keeps its plan/pin/check; the run-folder creation moves into `e2e.new_run_folder` for both.
- Pros: e2e behaviour (fixed spec path, header on line 1, "belongs in") stays as tested; the new code reads alone.
- Cons: about 40 lines of plan/check that look like `e2e.plan`.

### Option 2: One marker scanner under both e2e and tests
- Summary: rebuild `e2e plan/pin/check` on the generic scanner.
- Pros: no near-duplicate.
- Cons: e2e's rules differ (one spec per case at a fixed path, header on line 1); rewriting them risks regressions in a stable command for no user-visible gain.

### Recommended Approach
- Selected option: Option 1.
- Rationale: confirmed in discuss; the only real duplication, the run-folder loop, is shared.

## Scope
- In scope: `tests.py`, the `tests` CLI group, `e2e.new_run_folder`, the `report.py` change, the `/gin-qa:tests` skill, `templates/guidelines.md`, `templates/qa-readme.md`, `docs/guides/qa.md`, `docs/reference/cli.md`, `docs/reference/skills.md`, `docs/roles.md`, versions.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Each track builds on the previous one (run uses the parser and scan of Track 1; the docs describe both), so the tracks run one at a time.
```

## Tasks

### Track 1: Declared types, `gin-qa tests plan|pin|check`
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-qa/src/scripts/gin_qa/tests.py`
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:1` (docstring), `cli.py:12` (import), `cli.py:54` (new `_tests_parser`), `cli.py:220` (new `_run_tests`), `cli.py:245-249` (`tests` group and usage)
  - Test `tests/gin_qa/test_tests_cli.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded new module with a clear spec and exact code below; several edge cases (declaration errors, overlapping globs, capability filter), but no cross-module change.
- **Acceptance criteria**: spec US-1 and US-2; the tests of Step 1.1 pass; `python3 -m pytest -n auto` passes.
- **Estimated complexity**: medium

Interfaces produced (used by Track 2):
- `tests.SECTION: str`, `tests.MARKER: re.Pattern`
- `@dataclass AutomatedType(name: str, globs: list[str], command: str)`
- `@dataclass Marker(tc: str, pinned: str, path: str, line: int)`
- `declared(root: Path, eff: Effective) -> tuple[dict[str, AutomatedType], list[str]]`
- `_types(root: Path, eff: Effective, only: str | None = None) -> dict[str, AutomatedType]` (raises `QaError`)
- `_files(root: Path, globs: list[str]) -> list[str]`
- `markers(root: Path, files: list[str]) -> list[Marker]`
- `plan(root, eff, capability=None, only=None) -> {"types", "missing", "stale", "orphan"}`
- `pin(root, eff, ids) -> list[str]`, `check(root, eff, only=None) -> list[str]`

#### Step 1.1: Failing tests

Create `tests/gin_qa/test_tests_cli.py`:

```python
"""`gin-qa tests`: automated types declared in the guidelines; plan, pin, check, and run (with a fake runner)."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-qa/src/scripts"))

from qa_fixtures import AUTH_SPEC, case_file, gin_workflow_bin, make_repo, python_stub, qa, write  # noqa: E402
from gin_qa.cases import hash8 as case_hash8, parse_case_file  # noqa: E402

GUIDELINES = textwrap.dedent("""\
    # Test case guidelines

    - Language: English.

    ## Automated types

    ### api
    - Tests: `backend/tests/**/test_*.py`
    - Run: `fake-runner {files} --junitxml={junit}`
    """)

FAKE_RUNNER = textwrap.dedent('''\
    #!{python}
    """Stands in for a test runner: records its arguments and copies .fake-junit to the --junitxml path."""
    import json, pathlib, sys
    root = pathlib.Path.cwd()
    (root / ".runner-args").write_text(json.dumps(sys.argv[1:]))
    target = next(arg.split("=", 1)[1] for arg in sys.argv[1:] if arg.startswith("--junitxml="))
    if (root / ".fake-junit").exists():
        pathlib.Path(target).write_text((root / ".fake-junit").read_text())
    exit_file = root / ".fake-exit"
    sys.exit(int(exit_file.read_text()) if exit_file.exists() else 0)
''').format(python=sys.executable)


def junit(*tests: tuple[str, str]) -> str:
    """A JUnit file with one testcase per (name, outcome); outcome is passed, failure, error, or skipped."""
    body = "".join(f'<testcase classname="tests.test_auth" name="{name}">'
                   + ("" if outcome == "passed" else f"<{outcome}/>") + "</testcase>" for name, outcome in tests)
    return f'<?xml version="1.0"?><testsuites><testsuite name="pytest">{body}</testsuite></testsuites>'


class TestsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.bin = gin_workflow_bin(self.base)
        python_stub(self.bin, "fake-runner", FAKE_RUNNER)
        self.root = make_repo(self.base / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        self.guidelines = write(self.root, "qa/guidelines.md", GUIDELINES)
        for tc_id, kind in (("TC-AUTH-001", "api"), ("TC-AUTH-002", "api"), ("TC-AUTH-003", "manual")):
            self.add_case(tc_id, kind)

    def tearDown(self):
        self.tmp.cleanup()

    def add_case(self, tc_id: str, kind: str) -> None:
        write(self.root, f"qa/cases/auth/{tc_id}-x.{kind}.md",
              case_file(tc_id, "REQ: REQ-AUTH-001@00000000", title=tc_id))

    def tests(self, *args: str):
        return qa(self.root, self.bin, *args, group="tests")

    def run_json(self, *args: str) -> dict:
        result = self.tests(*args, "--format", "json")
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return json.loads(result.stdout)

    def tc_hash(self, tc_id: str) -> str:
        path = next((self.root / "qa/cases/auth").glob(f"{tc_id}-*.md"))
        found, _ = parse_case_file(path, path.relative_to(self.root).as_posix())
        return case_hash8(found[0])

    def write_test(self, *tc_ids: str, name: str = "test_auth.py", pinned: str | None = None) -> Path:
        lines: list[str] = []
        for tc_id in tc_ids:
            lines += [f"# TC: {tc_id}@{pinned or self.tc_hash(tc_id)}",
                      f"def test_{tc_id.lower().replace('-', '_')}():", "    pass", ""]
        return write(self.root, f"backend/tests/{name}", "\n".join(lines))

    def case_fields(self, tc_id: str) -> dict:
        payload = json.loads(qa(self.root, self.bin, "export", "--format", "json").stdout)
        return next(row for row in payload["cases"] if row["id"] == tc_id)


class TestDeclaration(TestsCase):
    def test_check_reports_each_declaration_error_and_other_commands_exit_2(self):
        self.guidelines.write_text(textwrap.dedent("""\
            ## Automated types

            ### api
            - Tests: `backend/tests/**/test_*.py`
            - Run: `pytest --junitxml=out.xml`

            ### e2e
            - Tests: `qa/e2e/**/*.spec.ts`
            - Run: `npx playwright test --reporter=junit {junit}`

            ### unit
            - Run: `pytest {files}x --junitxml={junit}`

            ### api
            - Tests: `a/*.py`
            - Run: `pytest --junitxml={junit}`
            """))
        result = self.tests("check")
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertEqual([
            "qa/guidelines.md:3: api: Run needs {junit}",
            "qa/guidelines.md:7: e2e: cannot be declared here; e2e and manual have their own commands",
            "qa/guidelines.md:11: unit: needs a '- Tests:' line with one or more backticked globs",
            "qa/guidelines.md:11: unit: {files} must be a whole argument",
            "qa/guidelines.md:14: api: declared twice (first at line 3)",
        ], result.stdout.splitlines())
        for args in (("plan",), ("pin", "TC-AUTH-001"), ("run", "--type", "api")):
            with self.subTest(args=args):
                result = self.tests(*args)
                self.assertEqual(2, result.returncode, result.stdout)
                self.assertIn("gin-qa tests check", result.stderr)

    def test_no_declared_type_means_nothing_to_do(self):
        self.guidelines.write_text("# Test case guidelines\n\n## Automated types\n\nNone yet.\n")
        result = self.tests("check")
        self.assertEqual((0, "ok\n"), (result.returncode, result.stdout))
        payload = self.run_json("plan")
        self.assertEqual(({}, [], [], []), (payload["types"], payload["missing"], payload["stale"], payload["orphan"]))
        self.guidelines.unlink()
        self.assertEqual("ok\n", self.tests("check").stdout)
        for args in (("run", "--type", "api"), ("plan", "--type", "api")):
            with self.subTest(args=args):
                result = self.tests(*args)
                self.assertEqual(2, result.returncode)
                self.assertIn("--type api: not declared", result.stderr)


class TestPlanPinCheck(TestsCase):
    def test_plan_lists_missing_stale_and_orphan(self):
        payload = self.run_json("plan")
        self.assertEqual(["TC-AUTH-001", "TC-AUTH-002"], [row["tc"] for row in payload["missing"]])
        self.assertEqual({"api": {"tests": ["backend/tests/**/test_*.py"],
                                  "run": "fake-runner {files} --junitxml={junit}"}}, payload["types"])
        self.assertEqual(("qa/guidelines.md", "api", self.tc_hash("TC-AUTH-001")),
                         (payload["guidelines"], payload["missing"][0]["type"], payload["missing"][0]["hash8"]))
        self.write_test("TC-AUTH-001", pinned="00000000")
        self.write_test("TC-AUTH-002", "TC-AUTH-003", "TC-AUTH-009", name="sub/test_more.py")
        write(self.root, "backend/other/test_x.py", "# TC: TC-AUTH-009@00000000\n")
        payload = self.run_json("plan", "auth", "--type", "api")
        self.assertEqual([], payload["missing"])
        self.assertEqual([("TC-AUTH-001", "backend/tests/test_auth.py", 1, "00000000")],
                         [(row["tc"], row["file"], row["line"], row["pinned"]) for row in payload["stale"]])
        self.assertEqual([("TC-AUTH-003", "backend/tests/sub/test_more.py", 5),
                          ("TC-AUTH-009", "backend/tests/sub/test_more.py", 9)],
                         [(row["tc"], row["file"], row["line"]) for row in payload["orphan"]])
        self.assertEqual(([], [], []), tuple(self.run_json("plan", "billing")[key]
                                             for key in ("missing", "stale", "orphan")))

    def test_a_marker_of_another_declared_type_is_not_an_orphan(self):
        self.guidelines.write_text(GUIDELINES + "\n### unit\n- Tests: `backend/tests/unit/*.py`\n"
                                                "- Run: `fake-runner --junitxml={junit}`\n")
        self.add_case("TC-AUTH-004", "unit")
        self.write_test("TC-AUTH-004", name="unit/test_unit.py")
        payload = self.run_json("plan")
        self.assertEqual(([], ["TC-AUTH-001", "TC-AUTH-002"]),
                         (payload["orphan"], [row["tc"] for row in payload["missing"]]))
        self.assertEqual([], self.run_json("plan", "--type", "unit")["missing"])

    def test_pin_rewrites_every_marker_of_the_case(self):
        first = self.write_test("TC-AUTH-001", pinned="00000000")
        second = write(self.root, "backend/tests/test_other.py", "x = 1  -- TC: TC-AUTH-001@11111111\n")
        result = self.tests("pin", "TC-AUTH-001", "TC-AUTH-009")
        self.assertEqual((1, "TC-AUTH-009: not a test case of a declared automated type\n"),
                         (result.returncode, result.stdout))
        self.assertIn("TC-AUTH-001@00000000", first.read_text())
        self.assertEqual(0, self.tests("pin", "TC-AUTH-001").returncode)
        now = self.tc_hash("TC-AUTH-001")
        self.assertTrue(first.read_text().startswith(f"# TC: TC-AUTH-001@{now}\ndef test_tc_auth_001():"))
        self.assertEqual(f"x = 1  -- TC: TC-AUTH-001@{now}\n", second.read_text())
        self.assertEqual([], self.run_json("plan")["stale"])
        result = self.tests("pin", "TC-AUTH-002", "TC-AUTH-003")
        self.assertEqual([
            "TC-AUTH-002: no 'TC: TC-AUTH-002@<hash8>' marker in the api tests",
            "TC-AUTH-003: not a test case of a declared automated type",
        ], result.stdout.splitlines())

    def test_check_reports_missing_stale_and_orphan(self):
        self.write_test("TC-AUTH-001", pinned="00000000")
        gone = self.write_test("TC-AUTH-009", name="test_gone.py", pinned="00000000")
        result = self.tests("check")
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertEqual([
            "qa/cases/auth/TC-AUTH-002-x.api.md:1: TC-AUTH-002 has no test of type api; "
            "write it with `/gin-qa:tests auth --type api`",
            f"backend/tests/test_auth.py:1: TC-AUTH-001 changed (pinned 00000000, now {self.tc_hash('TC-AUTH-001')}); "
            "update the test, then `gin-qa tests pin TC-AUTH-001`",
            "backend/tests/test_gone.py:1: TC-AUTH-009 is not a test case of type api",
        ], result.stdout.splitlines())
        self.write_test("TC-AUTH-001", "TC-AUTH-002")
        gone.unlink()
        result = self.tests("check", "--type", "api")
        self.assertEqual((0, "ok\n"), (result.returncode, result.stdout))


if __name__ == "__main__":
    unittest.main()
```

Run: `python3 -m pytest tests/gin_qa/test_tests_cli.py -q`
Expected: every test fails; `gin-qa` prints usage and exits 2 for the `tests` group.

#### Step 1.2: `tests.py`

Create `plugins/gin-qa/src/scripts/gin_qa/tests.py`:

```python
"""`gin-qa tests`: tests of the automated case types other than e2e, declared in the guidelines, and their runs."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shlex
from typing import Any

from . import cases as tc
from .reqs import Effective, QaError

SECTION = "## Automated types"
RESERVED = ("e2e", "manual")
MARKER = re.compile(r"\bTC: (TC-[A-Z][A-Z0-9-]*-\d{3,})@([0-9a-f]{8})\b")
_ITEM = re.compile(r"^- (Tests|Run): (.*)$")
_BACKTICKED = re.compile(r"`([^`]+)`")
SKIP_DIRS = {".git", "node_modules"}


@dataclass
class AutomatedType:
    name: str
    globs: list[str]
    command: str


@dataclass
class Marker:
    tc: str
    pinned: str
    path: str  # repository-relative, '/'-separated
    line: int


def _command_problems(command: str) -> list[str]:
    try:
        argv = shlex.split(command)
    except ValueError as error:
        return [f"Run: {error}"]
    problems = [] if any("{junit}" in token for token in argv) else ["Run needs {junit}"]
    if any("{files}" in token and token != "{files}" for token in argv):
        problems.append("{files} must be a whole argument")
    return problems


def declared(root: Path, eff: Effective) -> tuple[dict[str, AutomatedType], list[str]]:
    """The `## Automated types` section of the guidelines: the valid types by name, and the declaration errors."""
    path = root / eff.guidelines
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    blocks: list[tuple[str, int, dict[str, str]]] = []
    inside = False
    for number, line in enumerate(lines, 1):
        if line.startswith("## "):
            inside = line.rstrip() == SECTION
        elif inside and line.startswith("### "):
            blocks.append((line[4:].strip(), number, {}))
        elif inside and blocks and (item := _ITEM.match(line)):
            blocks[-1][2][item.group(1)] = item.group(2)
    types: dict[str, AutomatedType] = {}
    first: dict[str, int] = {}
    errors: list[str] = []
    for name, number, items in blocks:
        where = f"{eff.guidelines}:{number}: {name}"
        if not tc.TYPE.fullmatch(name):
            errors.append(f"{where}: not a type name (lower-case letters, digits, and '-')")
            continue
        if name in RESERVED:
            errors.append(f"{where}: cannot be declared here; e2e and manual have their own commands")
            continue
        if name in first:
            errors.append(f"{where}: declared twice (first at line {first[name]})")
            continue
        first[name] = number
        problems: list[str] = []
        globs = _BACKTICKED.findall(items.get("Tests", ""))
        if not globs:
            problems.append("needs a '- Tests:' line with one or more backticked globs")
        commands = _BACKTICKED.findall(items.get("Run", ""))
        if len(commands) != 1:
            problems.append("needs a '- Run:' line with one backticked command")
        else:
            problems += _command_problems(commands[0])
        errors += [f"{where}: {problem}" for problem in problems]
        if not problems:
            types[name] = AutomatedType(name, globs, commands[0])
    return types, errors


def _types(root: Path, eff: Effective, only: str | None = None) -> dict[str, AutomatedType]:
    types, errors = declared(root, eff)
    if errors:
        raise QaError(f"{eff.guidelines} declares automated types with errors; run `gin-qa tests check`")
    if only is not None and only not in types:
        raise QaError(f"--type {only}: not declared under '{SECTION}' in {eff.guidelines}")
    return types


def _files(root: Path, globs: list[str]) -> list[str]:
    """Repository-relative files matching any glob, found by walking each glob's leading folders without wildcards."""
    found: set[str] = set()
    for pattern in globs:
        regex = tc.glob_regex(pattern)
        parts = pattern.split("/")
        fixed = next((index for index, part in enumerate(parts) if "*" in part or "?" in part), len(parts))
        base = root.joinpath(*parts[:fixed])
        candidates = [base] if base.is_file() else []
        # ponytail: skips only .git and node_modules; a glob starting with `**` walks the whole repository
        for folder, dirs, names in os.walk(base):
            dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
            candidates += [Path(folder) / name for name in names]
        found.update(rel for rel in (path.relative_to(root).as_posix() for path in candidates) if regex.match(rel))
    return sorted(found)


def markers(root: Path, files: list[str]) -> list[Marker]:
    found: list[Marker] = []
    for rel in files:
        text = (root / rel).read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.split("\n"), 1):
            found += [Marker(match.group(1), match.group(2), rel, number) for match in MARKER.finditer(line)]
    return found


def _row(case: tc.Case, kind: str) -> dict[str, Any]:
    return {"tc": case.id, "type": kind, "hash8": tc.hash8(case), "case": tc.as_dict(case)}


def plan(root: Path, eff: Effective, capability: str | None = None, only: str | None = None) -> dict[str, Any]:
    types = _types(root, eff, only)
    cases, _ = tc.load(root, eff.cases_dir)  # parse findings are `gin-qa cases check`'s job
    by_id = {case.id: case for case in cases}
    files = {name: _files(root, kind.globs) for name, kind in types.items()}
    missing: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    orphan: list[dict[str, Any]] = []
    for name in sorted(types) if only is None else [only]:
        tested: set[str] = set()
        for mark in markers(root, files[name]):
            case = by_id.get(mark.tc)
            if case is not None and case.type != name and mark.path in files.get(case.type, []):
                continue  # a test of another declared type whose globs also cover this file
            if capability and tc.TC_ID.fullmatch(mark.tc).group(1) != capability.upper():
                continue
            where = {"file": mark.path, "line": mark.line}
            if case is None or case.type != name:
                orphan.append({"tc": mark.tc, "type": name, **where})
                continue
            if mark.pinned != tc.hash8(case):
                stale.append({**_row(case, name), **where, "pinned": mark.pinned})
            tested.add(case.id)
        missing += [_row(case, name) for case in cases
                    if case.type == name and (not capability or case.cap == capability) and case.id not in tested]
    return {"types": {name: {"tests": kind.globs, "run": kind.command} for name, kind in types.items()},
            "missing": missing, "stale": stale, "orphan": orphan}


def check(root: Path, eff: Effective, only: str | None = None) -> list[str]:
    _, errors = declared(root, eff)
    if errors:
        return errors
    work = plan(root, eff, None, only)
    findings = [f"{row['case']['file']}:{row['case']['line']}: {row['tc']} has no test of type {row['type']}; "
                f"write it with `/gin-qa:tests {row['case']['capability']} --type {row['type']}`"
                for row in work["missing"]]
    findings += [f"{row['file']}:{row['line']}: {row['tc']} changed (pinned {row['pinned']}, now {row['hash8']}); "
                 f"update the test, then `gin-qa tests pin {row['tc']}`" for row in work["stale"]]
    findings += [f"{row['file']}:{row['line']}: {row['tc']} is not a test case of type {row['type']}"
                 for row in work["orphan"]]
    return findings


def pin(root: Path, eff: Effective, ids: list[str]) -> list[str]:
    """Rewrites the hash8 of every marker of each case; writes nothing when any ID fails."""
    types = _types(root, eff)
    cases = {case.id: case for case in tc.load(root, eff.cases_dir)[0]}
    errors: list[str] = []
    edits: dict[str, list[tuple[int, str, str]]] = {}
    for case_id in ids:
        case = cases.get(case_id)
        if case is None or case.type not in types:
            errors.append(f"{case_id}: not a test case of a declared automated type")
            continue
        found = [mark for mark in markers(root, _files(root, types[case.type].globs)) if mark.tc == case_id]
        if not found:
            errors.append(f"{case_id}: no 'TC: {case_id}@<hash8>' marker in the {case.type} tests")
        for mark in found:
            edits.setdefault(mark.path, []).append((mark.line, case_id, tc.hash8(case)))
    if errors:
        return errors
    for rel, changes in edits.items():
        lines = (root / rel).read_text(encoding="utf-8").split("\n")
        for number, case_id, value in changes:
            lines[number - 1] = re.sub(rf"\bTC: {re.escape(case_id)}@[0-9a-f]{{8}}\b", f"TC: {case_id}@{value}",
                                       lines[number - 1])
        tc.write_atomic(root / rel, "\n".join(lines))
    return []
```

#### Step 1.3: CLI wiring

In `plugins/gin-qa/src/scripts/gin_qa/cli.py`:
- Line 1: `"""`gin-qa cases`, `gin-qa e2e`, `gin-qa tests`, and `gin-qa report`: exit 0 ok, 1 findings, 2 usage or environment error."""`
- Line 12: `from . import e2e, report, tests`
- After `_e2e_parser` (line 53), add:

```python
def _tests_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repository", type=Path, default=Path.cwd())
    common.add_argument("--format", choices=("text", "json"), default="text")
    parser = argparse.ArgumentParser(prog="gin-qa tests")
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("plan", parents=[common])
    item.add_argument("capability", nargs="?")
    item.add_argument("--type", dest="kind")
    sub.add_parser("pin", parents=[common]).add_argument("ids", nargs="+")
    sub.add_parser("check", parents=[common]).add_argument("--type", dest="kind")
    return parser
```

- After `_run_e2e` (line 219), add:

```python
def _run_tests(args: argparse.Namespace) -> int:
    root = args.repository.resolve()
    eff = resolve(specs_reqs(root))
    if args.command == "plan":
        work = tests.plan(root, eff, args.capability, args.kind)
        lines = [f"{kind} {row['tc']} {row['type']}" + (f" {row['file']}:{row['line']}" if "file" in row else "")
                 for kind in ("missing", "stale", "orphan") for row in work[kind]]
        _emit({"guidelines": eff.guidelines, **work}, args.format, "\n".join(lines) or "nothing to do")
        return 0
    if args.command == "pin":
        return _findings(tests.pin(root, eff, args.ids), args.format, f"pinned {' '.join(args.ids)}")
    return _findings(tests.check(root, eff, args.kind), args.format, "ok")
```

- In `main`: `groups` gains `"tests": (_tests_parser, _run_tests)`, and the usage text gains the line `"       gin-qa tests {plan,pin,check,run} ...\n"` after the `gin-qa e2e` line.

Run: `python3 -m pytest tests/gin_qa/test_tests_cli.py -q`
Expected: `TestDeclaration` and `TestPlanPinCheck` pass except the `("run", "--type", "api")` subtest of `test_check_reports_each_declaration_error_and_other_commands_exit_2` and the `run` subtest of `test_no_declared_type_means_nothing_to_do` (argparse exits 2 on the unknown `run` choice but stderr lacks the expected text). Track 2 makes them pass.

#### Step 1.4: Commit

```bash
git add plugins/gin-qa/src/scripts/gin_qa/tests.py plugins/gin-qa/src/scripts/gin_qa/cli.py tests/gin_qa/test_tests_cli.py
git commit -m "feat(gin-qa): gin-qa tests plan, pin, and check for declared automated types (gin-workflow-qa-test-types)"
```

### Track 2: `gin-qa tests run` and the report
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-qa/src/scripts/gin_qa/tests.py` (imports; `_select`, `_junit`, `_outcome`, `run`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/e2e.py:233-258` (extract `new_run_folder`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py` (`run` subparser in `_tests_parser`, `run` branch in `_run_tests`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/report.py:23-30`, `report.py:80` (a `tests run` folder is a plain reference)
  - Test `tests/gin_qa/test_tests_cli.py` (new class `TestRun`)
  - Test `tests/gin_qa/test_report.py` (one new test)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded: a subprocess run, JUnit parsing with the stdlib, and result mapping, all specified with their edge cases below; the e2e change is a pure extraction covered by its existing tests.
- **Acceptance criteria**: spec US-3 and US-5; every test in `test_tests_cli.py`, `test_e2e_cli.py`, and `test_report.py` passes; `python3 -m pytest -n auto` passes.
- **Estimated complexity**: medium

Interfaces consumed: `_types`, `_files`, `markers` from Track 1; `cases.record_result(root, cases_dir, case_id, status, run=None, bug=None)`.
Interfaces produced: `e2e.new_run_folder(root: Path, eff: Effective, suffix: str = "") -> str`; `tests.run(root, eff, kind: str, targets: list[str]) -> tuple[str, int, list[str], list[dict[str, str]]]`.

#### Step 2.1: Failing tests

Append to `tests/gin_qa/test_tests_cli.py`, before `if __name__ == "__main__":`:

```python
class TestRun(TestsCase):
    def setUp(self):
        super().setUp()
        self.add_case("TC-AUTH-004", "api")
        self.write_test("TC-AUTH-001", "TC-AUTH-002")
        self.write_test("TC-AUTH-004", name="test_more.py")

    def runner_args(self) -> list[str]:
        return json.loads((self.root / ".runner-args").read_text())

    def test_records_the_worst_result_per_case(self):
        write(self.root, ".fake-junit", junit(("test_tc_auth_001_login", "passed"), ("test_tc_auth_001_again[x]", "passed"),
                                              ("test_tc_auth_002", "passed"), ("test_TC_AUTH_002_b", "failure"),
                                              ("TestAuth::test_ok", "passed"), ("test_tc_auth_004", "skipped")))
        write(self.root, ".fake-exit", "3")
        result = self.tests("run", "--type", "api", "--format", "json")
        self.assertEqual(3, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        folder = payload["run"]
        self.assertRegex(folder, r"^qa/evidence/\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-api$")
        self.assertEqual((3, []), (payload["exit"], payload["findings"]))
        self.assertEqual([{"tc": "TC-AUTH-001", "result": "passed"}, {"tc": "TC-AUTH-002", "result": "failed"},
                          {"tc": "TC-AUTH-004", "result": "blocked"}], payload["recorded"])
        fields = self.case_fields("TC-AUTH-002")
        self.assertEqual(("failed", folder), (fields["result"], fields["run"]))
        record = json.loads((self.root / folder / "run.json").read_text())
        self.assertEqual(("api", 3, ["TC-AUTH-001", "TC-AUTH-002", "TC-AUTH-004"]),
                         (record["type"], record["exit"], record["cases"]))
        args = self.runner_args()
        self.assertEqual(["fake-runner", *args], record["command"])
        self.assertEqual(["backend/tests/test_auth.py", "backend/tests/test_more.py"], args[:2])
        self.assertEqual((self.root / folder / "junit.xml").resolve(), Path(args[2].split("=", 1)[1]).resolve())
        self.assertTrue((self.root / folder / "junit.xml").is_file())

    def test_targets_select_the_files_and_the_cases(self):
        write(self.root, ".fake-junit", junit(("test_tc_auth_001", "error"), ("test_tc_auth_002", "passed"),
                                              ("test_tc_auth_004", "passed")))
        payload = self.run_json("run", "--type", "api", "TC-AUTH-004")
        self.assertEqual([{"tc": "TC-AUTH-004", "result": "passed"}], payload["recorded"])
        self.assertEqual(["backend/tests/test_more.py"], self.runner_args()[:-1])
        self.assertEqual("not run", self.case_fields("TC-AUTH-001")["result"])
        payload = self.run_json("run", "--type", "api", "auth")
        self.assertEqual(["failed", "passed", "passed"], [row["result"] for row in payload["recorded"]])
        self.assertEqual("not run", self.case_fields("TC-AUTH-003")["result"])

    def test_without_files_the_whole_command_runs(self):
        self.guidelines.write_text(GUIDELINES.replace("{files} ", ""))
        write(self.root, ".fake-junit", junit(("test_tc_auth_001", "passed"), ("test_tc_auth_002", "failure")))
        payload = self.run_json("run", "--type", "api", "TC-AUTH-001")
        self.assertEqual(1, len(self.runner_args()))
        self.assertEqual([{"tc": "TC-AUTH-001", "result": "passed"}], payload["recorded"])
        self.assertEqual("not run", self.case_fields("TC-AUTH-002")["result"])

    def test_a_case_without_a_matching_test_is_blocked(self):
        write(self.root, ".fake-junit", junit(("test_tc_auth_001", "passed"), ("test_tc_auth_0020", "passed")))
        result = self.tests("run", "--type", "api", "--format", "json")
        self.assertEqual(1, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(["TC-AUTH-002: no test named after it ran", "TC-AUTH-004: no test named after it ran"],
                         payload["findings"])
        self.assertEqual(["passed", "blocked", "blocked"], [row["result"] for row in payload["recorded"]])

    def test_a_missing_or_invalid_junit_file_blocks_every_selected_case(self):
        result = self.tests("run", "--type", "api", "--format", "json")
        self.assertEqual(1, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual([f"{payload['run']}/junit.xml: missing; the Run command must write JUnit XML to {{junit}}"],
                         payload["findings"])
        self.assertEqual(["blocked"] * 3, [row["result"] for row in payload["recorded"]])
        write(self.root, ".fake-junit", "not xml")
        self.assertRegex(self.run_json("run", "--type", "api")["findings"][0], r"/junit\.xml: not valid XML")
        write(self.root, ".fake-junit", "<report/>")
        self.assertRegex(self.run_json("run", "--type", "api")["findings"][0],
                         r"/junit\.xml: the root is <report>, not <testsuites> or <testsuite>$")

    def test_usage_errors_exit_2_and_leave_no_run_folder(self):
        for args, message in ((("TC-AUTH-003",), "TC-AUTH-003: no api test with its marker"),
                              (("billing",), "billing: no api tests in this capability")):
            with self.subTest(args=args):
                result = self.tests("run", "--type", "api", *args)
                self.assertEqual(2, result.returncode, result.stdout)
                self.assertIn(message, result.stderr)
        self.guidelines.write_text(GUIDELINES.replace("fake-runner", "no-such-runner"))
        result = self.tests("run", "--type", "api")
        self.assertEqual(2, result.returncode, result.stdout)
        self.assertIn("no-such-runner: not found", result.stderr)
        self.assertFalse((self.root / "qa/evidence").exists())
```

Append to class `TestReport` in `tests/gin_qa/test_report.py`, after `test_a_run_outside_the_evidence_folder_is_plain_text`:

```python
    def test_a_tests_run_folder_is_a_plain_reference(self):
        run = "qa/evidence/2026-11-04T09-00-00-api"
        write(self.root, f"{run}/run.json", json.dumps({"type": "api", "started": "2026-11-04T09:00:00+00:00",
                                                        "command": ["pytest"], "cases": ["TC-BILLING-001"], "exit": 0}))
        self.record("TC-BILLING-001", "passed", run)
        result = self.report("--format", "json")
        self.assertEqual((0, ""), (result.returncode, result.stderr))
        payload = json.loads(result.stdout)
        billing = self.page(self.root / payload["report"])["cases"][1]
        self.assertEqual(("none", run, "passed", []),
                         (billing["evidence"], billing["run"], billing["result"], payload["missing_evidence"]))
```

Run: `python3 -m pytest tests/gin_qa/test_tests_cli.py tests/gin_qa/test_report.py -q`
Expected: the `TestRun` tests fail (argparse rejects `run`), and so does `test_a_tests_run_folder_is_a_plain_reference` (`missing_evidence` lists the run).

#### Step 2.2: `e2e.new_run_folder`

In `plugins/gin-qa/src/scripts/gin_qa/e2e.py`, add after `evidence_root` (line 36):

```python
def new_run_folder(root: Path, eff: Effective, suffix: str = "") -> str:
    """Creates `<evidence root>/<UTC stamp><suffix>`, with `-2`, `-3`, ... when another run took the name."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S") + suffix
    folder, number = f"{evidence_root(eff)}/{stamp}", 2
    (root / evidence_root(eff)).mkdir(parents=True, exist_ok=True)
    while True:
        try:
            (root / folder).mkdir()
            return folder
        except FileExistsError:  # another run started in the same second
            folder, number = f"{evidence_root(eff)}/{stamp}-{number}", number + 1
```

In `run` (lines 248-256), replace the stamp, `mkdir`, and `while True` loop with `folder = new_run_folder(root, eff)`.

Run: `python3 -m pytest tests/gin_qa/test_e2e_cli.py -q`
Expected: all pass (no behaviour change).

#### Step 2.3: `tests.run`

In `plugins/gin-qa/src/scripts/gin_qa/tests.py`, extend the imports to:

```python
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any
from xml.etree import ElementTree

from . import cases as tc
from .e2e import new_run_folder
from .reqs import Effective, QaError
```

Append:

```python
def _select(cases: dict[str, tc.Case], marked: dict[str, set[str]], kind: str, targets: list[str]) -> list[str]:
    """The case IDs to run: every case of the type with a marker, or those the targets name."""
    ids = sorted(marked)
    if not targets:
        if not ids:
            raise QaError(f"no {kind} tests with a 'TC:' marker; write them with /gin-qa:tests <capability> --type {kind}")
        return ids
    chosen: list[str] = []
    for target in targets:
        if tc.TC_ID.fullmatch(target):
            if target not in marked:
                raise QaError(f"{target}: no {kind} test with its marker")
            chosen.append(target)
        else:
            found = [case_id for case_id in ids if cases[case_id].cap == target]
            if not found:
                raise QaError(f"{target}: no {kind} tests in this capability")
            chosen += found
    return list(dict.fromkeys(chosen))


def _junit(path: Path) -> tuple[list[tuple[str, str]], str | None]:
    """(`classname name` upper-cased with `_` as `-`, status) per testcase, or the problem with the file."""
    if not path.is_file():
        return [], "missing; the Run command must write JUnit XML to {junit}"
    try:
        top = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as error:
        return [], f"not valid XML: {error}"
    if top.tag not in ("testsuites", "testsuite"):
        return [], f"the root is <{top.tag}>, not <testsuites> or <testsuite>"
    rows: list[tuple[str, str]] = []
    for test in top.iter("testcase"):
        if test.find("failure") is not None or test.find("error") is not None:
            status = "failed"
        elif test.find("skipped") is not None:
            status = "blocked"
        else:
            status = "passed"
        rows.append((f"{test.get('classname', '')} {test.get('name', '')}".replace("_", "-").upper(), status))
    return rows, None


def _outcome(case_id: str, rows: list[tuple[str, str]]) -> str | None:
    """The worst status of the test cases named after the case, or None when none ran."""
    named = re.compile(rf"(?<![A-Z0-9]){re.escape(case_id)}(?!\d)")
    statuses = [status for name, status in rows if named.search(name)]
    return next((worst for worst in ("failed", "blocked", "passed") if worst in statuses), None)


def run(root: Path, eff: Effective, kind: str, targets: list[str]) -> tuple[str, int, list[str], list[dict[str, str]]]:
    """Runs the declared command of `kind` into a new evidence folder and records each selected case's result.

    Returns (folder, the command's exit, findings, recorded results).
    """
    declared_type = _types(root, eff, kind)[kind]
    cases = {case.id: case for case in tc.load(root, eff.cases_dir)[0] if case.type == kind}
    marked: dict[str, set[str]] = {}
    for mark in markers(root, _files(root, declared_type.globs)):
        if mark.tc in cases:
            marked.setdefault(mark.tc, set()).add(mark.path)
    selected = _select(cases, marked, kind, targets)
    argv = shlex.split(declared_type.command)
    program = shutil.which(str(root / argv[0]) if "/" in argv[0] or "\\" in argv[0] else argv[0])
    if program is None:
        raise QaError(f"{argv[0]}: not found; check the Run command of {kind} in {eff.guidelines}")
    folder = new_run_folder(root, eff, f"-{kind}")
    junit = root / folder / "junit.xml"
    files = sorted({path for case_id in selected for path in marked[case_id]})
    command: list[str] = []
    for token in argv:
        command += files if token == "{files}" else [token.replace("{junit}", str(junit))]
    record: dict[str, Any] = {"type": kind, "started": datetime.now(timezone.utc).isoformat(), "command": command,
                              "cases": selected, "exit": None}
    (root / folder / "run.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    result = subprocess.run([program, *command[1:]], cwd=root, stdout=sys.stderr)
    record["exit"] = result.returncode
    (root / folder / "run.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    rows, problem = _junit(junit)
    findings = [f"{folder}/junit.xml: {problem}"] if problem else []
    recorded: list[dict[str, str]] = []
    for case_id in selected:
        status = "blocked" if problem else _outcome(case_id, rows)
        if status is None:
            findings.append(f"{case_id}: no test named after it ran")
            status = "blocked"
        try:
            tc.record_result(root, eff.cases_dir, case_id, status, run=folder)
        except ValueError as error:
            findings.append(f"{case_id}: result not recorded: {error}")
            continue
        recorded.append({"tc": case_id, "result": status})
    return folder, result.returncode, findings, recorded
```

#### Step 2.4: CLI `run`

In `cli.py`, inside `_tests_parser` before `return parser`:

```python
    item = sub.add_parser("run", parents=[common])
    item.add_argument("--type", dest="kind", required=True)
    item.add_argument("targets", nargs="*", metavar="TC-ID|capability")
```

In `_run_tests`, replace the last line (`return _findings(tests.check(...))`) with:

```python
    if args.command == "check":
        return _findings(tests.check(root, eff, args.kind), args.format, "ok")
    folder, code, errors, recorded = tests.run(root, eff, args.kind, args.targets)
    _emit({"run": folder, "exit": code, "findings": errors, "recorded": recorded}, args.format,
          "\n".join([*errors, *(f"{row['tc']} {row['result']}" for row in recorded), f"run: {folder}"]))
    return code or (1 if errors else 0)
```

#### Step 2.5: Report

In `plugins/gin-qa/src/scripts/gin_qa/report.py`, add after `_run_results` (line 30):

```python
def _tests_run(root: Path, run: str) -> bool:
    """A `gin-qa tests run` folder: its run.json names a test type, and it holds no e2e evidence to show."""
    try:
        return "type" in json.loads((root / run / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
```

In `build`, change `if run.startswith(evidence):  # anything else is a manual run reference, shown as text` to:

```python
        if run.startswith(evidence) and not _tests_run(root, run):  # anything else is shown as text
```

Run: `python3 -m pytest tests/gin_qa -q`
Expected: all pass.

#### Step 2.6: Commit

```bash
git add plugins/gin-qa/src/scripts/gin_qa tests/gin_qa
git commit -m "feat(gin-qa): gin-qa tests run records results from JUnit XML (gin-workflow-qa-test-types)"
```

### Track 3: Skill, templates, docs, and gin-qa 0.8
- **Dependencies**: Track 2
- **Files**:
  - Create `plugins/gin-qa/src/skills/tests/SKILL.md`
  - Modify `plugins/gin-qa/src/templates/guidelines.md` (new `## Automated types` section at the end)
  - Modify `plugins/gin-qa/src/templates/qa-readme.md` (the `evidence/` line, the results line, the commands)
  - Modify `tests/gin_qa/test_packaging.py:13-15`, `test_packaging.py:35`, `test_packaging.py:51` (skill list; template parses to no type)
  - Modify `docs/guides/qa.md:65` (new section before `## Report`), `docs/guides/qa.md:72`, `docs/guides/qa.md:117`
  - Modify `docs/reference/cli.md:386`, `docs/reference/cli.md:408` (new `### gin-qa tests` after it), `docs/reference/cli.md:412`
  - Modify `docs/reference/skills.md:65` (new row)
  - Modify `docs/roles.md:12` (Tester row)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:15` (`VERSION = "0.8"`)
  - Modify `plugins/gin-qa/plugin.meta.json`, `plugins/gin-qa/src/.claude-plugin/plugin.json`, `plugins/gin-qa/src/.codex-plugin/plugin.json` (version `0.9.0`, description)
  - Modify `install.sh:13`, `install.ps1:19` (launcher version `0.8`)
  - Test `tests/install_smoke_test.sh` (gin-qa version 0.8, `tests` skill installed)
  - Test `tests/install_smoke_test.ps1` (gin-qa version 0.8, `tests` skill built)
- **Provider role**: `docs`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** documentation, a skill, a template section, and version strings, all with the exact text given below.
- **Acceptance criteria**: spec US-4; `python3 -m pytest -n auto` passes; `bash tests/install_smoke_test.sh` passes; the docs describe the declaration, the marker, and `run` as built.
- **Estimated complexity**: low

Interfaces consumed: the CLI and JSON output of Tracks 1 and 2; `tests.declared`.

#### Step 3.1: Failing packaging tests

In `tests/gin_qa/test_packaging.py`:
- After `sys.path.insert(0, str(CORE / "scripts"))` (line 15), add `sys.path.insert(0, str(QA / "src/scripts"))`, and add `import shutil` and `import tempfile` to the imports.
- Line 35: add `"tests": []` to `expected`:

```python
        expected = {"cases": ["../../templates/guidelines.md", "../../templates/qa-readme.md", "../../templates/cases.md"], "e2e": ["references/explore-case.md"] * 2, "report": [], "tests": []}
```

- After `test_guidelines_template_sets_no_language`, add:

```python
    def test_guidelines_template_declares_no_automated_type(self):
        from gin_qa.reqs import Effective
        from gin_qa.tests import declared
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "qa").mkdir()
            shutil.copyfile(QA / "src/templates/guidelines.md", root / "qa/guidelines.md")
            text = (root / "qa/guidelines.md").read_text(encoding="utf-8")
            self.assertIn("## Automated types\n", text)
            self.assertEqual(({}, []), declared(root, Effective("legacy", "qa/cases", "qa/guidelines.md", [])))
```

Run: `python3 -m pytest tests/gin_qa/test_packaging.py -q`
Expected: `test_skill_budget_and_links` fails (no `tests` skill folder), and `test_guidelines_template_declares_no_automated_type` fails (no section).

#### Step 3.2: Skill and templates

Create `plugins/gin-qa/src/skills/tests/SKILL.md`:

````markdown
---
name: tests
description: Write, run, and check automated tests for api, unit, integration, or other declared case types (not e2e) in the project's own test style, traced to the cases by the gin-qa CLI.
---

# Automated Tests

`/gin-qa:tests <capability> --type <type>` or `/gin-qa:tests <TC-ID>... --type <type>`. All commands are `gin-qa tests <command>`; exit 1 means findings to fix, exit 2 means wrong usage, an invalid `## Automated types` section, or a missing tool.

1. Preconditions: `gin-workflow` and `gin-qa` are on `PATH` and `.agent-workflow/generated/effective-config.yaml` exists; otherwise stop and name what to install or run (`install.sh --plugin gin-qa`, `/setup`). For `e2e` use `/gin-qa:e2e`; `manual` cases have no tests.
2. Read the guidelines file (`plan --format json` names it under `guidelines`; `/gin-qa:cases` creates it). Its rules override everything below.
3. When its `## Automated types` section has no `### <type>`: find the project's test runner and where tests of this kind live (existing tests, `pyproject.toml`, `package.json`), propose the subsection to the user, and write it only after they confirm:
   ```markdown
   ### <type>
   - Tests: `<glob>`, `<glob>`
   - Run: `<runner> {files} <JUnit option>{junit}`
   ```
   `{junit}` is required: it becomes the path of the JUnit XML file the runner must write (`pytest --junitxml={junit}`, `vitest run --reporter=junit --outputFile={junit}`). `{files}` is optional and a whole argument: it becomes the test files of the cases being run. The command runs from the repository root without a shell; use the runner's own option for another folder (`uv run --directory backend pytest`, `pnpm -C frontend vitest`). Then `check --type <type>` must show no declaration error.
4. `plan <capability> --type <type> --format json` gives the work: `missing`, `stale`, `orphan`. With TC-IDs, keep only those cases.
5. `missing` and `stale`: take an existing test in the type's globs as the pattern (imports, fixtures, fakes, naming). For each case write, or update, a test that performs its steps with its test data and asserts its expected results:
   - its name contains the TC-ID (`test_tc_auth_004_locks_after_five_failures`, `it('TC-AUTH-004 locks the account')`): the JUnit name maps the result to the case;
   - a comment line right above it holds `TC: <TC-ID>@<hash8>` with the plan row's `hash8` (`# TC: TC-AUTH-004@1a2b3c4d`);
   - several cases may share a file, and a case may have several tests; its result is the worst of them.
   After updating a stale case's test, `pin <TC-ID>...`.
6. `orphan`: list the tests and ask the user whether to delete or keep each one. Never delete on your own.
7. `run --type <type> <capability|TC-ID...> --format json`. When a test you wrote fails, fix the test if it is wrong; if the product is wrong, keep the test and report the case as a product defect with the failing assertion. `blocked` means the test was skipped or did not run under a name holding the TC-ID: fix the name. Repeat until each case is `passed` or a reported defect.
8. `check --type <type>` must print `ok`, or list only findings outside this scope, which you report without fixing.
9. Report the tests added and changed, the run folder, each case's result, the defects, and any guidelines change. Never edit `Result`, `Run`, or `Bug` lines yourself: `run` writes them. Do not commit; the user reviews and commits.
````

At the end of `plugins/gin-qa/src/templates/guidelines.md`, append:

```markdown

## Automated types

Case types other than e2e whose tests `gin-qa tests` plans and runs (`/gin-qa:tests`). One `### <type>` per type; `{junit}` is the JUnit XML file the command writes, `{files}` (optional) the test files of the cases run. For example:

    ### api
    - Tests: `backend/tests/**/test_*.py`
    - Run: `pytest {files} --junitxml={junit}`

None yet.
```

In `plugins/gin-qa/src/templates/qa-readme.md`:
- Replace the line `` - `evidence/`: run folders written by `gin-qa e2e run`; git-ignored. `` with `` - `evidence/`: run folders written by `gin-qa e2e run` and `gin-qa tests run`; git-ignored. ``
- Replace the line `` - `gin-qa e2e run` records the automated results. `` with `` - `gin-qa e2e run` and `gin-qa tests run` record the automated results. ``
- After the last line, `` - `gin-qa e2e run [TC-ID|capability]`: runs the specs and records their results. ``, add `` - `gin-qa tests run --type <type> [TC-ID|capability]`: runs the tests of a type the guidelines declare under `Automated types` and records their results. ``

Run: `python3 -m pytest tests/gin_qa/test_packaging.py -q`
Expected: all pass.

#### Step 3.3: Docs

`docs/guides/qa.md`:
- Before `## Report: `/gin-qa:report`` (line 65), insert:

````markdown
## Other automated tests: `/gin-qa:tests`

`/gin-qa:tests <capability> --type <type>` writes, runs, and checks the tests of cases whose type is neither `e2e` nor `manual`, such as `api` or `unit`, in the project's own test framework:

- `qa/guidelines.md` declares each such type under `## Automated types`: the globs of its test files and the command that runs them. The skill proposes the declaration when it is missing.

  ```markdown
  ## Automated types

  ### api
  - Tests: `backend/tests/**/test_*.py`
  - Run: `uv run --directory backend pytest {files} --junitxml={junit}`
  ```

  `{junit}` (required) is the JUnit XML file the command must write; `{files}` (optional) is the test files of the cases being run. The command runs from the repository root, without a shell.
- A test has a comment line `TC: <TC-ID>@<hash8>` and a name holding the TC-ID (`test_tc_auth_004_...`). `gin-qa tests plan` and `check` compare the marker with the case, as `gin-qa e2e` does with a spec's header; `gin-qa tests pin` updates it.
- `gin-qa tests run --type <type> [TC-ID|capability]` runs the command into `qa/evidence/<UTC time>-<type>/` (`run.json` and `junit.xml`) and records each case's result: `failed` when a test named after it failed or errored, `blocked` when it was skipped or none ran, otherwise `passed`.

````

- In the `## Report` section, replace `A `Run` outside `qa/evidence/`, such as a manual run reference, is shown as text.` with `A `Run` outside `qa/evidence/`, such as a manual run reference, and a `gin-qa tests run` folder are shown as text.`
- The first sentence of the `## Commands` section becomes: `` `gin-qa cases {plan,next-id,pin,result,split,check,export}`, `gin-qa e2e {init,plan,pin,run,check,export}`, `gin-qa tests {plan,pin,check,run}`, and `gin-qa report [capability] [--out DIR]`; exit 0 ok, 1 findings, 2 usage or environment error. ``

`docs/reference/cli.md`:
- Line 386: replace `` `gin-qa e2e {init,plan,pin,run,check,export}`, and `` with `` `gin-qa e2e {init,plan,pin,run,check,export}`, `gin-qa tests {plan,pin,check,run}`, and ``.
- After line 408 (the `gin-qa e2e run` paragraph), insert:

```markdown

### `gin-qa tests`

`gin-qa tests` plans, pins, checks, and runs the tests of the automated types declared under `## Automated types` in the guidelines file (`qa.guidelines`): one `### <type>` per type, with `- Tests:` (backticked globs) and `- Run:` (one backticked command that holds `{junit}` and optionally `{files}` as a whole argument). `e2e` and `manual` cannot be declared. A declaration error is a finding of `check` and makes the other subcommands exit 2.

- `plan [capability] [--type T]`: `missing` (a case of the type with no `TC: <TC-ID>@<hash8>` line in the type's test files), `stale` (a marker whose hash8 is not the case's), and `orphan` (a marker of a case that is gone or of another type). `--format json` adds `types` and `guidelines`.
- `pin <TC-ID>...`: rewrites the hash8 of every marker of each case.
- `check [--type T]`: the declaration errors, then the `plan` rows, as findings.
- `run --type T [TC-ID|capability ...]`: runs the command from the repository root, without a shell, into `qa/evidence/<UTC stamp>-<T>/` (`run.json`, `junit.xml`). `{junit}` becomes the JUnit file's path and `{files}` the test files of the selected cases. A JUnit test case whose name or classname holds the TC-ID (in any case, `_` read as `-`) belongs to that case. The case records `failed` (a failure or error), `blocked` (skipped), or `passed`, the worst over its tests, and `blocked` with a finding when none ran. `--format json` prints `{"run", "exit", "findings", "recorded"}`. Exit: the command's non-zero exit, else 1 on findings, else 0; a command not found exits 2.
```

- At the end of the `### gin-qa report` paragraph, append the sentence: `A `Run` folder written by `gin-qa tests run` is shown as text, not read as e2e evidence.`

`docs/reference/skills.md`: after the `e2e` row (line 65), add:

```markdown
| `tests` | Write, run, and check tests of declared automated types other than e2e (`api`, `unit`, ...) in the project's own test framework |
```

`docs/roles.md:12`: in the Tester row, replace `` `/gin-qa:cases`, `/gin-qa:e2e`, `/gin-qa:report`, `` with `` `/gin-qa:cases`, `/gin-qa:e2e`, `/gin-qa:tests`, `/gin-qa:report`, ``.

#### Step 3.4: Version 0.8 / 0.9.0

- `plugins/gin-qa/src/scripts/gin_qa/cli.py:15`: `VERSION = "0.8"`.
- `install.sh:13`: `QA_LAUNCHER_VERSION="0.8"`; `install.ps1:19`: `$QaLauncherVersion = '0.8'`.
- `plugins/gin-qa/plugin.meta.json`, `plugins/gin-qa/src/.claude-plugin/plugin.json`, `plugins/gin-qa/src/.codex-plugin/plugin.json`: `"version": "0.9.0"` and `"description": "QA add-on for gin-workflow: test cases derived from specs, Playwright specs with per-step evidence, and tests of other declared types run from JUnit XML, traced, exported as JSON, and reported as offline HTML."`
- `tests/install_smoke_test.sh`: `would install gin-qa launcher version 0.7 to`, every `.local/lib/gin-qa/0.7/` path, and `"gin-qa 0.7"` change `0.7` to `0.8`; `gin-qa) old_version=0.4; current_version=0.7 ;;` becomes `gin-qa) old_version=0.4; current_version=0.8 ;;`. After `assert_exists "plugins/gin-qa/dist/claude-code/skills/e2e/SKILL.md"` add `assert_exists "plugins/gin-qa/dist/claude-code/skills/tests/SKILL.md"`; after `assert_exists "$MOCK_HOME/.claude/skills/gin-qa/skills/e2e/SKILL.md"` add `assert_exists "$MOCK_HOME/.claude/skills/gin-qa/skills/tests/SKILL.md"`.
- `tests/install_smoke_test.ps1`: `would install gin-qa launcher version 0.7`, every `.local/lib/gin-qa/0.7/` path, and `Current = '0.7'` (the gin-qa row) change `0.7` to `0.8`. After `Assert-Exists (Join-Path $Root 'plugins/gin-qa/dist/codex/skills/e2e/SKILL.md')` add `    Assert-Exists (Join-Path $Root 'plugins/gin-qa/dist/codex/skills/tests/SKILL.md')`.

Run: `grep -rn "0\.7" install.sh install.ps1 tests/install_smoke_test.sh tests/install_smoke_test.ps1 | grep -i "qa"`
Expected: no gin-qa launcher version `0.7` left.

Run: `python3 -m pytest -n auto -q && bash tests/install_smoke_test.sh`
Expected: all tests pass; the smoke test ends with its success line.

#### Step 3.5: Commit

```bash
git add plugins/gin-qa docs tests install.sh install.ps1
git commit -m "docs(gin-qa): /gin-qa:tests skill, Automated types template, and docs; gin-qa 0.9.0 (gin-workflow-qa-test-types)"
```

## Integration
- **Branch**: `feat/qa-test-types`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes
- [ ] `bash tests/install_smoke_test.sh` passes
- [ ] Manual check: in a scratch copy of gin-console, declare `api` (`Tests: backend/tests/**/test_*.py`, `Run: uv run --directory backend pytest {files} --junitxml={junit}`), add one marker and one test name for an `api` case, and run `gin-qa tests run --type api <TC-ID>`; the case file gets `Result` and `Run`, and `gin-qa report` shows it with no `evidence not found`.

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog (`haiku`, `sonnet`, `opus`; `low` … `max`) using the route rubric.
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- The Parent Bead (`gin-workflow-qa-test-types`) stays open until the human-confirmed merge; track beads close once their tests and review pass.
- The CLI `VERSION` (launcher folder `~/.local/lib/gin-qa/<VERSION>`) and the plugin manifest version are separate numbers; this epic moves them from 0.7 / 0.8.0 to 0.8 / 0.9.0.
- Spec amended during planning (2026-11-04): an overlapping marker of another declared type is not an orphan; the version line names both numbers and `docs/roles.md`.
- Existing gap left alone: `docs/reference/skills.md` has no `report` row; the `cases` row still describes the flat layout.

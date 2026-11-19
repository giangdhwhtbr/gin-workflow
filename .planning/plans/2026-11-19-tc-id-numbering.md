# Plan: Gap-free TC-ID numbering in gin-qa

Workflow: tc-id-numbering
Spec: `.planning/specs/2026-11-19-tc-id-numbering-design.md`

## Objective

`gin-qa cases next-id` and `gin-qa cases new` give the lowest free number of a capability, read from the files on disk only, skipping numbers an e2e spec or an automated test marker still names. A new `gin-qa cases renumber <cap> [--dry-run]` closes existing gaps to 001..N and rewrites case files, e2e specs, automated test files, and e2e evidence of the renumbered cases.

## Global Constraints

Copied from the spec:

- No `git` process in `next_id`; the result is the same inside and outside a git repository.
- A number is taken by a case (file name in `<cases>/<cap>/` or TC-ID in a flat `<cases>/<cap>.md`), an e2e spec (`<e2e>/<cap>/tc-<cap>-NNN.spec.ts` or its `// TC:` header), or an automated test marker (`TC: TC-<CAP>-NNN@<hash8>` in a file matched by the `Tests:` globs).
- `renumber` keeps the order, applies the whole mapping in one regex pass, renames through temporary names, and leaves `@<hash8>` untouched.
- `renumber` refuses (exit 1, nothing written) on a flat `<cap>.md`, a duplicate TC-ID, an orphan e2e spec or marker, a case file / e2e spec / automated test file it would change that is modified, staged, or untracked in git, or a rename target that already exists.
- Out of scope: collisions between parallel branches, bug bead titles, external trackers, `gin-qa tests run` folders, exported reports, `gin specs next-id`.

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
- Problem statement: `next_id` (`plugins/gin-qa/src/scripts/gin_qa/cases.py:255-267`) reads `git log`, so every deleted case leaves a permanent gap; testers want contiguous numbers in the cases folder and the report.
- Success criteria: US-1 and US-2 acceptance criteria pass as tests in `tests/gin_qa/`; the full `tests/gin_qa` suite stays green.
- Constraints: Global Constraints above.
- Non-goals: the out-of-scope list above.

## Approach Options
### Option 1: Lowest free number + `renumber` command (confirmed at discuss)
- Summary: `next_id` fills gaps from current files plus held IDs; a new `numbering` module owns held IDs and `renumber`.
- Pros: new cases close gaps on their own; existing gaps close once on request; no git dependency.
- Cons: a deleted case's number can come back on another case; old bug titles and exported reports keep the old meaning.

### Option 2: Report-only sequence column
- Summary: keep IDs, show 1..N in the report.
- Pros: no risk to references.
- Cons: IDs in files keep their gaps; rejected at discuss.

### Recommended Approach
- Selected option: Option 1.
- Rationale: confirmed by the user; the `numbering` module keeps `cases.py` free of imports from `e2e.py` and `tests.py` (both import `cases`, so the reverse import would be circular).

## Scope
- In scope: R1–R3 of the spec.
- Out of scope: Global Constraints' out-of-scope list.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 builds on the numbering module and CLI wiring that Track 1 adds; both edit cli.py.
```

## Tasks

### Track 1: Lowest free number for next-id and new

- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cases.py:8-13,255-267,435-454` (drop `subprocess`; `next_id` takes `held`; `new_case` passes `held`)
  - Create `plugins/gin-qa/src/scripts/gin_qa/numbering.py` (`held`, `test_files`, `cap_of`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:11-13,211-216,233-238` (import `numbering`; pass held IDs to `next_id` and `new_case`)
  - Modify `plugins/gin-qa/src/templates/qa-readme.md:14` (how numbers are given)
  - Test `tests/gin_qa/test_cases_cli.py:229-237,332-338`
  - Test `tests/gin_qa/test_cases_new.py`
  - Test `tests/gin_qa/test_workspace_root.py:103`
- **Interfaces**:
  - `cases.next_id(root: Path, cases_dir: str, cap: str, held: Iterable[str] = ()) -> str`
  - `cases.new_case(root, cases_dir, guidelines, cap, kind, title, key, value, held: Iterable[str] = ()) -> tuple[str, Path]`
  - `numbering.cap_of(tc_id: str) -> str | None` (lower-case capability of a TC-ID, None when not one)
  - `numbering.test_files(root: Path, eff: Effective) -> list[str]` (repository-relative files matched by the valid automated types' `Tests:` globs)
  - `numbering.held(root: Path, eff: Effective, cap: str) -> set[str]` (TC-IDs of `cap` named by an e2e spec file name or header, or by a test marker)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change to one function plus a small helper module, with exact cases from the spec.
- **Acceptance criteria**: US-1 of the spec; `python3 -m pytest tests/gin_qa -q` passes.
- **Estimated complexity**: low

Steps:

1. Replace the two old tests in `tests/gin_qa/test_cases_cli.py` (`TestIdsAndExport.test_next_id_never_reuses_a_number` at :229 and the test `test_next_id_counts_file_names_and_their_history` at :332, which is in the class that defines `put`). Add `from gin_qa.cases import next_id` to the existing `gin_qa.cases` import line. In the class with `put` (around :287), write:

   ```python
   def test_next_id_fills_the_lowest_gap_and_forgets_history(self):
       self.assertEqual("TC-AUTH-001\n", qa_subprocess(self.root, self.bin, "next-id", "auth").stdout)
       for number in ("001", "002", "004"):
           self.put(f"auth/TC-AUTH-{number}-x.e2e.md", case_file(f"TC-AUTH-{number}", self.ref("REQ-AUTH-001")))
       self.assertEqual("TC-AUTH-003\n", qa(self.root, self.bin, "next-id", "auth").stdout)
       commit_all(self.root)
       (self.root / "qa/cases/auth/TC-AUTH-001-x.e2e.md").unlink()
       self.assertEqual("TC-AUTH-001\n", qa(self.root, self.bin, "next-id", "auth").stdout)
       self.assertEqual("TC-USER-AUTH-001\n", qa(self.root, self.bin, "next-id", "user-auth").stdout)

   def test_next_id_skips_numbers_an_e2e_spec_or_a_test_marker_still_names(self):
       for number in ("001", "002", "004"):
           self.put(f"auth/TC-AUTH-{number}-x.e2e.md", case_file(f"TC-AUTH-{number}", self.ref("REQ-AUTH-001")))
       spec = write(self.root, "qa/e2e/auth/tc-auth-003.spec.ts", "// TC: TC-AUTH-003@00000000\n")
       self.assertEqual("TC-AUTH-005\n", qa(self.root, self.bin, "next-id", "auth").stdout)
       spec.unlink()
       write(self.root, "qa/guidelines.md", "## Automated types\n\n### api\n- Tests: `backend/tests/**/test_*.py`\n"
                                            "- Run: `fake {files} --junitxml={junit}`\n")
       marker = write(self.root, "backend/tests/test_auth.py", "# TC: TC-AUTH-003@00000000\ndef test_x():\n    pass\n")
       self.assertEqual("TC-AUTH-005\n", qa(self.root, self.bin, "next-id", "auth").stdout)
       marker.unlink()
       self.assertEqual("TC-AUTH-003\n", qa(self.root, self.bin, "next-id", "auth").stdout)

   def test_next_id_needs_no_git_repository(self):
       with tempfile.TemporaryDirectory() as tmp:
           folder = Path(tmp) / "qa/cases/auth"
           folder.mkdir(parents=True)
           (folder / "TC-AUTH-002-x.manual.md").write_text("# TC-AUTH-002: x\n")
           self.assertEqual("TC-AUTH-001", next_id(Path(tmp), "qa/cases", "auth"))
           self.assertEqual("TC-AUTH-003", next_id(Path(tmp), "qa/cases", "auth", {"TC-AUTH-001"}))
   ```

   In `tests/gin_qa/test_cases_new.py`, add to the class holding `test_writes_a_named_pinned_file_with_the_next_id`:

   ```python
   def test_new_takes_the_lowest_free_number(self):
       for title in ("One", "Two", "Three"):
           self.assertEqual(0, self.new("--req", "REQ-AUTH-001", title=title).returncode)
       (self.root / "qa/cases/auth/TC-AUTH-002-two.manual.md").unlink()
       self.assertEqual("qa/cases/auth/TC-AUTH-002-four.manual.md",
                        self.new("--req", "REQ-AUTH-001", title="Four").stdout.strip())
   ```

   In `tests/gin_qa/test_workspace_root.py:103`, rename `test_next_id_from_the_child_uses_child_history` to `test_next_id_from_the_child_uses_child_cases` (body unchanged).
2. Run `python3 -m pytest tests/gin_qa/test_cases_cli.py tests/gin_qa/test_cases_new.py -q -k "next_id or lowest"`: the gap and marker tests fail (TC-AUTH-005 / TC-AUTH-004 printed, `next_id` takes no `held`).
3. In `cases.py`: remove `import subprocess` (its only use is `next_id`), add `import itertools` and `from typing import Iterable`, and replace `next_id`:

   ```python
   def next_id(root: Path, cases_dir: str, cap: str, held: Iterable[str] = ()) -> str:
       """The lowest number used by no case of `cap` (flat file or case file names) and by no TC-ID in `held`."""
       path, folder = root / cases_dir / f"{cap}.md", root / cases_dir / cap
       text = path.read_text(encoding="utf-8") if path.is_file() else ""
       text += "\n" + "\n".join(item.name for item in folder.glob("*.md")) if folder.is_dir() else ""
       text += "\n" + "\n".join(held)
       upper = cap.upper()
       taken = {int(match.group(2)) for match in TC_ID.finditer(text) if match.group(1) == upper}
       return f"TC-{upper}-{next(number for number in itertools.count(1) if number not in taken):03d}"
   ```

   `new_case` gains a last parameter `held: Iterable[str] = ()` (docstring: "`held`: TC-IDs that other files still name") and calls `next_id(root, cases_dir, cap, held)`.
4. Create `numbering.py`:

   ```python
   """TC-ID numbering: the IDs that keep a number from a new case, and `gin-qa cases renumber`."""

   from __future__ import annotations

   from pathlib import Path, PurePosixPath

   from . import cases as tc
   from . import e2e, tests
   from .reqs import Effective


   def cap_of(tc_id: str) -> str | None:
       found = tc.TC_ID.fullmatch(tc_id or "")
       return found.group(1).lower() if found else None


   def test_files(root: Path, eff: Effective) -> list[str]:
       """Files matched by the `Tests:` globs of the valid automated types; a declaration error drops only its type."""
       types, _ = tests.declared(root, eff)
       return tests._files(root, [glob for kind in types.values() for glob in kind.globs])


   def _specs(root: Path, eff: Effective, cap: str) -> list[tuple[str, str | None, str]]:
       """(path, header TC-ID, TC-ID of the file name) of each spec in `<e2e>/<cap>/`."""
       return [(spec.path, spec.tc, PurePosixPath(spec.path).name.removesuffix(".spec.ts").upper())
               for spec in e2e.load_specs(root, eff) if spec.path.split("/")[-2] == cap]


   def held(root: Path, eff: Effective, cap: str) -> set[str]:
       ids = {item for _, header, named in _specs(root, eff, cap) for item in (header, named) if item}
       ids |= {marker.tc for marker in tests.markers(root, test_files(root, eff))}
       return {item for item in ids if cap_of(item) == cap}
   ```
5. In `cli.py`, change the import to `from . import bugs, e2e, numbering, report, tests`. In `_run`, `next-id` calls `tc.next_id(root, eff.cases_dir, args.capability, numbering.held(root, eff, args.capability))`. `new` passes `held=numbering.held(root, eff, args.capability)` to `tc.new_case`.
6. In `qa-readme.md`, after line 14 add: `- A new case takes the lowest number free in its capability; a number an e2e spec or a test marker still names stays taken.`
7. Run `python3 -m pytest tests/gin_qa -q`: all pass.
8. Commit on the track branch: `fix(gin-qa): next-id gives the lowest free number, without git history`.

### Track 2: `gin-qa cases renumber`

- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-qa/src/scripts/gin_qa/numbering.py` (add `renumber` and its helpers)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:23-53,211-216,335` (subcommand, handler, usage line)
  - Modify `plugins/gin-qa/src/skills/cases/SKILL.md:15,20-21` (step 6 wording; new step for renumbering)
  - Modify `plugins/gin-qa/src/templates/qa-readme.md` (one line on `renumber`)
  - Modify `docs/reference/cli.md:470` (subcommand list and one sentence)
  - Modify `docs/guides/qa.md:264` and `docs/guides/qa.vi.md:228` (subcommand list)
  - Create `tests/gin_qa/test_cases_renumber.py`
- **Interfaces**:
  - consumes `numbering.cap_of`, `numbering.test_files`, `numbering._specs`, `tc._lock`, `tc.load`, `tc.write_atomic`, `tc.TYPE`, `tests.markers`, `e2e.evidence_root`
  - `numbering.UNTOUCHED: list[str] = ["bug bead titles", "gin-qa tests run folders", "exported reports"]`
  - `numbering.renumber(root: Path, eff: Effective, cap: str, dry_run: bool) -> tuple[dict[str, Any], list[str]]`: `({"mapping": {old: new}, "files": [repository-relative paths after the run], "untouched": UNTOUCHED, "dry_run": bool}, findings)`; findings non-empty means nothing was written and the dict is `{}`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** a clear spec in one module, but many edge cases: one-pass rewrite in four written forms, chained renames, evidence folders, and five refusals that must write nothing.
- **Acceptance criteria**: US-2 of the spec; `python3 -m pytest tests/gin_qa -q` passes.
- **Estimated complexity**: medium

Steps:

1. Create `tests/gin_qa/test_cases_renumber.py`:

   ```python
   """`gin-qa cases renumber`: close the gaps of a capability and rewrite every reference gin-qa owns."""

   from __future__ import annotations

   import json
   from pathlib import Path
   import subprocess
   import sys
   import tempfile
   import unittest

   sys.path.insert(0, str(Path(__file__).resolve().parent))
   sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-qa/src/scripts"))

   from qa_fixtures import (AUTH_SPEC, case_file, commit_all, gin_workflow_bin, hash8 as req_hash8,  # noqa: E402
                            make_repo, write, write_activity)
   from qa_fixtures import qa as qa_subprocess, qa_in_process as qa  # noqa: E402
   from gin_qa.cases import hash8 as case_hash8, parse_case_file  # noqa: E402

   RUN = "qa/evidence/2026-11-04T08-00-00"
   GUIDELINES = ("## Automated types\n\n### api\n- Tests: `backend/tests/**/test_*.py`\n"
                 "- Run: `fake {files} --junitxml={junit}`\n")
   CASES = (("001", "e2e", "One"), ("002", "api", "Two"), ("005", "e2e", "Five"), ("009", "api", "Nine"))


   class RenumberCase(unittest.TestCase):
       def setUp(self):
           self.tmp = tempfile.TemporaryDirectory()
           self.base = Path(self.tmp.name)
           self.bin = gin_workflow_bin(self.base)
           self.root = make_repo(self.base / "repo")
           write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
           write_activity(self.root)
           write(self.root, "qa/guidelines.md", GUIDELINES)
           for number, kind, title in CASES:
               self.add_case(number, kind, title)
           for number in ("001", "005"):
               tc_id = f"TC-AUTH-{number}"
               write(self.root, f"qa/e2e/auth/{tc_id.lower()}.spec.ts",
                     f"// TC: {tc_id}@{self.tc_hash(tc_id)}\ntest('{tc_id}: x', async () => {{}});\n")
           write(self.root, "backend/tests/test_auth.py", "".join(
               f"# TC: TC-AUTH-{n}@{self.tc_hash(f'TC-AUTH-{n}')}\ndef test_tc_auth_{n}_x():\n    pass\n\n"
               for n in ("002", "009")))
           write(self.root, f"{RUN}/run.json", json.dumps({"started": "2026-11-04T08:00:00+00:00",
                                                           "specs": ["qa/e2e/auth/tc-auth-005.spec.ts"],
                                                           "playwright_exit": 1}))
           write(self.root, f"{RUN}/tc-auth-005/01.png", "png-bytes")
           write(self.root, f"{RUN}/tc-auth-005/result.json", json.dumps({
               "tc": "TC-AUTH-005", "tc_hash8": self.tc_hash("TC-AUTH-005"), "project": None, "status": "failed",
               "error": None, "started": "2026-11-04T08:00:01Z", "finished": "2026-11-04T08:00:09Z",
               "steps": [{"n": 1, "title": "1. Open /login", "status": "failed", "screenshot": "01.png",
                          "snapshot": None, "url": "http://127.0.0.1/login", "error": "timeout"}]}))
           self.assertEqual(0, qa(self.root, self.bin, "result", "TC-AUTH-005", "failed", "--run", RUN).returncode)
           commit_all(self.root)

       def tearDown(self):
           self.tmp.cleanup()

       def add_case(self, number: str, kind: str, title: str) -> Path:
           req = "REQ-AUTH-002" if title == "Two" else "REQ-AUTH-001"  # every REQ covered, so `cases check` is ok
           return write(self.root, f"qa/cases/auth/TC-AUTH-{number}-{title.lower()}.{kind}.md",
                        case_file(f"TC-AUTH-{number}", f"REQ: {req}@{req_hash8(self.root, self.bin, req)}",
                                  title=title))

       def tc_hash(self, tc_id: str) -> str:
           path = next((self.root / "qa/cases/auth").glob(f"{tc_id}-*.md"))
           return case_hash8(parse_case_file(path, path.relative_to(self.root).as_posix())[0][0])

       def tree(self) -> dict[str, bytes]:
           return {path.relative_to(self.root).as_posix(): path.read_bytes()
                   for path in sorted(self.root.rglob("*")) if path.is_file() and ".git" not in path.parts}

       def renumber(self, *args: str):
           return qa(self.root, self.bin, "renumber", "auth", *args)


   class TestRenumber(RenumberCase):
       def test_dry_run_prints_the_mapping_and_writes_nothing(self):
           before = self.tree()
           result = self.renumber("--dry-run", "--format", "json")
           self.assertEqual(0, result.returncode, result.stderr)
           payload = json.loads(result.stdout)
           self.assertEqual({"TC-AUTH-005": "TC-AUTH-003", "TC-AUTH-009": "TC-AUTH-004"}, payload["mapping"])
           self.assertTrue(payload["dry_run"])
           self.assertEqual(before, self.tree())

       def test_rewrites_cases_specs_markers_and_evidence(self):
           result = qa_subprocess(self.root, self.bin, "renumber", "auth")
           self.assertEqual(0, result.returncode, result.stderr)
           self.assertIn("TC-AUTH-005 -> TC-AUTH-003\nTC-AUTH-009 -> TC-AUTH-004\n", result.stdout)
           self.assertTrue(result.stdout.endswith(
               "not rewritten: bug bead titles, gin-qa tests run folders, exported reports\n"))
           self.assertEqual(["TC-AUTH-001-one.e2e.md", "TC-AUTH-002-two.api.md", "TC-AUTH-003-five.e2e.md",
                             "TC-AUTH-004-nine.api.md"],
                            sorted(path.name for path in (self.root / "qa/cases/auth").glob("*.md")))
           self.assertTrue((self.root / "qa/cases/auth/TC-AUTH-003-five.e2e.md").read_text()
                           .startswith("# TC-AUTH-003: Five\n"))
           spec = (self.root / "qa/e2e/auth/tc-auth-003.spec.ts").read_text()
           self.assertTrue(spec.startswith(f"// TC: TC-AUTH-003@{self.tc_hash('TC-AUTH-003')}\n"))
           self.assertIn("test('TC-AUTH-003: x'", spec)
           self.assertFalse((self.root / "qa/e2e/auth/tc-auth-005.spec.ts").exists())
           test = (self.root / "backend/tests/test_auth.py").read_text()
           self.assertIn("# TC: TC-AUTH-004@", test)
           self.assertIn("def test_tc_auth_004_x():", test)
           self.assertNotIn("009", test)
           self.assertEqual("TC-AUTH-003",
                            json.loads((self.root / RUN / "tc-auth-003/result.json").read_text())["tc"])
           self.assertEqual(["qa/e2e/auth/tc-auth-003.spec.ts"],
                            json.loads((self.root / RUN / "run.json").read_text())["specs"])
           for group in ("cases", "e2e", "tests"):
               found = qa(self.root, self.bin, "check", group=group)
               self.assertEqual((0, "ok\n"), (found.returncode, found.stdout), f"{group}: {found.stderr}")
           export = json.loads(qa(self.root, self.bin, "export", "--run", RUN, "--format", "json",
                                  group="e2e").stdout)
           row = next(row for row in export["cases"] if row["id"] == "TC-AUTH-003")
           self.assertEqual(1, len(row["results"]))

       def test_chained_numbers_move_in_one_pass(self):
           (self.root / "qa/cases/auth/TC-AUTH-001-one.e2e.md").unlink()
           (self.root / "qa/e2e/auth/tc-auth-001.spec.ts").unlink()
           two, five = self.tc_hash("TC-AUTH-002"), self.tc_hash("TC-AUTH-005")
           write(self.root, "qa/e2e/auth/tc-auth-002.spec.ts", f"// TC: TC-AUTH-002@{two}\n")  # 002 -> 001 while 005 -> 002
           commit_all(self.root)
           self.assertEqual(0, self.renumber().returncode)
           self.assertEqual(["TC-AUTH-001-two.api.md", "TC-AUTH-002-five.e2e.md", "TC-AUTH-003-nine.api.md"],
                            sorted(path.name for path in (self.root / "qa/cases/auth").glob("*.md")))
           self.assertEqual(f"// TC: TC-AUTH-001@{two}\n", (self.root / "qa/e2e/auth/tc-auth-001.spec.ts").read_text())
           self.assertTrue((self.root / "qa/e2e/auth/tc-auth-002.spec.ts").read_text()
                           .startswith(f"// TC: TC-AUTH-002@{five}\n"))
           test = (self.root / "backend/tests/test_auth.py").read_text()
           self.assertIn("def test_tc_auth_001_x():", test)
           self.assertIn("def test_tc_auth_003_x():", test)

       def test_contiguous_numbers_print_nothing_to_renumber(self):
           self.renumber()
           commit_all(self.root)
           before = self.tree()
           result = self.renumber()
           self.assertEqual((0, "nothing to renumber\n"), (result.returncode, result.stdout))
           self.assertEqual(before, self.tree())

       def test_refusals_write_nothing(self):
           cases = {
               "flat": (lambda: write(self.root, "qa/cases/auth.md", "# Test cases: auth\n"),
                        "qa/cases/auth.md: a flat cases file; run `gin-qa cases split auth` first"),
               "duplicate": (lambda: self.add_case("005", "manual", "Again"), "duplicate TC-AUTH-005"),
               "orphan spec": (lambda: write(self.root, "qa/e2e/auth/tc-auth-007.spec.ts",
                                             "// TC: TC-AUTH-007@00000000\n"),
                               "qa/e2e/auth/tc-auth-007.spec.ts: orphan e2e spec"),
               "orphan marker": (lambda: write(self.root, "backend/tests/test_more.py",
                                               "# TC: TC-AUTH-007@00000000\n"),
                                 "backend/tests/test_more.py:1: orphan marker TC-AUTH-007"),
               "uncommitted": (lambda: (self.root / "backend/tests/test_auth.py").open("a").write("# note\n"),
                               "backend/tests/test_auth.py: not committed"),
               "target": (lambda: write(self.root, f"{RUN}/tc-auth-003/result.json", "{}"),
                          f"{RUN}/tc-auth-003: already exists"),
           }
           for name, (make, message) in cases.items():
               with self.subTest(name):
                   make()
                   if name != "uncommitted":
                       commit_all(self.root)
                   before = self.tree()
                   result = self.renumber()
                   self.assertEqual(1, result.returncode, result.stderr)
                   self.assertIn(message, result.stdout)
                   self.assertEqual(before, self.tree())
                   subprocess.run(["git", "reset", "-q", "--hard", "HEAD~1" if name != "uncommitted" else "HEAD"],
                                  cwd=self.root, check=True)
                   subprocess.run(["git", "clean", "-qfdx", "--", "qa/evidence/"], cwd=self.root, check=True)


   if __name__ == "__main__":
       unittest.main()
   ```

   (`git clean -x` on the evidence folder drops an ignored `tc-auth-003/` left by the `target` subtest; the setUp commit keeps the rest of the evidence because `make_repo` has no `.gitignore` entry for it.)
2. Run `python3 -m pytest tests/gin_qa/test_cases_renumber.py -q`: every test fails with `invalid choice: 'renumber'` (exit 2).
3. In `numbering.py`, add imports `from collections import Counter`, `import re`, `import subprocess`, `from typing import Any`, and:

   ```python
   UNTOUCHED = ["bug bead titles", "gin-qa tests run folders", "exported reports"]


   def _pattern(mapping: dict[str, str]) -> tuple[re.Pattern[str], dict[str, str]]:
       """One regex over the four written forms of every old ID (TC-AUTH-005, tc-auth-005, tc_auth_005,
       TC_AUTH_005), and the same form of its new ID."""
       forms: dict[str, str] = {}
       for old, new in mapping.items():
           for shape in (str.upper, str.lower):
               for sep in ("-", "_"):
                   forms[shape(old).replace("-", sep)] = shape(new).replace("-", sep)
       alternatives = "|".join(sorted(map(re.escape, forms), key=len, reverse=True))
       return re.compile(rf"(?<![A-Za-z0-9])(?:{alternatives})(?!\d)"), forms


   def _uncommitted(root: Path, paths: list[str]) -> list[str]:
       """The paths git reports modified, staged, or untracked; none outside a git repository."""
       if not paths:
           return []
       done = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", *paths], cwd=root,
                             capture_output=True, text=True, check=False)
       return [line[3:] for line in done.stdout.splitlines() if line.strip()] if done.returncode == 0 else []


   def _move(moves: list[tuple[Path, Path]]) -> None:
       """Renames through temporary names first, so `003 -> 002` never lands on `002` before it moved on."""
       staged = []
       for index, (source, target) in enumerate(moves):
           temporary = source.with_name(f".renumber-{index}-{source.name}")
           source.rename(temporary)
           staged.append((temporary, target))
       for temporary, target in staged:
           temporary.rename(target)


   def renumber(root: Path, eff: Effective, cap: str, dry_run: bool) -> tuple[dict[str, Any], list[str]]:
       """`<cap>`'s cases to 001..N in their order, with their case files, e2e specs, test markers and names,
       and the e2e evidence their `Run:` names; nothing is written when there is a finding."""
       if not tc.TYPE.fullmatch(cap):
           raise ValueError(f"{cap!r}: a capability matches [a-z][a-z0-9-]*")
       base = root / eff.cases_dir
       if (base / f"{cap}.md").is_file():
           return {}, [f"{eff.cases_dir}/{cap}.md: a flat cases file; run `gin-qa cases split {cap}` first"]
       done = {"mapping": {}, "files": [], "untouched": UNTOUCHED, "dry_run": dry_run}
       if not (base / cap).is_dir():
           return done, []
       with tc._lock(base):
           mine = [case for case in tc.load(root, eff.cases_dir)[0] if case.cap == cap]
           counts = Counter(case.id for case in mine)
           findings = [f"{case.path}:{case.line}: duplicate {case.id}" for case in mine if counts[case.id] > 1]
           specs = _specs(root, eff, cap)
           findings += [f"{path}: orphan e2e spec ({header or named} has no case); delete it or restore the case"
                        for path, header, named in specs if named not in counts or (header and header not in counts)]
           files = test_files(root, eff)
           findings += [f"{marker.path}:{marker.line}: orphan marker {marker.tc} (no case); delete it or restore "
                        "the case" for marker in tests.markers(root, files)
                        if cap_of(marker.tc) == cap and marker.tc not in counts]
           if findings:
               return {}, findings
           upper = cap.upper()
           ordered = sorted(counts, key=lambda item: int(tc.TC_ID.fullmatch(item).group(2)))
           mapping = {old: f"TC-{upper}-{index:03d}" for index, old in enumerate(ordered, 1)
                      if old != f"TC-{upper}-{index:03d}"}
           if not mapping:
               return done, []
           pattern, forms = _pattern(mapping)
           edits: dict[Path, str] = {}
           moves: list[tuple[Path, Path]] = []
           tracked = [*(root / case.path for case in mine), *(root / path for path, _, _ in specs),
                      *(root / path for path in files)]
           evidence: list[Path] = []
           for case in mine:
               if case.id not in mapping:
                   continue
               path = root / case.path
               moves.append((path, path.with_name(mapping[case.id] + path.name[len(case.id):])))
               run = case.fields.get("Run", "").strip()
               old_dir = root / run / case.id.lower()
               if run.startswith(e2e.evidence_root(eff) + "/") and (root / run / "run.json").is_file() \
                       and old_dir.is_dir():
                   evidence += [root / run / "run.json", *old_dir.rglob("result.json")]
                   moves.append((old_dir, old_dir.with_name(mapping[case.id].lower())))
           for path, _, named in specs:
               if named in mapping:
                   moves.append((root / path, (root / path).with_name(mapping[named].lower() + ".spec.ts")))
           for path in dict.fromkeys([*tracked, *evidence]):
               text = path.read_text(encoding="utf-8")
               new = pattern.sub(lambda match: forms[match.group(0)], text)
               if new != text:
                   edits[path] = new
           sources = {source for source, _ in moves}
           findings += [f"{target.relative_to(root).as_posix()}: already exists; delete it if it belongs to a "
                        "deleted case" for _, target in moves if target.exists() and target not in sources]
           changed = sorted({path.relative_to(root).as_posix() for path in [*edits, *sources] if path in tracked})
           findings += [f"{path}: not committed; commit or discard it first" for path in _uncommitted(root, changed)]
           if findings:
               return {}, findings
           def after(path: Path) -> str:
               """Where `path` is once the moves ran; a file inside a moved evidence folder moves with it."""
               for source, target in moves:
                   if path == source or source in path.parents:
                       return (target / path.relative_to(source)).relative_to(root).as_posix()
               return path.relative_to(root).as_posix()

           shown = sorted({after(path) for path in [*edits, *sources]})
           if not dry_run:
               for path, text in edits.items():
                   tc.write_atomic(path, text)
               _move(moves)
           return {**done, "mapping": mapping, "files": shown}, []
   ```

4. In `cli.py` `_parser`, after the `split` parser add:

   ```python
   item = sub.add_parser("renumber", parents=[common])
   item.add_argument("capability")
   item.add_argument("--dry-run", action="store_true")
   ```

   In `_run`, before `if args.command == "check":`:

   ```python
   if args.command == "renumber":
       row, errors = numbering.renumber(root, eff, tc.capability_arg(args.capability), args.dry_run)
       if errors:
           return _findings(errors, args.format, "ok")
       lines = [*(f"{old} -> {new}" for old, new in row["mapping"].items()), *row["files"],
                "not rewritten: " + ", ".join(row["untouched"])]
       _emit(row, args.format, "\n".join(lines) if row["mapping"] else "nothing to renumber")
       return 0
   ```

   In `main`, the usage line becomes `gin-qa cases {plan,next-id,pin,result,bug,to-manual,new,split,renumber,check,export} ...`.
5. Run `python3 -m pytest tests/gin_qa/test_cases_renumber.py -q`: all pass. Fix the implementation, not the tests, on a failure.
6. Docs and skill:
   - `SKILL.md` step 6: "which writes the file with the next ID" becomes "which writes the file with the lowest free ID". Add a step after step 11: `12. Gaps in the numbers: only when the user asks to close them, run \`renumber <capability> --dry-run\`, show the mapping, and on a yes run \`renumber <capability>\`, then \`check\`, \`gin-qa e2e check\`, and \`gin-qa tests check\`. A refusal lists what to fix first (flat file, duplicate, orphan spec or marker, uncommitted file, existing target).` and renumber the current step 12 to 13.
   - `qa-readme.md`: after the line Track 1 added: `- \`gin-qa cases renumber <capability>\` closes the gaps to 001..N and rewrites the case files, e2e specs, test markers and names, and the e2e evidence of each renamed case; bug bead titles and exported reports keep the old ID.`
   - `docs/reference/cli.md:470`, `docs/guides/qa.md:264`, `docs/guides/qa.vi.md:228`: add `renumber` to the `gin-qa cases {...}` list after `split`. In `cli.md`, append to that paragraph: `` `gin-qa cases next-id CAP` prints the lowest number free in the capability (a number an e2e spec or a test marker still names stays taken); `gin-qa cases renumber CAP [--dry-run]` closes the gaps to 001..N and rewrites the case files, e2e specs, test markers, and the e2e evidence of the renamed cases, or exits 1 and writes nothing on a flat file, a duplicate, an orphan spec or marker, an uncommitted file, or an existing target. ``
7. Run `python3 -m pytest tests/gin_qa -q` (includes `test_packaging.py`): all pass.
8. Commit on the track branch: `feat(gin-qa): cases renumber closes TC-ID gaps and rewrites specs, markers, and evidence`.

## Integration
- **Branch**: `feat/tc-id-numbering`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest tests/gin_qa -q` passes
- [ ] `python3 -m pytest -n auto` passes (pre-push hook)
- [ ] Manual: in a scratch repo, `gin-qa cases renumber <cap> --dry-run` then `renumber`, and `/gin-qa:report` shows the renamed case's screenshots

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- Deliverable merge-holds apply only to the Parent Bead; track beads close after tests and review pass.

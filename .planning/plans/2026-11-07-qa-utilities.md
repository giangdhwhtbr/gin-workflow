# Plan: gin-qa utilities: move a flaky e2e case to manual, keep re-run evidence, and remove tester chores

Epic: gin-workflow-uj96
Spec: .planning/specs/2026-11-07-qa-utilities-design.md

## Objective
`gin-qa cases to-manual` moves a flaky e2e case to manual and the report shows it; `gin-qa cases bug` keeps re-run evidence on an open bug; `tests run` and `report` git-ignore the evidence folder; `gin-qa cases new`, `gin-qa report --zip`, and `gin-qa e2e init --install` replace hand work; an older `evidence.ts` gets step snapshots when it matches the template.

Architecture: every change sits in the existing modules of `plugins/gin-qa/src/scripts/gin_qa/`. `cases.py` owns the case file (`move_to_manual`, `new_case`, the `Moved from e2e` field), `e2e.py` owns specs, the evidence ignore entry, and `init`, `bugs.py` owns the bead calls, `report.py` owns the report folder and archive, and `cli.py` wires the commands. No new module.

Tech stack: Python 3 standard library, one HTML template with inline JavaScript, Markdown skills and docs, Python `unittest` tests run by `python3 -m pytest -n auto`.

Global Constraints (from the spec):
- Moving a case deletes its spec; git history keeps the file.
- The move is one command plus one field in the case, not a skill-only rule and not a separate history file.
- QA decides when a case moves; gin-qa does not count failures.
- A moved case starts as `not run`: `Result: not run`, because `cases check` refuses a `Bug:` without a `Result:` (`cases.py:106-108`).
- Out of scope: moving a case back to e2e with a command, moving a case of a type other than e2e, copying `.claude/skills/<name>-qa/` to other harnesses.
- Usage and validation errors exit 2 with a message on stderr; `cases check` findings exit 1.
- `hash8` values do not change; new json keys are additions; existing case files stay valid.
- gin-qa commands do not commit.
- A value passed to `gin` as an argument holds no line break and no double quote (Windows `.cmd` shim, `bugs.py:115`).
- Skills stay within 6,000 characters (`tests/gin_qa/test_packaging.py:43`).
- Every docs page follows `plugins/gin-workflow/src/references/docs-style.md` (no em or en dashes).

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
- Problem statement: a re-run on an open bug drops the tester's data, QA has no supported way to take a flaky e2e case off the pipeline, the evidence folder is ignored only after `e2e init`, and three chores stay manual.
- Success criteria: US-1 to US-7 of the spec; the full suite passes.
- Constraints: the Global Constraints above.
- Non-goals: the out-of-scope list above.

## Approach Options
### Option 1: extend the existing modules
- Summary: add functions to `cases.py`, `e2e.py`, `bugs.py`, and `report.py`, and subcommands to `cli.py`.
- Pros: follows the current module split; reuses `find`, `_with_result`, `_lock`, `write_atomic`, and `next_id`.
- Cons: `cases.py` grows by about 60 lines.

### Option 2: a new `gin_qa/utilities.py`
- Summary: put the new commands in one module.
- Pros: one new file to read.
- Cons: the module has no single job and must reach into private helpers of `cases.py`.

### Recommended Approach
- Selected option: Option 1.
- Rationale: each change belongs to a module that already owns that data.

## Scope
- In scope: R1 to R9 of the spec.
- Out of scope: as listed in the Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks 1 to 3 all edit cli.py and the same test modules, and Track 4 documents their commands, so one track at a time avoids conflicts.
```

## Tasks

### Track 1: `gin-qa cases to-manual` and moved cases in the report
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cases.py:25-26,102-108,418-427` (field, check, `move_to_manual`, `moved_from_e2e`, `as_dict`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/e2e.py:52-54` (`to_manual`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:29-44,196-204,301` (subcommand, usage)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/report.py:113-116` (`moved` key)
  - Modify `plugins/gin-qa/src/templates/report.html` (section, label, detail fact)
  - Test `tests/gin_qa/test_cases_to_manual.py`
  - Test `tests/gin_qa/test_report.py`
- **Interfaces**:
  - Produces: `cases.MOVED_FIELD = "Moved from e2e"`, `cases.moved_from_e2e(case: Case) -> dict[str, str] | None`, `cases.move_to_manual(root: Path, cases_dir: str, guidelines: str, case_id: str, reason: str) -> Path`, `e2e.to_manual(root: Path, eff: Effective, case_id: str, reason: str) -> dict[str, str | None]`, `as_dict` key `moved_from_e2e`, report key `moved`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change in known modules, with the code below and the edge cases in the spec.
- **Acceptance criteria**:
  - `tests/gin_qa/test_cases_to_manual.py` and `tests/gin_qa/test_report.py` pass.
  - The full suite passes.
- **Estimated complexity**: medium

#### Steps

1. Create `tests/gin_qa/test_cases_to_manual.py`:
   ```python
   """`gin-qa cases to-manual`: the renamed case, the deleted spec, and every refusal."""

   from __future__ import annotations

   import json
   from pathlib import Path
   import re
   import sys
   import tempfile
   import unittest

   sys.path.insert(0, str(Path(__file__).resolve().parent))

   from qa_fixtures import AUTH_SPEC, case_file, cases_file, case, gin_workflow_bin, make_repo, qa, write  # noqa: E402

   OLD = "qa/cases/auth/TC-AUTH-001-login.e2e.md"
   NEW = "qa/cases/auth/TC-AUTH-001-login.manual.md"
   SPEC = "qa/e2e/auth/tc-auth-001.spec.ts"
   MOVED = re.compile(r"^- \*\*Moved from e2e:\*\* \d{4}-\d{2}-\d{2}: flaky on CI$", re.M)


   class ToManualCase(unittest.TestCase):
       def setUp(self):
           self.tmp = tempfile.TemporaryDirectory()
           self.base = Path(self.tmp.name)
           self.bin = gin_workflow_bin(self.base)
           self.root = make_repo(self.base / "repo")
           write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
           write(self.root, OLD, case_file("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000", title="Login",
                                           extra="Result: failed\nRun: qa/evidence/x\nBug: gw-7"))
           write(self.root, SPEC, "// TC: TC-AUTH-001@00000000\n")
           self.assertEqual(0, self.cases("pin", "TC-AUTH-001").returncode)

       def tearDown(self):
           self.tmp.cleanup()

       def cases(self, *args: str):
           return qa(self.root, self.bin, *args)

       def move(self, *args: str):
           return self.cases("to-manual", "TC-AUTH-001", "--reason", "flaky on CI", *args)

       def assert_unchanged(self, result) -> None:
           self.assertEqual(2, result.returncode, result.stdout)
           self.assertTrue((self.root / OLD).is_file())
           self.assertFalse((self.root / NEW).exists())
           self.assertTrue((self.root / SPEC).is_file())


   class TestToManual(ToManualCase):
       def test_renames_records_the_reason_resets_the_result_and_deletes_the_spec(self):
           result = self.move("--format", "json")
           self.assertEqual(0, result.returncode, result.stderr)
           self.assertEqual({"tc": "TC-AUTH-001", "file": NEW, "spec": SPEC}, json.loads(result.stdout))
           text = (self.root / NEW).read_text(encoding="utf-8")
           self.assertRegex(text, MOVED)
           self.assertIn("- **Result:** not run\n", text)
           self.assertIn("- **Bug:** gw-7\n", text)
           self.assertNotIn("**Run:**", text)
           self.assertFalse((self.root / OLD).exists())
           self.assertFalse((self.root / SPEC).exists())

       def test_checks_are_clean_and_the_hash_is_kept(self):
           before = json.loads(self.cases("export", "--format", "json").stdout)["cases"][0]["hash8"]
           self.assertEqual(0, self.move().returncode)
           after = json.loads(self.cases("export", "--format", "json").stdout)["cases"][0]
           self.assertEqual((before, "manual"), (after["hash8"], after["type"]))
           self.assertRegex(after["moved_from_e2e"]["date"], r"^\d{4}-\d{2}-\d{2}$")
           self.assertEqual("flaky on CI", after["moved_from_e2e"]["reason"])
           self.assertNotIn("TC-AUTH-001", self.cases("check").stdout)
           self.assertNotIn("TC-AUTH-001", qa(self.root, self.bin, "check", group="e2e").stdout)

       def test_a_missing_spec_is_not_an_error(self):
           (self.root / SPEC).unlink()
           result = self.move()
           self.assertEqual(0, result.returncode, result.stderr)
           self.assertEqual([NEW, "no spec"], result.stdout.split("\n")[:2])

       def test_crlf_line_endings_are_kept(self):
           path = self.root / OLD
           path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
           self.assertEqual(0, self.move().returncode)
           self.assertIn(b"\r\n", (self.root / NEW).read_bytes())
           self.assertNotIn(b"\n", (self.root / NEW).read_bytes().replace(b"\r\n", b""))


   class TestRefusals(ToManualCase):
       def test_bad_reasons(self):
           for reason in ("", "   ", "two\nlines"):
               with self.subTest(reason=reason):
                   self.assert_unchanged(self.cases("to-manual", "TC-AUTH-001", "--reason", reason))

       def test_unknown_case(self):
           self.assertEqual(2, self.cases("to-manual", "TC-AUTH-099", "--reason", "x").returncode)

       def test_a_manual_case(self):
           write(self.root, "qa/cases/auth/TC-AUTH-002-pay.manual.md",
                 case_file("TC-AUTH-002", "REQ: REQ-AUTH-002@00000000", title="Pay"))
           result = self.cases("to-manual", "TC-AUTH-002", "--reason", "x")
           self.assertEqual(2, result.returncode)
           self.assertIn("only an e2e case", result.stderr)

       def test_manual_not_listed_in_the_guidelines(self):
           write(self.root, "qa/guidelines.md", "# Guidelines\n\n## Types\n\n- `e2e`: browser\n")
           result = self.move()
           self.assert_unchanged(result)
           self.assertIn("manual", result.stderr)

       def test_a_flat_cases_file(self):
           (self.root / OLD).unlink()
           write(self.root, "qa/cases/auth.md", cases_file("auth", case("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000")))
           result = self.move()
           self.assertEqual(2, result.returncode)
           self.assertIn("gin-qa cases split auth", result.stderr)

       def test_a_malformed_moved_line_is_a_check_finding(self):
           path = self.root / OLD
           path.write_text(path.read_text(encoding="utf-8").replace(
               "- **Priority:** high\n", "- **Priority:** high\n- **Moved from e2e:** yesterday\n"), encoding="utf-8")
           result = self.cases("check")
           self.assertEqual(1, result.returncode)
           self.assertIn("Moved from e2e", result.stdout)
   ```
   Add to `tests/gin_qa/test_report.py`, in `class TestReport`:
   ```python
       def test_moved_cases_are_counted_and_carry_date_and_reason(self):
           self.assertEqual(0, self.report_json()["moved"])
           result = qa(self.root, self.bin, "to-manual", "TC-AUTH-001", "--reason", "flaky on CI")
           self.assertEqual(0, result.returncode, result.stderr)
           self.record("TC-AUTH-001", "passed", "manual 2026-11-07")
           payload = self.report_json()
           self.assertEqual(1, payload["moved"])
           row = next(item for item in self.page(self.root / payload["report"])["cases"] if item["id"] == "TC-AUTH-001")
           self.assertEqual(("manual", "passed", "flaky on CI"),
                            (row["type"], row["result"], row["moved_from_e2e"]["reason"]))

       def test_the_template_holds_the_moved_section(self):
           text = TEMPLATE.read_text(encoding="utf-8")
           self.assertIn('id="moved"', text)
           self.assertIn("Moved from e2e to manual", text)
           self.assertIn("moved_from_e2e", text)
   ```
   Run `python3 -m pytest tests/gin_qa/test_cases_to_manual.py tests/gin_qa/test_report.py -q`. Expected: the new tests fail.

2. In `cases.py`, add `from datetime import datetime, timezone` to the imports. Replace lines 25-26 and add the pattern:
   ```python
   RESULT_FIELDS = ("Result", "Run", "Bug")
   MOVED_FIELD = "Moved from e2e"
   _MOVED = re.compile(r"^(\d{4}-\d{2}-\d{2}): (\S.*)$")
   KNOWN_FIELDS = ("REQ", "Source", "Type", "Priority", MOVED_FIELD, *RESULT_FIELDS)
   ```
   In `_parse_block`, after the `for key in ("Run", "Bug"):` loop and before `return case`:
   ```python
       moved = case.fields.get(MOVED_FIELD)
       if moved is not None and not _MOVED.match(moved):
           errors.append(f"{path}:{case.field_lines[MOVED_FIELD]}: {case.id}: {MOVED_FIELD}: is "
                         f"'<YYYY-MM-DD>: <reason>'; got {moved!r}")
   ```
   After `record_result`, add:
   ```python
   def move_to_manual(root: Path, cases_dir: str, guidelines: str, case_id: str, reason: str) -> Path:
       """Renames an e2e case file to `.manual.md`, records why, and resets its result; returns the new path."""
       one_line(reason)
       case = find(root, cases_dir, case_id)
       path = root / case.path
       if case.type != "e2e":
           raise ValueError(f"{case_id}: is a {case.type or 'untyped'} case; only an e2e case moves to manual")
       if path.parent == root / cases_dir:
           raise ValueError(f"{case.path}: a flat cases file; run `gin-qa cases split {case.cap}` first")
       if MOVED_FIELD in case.fields:
           raise ValueError(f"{case.path}:{case.field_lines[MOVED_FIELD]}: {case_id}: remove the {MOVED_FIELD}: line first")
       types, _ = declared_types(root, guidelines)
       if types is not None and "manual" not in types:
           raise ValueError(f"manual is not listed under '{TYPES_SECTION}' in {guidelines}")
       target = path.with_name(path.name[:-len(".e2e.md")] + ".manual.md")
       if target.exists():
           raise ValueError(f"{target.relative_to(root).as_posix()}: already exists")
       day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
       values = [(MOVED_FIELD, f"{day}: {reason}"), ("Result", "not run"), ("Bug", case.fields.get("Bug"))]
       with _lock(root / cases_dir):
           text = _with_result(path.read_text(encoding="utf-8"), case, values)
           path.rename(target)
           write_atomic(target, text)  # after the rename: write_atomic keeps the line endings of the file it replaces
       return target
   ```
   Before `as_dict`, add:
   ```python
   def moved_from_e2e(case: Case) -> dict[str, str] | None:
       found = _MOVED.match(case.fields.get(MOVED_FIELD, ""))
       return {"date": found.group(1), "reason": found.group(2)} if found else None
   ```
   In `as_dict`, add `"moved_from_e2e": moved_from_e2e(case),` after `"bug": case.fields.get("Bug", ""),`.

3. In `e2e.py`, after `spec_path`, add:
   ```python
   def to_manual(root: Path, eff: Effective, case_id: str, reason: str) -> dict[str, str | None]:
       """Moves an e2e case to manual, then deletes its spec, so a failed delete leaves an orphan `check` reports."""
       spec = spec_path(eff, tc.find(root, eff.cases_dir, case_id))
       target = tc.move_to_manual(root, eff.cases_dir, eff.guidelines, case_id, reason)
       existed = (root / spec).is_file()
       (root / spec).unlink(missing_ok=True)
       return {"tc": case_id, "file": target.relative_to(root).as_posix(), "spec": spec if existed else None}
   ```

4. In `cli.py` `_parser`, before `sub.add_parser("split", ...)`:
   ```python
       item = sub.add_parser("to-manual", parents=[common])
       item.add_argument("id")
       item.add_argument("--reason", required=True)
   ```
   In `_run`, before `if args.command == "split":`:
   ```python
       if args.command == "to-manual":
           row = e2e.to_manual(root, eff, args.id, args.reason)
           _emit(row, args.format, "\n".join([row["file"], row["spec"] or "no spec"]))
           return 0
   ```
   In the usage text of `main`, change the first line to `gin-qa cases {plan,next-id,pin,result,bug,to-manual,split,check,export} ...`.

5. In `report.py` `build`, add to the returned dict: `"moved": sum(1 for row in rows if row["moved_from_e2e"]),`.

6. In `report.html`:
   - After the `.run-steps img` CSS rule, add `#moved { margin-top: 16px; }`.
   - After the closing `</div>` of the `table-wrap` in `<main>`, add:
     ```html
     <section id="moved" hidden>
       <h2>Moved from e2e to manual</h2>
       <div class="table-wrap">
         <table>
           <thead><tr><th>ID</th><th>Title</th><th>Moved on</th><th>Reason</th><th>Result</th></tr></thead>
           <tbody id="moved-rows"></tbody>
         </table>
       </div>
     </section>
     ```
   - In `renderTable`, replace `el('td', { text: item.title })` with `el('td', {}, item.title, item.moved_from_e2e ? el('span', { class: 'muted', text: ' (moved from e2e)' }) : null)`.
   - After `renderTable`, add:
     ```js
     function renderMoved() {
       const moved = cases.filter((item) => item.moved_from_e2e);
       $('moved').hidden = !moved.length;
       $('moved-rows').replaceChildren(...moved.map((item) => el('tr', { tabindex: '0', onclick: () => openCase(item) },
         el('td', { text: item.id }), el('td', { text: item.title }), el('td', { text: item.moved_from_e2e.date }),
         el('td', { text: item.moved_from_e2e.reason }), el('td', {}, badge(item.result)))));
     }
     ```
   - In `openCase`, add to `facts` after `...Object.entries(item.fields),`: `['Moved from e2e', item.moved_from_e2e && `${item.moved_from_e2e.date}: ${item.moved_from_e2e.reason}`],`.
   - After the final `renderSelects();` call, add `renderMoved();`.

7. Run `python3 -m pytest tests/gin_qa/test_cases_to_manual.py tests/gin_qa/test_report.py tests/gin_qa/test_cases_cli.py -q`. Expected: pass.

8. Run `python3 -m pytest -n auto -q`. Expected: pass. Commit:
   ```
   feat(gin-qa): cases to-manual moves a flaky e2e case to manual, and the report lists moved cases (gin-workflow-uj96.1)
   ```

### Track 2: re-run notes, evidence ignore, `cases new`, and `report --zip`
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-qa/src/scripts/gin_qa/bugs.py:78,90-130` (`rerun_note`, `file_bug`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/e2e.py:173-178` (`ignore_evidence`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/tests.py:19,286` (call it)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cases.py` (`new_case`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/report.py` (`_archive`, ignore call, `archive` parameter)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py` (`new` subcommand, `--zip`, usage)
  - Test `tests/gin_qa/test_cases_bug.py`
  - Test `tests/gin_qa/test_cases_new.py`
  - Test `tests/gin_qa/test_report.py`
  - Test `tests/gin_qa/test_tests_cli.py`
- **Interfaces**:
  - Consumes: `cases._lock`, `next_id`, `_slug`, `declared_types`, `write_atomic`, `capability_arg`.
  - Produces: `bugs.rerun_note(run: str | None, actual: str, evidence: list[str]) -> str`, `e2e.ignore_evidence(root: Path, eff: Effective) -> bool`, `cases.new_case(root: Path, cases_dir: str, guidelines: str, cap: str, kind: str, title: str, key: str, value: str) -> tuple[str, Path]`, `report.build(..., archive: bool = False)`, report key `zip`, bug key `appended`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** four small bounded changes with the code below; the data-loss order in `file_bug` and the `.cmd` shim limit need care.
- **Acceptance criteria**:
  - The named test files pass.
  - The full suite passes.
- **Estimated complexity**: medium

#### Steps

1. In `tests/gin_qa/test_cases_bug.py`:
   - In the expected dict of `test_files_a_bug_linked_to_the_spec_epic_and_records_it` (line 109), add `"appended": False`.
   - In `test_an_open_bug_is_kept_without_an_epic_and_a_closed_bug_is_replaced`, change the answers to `{"task show gw-7": shown("gw-7", "in_progress"), "task update gw-7": {}}` and add `"appended": True` to the expected dict.
   - Any other test that keeps an open bug gets the same `"task update <bug>": {}` answer.
   - Add to `class TestLegacy`:
     ```python
         def kept_bug(self) -> None:
             write(self.root, FILE, CASE.replace("- **Priority:** low\n",
                                                 "- **Priority:** low\n- **Result:** blocked\n- **Bug:** gw-7\n"))

         def test_a_re_run_appends_one_line_to_the_notes_of_the_open_bug(self):
             self.kept_bug()
             self.answer({"task show gw-7": shown("gw-7", "open"), "task update gw-7": {}})
             result = self.bug("TC-AUTH-001", "--actual", 'Shows "500" again', "--evidence", "a.png", "--evidence", "b.png",
                               "--run", "manual 2026-11-07")
             self.assertEqual(0, result.returncode, result.stderr)
             [update] = [call for call in self.calls() if call["argv"][:2] == ["task", "update"]]
             note = self.option(update["argv"], "--append-notes")
             self.assertRegex(note, r"^Re-run \d{4}-\d{2}-\d{2}; Run: manual 2026-11-07; "
                                    r"Actual: Shows '500' again; Evidence: a\.png, b\.png$")
             self.assertIn("- **Result:** failed\n", self.path.read_text(encoding="utf-8"))

         def test_a_failed_notes_update_exits_2_and_leaves_the_case(self):
             self.kept_bug()
             before = self.path.read_text(encoding="utf-8")
             self.answer({"task show gw-7": shown("gw-7", "open"),
                          "task update gw-7": {"stderr": "database locked\n", "code": 1}})
             result = self.bug("TC-AUTH-001", "--actual", "Still broken")
             self.assertEqual(2, result.returncode)
             self.assertIn("database locked", result.stderr)
             self.assertEqual(before, self.path.read_text(encoding="utf-8"))
     ```

2. Create `tests/gin_qa/test_cases_new.py`:
   ```python
   """`gin-qa cases new`: the file it writes, the SDD and legacy references, and every refusal."""

   from __future__ import annotations

   import json
   from pathlib import Path
   import sys
   import tempfile
   import unittest

   sys.path.insert(0, str(Path(__file__).resolve().parent))

   from qa_fixtures import AUTH_SPEC, gin_workflow_bin, make_repo, qa, write  # noqa: E402

   FILE = "qa/cases/auth/TC-AUTH-001-cancel-an-order.manual.md"


   class NewCase(unittest.TestCase):
       def setUp(self):
           self.tmp = tempfile.TemporaryDirectory()
           self.base = Path(self.tmp.name)
           self.bin = gin_workflow_bin(self.base)
           self.root = make_repo(self.base / "repo")
           write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)

       def tearDown(self):
           self.tmp.cleanup()

       def new(self, *args: str, title: str = "Cancel an order"):
           return qa(self.root, self.bin, "new", "auth", "--type", "manual", "--title", title, *args)

       def nothing_written(self) -> None:
           self.assertEqual([], list((self.root / "qa/cases").glob("**/*.md")) if (self.root / "qa/cases").exists() else [])

       def test_writes_a_named_pinned_file_with_the_next_id(self):
           result = self.new("--req", "REQ-AUTH-001", "--format", "json")
           self.assertEqual(0, result.returncode, result.stderr)
           self.assertEqual({"tc": "TC-AUTH-001", "file": FILE}, json.loads(result.stdout))
           text = (self.root / FILE).read_text(encoding="utf-8")
           self.assertTrue(text.startswith("# TC-AUTH-001: Cancel an order\n"))
           self.assertRegex(text, r"- \*\*REQ:\*\* REQ-AUTH-001@[0-9a-f]{8}\n- \*\*Priority:\*\* medium\n")
           for heading in ("Preconditions", "Test data", "Steps", "Expected"):
               self.assertIn(f"**{heading}:**\n", text)
           second = self.new("--req", "REQ-AUTH-001", title="Second")
           self.assertEqual("qa/cases/auth/TC-AUTH-002-second.manual.md", second.stdout.strip())

       def test_refusals_write_nothing(self):
           write(self.root, "qa/guidelines.md", "# Guidelines\n\n## Types\n\n- `manual`: by hand\n")
           for args in (("--req", "REQ-AUTH-999"), ("--source", "x.md"), ()):
               with self.subTest(args=args):
                   self.assertEqual(2, self.new(*args).returncode)
                   self.nothing_written()
           self.assertEqual(2, self.new("--req", "REQ-AUTH-001", title="").returncode)
           self.nothing_written()
           unlisted = qa(self.root, self.bin, "new", "auth", "--type", "e2e", "--title", "T", "--req", "REQ-AUTH-001")
           self.assertEqual(2, unlisted.returncode)
           self.assertIn("## Types", unlisted.stderr)
           self.nothing_written()

       def test_a_flat_cases_file_is_refused(self):
           write(self.root, "qa/cases/auth.md", "# Test cases: auth\n")
           result = self.new("--req", "REQ-AUTH-001")
           self.assertEqual(2, result.returncode)
           self.assertIn("gin-qa cases split auth", result.stderr)

       def test_the_legacy_layout_takes_a_source(self):
           root = make_repo(self.base / "legacy", layout="legacy")
           args = ("new", "auth", "--type", "manual", "--title", "T")
           self.assertEqual(2, qa(root, self.bin, *args, "--req", "REQ-AUTH-001").returncode)
           result = qa(root, self.bin, *args, "--source", ".planning/specs/a.md#US-1")
           self.assertEqual(0, result.returncode, result.stderr)
           self.assertIn("- **Source:** .planning/specs/a.md#US-1\n", (root / result.stdout.strip()).read_text(encoding="utf-8"))
   ```
   Add to `class TestReport` in `tests/gin_qa/test_report.py`, and `import zipfile` at the top:
   ```python
       def test_zip_holds_the_folder_and_keeps_it(self):
           payload = self.report_json("--zip")
           folder = (self.root / payload["report"]).parent
           self.assertEqual(f"{folder.name}.zip", Path(payload["zip"]).name)
           with zipfile.ZipFile(self.root / payload["zip"]) as archive:
               names = archive.namelist()
           self.assertIn(f"{folder.name}/index.html", names)
           self.assertIn(f"{folder.name}/2026-11-04T08-00-00/tc-auth-001/01.png", names)
           self.assertTrue(folder.is_dir())
           self.assertIsNone(self.report_json()["zip"])

       def test_a_failed_zip_exits_2_and_leaves_no_archive(self):
           with mock.patch("gin_qa.report.shutil.make_archive", side_effect=OSError("disk full")):
               with self.assertRaises(OSError):
                   report.build(self.root, resolve(specs_reqs(self.root)), None, "out", archive=True)
           self.assertEqual([], list(self.root.glob("*.zip")) + list(self.root.glob(".*.zip")))

       def test_the_evidence_folder_is_ignored_once_and_out_elsewhere_is_not(self):
           self.assertEqual(0, self.report("--out", "elsewhere").returncode)
           self.assertFalse((self.root / ".gitignore").exists())
           self.report_json()
           self.report_json()
           self.assertEqual(1, (self.root / ".gitignore").read_text().split().count("/qa/evidence/"))
   ```
   The `mock.patch` test needs `gin` on `PATH` for `specs_reqs`: reuse the way the existing `mock` test of this file sets it (`TOOLS_PATH`, `self.bin`).
   In `tests/gin_qa/test_tests_cli.py`, in the test holding `self.gin_tests("run", "--type", "api", "--format", "json")` at line 265, add after the returncode assertion:
   ```python
           self.assertIn("/qa/evidence/", (self.root / ".gitignore").read_text().split())
   ```
   Run `python3 -m pytest tests/gin_qa/test_cases_bug.py tests/gin_qa/test_cases_new.py tests/gin_qa/test_report.py tests/gin_qa/test_tests_cli.py -q`. Expected: the new tests fail.

3. In `bugs.py`, add `from datetime import datetime, timezone` to the imports. Before `file_bug`, add:
   ```python
   def rerun_note(run: str | None, actual: str, evidence: list[str]) -> str:
       """One line with no double quote: a Windows .cmd shim cuts an argument at its first newline and re-parses quotes."""
       day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
       parts = [f"Re-run {day}", *([f"Run: {run}"] if run else []), f"Actual: {actual}",
                *([f"Evidence: {', '.join(evidence)}"] if evidence else [])]
       return "; ".join(parts).replace('"', "'")
   ```
   In `file_bug`, replace the two lines under `if old is not None and old.get("status") not in (None, "closed"):` with:
   ```python
               added = _gin_workflow(root, "task", "update", previous, "--append-notes", rerun_note(run, actual, evidence))
               if added.returncode != 0:  # before the case changes, so the tester can run this again
                   raise QaError(added.stderr.strip() or f"gin task update exited {added.returncode}")
               row = tc.record_result(root, eff.cases_dir, case_id, "failed", run, previous)
               return {"tc": case_id, "bug": previous, "epic": None, "created": False, "appended": True,
                       "file": row["file"]}
   ```
   In the last `return` of `file_bug`, add `"appended": False`.

4. In `e2e.py`, before `init`, add:
   ```python
   def ignore_evidence(root: Path, eff: Effective) -> bool:
       """Adds the evidence folder to `.gitignore`; returns whether it wrote the entry."""
       ignore = root / ".gitignore"
       entry = f"/{evidence_root(eff)}/"
       lines = ignore.read_text(encoding="utf-8").splitlines() if ignore.is_file() else []
       if entry in lines:
           return False
       ignore.write_text("\n".join([*lines, entry]) + "\n", encoding="utf-8")
       return True
   ```
   In `init`, replace the five lines from `ignore = root / ".gitignore"` to `done.append(f"added {entry} to .gitignore")` with:
   ```python
       if ignore_evidence(root, eff):
           done.append(f"added /{evidence_root(eff)}/ to .gitignore")
   ```

5. In `tests.py`, change line 19 to `from .e2e import ignore_evidence, new_run_folder`, and add `ignore_evidence(root, eff)` right after `folder = new_run_folder(root, eff, f"-{kind}")`.

6. In `cases.py`, after `_slug`, add:
   ```python
   def new_case(root: Path, cases_dir: str, guidelines: str, cap: str, kind: str, title: str, key: str,
                value: str) -> tuple[str, Path]:
       """Writes `<cases>/<cap>/<TC-ID>-<slug>.<kind>.md` with the next ID; `key`/`value` is its REQ or Source field."""
       one_line(title)
       cap = capability_arg(cap)
       if not TYPE.fullmatch(cap):
           raise ValueError(f"{cap!r}: a capability matches [a-z][a-z0-9-]*")
       types, _ = declared_types(root, guidelines)
       if not TYPE.fullmatch(kind) or (types is not None and kind not in types):
           raise ValueError(f"{kind}: not listed under '{TYPES_SECTION}' in {guidelines}")
       base = root / cases_dir
       if (base / f"{cap}.md").is_file():
           raise ValueError(f"{cases_dir}/{cap}.md: a flat cases file; run `gin-qa cases split {cap}` first")
       (base / cap).mkdir(parents=True, exist_ok=True)
       with _lock(base):
           case_id = next_id(root, cases_dir, cap)
           path = base / cap / f"{case_id}{_slug(title)}.{kind}.md"
           write_atomic(path, f"# {case_id}: {title}\n\n- **{key}:** {value}\n- **Priority:** medium\n\n"
                              "**Preconditions:**\n\n**Test data:**\n\n**Steps:**\n\n**Expected:**\n")
       return case_id, path
   ```
   When `declared_types` returns None and `kind` matches `TYPE`, the type is accepted, as `cases check` does. The error message for an unlisted type names `## Types` through `TYPES_SECTION`.

7. In `cli.py` `_parser`, before `sub.add_parser("split", ...)`:
   ```python
       item = sub.add_parser("new", parents=[common])
       item.add_argument("capability")
       item.add_argument("--type", dest="kind", required=True)
       item.add_argument("--title", required=True)
       item.add_argument("--req", action="append", default=[])
       item.add_argument("--source")
   ```
   Before `_run`, add:
   ```python
   def _reference(eff: Effective, reqs: list[str], source: str | None) -> tuple[str, str]:
       """The REQ: field of an SDD case or the Source: field of a legacy case, as `(key, value)`."""
       if eff.layout != "sdd":
           if reqs or not source:
               raise ValueError("the legacy layout takes --source, not --req")
           return "Source", tc.one_line(source)
       if source or not reqs:
           raise ValueError("the SDD layout takes --req, not --source")
       unknown = [req for req in reqs if req not in eff.reqs]
       if unknown:
           raise ValueError(f"{', '.join(unknown)}: no such requirement")
       return "REQ", ", ".join(f"{req}@{eff.reqs[req]['hash'][:8]}" for req in reqs)
   ```
   In `_run`, before `if args.command == "split":`:
   ```python
       if args.command == "new":
           case_id, path = tc.new_case(root, eff.cases_dir, eff.guidelines, args.capability, args.kind, args.title,
                                       *_reference(eff, args.req, args.source))
           shown = path.relative_to(root).as_posix()
           _emit({"tc": case_id, "file": shown}, args.format, shown)
           return 0
   ```
   In `_report_parser`, add `parser.add_argument("--zip", action="store_true", dest="archive")`. In `_run_report`, pass `args.archive` to `report.build` and change the emit to:
   ```python
       _emit(payload, args.format, "\n".join(filter(None, (payload["report"], payload["zip"]))))
   ```
   In the usage text of `main`, add `new` to the `cases` list and change the report line to `gin-qa report [capability] [--out DIR] [--zip]`.

8. In `report.py`, add `import os`. Before `build`, add:
   ```python
   def _archive(folder: Path) -> Path:
       """`<folder>.zip` next to the folder, holding it; a failed write leaves no archive."""
       base = folder.with_name(f".{folder.name}.tmp")
       target = folder.with_name(f"{folder.name}.zip")
       try:
           os.replace(shutil.make_archive(str(base), "zip", root_dir=folder.parent, base_dir=folder.name), target)
       except OSError:
           Path(f"{base}.zip").unlink(missing_ok=True)
           raise
       return target
   ```
   Change the signature to `def build(root: Path, eff: Effective, capability: str | None, out: str | None, archive: bool = False) -> dict[str, Any]:`. Before the final `return`, add:
   ```python
       if root / e2e.evidence_root(eff) in folder.parents:
           e2e.ignore_evidence(root, eff)
       packed = _archive(folder) if archive else None
   ```
   Before `build`, add:
   ```python
   def _shown(root: Path, path: Path) -> str:
       return path.relative_to(root).as_posix() if root in path.parents else str(path)
   ```
   Use `_shown(root, index)` for `"report"`, and add `"zip": _shown(root, packed) if packed else None,` to the returned dict.

9. Run `python3 -m pytest tests/gin_qa -q`. Expected: pass.

10. Run `python3 -m pytest -n auto -q`. Expected: pass. Commit:
    ```
    feat(gin-qa): re-run notes on open bugs, evidence ignored without e2e, cases new, report --zip (gin-workflow-uj96.2)
    ```

### Track 3: `gin-qa e2e init --install` and the `ariaSnapshot` merge
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-qa/src/scripts/gin_qa/e2e.py` (`init`, `_commands`, `_install`, `_merge_snapshot`, `ARIA_EDITS`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:54,230` (`--install`)
  - Test `tests/gin_qa/test_e2e_cli.py`
- **Interfaces**:
  - Consumes: `e2e._playwright`, `e2e._has_e2e_script`, `cases.write_atomic`.
  - Produces: `e2e.init(root: Path, eff: Effective, base_url: str | None = None, install: bool = False) -> list[str]`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one function grows; subprocess failures and exact anchors are listed below.
- **Acceptance criteria**:
  - `tests/gin_qa/test_e2e_cli.py` passes.
  - The full suite passes.
- **Estimated complexity**: medium

#### Steps

1. In `tests/gin_qa/test_e2e_cli.py`, add after `FAKE_NPX`:
   ```python
   FAKE_MANAGER = textwrap.dedent('''\
       #!{python}
       """Stands in for npm, npx, pnpm, and yarn: logs its call; .pm-exit holds its exit code."""
       import pathlib, sys
       root = pathlib.Path.cwd()
       with open(root / ".pm-calls", "a") as log:
           log.write(" ".join([pathlib.Path(sys.argv[0]).stem, *sys.argv[1:]]) + "\\n")
       sys.exit(int((root / ".pm-exit").read_text()) if (root / ".pm-exit").exists() else 0)
   ''')

   OLD_FIXTURE = ("  screenshot: string | null;\n  error: string | null;\n"
                  "          let screenshot: string | null = null;\n"
                  "            } catch {\n              screenshot = null;\n            }\n"
                  "            screenshot,\n            error: failure ? firstLine(failure) : null,\n")
   ```
   Add this class:
   ```python
   class TestInitInstall(E2eCase):
       def setUp(self):
           super().setUp()
           for name in ("npm", "npx", "pnpm", "yarn"):
               python_stub(self.bin, name, FAKE_MANAGER.format(python=sys.executable))
           write(self.root, "package.json", '{"name": "app"}\n')

       def calls(self) -> list[str]:
           log = self.root / ".pm-calls"
           return log.read_text().splitlines() if log.exists() else []

       def test_without_the_flag_nothing_is_installed(self):
           self.assertEqual(0, self.e2e("init").returncode)
           self.assertEqual([], self.calls())

       def test_the_manager_follows_the_lockfile(self):
           for lockfile, expected in (
                   (None, ["npm install -D @playwright/test", "npx playwright install chromium"]),
                   ("pnpm-lock.yaml", ["pnpm add -D @playwright/test", "pnpm exec playwright install chromium"]),
                   ("yarn.lock", ["yarn add -D @playwright/test", "yarn playwright install chromium"])):
               with self.subTest(lockfile=lockfile):
                   (self.root / ".pm-calls").unlink(missing_ok=True)
                   if lockfile:
                       write(self.root, lockfile, "")
                   result = self.e2e("init", "--install")
                   self.assertEqual(0, result.returncode, result.stderr)
                   self.assertEqual(expected, self.calls())
                   (self.root / (lockfile or "none")).unlink(missing_ok=True)

       def test_adds_the_script_and_keeps_the_rest_of_package_json(self):
           self.assertEqual(0, self.e2e("init", "--install").returncode)
           data = json.loads((self.root / "package.json").read_text())
           self.assertEqual({"name": "app", "scripts": {"e2e": "playwright test"}}, data)

       def test_an_installed_package_is_not_installed_again(self):
           write(self.root, "node_modules/@playwright/test/package.json", "{}")
           self.assertEqual(0, self.e2e("init", "--install").returncode)
           self.assertEqual(["npx playwright install chromium"], self.calls())

       def test_a_failed_install_exits_2_and_names_the_commands(self):
           write(self.root, ".pm-exit", "3")
           result = self.e2e("init", "--install")
           self.assertEqual(2, result.returncode)
           self.assertIn("npm install -D @playwright/test", result.stderr)
           self.assertIn("npx playwright install chromium", result.stderr)

       def test_no_package_json_exits_2_and_writes_nothing(self):
           (self.root / "package.json").unlink()
           result = self.e2e("init", "--install")
           self.assertEqual(2, result.returncode)
           self.assertIn("package.json", result.stderr)
           self.assertFalse((self.root / "qa/e2e/evidence.ts").exists())


   class TestSnapshotMerge(E2eCase):
       def test_an_older_fixture_matching_the_anchors_is_merged(self):
           path = write(self.root, "qa/e2e/evidence.ts", OLD_FIXTURE)
           result = self.e2e("init")
           self.assertEqual(0, result.returncode, result.stderr)
           text = path.read_text()
           for needle in ("  snapshot: string | null;\n  url: string;\n", "let snapshot: string | null = null;",
                          "ariaSnapshot({ timeout: 5000 })", "snapshot,\n            url: page.url(),"):
               self.assertIn(needle, text)
           self.assertIn("merged", result.stdout)

       def test_an_edited_fixture_stays_unchanged_and_names_the_manual_steps(self):
           path = write(self.root, "qa/e2e/evidence.ts", "// my own fixture\n")
           result = self.e2e("init")
           self.assertEqual(0, result.returncode, result.stderr)
           self.assertEqual("// my own fixture\n", path.read_text())
           self.assertIn("explore-case.md", result.stdout)

       def test_a_current_fixture_is_left_alone(self):
           self.assertEqual(0, self.e2e("init").returncode)
           path = self.root / "qa/e2e/evidence.ts"
           before = path.read_text()
           self.assertNotIn("merged", self.e2e("init").stdout)
           self.assertEqual(before, path.read_text())
   ```
   Run `python3 -m pytest tests/gin_qa/test_e2e_cli.py -q -k "TestInitInstall or TestSnapshotMerge"`. Expected: fail.

2. In `e2e.py`, after `DEFAULT_BASE_URL`, add:
   ```python
   MANAGERS = (("pnpm-lock.yaml", ("pnpm", "add", "-D"), ("pnpm", "exec")), ("yarn.lock", ("yarn", "add", "-D"), ("yarn",)))
   ARIA_BLOCK = ("            try {\n"
                 "              const aria = await page.locator('body').ariaSnapshot({ timeout: 5000 });\n"
                 "              const file = `${String(n).padStart(2, '0')}.aria.yml`;\n"
                 "              fs.writeFileSync(path.join(tcDir, file), aria + '\\n');\n"
                 "              snapshot = file;\n"
                 "            } catch {\n"
                 "              snapshot = null;\n"
                 "            }\n")
   SCREENSHOT_CATCH = "            } catch {\n              screenshot = null;\n            }\n"
   # (old, new) pairs: each old text is in the template as `gin-qa e2e init` copied it before step snapshots.
   ARIA_EDITS = (
       ("  screenshot: string | null;\n  error: string | null;\n",
        "  screenshot: string | null;\n  snapshot: string | null;\n  url: string;\n  error: string | null;\n"),
       ("          let screenshot: string | null = null;\n",
        "          let screenshot: string | null = null;\n          let snapshot: string | null = null;\n"),
       (SCREENSHOT_CATCH, SCREENSHOT_CATCH + ARIA_BLOCK),
       ("            screenshot,\n            error: failure",
        "            screenshot,\n            snapshot,\n            url: page.url(),\n            error: failure"),
   )
   ```

3. In `e2e.py`, before `init`, add:
   ```python
   def _merge_snapshot(path: Path, shown: str) -> str:
       """Adds step snapshots to an older fixture on an exact anchor match; returns what it did, or ""."""
       text = path.read_text(encoding="utf-8")
       if "ariaSnapshot" in text:
           return ""
       if any(text.count(old) != 1 for old, _ in ARIA_EDITS):
           return (f"{shown} has no ariaSnapshot and differs from the template; merge it by hand "
                   "(references/explore-case.md of the e2e skill)")
       for old, new in ARIA_EDITS:
           text = text.replace(old, new)
       tc.write_atomic(path, text)
       return f"merged ariaSnapshot into {shown}"


   def _commands(root: Path) -> tuple[list[str], list[str]]:
       """The commands that install the package and chromium, by the lockfile at the repository root."""
       add, run = next(((add, run) for lockfile, add, run in MANAGERS if (root / lockfile).is_file()),
                       (("npm", "install", "-D"), ("npx",)))
       return [*add, "@playwright/test"], [*run, "playwright", "install", "chromium"]


   def _install(root: Path) -> list[str]:
       """Installs Playwright and chromium and adds the `e2e` script; a failure names the commands to run by hand."""
       package, browser = _commands(root)
       by_hand = " && ".join(" ".join(argv) for argv in (package, browser))
       done: list[str] = []
       for argv in ([] if _playwright(root) else [package]) + [browser]:
           program = shutil.which(argv[0])
           if program is None:
               raise QaError(f"{argv[0]}: not found; run by hand: {by_hand}")
           result = subprocess.run([program, *argv[1:]], cwd=root, capture_output=True, text=True)
           if result.returncode != 0:
               raise QaError(f"{' '.join(argv)} failed: {result.stderr.strip()[-300:]}; run by hand: {by_hand}")
           done.append(f"ran {' '.join(argv)}")
       if not _has_e2e_script(root):
           path = root / "package.json"
           data = json.loads(path.read_text(encoding="utf-8"))
           if not isinstance(data, dict) or not isinstance(data.setdefault("scripts", {}), dict):
               raise QaError("package.json: expected an object whose scripts is an object")
           data["scripts"]["e2e"] = "playwright test"
           tc.write_atomic(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
           done.append('added "e2e": "playwright test" to package.json')
       return done
   ```

4. In `init`:
   - Change the signature to `def init(root: Path, eff: Effective, base_url: str | None = None, install: bool = False) -> list[str]:`.
   - After `url = check_base_url(...)`, add:
     ```python
         if install and not (root / "package.json").is_file():
             raise QaError("no package.json at the repository root; create one before --install")
     ```
   - After the `if not target.exists():` block, add:
     ```python
         else:
             merged = _merge_snapshot(target, f"{eff.e2e_dir}/{FIXTURE}")
             done += [merged] if merged else []
     ```
   - Replace the last two `if` blocks, from `if _playwright(root) is None:` to the `add "e2e"` line, with:
     ```python
         if install:
             return done + _install(root)
         if _playwright(root) is None:
             done.append("@playwright/test is not installed here: npm install -D @playwright/test && "
                         "npx playwright install chromium")
         if not _has_e2e_script(root):
             done.append('add "e2e": "playwright test" to the package.json scripts')
     ```

5. In `cli.py`, replace `sub.add_parser("init", parents=[common]).add_argument("--base-url")` with:
   ```python
       item = sub.add_parser("init", parents=[common])
       item.add_argument("--base-url")
       item.add_argument("--install", action="store_true")
   ```
   and change the call to `e2e.init(root, eff, args.base_url, args.install)`.

6. Run `python3 -m pytest tests/gin_qa -q`. Expected: pass. An existing test that writes its own `evidence.ts` before `init` and compares the output exactly must expect the new hand-merge line; that line is the intended behaviour.

7. Run `python3 -m pytest -n auto -q`. Expected: pass. Commit:
   ```
   feat(gin-qa): e2e init --install and the ariaSnapshot merge for an older fixture (gin-workflow-uj96.3)
   ```

### Track 4: skills, templates, docs, and version
- **Dependencies**: Track 3
- **Files**:
  - Modify `plugins/gin-qa/src/skills/cases/SKILL.md:15` (step 6)
  - Modify `plugins/gin-qa/src/skills/run/SKILL.md:18` (step 5)
  - Modify `plugins/gin-qa/src/skills/report/SKILL.md:13` (step 4)
  - Modify `plugins/gin-qa/src/skills/e2e/SKILL.md:10` (step 1, and a new last rule)
  - Modify `plugins/gin-qa/src/skills/e2e/references/explore-case.md:31` (section "Fixture without snapshots")
  - Modify `plugins/gin-qa/src/templates/qa-readme.md:7`
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:15` (`VERSION = "0.11"`)
  - Modify `docs/guides/qa.md:64,84,95,120,172`, `docs/guides/qa.vi.md` (same sections)
  - Modify `docs/guides/ai-strategy.md:120-124`
  - Modify `docs/reference/cli.md:390-460` (gin-qa commands)
  - Test `tests/gin_qa/test_packaging.py`
- **Interfaces**:
  - Consumes: the commands, flags, and output of Tracks 1 to 3, exactly as their `Interfaces` state.
  - Produces: skill and docs text only, and the version.
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** text edits with the content below; budget and docs tests catch mistakes.
- **Acceptance criteria**:
  - `tests/gin_qa/test_packaging.py`, `gin docs check` on the changed docs, and the full suite pass.
- **Estimated complexity**: low

#### Steps

1. Run `grep -rn "0\.10" tests/gin_qa docs/reference docs/guides/qa.md`. Change `VERSION` in `cli.py` to `"0.11"` and any test or page that names the old version.

2. Skills:
   - `cases/SKILL.md` step 6: replace "Get each ID from `next-id <capability>`; never pick numbers yourself." with "Create each case with `new <capability> --type <type> --title <title> --req <REQ-ID>` (`--source <path>` with the legacy layout), which writes the file with the next ID and the pin, then fill it in; never pick numbers yourself." Keep the rest of the step.
   - `run/SKILL.md` step 5: replace "A kept bug did not get the new actual result or evidence: say so, so the tester can add them to the bug." with "A kept bug got the new actual result and evidence in its notes."
   - `report/SKILL.md` step 4: replace "To share the report, zip the folder that holds `index.html`: it contains every screenshot the page shows." with "To share the report, run `gin-qa report [capability] --zip`: it also writes `<folder>.zip`, with every screenshot the page shows." Keep the rest of the step.
   - `e2e/SKILL.md` step 1: where it runs `init`, say `init --install` installs Playwright and chromium, and adds the `e2e` script.
   - `e2e/SKILL.md`, last step: add "A case that keeps failing or flaking on the pipeline can leave automation: when the user decides so, run `gin-qa cases to-manual <TC-ID> --reason <why>`. It renames the case to `.manual.md`, deletes the spec, and resets the result; `/gin-qa:run` then walks it."
   - `explore-case.md`, section "Fixture without snapshots": open with "`gin-qa e2e init` merges this block when the fixture matches the template exactly, and otherwise says so and leaves the file." Keep the block for the manual case.

3. `plugins/gin-qa/src/templates/qa-readme.md` line 7: replace "`gin-qa e2e init` git-ignores it (without e2e, add `qa/evidence/` to `.gitignore`)" with "`gin-qa e2e init`, `gin-qa tests run`, and `gin-qa report` git-ignore it".

4. `docs/guides/qa.md`, and the same changes in Vietnamese in `qa.vi.md`, with commands and paths verbatim:
   - Line 64: IDs come from `gin-qa cases new`, which also writes the file and the pin.
   - Line 84: when the case's `Bug:` names an open bead, no bug is filed; the new actual result and evidence go into the bead's notes as one line.
   - Line 95: `gin-qa e2e init --install` also installs Playwright and chromium with the manager of the lockfile and adds the `e2e` script; `e2e init` merges step snapshots into an older fixture that matches the template.
   - Section on the report: `--zip`; the section "Moved from e2e to manual".
   - New section "Moving a flaky e2e case to manual": when to use it (QA decides, gin-qa does not count failures); the command; what it changes (file name, `Moved from e2e:` line, `Result: not run`, spec deleted; `Bug:` kept); then `/gin-qa:run`; how to go back (rename the file, remove the line, run `/gin-qa:e2e`).
   - Line 172: the command lists.

5. `docs/guides/ai-strategy.md:120-124`: replace the `next-id`, hand-written file, and `pin` steps with `gin-qa cases new`.

6. `docs/reference/cli.md`: in the command list at line 390 add `new` and `to-manual`; add sections `### gin-qa cases new` and `### gin-qa cases to-manual` with usage, exit 2 cases, and text and JSON output, as the other sections do; in `### gin-qa cases bug` state the notes line and `appended`; in `### gin-qa cases export` add `moved_from_e2e`; in `### gin-qa report` add `--zip`, `zip`, and `moved`; in the `e2e init` entry add `--install`.

7. Run `python3 -m pytest tests/gin_qa/test_packaging.py -q` and `gin docs check docs/guides/qa.md docs/guides/qa.vi.md docs/guides/ai-strategy.md docs/reference/cli.md`. Expected: pass and `ok`.

8. Run `python3 -m pytest -n auto -q`. Expected: pass. Commit:
   ```
   docs(gin-qa): skills and guides use cases new, cases to-manual, report --zip, and e2e init --install; gin-qa 0.11 (gin-workflow-uj96.4)
   ```

## Integration
- **Branch**: `feat/qa-utilities`
- **Merge strategy**: sequential

## Validation
- [ ] All tests pass (`python3 -m pytest -n auto -q`)
- [ ] `gin docs check` is `ok` on the changed pages
- [ ] Manual verification: in a scratch repository, move an e2e case to manual, record a result, and open the report's `index.html` to see the section

## Notes
- `Model:` and `Effort:` come from the main harness catalog using the route rubric.
- The parent bead `gin-workflow-uj96` stays open until a human-confirmed merge; track beads close after tests and review pass.
- Test placement differs a little from the spec's Testing section: `to-manual` and `cases new` get their own test files because each needs its own setup.

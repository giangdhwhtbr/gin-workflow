# Plan: Case files per test case, readable format, recorded results

Epic: gin-workflow-qa-case-folders
Spec: .planning/specs/2026-11-04-qa-case-folders-design.md

## Objective

Each test case can live in its own file, `qa/cases/<capability>/TC-<CAP>-NNN[-<slug>].<type>.md`, whose name sets the type; cases read well when rendered (bold `- **Key:** value` fields, bold section labels, a `Test data` section); every case carries its latest `Result`, `Run`, and `Bug`, written only by `gin-qa cases result` and by `gin-qa e2e run`; `gin-qa cases split` moves a flat `<capability>.md` to per-case files without changing any `hash8`.

Goal (from the spec): after this change each case is its own file, `qa/cases/<capability>/TC-<CAP>-NNN-<slug>.<type>.md`; the file name sets the type; each case carries `Result`, `Run`, and `Bug` lines written only by `gin-qa cases result`; and `gin-qa e2e run` records every case it ran.

Architecture: all parsing and writing of case files stays in `plugins/gin-qa/src/scripts/gin_qa/cases.py`. One parser (`_parse_block`) reads both label forms and both heading levels; `load()` reads flat files and per-case files through one `parse_path()`. Writers (`record_result`, `split`, and `pin` through `field_line`) live next to the parser and write under a lock file with an atomic replace. `cli.py` only wires subcommands; `e2e.py` selects cases by `Case.type` and calls `cases.record_result` after a run.

Tech Stack: Python 3 stdlib (`re`, `os`, `subprocess`, `contextlib`, `time`) in the gin-qa CLI; `unittest` tests run by `python3 -m pytest -n auto`; Markdown skills, templates, and docs.

### Global Constraints (verbatim from the spec)

- Out of scope: runners for non-e2e types; a manual-run skill (epic `gin-workflow-qa-manual-bugs`); the report (epic `gin-workflow-qa-report`, now an interactive HTML report), which reads the export fields this epic adds.
- One file per case, the type as the last name part before `.md` (`.e2e.md`, `.manual.md`, `.api.md`), not one file per type.
- Migration through a `split` command, not a silent dual layout.
- A result recorded without `--bug` keeps the existing `Bug` line.
- Field and section labels in bold; fields as `- ` list items so rendered Markdown keeps one field per line.
- A `Test data` section modelled on QFO-AT's scenarios: the data a case needs, described in words; credentials only as environment variable names.
- `e2e run` records results on every run; no `--no-record` flag (per-case files remove concurrent writes to one file).
- `hash8` is unchanged for every existing case (R2, R6), so no e2e spec becomes stale from this release.
- `cases export` keeps its existing keys; `result`, `run`, `bug`, `test_data` are added.
- `cases result` and `split` write files only after every check passes; a failed command leaves the tree unchanged.

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
- Problem statement: cases live one file per capability with the type in a `Type:` field (`cases.py:103-124`), the format renders as one run-on paragraph of fields, there is no place for test data or a recorded result, and `e2e run` leaves nothing in the case files (`e2e.py:207-236`).
- Success criteria: the spec's US-1 to US-5 acceptance criteria; `python3 -m pytest -n auto` green; `bash tests/install_smoke_test.sh` passes; every existing case keeps its `hash8`.
- Constraints: Global Constraints above; the evidence fixture, `result.json`, `check_run`, and `e2e export` shapes are unchanged.
- Non-goals: non-e2e runners, a manual-run skill, the report, restyling plain-label cases automatically.

## Approach Options
### Option 1: Extend `cases.py` in place
- Summary: one parser handles both label forms and both heading levels; `load()` adds per-case files; writers sit next to the parser.
- Pros: one module owns the case format; flat and per-case cases share every check; smallest surface.
- Cons: `cases.py` grows from 173 to about 330 lines.

### Option 2: A separate `case_files.py` module for the per-case layout and writers
- Summary: keep `cases.py` for flat files, add a module for the new layout and the writers.
- Pros: smaller files.
- Cons: two parsers drift; `record_result` and `pin` must handle both layouts anyway, so the split is artificial.

### Recommended Approach
- Selected option: Option 1.
- Rationale: the format is one concept with two spellings; one owner keeps `hash8` identical across layouts, which the spec requires.

## Scope
- In scope: spec R1–R10.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 writes through the parser Track 1 changes, Track 3 calls Track 2's writer, and Track 4 documents the commands the first three tracks create, so each track runs after the one before.
```

## Tasks

### Track 1: Parser, per-case loader, check, next-id, hash and export
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cases.py:1-173` (regexes and constants, `Case`, `_parse_block`, `parse_file`, new `parse_case_file`/`parse_path`, `case_files`, `load`, `next_id`, `hash8`, `as_dict`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:91-99` (`_check` probe iterates the list `case_files` now returns)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/e2e.py:43-45` (`e2e_cases` selects by `case.type`)
  - Test `tests/gin_qa/qa_fixtures.py` (new helper `case_file`)
  - Test `tests/gin_qa/test_cases_cli.py` (updated section-order message; new classes `TestCaseFiles`, `TestReadableFormat`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** one module with a clear spec, but the parser takes many edge cases (two label forms, two heading levels, file-name rules, history-based IDs) and must keep every existing `hash8`.
- **Acceptance criteria**: spec US-1, US-2; R1–R6 as written; every test in Steps passes; all existing tests in `tests/gin_qa/` pass with only the one message change in Step 1.1.
- **Estimated complexity**: medium

Interfaces produced:
- `cases.SECTIONS = ("Preconditions", "Test data", "Steps", "Expected")`
- `cases.RESULTS = ("passed", "failed", "blocked", "not run")`
- `cases.RESULT_FIELDS = ("Result", "Run", "Bug")`
- `cases.KNOWN_FIELDS = ("REQ", "Source", "Type", "Priority", "Result", "Run", "Bug")`
- `Case.type: str = ""`, `Case.test_data: list[str]`
- `cases.parse_file(path: Path, shown: str) -> tuple[list[Case], list[str]]` (flat file; sets `type` from `Type:`)
- `cases.parse_case_file(path: Path, shown: str) -> tuple[list[Case], list[str]]` (per-case file; sets `type` from the name)
- `cases.parse_path(root: Path, cases_dir: str, path: Path) -> tuple[list[Case], list[str]]` (picks one of the two)
- `cases.case_files(root: Path, cases_dir: str) -> list[Path]` (flat `*.md` and `*/*.md`, sorted)
- `cases.field_line(like: str, key: str, value: str) -> str`
- `as_dict` adds `type` (from `case.type`), `result`, `run`, `bug`, `test_data`.

Interfaces consumed: `qa`, `write`, `case`, `cases_file`, `commit_all`, `hash8` (`tests/gin_qa/qa_fixtures.py`); `QaCase` (`tests/gin_qa/test_cases_cli.py:21-44`).

#### Step 1.1: Fixture helper and failing tests

In `tests/gin_qa/qa_fixtures.py`, append:

```python
def case_file(tc_id: str, ref: str, *, title: str = "Case", extra: str = "", bold: bool = True) -> str:
    """One per-case file body (`# ` heading, no Type:); `ref` is the whole REQ:/Source: value line, plain form."""
    key, value = ref.split(": ", 1)
    if not bold:
        return case(tc_id, ref, title=title, extra=extra).replace("### ", "# ", 1).replace("Type: e2e\n", "")
    fields = [f"- **{key}:** {value}", "- **Priority:** high",
              *(f"- **{k}:** {v}" for k, v in (line.split(": ", 1) for line in extra.splitlines() if line))]
    return (f"# {tc_id}: {title}\n\n" + "\n".join(fields) + "\n\n**Preconditions:**\n- a user exists\n\n"
            "**Steps:**\n1. Open /login\n2. Click \"Sign in\"\n\n**Expected:**\n- The dashboard is shown\n")
```

In `tests/gin_qa/test_cases_cli.py`:
- Import `case_file` from `qa_fixtures`, and `parse_case_file` from `gin_qa.cases`.
- In `test_each_structure_finding_has_file_and_line`, replace the expected message `"qa/cases/auth.md:26: TC-AUTH-003: sections must appear once, in the order Preconditions, Steps, Expected"` with `"qa/cases/auth.md:26: TC-AUTH-003: sections must appear once, in the order Preconditions, Test data, Steps, Expected"`.
- Add before `class TestCaseHash`:

```python
class TestCaseFiles(QaCase):
    def put(self, name: str, body: str) -> Path:
        return write(self.root, f"qa/cases/{name}", body)

    def test_per_case_files_load_with_type_from_the_name(self):
        self.put("auth/TC-AUTH-001-sign-in.e2e.md", case_file("TC-AUTH-001", self.ref("REQ-AUTH-001"), title="Login"))
        self.put("auth/TC-AUTH-002.manual.md", case_file("TC-AUTH-002", self.ref("REQ-AUTH-002"), bold=False))
        self.assertEqual([], self.findings())
        rows = {row["id"]: row for row in self.run_json("export")["cases"]}
        self.assertEqual(("e2e", "qa/cases/auth/TC-AUTH-001-sign-in.e2e.md", 1, "Login"),
                         (rows["TC-AUTH-001"]["type"], rows["TC-AUTH-001"]["file"], rows["TC-AUTH-001"]["line"],
                          rows["TC-AUTH-001"]["title"]))
        self.assertEqual("manual", rows["TC-AUTH-002"]["type"])
        self.assertEqual(("not run", "", "", []), tuple(rows["TC-AUTH-001"][key]
                                                         for key in ("result", "run", "bug", "test_data")))

    def test_each_per_case_finding(self):
        good = self.ref("REQ-AUTH-001", "REQ-AUTH-002")
        self.put("auth/TC-AUTH-001.e2e.md", case_file("TC-AUTH-001", good))
        self.put("auth/sign-in.e2e.md", case_file("TC-AUTH-002", good))
        self.put("auth/TC-AUTH-003-Bad.e2e.md", case_file("TC-AUTH-003", good))
        self.put("auth/TC-AUTH-004.e2e.md", case_file("TC-AUTH-005", good))
        self.put("auth/TC-BILL-001.e2e.md", case_file("TC-BILL-001", good))
        self.put("auth/TC-AUTH-006.e2e.md", case_file("TC-AUTH-006", good) + "\n" + case_file("TC-AUTH-007", good))
        self.put("auth/TC-AUTH-008.e2e.md", case_file("TC-AUTH-008", good).replace("- **Priority:** high",
                                                                                  "- **Type:** e2e"))
        self.put("auth/TC-AUTH-009.e2e.md", case_file("TC-AUTH-009", good, extra="Result: done\n"))
        self.put("auth/TC-AUTH-010.e2e.md", case_file("TC-AUTH-010", good, extra="Bug: gw-1\n"))
        self.put("auth/TC-AUTH-011.e2e.md", case_file("TC-AUTH-011", good).replace("# TC-AUTH-011", "### TC-AUTH-011"))
        self.write_cases(case("TC-AUTH-012", good))
        self.maxDiff = None
        self.assertEqual([
            "qa/cases/auth/TC-AUTH-003-Bad.e2e.md: case file name is not '<TC-ID>[-<slug>].<type>.md'",
            "qa/cases/auth/TC-AUTH-004.e2e.md:1: TC-AUTH-005: file name says TC-AUTH-004",
            "qa/cases/auth/TC-AUTH-006.e2e.md: holds 2 headings; a case file holds one '# TC-<CAP>-<NNN>: <title>'",
            "qa/cases/auth/TC-AUTH-008.e2e.md:4: TC-AUTH-008: Type comes from the file name; remove the Type: line",
            "qa/cases/auth/TC-AUTH-009.e2e.md:5: TC-AUTH-009: Result is one of passed, failed, blocked, not run; "
            "got 'done'",
            "qa/cases/auth/TC-AUTH-010.e2e.md:5: TC-AUTH-010: Bug: needs a Result: line",
            "qa/cases/auth/TC-AUTH-011.e2e.md:1: heading is not a test case '# TC-<CAP>-<NNN>: <title>': "
            "'### TC-AUTH-011: Case'",
            "qa/cases/auth/TC-BILL-001.e2e.md:1: TC-BILL-001 belongs in qa/cases/bill/, not auth/",
            "qa/cases/auth/sign-in.e2e.md: case file name is not '<TC-ID>[-<slug>].<type>.md'",
            "qa/cases/auth.md: capability also has folder qa/cases/auth/; run gin-qa cases split auth",
        ], self.findings())

    def test_next_id_counts_file_names_and_their_history(self):
        self.put("auth/TC-AUTH-004-old.e2e.md", case_file("TC-AUTH-004", self.ref("REQ-AUTH-001")))
        self.assertEqual("TC-AUTH-005\n", qa(self.root, self.bin, "next-id", "auth").stdout)
        commit_all(self.root)
        (self.root / "qa/cases/auth/TC-AUTH-004-old.e2e.md").unlink()
        self.assertEqual("TC-AUTH-005\n", qa(self.root, self.bin, "next-id", "auth").stdout)
        self.assertEqual("TC-USER-AUTH-001\n", qa(self.root, self.bin, "next-id", "user-auth").stdout)

    def test_test_globs_probe_covers_case_files(self):
        config = self.root / ".agent-workflow/config.yaml"
        config.write_text(config.read_text().replace("  layout: sdd\n", "  layout: sdd\n  test_globs:\n"
                                                      "    - qa/cases/*/*.e2e.md\n"))
        self.put("auth/TC-AUTH-001.e2e.md", case_file("TC-AUTH-001", self.ref("REQ-AUTH-001", "REQ-AUTH-002")))
        self.assertEqual(["qa/cases/auth/TC-AUTH-001.e2e.md: matches artifacts.test_globs pattern "
                          "'qa/cases/*/*.e2e.md'; test cases would count as executed tests in specs trace"],
                         self.findings())


class TestReadableFormat(unittest.TestCase):
    def parse(self, body: str, name: str = "TC-AUTH-001.e2e.md"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "auth" / name
            path.parent.mkdir()
            path.write_text(body, encoding="utf-8")
            found, errors = parse_case_file(path, f"qa/cases/auth/{name}")
        self.assertEqual([], errors)
        return found[0]

    def test_bold_and_plain_forms_parse_alike_and_hash_alike(self):
        bold = self.parse(case_file("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000", extra="Owner: qa\n"))
        plain = self.parse(case_file("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000", extra="Owner: qa\n", bold=False))
        flat = parse_file_text(case("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000", extra="Owner: qa\n"))
        self.assertEqual(({"Owner": "qa"}, [("REQ-AUTH-001", "00000000")]), (
            {k: v for k, v in bold.fields.items() if k == "Owner"}, bold.reqs))
        self.assertEqual(case_hash8(bold), case_hash8(plain))
        self.assertEqual(case_hash8(flat), case_hash8(bold))

    def test_test_data_is_parsed_exported_and_hashed_only_when_present(self):
        body = case_file("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000")
        without = self.parse(body)
        with_data = self.parse(body.replace("**Steps:**", "**Test data:**\n- Email: alice@example.com\n\n**Steps:**"))
        self.assertEqual(["Email: alice@example.com"], with_data.test_data)
        self.assertNotEqual(case_hash8(without), case_hash8(with_data))
        self.assertEqual(case_hash8(without), case_hash8(self.parse(body.replace(
            "**Steps:**", "**Test data:**\n\n**Steps:**"))))

    def test_result_fields_change_neither_hash_nor_free_fields(self):
        body = case_file("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000")
        recorded = self.parse(body.replace("- **Priority:** high", "- **Priority:** high\n- **Result:** failed\n"
                                                                   "- **Run:** qa/evidence/x\n- **Bug:** gw-9"))
        self.assertEqual(case_hash8(self.parse(body)), case_hash8(recorded))
        row = as_dict(recorded)
        self.assertEqual(({}, "failed", "qa/evidence/x", "gw-9"), (row["fields"], row["result"], row["run"], row["bug"]))
```

and add this module-level helper next to the imports:

```python
def parse_file_text(block: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "auth.md"
        path.write_text(cases_file("auth", block), encoding="utf-8")
        found, errors = parse_file(path, "qa/cases/auth.md")
    assert errors == [], errors
    return found[0]
```

Also import `as_dict` from `gin_qa.cases`. Update `test_export_keeps_free_fields` to expect the four new keys: `"result": "not run", "run": "", "bug": "", "test_data": []`.

Run: `python3 -m pytest tests/gin_qa/test_cases_cli.py -q` → the new tests and the two edited ones fail.

#### Step 1.2: Parser constants and `Case`

In `cases.py`, replace the constants block (lines 10-17) with:

```python
TC_ID = re.compile(r"\bTC-([A-Z][A-Z0-9-]*)-(\d{3,})\b")
_FIELD = re.compile(r"^(?:- )?(\*\*)?([A-Za-z][A-Za-z0-9 _-]*):(?(1)\*\*)\s*(\S.*)$")
_REQ_ITEM = re.compile(r"^(REQ-[A-Z][A-Z0-9-]*-\d{3,})@([0-9a-f]{8})$")
_STEP = re.compile(r"^(\d+)\. (\S.*)$")
_CASE_FILE = re.compile(r"^(TC-[A-Z][A-Z0-9-]*-\d{3,})(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?\.([a-z][a-z0-9-]*)\.md$")
TYPE = re.compile(r"^[a-z][a-z0-9-]*$")
SECTIONS = ("Preconditions", "Test data", "Steps", "Expected")
RESULTS = ("passed", "failed", "blocked", "not run")
RESULT_FIELDS = ("Result", "Run", "Bug")
KNOWN_FIELDS = ("REQ", "Source", "Type", "Priority", *RESULT_FIELDS)


def _heading(level: str) -> re.Pattern[str]:
    return re.compile(rf"^{level} (TC-([A-Z][A-Z0-9-]*)-(\d{{3,}})): (\S.*)$")
```

Add to `Case` after `expected`: `test_data: list[str] = field(default_factory=list)` and `type: str = ""`.

#### Step 1.3: `_parse_block` with both forms

Change the signature to `_parse_block(path, lines, start, end, errors, level: str = "###")`. Changes inside:

- `found = _heading(level).match(lines[start])`; the heading error message becomes `f"{where}: heading is not a test case '{level} TC-<CAP>-<NNN>: <title>': {lines[start]!r}"`.
- Section detection: `label = line.strip().removeprefix("**").removesuffix("**")` and `name = label[:-1] if label.endswith(":") else ""`.
- The order message becomes `"sections must appear once, in the order " + ", ".join(SECTIONS)`.
- Field lines: `key, value = match.group(2).strip(), match.group(3).strip()`.
- Bullet sections: `{"Preconditions": case.preconditions, "Test data": case.test_data, "Expected": case.expected}[section].append(...)`.
- After the REQ handling, before `return case`:

```python
    result = case.fields.get("Result")
    if result is not None and result not in RESULTS:
        errors.append(f"{path}:{case.field_lines['Result']}: {case.id}: Result is one of {', '.join(RESULTS)}; "
                      f"got {result!r}")
    for key in ("Run", "Bug"):
        if key in case.fields and result is None:
            errors.append(f"{path}:{case.field_lines[key]}: {case.id}: {key}: needs a Result: line")
```

#### Step 1.4: Files, loader, next-id

Replace `parse_file`'s last loop so each case gets `case.type = case.fields.get("Type", "").strip().lower()`. Add:

```python
def parse_case_file(path: Path, shown: str) -> tuple[list[Case], list[str]]:
    """A per-case file `<TC-ID>[-<slug>].<type>.md` holding one `# TC-…: <title>` case; the type is the name's."""
    named = _CASE_FILE.match(path.name)
    if not named:
        return [], [f"{shown}: case file name is not '<TC-ID>[-<slug>].<type>.md'"]
    lines = path.read_text(encoding="utf-8").splitlines()
    heads = [index for index, line in enumerate(lines) if line.startswith("#")]
    if len(heads) != 1:
        return [], [f"{shown}: holds {len(heads)} headings; a case file holds one '# TC-<CAP>-<NNN>: <title>'"]
    errors: list[str] = []
    case = _parse_block(PurePosixPath(shown), lines, heads[0], len(lines), errors, "#")
    if case is None:
        return [], errors
    case.type = named.group(2)
    if case.id != named.group(1):
        errors.append(f"{shown}:{case.line}: {case.id}: file name says {named.group(1)}")
    if "Type" in case.fields:
        errors.append(f"{shown}:{case.field_lines['Type']}: {case.id}: Type comes from the file name; "
                      "remove the Type: line")
    return [case], errors


def parse_path(root: Path, cases_dir: str, path: Path) -> tuple[list[Case], list[str]]:
    shown = path.relative_to(root).as_posix()
    flat = path.parent == root / cases_dir
    return parse_file(path, shown) if flat else parse_case_file(path, shown)


def case_files(root: Path, cases_dir: str) -> list[Path]:
    """Flat `<cases>/<capability>.md` files and per-case `<cases>/<capability>/*.md` files."""
    base = root / cases_dir
    return sorted([*base.glob("*.md"), *base.glob("*/*.md")]) if base.is_dir() else []
```

`load()` iterates `case_files`; for each path: `found, problems = parse_path(root, cases_dir, path)`; `errors += problems`. For a flat file (`path.parent == base`): `cap = path.stem`; when `(base / cap).is_dir()` append `f"{cases_dir}/{cap}.md: capability also has folder {cases_dir}/{cap}/; run gin-qa cases split {cap}"`; the existing `belongs in` message stays. For a per-case file: `folder = path.parent.name`; a case with `case.cap != folder` appends `f"{case.path}:{case.line}: {case.id} belongs in {cases_dir}/{case.cap}/, not {folder}/"`. The duplicate check is unchanged.

Findings order must match Step 1.1: files are visited in `sorted` `Path` order, where a capability folder's files (`auth/…`) sort before the flat `auth.md`; each file's findings are appended as they come, and a flat file's folder-conflict finding comes before its own parse findings.

`next_id`:

```python
def next_id(root: Path, cases_dir: str, cap: str) -> str:
    """One past the highest number in the flat file, the case file names, or their git history: never reused."""
    path, folder = root / cases_dir / f"{cap}.md", root / cases_dir / cap
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    text += "\n".join(item.name for item in folder.glob("*.md")) if folder.is_dir() else ""
    for args in (["-p", "--", str(path)], ["--name-only", "--", str(folder)]):
        history = subprocess.run(["git", "log", "--format=", *args], cwd=root, capture_output=True, text=True,
                                 check=False)
        if history.returncode == 0:
            text += "\n" + history.stdout
    upper = cap.upper()
    numbers = [int(match.group(2)) for match in TC_ID.finditer(text) if match.group(1) == upper]
    return f"TC-{upper}-{max(numbers, default=0) + 1:03d}"
```

#### Step 1.5: `hash8`, `as_dict`, `field_line`

```python
def hash8(case: Case) -> str:
    """What a test implements: title, free fields, and sections. REQ:/Source:, Type, Priority, and the result
    fields are left out; an empty Test data section adds nothing, so cases written before it keep their hash."""
    lines = [case.title, *(f"{key}: {value}" for key, value in case.fields.items() if key not in KNOWN_FIELDS)]
    for name, items in zip(SECTIONS, (case.preconditions, case.test_data, case.steps, case.expected)):
        if name != "Test data" or items:
            lines += [f"{name}:", *items]
    return hashlib.sha256("\n".join(line.strip() for line in lines).encode("utf-8")).hexdigest()[:8]


def field_line(like: str, key: str, value: str) -> str:
    """`key: value` in the form of the field line `like`: `- **Key:** value` or `Key: value`."""
    return f"- **{key}:** {value}" if like.lstrip().startswith("- **") else f"{key}: {value}"
```

`as_dict`: `"type": case.type`; add `"result": case.fields.get("Result", "not run")`, `"run": case.fields.get("Run", "")`, `"bug": case.fields.get("Bug", "")`, `"test_data": case.test_data`.

In `e2e.py:45`: `return {case.id: case for case in cases if case.type == "e2e"}`.

In `cli.py:93-94`: `files = [f"{eff.cases_dir}/probe.md", *(path.relative_to(root).as_posix() for path in tc.case_files(root, eff.cases_dir))]`.

Run: `python3 -m pytest tests/gin_qa -q` → all pass.

#### Step 1.6: Commit

`git add -A plugins/gin-qa/src/scripts tests/gin_qa && git commit -m "feat(gin-qa): per-case files, readable format, test data, result fields"`.

### Track 2: `cases result`, `cases split`, and form-keeping `pin`
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cases.py` (new `_lock`, `write_atomic`, `_with_result`, `record_result`, `_slug`, `split`; imports `os`, `time`, `contextlib.contextmanager`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:18-32` (subparsers `result`, `split`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:115-141` (`_pin` keeps the line form, writes atomically)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:150-173` (`_run` handles `result` and `split`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:212` (usage line lists `result`, `split`)
  - Test `tests/gin_qa/test_cases_cli.py` (new classes `TestResult`, `TestSplit`; one pin test)
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** file writers under concurrency (lock file, atomic replace, Windows replace retry) plus a migration command that must refuse before writing anything and keep every `hash8`.
- **Acceptance criteria**: spec US-3, US-4; R7, R8 as written; every test in Steps passes.
- **Estimated complexity**: high

Interfaces produced:
- `cases.record_result(root: Path, cases_dir: str, case_id: str, status: str, run: str | None = None, bug: str | None = None) -> dict[str, str]` — returns `{"tc", "result", "run", "bug", "file"}`; raises `ValueError` (CLI exit 2) for an unknown case, bad status, bad value, findings on that case, or a held lock.
- `cases.split(root: Path, cases_dir: str, cap: str) -> tuple[list[str], list[str]]` — `(written paths, findings)`; findings mean nothing was written; raises `ValueError` when the flat file does not exist.
- `cases.write_atomic(path: Path, text: str) -> None`
- CLI: `gin-qa cases result <TC-ID> <status> [--run REF] [--bug ID|none]`, `gin-qa cases split <capability>`, both with `--repository`, `--format`.

Interfaces consumed: `parse_path`, `load`, `field_line`, `RESULTS`, `RESULT_FIELDS`, `TYPE`, `parse_file` (Track 1).

#### Step 2.1: Failing tests

Add to `tests/gin_qa/test_cases_cli.py` (before `class TestReadableFormat`):

```python
class TestResult(QaCase):
    def setUp(self):
        super().setUp()
        self.path = write(self.root, "qa/cases/auth/TC-AUTH-001.e2e.md",
                          case_file("TC-AUTH-001", self.ref("REQ-AUTH-001", "REQ-AUTH-002")))

    def result(self, *args: str):
        return qa(self.root, self.bin, "result", "TC-AUTH-001", *args)

    def test_add_replace_and_remove_lines_in_the_case_form(self):
        self.assertEqual(0, self.result("failed", "--run", "qa/evidence/r1", "--bug", "gw-7").returncode)
        text = self.path.read_text()
        self.assertIn("- **Priority:** high\n- **Result:** failed\n- **Run:** qa/evidence/r1\n- **Bug:** gw-7\n\n"
                      "**Preconditions:**", text)
        out = qa(self.root, self.bin, "result", "TC-AUTH-001", "passed", "--format", "json")
        self.assertEqual({"tc": "TC-AUTH-001", "result": "passed", "run": "", "bug": "gw-7",
                          "file": "qa/cases/auth/TC-AUTH-001.e2e.md"}, json.loads(out.stdout))
        self.assertIn("- **Priority:** high\n- **Result:** passed\n- **Bug:** gw-7\n\n", self.path.read_text())
        self.assertEqual(0, self.result("not run", "--bug", "none").returncode)
        self.assertIn("- **Priority:** high\n- **Result:** not run\n\n", self.path.read_text())
        self.assertEqual([], self.findings())

    def test_plain_flat_case_gets_plain_lines(self):
        self.path.unlink()
        self.path.parent.rmdir()
        flat = self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001", "REQ-AUTH-002")))
        self.assertEqual(0, self.result("blocked", "--run", "manual 2026-11-04").returncode)
        self.assertIn("Priority: high\nResult: blocked\nRun: manual 2026-11-04\n", flat.read_text())

    def test_bad_input_exits_2_and_writes_nothing(self):
        before = self.path.read_text()
        for args, message in ((("done",), "status is one of passed, failed, blocked, not run"),
                              (("passed", "--run", "a\nb"), "values are one non-empty line"),
                              (("passed", "--bug", ""), "values are one non-empty line")):
            with self.subTest(args=args):
                result = self.result(*args)
                self.assertEqual(2, result.returncode)
                self.assertIn(message, result.stderr)
        unknown = qa(self.root, self.bin, "result", "TC-AUTH-404", "passed")
        self.assertEqual((2, True), (unknown.returncode, "TC-AUTH-404: no such test case" in unknown.stderr))
        self.path.write_text(before.replace("1. Open /login", "- Open /login"))
        broken = self.path.read_text()
        self.assertEqual(2, self.result("passed").returncode)
        self.assertEqual(broken, self.path.read_text())


class TestSplit(QaCase):
    def flat(self, *blocks: str) -> Path:
        return self.write_cases(*blocks)

    def test_split_writes_one_file_per_case_with_the_same_hash(self):
        good = self.ref("REQ-AUTH-001", "REQ-AUTH-002")
        manual = case("TC-AUTH-002", good, title="Reset: the password!").replace("Type: e2e", "Type: manual")
        path = self.flat(case("TC-AUTH-001", good, title="Sign in"), manual)
        before = {row["id"]: row["hash8"] for row in self.run_json("export")["cases"]}
        result = qa(self.root, self.bin, "split", "auth")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertFalse(path.exists())
        self.assertEqual(["TC-AUTH-001-sign-in.e2e.md", "TC-AUTH-002-reset-the-password.manual.md"],
                         sorted(item.name for item in (self.root / "qa/cases/auth").iterdir()))
        text = (self.root / "qa/cases/auth/TC-AUTH-001-sign-in.e2e.md").read_text()
        self.assertTrue(text.startswith("# TC-AUTH-001: Sign in\n"))
        self.assertNotIn("Type:", text)
        self.assertEqual([], self.findings())
        after = {row["id"]: (row["hash8"], row["type"]) for row in self.run_json("export")["cases"]}
        self.assertEqual({key: (value, kind) for (key, value), kind in zip(before.items(), ("e2e", "manual"))}, after)
        self.assertIn("TC-AUTH-003", qa(self.root, self.bin, "next-id", "auth").stdout)

    def test_refusals_write_nothing(self):
        good = self.ref("REQ-AUTH-001", "REQ-AUTH-002")
        cases = (
            (case("TC-AUTH-001", good).replace("Type: e2e\n", ""), "TC-AUTH-001: needs a Type: matching"),
            (case("TC-AUTH-001", good).replace("Type: e2e", "Type: Web UI"), "TC-AUTH-001: needs a Type: matching"),
            ("Intro prose.\n\n" + case("TC-AUTH-001", good), "holds text outside its title and case blocks"),
            (case("TC-AUTH-001", good) + "\n## Notes\n- later\n", "holds text outside its title and case blocks"),
        )
        for block, message in cases:
            with self.subTest(message=message):
                path = self.flat(block)
                before = path.read_text()
                result = qa(self.root, self.bin, "split", "auth")
                self.assertEqual(1, result.returncode)
                self.assertIn(message, result.stdout)
                self.assertEqual(before, path.read_text())
                self.assertFalse((self.root / "qa/cases/auth").exists())
        path = self.flat(case("TC-AUTH-001", good))
        write(self.root, "qa/cases/auth/TC-AUTH-001-case.e2e.md", "x\n")
        result = qa(self.root, self.bin, "split", "auth")
        self.assertEqual(1, result.returncode)
        self.assertIn("qa/cases/auth/TC-AUTH-001-case.e2e.md: already exists", result.stdout)
        self.assertTrue(path.exists())
        self.assertEqual(2, qa(self.root, self.bin, "split", "billing").returncode)
```

In `TestPlanAndCheck`, add:

```python
    def test_pin_keeps_the_bold_form(self):
        path = write(self.root, "qa/cases/auth/TC-AUTH-001.e2e.md",
                     case_file("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000, REQ-AUTH-002@00000000"))
        self.assertEqual(0, qa(self.root, self.bin, "pin", "TC-AUTH-001").returncode)
        first = path.read_text().splitlines()[2]
        self.assertEqual(f"- **REQ:** REQ-AUTH-001@{hash8(self.root, self.bin, 'REQ-AUTH-001')}, "
                         f"REQ-AUTH-002@{hash8(self.root, self.bin, 'REQ-AUTH-002')}", first)
```

Run: `python3 -m pytest tests/gin_qa/test_cases_cli.py -q` → the new tests fail.

#### Step 2.2: Lock, atomic write, `record_result`

Add to `cases.py` (imports: `from contextlib import contextmanager`, `import os`, `import time`):

```python
@contextmanager
def _lock(folder: Path, timeout: float = 10.0):
    """One gin-qa writer at a time per cases folder; a crashed writer leaves the file, named in the error."""
    path = folder / ".gin-qa.lock"
    deadline = time.monotonic() + timeout
    while True:
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except (FileExistsError, PermissionError):
            if time.monotonic() > deadline:
                raise ValueError(f"{path}: held for {timeout:.0f}s; delete it if no gin-qa is running") from None
            time.sleep(0.02)
    try:
        yield
    finally:
        os.close(handle)
        os.unlink(path)


def write_atomic(path: Path, text: str) -> None:
    """Readers in other processes see the old or the new file, never half of one."""
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    for attempt in range(40):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:  # ponytail: Windows refuses a replace while a reader has the file open; retry 2s
            if attempt == 39:
                raise
            time.sleep(0.05)


def _with_result(text: str, case: Case, values: list[tuple[str, str | None]]) -> str:
    lines = text.split("\n")
    own = {case.field_lines[key] for key in RESULT_FIELDS if key in case.field_lines}
    others = [number for key, number in case.field_lines.items() if key not in RESULT_FIELDS]
    anchor = max(others) if others else (min(own) - 1 if own else case.line)
    like = lines[max(others) - 1] if others else (lines[min(own) - 1] if own else "")
    new = [field_line(like, key, value) for key, value in values if value is not None]
    anchor -= sum(1 for number in own if number <= anchor)
    kept = [line for number, line in enumerate(lines, 1) if number not in own]
    return "\n".join(kept[:anchor] + new + kept[anchor:])


def record_result(root: Path, cases_dir: str, case_id: str, status: str, run: str | None = None,
                  bug: str | None = None) -> dict[str, str]:
    """The only writer of Result/Run/Bug: Run is replaced (dropped when None); Bug changes only when given."""
    if status not in RESULTS:
        raise ValueError(f"status is one of {', '.join(RESULTS)}; got {status!r}")
    for value in (run, bug):
        if value is not None and (not value.strip() or any(ord(char) < 32 for char in value)):
            raise ValueError(f"{value!r}: values are one non-empty line")
    cases, _ = load(root, cases_dir)
    located = next((case for case in cases if case.id == case_id), None)
    if located is None:
        raise ValueError(f"{case_id}: no such test case")
    path = root / located.path
    with _lock(root / cases_dir):
        found, errors = parse_path(root, cases_dir, path)
        case = next((item for item in found if item.id == case_id), None)
        problems = [error for error in errors if re.search(rf"\b{re.escape(case_id)}\b", error)]
        if case is None or problems:
            raise ValueError("; ".join(problems) or f"{case_id}: no longer in {located.path}")
        kept_bug = case.fields.get("Bug") if bug is None else (None if bug == "none" else bug)
        values = [("Result", status), ("Run", run), ("Bug", kept_bug)]
        write_atomic(path, _with_result(path.read_text(encoding="utf-8"), case, values))
    return {"tc": case_id, "result": status, "run": run or "", "bug": kept_bug or "", "file": str(located.path)}
```

The test `test_bad_input_exits_2_and_writes_nothing` breaks the steps (`- Open /login` under Steps) so `parse_path` reports `TC-AUTH-001: steps must be numbered…`; `record_result` raises before writing.

#### Step 2.3: `split`

```python
def _slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if len(slug) > 40:
        slug = slug[:41].rsplit("-", 1)[0] if "-" in slug[:41] else slug[:40]
    return f"-{slug}" if slug else ""


def split(root: Path, cases_dir: str, cap: str) -> tuple[list[str], list[str]]:
    """`<cases>/<cap>.md` → one `<cases>/<cap>/<TC-ID>-<slug>.<type>.md` per case; nothing is written on findings."""
    base = root / cases_dir
    path = base / f"{cap}.md"
    shown = f"{cases_dir}/{cap}.md"
    if not path.is_file():
        raise ValueError(f"{shown}: no such file")
    found, errors = parse_file(path, shown)
    lines = path.read_text(encoding="utf-8").split("\n")
    first = next((index for index, line in enumerate(lines) if line.startswith("### ")), len(lines))
    head = [line for line in lines[:first] if line.strip()]
    if head[1:] or (head and not head[0].startswith("# ")) or any(line.startswith("## ") for line in lines):
        errors.append(f"{shown}: holds text outside its title and case blocks; move it before splitting")
    targets: dict[str, Path] = {}
    for case in found:
        kind = case.fields.get("Type", "").strip().lower()
        if not TYPE.match(kind):
            errors.append(f"{shown}:{case.line}: {case.id}: needs a Type: matching [a-z][a-z0-9-]* to split")
        if case.cap != cap or case.id in targets:
            errors.append(f"{shown}:{case.line}: {case.id}: not a unique {cap} case")
        target = base / cap / f"{case.id}{_slug(case.title)}.{kind}.md"
        if target.exists():
            errors.append(f"{target.relative_to(root).as_posix()}: already exists")
        targets[case.id] = target
    if errors:
        return [], errors
    starts = [case.line - 1 for case in found] + [len(lines)]
    for case, start, end in zip(found, starts, starts[1:]):
        block = lines[start:end]
        block[0] = "# " + block[0][len("### "):]
        del block[case.field_lines["Type"] - 1 - start]
        targets[case.id].parent.mkdir(parents=True, exist_ok=True)
        targets[case.id].write_text("\n".join(block).rstrip("\n") + "\n", encoding="utf-8")
    path.unlink()
    return [target.relative_to(root).as_posix() for target in targets.values()], []
```

`starts` uses the order of `found`, which follows the file; the refusal of `## ` lines guarantees each block ends at the next case or the end of file.

#### Step 2.4: CLI

In `_parser()` add:

```python
    item = sub.add_parser("result", parents=[common])
    item.add_argument("id")
    item.add_argument("status")
    item.add_argument("--run")
    item.add_argument("--bug")
    sub.add_parser("split", parents=[common]).add_argument("capability")
```

In `_run`, after the `pin` branch:

```python
    if args.command == "result":
        row = tc.record_result(root, eff.cases_dir, args.id, args.status, args.run, args.bug)
        _emit(row, args.format, f"{row['tc']} {row['result']}")
        return 0
    if args.command == "split":
        written, errors = tc.split(root, eff.cases_dir, args.capability)
        if errors:
            return _findings(errors, args.format, "")
        _emit({"written": written}, args.format, "\n".join(written))
        return 0
```

`_pin`: store the new value instead of a whole line: `edits.setdefault(root / case.path, {})[case.field_lines["REQ"]] = value` with `value = ", ".join(...)`; when writing, `text[number - 1] = tc.field_line(text[number - 1], "REQ", value)`, and write with `tc.write_atomic(path, "\n".join(text))`.

Usage line: `"usage: gin-qa cases {plan,next-id,pin,result,split,check,export} ...\n"`.

Run: `python3 -m pytest tests/gin_qa -q` → all pass.

#### Step 2.5: Commit

`git add -A plugins/gin-qa/src/scripts tests/gin_qa && git commit -m "feat(gin-qa): cases result and cases split"`.

### Track 3: `e2e run` records results
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-qa/src/scripts/gin_qa/e2e.py:207-236` (`run` records each case; new `_outcome`, `_record`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:200-203` (`recorded` in the output)
  - Test `tests/gin_qa/test_e2e_cli.py` (new methods in `TestRunAndEvidence`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change at the end of one function with a clear spec; the writer and its concurrency handling come from Track 2.
- **Acceptance criteria**: spec US-5; R9 as written; every test in Steps passes, including the existing concurrent-runs test.
- **Estimated complexity**: low

Interfaces produced:
- `e2e.run(root, eff, targets) -> tuple[str, int, list[str], list[dict[str, str]]]` — adds `recorded` rows `{"tc", "result"}`.
- CLI `gin-qa e2e run` JSON gains `recorded`; text output adds one `<TC-ID> <result>` line per recorded case before `run: <folder>`.

Interfaces consumed: `cases.record_result` (Track 2); `HEADER`, `_result`, `_result_folders`, `_contained` (`e2e.py`).

#### Step 3.1: Failing tests

In `TestRunAndEvidence` (`tests/gin_qa/test_e2e_cli.py`), add:

```python
    def case_lines(self) -> str:
        return self.cases.read_text().split("### TC-AUTH-002")[0]

    def test_run_records_the_result_and_run_folder(self):
        payload = json.loads(self.run_e2e().stdout)
        self.assertEqual([{"tc": "TC-AUTH-001", "result": "passed"}], payload["recorded"])
        self.assertIn(f"Priority: high\nResult: passed\nRun: {payload['run']}\n", self.case_lines())
        self.assertEqual(0, self.e2e("check", "--run", payload["run"]).returncode)

    def test_worst_result_over_projects_and_missing_results(self):
        (self.root / ".fake-skip").write_text("TC-AUTH-001")
        payload = json.loads(self.run_e2e().stdout)
        self.assertEqual([{"tc": "TC-AUTH-001", "result": "blocked"}], payload["recorded"])
        (self.root / ".fake-skip").unlink()
        folder = json.loads(self.run_e2e().stdout)["run"]
        case_dir = self.root / folder / "tc-auth-001"
        data = json.loads((case_dir / "result.json").read_text())
        for project, status in (("chromium", "passed"), ("mobile", "failed")):
            (case_dir / project).mkdir()
            (case_dir / project / "result.json").write_text(json.dumps({**data, "status": status}))
        for name in ("result.json", "01.png", "01.aria.yml"):
            (case_dir / name).unlink()
        from gin_qa import e2e as e2e_module
        self.assertEqual("failed", e2e_module._outcome(self.root / folder, "TC-AUTH-001"))
```

Run: `python3 -m pytest tests/gin_qa/test_e2e_cli.py -q` → the two new tests fail.

#### Step 3.2: Implementation

In `e2e.py`:

```python
def _outcome(run_dir: Path, case_id: str) -> str:
    """The worst status over the case's result folders: failed, then blocked (no valid result.json), then passed."""
    statuses = [((_result(folder / "result.json")[0] or {}).get("status", "blocked")
                 if _contained(run_dir, folder) else "blocked")
                for folder in _result_folders(run_dir / case_id.lower())]
    return next((worst for worst in ("failed", "blocked") if worst in statuses), "passed" if statuses else "blocked")


def _record(root: Path, eff: Effective, folder: str, specs: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    recorded: list[dict[str, str]] = []
    errors: list[str] = []
    for spec in specs:
        match = HEADER.match((root / spec).read_text(encoding="utf-8").split("\n", 1)[0]) \
            if (root / spec).is_file() else None
        if match is None:
            continue  # check_run reports the missing header
        case_id, status = match.group(1), _outcome(root / folder, match.group(1))
        try:
            tc.record_result(root, eff.cases_dir, case_id, status, run=folder)
        except ValueError as error:
            errors.append(f"{case_id}: result not recorded: {error}")
            continue
        recorded.append({"tc": case_id, "result": status})
    return recorded, errors
```

In `run`, replace the final `return` with:

```python
    findings = check_run(root, eff, folder)
    recorded, problems = _record(root, eff, folder, specs)
    return folder, result.returncode, findings + problems, recorded
```

and update its docstring to `Returns (folder, Playwright exit, findings, recorded results).`

In `cli.py`, the `run` branch:

```python
    folder, code, errors, recorded = e2e.run(root, eff, args.targets)
    _emit({"run": folder, "playwright_exit": code, "findings": errors, "recorded": recorded}, args.format,
          "\n".join([*errors, *(f"{row['tc']} {row['result']}" for row in recorded), f"run: {folder}"]))
```

Run: `python3 -m pytest tests/gin_qa -q` → all pass (run it three times to watch the concurrent-runs test: `for i in 1 2 3; do python3 -m pytest tests/gin_qa/test_e2e_cli.py -q -k concurrent || break; done`).

#### Step 3.3: Commit

`git add -A plugins/gin-qa/src/scripts tests/gin_qa && git commit -m "feat(gin-qa): e2e run records each case's result"`.

### Track 4: Templates, skills, docs, version
- **Dependencies**: Track 3
- **Files**:
  - Modify `plugins/gin-qa/src/templates/cases.md` (one per-case file in the R2 form)
  - Create `plugins/gin-qa/src/templates/qa-readme.md`
  - Modify `plugins/gin-qa/src/templates/guidelines.md` (type and test data lines)
  - Modify `plugins/gin-qa/src/skills/cases/SKILL.md` (layout, format, Test data, split, result, README)
  - Modify `plugins/gin-qa/src/skills/e2e/SKILL.md` (step 5, step 7 recording)
  - Modify `plugins/gin-qa/src/skills/e2e/references/explore-case.md` (Test data)
  - Modify `docs/guides/qa.md`, `docs/guides/customizing-templates.md`, `docs/reference/cli.md`
  - Modify `plugins/gin-qa/plugin.meta.json`, `plugins/gin-qa/src/.claude-plugin/plugin.json`, `plugins/gin-qa/src/.codex-plugin/plugin.json` (`0.7.0`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:15` (`VERSION = "0.6"`)
  - Modify `tests/install_smoke_test.sh:190` and `tests/install_smoke_test.ps1` (launcher version `0.6`; assert `templates/qa-readme.md` is installed next to `cases.md`)
  - Test `tests/gin_qa/test_packaging.py:36` (cases skill links include `../../templates/qa-readme.md`)
- **Provider role**: `docs`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** documentation and template edits that follow the spec text; the version bump is mechanical.
- **Acceptance criteria**: R10 as written; `python3 -m pytest -n auto` and `bash tests/install_smoke_test.sh` pass; every command and file name in the docs matches Tracks 1–3.
- **Estimated complexity**: low

Interfaces consumed: the CLI commands and messages of Tracks 1–3; spec R2 (format), R7, R8, R9.

#### Step 4.1: Tests first

In `tests/gin_qa/test_packaging.py:36`, the `cases` entry becomes `["../../templates/guidelines.md", "../../templates/qa-readme.md", "../../templates/cases.md"]` (the order the links appear in the skill, Step 4.3). In `tests/install_smoke_test.sh`, change `would install gin-qa launcher version 0.5` to `0.6`, and next to the existing gin-qa template assertions add the installed `templates/qa-readme.md` (same directory and assertion style as the `cases.md` template line). Make the same version change in `tests/install_smoke_test.ps1` (Windows only; not runnable here). Run `python3 -m pytest tests/gin_qa/test_packaging.py -q` → fails.

#### Step 4.2: Templates and version

`templates/cases.md` becomes exactly the R2 example of the spec, without the `Result` and `Run` lines and with `Expected` unchanged (`- The dashboard is shown`), preceded by one HTML comment line: `<!-- One case per file: <cases>/<capability>/TC-<CAP>-NNN-<slug>.<type>.md; the type is the name's .<type>. -->`.

`templates/qa-readme.md` (new), written for testers, under 60 lines, sections:
- `# QA` — what lives here: `cases/`, `e2e/`, `evidence/` (git-ignored run folders), `guidelines.md`.
- `## Case files` — the naming rule `TC-<CAP>-NNN[-<slug>].<type>.md`, one case per file, `gin-qa cases next-id <capability>` for IDs.
- `## Case format` — fields (`REQ`, `Priority`, extra fields from the guidelines, `Result`, `Run`, `Bug`), sections (`Preconditions`, `Test data`, `Steps`, `Expected`), the credentials rule.
- `## Results` — the four values; `gin-qa cases result <TC-ID> <status> [--run <ref>] [--bug <id>|none]` is the only way to change them; `gin-qa e2e run` records automated results.
- `## Commands` — `next-id`, `check`, `result`, `split`, `export`, `e2e run`, one line each.

`templates/guidelines.md`: replace `` - `Type: e2e` for cases a browser test can run, `manual` otherwise.`` with `` - Type is the file suffix: `.e2e.md` for cases a browser test can run, `.manual.md` otherwise; add the types this team uses.``; replace the e2e `Test data:` line with `` - Test data: none yet (shared users and records specs may rely on; data one case needs goes in its `Test data` section).``

Versions: `0.6.0` → `0.7.0` in the three manifests; `VERSION = "0.6"` in `cli.py`.

#### Step 4.3: Skills

`skills/cases/SKILL.md`:
- Description (frontmatter): `Write or update test cases from gin-workflow specs — one file per case in qa/cases/<capability>/, traced to REQ-IDs, checked by the gin-qa CLI.`
- Step 3: also create `README.md` next to the guidelines file from [qa-readme.md](../../templates/qa-readme.md) when it does not exist.
- Step 4 (Format): one file per case, `<cases>/<capability>/<TC-ID>-<slug>.<type>.md` (slug from the title, lower-case words joined by `-`; type from the guidelines); heading `# TC-<CAP>-NNN: <title>`; fields as `- **Key:** value` (`REQ`, `Priority`, extra fields; no `Type`); sections `**Preconditions:**` (optional), `**Test data:**` (optional), `**Steps:**`, `**Expected:**`. Link [cases.md](../../templates/cases.md).
- New rule after step 5: write `Test data` when a case needs specific records or values: a literal value or a rule for producing it; name credentials only by environment variable, never their values.
- New rule: an existing flat `<cases>/<capability>.md` is moved with `split <capability>` before adding cases; on refusal, show the findings to the user.
- New rule: never edit `Result`, `Run`, or `Bug` lines by hand; `result <TC-ID> <status> [--run <ref>] [--bug <id>|none]` writes them.
- The legacy-layout paragraph and the export sentence stay; the export sentence adds `result`, `run`, `bug`, `test_data`.

`skills/e2e/SKILL.md`:
- Step 5: only these cases' spec files, and the `Result`/`Run` lines of their case files, may have changed.
- Step 7: after the official `run`, its results are recorded in the case files; report them with the run folder.

`skills/e2e/references/explore-case.md`, after the `Preconditions` sentence: `Test data` items are built before the first step, in the spec or a fixture the guidelines name; a rule ("a unique email per run") becomes code that produces the value, a credential is read from the environment variable the item names.

Keep each SKILL.md under 6,000 characters (`test_packaging.py`).

#### Step 4.4: Docs

- `docs/guides/qa.md`: the case layout, the format with a short example, `Test data`, results (`cases result`, recording by `e2e run`), and `split` for existing flat files.
- `docs/guides/customizing-templates.md:105-160`: the example case uses the per-case file and bold form; type comes from the file name; custom fields stay `- **Key:** value` lines exported under `fields`; `Result`, `Run`, `Bug` are reserved.
- `docs/reference/cli.md`: `gin-qa cases result` and `gin-qa cases split` (arguments, exit codes 0/1/2, output), the `recorded` key of `gin-qa e2e run`, and the new export keys.

Run: `python3 -m pytest -n auto` and `bash tests/install_smoke_test.sh` → pass.

#### Step 4.5: Commit

`git add -A plugins/gin-qa docs tests && git commit -m "docs(gin-qa): per-case files, results, split; gin-qa 0.7.0"`.

## Integration
- **Branch**: `feat/qa-case-folders`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes
- [ ] `bash tests/install_smoke_test.sh` passes
- [ ] `GIN_QA_PLAYWRIGHT_NODE_MODULES=$HOME/gin-fam/gin-console/node_modules python3 -m pytest tests/gin_qa/test_e2e_playwright.py` passes (real Playwright still records and checks)
- [ ] Manual: copy gin-console's `qa/cases/milestone-ui.md` into a scratch SDD repository, run `gin-qa cases export --format json > before.json`, `gin-qa cases split milestone-ui`, `gin-qa cases export --format json > after.json`; every case keeps its `hash8` and gets type `e2e` or `api`; `gin-qa cases check` reports no new finding.

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog (`haiku`, `sonnet`, `opus`; `low` … `max`) using the route rubric.
- The user may override `Model:` and `Effort:` before plan approval.
- Deliverable merge-holds apply only to the Parent Bead (`gin-workflow-qa-case-folders`); track beads close after tests and review pass.
- `tests/install_smoke_test.ps1` runs only on Windows; Track 4 edits it but cannot run it here.
- Lost updates: concurrent `record_result` calls are serialized by the lock, so two runs recording the same case end with the later run's result.

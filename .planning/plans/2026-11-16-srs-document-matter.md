# Plan: SRS document matter: revision history, sign-off, glossary, actors, traceability

Epic: gin-workflow-414v
Workflow: gin-workflow-414v
Spec: `.planning/specs/2026-11-16-srs-document-matter-design.md`

## Objective

`gin specs export` writes an SRS that opens with a revision history (from archived changes), a sign-off page, a glossary (confirmed terms), and an actor catalogue (from use cases, with optional descriptions), ends with a traceability matrix (REQ to use cases, test files, gin-qa cases), and shows each use case's `<cap>/<slug>` ID. `specs lint` checks `<specs>/actors.md`, and `setup doctor` accepts it.

## Global Constraints

Copied from the spec:

- Revision history is generated from the archived change folders.
- The traceability matrix lists, per requirement, its use cases, the test files that cite it (as `specs trace` finds them), and the gin-qa cases that cite it.
- The actor catalogue is generated from the use cases; an optional `<specs>/actors.md` adds a description per actor.
- A use case is cited as `<cap>/<slug>`; no generated numbers.
- The data is built in a new module `workflow_core/specs_matter.py` and rendered by `specs_export.py` through new placeholders of `srs.html`.
- Glossary: only `confirmed` rows; sign-off: a fixed blank table in `srs.html`; exporting one capability limits revisions, actors, and traceability to it.
- Out of scope: NFRs and business rules (`gin-workflow-ngiz`), diagram extensions (`gin-workflow-16jz`), offline diagrams (`gin-workflow-1w5p`), QA cases in a workspace `shape: qa` child, a matrix command or CSV, gin-qa run results, the legacy layout.
- No new dependency. `specs trace` output unchanged.

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
- Problem statement: the SRS has no document-level matter (revisions, sign-off, glossary, actors, traceability) and no citable use case IDs; a BA writes them by hand.
- Success criteria: US-1 to US-6 of the spec pass as tests; `specs trace` output unchanged; `python3 -m pytest -n auto` green, also with `bd` off PATH.
- Constraints: Global Constraints above.
- Non-goals: the out-of-scope list above.

## Approach Options
### Option 1: Data module plus rendering in `specs_export.py`
- Summary: `specs_matter.py` returns plain rows (dicts); `specs_export.py` renders them into new `srs.html` placeholders; shared helpers (`actor_key`, `table_rows`, `req_sources`) are extracted from the code that already does that work.
- Pros: matches the existing `_chapter`/`fill` pattern; data testable without HTML; one self-contained SRS file.
- Cons: `srs.html` grows; overriding projects must add placeholders to get the sections.

### Option 2: A separate `specs matrix` command
- Summary: matrix as CSV/HTML from its own command; export embeds only front matter.
- Pros: QA could reuse the matrix outside the SRS.
- Cons: a second command no one asked for (no-speculative).

### Recommended Approach
- Selected option: Option 1 (confirmed at discuss).
- Rationale: smallest surface, reuses the trace scan and the actor matching, keeps one document.

## Scope
- In scope: R1 to R8 of the spec, the `actors.md` exemption in `specs_migrate._foreign`, tests, and docs.
- Out of scope: Global Constraints' out-of-scope list.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 renders the rows Track 1 builds and Track 3 documents both; they run one after another on feat/srs-document-matter.
```

## Tasks

### Track 1: Document matter as data, shared helpers, and actors.md lint (R2, R3, R4, R5)
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/specs_matter.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py` (add `ACTORS_FILE`, `actor_key`, `table_rows`, `lint_actors`; call `lint_actors` from `lint_living` and `lint_change`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_trace.py:38-71` (extract `req_sources`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_migrate.py:110-122` (`_foreign` owns `<specs>/actors.md`)
  - Create `tests/workflow_core/test_specs_matter.py`
  - Test `tests/workflow_core/test_specs.py`, `tests/workflow_core/test_specs_migrate.py`, `tests/workflow_core/test_specs_archive_trace.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** four bounded data functions and three small helpers with exact rows and messages from the spec; the trace refactor must keep its output, which existing tests pin.
- **Interfaces produced**:
  - `specs.ACTORS_FILE = "actors.md"`
  - `specs.actor_key(name: str) -> str`: `" ".join(name.split()).casefold()`.
  - `specs.table_rows(text: str) -> tuple[list[str], list[tuple[int, dict[str, str]]]] | None`: the first Markdown table of `text` (a `|` line followed by a rule line): header cells, and each data row as (1-based line number, {header: cell}); `None` without a table.
  - `specs.lint_actors(root, cfg) -> list[str]`.
  - `specs_trace.req_sources(root, cfg, req_ids: Iterable[str]) -> tuple[dict[str, list[str]], list[str]]`: sorted test file paths citing each REQ-ID, and the skipped workspace children.
  - `specs_matter.revisions(root, cfg, cap=None) -> list[dict]`: keys `date`, `epic`, `title`, `capabilities`, `added`, `modified`, `removed` (lists sorted).
  - `specs_matter.glossary(root, cfg) -> list[dict]`: keys `english`, `term`, `lang`, `meaning`.
  - `specs_matter.actors(root, cfg, cap=None) -> list[dict]`: keys `actor`, `description`, `use_cases` (list of `{"ref": "<cap>/<slug>", "secondary": bool}`).
  - `specs_matter.traceability(root, cfg, cap=None) -> list[dict]`: keys `id`, `title`, `capability`, `use_cases`, `tests`, `qa_cases`, `status`.
- **Steps**:
  1. Create `tests/workflow_core/test_specs_matter.py` with the same import header as `tests/workflow_core/test_specs_export.py` (lines 1-19: `sys.path.insert(0, str(Path(__file__).resolve().parent))`, then `from specs_fixtures import ...  # noqa: E402`, `from workflow_core import specs, specs_matter  # noqa: E402`), and these tests:
     ```python
     GLOSSARY = """# GLOSSARY

     ## Terms

     | Term | Lang | English | Meaning | Legacy identifiers | Evidence | Status |
     |---|---|---|---|---|---|---|
     | Đơn hàng | vi | Order | A customer's purchase | don_hang | db | confirmed |
     | Giỏ | vi | Cart | Items before checkout | gio | ui | proposed |
     | Hóa đơn | vi | invoice | A bill | hoa_don | db | confirmed |

     ## Conflicts

     | Term | Lang | Existing English | Candidate | Evidence |
     |---|---|---|---|---|
     """


     class TestSpecsMatter(unittest.TestCase):
         def setUp(self):
             self.tmp = tempfile.TemporaryDirectory()
             self.root = make_repo(Path(self.tmp.name) / "r")
             write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
             self.cfg = specs.sdd_config(specs.load_config(self.root))

         def tearDown(self):
             self.tmp.cleanup()

         def test_revisions_newest_first_with_capabilities_and_reqs(self):
             archive = "docs/changes/archive"
             write(self.root, f"{archive}/2026-11-01-ep-1-lockout/01-proposal.md", "# Lock accounts\n\nEpic: ep-1\n")
             write(self.root, f"{archive}/2026-11-01-ep-1-lockout/02-spec-delta.md", delta(added=ADDED_BLOCK))
             write(self.root, f"{archive}/2026-11-03-ep-2-tech/01-proposal.md", "# Faster login\n\nEpic: ep-2\nKind: technical\n")
             write(self.root, f"{archive}/notes/readme.md", "not a change\n")
             self.assertEqual([
                 {"date": "2026-11-03", "epic": "ep-2", "title": "Faster login", "capabilities": [],
                  "added": [], "modified": [], "removed": []},
                 {"date": "2026-11-01", "epic": "ep-1", "title": "Lock accounts", "capabilities": ["auth"],
                  "added": ["REQ-AUTH-003"], "modified": [], "removed": []},
             ], specs_matter.revisions(self.root, self.cfg))
             self.assertEqual(["2026-11-01"], [row["date"] for row in specs_matter.revisions(self.root, self.cfg, "auth")])

         def test_revisions_without_archive_or_proposal(self):
             self.assertEqual([], specs_matter.revisions(self.root, self.cfg))
             write(self.root, "docs/changes/archive/2026-11-05-ep-3-misc/02-spec-delta.md", delta(added=ADDED_BLOCK))
             row = specs_matter.revisions(self.root, self.cfg)[0]
             self.assertEqual(("ep-3-misc", ""), (row["title"], row["epic"]))

         def test_glossary_keeps_confirmed_rows_sorted_by_english(self):
             self.assertEqual([], specs_matter.glossary(self.root, self.cfg))
             write(self.root, "docs/codebase/11-GLOSSARY.md", GLOSSARY)
             self.assertEqual([
                 {"english": "invoice", "term": "Hóa đơn", "lang": "vi", "meaning": "A bill"},
                 {"english": "Order", "term": "Đơn hàng", "lang": "vi", "meaning": "A customer's purchase"},
             ], specs_matter.glossary(self.root, self.cfg))

         def test_glossary_reads_columns_by_header(self):
             write(self.root, "docs/codebase/11-GLOSSARY.md",
                   "# G\n\n## Terms\n\n| Status | English | Term | Lang | Meaning |\n|---|---|---|---|---|\n"
                   "| confirmed | Invoice | Hóa đơn | vi | A bill |\n")
             self.assertEqual(["Invoice"], [row["english"] for row in specs_matter.glossary(self.root, self.cfg)])

         def test_actors_merge_spellings_mark_secondary_and_take_descriptions(self):
             write(self.root, "docs/specs/auth/use-cases/sign-in.md", USE_CASE.replace("Registered user", "Customer").replace(
                 "Requirements:", "Secondary actors: Mail service\nRequirements:"))
             write(self.root, "docs/specs/auth/use-cases/sign-out.md", USE_CASE.replace("Registered user", "customer"))
             write(self.root, "docs/specs/billing/spec.md", "# Billing\n\n## Purpose\n\nInvoices.\n\n## Requirements\n")
             write(self.root, "docs/specs/billing/use-cases/pay.md", USE_CASE.replace("Registered user", "Accountant"))
             write(self.root, "docs/specs/actors.md", "| Actor | Description |\n|---|---|\n| CUSTOMER | Buys things |\n")
             self.assertEqual([
                 {"actor": "Accountant", "description": "", "use_cases": [{"ref": "billing/pay", "secondary": False}]},
                 {"actor": "Customer", "description": "Buys things",
                  "use_cases": [{"ref": "auth/sign-in", "secondary": False}, {"ref": "auth/sign-out", "secondary": False}]},
                 {"actor": "Mail service", "description": "", "use_cases": [{"ref": "auth/sign-in", "secondary": True}]},
             ], specs_matter.actors(self.root, self.cfg))
             self.assertEqual(["Customer", "Mail service"],
                              [row["actor"] for row in specs_matter.actors(self.root, self.cfg, "auth")])

         def test_traceability_rows_link_use_cases_tests_and_qa_cases(self):
             write(self.root, "docs/specs/auth/use-cases/sign-in.md", USE_CASE)
             write(self.root, "tests/test_login.py", "def test_login():  # REQ-AUTH-001\n    pass\n")
             write(self.root, "qa/cases/auth/TC-AUTH-001-login.md", "# Login\n\nREQ: REQ-AUTH-001\n")
             commit_all(self.root)
             self.assertEqual([
                 {"id": "REQ-AUTH-001", "title": "Sign in with password", "capability": "auth",
                  "use_cases": ["auth/sign-in"], "tests": ["tests/test_login.py"], "qa_cases": ["TC-AUTH-001"],
                  "status": "covered"},
                 {"id": "REQ-AUTH-002", "title": "Reject wrong password", "capability": "auth",
                  "use_cases": ["auth/sign-in"], "tests": [], "qa_cases": [], "status": "missing"},
             ], specs_matter.traceability(self.root, self.cfg))

         def test_traceability_reads_configured_qa_cases_and_filters_by_capability(self):
             root = make_repo(Path(self.tmp.name) / "q", extra="qa:\n  cases: spec-cases\n")
             write(root, "docs/specs/auth/spec.md", AUTH_SPEC)
             write(root, "spec-cases/TC-AUTH-002-wrong.md", "Covers REQ-AUTH-002.\n")
             cfg = specs.sdd_config(specs.load_config(root))
             self.assertEqual(["TC-AUTH-002"], specs_matter.traceability(root, cfg, "auth")[1]["qa_cases"])
             self.assertEqual([], specs_matter.traceability(root, cfg, "billing"))
     ```
     Import from `specs_fixtures`: `ADDED_BLOCK, AUTH_SPEC, USE_CASE, commit_all, delta, make_repo, write`.
     In `tests/workflow_core/test_specs.py` (`TestRepositoryCommands`), add:
     ```python
     def test_lint_actors_file(self):
         self.assertEqual([], specs.lint_actors(self.root, self.cfg))
         write(self.root, "docs/specs/auth/use-cases/sign-in.md", USE_CASE)
         write(self.root, "docs/specs/actors.md",
               "# Actors\n\n| Actor | Description |\n|---|---|\n| registered USER | Has an account |\n| Auditor | Reads logs |\n")
         self.assertEqual(["docs/specs/actors.md:6: actor 'Auditor' is in no use case"],
                          specs.lint_actors(self.root, self.cfg))
         self.assertEqual(1, run_specs(self.root, "lint").returncode)
         write(self.root, "docs/specs/actors.md", "# Actors\n\nCustomer: buys.\n")
         self.assertEqual(["docs/specs/actors.md: needs a table with Actor and Description columns"],
                          specs.lint_actors(self.root, self.cfg))
     ```
     In `tests/workflow_core/test_specs_migrate.py`, in the test that writes `.gitkeep`/`.DS_Store` and then the `foreign` list (around line 128), also write `docs/specs/actors.md` before the `foreign` files and keep the `foreign` assertion unchanged (so `actors.md` must not be reported). Also write `docs/specs/auth/actors.md` and add `"auth/actors.md"` to the `foreign` list in sorted position (only the top-level file is owned).
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_specs_matter.py tests/workflow_core/test_specs.py tests/workflow_core/test_specs_migrate.py -q`: the new tests fail (`ImportError` for `specs_matter`, `AttributeError` for `lint_actors`, `actors.md` reported).
  3. In `specs.py`, next to `CAPABILITY_FOLDERS`, add `ACTORS_FILE = "actors.md"`, and next to `line_values` add:
     ```python
     _TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


     def actor_key(name: str) -> str:
         """An actor name without regard to case or repeated spaces: the key use case diagrams and catalogues share."""
         return " ".join(name.split()).casefold()


     def _cells(line: str) -> list[str]:
         return [cell.strip() for cell in line.strip().strip("|").split("|")]


     def table_rows(text: str) -> tuple[list[str], list[tuple[int, dict[str, str]]]] | None:
         """The first Markdown table of `text`: its header cells and each row as (line number, {header: cell})."""
         lines = text.split("\n")
         for index, line in enumerate(lines[:-1]):
             if line.lstrip().startswith("|") and _TABLE_RULE.match(lines[index + 1]):
                 header = _cells(line)
                 rows = []
                 for number in range(index + 2, len(lines)):
                     if not lines[number].lstrip().startswith("|"):
                         break
                     cells = _cells(lines[number])
                     rows.append((number + 1, dict(zip(header, cells + [""] * (len(header) - len(cells))))))
                 return header, rows
         return None


     def lint_actors(root: Path, cfg: Mapping[str, Any]) -> list[str]:
         """`<specs>/actors.md`, when present, is a table with Actor and Description columns naming only actors of use cases."""
         base = specs_dir(root, cfg)
         path = base / ACTORS_FILE
         if not path.is_file():
             return []
         table = table_rows(path.read_text(encoding="utf-8"))
         if table is None or not {"Actor", "Description"} <= set(table[0]):
             return [f"{shown(root, path)}: needs a table with Actor and Description columns"]
         named = set()
         for case in base.glob(f"*/{USE_CASES_DIR}/*.md"):
             text = case.read_text(encoding="utf-8")
             named |= {actor_key(name) for name in [line_value(text, "Actor"), *line_values(text, "Secondary actors")] if name}
         return [f"{shown(root, path)}:{number}: actor '{row['Actor']}' is in no use case"
                 for number, row in table[1] if row["Actor"] and actor_key(row["Actor"]) not in named]
     ```
     Check first that `specs.py` has no `_TABLE_RULE` or `_cells` yet (`grep -n "_TABLE_RULE\|def _cells" specs.py`); if one exists, reuse it. Append `+ lint_actors(root, cfg)` to the `return` of `lint_living` and of `lint_change`.
  4. In `specs_migrate._foreign`, extend `owned` with `or parts == (specs.ACTORS_FILE,)` (import `ACTORS_FILE` the way `CAPABILITY_FOLDERS` is imported there).
  5. In `specs_trace.py`, extract the scan:
     ```python
     def req_sources(root: Path, cfg: Mapping[str, Any], req_ids: Iterable[str]) -> tuple[dict[str, list[str]], list[str]]:
         """Test files citing each REQ-ID (sorted repository paths), and the workspace children that could not be listed."""
         wanted = set(req_ids)
         sources: dict[str, list[str]] = {req: [] for req in wanted}
         candidates = list(test_files(root, cfg, _tracked(root)))
         skipped: list[str] = []
         space = load(root)
         for repo in (space.repos if space else []):
             if not repo.workable:
                 continue
             tracked = _child_tracked(space.checkout(repo)) if space.present(repo) else None
             if tracked is None:
                 skipped.append(repo.path)
                 continue
             candidates += [f"{repo.path}/{path}" for path in test_files(root, cfg, tracked)]
         for relative in candidates:
             try:
                 text = (Path(root) / relative).read_text(encoding="utf-8")
             except (OSError, UnicodeDecodeError):
                 continue
             for req in {match.group(0) for match in REQ_ID.finditer(text)} & wanted:
                 sources[req].append(relative)
         return {req: sorted(paths) for req, paths in sources.items()}, skipped
     ```
     and make `trace` call it: `sources, skipped = req_sources(root, cfg, wanted)`, keeping its `05-tests.md` loop, its `sorted(sources[req])`, and its return value as they are. Import `Iterable` from `typing`.
  6. Create `specs_matter.py`:
     ```python
     """SRS document matter as data: revision history, glossary, actor catalogue, traceability matrix."""

     from __future__ import annotations

     from pathlib import Path
     import re
     from typing import Any, Mapping

     from . import specs
     from .specs_trace import req_sources

     _DATED = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")
     _TITLE = re.compile(r"^# (\S.*)$", re.MULTILINE)
     _TERMS = re.compile(r"^## Terms[ \t]*\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
     _CASE_ID = re.compile(r"^(TC-[A-Z][A-Z0-9-]*?-\d{3,})")


     def revisions(root: Path, cfg: Mapping[str, Any], cap: str | None = None) -> list[dict[str, Any]]:
         """One row per archived change folder `<date>-<name>`, newest first; with `cap`, only changes touching it."""
         archive = specs.changes_dir(root, cfg) / "archive"
         rows = []
         for folder in sorted((p for p in archive.iterdir() if p.is_dir()), reverse=True) if archive.is_dir() else []:
             dated = _DATED.match(folder.name)
             if not dated:
                 continue
             proposal = specs.change_file(folder, "proposal")
             text = specs._COMMENT.sub("", proposal.read_text(encoding="utf-8")) if proposal.is_file() else ""
             epic, title = specs._EPIC_LINE.search(text), _TITLE.search(text)
             delta = specs.change_file(folder, "spec-delta")
             blocks = specs.parse_blocks(delta.read_text(encoding="utf-8"))[0] if delta.is_file() else []
             caps = sorted({block.cap for block in blocks})
             if cap and cap not in caps:
                 continue
             rows.append({"date": dated.group(1), "epic": epic.group(1) if epic else "",
                          "title": title.group(1).strip() if title else dated.group(2), "capabilities": caps,
                          **{section.lower(): sorted(b.id for b in blocks if b.section == section)
                             for section in specs.DELTA_SECTIONS}})
         return rows


     def glossary(root: Path, cfg: Mapping[str, Any]) -> list[dict[str, str]]:
         """The `confirmed` rows of `## Terms` in `<codebase>/11-GLOSSARY.md`, sorted by English."""
         path = Path(root) / cfg["codebase"] / "11-GLOSSARY.md"
         section = _TERMS.search(path.read_text(encoding="utf-8")) if path.is_file() else None
         table = specs.table_rows(section.group(1)) if section else None
         rows = [{"english": row.get("English", ""), "term": row.get("Term", ""), "lang": row.get("Lang", ""),
                  "meaning": row.get("Meaning", "")}
                 for _, row in (table[1] if table else []) if row.get("Status", "").lower() == "confirmed"]
         return sorted(rows, key=lambda row: row["english"].casefold())


     def actors(root: Path, cfg: Mapping[str, Any], cap: str | None = None) -> list[dict[str, Any]]:
         """Each actor of the use cases with its description from `<specs>/actors.md` and its use cases."""
         base = specs.specs_dir(root, cfg)
         found: dict[str, dict[str, Any]] = {}
         for path in sorted(base.glob(f"*/{specs.USE_CASES_DIR}/*.md")):
             owner = path.parent.parent.name
             if cap and owner != cap:
                 continue
             text = path.read_text(encoding="utf-8")
             primary = specs.line_value(text, "Actor")
             names = ([(primary, False)] if primary else []) + [(n, True) for n in specs.line_values(text, "Secondary actors")]
             for name, secondary in names:
                 row = found.setdefault(specs.actor_key(name),
                                        {"actor": " ".join(name.split()), "description": "", "use_cases": []})
                 row["use_cases"].append({"ref": f"{owner}/{path.stem}", "secondary": secondary})
         listed = base / specs.ACTORS_FILE
         table = specs.table_rows(listed.read_text(encoding="utf-8")) if listed.is_file() else None
         for _, row in (table[1] if table else []):
             if row.get("Actor") and specs.actor_key(row["Actor"]) in found:
                 found[specs.actor_key(row["Actor"])]["description"] = row.get("Description", "")
         return sorted(found.values(), key=lambda row: row["actor"].casefold())


     def qa_cases_dir(root: Path) -> Path:
         """`qa.cases` when set, else `<qa.dir or qa>/cases`, under the project root."""
         qa = specs.load_config(root).get("qa") or {}
         return Path(root) / (qa["cases"] if "cases" in qa else f"{qa.get('dir', 'qa')}/cases")


     def traceability(root: Path, cfg: Mapping[str, Any], cap: str | None = None) -> list[dict[str, Any]]:
         """One row per living requirement: its use cases, the test files and QA cases citing it, and coverage."""
         blocks = sorted((block for _, block in specs.living_blocks(root, cfg).values() if cap is None or block.cap == cap),
                         key=lambda block: (block.cap, block.id))
         ids = {block.id for block in blocks}
         use_cases: dict[str, list[str]] = {req: [] for req in ids}
         for path in sorted(specs.specs_dir(root, cfg).glob(f"*/{specs.USE_CASES_DIR}/*.md")):
             for req in set(specs.line_values(path.read_text(encoding="utf-8"), "Requirements")) & ids:
                 use_cases[req].append(f"{path.parent.parent.name}/{path.stem}")
         tests = req_sources(root, cfg, ids)[0]
         qa: dict[str, list[str]] = {req: [] for req in ids}
         folder = qa_cases_dir(root)
         for path in sorted(folder.rglob("*.md")) if folder.is_dir() else []:
             case = _CASE_ID.match(path.name)
             try:
                 text = path.read_text(encoding="utf-8")
             except (OSError, UnicodeDecodeError):
                 continue
             for req in ({match.group(0) for match in specs.REQ_ID.finditer(text)} & ids) if case else ():
                 qa[req].append(case.group(1))
         return [{"id": block.id, "title": block.title, "capability": block.cap, "use_cases": use_cases[block.id],
                  "tests": tests[block.id], "qa_cases": sorted(set(qa[block.id])),
                  "status": "covered" if tests[block.id] or qa[block.id] else "missing"} for block in blocks]
     ```
     `Requirements:` values are REQ-IDs separated by commas, so `line_values` returns them; a value with extra text is matched only when it equals a REQ-ID (the template has only IDs there).
  7. Run `timeout 300 python3 -m pytest tests/workflow_core/test_specs_matter.py tests/workflow_core/test_specs.py tests/workflow_core/test_specs_migrate.py tests/workflow_core/test_specs_archive_trace.py -q`: passes (trace tests unchanged and green).
  8. Commit: `feat(specs): SRS document matter as data (revisions, glossary, actors, traceability), actors.md lint, and a shared REQ test scan (gin-workflow-414v.1)`.
- **Acceptance criteria**: the data criteria of US-1, US-3, US-4, US-5 pass as tests; `specs lint` reports `actors.md` problems with file and line; `setup doctor` does not report `<specs>/actors.md`; `specs trace` tests pass unchanged.
- **Estimated complexity**: medium

### Track 2: Render the document matter and use case IDs in the SRS (R1, R6, R7)
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/templates/srs.html` (comment, CSS, new sections)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_export.py:216-330` (`use_case_diagram` uses `specs.actor_key`; `_chapter` adds use case IDs; render helpers; `export` fills the new placeholders and TOC entries)
  - Test `tests/workflow_core/test_specs_export.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** rendering rows into escaped HTML tables in one module with fixed placeholders; the TOC order and anchors are the subtle part.
- **Interfaces consumed**: `specs_matter.revisions`, `glossary`, `actors`, `traceability`; `specs.actor_key`.
- **Steps**:
  1. Write failing tests in `TestExport` of `tests/workflow_core/test_specs_export.py`:
     ```python
     def test_document_matter_sections_in_order_with_toc(self):
         write(self.root, "docs/changes/archive/2026-11-01-ep-1-x/01-proposal.md", "# Lock accounts\n\nEpic: ep-1\n")
         write(self.root, "docs/codebase/11-GLOSSARY.md",
               "# G\n\n## Terms\n\n| Term | Lang | English | Meaning | Status |\n|---|---|---|---|---|\n"
               "| Đơn hàng | vi | Order | A purchase | confirmed |\n")
         self.assertEqual(0, run_specs(self.root, "export", "--all").returncode)
         html = self.read("srs.html")
         order = [html.index(f'id="{anchor}"') for anchor in ("revisions", "signoff", "glossary", "actors", "auth", "traceability")]
         self.assertEqual(sorted(order), order)
         self.assertLess(html.index('id="signoff"'), html.index('<nav class="toc">'))
         for anchor in ("revisions", "signoff", "glossary", "actors", "traceability"):
             with self.subTest(anchor=anchor):
                 self.assertIn(f'<a href="#{anchor}">', html)
         self.assertIn("<td>Lock accounts</td>", html)
         self.assertIn("<td>Đơn hàng (vi)</td>", html)
         for row in ("Prepared by", "Reviewed by", "Approved by"):
             self.assertIn(f"<th>{row}</th>", html)

     def test_use_case_ids_and_links(self):
         self.assertEqual(0, run_specs(self.root, "export", "auth").returncode)
         html = self.read("srs-auth.html")
         self.assertIn('<p class="use-case-id">auth/sign-in</p>', html)
         self.assertLess(html.index("<h3>Sign in</h3>"), html.index('<p class="use-case-id">auth/sign-in</p>'))
         self.assertIn('<a href="#auth-sign-in">auth/sign-in</a>', html[html.index('id="actors"'):])
         self.assertIn('<a href="#auth-sign-in">auth/sign-in</a>', html[html.index('id="traceability"'):])
         self.assertIn("<td>missing</td>", html)

     def test_empty_sources_print_none_lines(self):
         self.assertEqual(0, run_specs(self.root, "export", "billing").returncode)
         html = self.read("srs-billing.html")
         for line in ("No revisions yet.", "No glossary.", "No actors."):
             with self.subTest(line=line):
                 self.assertIn(line, html)

     def test_template_without_matter_placeholders_exports_as_before(self):
         document = specs.template_text(self.root, "srs.html")
         for name in ("revisions", "glossary", "actors", "traceability"):
             document = document.replace("{{" + name + "}}", "")
         write(self.root, ".agent-workflow/templates/srs.html", document)
         self.assertEqual(0, run_specs(self.root, "export", "auth").returncode)
         self.assertNotIn("No revisions yet.", self.read("srs-auth.html"))
     ```
     In `TestTemplates.test_srs_templates_print_their_placeholders` (around line 329), add `"{{revisions}}", "{{glossary}}", "{{actors}}", "{{traceability}}"` to the needles. Keep `test_use_case_diagram_shows_actors_use_cases_and_relations` passing unchanged.
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_specs_export.py -q`: the new tests fail.
  3. `templates/srs.html`:
     - The comment's placeholder list becomes: title, date, revisions, toc, glossary, actors, chapters, traceability; add one sentence: "The sign-off table is plain HTML below; edit, move, or delete it in your override." Write no `--` inside the comment.
     - CSS: `.signoff td { height: 2.5rem; min-width: 8rem; }` and, in `@media print`, `.signoff { break-after: page; }`.
     - Body, replacing the part from `<section class="cover">` through `{{chapters}}`:
       ```html
       <section class="cover">
         <h1>{{title}}</h1>
         <p class="subtitle">Software Requirements Specification</p>
         <p class="date">{{date}}</p>
       </section>
       <section class="revisions" id="revisions">
         <h2>Revision history</h2>
         {{revisions}}
       </section>
       <section class="signoff" id="signoff">
         <h2>Sign-off</h2>
         <table>
           <thead><tr><th></th><th>Name</th><th>Role</th><th>Signature</th><th>Date</th></tr></thead>
           <tbody>
             <tr><th>Prepared by</th><td></td><td></td><td></td><td></td></tr>
             <tr><th>Reviewed by</th><td></td><td></td><td></td><td></td></tr>
             <tr><th>Approved by</th><td></td><td></td><td></td><td></td></tr>
           </tbody>
         </table>
       </section>
       <nav class="toc">
         <h2>Contents</h2>
         {{toc}}
       </nav>
       <section class="glossary" id="glossary">
         <h2>Glossary</h2>
         {{glossary}}
       </section>
       <section class="actors" id="actors">
         <h2>Actors</h2>
         {{actors}}
       </section>
       {{chapters}}
       <section class="traceability" id="traceability">
         <h2>Traceability matrix</h2>
         {{traceability}}
       </section>
       ```
     The template override test above removes only the placeholders, so the `<h2>` headings stay; it asserts on the "No …" lines, which come only from code.
  4. `specs_export.py`:
     - `use_case_diagram`: its `actor` helper keys on `specs.actor_key(name)` instead of `label.casefold()`; output unchanged.
     - `_chapter`: for each use case, render as today, then insert `f'<p class="use-case-id">{escape(cap)}/{escape(path.stem)}</p>'` right after the first closing heading tag (`re.sub(r"(</h[1-6]>)", r"\1" + id_html, html, count=1)`), or before the content when it has no heading.
     - Add, with `from . import specs_matter`:
       ```python
       def _table(headers: list[str], rows: list[list[str]], empty: str) -> str:
           """Cells are HTML already escaped by the caller."""
           if not rows:
               return f'<p class="none">{escape(empty)}</p>'
           head = "".join(f"<th>{escape(name)}</th>" for name in headers)
           body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
           return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


       def _use_case_link(ref: str, caps: list[str]) -> str:
           owner, slug = ref.split("/", 1)
           return f'<a href="#{escape(owner)}-{escape(slug)}">{escape(ref)}</a>' if owner in caps else escape(ref)


       def _matter(root: Path, cfg: Mapping[str, Any], cap: str | None, caps: list[str]) -> dict[str, str]:
           """The HTML of the document-level sections for `export`."""
           join = lambda items: ", ".join(escape(item) for item in items)  # noqa: E731
           revisions = [[escape(r["date"]), escape(r["epic"]), escape(r["title"]), join(r["capabilities"]),
                         join(r["added"]), join(r["modified"]), join(r["removed"])]
                        for r in specs_matter.revisions(root, cfg, cap)]
           glossary = [[escape(g["english"]), escape(f"{g['term']} ({g['lang']})" if g["lang"] else g["term"]),
                        escape(g["meaning"])] for g in specs_matter.glossary(root, cfg)]
           actors = [[escape(a["actor"]), escape(a["description"]),
                      ", ".join(_use_case_link(u["ref"], caps) + (" (secondary)" if u["secondary"] else "")
                                for u in a["use_cases"])] for a in specs_matter.actors(root, cfg, cap)]
           trace = [[f'<a href="#{escape(t["id"])}">{escape(t["id"])}</a>: {escape(t["title"])}', escape(t["capability"]),
                     ", ".join(_use_case_link(ref, caps) for ref in t["use_cases"]),
                     "<br>".join(f"<code>{escape(path)}</code>" for path in t["tests"]), join(t["qa_cases"]),
                     escape(t["status"])] for t in specs_matter.traceability(root, cfg, cap)]
           return {
               "revisions": _table(["Date", "Epic", "Title", "Capabilities", "Added", "Modified", "Removed"],
                                   revisions, "No revisions yet."),
               "glossary": _table(["English", "Term", "Meaning"], glossary, "No glossary."),
               "actors": _table(["Actor", "Description", "Use cases"], actors, "No actors."),
               "traceability": _table(["Requirement", "Capability", "Use cases", "Tests", "QA cases", "Status"],
                                      trace, "No requirements."),
           }
       ```
     - `export`: after building `chapters` and `toc`, compute `matter = _matter(root, cfg, cap, caps)`; build the table of contents as the sections the document holds, in order: `front = [(a, l) for a, l in (("revisions", "Revision history"), ("signoff", "Sign-off"), ("glossary", "Glossary"), ("actors", "Actors")) if f'id="{a}"' in document]`, then the chapter entries, then `("traceability", "Traceability matrix")` when `'id="traceability"' in document`; each as `<li><a href="#{a}">{l}</a></li>`. Pass `**matter` to the `fill` of the document. Use a named function instead of the `join` lambda if the linter flags E731.
  5. Run `timeout 300 python3 -m pytest tests/workflow_core/test_specs_export.py tests/workflow_core/test_specs_matter.py tests/workflow_core/test_specs.py -q`: passes. An existing test that asserts the exact TOC or chapter HTML is adapted to the new sections without weakening it (report each).
  6. Render check: export a demo SRS from a scratch SDD repo (two use cases, an archived change, a glossary, a test file) and open it in Chromium (Playwright); confirm the sections show in order, the Mermaid blocks render, and no comment text leaks. Note the result in the commit body.
  7. Commit: `feat(specs): the SRS gets a revision history, sign-off, glossary, actors, a traceability matrix, and use case IDs (gin-workflow-414v.2)`.
- **Acceptance criteria**: US-1 to US-6 rendering criteria pass as tests; an override without the new placeholders exports without those sections; the use case diagram output is unchanged.
- **Estimated complexity**: medium

### Track 3: Documentation (R8)
- **Dependencies**: Track 2
- **Files**:
  - Modify `docs/guides/sdd.md`, `docs/guides/sdd.vi.md` (SRS paragraph)
  - Modify `docs/guides/ba.md`, `docs/guides/ba.vi.md` (`actors.md`, citing `<cap>/<slug>`, glossary source)
  - Modify `docs/guides/customizing-templates.md`, `docs/guides/customizing-templates.vi.md` (new `srs.html` placeholders and the sign-off section)
  - Modify `docs/reference/cli.md` (`export` and `lint` rows)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** documentation of behaviour built in Tracks 1 and 2, checked against the code.
- **Steps**:
  1. Read `specs_matter.py`, `specs_export.py`, `templates/srs.html`, and `specs.lint_actors` for the exact behaviour, messages, and defaults.
  2. `docs/guides/sdd.md`: in the SRS paragraph, name the new sections in document order and the source of each (archived changes, the blank sign-off table, confirmed rows of `11-GLOSSARY.md`, use cases plus optional `actors.md`, requirements with use cases, test files, and QA cases), that one-capability exports filter revisions, actors, and traceability, and that each use case shows `<cap>/<slug>`. Same content in `sdd.vi.md` in natural Vietnamese.
  3. `docs/guides/ba.md` and `.vi.md`: how to write `<specs>/actors.md` (a table with `Actor` and `Description`, names matched without regard to case), the two lint findings, citing use cases as `<cap>/<slug>`, and that only `confirmed` glossary terms reach the SRS. Link to sdd.md for the SRS sections instead of repeating them (one-home).
  4. `docs/guides/customizing-templates.md` and `.vi.md`: the placeholders `revisions`, `glossary`, `actors`, `traceability` in the `srs.html` list, and that the sign-off table is plain HTML to edit in an override.
  5. `docs/reference/cli.md`: the `export` row lists the new sections; the `lint` row adds the `actors.md` checks.
  6. Run `gin docs check docs/guides/sdd.md docs/guides/sdd.vi.md docs/guides/ba.md docs/guides/ba.vi.md docs/guides/customizing-templates.md docs/guides/customizing-templates.vi.md docs/reference/cli.md`: exits 0.
  7. Commit: `docs(specs): SRS document matter, actors.md, and use case IDs (gin-workflow-414v.3)`.
- **Acceptance criteria**: R8; every docs claim matches the code; docs check exits 0.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/srs-document-matter`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes, and once with `bd` off PATH before a release.
- [ ] `gin docs check` on the changed pages exits 0.
- [ ] Manual: the demo SRS of Track 2 step 6 shows every section in order in a browser.

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- Deliverable merge-holds apply only to the Parent Bead `gin-workflow-414v`; track beads close when their tests and review pass.
- Track IDs in commit messages (`gin-workflow-414v.N`) are the track beads orchestrate creates; use the real IDs.

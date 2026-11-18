# Plan: SRS requirement types: non-functional requirements and business rules

Epic: gin-workflow-ngiz
Workflow: gin-workflow-ngiz
Spec: `.planning/specs/2026-11-18-srs-requirement-types-design.md`

## Objective

A requirement block can carry `Type:` (functional, non-functional, business-rule), a `Category:` from a fixed list for non-functional blocks, and a `Measure:` that replaces a scenario for them. Lint checks these lines, the activity diagram rule ignores non-functional blocks, `gin specs reqs` reports them, and the SRS groups each chapter's requirements by type, lists every NFR and business rule in two document catalogues, and shows the type in the traceability matrix.

## Global Constraints

Copied from the spec:

- NFRs and business rules stay `### REQ-<CAP>-<NNN>` blocks with a `Type:` line (`functional`, `non-functional`, `business-rule`; default `functional`). No new ID families: next-id, hash, delta, renumber, archive, trace, and gin-qa keep working unchanged.
- A non-functional block has a `Category:` from `performance`, `security`, `reliability`, `usability`, `compatibility`, `maintainability`, `portability`, `constraint`.
- A non-functional block needs a full scenario or a `Measure:` line; functional and business-rule blocks keep needing a scenario.
- A non-functional block does not count toward the per-capability activity diagram rule of `specs lint --change`. Business rules still count.
- In the SRS, each chapter groups its requirements by type (NFRs by category), the document gains a non-functional requirements catalogue and a business rules catalogue after the actors, and the traceability matrix gains a Type column.
- A block without `Type:` lints, hashes, archives, and traces as before. `skills/sdd/SKILL.md` is not changed. Out of scope: `/gin:explain`, measuring NFR coverage, configurable categories, the legacy layout.

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
- Problem statement: requirements have no type, so the SRS cannot separate NFRs and business rules, lint cannot require measurable NFRs, and an added NFR forces an activity diagram.
- Success criteria: US-1 to US-3 pass as tests; specs without `Type:` keep findings and hashes; full suite green.
- Constraints: Global Constraints above.
- Non-goals: the out-of-scope list above.

## Approach Options
### Option 1: Type lines on REQ blocks (confirmed at discuss)
- Summary: properties on `Block`, rules in `lint_block`, rows in `specs_matter`, rendering in `specs_export`.
- Pros: every tool that reads REQ-IDs keeps working; one place per concern.
- Cons: type is a line of text, not part of the ID.

### Option 2: New ID families NFR-/BR-
- Summary: separate headings and ID allocation.
- Pros: closest to classic SRS numbering.
- Cons: touches next-id, hash, renumber, delta, archive, trace, explain, gin-qa; rejected at discuss.

### Recommended Approach
- Selected option: Option 1.
- Rationale: confirmed by the user; smallest change with the same SRS result.

## Scope
- In scope: R1 to R5 of the spec.
- Out of scope: Global Constraints' out-of-scope list.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 renders the properties and rows Track 1 adds, and Track 3 documents both; they run one after another on feat/srs-requirement-types.
```

## Tasks

### Track 1: Requirement type, category, measure, lint, and reqs data (R1, R2, R3 reqs)
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py` (constants; `Block.type`, `category`, `measure`; `type_of`, `statement`; `lint_block`; `_feature_diagram_findings`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_reqs.py:31-35` (`_row` adds `type`, `category`)
  - Modify `plugins/gin-workflow/src/templates/spec-delta.md` (comment)
  - Test `tests/workflow_core/test_specs.py`, `tests/workflow_core/test_specs_reqs.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded rules in one module with exact messages from the spec; compatibility with existing blocks is pinned by tests.
- **Interfaces produced**:
  - `specs.REQ_TYPES = ("functional", "non-functional", "business-rule")`
  - `specs.NFR_CATEGORIES = ("performance", "security", "reliability", "usability", "compatibility", "maintainability", "portability", "constraint")`
  - `Block.type -> str` (the `Type:` value, else `"functional"`), `Block.category -> str`, `Block.measure -> str` (else `""`), read outside `####` sections, comments ignored.
  - `specs.type_of(block: Block) -> str`: `block.type` when it is in `REQ_TYPES`, else `"functional"`.
  - `specs.statement(block: Block) -> str`: the first body line, outside `####` sections and not a bullet, holding SHALL or MUST; `""` without one.
- **Steps**:
  1. Write failing tests in `tests/workflow_core/test_specs.py` (`TestBlocks` for pure block rules, `TestRepositoryCommands` for the diagram rule):
     ```python
     NFR = ("### REQ-AUTH-004: Sign-in response time\nType: non-functional\nCategory: performance\n"
            "Measure: p95 below 300 ms at 200 requests per second\n"
            "The system SHALL answer a sign-in request within 300 ms at the 95th percentile.\n")
     RULE = ("### REQ-AUTH-005: Lockout threshold\nType: business-rule\n"
             "The system MUST lock an account after 5 failed sign-ins within 15 minutes.\n\n"
             "#### Scenario: fifth failure\n- GIVEN a user with 4 failed sign-ins\n- WHEN the next sign-in fails\n"
             "- THEN the account is locked\n")

     def block(text: str) -> specs.Block:
         return specs.parse_blocks(text)[0][0]

     def test_block_type_category_measure(self):
         nfr = block(NFR)
         self.assertEqual(("non-functional", "performance", "p95 below 300 ms at 200 requests per second"),
                          (nfr.type, nfr.category, nfr.measure))
         plain = block(ADDED_BLOCK)
         self.assertEqual(("functional", "", ""), (plain.type, plain.category, plain.measure))
         self.assertEqual("functional", specs.type_of(block(RULE.replace("business-rule", "policy"))))
         self.assertEqual("The system MUST lock an account after 5 failed sign-ins within 15 minutes.",
                          specs.statement(block(RULE)))
         scenario_type = block(ADDED_BLOCK + "Type: business-rule\n")  # inside the scenario section: ignored
         self.assertEqual("functional", scenario_type.type)

     def test_lint_requirement_types(self):
         self.assertEqual([], specs.lint_block(block(NFR)))
         self.assertEqual([], specs.lint_block(block(RULE)))
         categories = ", ".join(specs.NFR_CATEGORIES)
         self.assertEqual([f"REQ-AUTH-004: Category must be one of {categories}"],
                          specs.lint_block(block(NFR.replace("Category: performance\n", ""))))
         self.assertEqual([f"REQ-AUTH-004: Category must be one of {categories}"],
                          specs.lint_block(block(NFR.replace("performance", "speed"))))
         self.assertEqual(["REQ-AUTH-004: needs at least one '#### Scenario:' or a 'Measure:' line"],
                          specs.lint_block(block(NFR.replace("Measure: p95 below 300 ms at 200 requests per second\n", ""))))
         self.assertEqual(["REQ-AUTH-005: Type must be one of functional, non-functional, business-rule"],
                          specs.lint_block(block(RULE.replace("business-rule", "policy"))))
         self.assertIn("REQ-AUTH-005: needs at least one '#### Scenario:'",
                       specs.lint_block(block(RULE.split("\n\n#### ")[0] + "\n")))
         self.assertEqual(["REQ-AUTH-003: Category and Measure are only for Type: non-functional"],
                          specs.lint_block(block(ADDED_BLOCK.replace("The system SHALL", "Measure: 5 tries\nThe system SHALL"))))
         with_scenario = NFR + "\n#### Scenario: slow\n- GIVEN load\n- THEN fast\n"
         self.assertEqual(["REQ-AUTH-004: scenario 1 lacks WHEN"], specs.lint_block(block(with_scenario)))

     def test_blocks_without_type_keep_findings_and_hash(self):
         for text in (ADDED_BLOCK, AUTH_SPEC.split("## Requirements\n\n", 1)[1]):
             with self.subTest(text=text[:30]):
                 first = block(text)
                 self.assertEqual([], specs.lint_block(first))
         self.assertEqual("8f31b417", specs.block_hash(block(ADDED_BLOCK).text)[:8])
     ```
     `8f31b417` is the hash prefix of `ADDED_BLOCK` on master before this change; the assertion pins that hashing is unchanged.
     Diagram rule tests in `TestRepositoryCommands` (follow `test_lint_against_base_needs_a_changed_activity_diagram_per_capability`):
     ```python
     def test_non_functional_added_blocks_need_no_activity_diagram(self):
         commit_all(self.root)
         git(self.root, "checkout", "-q", "-b", "feature")
         nfr = NFR.replace("REQ-AUTH-004", "REQ-AUTH-003")
         change = make_change(self.root, spec_delta=delta(added=nfr))
         self.assertFalse([e for e in specs.lint_change(self.root, self.cfg, change, against="main") if "activity diagram" in e])
         (self.root / "docs/specs/auth/diagrams/login-activity.md").unlink()
         self.assertFalse([e for e in specs.lint_change(self.root, self.cfg, change) if "activity diagram" in e])
         rule = RULE.replace("REQ-AUTH-005", "REQ-AUTH-003")
         write(self.root, "docs/changes/ep-1-lockout/02-spec-delta.md", delta(added=rule))
         self.assertTrue([e for e in specs.lint_change(self.root, self.cfg, change, against="main") if "activity diagram" in e])
     ```
     Move `NFR`, `RULE`, and `block` to module level so both classes use them. In `TestSpecsCli`, assert the `spec-delta.md` template holds `"Type:"`, `"Category:"`, `"Measure:"`, `"non-functional"`, `"business-rule"`, and that the text between `<!--` and the first `-->` holds no `--`.
     In `tests/workflow_core/test_specs_reqs.py`, add an assertion that a living `NFR` block's row has `"type": "non-functional", "category": "performance"` and a plain block's row has `"type": "functional", "category": ""` (follow the existing `gin specs reqs` JSON test there).
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_specs.py tests/workflow_core/test_specs_reqs.py -q`: the new tests fail.
  3. In `specs.py`:
     - Near `_STATEMENT`, add the two constants of the Interfaces.
     - In `Block`, add:
       ```python
       def _field(self, key: str) -> str:
           """A `<key>:` line of the block body before its first `####` section."""
           return line_value(self.text.split("\n#### ", 1)[0], key)

       @property
       def type(self) -> str:
           return self._field("Type") or "functional"

       @property
       def category(self) -> str:
           return self._field("Category")

       @property
       def measure(self) -> str:
           return self._field("Measure")
       ```
     - After `block_hash`, add:
       ```python
       def type_of(block: Block) -> str:
           """The block's type, or functional when its `Type:` is not a known one (lint reports that)."""
           return block.type if block.type in REQ_TYPES else "functional"


       def statement(block: Block) -> str:
           """The first SHALL or MUST line of the block body, outside scenarios and bullets."""
           head = block.text.split("\n#### ", 1)[0].splitlines()[1:]
           return next((line.strip() for line in head if not line.startswith(("#", "- ")) and _STATEMENT.search(line)), "")
       ```
     - In `lint_block`, after the SHALL/MUST check, add the type rules, and make the scenario rule accept a measure:
       ```python
       head = _COMMENT.sub("", block.text.split("\n#### ", 1)[0])
       if block.type not in REQ_TYPES:
           errors.append(f"{block.id}: Type must be one of {', '.join(REQ_TYPES)}")
       non_functional = block.type == "non-functional"
       if non_functional and block.category not in NFR_CATEGORIES:
           errors.append(f"{block.id}: Category must be one of {', '.join(NFR_CATEGORIES)}")
       if not non_functional and re.search(r"^(Category|Measure):", head, re.MULTILINE):
           errors.append(f"{block.id}: Category and Measure are only for Type: non-functional")
       ```
       and replace `if not scenarios: errors.append(f"{block.id}: needs at least one '#### Scenario:'")` with:
       ```python
       if not scenarios and non_functional and not block.measure:
           errors.append(f"{block.id}: needs at least one '#### Scenario:' or a 'Measure:' line")
       elif not scenarios and not non_functional:
           errors.append(f"{block.id}: needs at least one '#### Scenario:'")
       ```
       Keep the order of findings: statement, type rules, scenario rules (the tests expect single findings, so order matters only in the multi-finding cases).
     - In `_feature_diagram_findings`, count only blocks whose type is not non-functional: at the top, `blocks = [block for block in blocks if block.type != "non-functional"]`.
  4. In `specs_reqs._row`, add `"type": block.type, "category": block.category`.
  5. In `templates/spec-delta.md`, extend the comment (no `--` inside it): "A requirement may add, right under its heading, `Type: functional | non-functional | business-rule` (default functional). A non-functional one adds `Category:` (performance, security, reliability, usability, compatibility, maintainability, portability, constraint) and either a scenario or `Measure:` with a measurable target; it needs no activity diagram. A business rule keeps a scenario; use cases cite it on `Requirements:`."
  6. Run `timeout 300 python3 -m pytest tests/workflow_core/test_specs.py tests/workflow_core/test_specs_reqs.py tests/workflow_core/test_specs_archive_trace.py tests/workflow_core/test_specs_matter.py tests/workflow_core/test_specs_export.py -q`: passes.
  7. Commit: `feat(specs): requirement Type, Category, and Measure, linted; non-functional blocks need no activity diagram (gin-workflow-ngiz.1)`.
- **Acceptance criteria**: US-1, US-2, and the `gin specs reqs` criterion of US-3; blocks without `Type:` keep findings and hashes.
- **Estimated complexity**: medium

### Track 2: Catalogues and SRS rendering by type (R3 matter, R4)
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_matter.py` (`nonfunctional`, `business_rules`; `traceability` adds `type`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_export.py` (requirement grouping and field table in `_chapter`; `_matter` catalogues and Type column; TOC entries)
  - Modify `plugins/gin-workflow/src/templates/srs.html` (two sections, comment)
  - Test `tests/workflow_core/test_specs_matter.py`, `tests/workflow_core/test_specs_export.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** rows and HTML following the patterns of the previous SRS epics; grouping and anchors are the subtle part.
- **Interfaces consumed**: `specs.type_of`, `specs.statement`, `specs.NFR_CATEGORIES`, `Block.category`, `Block.measure`.
- **Interfaces produced**:
  - `specs_matter.nonfunctional(root, cfg, cap=None) -> list[dict]`: keys `id`, `title`, `capability`, `category`, `measure`.
  - `specs_matter.business_rules(root, cfg, cap=None) -> list[dict]`: keys `id`, `title`, `capability`, `statement`, `use_cases`.
- **Steps**:
  1. Tests in `tests/workflow_core/test_specs_matter.py` (spec text with three blocks):
     ```python
     TYPED_SPEC = AUTH_SPEC + """
     ### REQ-AUTH-004: Sign-in response time
     Type: non-functional
     Category: performance
     Measure: p95 below 300 ms
     The system SHALL answer a sign-in request within 300 ms.

     ### REQ-AUTH-005: Lockout threshold
     Type: business-rule
     The system MUST lock an account after 5 failed sign-ins.

     #### Scenario: fifth failure
     - GIVEN a user with 4 failed sign-ins
     - WHEN the next sign-in fails
     - THEN the account is locked

     ### REQ-AUTH-006: Password storage
     Type: non-functional
     Category: security
     Measure: bcrypt cost 12
     The system MUST store passwords only as salted hashes.
     """

     def test_nonfunctional_and_business_rules_catalogues(self):
         write(self.root, "docs/specs/auth/spec.md", TYPED_SPEC)
         write(self.root, "docs/specs/auth/use-cases/sign-in.md", USE_CASE.replace("REQ-AUTH-002", "REQ-AUTH-005"))
         self.assertEqual([
             {"id": "REQ-AUTH-004", "title": "Sign-in response time", "capability": "auth", "category": "performance",
              "measure": "p95 below 300 ms"},
             {"id": "REQ-AUTH-006", "title": "Password storage", "capability": "auth", "category": "security",
              "measure": "bcrypt cost 12"},
         ], specs_matter.nonfunctional(self.root, self.cfg))
         self.assertEqual([
             {"id": "REQ-AUTH-005", "title": "Lockout threshold", "capability": "auth",
              "statement": "The system MUST lock an account after 5 failed sign-ins.", "use_cases": ["auth/sign-in"]},
         ], specs_matter.business_rules(self.root, self.cfg))
         self.assertEqual([], specs_matter.nonfunctional(self.root, self.cfg, "billing"))
         types = {row["id"]: row["type"] for row in specs_matter.traceability(self.root, self.cfg)}
         self.assertEqual({"REQ-AUTH-001": "functional", "REQ-AUTH-002": "functional", "REQ-AUTH-004": "non-functional",
                           "REQ-AUTH-005": "business-rule", "REQ-AUTH-006": "non-functional"}, types)
     ```
     Tests in `tests/workflow_core/test_specs_export.py`:
     ```python
     def test_chapter_groups_requirements_by_type(self):
         write(self.root, "docs/specs/auth/spec.md", TYPED_SPEC)
         self.assertEqual(0, run_specs(self.root, "export", "auth").returncode)
         html = self.read("srs-auth.html")
         chapter = html[html.index('<section class="chapter" id="auth">'):html.index('id="traceability"')]
         order = [chapter.index(text) for text in ("<h3>Functional requirements</h3>", 'id="REQ-AUTH-001"',
                                                    "<h3>Non-functional requirements</h3>", "<h4>performance</h4>",
                                                    'id="REQ-AUTH-004"', "<h4>security</h4>", 'id="REQ-AUTH-006"',
                                                    "<h3>Business rules</h3>", 'id="REQ-AUTH-005"')]
         self.assertEqual(sorted(order), order)
         self.assertIn('<table class="requirement-fields"><tr><th>Type</th><td>non-functional</td></tr>'
                       "<tr><th>Category</th><td>performance</td></tr><tr><th>Measure</th><td>p95 below 300 ms</td></tr></table>",
                       chapter)

     def test_functional_only_chapter_has_no_group_headings(self):
         self.assertEqual(0, run_specs(self.root, "export", "auth").returncode)
         self.assertNotIn("Functional requirements", self.read("srs-auth.html"))

     def test_nfr_and_rules_catalogues_and_type_column(self):
         write(self.root, "docs/specs/auth/spec.md", TYPED_SPEC)
         self.assertEqual(0, run_specs(self.root, "export", "--all").returncode)
         html = self.read("srs.html")
         order = [html.index(f'id="{anchor}"') for anchor in ("actors", "nfr", "business-rules", "auth")]
         self.assertEqual(sorted(order), order)
         nfr = html[html.index('id="nfr"'):html.index('id="business-rules"')]
         self.assertIn('<td>performance</td><td><a href="#REQ-AUTH-004">REQ-AUTH-004</a>: Sign-in response time</td>'
                       "<td>auth</td><td>p95 below 300 ms</td>", nfr)
         rules = html[html.index('id="business-rules"'):html.index('<section class="chapter"')]
         self.assertIn("The system MUST lock an account after 5 failed sign-ins.", rules)
         self.assertIn('<a href="#nfr">Non-functional requirements</a>', html)
         self.assertIn('<a href="#business-rules">Business rules</a>', html)
         self.assertIn("<th>Type</th>", html[html.index('id="traceability"'):])
         self.assertEqual(0, run_specs(self.root, "export", "billing").returncode)
         billing = self.read("srs-billing.html")
         self.assertIn("No non-functional requirements.", billing)
         self.assertIn("No business rules.", billing)
     ```
     Put `TYPED_SPEC` in `tests/workflow_core/specs_fixtures.py` (it is shared by both test files) and import it. Extend `test_srs_templates_print_their_placeholders` with `"{{nfr}}"`, `"{{business_rules}}"`. Extend `test_template_without_matter_placeholders_exports_as_before` to also blank `nfr` and `business_rules` and assert "No business rules." is absent.
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_specs_matter.py tests/workflow_core/test_specs_export.py -q`: the new tests fail.
  3. `specs_matter.py`:
     ```python
     def _living(root: Path, cfg: Mapping[str, Any], cap: str | None, kind: str) -> list[specs.Block]:
         return sorted((block for _, block in specs.living_blocks(root, cfg).values()
                        if specs.type_of(block) == kind and (cap is None or block.cap == cap)),
                       key=lambda block: (block.cap, _id_order(block.id)))


     def nonfunctional(root: Path, cfg: Mapping[str, Any], cap: str | None = None) -> list[dict[str, str]]:
         """Non-functional living requirements by category order, then capability and number."""
         rank = {name: index for index, name in enumerate(specs.NFR_CATEGORIES)}
         blocks = sorted(_living(root, cfg, cap, "non-functional"),
                         key=lambda block: rank.get(block.category, len(rank)))
         return [{"id": b.id, "title": b.title, "capability": b.cap, "category": b.category, "measure": b.measure}
                 for b in blocks]


     def business_rules(root: Path, cfg: Mapping[str, Any], cap: str | None = None) -> list[dict[str, Any]]:
         """Business-rule living requirements with their statement and the use cases citing them."""
         blocks = _living(root, cfg, cap, "business-rule")
         ids = {block.id for block in blocks}
         citing: dict[str, list[str]] = {req: [] for req in ids}
         for path in sorted(specs.specs_dir(root, cfg).glob(f"*/{specs.USE_CASES_DIR}/*.md")):
             text = specs.read_text_or_none(path)
             for req in set(specs.line_values(text or "", "Requirements")) & ids:
                 citing[req].append(f"{path.parent.parent.name}/{path.stem}")
         return [{"id": b.id, "title": b.title, "capability": b.cap, "statement": specs.statement(b),
                  "use_cases": citing[b.id]} for b in blocks]
     ```
     (`sorted` is stable, so the category sort keeps the capability/number order inside a category.) In `traceability`, add `"type": specs.type_of(block)` to each row. Check `specs.read_text_or_none` exists with that name (Track 1 of `gin-workflow-414v` added it); use the actual name.
  4. `specs_export.py`:
     - Generalise the header-field reader: rename `_use_case_fields(text)` to `_header_fields(text, pattern, css)` taking the field regex and the table class, and search the first section heading from the second line (`_FIRST_SECTION.search(text, text.find("\n") + 1)` when the text has a newline) so a `### REQ-…` heading is not taken as the end of the head; `_use_case` passes `_FIELD` and `"use-case-fields"` and keeps its output. Add `_REQUIREMENT_FIELD = re.compile(r"^(Type|Category|Measure):[ \t]*(.*)$")`.
     - In `_chapter`, render each requirement as `_requirement(block, ...)`: `fields, text = _header_fields(block.text, _REQUIREMENT_FIELD, "requirement-fields")`, then `markdown_html(text, ...)` with the fields table inserted after the first closing heading tag (as `_with_id` does). Group: when every block is functional (`specs.type_of`), join as today; otherwise emit `<h3>Functional requirements</h3>` + functional blocks (if any), `<h3>Non-functional requirements</h3>` + for each category in `NFR_CATEGORIES` that has blocks `<h4>{category}</h4>` + its blocks (blocks with a category outside the list go last under `<h4>other</h4>`), and `<h3>Business rules</h3>` + rule blocks (if any). Keep `id="<REQ-ID>"` on each `<section class="requirement">` and keep the TOC built from all blocks in file order.
     - In `_matter`, add:
       ```python
       nfr = [[escape(n["category"]), f'<a href="#{escape(n["id"])}">{escape(n["id"])}</a>: {escape(n["title"])}',
               escape(n["capability"]), escape(n["measure"])] for n in specs_matter.nonfunctional(root, cfg, cap)]
       rules = [[f'<a href="#{escape(r["id"])}">{escape(r["id"])}</a>: {escape(r["title"])}', escape(r["capability"]),
                 escape(r["statement"]), ", ".join(_use_case_link(ref, caps) for ref in r["use_cases"])]
                for r in specs_matter.business_rules(root, cfg, cap)]
       ```
       and in the returned dict `"nfr": _table(["Category", "Requirement", "Capability", "Measure"], nfr, "No non-functional requirements.")`, `"business_rules": _table(["Rule", "Capability", "Statement", "Use cases"], rules, "No business rules.")`. Insert `escape(t["type"])` after the capability cell of each traceability row and `"Type"` after `"Capability"` in its headers.
     - In `export`, add `("nfr", "Non-functional requirements"), ("business-rules", "Business rules")` after `("actors", "Actors")` in the `front` list.
  5. `templates/srs.html`: add after the actors section
     ```html
     <section class="nfr" id="nfr">
       <h2>Non-functional requirements</h2>
       {{nfr}}
     </section>
     <section class="business-rules" id="business-rules">
       <h2>Business rules</h2>
       {{business_rules}}
     </section>
     ```
     and add `nfr, business_rules` to the comment's placeholder list (after `actors`), with no `--` in the comment.
  6. Run `timeout 300 python3 -m pytest tests/workflow_core/test_specs_matter.py tests/workflow_core/test_specs_export.py tests/workflow_core/test_specs.py -q`: passes; existing use case field tests still pass.
  7. Render check: export a scratch SDD repo built with `TYPED_SPEC` and a use case citing REQ-AUTH-005 (scratch files under `/tmp/claude-1002/-home-gin-gin-fam-gin-workflow/06b4f8ac-7dbf-4dd5-95e7-c8ff3f98bfa4/scratchpad/`, export with `python3 plugins/gin-workflow/src/scripts/gin specs export --all --repository <scratch>`), open it in Chromium with Node Playwright (`NODE_PATH=/home/gin/scotty/node_modules node <script>`), and check the groups, the field tables, both catalogues, and that no comment text shows. Save a screenshot as `srs-types.png` in that scratchpad.
  8. Commit: `feat(specs): the SRS groups requirements by type and lists non-functional requirements and business rules (gin-workflow-ngiz.2)`.
- **Acceptance criteria**: the SRS criteria of US-3; existing use case and export tests pass unchanged; browser render as in step 7.
- **Estimated complexity**: medium

### Track 3: Documentation (R5)
- **Dependencies**: Track 2
- **Files**:
  - Modify `docs/guides/sdd.md`, `docs/guides/sdd.vi.md`
  - Modify `docs/guides/ba.md`, `docs/guides/ba.vi.md`
  - Modify `docs/guides/customizing-templates.md`, `docs/guides/customizing-templates.vi.md`
  - Modify `docs/reference/cli.md`
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** documentation of behaviour built in Tracks 1 and 2, checked against the code.
- **Steps**:
  1. Read `specs.py` (`REQ_TYPES`, `NFR_CATEGORIES`, `lint_block`, `_feature_diagram_findings`), `specs_reqs._row`, `specs_matter.nonfunctional`/`business_rules`, `specs_export` (grouping, `_matter`, TOC), `templates/srs.html`, `templates/spec-delta.md` for the exact behaviour and messages.
  2. `docs/guides/sdd.md` (and `.vi.md`): a section on requirement types: the three lines, the categories, `Measure:` versus a scenario, the lint messages, that a non-functional block needs no activity diagram (link the diagram rules), and the SRS grouping and catalogues (in the SRS paragraph). How to reclassify an existing requirement: a `MODIFIED` block with the new lines and its `base:` hash.
  3. `docs/guides/ba.md` (and `.vi.md`): when a requirement is non-functional or a business rule, one example each, and that use cases cite rules on `Requirements:`; link to sdd.md for the rules (one-home).
  4. `docs/guides/customizing-templates.md` (and `.vi.md`): the `nfr` and `business_rules` placeholders.
  5. `docs/reference/cli.md`: `lint` (type rules, diagram exemption), `reqs` (`type`, `category`), `export` (grouping, catalogues, Type column).
  6. Run `gin docs check docs/guides/sdd.md docs/guides/sdd.vi.md docs/guides/ba.md docs/guides/ba.vi.md docs/guides/customizing-templates.md docs/guides/customizing-templates.vi.md docs/reference/cli.md` and `timeout 300 python3 -m pytest tests/workflow_core/test_docs*.py -q`: pass.
  7. Commit: `docs(specs): requirement types, non-functional requirements, and business rules (gin-workflow-ngiz.3)`.
- **Acceptance criteria**: R5; every docs claim matches the code; docs check exits 0.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/srs-requirement-types`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes (pre-push hook), and with `bd` off PATH before a release.
- [ ] `gin docs check` on the changed pages exits 0.
- [ ] Manual: the browser render of Track 2 step 7.

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- Deliverable merge-holds apply only to the Parent Bead `gin-workflow-ngiz`; track beads close when their tests and review pass.
- Track IDs in commit messages (`gin-workflow-ngiz.N`) are the beads orchestrate creates; use the real IDs.

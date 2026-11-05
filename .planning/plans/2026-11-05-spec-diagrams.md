# Plan: Diagrams in specs: activity diagram per feature, state diagram for complex features

Epic: gin-workflow-ycg8
Spec: .planning/specs/2026-11-05-spec-diagrams-design.md

## Objective
With the SDD layout, each capability keeps Mermaid diagrams in `docs/specs/<capability>/diagrams/`: `<feature>-activity.md` (a `flowchart`) per feature and `<entity>-state.md` (a `stateDiagram-v2`) for an entity with three or more states or a guarded transition. `specs lint` checks each file holds a block of its kind; `specs lint --change` (and therefore `specs archive`) requires an activity diagram for each capability with an `ADDED` or `MODIFIED` block; `specs archive` links the diagrams of a new capability under `## Diagrams` in its new `spec.md`; `gin-sdd` and the guides state the convention.

Architecture: two new templates and two edited ones (`spec.md`, `design.md`); `lint_diagrams` plus an activity-diagram check in `lint_change` in `workflow_core/specs.py`; five lines in `workflow_core/specs_archive.py` for a new capability; test fixtures gain a valid activity diagram; skill text and docs. No new command, config key, or event.

Tech stack: Python 3 standard library (`re`, `pathlib`), `unittest` tests run by `python3 -m pytest -n auto`.

Global Constraints (from the spec):
- SDD layout only; `specs` commands already exit 2 with the legacy layout.
- Diagram files are not requirement blocks: they never go through `02-spec-delta.md` and carry no `base:` hash; `specs archive` never moves or edits them.
- `specs archive` changes only to link the diagrams of a new capability; an existing `spec.md` is not touched outside its requirement blocks.
- Only the diagram type on the first line of a Mermaid block is checked (lines starting with `%%` are skipped); Mermaid syntax is not validated; files in `diagrams/` without the `-activity.md` or `-state.md` suffix are not checked; links in `## Diagrams` are not checked.
- A delta with only `REMOVED` blocks for a capability needs no diagram there.
- `## Requirements` stays the last section of `spec.md`, because archive appends `ADDED` blocks at the end of the file.
- `skills/gin-*/SKILL.md` stay within 6,000 characters (`tests/workflow_core/test_token_budget.py`).

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
- Problem statement: living specs hold only requirement blocks; nothing shows how a feature flows or which states an entity takes, and `03-design.md` `## Data Flow` leaves with the change folder at archive.
- Success criteria: user stories US-1..US-3 of the spec; `specs lint` and `specs lint --change` report the findings of R3 with the exact messages; a new capability's archived `spec.md` links its diagrams; full suite green.
- Constraints: see Global Constraints.
- Non-goals: the SRS export (`gin-workflow-bel0`); diagrams through the spec delta; diagrams inside requirement blocks; a fence-aware `parse_blocks`; link checks; rendering; the legacy layout.

## Approach Options
### Option 1: Diagram files per capability, edited directly (chosen in discuss)
- Summary: `docs/specs/<cap>/diagrams/*.md`, lint per file and per change, archive links them for a new capability.
- Pros: no parser change; about 35 lines of Python; reviewers see the files with the change through the existing cited-path check.
- Cons: diagram edits carry no `base:` hash, so a concurrent edit is a plain git conflict.

### Option 2: `## DIAGRAMS` in the delta, merged by archive
- Summary: diagrams travel through `02-spec-delta.md` and archive merges them into `spec.md`.
- Pros: history in the change folder.
- Cons: a fence-aware parser, new archive merge code, and lint rules; several times the diff.

### Recommended Approach
- Selected option: Option 1.
- Rationale: chosen by the user in discuss on 2026-11-05, with lint at the change level (option 1 of the enforcement question) and archive linking a new capability's diagrams.

## Scope
- In scope: R1–R4 of the spec.
- Out of scope: everything under the spec's "Out of scope".

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Two tracks; Track 2 documents the templates, lint messages, and archive behavior that Track 1 ships, so they run one after the other on the feature branch.
```

## Tasks
### Track 1: Diagram templates, lint checks, and archive links
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/templates/activity.md`
  - Create `plugins/gin-workflow/src/templates/state.md`
  - Modify `plugins/gin-workflow/src/templates/spec.md` (add `## Diagrams` before `## Requirements`)
  - Modify `plugins/gin-workflow/src/templates/design.md:7` (comment under `## Data Flow`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py:280-341` (add `_MERMAID`, `_DIAGRAM_KINDS`, `_mermaid_types`, `lint_diagrams`; append it in `lint_living` and `lint_change`; activity-diagram check in `lint_change`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_archive.py:76-81` (links for a new capability)
  - Modify `tests/workflow_core/specs_fixtures.py` (add `ACTIVITY`, `STATE`, `write_activity`)
  - Test `tests/workflow_core/test_specs.py:61-66,242-258` (setUp writes an activity diagram; two new tests; template assertions)
  - Test `tests/workflow_core/test_specs_reqs.py:29-32` (setUp writes an activity diagram)
  - Test `tests/workflow_core/test_specs_archive_trace.py:33-48,140-147` (setUp, billing diagram, new test, end-to-end diagram)
  - Test `tests/gin_qa/qa_fixtures.py:17-18` and `tests/gin_qa/test_cases_cli.py:31-36` (re-export and setUp)
  - Modify `docs/reference/cli.md:132,136` (`lint` and `archive` rows)
  - Modify `docs/guides/customizing-templates.md:27,40` (template list and a table row)
  - Modify `docs/guides/customizing-templates.vi.md:27,40` (same, Vietnamese)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change to two modules with the exact functions, messages, fixtures, and tests given below; the edge cases (`%%` lines, unsuffixed files, `REMOVED`-only deltas, template without `## Diagrams`) are listed.
- **Interfaces**:
  - Produces `workflow_core.specs.lint_diagrams(root: Path, cfg: Mapping[str, Any]) -> list[str]`, findings `"<specs>/<cap>/diagrams/<file>: no mermaid block starting with flowchart or graph"` and `"...: no mermaid block starting with stateDiagram"`, sorted by path.
  - Produces the `lint_change` finding `"<cap>: no activity diagram in <specs>/<cap>/diagrams/ (gin-workflow specs template activity.md)"`, one per capability, sorted.
  - Produces template names `activity.md` and `state.md` for `gin-workflow specs template`.
  - Produces in `specs_fixtures`: `ACTIVITY: str`, `STATE: str`, `write_activity(root: Path, cap: str = "auth", name: str = "login") -> Path`.
  - Consumes `specs_dir(root, cfg)` (`specs.py:213`), `shown(root, path)` (`specs.py:260`), `Block.cap`, `render`, `template_text`.
- **Steps**:
  1. Fixtures. In `tests/workflow_core/specs_fixtures.py`, after `ADDED_BLOCK`, add:
     ````python
     ACTIVITY = """# Login

     How a user signs in.

     ```mermaid
     flowchart TD
       submit([Submit password]) --> check{Valid?}
       check -->|yes| done([Signed in])
     ```
     """

     STATE = """# Invoice

     The states of an invoice.

     ```mermaid
     %% stored in invoices.status
     stateDiagram-v2
       [*] --> Open
       Open --> Paid: payment received
     ```
     """
     ````
     and after `write`:
     ```python
     def write_activity(root: Path, cap: str = "auth", name: str = "login") -> Path:
         return write(root, f"docs/specs/{cap}/diagrams/{name}-activity.md", ACTIVITY)
     ```
     Add `write_activity` (and `STATE` where used) to the `from specs_fixtures import (...)` lists of `test_specs.py`, `test_specs_reqs.py`, `test_specs_archive_trace.py`, and `tests/gin_qa/qa_fixtures.py` (which re-exports to `test_cases_cli.py`; add `write_activity` to its import from `qa_fixtures` too). Call `write_activity(self.root)` right after `write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)` in the `setUp` of `TestRepositoryCommands` (`test_specs.py`), `TestSpecsReqs`, `TestArchive`, and `QaCase` (`test_cases_cli.py`); in `TestEndToEnd.test_new_delta_lint_trace_archive` call `write_activity(root)` after writing `AUTH_SPEC`; in `TestArchive.test_applies_added_modified_removed_and_new_capability` call `write_activity(self.root, "billing", "pay")` before `make_change`.
  2. Failing tests. In `test_specs.py`, class `TestRepositoryCommands`, after `test_lint_flags_dated_asset_folder_without_description`, add:
     ```python
     def test_lint_checks_each_diagram_holds_a_block_of_its_kind(self):
         write(self.root, "docs/specs/auth/diagrams/login-activity.md", "# Login\n\nNo diagram yet.\n")
         write(self.root, "docs/specs/auth/diagrams/account-state.md",
               "# Account\n\n```mermaid\nflowchart TD\n  a --> b\n```\n")
         write(self.root, "docs/specs/auth/diagrams/token-state.md", STATE)
         write(self.root, "docs/specs/auth/diagrams/sso-sequence.md", "# SSO\n\nNo block.\n")
         expected = ["docs/specs/auth/diagrams/account-state.md: no mermaid block starting with stateDiagram",
                     "docs/specs/auth/diagrams/login-activity.md: no mermaid block starting with flowchart or graph"]
         self.assertEqual(expected, specs.lint_living(self.root, self.cfg))
         self.assertEqual(expected, specs.lint_change(self.root, self.cfg, make_change(self.root)))
         result = run_specs(self.root, "lint")
         self.assertEqual(1, result.returncode)
         self.assertIn(expected[0], result.stdout)
         write(self.root, "docs/specs/auth/diagrams/login-activity.md", specs.template_text(self.root, "activity.md"))
         write(self.root, "docs/specs/auth/diagrams/account-state.md", specs.template_text(self.root, "state.md"))
         self.assertEqual([], specs.lint_living(self.root, self.cfg))

     def test_lint_change_needs_an_activity_diagram_where_requirements_are_added_or_modified(self):
         (self.root / "docs/specs/auth/diagrams/login-activity.md").unlink()
         missing = "auth: no activity diagram in docs/specs/auth/diagrams/ (gin-workflow specs template activity.md)"
         change = make_change(self.root)
         self.assertEqual([missing], specs.lint_change(self.root, self.cfg, change))
         result = run_specs(self.root, "lint", "--change", "ep-1")
         self.assertEqual(1, result.returncode)
         self.assertIn(missing, result.stdout)
         base2 = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-002")[1]
         modified = (f"### REQ-AUTH-002: Reject wrong password\n<!-- base: {base2} -->\n"
                     "The system SHALL reject a wrong password twice.\n\n#### Scenario: wrong password\n"
                     "- GIVEN a registered user\n- WHEN they submit a wrong password\n- THEN they see an error\n")
         write(self.root, "docs/changes/ep-1-lockout/02-spec-delta.md", delta(modified=modified))
         self.assertEqual([missing], specs.lint_change(self.root, self.cfg, change))
         base1 = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-001")[1]
         write(self.root, "docs/changes/ep-1-lockout/02-spec-delta.md", delta(
             removed=f"### REQ-AUTH-001: Sign in with password\n<!-- base: {base1} -->\nReason: replaced by SSO\n"))
         self.assertEqual([], specs.lint_change(self.root, self.cfg, change))
         write_activity(self.root)
         write(self.root, "docs/changes/ep-1-lockout/02-spec-delta.md", delta(added=ADDED_BLOCK))
         self.assertEqual([], specs.lint_change(self.root, self.cfg, change))
     ```
     In `TestSpecsCli.test_pm_and_ba_templates_ship_and_can_be_overridden`, add `"activity.md", "state.md"` to the name tuple, and after the iteration needles:
     ```python
     self.assertIn("```mermaid\nflowchart TD", run_specs(root, "template", "activity.md").stdout)
     self.assertIn("```mermaid\nstateDiagram-v2", run_specs(root, "template", "state.md").stdout)
     living = run_specs(root, "template", "spec.md").stdout
     self.assertLess(living.index("## Diagrams"), living.index("## Requirements"))
     ```
     In `test_specs_archive_trace.py`, class `TestArchive`, add:
     ```python
     def test_new_capability_spec_links_its_diagrams(self):
         write_activity(self.root, "billing", "pay")
         write(self.root, "docs/specs/billing/diagrams/invoice-state.md", STATE)
         auth_before = (self.root / "docs/specs/auth/spec.md").read_text(encoding="utf-8")
         change = make_change(self.root, spec_delta=delta(
             added=ADDED_BLOCK + "\n" + ADDED_BLOCK.replace("REQ-AUTH-003", "REQ-BILLING-001")))
         commit_all(self.root)
         archive(self.root, self.cfg, change, today=TODAY)
         billing = (self.root / "docs/specs/billing/spec.md").read_text(encoding="utf-8")
         self.assertIn("## Diagrams\n\n- [invoice-state](diagrams/invoice-state.md)\n"
                       "- [pay-activity](diagrams/pay-activity.md)\n\n## Requirements", billing)
         auth = (self.root / "docs/specs/auth/spec.md").read_text(encoding="utf-8")
         self.assertTrue(auth.startswith(auth_before.rstrip()))
         self.assertNotIn("## Diagrams", auth)
         self.assertEqual(STATE, (self.root / "docs/specs/billing/diagrams/invoice-state.md").read_text(encoding="utf-8"))
     ```
  3. Run `python3 -m pytest tests/workflow_core/test_specs.py tests/workflow_core/test_specs_archive_trace.py -k "diagram or templates_ship" -q`: expect 4 failures (`lint_living` returns `[]`; `lint_change` returns `[]`; `specs template activity.md` exits 2 with `unknown template: activity.md`; `## Diagrams` absent from the billing spec).
  4. Create `plugins/gin-workflow/src/templates/activity.md`:
     ````markdown
     # {{title}}

     <!-- Activity diagram of one feature: docs/specs/<capability>/diagrams/<feature>-activity.md. One flowchart
          from the trigger to each outcome; decisions as {question?} nodes. Cite it in 03-design.md ## Data Flow and
          link it from spec.md ## Diagrams. specs lint needs a mermaid block starting with flowchart. -->

     What the flow covers, in one or two sentences.

     ```mermaid
     flowchart TD
       start([Trigger]) --> step[Step]
       step --> done([Outcome])
     ```
     ````
     Create `plugins/gin-workflow/src/templates/state.md`:
     ````markdown
     # {{title}}

     <!-- State diagram of one entity: docs/specs/<capability>/diagrams/<entity>-state.md. Required when the entity
          has three or more states, or a transition allowed only under a condition (a role, a field value, a time
          limit); write the condition on the transition. specs lint needs a mermaid block starting with stateDiagram. -->

     Which entity, and where its state is stored, in one or two sentences.

     ```mermaid
     stateDiagram-v2
       [*] --> Draft
       Draft --> Submitted: owner submits
       Submitted --> [*]
     ```
     ````
     Replace `plugins/gin-workflow/src/templates/spec.md` with:
     ```markdown
     # {{capability}}

     ## Purpose

     ## Diagrams

     ## Requirements
     ```
     In `plugins/gin-workflow/src/templates/design.md`, under `## Data Flow`, add a blank line and:
     `<!-- Cite the capability's diagram files (docs/specs/<capability>/diagrams/<feature>-activity.md, <entity>-state.md); do not copy them here. -->`
  5. In `plugins/gin-workflow/src/scripts/workflow_core/specs.py`, after `lint_iterations`, add:
     ```python
     _MERMAID = re.compile(r"^```mermaid[ \t]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
     _DIAGRAM_KINDS = {"-activity.md": ("flowchart", "graph"), "-state.md": ("stateDiagram",)}


     def _mermaid_types(text: str) -> list[str]:
         """The first word of each ```mermaid block, skipping blank lines and `%%` comments."""
         types: list[str] = []
         for body in _MERMAID.findall(text):
             first = next((line.strip() for line in body.splitlines()
                           if line.strip() and not line.strip().startswith("%%")), "")
             types.append(first.split()[0] if first else "")
         return types


     def lint_diagrams(root: Path, cfg: Mapping[str, Any]) -> list[str]:
         """Every `<specs>/<cap>/diagrams/*-activity.md` / `*-state.md` holds a mermaid block of its kind."""
         errors: list[str] = []
         for path in sorted(specs_dir(root, cfg).glob("*/diagrams/*.md")):
             kinds = next((types for suffix, types in _DIAGRAM_KINDS.items() if path.name.endswith(suffix)), None)
             if kinds and not any(kind.startswith(kinds) for kind in _mermaid_types(path.read_text(encoding="utf-8"))):
                 errors.append(f"{shown(root, path)}: no mermaid block starting with {' or '.join(kinds)}")
         return errors
     ```
     Change the last line of `lint_living` to `return errors + lint_iterations(root, cfg) + lint_diagrams(root, cfg)`. In `lint_change`, replace its last line with:
     ```python
     base = specs_dir(root, cfg)
     for cap in sorted({block.cap for block in blocks if block.section in ("ADDED", "MODIFIED")}):
         if not any((base / cap / "diagrams").glob("*-activity.md")):
             errors.append(f"{cap}: no activity diagram in {shown(root, base / cap / 'diagrams')}/ "
                           "(gin-workflow specs template activity.md)")
     return errors + _untracked_citations(root, change) + lint_iterations(root, cfg) + lint_diagrams(root, cfg)
     ```
  6. In `plugins/gin-workflow/src/scripts/workflow_core/specs_archive.py`, in `archive`, replace the two lines of the `else:` branch that render the template:
     ```python
     title = block.cap.replace("-", " ").capitalize()
     texts[block.cap] = render(template_text(root, "spec.md"), {"capability": title}).splitlines()
     ```
     with:
     ```python
     title = block.cap.replace("-", " ").capitalize()
     text = render(template_text(root, "spec.md"), {"capability": title})
     links = "".join(f"- [{p.stem}](diagrams/{p.name})\n" for p in sorted((base / block.cap / "diagrams").glob("*.md")))
     texts[block.cap] = (text.replace("## Diagrams\n", f"## Diagrams\n\n{links}", 1) if links else text).splitlines()
     ```
  7. Run the command of step 3: expect 4 passed. Run `python3 -m pytest tests/workflow_core/test_specs.py tests/workflow_core/test_specs_reqs.py tests/workflow_core/test_specs_archive_trace.py tests/gin_qa/test_cases_cli.py tests/workflow_core/test_lifecycle_cli.py -q -n auto`: expect all passed (these are the files whose tests the new `lint_change` rule touches).
  8. Docs:
     - `docs/reference/cli.md:132`, in the `lint` row, after "without a `description.md`" insert: `, each `<specs>/<cap>/diagrams/*-activity.md` without a mermaid block starting with `flowchart` or `graph` and `*-state.md` without one starting with `stateDiagram`, and with `--change` each capability with an `ADDED` or `MODIFIED` block but no `*-activity.md``.
     - `docs/reference/cli.md:136`, the `archive` row: append `; a new capability's `spec.md` links each file in its `diagrams/` under `## Diagrams``.
     - `docs/guides/customizing-templates.md:27`: append `, `activity.md`, `state.md`` to the "Specs, stories, and roadmap" list; after line 40 add `| Activity and state diagrams (SDD layout) | `/gin-workflow:discuss` | `.agent-workflow/templates/activity.md`, `state.md` |`.
     - `docs/guides/customizing-templates.vi.md:27`: the same list entry; after line 40 add `| Sơ đồ activity và state (layout SDD) | `/gin-workflow:discuss` | `.agent-workflow/templates/activity.md`, `state.md` |`.
     - Run `gin-workflow docs check docs/reference/cli.md docs/guides/customizing-templates.md docs/guides/customizing-templates.vi.md`: expect exit 0.
  9. Commit: `feat(specs): activity and state diagrams per capability, checked by specs lint (gin-workflow-ycg8)`.
- **Acceptance criteria**: US-3 of the spec; the template and archive parts of US-1 and US-2 (`specs template activity.md` prints a `flowchart` block, `state.md` a `stateDiagram-v2` block, `spec.md` has `## Diagrams` before `## Requirements`; archive leaves diagram files unchanged and links them for a new capability).
- **Estimated complexity**: medium

### Track 2: `gin-sdd` discuss and the SDD guide state the diagram convention
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md:13` (discuss step 3)
  - Test `tests/workflow_core/test_skill_routing.py:70-73` (needles in `test_sdd_discuss_confirms_capabilities_before_ids`)
  - Modify `docs/guides/sdd.md:15-30,52,58,73-81` (layout tree, template list, assets paragraph, new `## Diagrams` section, `discuss` row)
  - Modify `docs/guides/sdd.vi.md:15-30,52,58,73-81` (same, Vietnamese)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** text edits with the exact wording given; `sonnet` rather than `haiku` because the skill must stay within its 6,000-character budget and the Vietnamese guide must match the English one.
- **Interfaces**: consumes the template names `activity.md` and `state.md`, the lint findings, and the archive behavior of Track 1.
- **Steps**:
  1. Failing test. In `test_sdd_discuss_confirms_capabilities_before_ids`, add to the needle tuple: `"`<specs>/<cap>/diagrams/<feature>-activity.md`"`, `"`specs template activity.md`"`, `"`specs template state.md`"`, `"three or more states"`, `"`## Data Flow`"`, `"`## Diagrams`"`.
  2. Run `python3 -m pytest tests/workflow_core/test_skill_routing.py -k capabilities_before_ids -q`: expect 1 failure.
  3. `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md`, step 3: after "never edit an older dated folder." insert:
     `Each feature gets an activity diagram `<specs>/<cap>/diagrams/<feature>-activity.md` from `specs template activity.md`; an entity with three or more states, or a transition allowed only under a condition, gets `<entity>-state.md` from `specs template state.md`. Cite them in `03-design.md` `## Data Flow`, list them in `## Capabilities Affected`, and link them from `## Diagrams` of an existing `spec.md` (archive links them for a new capability).`
  4. Run the command of step 2: expect 1 passed. Run `python3 -m pytest tests/workflow_core/test_token_budget.py -q`: expect all passed.
  5. `docs/guides/sdd.md`:
     - Layout tree: after the line `    <capability>/spec.md     requirements for one capability` add `    <capability>/diagrams/   activity and state diagrams (Mermaid)`.
     - Line 52: add `` `activity.md`, `state.md` `` to the template list after `` `iteration.md` ``.
     - Line 58: `Keep screenshots, mockups and diagrams for a capability` → `Keep screenshots and mockups for a capability`.
     - Before `## How the stages change`, add:
       ````markdown
       ## Diagrams

       Each feature has an activity diagram. An entity with three or more states, or a transition allowed only under a condition (a role, a field value, a time limit), also has a state diagram. Both are Mermaid files in the capability's folder:

       ```text
       docs/specs/orders/
         spec.md                  ## Diagrams links the files below
         diagrams/
           checkout-activity.md   flowchart: one feature, from the trigger to each outcome
           order-state.md         stateDiagram-v2: one entity's states and transitions
       ```

       Start them from `gin-workflow specs template activity.md` and `state.md`. Discuss edits them directly on the spec branch, as it does assets: they are not requirement blocks and never go through `02-spec-delta.md`. The change's `03-design.md` cites them under `## Data Flow` and `01-proposal.md` lists them under `## Capabilities Affected`, so they are committed and reviewed with the change. `specs archive` leaves them in place; when it creates `spec.md` for a new capability, it links every file in `diagrams/` under `## Diagrams`.

       `specs lint` reports a `*-activity.md` without a mermaid block starting with `flowchart` or `graph`, and a `*-state.md` without one starting with `stateDiagram`; other files in `diagrams/` are not checked. `specs lint --change` also reports each capability with an `ADDED` or `MODIFIED` block but no `*-activity.md`. When an entity needs a state diagram is a convention that lint does not check.
       ````
     - `discuss` row of the stage table: after "`03-design.md`" insert ", the capability's diagrams".
  6. `docs/guides/sdd.vi.md`, the same five edits:
     - Layout tree: the same added line (the tree is English in both pages).
     - Line 52: add `` `activity.md`, `state.md` `` to the template list.
     - Line 58: `Giữ screenshot, mockup và sơ đồ của một capability` → `Giữ screenshot và mockup của một capability`.
     - Before `## Các stage thay đổi thế nào { #how-the-stages-change }`, add `## Sơ đồ { #diagrams }` with the same `text` tree and:
       `Mỗi feature có một activity diagram. Một entity có từ ba trạng thái trở lên, hoặc có chuyển trạng thái chỉ được phép khi thỏa một điều kiện (một role, một giá trị field, một giới hạn thời gian), có thêm state diagram. Cả hai là file Mermaid trong thư mục của capability:`
       (before the tree) and, after it:
       `Bắt đầu từ `gin-workflow specs template activity.md` và `state.md`. Discuss sửa chúng trực tiếp trên spec branch, như với asset: chúng không phải requirement block và không bao giờ đi qua `02-spec-delta.md`. `03-design.md` của change trích dẫn chúng trong `## Data Flow` và `01-proposal.md` liệt kê chúng trong `## Capabilities Affected`, nên chúng được commit và review cùng change. `specs archive` để nguyên chúng; khi tạo `spec.md` cho một capability mới, nó link mọi file trong `diagrams/` dưới `## Diagrams`.`
       `specs lint` báo `*-activity.md` không có khối mermaid bắt đầu bằng `flowchart` hoặc `graph`, và `*-state.md` không có khối bắt đầu bằng `stateDiagram`; các file khác trong `diagrams/` không bị kiểm tra. `specs lint --change` còn báo mỗi capability có block `ADDED` hoặc `MODIFIED` mà không có `*-activity.md`. Khi nào một entity cần state diagram là quy ước mà lint không kiểm tra.`
     - `discuss` row (line 81): after "`03-design.md`" insert ", các sơ đồ của capability".
  7. Run `gin-workflow docs check docs/guides/sdd.md docs/guides/sdd.vi.md`: expect exit 0.
  8. Commit: `docs(sdd): activity and state diagrams in gin-sdd and the guide (gin-workflow-ycg8)`.
- **Acceptance criteria**: the skill and guide parts of US-1 and US-2 of the spec; `test_skill_routing.py` and `test_token_budget.py` pass.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/spec-diagrams`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes (pre-push hook).
- [ ] `gin-workflow docs check` exits 0 on the five changed docs pages.
- [ ] Manual: in a scratch SDD repo with `docs/specs/auth/spec.md` and a change adding `REQ-AUTH-003`, `gin-workflow specs lint --change ep-1` exits 1 with `auth: no activity diagram in docs/specs/auth/diagrams/ (gin-workflow specs template activity.md)`; after `mkdir -p docs/specs/auth/diagrams && gin-workflow specs template activity.md > docs/specs/auth/diagrams/login-activity.md` it prints `ok`.

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog (`haiku`, `sonnet`, `opus`; efforts `low`..`max`).
- The user may override `Model:` and `Effort:` before plan approval.
- The Parent Bead `gin-workflow-ycg8` stays open until the human-confirmed merge; track beads close after tests and review pass.

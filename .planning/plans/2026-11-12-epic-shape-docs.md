# Plan: One epic rule, owner roles, and prompts that match the starter

Spec: .planning/specs/2026-11-12-epic-shape-docs-design.md
Epic: gin-workflow-epic-shape-docs
Workflow: gin-workflow-epic-shape-docs

## Objective

The workspace guide and roles page state the epic rule (tracks per repository, QA tracks, shared packages), who runs discuss for capability and technical epics, how the contract is decided and approved, and the PM and tech lead roadmap duties; the brownfield starter and the skills reference show those rules in their tables, config, and prompts.

**Goal** (spec): The workspace guide, roles page, and brownfield starter state one epic per capability with one track per repository, who owns technical epics and milestone writes, and prompts that match the workspace layout.

**Architecture**: docs only. Each rule has one home: `docs/guides/workspace.md` for tracks per repository, QA tracks, shared packages, and the contract (Limits, a new shared-package section, Contract); `docs/roles.md` for who runs discuss and the roadmap duties. The starter (`docs/starters/brownfield.md`) and the skills reference (`docs/reference/skills.md`) are worked examples that link those homes. Every page's `.vi.md` translation follows.

**Tech Stack**: Markdown; `gin docs check`; `tests/workflow_core/test_docs_coverage.py`, `tests/workflow_core/test_walkthrough_docs.py`; the config schema (`workflow_core.schemas.validate_config_schema`) for the starter's `team` block.

**Global Constraints** (spec, verbatim):
- Docs only: no code, schema, or skill file changes.
- The starter's `requirement_confirmed` object form needs gin-workflow 3.1 or later, as its `ship` policy already does; the text says so once.
- `.vi.md` pages keep the English anchors of every heading, so links from other pages keep working.
- Out of scope: behaviour changes (each owning epic documents its own); an `area_lead` policy for `requirement_confirmed` or an epic kind on roadmap entries (code); the monorepo variant paragraph of the starter, which stays as the documented alternative.

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
- Problem statement: the starter's track table contradicts the guide's epic rule, QA and shared-package work have no rule, only the BA runs discuss and the BA's prompt asks for the REST contract, the contract freezes before the leads decide it, roadmap duties are half stated, and the skills reference shows a monorepo and `legacy/` tracks.
- Success criteria: spec R1 to R10; US-1 to US-4 checked on the pages; docs checks and tests pass.
- Constraints: Global Constraints above.
- Non-goals: see Global Constraints.

## Approach Options
### Option 1: rules in the guide and roles page, examples follow (confirmed)
- Summary: write each rule once in `workspace.md` or `roles.md`; the starter and the skills reference show it and link it.
- Pros: one home per fact; examples cannot drift from a second statement of the rule.
- Cons: readers of the starter follow links for the rule text.

### Option 2: rules restated in the starter
- Summary: the starter repeats every rule next to its example.
- Pros: the starter reads on its own.
- Cons: two homes per fact (docs#one-home); rejected.

### Recommended Approach
- Selected option: Option 1, with the contract decided as technical questions in plan and approved by the area leads (confirmed in `/discuss` on 2026-11-12).
- Rationale: docs only, no new policy code, and the plan pull request already needs every touched area's lead.

## Scope
- In scope: R1 to R10.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2's starter and prompts link the sections Track 1 writes; one lane keeps the anchors in place first.
```

## Tasks

### Track 1: Rules in the workspace guide and the roles page
- **Dependencies**: none
- **Files**:
  - Modify `docs/guides/workspace.md:118-120` (Contract), `:136-140` (Limits), new section `## Shared packages` before `## Commands` (`:122`), and `:65-80` (PM and BA: link to roles for discuss owners)
  - Modify `docs/guides/workspace.vi.md` (same sections; anchors `{ #contract }`, `{ #limits }`, `{ #shared-packages }`)
  - Modify `docs/roles.md:20-22` (PM, BA, Tech lead rows) and `:70-76` (Keeping work apart, only if a sentence there restates discuss ownership)
  - Modify `docs/roles.vi.md` (same)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** documentation of existing behaviour on two pages and their translations, with the wording fixed by the spec.
- **Steps**:
  1. `workspace.md` Limits, first bullet (R1, R2): "A capability epic has at least one track in each repository it changes, and a track never spans two repositories; one repository may hold several tracks of the epic. QA work for the capability is one or more tracks in the `shape: qa` repository inside the same epic, not a separate epic."
  2. `workspace.md` new `## Shared packages` before `## Commands` (R3): a shared package is a `shape: library` entry of `workspace.repos`; a change to it is a track in that repository inside the capability epic that needs it; each app that adopts the change does it in its own track, which depends on the library track (`gin task dep add`); publishing the package and bumping its version in the apps follow the team's release practice, a convention gin does not enforce; gin pins no child versions (link the Limits bullet, do not restate it).
  3. `workspace.md` `## Contract` (R6): replace "and `requirement_confirmed` is the moment it is frozen" with: the business part of the spec is frozen at `requirement_confirmed`; `/gin:discuss` records each contract detail (path, method, fields, error codes) as `- TQ-<n>:` under `## Open Technical Questions` ([team mode](team.md)), `/gin:plan` answers each with a `Decision:` line, and the contract is frozen at `plan_approved`, approved by the lead of each area the plan touches (`plan_approved: area_lead`), so the providing and the consuming area both approve it. Keep the OpenAPI file, mocks, change-after-approval, and integration-epic sentences.
  4. `workspace.md` `## PM and BA`: after the table, one sentence linking [who runs discuss](../roles.md#who-owns-what) instead of restating it.
  5. `roles.md` (R4, R8):
     - PM row, Skills cell: after the existing milestone text add "; owns the roadmap deadline and scope".
     - BA row: Skills keep `/gin:discuss`; add "(capability epics)".
     - Tech lead row: Skills add "`/gin:discuss` (purely technical epics, such as an integration or platform epic)"; Approves add "`roadmap` order and technical epics with the PM, when listed in `team.approvals.roadmap`".
     - Under the table, one sentence: "The BA runs discuss for a capability epic and writes each contract detail as a technical question that the tech lead decides in plan; see [the contract](guides/workspace.md#contract)."
  6. `workspace.vi.md` and `roles.vi.md`: the same facts in Vietnamese, code and paths verbatim, English anchors on every heading.
  7. `gin docs check` on the four pages → ok; check every new link and anchor resolves; `python3 -m pytest tests/workflow_core/test_docs_coverage.py -q` → pass.
  8. Commit: `docs(workspace): tracks per repository, QA and shared-package tracks, contract frozen at plan approval; discuss owners in roles (gin-workflow-epic-shape-docs)`.
- **Acceptance criteria**: R1 (guide part), R2, R3, R4, R6, R8, R10 for these pages; US-1 criteria 1 to 3; US-2 criteria 2 and 4; US-3.
- **Estimated complexity**: low

### Track 2: The starter and the skills reference follow the rules
- **Dependencies**: Track 1
- **Files**:
  - Modify `docs/starters/brownfield.md:50-60` (approvals block and its explanation), `:301-334` (Discuss an epic, prompt, "Legacy behavior and living specs" REST paragraph), `:336-394` (Plan and orchestrate: REST contract as the tech lead's work, track table `Repo` column, epic-rule link, diagram label)
  - Modify `docs/starters/brownfield.vi.md` (same)
  - Modify `docs/reference/skills.md:117-191` (setup, team-setup as lead, discuss, plan prompts)
  - Modify `docs/reference/skills.vi.md` (same prompts; prompts stay in English as they are today if the translation keeps them verbatim)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** many coordinated edits across a long starter, a reference page, and two translations, where the config block must stay valid and every prompt must match the starter.
- **Steps**:
  1. Starter approvals (R7): set `requirement_confirmed: {all: [ba], any: [be_lead, fe_lead]}`. Rewrite the explanation per `docs/guides/team.md` (Approval policies): when An, the only `ba`, authors a spec, the `ba` role is skipped with a note and Binh or Hoa approves; when Binh authors a technical epic's spec, An and Hoa approve; Lan's roadmap pull requests are still approved by Binh (`roadmap: [pm, be_lead]`). State once that the object form needs gin-workflow 3.1 or later (it already says so for `ship`: keep one sentence covering both).
  2. Validate the block: run
     ```bash
     python3 - <<'EOF'
     import re, sys, yaml
     sys.path.insert(0, "plugins/gin-workflow/src/scripts")
     from workflow_core.schemas import validate_config_schema
     text = open("docs/starters/brownfield.md", encoding="utf-8").read()
     block = next(b for b in re.findall(r"```yaml\n(.*?)```", text, re.S) if b.startswith("team:"))
     validate_config_schema({"schema_version": "2.10", **yaml.safe_load(block)})
     print("ok")
     EOF
     ```
     → `ok`.
  3. Discuss an epic (R5): the prompt drops the "API contract: …" line; the "Put in the prompt" sentence no longer asks for the REST contract and says discuss records each contract detail as a technical question for the tech lead (link `../guides/workspace.md#contract`); the "Gate or approval" paragraph names the new policy.
  4. Move the paragraph "Write the REST contract of each endpoint the same way…" (`:334`) to `## Plan and orchestrate` as the tech lead's work: plan answers each `TQ-<n>` with the endpoint's path, method, request, response, and error codes, and the plan pull request is approved by Binh and Hoa as the leads of `api` and `web`.
  5. Track table (R1): add a `Repo` column: tracks 1 and 6 `qa`, track 2 `services/catalog-api`, tracks 3 and 4 `apps/web-shop`, track 5 `services/order-api` (and drop the parenthesis from track 5's Area cell). Before the table, one sentence: one epic for the capability, with tracks in each repository it changes ([workspace limits](../guides/workspace.md#limits)).
  6. Diagram (R9): `T5["Track 5 legacy cutover"]` → `T5["Track 5 router cutover"]`.
  7. `docs/reference/skills.md` (R9):
     - setup prompt (`:117-123`): `Stage: brownfield. Shape: fullstack. Workspace: yes.` and the starter's repositories line (`legacy/shop-portal (Struts, frozen), services/order-api and services/catalog-api (Spring Boot, Maven), apps/web-shop and apps/web-admin (React, npm), qa (automation), .beads (shared Beads database)`).
     - team-setup as lead (`:125-134`): members as the starter (`hoa@example.com fe_lead and fe_dev`); `Areas: legacy legacy/shop-portal/** (read-only), api services/** led by be_lead, web apps/** led by fe_lead, qa qa/** led by be_lead.`; `Approvals: requirement_confirmed {all: [ba], any: [be_lead, fe_lead]}, plan_approved area_lead, ship {all: [qe], any: [be_lead, fe_lead]}, roadmap [pm, be_lead].`
     - discuss prompt (`:175-180`): remove "give an explicit REST contract per endpoint"; keep the business content.
     - plan prompt (`:182-191`): each track adds `Repo:` and paths inside that repository: Track 1 `Repo: qa`, `Create cases/catalog/**`; Track 2 `Repo: services/catalog-api`; Tracks 3 and 4 `Repo: apps/web-shop`; Track 5 `Area api, Repo: services/order-api, … Router cutover to the facade`; Track 6 `Repo: qa`, `Create e2e/catalog/...`. Add one line: answer each `TQ-<n>` with the endpoint contract. No track names `legacy/`.
  8. `brownfield.vi.md` and `skills.vi.md`: the same changes; code, config, and prompt text as in the English page; English anchors on headings.
  9. `grep -n "legacy/" docs/reference/skills.md docs/starters/brownfield.md` shows no track in `legacy/`; `gin docs check` on the four pages → ok; links and anchors resolve; `python3 -m pytest tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_walkthrough_docs.py -q` → pass.
  10. Commit: `docs(starters): approvals with the BA and a lead, contract as technical questions, tracks per repository, prompts in the workspace layout (gin-workflow-epic-shape-docs)`.
- **Acceptance criteria**: R1 (starter part), R5, R7, R9, R10 for these pages; US-1 criterion 4; US-2 criteria 1 and 3; US-4.
- **Estimated complexity**: medium

## Integration
- **Branch**: `feat/epic-shape-docs`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto -q` passes (pre-push runs it).
- [ ] `gin docs check` on the changed pages reports no findings.
- [ ] The starter's `team` block validates against the config schema (Track 2 step 2).

## Notes
- Omit `Effort:` when the catalog lists no efforts.
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- Deliverable merge-holds (e.g. "remain open until human-confirmed merge") apply exclusively to the Parent Bead. Individual track beads must close upon passing tests and code review to unblock downstream dependent tracks.
- `test_walkthrough_docs.py` checks that every `gin <command>` cited in the starter exists in the CLI reference; avoid prose like `gin accept` that reads as a command.

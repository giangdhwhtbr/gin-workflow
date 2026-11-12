# Plan: Epic kinds: capability, technical, parity

Spec: .planning/specs/2026-11-12-epic-kinds-design.md
Workflow: epic-kinds

## Objective

Every epic has a kind (`capability` default, `technical`, `parity`) on its bead (`kind:<kind>` label), its roadmap entry, and its spec (`Kind:` line). Spec lint relaxes per kind (technical: no user stories, an empty or missing SDD spec delta; parity: a `Parity with:` line naming confirmed legacy captures). `team.approvals.requirement_confirmed` may be a per-kind map, and record, team check, and waivers pick the policy of the epic's kind. Discuss, roadmap, and docs follow.

**Goal** (spec): Every epic carries a kind, `capability`, `technical`, or `parity`, and the kind decides what `/gin:discuss` writes, what spec lint requires, and which roles approve the spec in team mode, so technical epics stop producing BA-style documents and waiting for BA or PM review, and 1-1 legacy ports need only a confirmed capture and the deltas.

**Architecture**: a new module `workflow_core/epic_kind.py` owns the kind values, parsing (`Kind:` line, `kind:` label), and the lookup that combines bead and spec. `specs.py` (`lint_design_spec`, `lint_change`, `change_kind`) and `specs_trace`/`specs_archive` use it for lint and empty technical deltas. `team.py` gains `policy_for(team, gate, kind)` used by every approval function; `schemas.py` accepts the kind map; `lifecycle_cli.py` (record, unblock) and `team_cli.py` (check) resolve the kind and pass it. Skills read one shared reference `references/epic-kinds.md`; roadmap uses its `capability-epics.md` reference for the field and the label.

**Tech Stack**: Python 3 standard library; unittest/pytest (`tests/workflow_core/test_specs.py`, `test_specs_archive_trace.py`, `test_team_gates.py`, `test_team_init.py`, `test_lifecycle_cli.py`, `test_token_budget.py`, `test_docs_coverage.py`); `gin docs check`.

**Global Constraints** (spec, verbatim):
- Default `capability` everywhere: no change for epics, specs, or configs without a kind.
- The map form is new configuration: a project using it needs this gin version; older gin refuses it at schema validation. Docs say so.
- `kind:` labels are new; every current reader of epic labels tolerates extra labels (milestone, team ready); gin-console reads no labels.
- A spec/bead kind mismatch is a refusal with both values named, never a silent choice.
- Skill budgets stay within limits (`tests/workflow_core/test_token_budget.py`).
- Out of scope: work split by role and assignment; showing the kind in `/gin:progress` or gin-console; changing an epic's kind after its spec is confirmed.

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
- Problem statement: technical epics follow the business spec flow and need BA/PM approval; there is no epic kind anywhere.
- Success criteria: spec R1 to R11; US-1 to US-4 as tests (code) or checked text (skills, docs); existing tests pass; budgets hold.
- Constraints: Global Constraints above.
- Non-goals: see Global Constraints.

## Approach Options
### Option 1: kind label + spec line, per-kind map inside `requirement_confirmed` (confirmed)
- Summary: as the Architecture above.
- Pros: one gate, backward compatible, one lookup module.
- Cons: every approval function takes a `kind`.

### Option 2: separate gate keys per kind
- Summary: `requirement_confirmed_technical`, `requirement_confirmed_parity`.
- Pros: flat config.
- Cons: more gate names in waivers, strict mode, and team init; rejected in `/discuss`.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-12).
- Rationale: smallest change with a single default path.

## Scope
- In scope: R1 to R11.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 uses Track 1's epic_kind module, skills and docs describe both; one lane.
```

## Tasks

`S` is `plugins/gin-workflow/src/scripts/workflow_core`.

### Track 1: Kind values, spec lint per kind, and empty technical deltas
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/epic_kind.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py:70-101` (`lint_design_spec`), `:338-351` (`delta_blocks`), `:461-504` (`lint_change`); new `change_kind`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py:112-114` (`lint --spec` passes the root)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_trace.py:38-41`, `plugins/gin-workflow/src/scripts/workflow_core/specs_archive.py:54-60` (empty technical delta)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:253-263` (`_spec_lint_errors` passes the root)
  - Create `plugins/gin-workflow/src/templates/technical-design.md`; Modify `plugins/gin-workflow/src/templates/design-spec.md`, `plugins/gin-workflow/src/templates/proposal.md` (a `Kind: capability` line)
  - Test `tests/workflow_core/test_epic_kind.py` (new), `tests/workflow_core/test_specs.py`, `tests/workflow_core/test_specs_archive_trace.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded changes inside the specs module with every rule and message fixed by the spec.
- **Interfaces**:
  - `epic_kind.KINDS = ("capability", "technical", "parity")`, `epic_kind.DEFAULT = "capability"`.
  - `epic_kind.spec_kind(text: str) -> str | None`: the value of the first `^Kind:\s*(\S+)` line outside code fences, or None.
  - `epic_kind.label_kind(labels: Sequence[str]) -> str | None`: the value of the first `kind:<value>` label, or None.
  - `epic_kind.invalid(value: str | None) -> str | None`: an error `"Kind: <value> is not one of capability, technical, parity"` for a value outside KINDS, else None.
  - `epic_kind.parity_sources(text: str) -> list[str]`: backticked paths on the `Parity with:` line (empty when absent).
  - `epic_kind.parity_errors(root: Path, text: str, label: str) -> list[str]`: `"<label>: Kind: parity needs a 'Parity with:' line naming confirmed legacy asset folders"` when no path; per path, `"<label>: Parity with: <path> <reason>"` with reason `is missing`, `has no description.md`, `is not Kind: legacy`, or `is not confirmed` (reuse `specs_assets.confirmed_date` and read `Kind:` from `description.md`). Paths are relative to `root`.
  - `specs.lint_design_spec(path: Path, root: Path | None = None) -> list[str]`: reports `invalid(spec_kind)`; with `technical` or `parity` it does not add "no user stories"; with `parity` it adds `parity_errors(root or <git toplevel of path>, text, shown path)`.
  - `specs.change_kind(change: Path) -> str`: `spec_kind` of `change_file(change, "proposal")`, else DEFAULT.
  - `specs.delta_blocks(root, change)`: for a `technical` change with no spec-delta file, returns `([], [])` instead of the missing-file error.
  - `specs.lint_change(...)`: also reports `invalid` of the proposal's `Kind:` and, for `parity`, `parity_errors` on the proposal text.
  - `specs_trace.trace` returns `{"change", "requirements": [], "missing": [], "skipped": [...]}` for a change without blocks; `specs_archive.archive` of a change without blocks moves the folder to the archive and updates no spec (`"specs": []`).
- **Steps**:
  1. Failing tests: `tests/workflow_core/test_epic_kind.py` for every interface function (fenced `Kind:` ignored; invalid value message; label parsing; parity errors for each reason with fixture folders built under a temp root: `docs/specs/catalog/assets/2026-11-01/description.md` with `Kind: legacy` and `Confirmed: 2026-11-02`, an unconfirmed one, a `Kind: new` one, a missing one). In `test_specs.py`: a `Kind: technical` spec without stories lints `[]`; a `Kind: parity` spec naming the confirmed legacy folder and without stories lints `[]`; the same without `Parity with:` or with each bad folder fails with the messages above; `Kind: other` fails; a spec without `Kind:` still needs stories (today's message). SDD (`test_specs_archive_trace.py`): a change whose `01-proposal.md` says `Kind: technical` and has no `02-spec-delta.md` lints without the missing-file error, traces to empty, and archives with `specs == []`; a technical change that does contain an `ADDED` block still needs its activity diagram.
  2. Run `python3 -m pytest tests/workflow_core/test_epic_kind.py tests/workflow_core/test_specs.py tests/workflow_core/test_specs_archive_trace.py -q` → new tests fail.
  3. Implement per the interfaces; `specs_cli` and `lifecycle_cli._spec_lint_errors` pass the repository root to `lint_design_spec`.
  4. Templates: `technical-design.md` with `# {{title}}`, `Epic: {{epic}}`, `Kind: technical`, `Status: draft for user review.`, then `## Goal and scope`, `## Approach`, `## Risks and rollback`, `## Testing`, `## Open Technical Questions` (each with a one-line HTML comment like `design-spec.md`'s); `design-spec.md` and `proposal.md` gain `Kind: capability` after `Epic:` with a comment naming the other kinds and `technical-design.md`.
  5. Run step 2 → pass; `python3 -m pytest tests/workflow_core -q -n auto -k "specs or kind or lifecycle"` → pass.
  6. Commit: `feat(specs): epic kinds in spec lint, technical design template, parity sources, empty technical deltas (epic-kinds)`.
- **Acceptance criteria**: R1, R4 (spec line and lint), R5, R6, R7; US-1 criteria 1, 2, 4; US-2.
- **Estimated complexity**: medium

### Track 2: Approval policy per kind and kind lookup
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/schemas.py:19-22,51-58` (`_KIND_MAP`, `requirement_confirmed`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py:110-145` (validation, aws identity, strict), `:446-512` (`check_approval`), `:536-551` (`gate_roles`, `has_policy`, `can_waive`), `:576-612` (`verify_gate`, `authorize_record`, `authorize_waiver`); new `policy_for`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_init.py:45-46,159-170` (roles of every kind)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py:95-115` (`check --workflow-id`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:292-340` (record: kind lookup and mismatch), `:515-525` (unblock: kind)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/epic_kind.py` (`lookup`)
  - Test `tests/workflow_core/test_team_gates.py`, `tests/workflow_core/test_team_init.py`, `tests/workflow_core/test_lifecycle_cli.py`, `tests/workflow_core/test_epic_kind.py`, the schema tests that cover `team.approvals` (search `requirement_confirmed` under `tests/workflow_core`)
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** a security-relevant gate change across schema, team policy, three CLIs, and team init, where a wrong default would let a spec through without its approvers.
- **Interfaces**:
  - Schema: `_KIND_MAP = {"type": "object", "required": ["capability"], "properties": {k: _GATE for k in KINDS}, "additionalProperties": False}`; `requirement_confirmed: {"anyOf": [_ROLES, _POLICY, _KIND_MAP]}`. The map's error names the unknown key or the missing `capability`.
  - `team.policy_for(team: TeamConfig, gate: str, kind: str | None = None) -> Any`: the gate's policy; for a kind map (a Mapping with a `capability` key), `map.get(kind or DEFAULT, map["capability"])`.
  - `check_approval(..., kind=None)`, `gate_roles(gate, team, kind=None)`, `has_policy(gate, team, kind=None)`, `can_waive(member, gate, team, kind=None)`, `verify_gate(..., kind=None)`, `authorize_record(..., kind=None)`, `authorize_waiver(..., kind=None)` all read `policy_for`.
  - Validation: roles in every kind's policy must be held; `all`/`any` both empty is refused per kind; aws-identity approving roles include every kind's roles; `team.strict` needs a role policy for the `capability` entry (and for each other kind present).
  - `team_init`: CODEOWNERS spec owners are the union of every kind's roles plus leads.
  - `epic_kind.lookup(root: Path, workflow_id: str | None, spec_path: Path | None) -> tuple[str, str | None]`: `(kind, error)`. Bead kind from `tasks.query(root, ["show", workflow_id, "--json"])` labels when the workflow id is a bead; spec kind from `spec_path` when it is a file; both present and different → error `"kind mismatch: epic <id> is kind:<a>, spec <path> says Kind: <b>"`; either present → that kind; neither → DEFAULT.
  - `gin record requirement-confirmed`: calls `lookup(repo, args.workflow_id, evidence or --spec path)`; a mismatch returns status `rejected`, exit 1; passes `kind` to `authorize_record`.
  - `gin unblock --gate requirement_confirmed --workflow-id W`: passes `lookup(repo, W, None)[0]` to `authorize_waiver`.
  - `gin team check --gate requirement_confirmed <url> [--workflow-id W]`: kind from `lookup(root, W, <local file of the resolved artifact>)`; JSON adds `"kind"`.
- **Steps**:
  1. Failing tests: schema accepts the map and today's forms, refuses a map without `capability` and with `review:` (unknown key); `policy_for` default and fallback; `check_approval` passes a technical spec PR approved by `be_lead` under `{capability: [ba], technical: [be_lead]}` and fails the same PR for `capability`; `can_waive` per kind; validation of roles held per kind; team init owners union; lifecycle: record refuses a mismatch (bead `kind:technical`, spec `Kind: capability`) naming both, and uses the technical policy when they agree (use the existing fake host and fake bd fixtures in `tests/workflow_core/team_fixtures.py` and `test_team_gates.py`); `team check --workflow-id` reports `"kind"`.
  2. Run the touched test files → new tests fail.
  3. Implement per the interfaces.
  4. Run the touched test files → pass; `python3 -m pytest tests/workflow_core -q -n auto -k "team or lifecycle or schema or kind"` → pass.
  5. Commit: `feat(team): requirement_confirmed policy per epic kind, kind lookup in record, check, and unblock (epic-kinds)`.
- **Acceptance criteria**: R2 (label read), R4 (mismatch refusal), R8, R9; US-1 criterion 3; US-3 criteria 2 and 3; US-4.
- **Estimated complexity**: high

### Track 3: Skills, roadmap kind, and the epic-kinds reference
- **Dependencies**: Track 2
- **Files**:
  - Create `plugins/gin-workflow/src/references/epic-kinds.md`
  - Modify `plugins/gin-workflow/src/skills/discuss/SKILL.md` (one line linking the reference)
  - Modify `plugins/gin-workflow/src/skills/roadmap/SKILL.md:27-33` (name `Kind:` in the field list and `kind:<kind>` in the sync labels, offset by shortening the `Complexity:` parenthesis; the file is 11,997 of 12,000)
  - Modify `plugins/gin-workflow/src/skills/roadmap/references/capability-epics.md` (Kind field and label rules; integration epics are technical)
  - Modify `plugins/gin-workflow/src/templates/epic.md`, `plugins/gin-workflow/src/templates/roadmap.md` (`Kind:` line)
  - Test `tests/workflow_core/test_token_budget.py` (existing), `tests/workflow_core/test_skill_routing.py` (existing)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** skill text under hard budgets (roadmap SKILL.md has 3 characters left; team and sdd skills are not touched) and one new reference that must match Tracks 1 and 2.
- **Steps**:
  1. `references/epic-kinds.md` (≤ 2,500 characters): the three kinds and the default; where the kind lives (label, `Kind:` line) and that a mismatch is refused; discuss per kind: capability as today; technical: technical questions only, `gin specs template technical-design.md` (legacy) or `03-design.md` with an empty or missing spec delta (SDD), no user stories, use cases, or activity diagrams; parity: read the confirmed `Kind: legacy` folders, write `Parity with:` with their backticked paths, ask and write stories or REQs only for deltas; when the epic has no `kind:` label, ask once and add it (`gin task update <epic> --add-label kind:<kind>`); approval follows `team.approvals.requirement_confirmed` for the kind.
  2. `discuss/SKILL.md`: one line in "Roadmap epic" or step 2: "Read the epic's kind (`kind:` label, default `capability`) and follow [epic kinds](../../references/epic-kinds.md)." Check the discuss stage chain stays ≤ 12,000.
  3. Roadmap: `capability-epics.md` adds a `## Kind` section (each entry has `Kind: capability|technical|parity`; propose it per epic; integration epics are `technical`; create epics with `--labels roadmap,kind:<kind>`; on a changed kind, `gin task update <id> --remove-label kind:<old> --add-label kind:<new>` unless `in_progress` or adopted, then the `[gin roadmap]` comment rule applies). `roadmap/SKILL.md`: add `Kind:` to the step 4 field list and `kind:<kind>` to the step 5 create command, shortening the `Complexity:` driver list so the file stays ≤ 12,000 characters; templates `epic.md` and `roadmap.md` gain a `Kind:` line.
  4. `python3 -c "import pathlib;print(len(pathlib.Path('plugins/gin-workflow/src/skills/roadmap/SKILL.md').read_text(encoding='utf-8')))"` ≤ 12000; `python3 -m pytest tests/workflow_core/test_token_budget.py tests/workflow_core/test_skill_routing.py -q` → pass.
  5. Commit: `feat(skills): epic kinds reference for discuss; Kind field and label in the roadmap (epic-kinds)`.
- **Acceptance criteria**: R2 (roadmap and discuss write the label), R3, R10; US-3 criterion 1; budgets hold.
- **Estimated complexity**: medium

### Track 4: Docs for epic kinds
- **Dependencies**: Track 3
- **Files**:
  - Modify `docs/concepts/lifecycle.md` (gates table and Variations: kinds)
  - Modify `docs/guides/team.md` and `docs/guides/team.vi.md` (Approval policies: the per-kind map with an example and the version note)
  - Modify `docs/reference/config.md` (`team.approvals.requirement_confirmed` map)
  - Modify `docs/reference/cli.md` (`specs template technical-design.md`, lint rules per kind, `team check --workflow-id`)
  - Modify `docs/roles.md`, `docs/roles.vi.md`, `docs/guides/ba.md`, `docs/guides/ba.vi.md`, `docs/guides/sdd.md`, `docs/guides/sdd.vi.md` (one home: the kinds in `lifecycle.md`, approval in `team.md`, SDD rules in `sdd.md`; others link)
  - Modify `docs/starters/brownfield.md`, `docs/starters/brownfield.vi.md` (approvals map example `capability: {all: [ba], any: [be_lead, fe_lead]}`, `technical: [be_lead, fe_lead]`, `parity: [ba]`, and one technical and one parity epic named in the roadmap section)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** documentation of shipped behaviour across eight pages and five translations, with one home per fact and a starter config that must validate.
- **Steps**:
  1. Write each page per the Files notes; the starter's `team` block validates with the schema check used in `gin-workflow-epic-shape-docs` (`validate_config_schema({"schema_version": "2.10", **yaml.safe_load(block)})`).
  2. `gin docs check` on every changed page → ok; links resolve; `python3 -m pytest tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_walkthrough_docs.py -q` → pass; `python3 -m pytest -n auto -q` → pass.
  3. Commit: `docs: epic kinds, per-kind spec approval, technical design and parity specs (epic-kinds)`.
- **Acceptance criteria**: R11; budgets and docs checks hold.
- **Estimated complexity**: medium

## Integration
- **Branch**: `feat/epic-kinds`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto -q` passes (pre-push runs it).
- [ ] `gin docs check` on the changed pages reports no findings.
- [ ] Manual: after `install.sh`, `gin specs template technical-design.md` prints the template and `gin specs lint --spec` accepts a technical spec without stories.

## Notes
- Omit `Effort:` when the catalog lists no efforts.
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- Deliverable merge-holds (e.g. "remain open until human-confirmed merge") apply exclusively to the Parent Bead. Individual track beads must close upon passing tests and code review to unblock downstream dependent tracks.
- Without a roadmap epic, orchestrate creates the parent epic bead; give it the label `kind:capability` (this epic is a gin capability).
- Do not propose a deferral for an IMPORTANT review finding before the user decides (review-ledger bug `gin-workflow-syug`).

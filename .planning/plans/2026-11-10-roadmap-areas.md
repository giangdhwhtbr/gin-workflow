# Plan: Roadmap areas on tracks, contract and integration epics

Spec: .planning/specs/2026-11-10-roadmap-areas-design.md
Epic: gin-workflow-roadmap-areas
Workflow: gin-workflow-roadmap-areas

## Objective

Roadmap epics list `Tracks:` per repository or area with `Area:`; plan starts tracks from them; orchestrate labels track beads `area:<name>`; the workspace guide states the confirmed spec is the API contract; the roadmap proposes one `<capability> integration` epic per capability. Skill and docs text only; budgets hold.

**Goal** (spec): a roadmap plans by area and contract: each roadmap epic lists its tracks per repository or area with `Area:`, orchestrate turns a track's area into an `area:<name>` label, the confirmed spec is the API contract, and `/gin:roadmap --milestone` schedules one integration epic per capability so the flag flip is tracked in Beads.

**Architecture**: a new roadmap reference file holds the epic entry format and the integration epic rule; the roadmap, plan, and orchestrate skills each gain one sentence; the workspace guide gains a Contract section; the way-of-working Integration block gains one sentence. No code.

**Tech Stack**: Markdown; existing budget tests in `tests/workflow_core/test_token_budget.py` (`test_each_stage_chain_within_budget`: every stage chain at most 12,000 characters; `test_roadmap_skill_within_12000`: roadmap `SKILL.md` at most 12,000 and `way-of-working.md` at most 6,000); `gin docs check`.

**Global Constraints** (spec, verbatim):
- R2. The roadmap `SKILL.md` ... stays within 12,000 characters; any characters added are cut elsewhere without dropping a rule.
- No CLI, JSON, or config change; gin-console is unaffected.
- Roadmap files without `Tracks:` stay valid; plan then derives tracks as today.
- Projects without team areas get no `Area:` lines and no `area:` labels, as today.
- Out of scope: epic-level area and a `check-plan` rule for it; a separate contract epic; a feature grouping above epics; read-only sibling inputs (`gin-workflow-ws-branch-model`); the epic-rule rewrite (`gin-workflow-epic-shape-docs`); new code checks.

Measured budgets on 2026-11-10 (`cd plugins/gin-workflow/src/scripts && python3 -m workflow_core.budget --report --src ../`): plan chain 11,994 of 12,000; orchestrate chain 7,535; roadmap `SKILL.md` 11,985 of 12,000; `way-of-working.md` 3,669 of 6,000.

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
- Problem statement: track areas exist and are enforced, but the roadmap never names tracks or areas, the area label lives only in the team skill, no contract location is defined, and integration is not tracked work.
- Success criteria: spec R1 to R7; US-1 to US-3 acceptance criteria; budget tests and `gin docs check` pass.
- Constraints: Global Constraints above.
- Non-goals: see Global Constraints.

## Approach Options
### Option 1: skill and docs text, guidance in a new reference
- Summary: one new reference file plus one sentence per skill; cuts in the plan and roadmap skills keep budgets.
- Pros: no code; the roadmap skill stays under its limit by moving detail into a reference.
- Cons: `Tracks:` and the integration epic are guidance, not enforced.

### Option 2: code checks as well
- Summary: `check-plan` compares `Area:` with `Repo:`; `gin milestone` warns when an integration epic shares a milestone with its blockers.
- Pros: enforced.
- Cons: code for cases not yet seen; confirmed against in `/discuss`.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-10).
- Rationale: meets R1 to R7 with the smallest change.

## Scope
- In scope: R1 to R7.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: One small docs track; the budgets of three skills must be checked together.
```

## Tasks

### Track 1: Capability epic entries, area labels, contract, and integration epics
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/skills/roadmap/references/capability-epics.md`
  - Modify `plugins/gin-workflow/src/skills/roadmap/SKILL.md:27` (step 4: one pointer sentence; an equal cut in the same step)
  - Modify `plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:14-15` (Integration block: one sentence)
  - Modify `plugins/gin-workflow/src/skills/plan/SKILL.md` (one sentence near line 21; an equal or larger cut elsewhere in the plan chain)
  - Modify `plugins/gin-workflow/src/skills/orchestrate/SKILL.md:21` (Track Beads bullet: area label)
  - Modify `docs/guides/workspace.md` (new `## Contract` section before `## Commands`; the first bullet of `## Limits`)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** documentation, but three skills sit at their character limits, so every added sentence needs an equal cut that drops no rule; that needs judgement above the weakest route.
- **Interfaces**: roadmap epic entry line `Tracks: <repo or area>: <what it builds>; ...` with `Area:` per track; epic title `<capability> integration`; label `area:<name>` on track beads.
- **Steps**:
  1. Record the baseline: `cd plugins/gin-workflow/src/scripts && python3 -m workflow_core.budget --report --src ../ && cd -` and `wc -m plugins/gin-workflow/src/skills/roadmap/SKILL.md plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md`.
  2. Create `plugins/gin-workflow/src/skills/roadmap/references/capability-epics.md` with this content:
     ```markdown
     # Capability epics: tracks, areas, contract, integration

     Read on `/roadmap` when presenting epics (step 4) and when adopting epics into a milestone.

     ## One epic per capability
     An epic delivers one capability. In a workspace it holds one track per repository; with team areas and no workspace, one track per area. A track never spans two repositories or two areas.

     ## Tracks line
     Add `Tracks:` to the epic entry when the project has a workspace or team areas, one item per track: `Tracks: services/catalog-api: browse endpoints (Area: backend); apps/web-shop: catalog pages (Area: frontend)`. Each track names the repository or area and what it builds, then the `Area:` it carries. Omit the line without a workspace and without areas. `/plan` starts its tracks from this line and may split a track further.

     ## Contract
     The confirmed spec of the epic is the API contract of the capability. `requirement_confirmed` freezes it. The service and app tracks of the epic build against that spec, and the app track generates its mocks from it. No separate contract epic is created.

     ## Integration epic
     With `--milestone`, propose one epic titled `<capability> integration` for each capability listed in `Integrates:` of the milestone block. It depends on the capability's build epics, its scope is "turn the flag on and run the E2E suite against the real API", and it belongs to the milestone of that integration point. It carries `Tracks:` only when the flag flip or the E2E run belongs to a specific repository.
     ```
  3. In roadmap `SKILL.md` step 4, after "`Complexity:` (...integration count)." add: "With a workspace or team areas, add `Tracks:` per [capability epics](references/capability-epics.md), which also sets the contract and integration epics." Cut the same number of characters or more from step 4 without dropping a rule; for example shorten "Every run proposes `Estimate: <working days>` per epic by the method of `--milestone` step 2." to "Every run proposes `Estimate: <working days>` per epic (`--milestone` step 2)." and "(`gin task config get issue_prefix`; slug of lowercase letters, digits, and hyphens)" to "(`gin task config get issue_prefix`; slug of `[a-z0-9-]`)". Run `wc -m plugins/gin-workflow/src/skills/roadmap/SKILL.md` → at most 12000.
  4. In `references/way-of-working.md` `## Integration`, after the sentence that ends "The flags listed under `Flags on:` are turned on that day.", add: "Each capability in `Integrates:` gets a `<capability> integration` epic in that milestone, blocked by the capability's build epics (see capability-epics.md)." Run `wc -m` on it → at most 6000.
  5. In plan `SKILL.md`, step 5, after the sentence ending "two repositories mean two tracks.", add: "When the epic's roadmap entry has `Tracks:`, start from it and give each track its `Area:`." Then run the budget report; the plan chain must stay at most 12,000. If it is over, shorten plan `SKILL.md` text by at least the excess without dropping a rule (for example, step 6's parenthetical "(spawn natively when supported, else run `gin-orchestrator dispatch --workflow-id <id> --task-id <id>-scout --stage plan --role research --model <model> --workspace . --objective \"<brief>\" --agent agent-researcher --json`)" repeats the dispatch form of the discuss skill; replace it with "(native subagent, else `gin-orchestrator dispatch --stage plan --role research --agent agent-researcher`)" only if the plan chain needs the room and the execute and discuss skills keep the full form). Report the before and after numbers.
  6. In orchestrate `SKILL.md`, the Track Beads bullet, after "A track whose plan entry has a `Human gate:` line gets `--labels human-gate`." add: "A track with `Area:` gets `--labels area:<name>`; the epic keeps only its `roadmap` label." Run the budget report; the orchestrate chain must stay at most 12,000.
  7. In `docs/guides/workspace.md`, add before `## Commands`:
     ```markdown
     ## Contract

     The confirmed spec of a capability's epic is its API contract, and `requirement_confirmed` is the moment it is frozen. When the contract uses an OpenAPI file, the file lives in the parent repository and the spec links it. The service track and the app track of the epic read the same spec; the app track generates its mocks from it. A contract change after plan approval goes back through `/discuss`, so the spec, the plan, and both tracks change together. The roadmap adds one `<capability> integration` epic per capability, blocked by the build epics, for the day the flag turns on.
     ```
     In `## Limits`, replace the first bullet with: "- One track per repository. A capability that needs a service and an app is one epic with two tracks, one in each repository; a track never spans two repositories." (This is the PM decision recorded in `.planning/roadmap.md` Constraints; the wider rewrite stays with `gin-workflow-epic-shape-docs`.)
     Run `gin docs check docs/guides/workspace.md` → no findings.
  8. Run `python3 -m pytest tests/workflow_core/test_token_budget.py -q` → passes; run `python3 -m pytest tests -q -n auto -k "skill or roadmap or docs or budget"` → passes.
  9. Commit: `docs(roadmap): capability epics with tracks, area labels, contract, integration epics (gin-workflow-roadmap-areas)`.
- **Acceptance criteria**: R1 to R7; US-1 to US-3; budget tests pass; roadmap `SKILL.md` and the plan chain at most 12,000 characters; `gin docs check` clean on `docs/guides/workspace.md`.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/roadmap-areas`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto -q` passes (pre-push runs it).
- [ ] `python3 -m pytest tests/workflow_core/test_token_budget.py -q` passes.
- [ ] `gin docs check docs/guides/workspace.md` reports no findings.
- [ ] Manual: read `references/capability-epics.md` and the three skill sentences once together; no rule dropped by the cuts.

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog using the route rubric.
- Omit `Effort:` when the catalog lists no efforts.
- Unclear requirements never raise the model or effort; ask the user or return to `discuss`.
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- Deliverable merge-holds (e.g. "remain open until human-confirmed merge") apply exclusively to the Parent Bead. Individual track beads must close upon passing tests and code review to unblock downstream dependent tracks.
- Lesson from `gin-workflow-milestone-capacity`: a trim once dropped a rule ("neither counts" without its subjects); every cut here is reviewed against rule loss.

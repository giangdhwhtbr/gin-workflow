# Roadmap areas on tracks, contract and integration epics

Epic: gin-workflow-roadmap-areas
Status: confirmed by the user on 2026-11-10.

## Goal and scope

A roadmap plans by area and contract: each roadmap epic lists its tracks per repository or area with `Area:`, orchestrate turns a track's area into an `area:<name>` label, the confirmed spec is the API contract, and `/gin:roadmap --milestone` schedules one integration epic per capability so the flag flip is tracked in Beads.

The process review (`.planning/reviews/2026-11-07-process-review/synthesis.md`) asked for areas in the roadmap (BE-LEAD-6, PM-10), a contract convention (BE-LEAD-7, FE-LEAD-6), and contract and integration work scheduled as tracked epics (PM-7, PM-9, FE-LEAD-4). Research on 2026-11-10 found that track areas already exist and are enforced: `plan_tracks` reads `- Area:` per track and `check_plan` refuses a missing or unknown area and files outside it (`plugins/gin-workflow/src/scripts/workflow_core/team.py:293-312`). The `area:<name>` track label is written only by the `team` skill text (`plugins/gin-workflow/src/skills/team/SKILL.md:25`); the roadmap does not name tracks or areas; no contract location is defined (`docs/guides/workspace.md` has no contract section); the integration point is a date in the roadmap file only.

In scope:
- Roadmap epic entries list tracks per repository or area, with `Area:`.
- The orchestrate skill writes `area:<name>` on track beads.
- A contract convention in the workspace guide.
- Integration epics proposed by `/gin:roadmap --milestone`.

Out of scope:
- An epic-level area and a `check-plan` rule comparing it with track areas (BE-LEAD-6 part): replaced by the PM decision that the area belongs to the track.
- A separate contract epic (PM-7, FE-LEAD-4 part): the confirmed spec is the contract.
- A feature grouping above epics (PM-9 part): replaced by one epic per capability.
- Read-only inputs from sibling repositories (`gin-workflow-ws-branch-model`).
- Rewriting the epic rule in the workspace guide and starter (`gin-workflow-epic-shape-docs`).
- New code checks: `Area:` against `Repo:`, or a milestone warning for an integration epic placed with its blockers.

Confirmed summary (user, 2026-11-10): the confirmed spec is the API contract and `requirement_confirmed` freezes it; the roadmap adds one integration epic per capability, depending on that capability's build epics; changes are skill and docs text plus the orchestrate label rule, with no new code checks.

## Requirements

R1. A new reference `plugins/gin-workflow/src/skills/roadmap/references/capability-epics.md` defines the roadmap epic entry for one capability: a `Tracks:` line listing one track per repository (in a workspace) or per area (team mode without a workspace), each as `<repo or area>: <what it builds>`, and the `Area:` each track will carry. Without areas and without a workspace, `Tracks:` is omitted.

R2. The roadmap `SKILL.md` points to `references/capability-epics.md` from the step that presents epics, in one sentence, and stays within 12,000 characters; any characters added are cut elsewhere without dropping a rule.

R3. The plan skill, when the spec names a roadmap epic, starts its track list from that epic's `Tracks:` line and gives each track the `Area:` it names; a track may still be split further.

R4. The orchestrate skill states that a track bead whose plan track has `Area:` gets `--labels area:<name>`, and that the epic keeps only its `roadmap` label. The `team` skill line that says the same is kept and not duplicated in other words.

R5. `docs/guides/workspace.md` gains a "Contract" section: the confirmed spec of a capability's epic is its API contract; `requirement_confirmed` is the moment it is frozen; an OpenAPI file, when used, lives in the parent repository and the spec links it; service and app tracks of the epic read that same spec; the app track generates its mocks from it; a contract change after plan approval goes back through `/discuss`.

R6. `references/capability-epics.md` and the Integration block of `references/way-of-working.md` state that `/gin:roadmap --milestone` proposes, for each capability listed in `Integrates:`, one epic titled `<capability> integration` that depends on the capability's build epics, has the scope "turn the flag on and run the E2E suite against the real API", and belongs to the milestone of the integration point.

R7. `gin docs check` passes on every changed page under `docs/`, and the skill budget tests pass.

## User Stories

### US-1: Tracks per repository in the roadmap
As a tech lead, I want each roadmap epic to name its tracks per repository with their area, so that plan and orchestrate start from the same split and every track bead carries its area.

Acceptance criteria:
- `references/capability-epics.md` shows a `Tracks:` example with one track per repository and its `Area:`.
- The plan skill tells the planner to start tracks from `Tracks:`.
- The orchestrate skill tells the orchestrator to label each track bead `area:<name>`.

### US-2: One contract source
As a frontend lead, I want to know where the API contract lives and how my app reads it, so that the service and the app build against the same thing.

Acceptance criteria:
- `docs/guides/workspace.md` has a "Contract" section stating that the confirmed spec is the contract, where an OpenAPI file lives, and how the app track uses it.
- The section says a contract change after plan approval goes back through `/discuss`.

### US-3: Integration as tracked work
As a PM, I want the integration of each capability to be an epic, so that the flag flip is blocked in Beads until the service and app epics close.

Acceptance criteria:
- `references/way-of-working.md` and `references/capability-epics.md` describe the `<capability> integration` epic, its dependencies, scope, and milestone.
- The roadmap `SKILL.md` stays within 12,000 characters.

## Errors and compatibility

- Roadmap files without `Tracks:` stay valid; plan then derives tracks as today.
- Projects without team areas get no `Area:` lines and no `area:` labels, as today.
- No CLI, JSON, or config change; gin-console is unaffected.

## Testing

- The existing skill budget tests and any skill content tests pass (`python3 -m pytest tests -q -k "budget or skill"`).
- `wc -c plugins/gin-workflow/src/skills/roadmap/SKILL.md` is at most 12000.
- `gin docs check docs/guides/workspace.md` reports no findings.

## Open Technical Questions

## Assumptions

- The integration epic is proposed by the roadmap skill and created through its Beads sync, like any roadmap epic; no CLI creates it.
- `Tracks:` is guidance for plan, not parsed by code.

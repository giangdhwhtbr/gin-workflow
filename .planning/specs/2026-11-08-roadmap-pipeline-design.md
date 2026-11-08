# Roadmap delivery pipeline: way of working, spec-ahead sequencing, and an integration point per milestone

Epic: gin-workflow-roadmap-pipeline
Status: draft for user review.

## Goal and scope

`/gin:roadmap` organizes a multi-role team (BA, SA, BE, FE, DevOps, QA) so roles wait on each other as little as possible. The skill proposes the team's way of working instead of waiting for the PM to describe it, sequences capabilities by spec readiness and real data needs, writes an integration point into every milestone, and `gin milestone show` warns when an epic enters a kicked-off milestone without a confirmed spec.

Confirmed understanding (2026-11-08):

- Specs are confirmed one milestone ahead of the build: the BA confirms milestone N+1 while developers build N.
- Each milestone has an integration point about three quarters through it, leaving hardening days; QA closes an epic inside its own milestone, never one milestone behind.
- Integration pattern: one feature flag per capability, controlled by the backend (`GET /api/feature-flags`; the backend also guards the endpoints of an off feature). The frontend runs ahead against mocks generated from the OpenAPI contract (for example MSW handlers from orval); a gate handler per capability passes requests to the real API when its flag is on and falls through to the mock when off. The frontend renders a `MOCK` watermark on a capability served by mocks. Flipping the flag is the integration point: QA writes E2E against the mocked UI during the build and reruns the same suite after the flip. Capabilities that share data share a flag or integrate together. CI runs contract-diff checks; production builds carry no mocks.
- The foundation milestone defaults to 2 weeks: CI/CD, environments, auth, feature flags, app shell, contract convention, and team onboarding (environment, tools, the gin skills on a first small capability).
- The skill never asks the team composition. In team mode it reads role counts from `team.members`; without team mode it relies on the lanes shipped by `gin-workflow-57fw`.
- The way of working is a section of the roadmap file that the PM confirms or adjusts like the epic split. The PM prompt then carries only business input: goal, deadline, fixed constraints, non-goals, cutover.
- The integration point lives in the roadmap file only (user decision 2026-11-08); a milestone metadata date with an `after_integration` warning is a possible later epic.

In scope: roadmap template, the roadmap skill and a new reference file, `gin milestone show`/`list` warning `spec_not_ready` with a per-epic `spec_confirmed` field, tests, docs in this repository.

Out of scope:
- Lanes, deadline, and forecast (shipped by `gin-workflow-57fw`).
- Starter-guide prompts and the brownfield guide (`gin-workflow-docs-refresh`).
- Integration date as milestone metadata and an `after_integration` schedule warning.
- Creating BA spec tasks or beads for the spec-ahead cadence; specs still come from `/discuss <epic>`.
- gin-console rendering of `spec_not_ready` and `spec_confirmed` (noted on `gin-console-cl0`).

Comments considered: 1, latest 2026-11-08T13:42:09Z. The comment reports that `gin-workflow-57fw` shipped lanes, deadline, and forecast (merge `6b27ce6`); this spec relies on lanes for the no-team case and on the roadmap lines it added (`Deadline:`, `AI capacity:`, `Estimate:`).

## Requirements

### R1. Roadmap template

`plugins/gin-workflow/src/templates/roadmap.md`:

- After `## Constraints` and before `## Strategy`, a section `## Way of working` with these bullets, each left for the skill to fill: `- Foundation:`, `- Spec cadence:`, `- Build:`, `- Integration:`, `- Quality:`, `- Load:`.
- The `## Milestone: {{milestone_title}}` block starts with two lines before the first epic: `Spec ready by: {{spec_ready_by}}` and `Integration point: {{integration_date}}`, the latter followed by four indented bullets `- Integrates:`, `- Flags on:`, `- E2E scope:`, `- Exit criteria:`.
- The header comment says that `## Way of working` is written by a plain `/roadmap` from `references/way-of-working.md` and kept on re-runs, and that `Spec ready by:` and `Integration point:` are written by `/roadmap --milestone`; older files without them stay valid.

### R2. Reference file

New `plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md`, read by the skill on demand (it is not part of the roadmap chain, so it has no budget; keep it under 6,000 characters). It holds the default pattern as text the skill tailors, one short block per bullet of `## Way of working`:

- Foundation: 2 weeks by default; CI/CD, environments, auth, feature flags, app shell, contract convention, onboarding on a first small capability. Shorter when the tech-doc set shows these exist.
- Spec cadence: BA confirms the specs of milestone N+1 during milestone N; `Spec ready by:` of a milestone is its kickoff (or start) date; an epic without a confirmed spec at kickoff is a `spec_not_ready` warning in `gin milestone show`.
- Build: contract first; BE and FE in parallel; FE on mocks generated from the OpenAPI contract (MSW handlers from orval as the example); for a migration a 1-1 copy of the legacy UI first.
- Integration: one backend-controlled flag per capability (`GET /api/feature-flags`, backend guards off endpoints); gate handler real API when on, mock when off; `MOCK` watermark from the flags state or an `X-Mock` header; capabilities sharing data share a flag or integrate together; contract-diff in CI; no mocks in production builds; the integration point at about 75% of the milestone's working days.
- Quality: QA writes E2E against the mocked UI during the build and reruns it after the flip; QA closes the epic inside the milestone; hardening days after the integration point.
- Load: role groups from `team.members`; the scarcest group bounds the milestone; without team mode the lanes of the roadmap `AI capacity:` line or the milestone `--lanes`.
- Role grouping rule: a role name's first token before `_` names its group (`be_dev`, `be_lead` → BE; `fe_*` → FE; `qa`, `qe` → QA; `ba`, `sa`, `devops`, `pm` as themselves); the skill prints the grouping and the PM corrects it.

### R3. Roadmap skill

`plugins/gin-workflow/src/skills/roadmap/SKILL.md`, under 12,000 characters, anchor phrases kept (`warn and leave its title, description, and dependencies unchanged`, `7. **Report**` with `[gin roadmap]`):

- Step 2 (Clarify) adds: never ask the team composition; in team mode read `team.members` from `.agent-workflow/config.yaml` and group roles per the reference; otherwise use the lanes. Ask only business input: goal, deadline, fixed constraints, non-goals, cutover.
- Step 3 (split) adds: sequence capabilities by spec readiness and by real API or data needs only; keep epic dependencies minimal; when the tech-doc set or brief shows no CI/CD, environments, auth, flags, shell, or contract convention, propose the corresponding foundation epics first, with the feature epics depending on them.
- New step between 3 and 4, **Propose the way of working**: read `references/way-of-working.md`, tailor each bullet to the team and the tech-doc set, present it with trade-offs, and revise until the PM confirms; on a re-run keep the confirmed section unless the PM asks for a change.
- Step 5 (Write) writes `## Way of working` from the confirmed text.
- `--milestone` section adds: balance the adopted epics against the scarcest role group (team mode) or the lanes (otherwise); write `Spec ready by:` (the milestone's kickoff, else start) and the `Integration point:` block (date = the working day at 75% of the milestone's working days from start, rounded down; `Integrates:` the adopted epics; `Flags on:` their capabilities, one flag per capability or one shared flag for capabilities that share data; `E2E scope:` the flows the flags expose; `Exit criteria:` E2E green against the real API and the watermark gone); name each adopted epic whose `spec_confirmed` is false in `gin milestone show <id> --json` and the BA work due before kickoff.
- Step 7 (Report) adds the `spec_not_ready` warnings of `gin milestone show`, when the milestone has a kickoff.

### R4. Spec readiness in `gin milestone`

- `milestone_cli.py` builds `confirmed: frozenset[str] | None`: the `workflow_id` of every `requirement.confirmed` event in `.agent-workflow/runtime/events.jsonl` of the main checkout (`WorkflowEventStore(path).read_all()`, path as in `lifecycle_cli._get_event_store`). A missing file gives an empty set. An unreadable file gives `None` and one stderr line `warning: event log unreadable: <error>; spec readiness unknown`; the command continues.
- `schedule(milestone, beads, start, today, default_lanes=1, confirmed=None)`: each row adds `"spec_confirmed": bool | None` (`None` when `confirmed` is `None`); a warning `{"code": "spec_not_ready"}` when `confirmed` is not `None`, the milestone status is `scheduled` or `active`, the epic is not closed, and its id is not in `confirmed`. Closed epics and `planned` milestones never get it.
- `show_payload` and `list_payload` pass `confirmed` through; `list` entry `warnings` counts the new code like the others; `forecast` is unchanged.
- `show` text prints the code in the existing warning column; `list` text is unchanged. `schema` stays 1.

### R5. Documentation

- `docs/reference/cli.md` `## gin milestone`: the `spec_not_ready` warning and the `spec_confirmed` field, the event log they read, and the stderr warning on an unreadable log.
- `docs/guides/customizing-templates.md` and `.vi.md`: the `## Way of working` section and the milestone block lines.
- `docs/reference/skills.md` and `.vi.md` roadmap row: proposes the way of working; `docs/concepts/lifecycle.md` `/roadmap` sentence.

## User Stories

### US-1: Get a proposed way of working
As a PM, I want `/gin:roadmap` to propose how the team will work from my team roles and the tech docs, so that I only supply business input and confirm or adjust the rest.

Acceptance criteria:
- A plain `/roadmap` presents a `Way of working` proposal with trade-offs before the roadmap and asks for confirmation.
- The confirmed text is written as `## Way of working` in the roadmap file and kept on a re-run unless I ask to change it.
- The skill never asks how many people hold each role.

### US-2: Sequence by spec readiness and real needs
As a PM, I want epics ordered so that roles wait as little as possible, so that BE and FE build in parallel and the BA stays one milestone ahead.

Acceptance criteria:
- The split step orders capabilities by spec readiness and by real API or data needs, and keeps `Depends on:` minimal.
- Foundation epics are proposed first when the project lacks CI/CD, environments, auth, flags, shell, or a contract convention, and feature epics depend on them.

### US-3: Plan a milestone with an integration point
As a PM, I want each milestone block to state its spec deadline and integration point, so that QA can close epics inside the milestone.

Acceptance criteria:
- `/roadmap --milestone <id>` writes `Spec ready by:` and the `Integration point:` block with the four bullets.
- The integration date is the working day at 75% of the milestone's working days, rounded down.
- Adoption is bounded by the scarcest role group in team mode, by the lanes otherwise, and the report names which bound applied.

### US-4: See which epics lack a confirmed spec
As a PM or QA, I want `gin milestone show` to flag an epic that enters a kicked-off milestone without a confirmed spec, so that the spec-ahead cadence is visible.

Acceptance criteria:
- Each epic row of `show --json` carries `spec_confirmed`.
- An open epic without a `requirement.confirmed` event in a `scheduled` or `active` milestone gets `spec_not_ready`; a `planned` milestone or a closed epic does not.
- A missing event log means no epic is confirmed; an unreadable log prints one stderr warning, sets `spec_confirmed` to null, and the command exits 0.

### US-5: Older roadmaps stay valid
As a PM with an existing roadmap, I want the new sections to be optional, so that nothing breaks before I re-run `/roadmap`.

Acceptance criteria:
- A roadmap file without `## Way of working`, `Spec ready by:`, or `Integration point:` is read as today.
- `gin milestone list --json` keeps `schema: 1` and every existing key.

## Errors and compatibility

| Case | Behaviour |
|---|---|
| `events.jsonl` missing | `confirmed` is empty; every open epic in a kicked-off milestone is `spec_not_ready` |
| `events.jsonl` unreadable | stderr `warning: event log unreadable: ...; spec readiness unknown`; `spec_confirmed` null; no `spec_not_ready`; exit 0 |
| Milestone `planned` (no kickoff) | `spec_confirmed` set, no `spec_not_ready` |
| Closed epic | never `spec_not_ready` |
| `team.members` absent or team mode off | the skill balances against the lanes and says so |
| Role name without `_` | its own group |

Compatibility: `schema` stays 1; `spec_confirmed` and `spec_not_ready` are additions. gin-console parses unknown warning codes (`EpicWarning.code` is a string) and renders them raw (`gantt.ts` `warningLines` default branch); the pretty label is a note on `gin-console-cl0`. Existing exact-payload tests gain `spec_confirmed`.

## Testing

- `tests/workflow_core/test_milestone.py`: `spec_confirmed` true/false/null; `spec_not_ready` for an active and a scheduled milestone, absent for planned and for closed epics; `list_payload` warning count includes it.
- `tests/workflow_core/test_milestone_cli.py`: a seeded `requirement.confirmed` event in the repo's `events.jsonl` marks that epic confirmed; a kickoff milestone shows `spec_not_ready` for the other epic; an unreadable log prints the stderr warning and exits 0; exact-payload tests updated.
- `tests/workflow_core/test_specs.py`: the rendered template contains `## Way of working`, `Spec ready by:`, `Integration point:`.
- `tests/workflow_core/test_epic_comments.py`, `test_skill_routing.py`, `test_token_budget.py` keep passing; `wc -c` of `SKILL.md` under 12,000 and of `references/way-of-working.md` under 6,000.
- `gin docs check` on every touched docs page prints `ok`.
- Full suite: `python3 -m pytest -n auto`.

## Open Technical Questions

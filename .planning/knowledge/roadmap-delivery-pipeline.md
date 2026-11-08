# Roadmap delivery pipeline: way of working, integration point, spec readiness, bead templates

**Context**
Epic `gin-workflow-roadmap-pipeline` (2026-11-08). `/gin:roadmap` waited for the PM to describe how a multi-role team (BA, SA, BE, FE, DevOps, QA) works, milestones had no integration point, and nothing flagged an epic that entered a kicked-off milestone without a confirmed spec. Raised while planning an 11-person JSP to Spring Boot + React migration. A user add-on in the same epic: a description template for track beads and a complexity rating on roadmap epics, so beads read the same way in gin-console.

**Decision/Solution**
- The default way of working lives in `plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md` (Foundation, Spec cadence, Build, Integration, Quality, Load, Milestone block). The skill tailors it, the PM confirms it, and it is written under `## Way of working` in the roadmap file and kept on re-runs. Pattern: 2-week foundation with onboarding; BA confirms milestone N+1 during N; contract-first BE and FE in parallel, FE on mocks generated from OpenAPI; one backend-controlled flag per capability with a gate handler and a `MOCK` watermark; contract-diff in CI and no mocks in production; QA closes epics inside their milestone.
- Integration point: working day floor(0.75 * N), N = working days from `start` to `end` inclusive, `start` is day 1, 0 falls back to `start`. It lives only in the roadmap file (`Spec ready by:`, `Integration point:` with Integrates, Flags on, E2E scope, Exit criteria); milestone metadata and an `after_integration` warning were deferred.
- Load bound: in team mode the member count of the scarcest role group the adopted epics need (role group = first token of the role name before `_`), times the working days; otherwise the lane count times the working days. The skill never asks the team composition.
- `gin milestone show/list` read `requirement.confirmed` events from `.agent-workflow/runtime/events.jsonl` of the main checkout (`milestone_cli._confirmed`) and pass the ids to the pure scheduler: rows carry `spec_confirmed`, and `spec_not_ready` fires for an open epic in a `scheduled` or `active` milestone without a confirmed spec. An unreadable log prints one stderr warning, sets `spec_confirmed` to null, and exits 0.
- `templates/task.md` (label lines `Plan:`, `Files:`, `Route:`, `Acceptance:`, `Notes:`, no headings because gin-console renders descriptions as plain text) is what `/gin:orchestrate` uses for track beads. `epic.md` and the roadmap epic block carry `Complexity:` (`low`, `medium`, `high` plus the main driver).

**Consequences**
- The core plugin may not name the add-on plugins `gin-qa` or `gin-ba` anywhere under `plugins/gin-workflow/src` (`tests/gin_qa/test_packaging.py`, `tests/gin_ba/test_ba_packaging.py`); the reference says "the gin skills the team installed".
- Roadmap `SKILL.md` is at 11,963 of 12,000 characters (`test_roadmap_skill_within_12000` now enforces it); the next addition must move text into `references/`.
- `gin evidence run` must gate the `review-requested` transition (`&&`, not `;`), or a failed run still requests review.
- The `Notes:` placeholder of `task.md` has no stated source in the orchestrate skill; agents fill it from leftover track text or leave it empty.
- gin-console follow-up: `gin-console-mbi` under `gin-harness-bkd` (`external:gin-workflow:milestone-spec-readiness`).

**References**
- `plugins/gin-workflow/src/skills/roadmap/{SKILL.md,references/way-of-working.md}`, `plugins/gin-workflow/src/skills/orchestrate/SKILL.md`, `plugins/gin-workflow/src/templates/{roadmap,epic,task}.md`
- `plugins/gin-workflow/src/scripts/workflow_core/{milestone,milestone_cli}.py`; tests `tests/workflow_core/test_{milestone,milestone_cli,specs,token_budget}.py`
- Docs: `docs/reference/cli.md` (`gin milestone`), `docs/guides/customizing-templates.md`, `docs/reference/skills.md`, `docs/concepts/lifecycle.md`
- `.planning/specs/2026-11-08-roadmap-pipeline-design.md`, `.planning/plans/2026-11-08-roadmap-pipeline.md`
- Commits `f63d784`, `2d2cb0e`, `edbacdd`, `8d75513`, `4b834ee`, `a0d7d76`, `55f1ad6`
- Beads: `gin-workflow-roadmap-pipeline`, `.1` to `.4`
- Related: [milestone-lanes-and-forecast](milestone-lanes-and-forecast.md), [epic-comments](epic-comments.md)

**Scope**
`/gin:roadmap`, `/gin:orchestrate` track beads, the roadmap and bead templates, and `gin milestone show/list` with the Beads task backend.

# Process review with role personas

**Context**
Before adding more features, epic `gin-workflow-process-review` checked how the lifecycle reads to the people who would run it on a legacy JSP to Spring Boot + React modernization in a multi-repository workspace.

**Decision/Solution**
- Five AI personas (PM, BA, QA, backend lead, frontend lead) read the docs and skills and walked 14 stages of one shared scenario; they did not run stages. Each run was a native `general-purpose` agent on `opus`, effort `high`, with no access to the other reports.
- The kit lives in `.planning/reviews/2026-11-07-process-review/`: `brief.md` (scenario and questions), `report-template.md`, `prompts/<role>.md`, and `check.py`, a stdlib script that checks prompt sections, the 14 stage sub-sections, tracked evidence paths, and that `synthesis.md` accounts for every finding ID once.
- The main session merged the 106 findings into 26 proposed epics in `synthesis.md` (3 P1, 21 P2, 2 P3), with 6 role conflicts left open. No bead was created; `/gin:roadmap` picks from the carry list.
- A persona's wrong line numbers with correct content were deferred to the synthesis track, which cites the corrected lines, instead of re-running an `opus`/`high` persona.

**Consequences**
- P1 items for the next roadmap: the ship gate refuses pull requests of workspace children; gin-qa cannot run from the `qa` child or a track worktree; `plan_approved: area_lead` deadlocks when one `be_lead` leads every area, and `ship: [qe, be_lead]` lets a lead merge without QA.
- Persona reports cite `file:line` but can cite wrong lines; `check.py` only checks that the path is tracked, so a reviewer must spot-check line content.
- `gin:developer` has no Agent tool, so a track whose work is a set of agent runs is launched from the main session.
- Re-running a persona produces a different set of findings, so reports are re-run only when unusable, never patched by hand.

**References**
- Spec `.planning/specs/2026-11-07-process-review-design.md`, plan `.planning/plans/2026-11-09-process-review.md`
- `.planning/reviews/2026-11-07-process-review/synthesis.md`, `reports/*.md`, `check.py`
- Beads: `gin-workflow-process-review`, `.1` to `.3`
- Related: [workspace](workspace.md), [milestone-lanes-and-forecast](milestone-lanes-and-forecast.md), [roadmap-delivery-pipeline](roadmap-delivery-pipeline.md)

**Scope**
Method and outcome of the 2026-11 role-persona process review; the findings themselves live in `synthesis.md`.

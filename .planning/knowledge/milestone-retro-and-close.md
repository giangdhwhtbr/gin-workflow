# Milestone retro and close: comment contracts and team metrics

**Context**
Epics `gin-workflow-sprint-retro` and `gin-workflow-milestone-close` (2026-11-15). Members needed a place to record a retro before a milestone closes, and closing a milestone with open epics needed manual `gin milestone move` calls with no record of what was delivered.

**Decision/Solution**
- Both are skills only (`/retro`, `/milestone-close`); the `gin milestone` CLI and its `schema: 1` JSON did not change.
- Results are bead comments with fixed English labels, parsed by `/milestone-close` and by gin-console through its bead comments API (`GET /beads/{project}/{bead_id}/comments`), not milestone metadata: the console bead model has no metadata.
  - `[gin retro] <milestone-id> <member>` with `Went well:`, `Slowed us:`, `Change next:`; named, optional, newest per member counts.
  - `[gin close] <milestone-id>` with `Delivered:`, `Spillover:`, `Outcome:`, `Demo:`, `Retros:`, `Metrics:`, `Action:`.
- Every open epic moves to the next milestone: the open one with the earliest `start` after the closing milestone's `start`. The write order create, move, estimate, comment, close is forced by the CLI: `move` refuses a closed milestone and `close` refuses open epics.
- Metrics are team level only: `completion`, `estimate_accuracy`, `capacity_used`, `cost_per_epic`, `rework`, compared with the previous `[gin close]`.
- `gin usage report --milestone` lists epics and their children in `beads`, and an epic's `quality` already includes its children. Sum quality only over entries whose `parent` is not another entry's `bead`, as `totals` does; summing all entries double counts (review finding F-1 of `gin-workflow-milestone-close.2`).
- Lessons from a close become knowledge records through the `learn` Reconcile steps; `gin task remember` stores only short facts the PM chooses.

**Consequences**
- The comment labels are a contract with gin-console; changing them needs a console change (`gin-console-workflow-catchup`).
- `status: active` needs `gin milestone kickstart`; without it, `/retro` and `/milestone-close` ask which milestone.
- A close that stops after the milestone is closed is finished by hand from the report.

**References**
- `plugins/gin-workflow/src/skills/retro/SKILL.md`, `plugins/gin-workflow/src/skills/milestone-close/SKILL.md`, `plugins/gin-workflow/src/templates/roadmap.md` (`Result:`), `plugins/gin-workflow/src/skills/roadmap/references/manager-view.md`
- `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py` (`_move`, `_close`), `plugins/gin-workflow/src/scripts/workflow_core/usage.py` (`report`)
- `.planning/specs/2026-11-15-sprint-retro-design.md`, `.planning/specs/2026-11-15-milestone-close-design.md`
- Beads: `gin-workflow-sprint-retro`, `gin-workflow-milestone-close`, `gin-workflow-4p75`; console: `gin-console-workflow-catchup`
- Related: [milestone-lanes-and-forecast](milestone-lanes-and-forecast.md), [roadmap-delivery-pipeline](roadmap-delivery-pipeline.md), [skill-authoring-limits](skill-authoring-limits.md)

**Scope**
Closing milestones, retros, and anything that reads `[gin retro]` or `[gin close]` comments.

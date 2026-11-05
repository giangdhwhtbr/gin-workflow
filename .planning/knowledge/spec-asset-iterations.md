# Spec assets: dated iteration folders, convention plus lint, no CLI

**Context**
Epic `gin-workflow-spec-iterations` (2026-11-05). With the SDD layout, `<specs>/<cap>/assets/` was flat: a new batch of customer requirements or designs landed next to the old files with no record of when or why, and a legacy project had no place for screenshots of the existing feature.

**Decision/Solution**
- Each batch of inputs gets `<specs>/<cap>/assets/<YYYY-MM-DD>/` with a required `description.md` from `gin-workflow specs template iteration.md` (`Kind:` `new|change|legacy`, `Source:`, `Previous:`, Summary, Changes, Files); optional `mockup/` and `legacy/` subfolders. An older dated folder is never edited; flat files under `assets/` stay valid.
- `lint_iterations` in `workflow_core/specs.py` reports a dated folder without `description.md`; `lint_living` and `lint_change` both append it, so `specs lint`, `specs lint --change`, and `specs archive` stop on it. `lint_change` checks every capability, not only the cited ones (one rule, one function).
- Only ISO dates (`^\d{4}-\d{2}-\d{2}$`) mark an iteration; `110526`-style names from the roadmap brief are not recognized.
- No `specs assets new` CLI (the roadmap listed one): the folder is a `mkdir` plus `specs template iteration.md`, which `gin-sdd` discuss does. `gin-workflow-ba-plugin` may add a command if it needs one.

**Consequences**
- The layout is a skill convention enforced only by the `description.md` lint; `docs/guides/sdd.md` labels it "By convention".
- Assets stay under the capability, never in change folders, and archive does not move them (as in [ba-capability-placement](ba-capability-placement.md)).

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/specs.py` (`lint_iterations`), `plugins/gin-workflow/src/templates/iteration.md`, `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md`, `docs/guides/sdd.md`
- `.planning/specs/2026-11-05-spec-iterations-design.md`, `.planning/plans/2026-11-05-spec-iterations.md`
- Beads: `gin-workflow-spec-iterations`, `gin-workflow-spec-iterations.1`, `gin-workflow-spec-iterations.2`

**Scope**
SDD layout only: specs lint, the `iteration.md` template, gin-sdd discuss, and the SDD guide.

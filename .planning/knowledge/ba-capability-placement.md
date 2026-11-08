# Capability placement: feature capability holds its UI, discuss confirms capabilities before REQ-IDs

**Context**
Epic `gin-workflow-7xy4` (2026-11-05). With the SDD layout the capability of a requirement was chosen silently at `specs next-id`, and nothing said where a feature's UI requirements or its mockups belong. gin-console ended with the Reports UI in a shared `ui` capability and the mockup under `reports/assets/`, and renumbering afterwards breaks test names and archived citations.

**Decision/Solution**
- One default rule for every SDD project: a feature's requirements, UI included, live in the feature's capability; `ui` holds only design system, layout, navigation, and shared components; assets live under `<specs>/<cap>/assets/` of the capability holding the requirements they illustrate. A project that wants another rule writes it in `docs/specs/README.md`.
- `/roadmap` names `Capabilities:` per epic (from `docs/specs/README.md`, else `02-FEATURES.md`, else the brief; `(new)` marks a missing folder); the `roadmap.md` and `epic.md` templates carry the line after `Out of scope:`.
- `gin-sdd` discuss presents a *Capabilities affected* table in the design the user confirms, before `specs new` and `specs next-id`; `01-proposal.md` `## Capabilities Affected` records capability, REQ-IDs, and asset paths; an in-repo asset is `git mv`ed into place, an outside one is not copied.
- No config key and no lint for the rule: the user fixed the default, and lint cannot tell a UI requirement from an API one. `specs archive` already maintains the README index.

**Consequences**
- The rule is a skill convention; `docs/guides/sdd.md` labels it as such.
- Since `gin-workflow-spec-iterations`, inputs under `<specs>/<cap>/assets/` go in dated folders `<YYYY-MM-DD>/` with a `description.md`; see [spec-asset-iterations](spec-asset-iterations.md).
- Since `gin-workflow-tp83`, assets go in with `gin specs assets add`, which copies files from inside or outside the repository, replacing `git mv`; see [ba-asset-intake](ba-asset-intake.md).
- Diagrams in specs and an SRS export were split into epics `gin-workflow-ycg8` and `gin-workflow-bel0`; both touch `gin-sdd/SKILL.md`, so they run after this epic.

**References**
- `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md`, `plugins/gin-workflow/src/skills/roadmap/SKILL.md`, `plugins/gin-workflow/src/templates/roadmap.md`, `plugins/gin-workflow/src/templates/epic.md`
- `.planning/specs/2026-11-05-ba-capability-placement-design.md`, `.planning/plans/2026-11-05-ba-capability-placement.md`
- Beads: `gin-workflow-7xy4`, `gin-workflow-7xy4.2`, `gin-workflow-7xy4.1`

**Scope**
The roadmap and gin-sdd skills, their templates, and the SDD guide.

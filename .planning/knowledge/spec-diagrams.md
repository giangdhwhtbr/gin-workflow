# Spec diagrams: files per capability, activity required by lint, state by convention

**Context**
Epic `gin-workflow-ycg8` (2026-11-05). With the SDD layout, living specs held only requirement blocks; a BA reading `docs/specs/` had no picture of a feature's flow or an entity's states.

**Decision/Solution**
- Diagrams are Mermaid files in `<specs>/<cap>/diagrams/`: `<feature>-activity.md` (`flowchart`/`graph`) and `<entity>-state.md` (`stateDiagram`), from `gin-workflow specs template activity.md` / `state.md`. Other files there are allowed and unchecked.
- They are not part of the spec delta: they carry no `base:` hash, and `parse_blocks` (`workflow_core/specs.py`) is not fence-aware, so Mermaid stays out of requirement blocks. Reviewers see them because `03-design.md` `## Data Flow` cites each path, and the existing untracked-citation check in `lint_change` requires cited files to be committed; `01-proposal.md` `## Capabilities Affected` lists them.
- `lint_diagrams` checks only the diagram type on the first non-empty, non-`%%` line of a mermaid block; Mermaid syntax and front matter are not validated. `lint_change` reports a capability with an `ADDED` or `MODIFIED` block and no `*-activity.md`; a `REMOVED`-only delta needs none.
- The state-diagram rule (three or more states, or a guarded transition) is a skill convention; lint cannot judge it.
- `templates/spec.md` has `## Diagrams`, then `## Use Cases` (since `gin-workflow-fm8l`, [spec-use-cases](spec-use-cases.md)), before `## Requirements`, which stays last because archive appends `ADDED` blocks at the end. Archive fills `## Diagrams` and `## Use Cases` only when it creates `spec.md` for a new capability; for an existing one, discuss adds the link.

**Consequences**
- A change in flight that adds or modifies requirements without an activity diagram fails `specs lint --change` and `specs archive` after upgrade.
- Known test gaps left open: archive stopping on a missing activity diagram, a project template without `## Diagrams`, and `startswith` accepting `graphviz` as `graph`.
- The SRS export ([srs-export](srs-export.md)) renders `diagrams/` in each chapter. Diagrams sit next to assets under the capability, as in [spec-asset-iterations](spec-asset-iterations.md) and [ba-capability-placement](ba-capability-placement.md).

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/specs.py` (`lint_diagrams`, `lint_change`), `plugins/gin-workflow/src/scripts/workflow_core/specs_archive.py`, `plugins/gin-workflow/src/templates/activity.md`, `state.md`, `spec.md`, `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md`, `docs/guides/sdd.md`
- `.planning/specs/2026-11-05-spec-diagrams-design.md`, `.planning/plans/2026-11-05-spec-diagrams.md`
- Beads: `gin-workflow-ycg8`, `gin-workflow-ycg8.1`, `gin-workflow-ycg8.2`

**Scope**
SDD layout only: specs lint and archive, the diagram templates, gin-sdd discuss, and the SDD guide.

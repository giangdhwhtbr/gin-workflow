# Spec use cases: optional files per capability, linted, printed in the SRS

**Context**
Epic `gin-workflow-fm8l` (2026-11-09). A BA asked to keep use cases next to a capability's requirements and to show them in the SRS sent to customers.

**Decision/Solution**
- Use cases follow the diagrams model ([spec-diagrams](spec-diagrams.md)): one file per use case, `<specs>/<cap>/use-cases/<slug>.md`, from `gin specs template use-case.md`; edited directly on the spec branch, no ID or hash, never in `02-spec-delta.md`. The user chose this over UC-IDs through the delta, which would have touched next-id, hash, renumber, archive, and trace.
- Optional: no lint rule requires a capability to have one. `lint_use_cases` (`workflow_core/specs.py`, called from `lint_living` and `lint_change`) checks each file for a `# ` title, an `Actor:` value, a `Requirements:` line with at least one REQ-ID, and a numbered list under `## Main flow`. A REQ-ID must be in a living spec or `ADDED`/`MODIFIED` in an open change's delta (`_known_req_ids`); a REQ only `REMOVED` there is reported. The template's own `REQ-<CAP>-NNN` fails lint on purpose.
- `_known_req_ids` walks the change folders itself: `specs_reqs.open_changes` cannot be imported from `specs.py` (circular import).
- `templates/spec.md` has `## Use Cases` between `## Diagrams` and `## Requirements`; archive links `use-cases/*.md` there only when it creates `spec.md` for a new capability.
- The SRS chapter (`srs-capability.html`, `{{use_cases}}`) prints use cases between Purpose and Diagrams as `<section class="use-case" id="<cap>-<stem>">`.

**Consequences**
- A use case and a diagram with the same file stem in one capability give a duplicate HTML id `<cap>-<stem>` in the SRS (MINOR, left open; fix would be a `uc-` prefix).
- A project that overrides `srs-capability.html` shows no use cases until it adds `{{use_cases}}`.
- `skills/sdd/SKILL.md` is capped at 6,000 characters by `test_skill_routing.py` (5,989 after this epic). Trimming it to make room dropped three rules (source order, never delete originals unprompted, reuse a roadmap epic) and took two extra review cycles; compare the old text sentence by sentence before cutting.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/specs.py`, `specs_export.py`, `specs_archive.py`, `plugins/gin-workflow/src/templates/use-case.md`, `spec.md`, `srs-capability.html`, `plugins/gin-workflow/src/skills/sdd/SKILL.md`, `docs/guides/sdd.md#use-cases`
- `.planning/specs/2026-11-09-use-cases-design.md`, `.planning/plans/2026-11-09-use-cases.md`, `.planning/reviews/gin-workflow-fm8l.3/`
- Beads: `gin-workflow-fm8l`, `gin-workflow-fm8l.1`, `gin-workflow-fm8l.2`, `gin-workflow-fm8l.3`

**Scope**
SDD layout only: specs lint, export, and archive, the use-case template, the sdd skill, and the SDD, BA, and template guides.

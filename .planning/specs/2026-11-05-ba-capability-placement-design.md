# Capability placement for requirements and assets

Epic: gin-workflow-7xy4
Status: draft for user review.

## Goal and scope

With the SDD layout, a change's requirements end up in `docs/specs/<capability>/spec.md` at archive, keyed by `REQ-<CAP>-<NNN>`. Today the capability is chosen silently: `gin-sdd` discuss step 2 calls `specs next-id <cap>` without presenting the choice, no stage proposes a capability list to the BA, and nothing says where a feature's UI requirements or its input assets (mockups, screenshots, briefs) belong. In gin-console epic `gin-console-xza`, discuss wrote the Reports page UI as `REQ-UI-088..095` in a shared `ui` capability while the approved mockup sat in `docs/specs/reports/assets/mockup/`, and the same repository already had a per-feature `milestone-ui` capability. Moving requirements afterwards breaks test names and archived change folders that cite the IDs.

This spec adds, for the SDD layout only:
- one placement rule for feature requirements, UI requirements, and assets;
- a `Capabilities:` line per epic in the roadmap and the epic bead, sourced from the tech-doc feature catalog or the living specs index;
- a capabilities table in the design that discuss presents and the user confirms before any REQ-ID is assigned, recorded in `01-proposal.md`.

Out of scope:
- Diagrams in specs (activity and state diagrams) and an SRS export: two separate epics, created after this spec is confirmed.
- A CLI check for the placement rule. It is a skill convention, documented as such.
- Any change to the legacy layout, to `/migrate-specs`, or to `specs archive`, which already appends new capabilities to `docs/specs/README.md` (`specs_archive.py:87-91`).
- The gin-console follow-up (link `REQ-UI-088` to `docs/specs/reports/assets/mockup/`); it lives in gin-console.
- New config keys or CLI commands.

## Requirements

### R1. Placement rule

`plugins/gin-workflow/src/skills/gin-sdd/SKILL.md` (discuss section) and `docs/guides/sdd.md` state one rule for every SDD project:
- A feature's requirements, its UI requirements included, live in the feature's capability (`reports`, not `ui`).
- A `ui` capability holds only what spans pages: design system, layout, navigation, shared components.
- Input assets live in `docs/specs/<capability>/assets/` of the capability that holds the requirements they illustrate; requirement blocks link them with paths relative to that capability's `spec.md`, as `docs/guides/sdd.md` already describes for images.
- A project that wants a different rule records it in `docs/specs/README.md`; discuss follows the README when it states one.

### R2. `Capabilities:` per roadmap epic

`plugins/gin-workflow/src/skills/roadmap/SKILL.md` step 4 adds `Capabilities:` to each epic: the capabilities its requirements will go to, as names matching `[a-z][a-z0-9-]*` (the `_CAP` pattern `specs lint` enforces). Names come from `docs/specs/README.md` when the project has living specs, else from the Feature Catalog of `02-FEATURES.md`, else from the product brief. A capability without a folder under `docs/specs/` is marked `(new)`. With the legacy layout the line is omitted.

`plugins/gin-workflow/src/templates/roadmap.md` gains `Capabilities:` after `Scope:`; `plugins/gin-workflow/src/templates/epic.md` gains `Capabilities: {{capabilities}}` after `Out of scope:`, so the epic bead carries the list into `/discuss <epic-id>`. Roadmap step 6 fills it like the other fields.

### R3. Capabilities table in discuss

`gin-sdd` discuss gains a step before the current step 1 (`specs new`): the design that the user confirms includes a *Capabilities affected* table with one row per requirement group: capability (existing, or `(new)`), what goes there (feature requirements, UI, API, data), and the asset paths under `docs/specs/<capability>/assets/`. Sources, in order: the epic's `Capabilities:` line, `docs/specs/README.md`, `02-FEATURES.md`. The rule in R1 decides where UI requirements go. The step tells the user that a capability change after `specs next-id` means renumbering, which breaks test and archive citations.

Only after the user confirms the table does discuss run `specs new` and `specs next-id <cap>`.

### R4. Proposal records the choice

`01-proposal.md` `## Capabilities Affected` lists, per capability, its REQ-IDs and its asset paths. An asset the user placed elsewhere in the repository is moved with `git mv` into `docs/specs/<capability>/assets/` on the spec branch. An asset outside the repository is not copied: discuss asks the user to put it under that folder before the proposal is written. `specs lint --change` already stops discuss and ship when a cited asset is not committed.

### R5. Documentation and budgets

- `docs/guides/sdd.md` and `docs/guides/sdd.vi.md`: the placement rule (R1) in the images-and-mockups section, and the capabilities table in the stage table row for `discuss`.
- `docs/reference/skills.md` and its translation: the `roadmap` row names `Capabilities:` among what each epic carries.
- `skills/gin-*/SKILL.md` stay within 6,000 characters (`gin-sdd` is 3,300 today); `discuss` stays within the 12,000-character stage budget.

## User Stories

### US-1: One place for a feature's requirements
As a BA, I want a feature's requirements, including its UI, in the feature's own capability, so that the spec, the mockup, and the tests of that feature are found together.

Acceptance criteria:
- `gin-sdd` discuss and `docs/guides/sdd.md` state that feature requirements and their UI go to the feature's capability, and that `ui` holds only design system, layout, navigation, and shared components.
- For a change like gin-console's Reports page, the design places the page's UI requirements and the mockup under `reports`, not `ui`.
- A project rule written in `docs/specs/README.md` overrides the default.

### US-2: Capabilities named before discuss starts
As a BA, I want the roadmap to name each epic's capabilities, so that I start discuss from a list instead of defining capabilities myself.

Acceptance criteria:
- `gin-workflow specs template roadmap.md` and `epic.md` print a `Capabilities:` line.
- `/roadmap` proposes `Capabilities:` per epic from `docs/specs/README.md`, `02-FEATURES.md`, or the brief, marks missing folders `(new)`, and writes the line into the roadmap file and the epic bead description.
- An epic without the line still works: discuss proposes capabilities from the README and `02-FEATURES.md`, and asks only when both are missing.

### US-3: Capability confirmed before REQ-IDs exist
As a BA, I want to confirm where each requirement group and asset goes before IDs are assigned, so that no renumbering is needed later.

Acceptance criteria:
- With the SDD layout, discuss presents the capabilities table in the design and runs `specs new` and `specs next-id` only after the user confirms it.
- The table uses an existing capability when a proposed `(new)` name matches one in `docs/specs/README.md` (for example `report` and `reports`), and says so.
- `01-proposal.md` `## Capabilities Affected` lists each capability with its REQ-IDs and asset paths, and every asset path is under `docs/specs/<capability>/assets/`.

## Errors and compatibility

- A capability name that does not match `[a-z][a-z0-9-]*` is normalized in the table before the user confirms; `specs next-id` and `specs lint` reject other names.
- A proposed `(new)` capability whose name is a near duplicate of an existing one is replaced by the existing one; discuss never creates a second capability for the same feature.
- An epic created before this change, or by hand, has no `Capabilities:` line; discuss derives the list as in US-2.
- Without a tech-doc folder, roadmap takes the names from the brief as it does for the other fields.
- Legacy layout: no capabilities table, no `Capabilities:` line, no change.
- Existing roadmap files and epic beads without the line stay valid; `/roadmap` adds it on a re-run for epics it may update.

## Testing

- `tests/workflow_core/test_skill_routing.py` (or the existing skill-text test file for `gin-sdd`): `gin-sdd` discuss names the `ui` rule, presents the capabilities table before `specs new`, and records asset paths in `## Capabilities Affected`; `roadmap` step 4 names `Capabilities:`.
- `tests/workflow_core/test_specs.py` template test: `roadmap.md` and `epic.md` contain `Capabilities:` and pass the docs check.
- `tests/workflow_core/test_token_budget.py`: `gin-sdd` within 6,000 characters, `discuss` within 12,000.
- `gin-workflow docs check` on the changed docs pages exits 0; `mkdocs build --strict` runs in CI.
- Full suite `python3 -m pytest -n auto` through the pre-push hook.

# Diagrams in specs: activity diagram per feature, state diagram for complex features

Epic: gin-workflow-ycg8
Status: draft for user review.

## Goal and scope

With the SDD layout, a capability's living spec `docs/specs/<capability>/spec.md` holds only requirement blocks (`### REQ-<CAP>-<NNN>`), and a change's `03-design.md` has a `## Data Flow` section that `specs archive` moves into `<changes>/archive/` with the change folder (`specs_archive.py:54-98`). Nothing in the living specs shows how a feature flows or which states an entity goes through, so a BA reading `docs/specs/` has requirements without the picture that connects them.

This spec adds, for the SDD layout only:
- diagram files per capability in `docs/specs/<capability>/diagrams/`, Mermaid, edited directly on the spec branch like assets;
- templates `activity.md` and `state.md`, and a `## Diagrams` section in the living spec template;
- lint: each diagram file holds a Mermaid block of its kind, and a change that adds or modifies requirements of a capability needs an activity diagram there;
- the convention in `gin-sdd` and the guides.

Out of scope:
- The SRS export (`gin-workflow-bel0`); it reads `diagrams/` later.
- Merging diagrams through the spec delta: diagram files are not requirement blocks and carry no `base:` hash. `specs archive` changes only as R2 states, to link the diagrams of a new capability.
- Diagrams embedded in requirement blocks, and making `parse_blocks` fence-aware.
- Checking the links in `## Diagrams`, or that every diagram file is linked.
- Rendering Mermaid: the project's own tooling (GitHub, its docs site) renders `docs/specs/`.
- The legacy layout.

## Requirements

### R1. Diagram files

A capability's diagrams live in `docs/specs/<capability>/diagrams/` (under `artifacts.specs`):
- `<feature>-activity.md`: the flow of one feature, a Mermaid `flowchart` (or `graph`);
- `<entity>-state.md`: the states and transitions of one entity, a Mermaid `stateDiagram-v2`;
- names match `[a-z][a-z0-9-]*` before the suffix. Other files in `diagrams/` (a sequence diagram, for example) are allowed and not checked.

Each file holds a title, one or two sentences on what the diagram covers, and one ```` ```mermaid ```` block. Discuss edits the files directly on the spec branch, as it does assets; `specs archive` never moves or edits them.

Reviewers see the diagrams with the change: `03-design.md` `## Data Flow` cites each diagram path in backticks, so `specs lint --change` requires the files committed (the existing check on cited paths) and a `pr` spec review carries them; `01-proposal.md` `## Capabilities Affected` lists each capability's diagram paths next to its asset paths.

Every feature gets an activity diagram. An entity gets a state diagram when it has three or more states, or a transition allowed only under a condition (a role, a field value, a time limit). This rule is a skill convention; lint cannot judge it.

### R2. Templates

- `plugins/gin-workflow/src/templates/activity.md` and `state.md`, printed by `gin-workflow specs template activity.md` / `state.md` and overridable in `.agent-workflow/templates/` like every template. Each carries a `# {{title}}` line, an explanatory comment, a description line, and a Mermaid block of its kind with a two-step example.
- `templates/spec.md` gains `## Diagrams` (a list of links to `diagrams/` files) between `## Purpose` and `## Requirements`. `## Requirements` stays the last section because archive appends `ADDED` blocks at the end of the file (`specs_archive.py:38-43`).
- When `specs archive` creates `spec.md` for a new capability, it fills `## Diagrams` with one line `- [<file stem>](diagrams/<file>)` per `diagrams/*.md` file of that capability, sorted by name. An existing `spec.md` is not touched outside its requirement blocks: discuss adds the link there itself. A project template without a `## Diagrams` line gets no links.
- `templates/design.md` gains a comment under `## Data Flow`: link the capability's diagram files instead of copying them.

### R3. Lint

`workflow_core/specs.py` gains `lint_diagrams(root, cfg)`. For every `<specs>/*/diagrams/*-activity.md` and `*-state.md`, it reads the ```` ```mermaid ```` blocks; the first line inside a block that is not empty and does not start with `%%` names the diagram type. A file with no block of the right type is a finding:

`docs/specs/reports/diagrams/report-filter-activity.md: no mermaid block starting with flowchart or graph`
`docs/specs/orders/diagrams/order-state.md: no mermaid block starting with stateDiagram`

`lint_living` and `lint_change` both append its findings.

`lint_change` also reports each capability with an `ADDED` or `MODIFIED` block in the change's `02-spec-delta.md` that has no `diagrams/*-activity.md` file:

`reports: no activity diagram in docs/specs/reports/diagrams/ (gin-workflow specs template activity.md)`

A delta with only `REMOVED` blocks for a capability needs no diagram there. `specs lint --change` and `specs archive` therefore stop on both findings.

### R4. Skill and documentation

- `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md`, discuss step 3: one activity diagram per feature from `specs template activity.md`, a state diagram per R1's rule from `specs template state.md`, both in `<specs>/<cap>/diagrams/`, cited in `03-design.md` `## Data Flow`, listed in `## Capabilities Affected`, and linked from `spec.md` `## Diagrams` when the capability already has one. The file stays within 6,000 characters.
- `docs/guides/sdd.md` and `docs/guides/sdd.vi.md`: a `## Diagrams` section with the folder, the two kinds, the state-diagram rule, the templates, and the lint checks; the layout tree shows `diagrams/`.
- `docs/guides/customizing-templates.md` and `.vi.md`: `activity.md` and `state.md` in the template list and table.
- `docs/reference/cli.md`: `specs lint` also checks diagram files, and `--change` requires an activity diagram.

## User Stories

### US-1: A feature's flow next to its requirements
As a BA, I want an activity diagram for each feature in the capability's living spec folder, so that a reader sees the flow that connects the requirements.

Acceptance criteria:
- `gin-workflow specs template activity.md` prints a template with a ```` ```mermaid ```` block starting with `flowchart`.
- `gin-sdd` discuss tells the agent to write `<specs>/<cap>/diagrams/<feature>-activity.md`, link it from `03-design.md` `## Data Flow` and from `spec.md` `## Diagrams` when the capability has a `spec.md`, and list it in `01-proposal.md` `## Capabilities Affected`.
- `gin-workflow specs template spec.md` prints `## Diagrams` before `## Requirements`.
- After `specs archive`, the diagram file is unchanged at `docs/specs/<cap>/diagrams/`; for a new capability, its new `spec.md` links each diagram file under `## Diagrams`.

### US-2: State diagram for a complex entity
As a BA, I want a state diagram for an entity with several states or guarded transitions, so that the allowed transitions are explicit before tests are written.

Acceptance criteria:
- `gin-workflow specs template state.md` prints a template with a ```` ```mermaid ```` block starting with `stateDiagram-v2`.
- `gin-sdd` discuss names the rule: three or more states, or a transition allowed only under a condition.

### US-3: Lint catches a missing or malformed diagram
As a BA, I want lint to stop a change whose capability has no activity diagram, or whose diagram file is not a diagram of its kind, so that the living specs keep their diagrams.

Acceptance criteria:
- `specs lint --change <epic>` exits 1 and names the capability when the delta has an `ADDED` or `MODIFIED` block for it and `<specs>/<cap>/diagrams/` has no `*-activity.md`.
- The same change passes once `<specs>/<cap>/diagrams/<feature>-activity.md` holds a `flowchart` block.
- A delta with only `REMOVED` blocks for a capability without diagrams passes.
- `specs lint` exits 1 and names the file for a `*-activity.md` without a `flowchart`/`graph` block and for a `*-state.md` without a `stateDiagram` block; a `%%` comment line before the type is skipped.
- A file in `diagrams/` without the `-activity.md` or `-state.md` suffix produces no finding.

## Errors and compatibility

- A project with no `diagrams/` folders sees no change in `specs lint` (living) results.
- A change already in flight that adds or modifies requirements of a capability without an activity diagram fails `specs lint --change` and `specs archive` after upgrading, until the diagram is added; the message names the template command.
- A Mermaid block that starts with front matter (`---`) or an `%%{init}%%` directive: the directive starts with `%%` and is skipped; front matter is not supported by the check and is a finding (assumption: specs do not use Mermaid front matter).
- Mermaid syntax inside the block is not validated; only the diagram type on its first line.
- Legacy layout: no change; `specs` commands exit 2 there as today.

## Testing

- `tests/workflow_core/test_specs.py`: `lint_diagrams` findings for a missing block and a wrong type in each kind, no finding for a valid file, a `%%` line skipped, an unsuffixed file ignored; `lint_change` finding for `ADDED` and for `MODIFIED` without an activity diagram, none with one, none for a `REMOVED`-only delta; `specs template activity.md`, `state.md`, `spec.md` print the expected lines.
- `tests/workflow_core/test_specs_archive_trace.py`: archiving a new capability with two diagram files writes both links under `## Diagrams` before `## Requirements`; an existing capability's `spec.md` keeps its text outside the requirement blocks.
- `tests/workflow_core/test_skill_routing.py`: `gin-sdd` discuss names `diagrams/`, `specs template activity.md`, `specs template state.md`, and the state-diagram rule.
- `tests/workflow_core/test_token_budget.py`: `gin-sdd` within 6,000 characters.
- `gin-workflow docs check` on the changed docs pages exits 0; `mkdocs build --strict` runs in CI.
- Full suite `python3 -m pytest -n auto` through the pre-push hook.

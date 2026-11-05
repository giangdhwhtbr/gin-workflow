# Spec assets: dated iteration folders and legacy capture

Epic: gin-workflow-spec-iterations
Status: draft for user review.

## Goal and scope

With the SDD layout, a capability's input assets (mockups, screenshots, briefs) live in `docs/specs/<capability>/assets/` (`gin-sdd` discuss step 1, `docs/guides/sdd.md` "Images and mockups"). The folder is flat: when a customer comes back with new requirements, changes, or designs, the new files land next to the old ones and nothing records which request they came from, when, or what changed. For a legacy project without design specs, there is no place for screenshots of the existing feature and no text that describes it.

This spec adds, for the SDD layout only:
- dated iteration folders `docs/specs/<capability>/assets/<YYYY-MM-DD>/`, one per batch of inputs, each with a required `description.md`;
- a `legacy/` subfolder for screenshots of an existing feature, described by the same `description.md`;
- a template `iteration.md` for `description.md`;
- a `specs lint` check that every dated folder has `description.md`;
- the convention in `gin-sdd` and the guides.

Out of scope:
- A CLI that creates the folder (`specs assets new`, listed in the roadmap). The folder is a `mkdir` plus `gin-workflow specs template iteration.md`; the skill does both. The `gin-ba` plugin (`gin-workflow-ba-plugin`) may add a command later if it needs one.
- Generating mockups or describing legacy screens from images (`gin-workflow-ba-plugin`).
- Moving existing flat assets into dated folders.
- Assets inside change folders, or `specs archive` moving assets: assets stay under the capability, as decided in `gin-workflow-7xy4`.
- The legacy layout: `specs` commands already require the SDD layout.

## Requirements

### R1. Iteration folder layout

An iteration folder is `docs/specs/<capability>/assets/<YYYY-MM-DD>/` (under `artifacts.specs`), named by the ISO date the inputs arrived (default: the day discuss creates it). It holds:
- `description.md`, required;
- the input files of that batch (images, PDFs, briefs);
- optional `mockup/` and `legacy/` subfolders.

A new batch of inputs gets a new dated folder; an older dated folder is never edited, so the folders form the history of the capability's inputs. A flat file directly under `assets/` stays valid. Requirement blocks link files with paths relative to the capability's `spec.md` (`assets/2026-05-11/login-form.png`), as `docs/guides/sdd.md` already describes for flat assets.

### R2. Template `iteration.md`

`plugins/gin-workflow/src/templates/iteration.md`, printed by `gin-workflow specs template iteration.md` and overridable in `.agent-workflow/templates/iteration.md` like every template. It carries:
- a title line with the capability and the date;
- `Kind:` one of `new`, `change`, `legacy`;
- `Source:` where the inputs came from (meeting, email, ticket, or the legacy screens captured);
- `Previous:` the earlier dated folder this one follows, or `none`;
- `## Summary`: what was asked, or for `legacy` what the existing feature does today;
- `## Changes`: for `change`, what differs from the previous iteration;
- `## Files`: one line per file, naming the screen and state it shows.

### R3. Lint check

`workflow_core/specs.py` gains `lint_iterations(root, cfg)`: for every directory matching `<specs>/*/assets/<YYYY-MM-DD>/` (four digits, two, two), including capabilities without a `spec.md` yet, a missing `description.md` is a finding:

`docs/specs/reports/assets/2026-05-11: missing description.md (gin-workflow specs template iteration.md)`

`lint_living` and `lint_change` both append its findings, so `specs lint`, `specs lint --change`, and `specs archive` report them. A directory under `assets/` whose name is not an ISO date is not checked.

### R4. Skill and documentation

- `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md`, discuss steps 1 and 3: assets are cited as `<specs>/<cap>/assets/<date>/<file>`; each new batch of inputs goes to a new dated folder with `description.md` from `specs template iteration.md`; screenshots of an existing feature go under `legacy/` with `Kind: legacy`; an older dated folder is never edited. The file stays within 6,000 characters.
- `docs/guides/sdd.md` and `docs/guides/sdd.vi.md`, "Images and mockups": the folder tree, the rules of R1, the template, and the lint check.
- `docs/guides/customizing-templates.md` and `.vi.md`: `iteration.md` in the template list and table.
- `docs/reference/cli.md`: `specs lint` also checks dated asset folders.

## User Stories

### US-1: One folder per customer iteration
As a BA, I want each batch of customer requirements, changes, and designs in its own dated folder with a description, so that I can tell which request every asset came from and what changed since the previous one.

Acceptance criteria:
- `gin-workflow specs template iteration.md` prints a template with `Kind:`, `Source:`, `Previous:`, `## Summary`, `## Changes`, and `## Files`.
- `gin-sdd` discuss tells the agent to put a new batch of inputs in `<specs>/<cap>/assets/<YYYY-MM-DD>/` with `description.md`, and never to edit an older dated folder.
- A requirement block linking `assets/2026-12-01/report-filter.png` resolves from the capability's `spec.md` after archive.

### US-2: Legacy features captured from screenshots
As a BA on a legacy project without design specs, I want to store screenshots of an existing feature with a description of how it behaves today, so that discuss can write requirements for the change against a recorded baseline.

Acceptance criteria:
- `gin-sdd` discuss tells the agent to put screenshots of an existing feature under `<specs>/<cap>/assets/<date>/legacy/` and to set `Kind: legacy` in that folder's `description.md`.
- `docs/guides/sdd.md` shows the `legacy/` subfolder in the folder tree.

### US-3: A dated folder without a description is caught
As a BA, I want lint to stop a change whose dated asset folder has no description, so that no batch of inputs is left unexplained.

Acceptance criteria:
- `specs lint` and `specs lint --change <epic>` exit 1 and name the folder when `<specs>/<cap>/assets/<YYYY-MM-DD>/` has no `description.md`.
- The same folder with `description.md` produces no finding.
- `<specs>/<cap>/assets/mockup/` and flat files under `assets/` produce no finding.

## Errors and compatibility

- A project with no dated folders sees no change in lint results.
- A folder named with another date format (`110526`) is not recognized as an iteration and is not checked; the guide names the ISO format.
- `lint_change` reports dated folders of every capability, not only those the change cites: a missing description anywhere blocks the change until it is added. This keeps one rule and one function; the cost is a finding unrelated to the change, which the message makes easy to fix.
- Legacy layout: no change; `specs` commands exit 2 there as today.
- Scope change from the roadmap: no `specs assets new` command (see Goal and scope); recorded in the epic bead notes.

## Testing

- `tests/workflow_core/test_specs.py`: a dated folder without `description.md` is a finding in `lint_living` and in `lint_change`; with `description.md` there is none; `assets/mockup/` and a flat file are ignored; a dated folder under a capability without `spec.md` is checked; `specs template iteration.md` prints the template.
- `tests/workflow_core/test_token_budget.py`: `gin-sdd` within 6,000 characters.
- `gin-workflow docs check` on the changed docs pages exits 0; `mkdocs build --strict` runs in CI.
- Full suite `python3 -m pytest -n auto` through the pre-push hook.

# Use cases in living specs and the SRS

Workflow: use-cases
Status: confirmed by the user on 2026-11-09.

## Goal and scope

A business analyst can write use cases for a capability in the SDD layout, next to its requirements and diagrams, and `gin specs export` prints them in the SRS.

Confirmed understanding (2026-11-09):

- A capability folder holds `spec.md` (requirement blocks), `diagrams/` (Mermaid files edited directly on the spec branch, no ID, no delta), and `assets/` (dated input folders).
- `specs export` builds each SRS chapter from the template `srs-capability.html` with the placeholders `cap`, `capability`, `purpose`, `diagrams`, `requirements`, `assets` (`specs_export.py:_chapter`).
- User decisions (2026-11-09):
  - Use cases follow the diagrams model: one file per use case, `<specs>/<cap>/use-cases/<slug>.md`, edited directly on the spec branch, no ID or hash, never in `02-spec-delta.md`.
  - Use cases are optional: no lint rule requires a capability to have one.

In scope: the `use-case.md` template, lint of use-case files, the `use_cases` placeholder in the SRS chapter, archive linking for a new capability, the `sdd` skill, tests, and docs.

Out of scope:
- `/gin:explain` (`specs_explain.py`) and the `gin-ba` plugin.
- The legacy layout, which has no living specs and no SRS.
- Turning REQ-IDs in a use case into links in the SRS.

## Requirements

### R1. Template

`gin specs template use-case.md` prints:

```markdown
# <Use case name>

Actor: <primary actor>
Requirements: REQ-<CAP>-NNN, …

## Goal
## Preconditions
## Main flow
1. …
## Alternative flows
### 2a. <condition>
## Postconditions
```

A project overrides it in `.agent-workflow/templates/use-case.md`, like the other templates. The `spec.md` template gains an empty `## Use Cases` section after `## Diagrams`.

### R2. Lint

`specs lint` (living and `--change`) checks each `<specs>/<cap>/use-cases/*.md` and reports, per file:

- no `# ` title line;
- no `Actor:` line with a value;
- no `Requirements:` line, or one with no REQ-ID;
- no `## Main flow` section holding a numbered list;
- a REQ-ID on the `Requirements:` line that is neither in a living spec nor `ADDED` or `MODIFIED` in an open change folder's spec delta (a REQ only `REMOVED` counts as missing).

A capability without `use-cases/` raises nothing. Other files in `use-cases/` (not `.md`) are not checked.

### R3. SRS export

`srs-capability.html` gains `<h2>Use Cases</h2>` and `{{use_cases}}` between Purpose and Diagrams. Each file in `use-cases/`, sorted by name, becomes `<section class="use-case" id="<cap>-<stem>">` rendered with `markdown_html`, so images embed and missing ones are reported as today. A capability without use cases gets an empty section, as diagrams do. A project template without the placeholder exports without use cases and without an error. The table of contents does not change.

### R4. Archive

When `specs archive` creates `spec.md` for a new capability, it links every file in `use-cases/` under `## Use Cases` (`- [<stem>](use-cases/<file>)`), next to the existing diagram links (`specs_archive.py:81`). An existing `spec.md` is not touched; discuss adds the link there.

### R5. Discuss (`sdd` skill)

Step 3 of the `sdd` skill's discuss section says: write a use case from `specs template use-case.md` when a feature has an actor interacting with the system or the user asks for one; list it in `01-proposal.md` `## Capabilities Affected`; link it from `## Use Cases` of an existing `spec.md`; its `Requirements:` names the REQ-IDs it covers.

## User Stories

### US-1: Write use cases for a capability
As a business analyst, I want to keep use cases next to a capability's requirements, so that the actor flows are reviewed with the spec.

Acceptance criteria:
- `gin specs template use-case.md` prints the template of R1.
- A use case citing a REQ that exists only in an open change's delta passes `specs lint`.
- A use case without `Actor:` or with an unknown REQ-ID fails `specs lint` with the file named.
- A capability with no `use-cases/` folder passes `specs lint` as before.

### US-2: Show use cases in the SRS
As a business analyst, I want the exported SRS to show each capability's use cases, so that the customer reads the flows with the requirements.

Acceptance criteria:
- `gin specs export <cap>` prints a `Use Cases` section with one section per use-case file, between Purpose and Diagrams.
- `gin specs export --all` does the same for each chapter.
- An overridden `srs-capability.html` without `{{use_cases}}` exports without error.

### US-3: Link use cases of a new capability
As a business analyst, I want archive to link the use cases of a new capability, so that `spec.md` lists them without a manual edit.

Acceptance criteria:
- Archiving a change that creates a capability with `use-cases/a.md` writes `- [a](use-cases/a.md)` under `## Use Cases` of the new `spec.md`.

## Errors and compatibility

- Lint findings exit 1, as the other lint findings do.
- Existing projects: no new finding unless they add `use-cases/`. A project-overridden `srs-capability.html` keeps working; `customizing-templates.md` documents the new placeholder.
- An existing `spec.md` without `## Use Cases` stays valid.
- `dist/` is regenerated by the build; no hand edits there.

## Testing

Unit tests in the existing specs test files:
- template listing and content;
- lint: valid file, each finding of R2, REQ in an open delta, REQ only removed, no folder;
- export: with use cases, without, template without the placeholder, missing image in a use case;
- archive: new capability links use cases; existing `spec.md` untouched.

Full suite: `python3 -m pytest -n auto`.

Docs: `docs/guides/sdd.md` (layout tree, a Use cases section, SRS paragraph), `docs/guides/ba.md`, `docs/guides/customizing-templates.md`, their `.vi.md` versions, and the template list in `docs/reference/cli.md`.

## Open Technical Questions

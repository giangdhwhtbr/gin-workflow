---
name: sdd
description: Use in a lifecycle stage when `project.layout` is `sdd` — change folders, REQ-IDs, trace, spec review, archive.
---

# SDD Layout

Applies only when `gin state --format json` reports `project.layout: sdd`. Paths come from `artifacts.specs` (default `docs/specs`) and `artifacts.changes` (default `docs/changes`). Every `state`/`record` call for a change passes `--workflow-id <epic>`. All commands are `gin specs <command>`; exit 1 means findings to fix, exit 2 means wrong usage or layout. `specs export <cap>` (or `--all`) writes the living specs into one printable SRS HTML file.

## discuss
1. In the design the user confirms, present a *Capabilities affected* table: per requirement group, the capability (an existing folder under `artifacts.specs`, or `(new)`), what goes there, its assets as `<specs>/<cap>/assets/<YYYY-MM-DD>/<file>`. Sources, in order: the epic's `Capabilities:` line, `<specs>/README.md`, the tech-doc `02-FEATURES.md`; ask only when all are missing. Rule: a feature's requirements, its UI included, go to the feature's capability; `ui` holds only design system, layout, navigation, and shared components; a rule written in `<specs>/README.md` overrides this. Normalize names to `[a-z][a-z0-9-]*`; when a `(new)` name nearly matches an existing capability (`report`, `reports`), use the existing one and say so. Say that changing a capability after `specs next-id` means renumbering.
2. After the user confirms the design: `gin task create --type epic --title "<title>"` → `specs new <slug> --epic <epic>` creates `<changes>/<epic>-<slug>/`.
3. Write `01-proposal.md`, `02-spec-delta.md`, and `03-design.md` in that folder (the number prefix is the reading order; an older unnumbered folder keeps its names). `01-proposal.md` lists `## User Stories` from `specs template user-story.md`, each with `REQ:`. `## Capabilities Affected` lists each capability with its REQ-IDs and asset paths; each batch of inputs gets a new dated folder: `specs assets add <cap> <files...> [--date <YYYY-MM-DD>]` copies the files, from inside or outside the repository, and writes `description.md` (`Kind:`, `Previous:`, `Confirmed: no`); `--legacy` puts screenshots of an existing feature under `legacy/`; delete an original only when the user asks. Never edit an older dated folder: `specs lint` reports a change to a folder confirmed on the base branch. Before writing requirements, read `description.md` and any `mockup/index.html` of each dated folder of the affected capabilities: cite only a folder whose `description.md` reads `Confirmed: <date>`, and ask the user to confirm or leave out one with `Confirmed: no` or no such line; turn its `## Open questions` into questions or listed assumptions; a requirement taken from an input gets a `Source:` line after its statement, with backticked paths (`#<screen-id>` for a mockup screen). Each feature gets an activity diagram `<specs>/<cap>/diagrams/<feature>-activity.md` from `specs template activity.md`; an entity with three or more states, or a transition allowed only under a condition, gets `<entity>-state.md` from `specs template state.md`. Cite them in `03-design.md` `## Data Flow`, list them in `## Capabilities Affected`, and link them from `## Diagrams` of an existing `spec.md`. A feature with an actor interacting with the system, or one the user asks for, gets a use case `<specs>/<cap>/use-cases/<slug>.md` from `specs template use-case.md`, its `Requirements:` naming the REQ-IDs it covers; list it in `## Capabilities Affected` and link it from `## Use Cases` of an existing `spec.md`. Each new requirement gets its ID from `specs next-id <cap>`; a `MODIFIED` or `REMOVED` block puts the output of `specs hash <REQ-ID>` on the line after its heading, and a `REMOVED` block adds `Reason: <why>`. An architecture decision also gets `docs/adr/NNNN-<slug>.md` from `specs template adr.md`.
4. `specs lint --change <epic>` must exit 0. When it reports an untracked cited file (an ADR, a mockup), commit it with the change folder and lint again.
5. `project.spec_review`:
   - `chat`: the user confirms → `gin record requirement-confirmed --workflow-id <epic> --evidence <change folder> --actor <id>`.
   - `pr`: commit only the change folder and the files it cites on branch `spec/<epic>-<slug>` and push; get approval (stage-contract Approvals), then open the PR (team mode: the `team.host` command from the `team` skill's references/hosts.md; else `gh pr create --fill`); return `awaiting_spec_review` without recording. On a later run, `specs status --change <epic>`: `merged` → record `requirement-confirmed` with evidence `<pr url> <merge commit>`; `open` → report and stop; `closed` or `none` → ask the user. Implementation branches from the updated base.

## plan
Write `<change>/04-plan.md`. Each track's Metadata adds `Requirements: REQ-…`; every `ADDED`/`MODIFIED` REQ in the delta belongs to at least one track. Record `plan-approved --workflow-id <epic>`.

## orchestrate
Reuse the epic as parent. Each track bead: `gin task create --parent <epic> --spec-id <epic>-<slug> --labels req:<REQ-ID>,…` from its `Requirements:`.

## execute and review
New or changed tests carry the REQ-ID in the test name or a comment (`# REQ-AUTH-003`). The reviewer checks that each scenario of the track's REQs has a test.

## ship
Before presenting options, run `specs lint --change <epic> --against <base>` and `specs trace --change <epic>`. A `missing` REQ is a warning under `easy` rigor and stops ship under `standard` and `strict`. A duplicate ID on the base: `specs renumber <old> <new> --change <epic>`, then rerun both. Then, on the feature branch: `specs archive --change <epic>`, then commit (`docs(specs): archive <epic>`). Exit 1 (a living block changed since the delta, or lint findings) stops ship: show the findings and ask the user.

## quick
Never creates a change folder. If the change alters behavior a living-spec REQ describes, stop and recommend the full lifecycle.

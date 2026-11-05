---
name: gin-sdd
description: Use in a lifecycle stage when `project.layout` is `sdd` — change folders, REQ-IDs, trace, spec review, archive.
---

# SDD Layout

Applies only when `gin-workflow state --format json` reports `project.layout: sdd`. Paths come from `artifacts.specs` (default `docs/specs`) and `artifacts.changes` (default `docs/changes`). Every `state`/`record` call for a change passes `--workflow-id <epic>`. All commands are `gin-workflow specs <command>`; exit 1 means findings to fix, exit 2 means wrong usage or layout.

## discuss
1. In the design the user confirms, present a *Capabilities affected* table: per requirement group, the capability (an existing folder under `artifacts.specs`, or `(new)`), what goes there, and its assets as `<specs>/<cap>/assets/<YYYY-MM-DD>/<file>`. Sources, in order: the epic's `Capabilities:` line, `<specs>/README.md`, the tech-doc `02-FEATURES.md`; ask only when all are missing. Rule: a feature's requirements, its UI included, go to the feature's capability; `ui` holds only design system, layout, navigation, and shared components; a rule written in `<specs>/README.md` overrides this. Normalize names to `[a-z][a-z0-9-]*`; when a `(new)` name nearly matches an existing capability (`report`, `reports`), use the existing one and say so. Say that changing a capability after `specs next-id` means renumbering, which breaks test names and archived citations.
2. After the user confirms the design: `gin-workflow task create --type epic --title "<title>"` (a roadmap epic is reused as is) → `specs new <slug> --epic <epic>` creates `<changes>/<epic>-<slug>/`.
3. Write `01-proposal.md`, `02-spec-delta.md`, and `03-design.md` in that folder (the number prefix is the reading order; a folder from before numbering keeps its unnumbered names, which every `specs` command still reads). `01-proposal.md` lists `## User Stories` from `specs template user-story.md`, each with `REQ:`. `## Capabilities Affected` lists each capability with its REQ-IDs and asset paths; `git mv` an asset placed elsewhere in the repository into `<specs>/<cap>/assets/`; an asset outside the repository is not copied: ask the user to put it there first. Each batch of inputs gets a new dated folder `assets/<YYYY-MM-DD>/` (the day it arrived) with `description.md` from `specs template iteration.md` (`Kind:` `new`, `change`, or `legacy`); screenshots of an existing feature go under its `legacy/`; never edit an older dated folder. Each feature gets an activity diagram `<specs>/<cap>/diagrams/<feature>-activity.md` from `specs template activity.md`; an entity with three or more states, or a transition allowed only under a condition, gets `<entity>-state.md` from `specs template state.md`. Cite them in `03-design.md` `## Data Flow`, list them in `## Capabilities Affected`, and link them from `## Diagrams` of an existing `spec.md` (archive links them for a new capability). Each new requirement gets its ID from `specs next-id <cap>`; a `MODIFIED` or `REMOVED` block puts the output of `specs hash <REQ-ID>` on the line after its heading, and a `REMOVED` block adds `Reason: <why>`. An architecture decision also gets `docs/adr/NNNN-<slug>.md` from `specs template adr.md`.
4. `specs lint --change <epic>` must exit 0. When it reports a cited file that git does not track (an ADR, a mockup), commit that file with the change folder and lint again.
5. `project.spec_review`:
   - `chat`: the user confirms → `gin-workflow record requirement-confirmed --workflow-id <epic> --evidence <change folder> --actor <id>`.
   - `pr`: commit only the change folder and the files it cites on branch `spec/<epic>-<slug>` and push; get approval (stage-contract Approvals), then `gh pr create --fill`; return `awaiting_spec_review` without recording. On a later run, `specs status --change <epic>`: `merged` → record `requirement-confirmed` with evidence `<pr url> <merge commit>`; `open` → report and stop; `closed` or `none` → ask the user. Implementation branches from the updated base.

## plan
Write `<change>/04-plan.md`. Each track's Metadata adds `Requirements: REQ-…`; every `ADDED`/`MODIFIED` REQ in the delta belongs to at least one track. Record `plan-approved --workflow-id <epic>`.

## orchestrate
Reuse the epic as parent. Each track bead: `gin-workflow task create --parent <epic> --spec-id <epic>-<slug> --labels req:<REQ-ID>,…` from its `Requirements:`.

## execute and review
New or changed tests carry the REQ-ID in the test name or a comment (`# REQ-AUTH-003`). The reviewer checks that each scenario of the track's REQs has a test.

## ship
Before presenting options, run `specs lint --change <epic> --against <base>` and `specs trace --change <epic>`. A `missing` REQ is a warning under `easy` rigor and stops ship under `standard` and `strict`. A duplicate ID on the base: `specs renumber <old> <new> --change <epic>`, then rerun both. Then, on the feature branch: `specs archive --change <epic>`, then commit (`docs(specs): archive <epic>`). Exit 1 (living block changed since the delta was written, or lint findings) stops ship: show the findings and ask the user.

## quick
Never creates a change folder. If the change alters behavior a living-spec REQ describes, stop and recommend the full lifecycle.

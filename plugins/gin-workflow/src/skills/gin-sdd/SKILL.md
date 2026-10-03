---
name: gin-sdd
description: Use in a lifecycle stage when `project.layout` is `sdd` — change folders, REQ-IDs, trace, spec review, archive.
---

# SDD Layout

Applies only when `gin-workflow state --format json` reports `project.layout: sdd`. Paths come from `artifacts.specs` (default `docs/specs`) and `artifacts.changes` (default `docs/changes`). Every `state`/`record` call for a change passes `--workflow-id <epic>`. All commands are `gin-workflow specs <command>`; exit 1 means findings to fix, exit 2 means wrong usage or layout.

## discuss
1. After the user confirms the design: `bd create --type epic --title "<title>"` → `specs new <slug> --epic <epic>` creates `<changes>/<epic>-<slug>/`.
2. Write `proposal.md`, `spec-delta.md`, and `design.md` in that folder. Each new requirement gets its ID from `specs next-id <cap>`; a `MODIFIED` or `REMOVED` block puts the output of `specs hash <REQ-ID>` on the line after its heading, and a `REMOVED` block adds `Reason: <why>`. An architecture decision also gets `docs/adr/NNNN-<slug>.md` from `specs template adr.md`.
3. `specs lint --change <epic>` must exit 0.
4. `project.spec_review`:
   - `chat`: the user confirms → `gin-workflow record requirement-confirmed --workflow-id <epic> --evidence <change folder> --actor <id>`.
   - `pr`: commit only the change folder on branch `spec/<epic>-<slug>` and push; ask approval, then `gh pr create --fill`; return `awaiting_spec_review` without recording. On a later run, `specs status --change <epic>`: `merged` → record `requirement-confirmed` with evidence `<pr url> <merge commit>`; `open` → report and stop; `closed` or `none` → ask the user. Implementation branches from the updated base.

## plan
Write `<change>/plan.md`. Each track's Metadata adds `Requirements: REQ-…`; every `ADDED`/`MODIFIED` REQ in the delta belongs to at least one track. Record `plan-approved --workflow-id <epic>`.

## orchestrate
Reuse the epic as parent. Each track bead: `bd create --parent <epic> --spec-id <epic>-<slug> --labels req:<REQ-ID>,…` from its `Requirements:`.

## execute and review
New or changed tests carry the REQ-ID in the test name or a comment (`# REQ-AUTH-003`). The reviewer checks that each scenario of the track's REQs has a test.

## verify
Run `specs lint --change <epic> --against <base>` and `specs trace --change <epic>`. A `missing` REQ is a warning under `easy` rigor and blocks `verification-passed` under `standard` and `strict`. A duplicate ID on the base: `specs renumber <old> <new> --change <epic>`, then rerun both.

## ship
Before presenting options, on the feature branch: `specs archive --change <epic>`, then commit (`docs(specs): archive <epic>`). Exit 1 (living block changed since the delta was written, or lint findings) stops ship: show the findings and ask the user.

## quick
Never creates a change folder. If the change alters behavior a living-spec REQ describes, stop and recommend the full lifecycle.

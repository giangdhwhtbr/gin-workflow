# Retired requirement IDs

Workflow: retired-req-ids
Kind: capability
Points: 8 (5 stories, 9 modules (specs, archive, signoff, reqs, trace, trace --all, export, explain, gin-qa) and 1 new command; medium: every reader of living requirements must skip retired ones)
Status: draft for user review.

## Goal and scope

GitHub issue #39. In the SDD layout a requirement ID that a spec review drops leaves no trace:

- A block deleted from an open change's delta before archive is gone from every tree, so `gin specs next-id` returns `max + 1` (`specs.py:1015`) over ids that no longer include it, and hands the number out again when it was the highest of its capability. `scan_ids` (`specs.py:993`) reads the current tree, the local worktrees and the remote-tracking branches, not history.
- A `## REMOVED` block is deleted from the living `spec.md` at archive (`specs_archive.py:27`); its reason survives only in the archived change folder. Readers see `REQ-AUTH-017, REQ-AUTH-019` and ask to renumber, which breaks every test name, QA case pin, bead label and commit that cites the shifted numbers.
- No section can hold a dropped id: `DELTA_SECTIONS` is `ADDED`, `MODIFIED`, `REMOVED` (`specs.py:26`), and `REMOVED` refuses an id that is neither living nor added by an open change (`specs.py:881`).

This epic adds a retired state for a requirement ID: a `## RETIRED` section in the change delta and a `## Retired` section in the living spec, a history scan so `next-id` never hands out a used number, readers that skip retired ids, and `gin specs gaps` to backfill the gaps that already exist.

In scope:

- The `## RETIRED` delta section, its lint, its sign-off, and archive into `## Retired` of `spec.md`; archive of `REMOVED` also leaves a `## Retired` entry.
- The git-history source of `scan_ids`, used by `next-id` and `renumber`.
- `living_blocks` skips `## Retired`; `retired_blocks` returns it. `gin specs reqs`, `trace`, `trace --all`, `export`, `explain`, use-case and diagram lint, and gin-qa handle retired ids.
- `gin specs gaps [<cap>] [--into <change>]`.
- Templates `spec-delta.md` and `spec.md`, the `sdd` and `qa-track` skills, `docs/guides/sdd.md` and `sdd.vi.md`, `docs/reference/cli.md`.

Out of scope:

- Renumbering to close a gap; the skill forbids it.
- Writing `## Retired` entries for `REMOVED` blocks archived before this epic without a command run: `gin specs gaps` proposes them, a person runs it.
- A new state value in `trace --all`: retired ids keep state `removed`, the value gin-console's `State` literal accepts (`gin-console/backend/src/gin_console/requirements/models.py:5`).
- The legacy layout, which has no REQ-IDs.
- `docs/changelog.md`, written at release time (`docs/contributing.md:115`).

## Requirements

### Format

A retired entry is a requirement heading and a reason, with no statement and no scenario:

```markdown
## RETIRED

### REQ-AUTH-002: Lock out
Reason: dropped in spec review; lockout moves to the rate-limit epic.
```

The delta section is `## RETIRED`; the living spec section is `## Retired`, the last section of `spec.md`. Both keep the `### REQ-<CAP>-<NNN>: <title>` heading, so `_HEADING_LINE`, `ids_at_ref` and `git grep '^### REQ-'` see the id unchanged. `parse_blocks` records the section; `living_blocks` returns only blocks outside `## Retired`, and `retired_blocks(root, cfg)` returns `{id: (path, block)}` for blocks under it.

### Lint

- Delta `RETIRED` block: needs `Reason: \S`; no statement, scenario or `<!-- base: -->` is required. Lint refuses it when the id is living (`use REMOVED`), is added by an open change including this one, is already retired in the living spec, or appears twice in the delta.
- Delta `ADDED` block: refused when the id is retired in the living spec, as it is for a living id.
- Living `## Retired` block: needs `Reason: \S`; `lint_block` is not applied.
- Lint does not check that a retired id was used before; a typo shows in the delta diff at spec review.

### Archive

- `RETIRED` blocks are appended to `## Retired`, created at the end of `spec.md` when missing.
- `REMOVED` blocks are deleted from the requirements, as today, and each leaves an entry in `## Retired` with its title and `Reason:`.
- `ADDED` blocks are inserted before `## Retired`, not after it.
- The result lists `retired` beside `added`, `modified` and `removed`.

### Sign-off

`RETIRED` joins `DELTA_SECTIONS`, so `signoff.change_requirements` lists retired ids with op `retired` and the hash of the retired block, and `trace --all` lists the op `retired` on the change.

### Next id

`scan_ids` adds a fifth source: `git log --all --format= -p --unified=0 -G '^### REQ-' -- <specs> <changes>`, taking ids from `+### REQ-` and `-### REQ-` lines. `next-id` stays `max + 1` and never fills a gap. `renumber` refuses a target found in history. In a shallow clone (`git rev-parse --is-shallow-repository` prints `true`) the scan still runs and adds the warning `shallow clone; history before <date> not scanned`. Without git the current warning stands.

### Readers

| Command | Behaviour |
|---|---|
| `gin specs reqs` | Rows with `section: RETIRED` and a `reason` key, for living `## Retired` blocks and for `## RETIRED` blocks of open changes. Text output shows `RETIRED`. |
| gin-qa `resolve` and `_work` | A `RETIRED` row is treated like `REMOVED`: no case is planned; a case pinned to it is `obsolete` with reason `retired: <reason>`. |
| `gin specs trace <change>` | Still wants tests for `ADDED` and `MODIFIED` only. Adds a `retired` list: each test file that names a retired or removed id, with the id. It does not make trace fail. |
| `gin specs trace --all` | A retired id gets state `removed`, hash and source `null`, and a new `reason` key. |
| `gin specs export` | Each capability chapter ends with a *Retired requirements* table (id, title, reason). Retired ids stay out of the requirement TOC and traceability. |
| `gin specs explain` | A change's explanation groups `RETIRED` blocks beside the other sections; a living spec's explanation skips them. |
| Use-case and diagram lint | Citing a retired id fails with `REQ-… is retired`, not `unknown id`. |
| `gin specs hash`, matter tables | Skip retired ids through `living_blocks`. |

### Gaps

`gin specs gaps [<cap>]` lists each id that history or an archived change has used and that is not living, not added by an open change, and not retired, per capability in id order. Each row carries a hint: the archived `REMOVED` block's change and reason, or the commit that deleted the heading last (short sha, date, subject) with its title. `--format json` prints the same rows.

`gin specs gaps [<cap>] --into <change>` appends a `## RETIRED` block for each listed id to that open change's delta, creating the section when missing. A reason from an archived `REMOVED` block is copied; otherwise the block gets an empty `Reason:` line, which lint refuses until someone writes it. The command never edits `spec.md`; the entries reach it through review, sign-off and archive.

### Skills and docs

- `templates/spec-delta.md` gains `## RETIRED`; `templates/spec.md` gains an empty `## Retired` at the end.
- `sdd` skill: when a review drops a requirement that is not living, move its block to `## RETIRED` with a `Reason:` instead of deleting it; a living one uses `REMOVED`; never renumber to close a gap; run `gin specs gaps` to explain existing gaps.
- `qa-track` skill: skip `section: RETIRED` as it skips `REMOVED`.
- `docs/guides/sdd.md` and `sdd.vi.md`: the format, lint, archive, history scan and `gaps`. `docs/reference/cli.md`: `specs lint`, `next-id`, `reqs`, `trace`, `trace --all` and `gaps`.

## User Stories

### US-1: Retire a dropped requirement
As a business analyst, I want to retire a requirement ID that the spec review drops, so that its number stays explained and is never reused.

Acceptance criteria:
- A delta with `## RETIRED` and `### REQ-AUTH-002: Lock out` plus `Reason: …` passes `gin specs lint`.
- The same block without `Reason:` fails lint with a message naming `REQ-AUTH-002`.
- A `RETIRED` block for a living id fails lint and names `REMOVED`.
- `ADDED` of an id that is retired in the living spec fails lint.
- After `gin specs archive`, `spec.md` has the entry under `## Retired`, and the archive result lists it under `retired`.
- After archive of a `REMOVED` block, `spec.md` no longer has the requirement and has a `## Retired` entry with its title and reason.
- An `ADDED` block archived into a spec that has `## Retired` lands before that section.

### US-2: Never hand out a used number
As a business analyst, I want `gin specs next-id` to skip every number ever used, so that no test, case, bead or commit points at the wrong requirement.

Acceptance criteria:
- The repro of issue #39 (add `REQ-AUTH-002`, commit, delete it, commit) makes `gin specs next-id auth` print `REQ-AUTH-003`.
- An id that exists only in a `## RETIRED` or `## Retired` section is counted as taken.
- In a shallow clone `next-id` prints the shallow-clone warning and still returns an id.
- `gin specs renumber` refuses a target id that only history holds.

### US-3: Readers skip retired IDs
As a tester, I want gin-qa and trace to ignore retired IDs and point at what still cites them, so that no case is planned for a requirement that is gone.

Acceptance criteria:
- `gin specs reqs --format json` shows the retired id with `section: RETIRED` and its reason, and no `LIVING` row for it.
- gin-qa plans no case for a retired id, and reports a case pinned to it as `obsolete` with reason `retired: <reason>`.
- `gin specs trace <change>` lists a test file that names a retired id under `retired` and keeps its exit status.
- `gin specs trace --all` shows a retired id with state `removed` and its `reason`.
- A use case citing a retired id fails lint with `REQ-… is retired`.

### US-4: See why a number is missing
As a reader of the exported spec, I want the export to list retired IDs with their reasons, so that a gap in the numbering explains itself.

Acceptance criteria:
- `gin specs export` renders a *Retired requirements* table with id, title and reason at the end of the capability chapter.
- The retired id does not appear in the requirement TOC or the traceability table.
- `gin specs explain <change>` shows the change's `RETIRED` blocks as their own group.

### US-5: Backfill existing gaps
As a business analyst, I want gin to find the IDs that were dropped before this feature and draft their retired entries, so that I only write the reasons gin cannot know.

Acceptance criteria:
- `gin specs gaps auth` lists an id deleted from a delta in history with the deleting commit and its title, and an id removed by an archived change with that change and its reason.
- Ids that are living, retired or added by an open change are not listed.
- `gin specs gaps auth --into <change>` appends `## RETIRED` blocks to that change's delta; the archived reason is copied, and the other block has an empty `Reason:` that lint refuses.
- `spec.md` is unchanged by `gaps --into`.

## Errors and compatibility

- `spec.md` and deltas without the new sections parse and lint as today.
- A `## Retired` block with a malformed heading is reported as malformed, as any block is today.
- `gaps --into` on a missing or archived change exits 1 with the change name.
- `trace --all` keeps its state values; the `reason` key and the `retired` op are additions, and gin-console's `op` field is a plain string.
- History scan failures (no git, git log error) add a warning and fall back to the current sources; `next-id` never fails because of them.
- gin-qa and `gin specs` ship in this repository and install together, so the `RETIRED` section needs no version check in gin-qa.

## Testing

pytest, in the existing files:

- `tests/workflow_core/test_specs.py`: parse and lint of `RETIRED` (each refusal above), living `## Retired` lint, `living_blocks` and `retired_blocks`, `next-id` over history with the issue repro, retired-only ids, shallow clone warning, `renumber` against history.
- `tests/workflow_core/test_specs_archive_trace.py`: archive of `RETIRED` and `REMOVED` into `## Retired`, `ADDED` placement, the `retired` result list, trace's `retired` list.
- `test_specs_reqs.py`, `test_specs_trace_all.py`, `test_specs_export.py`, `test_specs_explain.py`, `test_signoff.py`: the new section, key, op and table.
- `tests/gin_qa`: no planned case and the `obsolete` reason for a retired id.
- A new test file for `gin specs gaps`: listing, hints, exclusions, `--into`.

Risk: a reader that calls `parse_blocks` on `spec.md` directly bypasses the `living_blocks` filter. The callers today are `specs.py:363`, `:418`, `:702`, `specs_reqs.py:67`, `specs_explain.py:193`, `specs_export.py:346`, `specs_matter.py:30` and `specs_archive.py:31`; the plan gives each one a decision and a test.

## Open Technical Questions

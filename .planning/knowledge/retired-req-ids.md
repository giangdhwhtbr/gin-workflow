# Retired requirement IDs and `gin specs gaps`

**Context**
Epic `gin-workflow-retired-req-ids` (2026-11-27, GitHub issue #39). An id dropped from an open delta before archive vanished from every tree, so `gin specs next-id` handed it out again, and archive deleted a `REMOVED` block from `spec.md` without a trace, so readers saw unexplained gaps and asked to renumber.

**Decision/Solution**
- A retired entry keeps the `### REQ-<CAP>-<NNN>: <title>` heading plus `Reason:`, under `## RETIRED` in a delta and `## Retired` (last section) in a living `spec.md`. Keeping the heading form means `_HEADING_LINE`, `ids_at_ref`, `scan_ids` and `git grep '^### REQ-'` count the id with no change.
- `specs.is_retired` is true only for a living block under exactly `## Retired`; delta code checks `block.section == "RETIRED"`. `lint_living` reports a `## RETIRED` heading in a `spec.md`: before that fix, archive appended new ADDED blocks under a hand-written `## RETIRED`, which silently retired them.
- `living_blocks` skips retired blocks and `retired_blocks` returns them; readers that call `parse_blocks` on `spec.md` directly (`specs_reqs`, `specs_export`, `specs_explain`) filter with `is_retired` themselves.
- Archive writes `RETIRED` blocks and each `REMOVED` block (without its base line) under `## Retired` via `specs.append_to_section`, and inserts ADDED blocks before that section.
- `scan_ids` adds `history_ids`: one `git log --all -p --unified=0 -G '^### REQ-'` over the specs and changes folders. A shallow clone warns; no commits add no warning; a git error warns and falls back.
- `gin specs gaps` = (ids in the tree including archive, plus history) minus ids present now. Present must cover every ref `git log --all` sees: the tree, every worktree, `refs/heads` and `refs/remotes`, with archived changes left out. Missing `refs/heads` made an unpushed branch's ADDED id look like a gap, and `--into` would have retired it.
- `trace --all` keeps state `removed` for retired ids (gin-console's `State` literal) and adds `reason`; `gin specs reqs` rows gain `section: RETIRED` and `reason`; gin-qa treats `RETIRED` like `REMOVED` (`retired: <reason>` obsolete cases, `cases new --req` refused).

**Consequences**
- A new delta section changes every consumer of `specs.DELTA_SECTIONS`: `signoff` (`_ROW`, op `retired`), `specs_matter.revisions` (a new key per row), the export revision table, `specs_explain` grouping, and the `delta_blocks` "outside ## ..." message.
- `skills/sdd/SKILL.md` had 11 characters free; adding the retire rule needed compressing other sentences and moving the MODIFIED/REMOVED/RETIRED block rules into the `templates/spec-delta.md` comment (see `skill-authoring-limits.md`).
- `gaps` runs one `git log -p -G` per gap id; a repository with hundreds of gaps may want a single pass.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{specs,specs_archive,signoff,specs_reqs,specs_trace,specs_trace_all,specs_export,specs_explain,specs_gaps,specs_cli}.py`; `plugins/gin-qa/src/scripts/gin_qa/{reqs,cli}.py`
- Tests: `tests/workflow_core/{test_specs,test_specs_archive_trace,test_specs_gaps,test_specs_reqs,test_specs_trace_all,test_specs_export,test_specs_explain,test_signoff,test_specs_matter}.py`, `tests/gin_qa/{test_cases_cli,test_cases_new}.py`
- `docs/reference/cli.md` (specs rows), `docs/guides/sdd.md`
- `.planning/specs/2026-11-27-retired-req-ids-design.md`, `.planning/plans/2026-11-27-retired-req-ids.md`
- Beads: `gin-workflow-retired-req-ids`, `.1` to `.5`

**Scope**
SDD layout: requirement ids, spec deltas, archive, `next-id`, `gaps`, and readers of living specs, including gin-qa.

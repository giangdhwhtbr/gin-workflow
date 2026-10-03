---
name: migrate-specs
description: Move a legacy .planning specs/plans layout into the SDD docs/ layout, then optionally seed living specs.
---

# Migrate Specs

Load only when the user invokes it.

1. Run `gin-workflow specs migrate --dry-run`. Show the moves, skipped files, and refusals.
2. Refusals: uncommitted changes always stop; ask the user to commit first. An approved-but-unshipped workflow or an open worktree stops unless the user explicitly accepts `--force`.
3. On approval: `git switch -c chore/migrate-specs`, run `gin-workflow specs migrate [--force]`, then commit (`chore(specs): migrate .planning to SDD layout`). Never commit on `main`/`master`.
4. Ask whether to seed living specs now. If yes:
   - If `artifacts.codebase` is empty, run the `tech-doc` skill first.
   - Propose a capability list from `docs/codebase` and `docs/changes/archive/*/design.md`; the user edits it.
   - For each capability, one at a time: draft `docs/specs/<cap>/spec.md` from `gin-workflow specs template spec.md`, describing current behavior only, with IDs `REQ-<CAP>-001…` and at least one GIVEN/WHEN/THEN scenario each; add it to `docs/specs/README.md`; run `gin-workflow specs lint`; show the draft and wait for approval; commit.
   - Stopping midway keeps the committed capabilities.
5. Report the branch, commits, and remaining capabilities. Merging needs the user's approval.

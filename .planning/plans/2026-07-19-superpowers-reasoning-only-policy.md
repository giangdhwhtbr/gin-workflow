# Plan: Superpowers Skills as Reasoning-Only Guidance

## Objective
Gin Workflow skills that extend a `superpowers:*` base skill use that base skill only for its reasoning/process guidance. Any artifact-location or git-commit default the base skill carries is always superseded by gin-workflow conventions (`.planning/...`, explicit-authorization-before-commit). A standing, discoverable rule captures this so future overlay skills don't reintroduce the gap, and the one concrete instance already found (`discovering-work` writing specs to `docs/superpowers/specs/`) is fixed and its stray output migrated.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `brainstorm`: `high_reasoning`
  - `design`: `high_reasoning`
  - `plan`: `standard_impl`
  - `implement`: `standard_impl`
  - `verify`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: Use `high_reasoning` for planning only when execution boundaries, dependency sequencing, or major tradeoffs are still unresolved. Not needed here — this plan's content is fully specified below.

## Requirement Analysis
- **Problem statement**: `discovering-work` (the `/discuss` skill) extends `superpowers:brainstorming` but never overrides brainstorming's default artifact behavior — "write design doc to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` and commit." As a result, three design docs already landed in `docs/superpowers/specs/` instead of the project's `.planning/` convention, and one of them was committed automatically, bypassing the repo's explicit-authorization-before-commit rule. No written rule tells overlay authors that superpowers skills' artifact/commit defaults must always be redirected, so the gap can recur in any future overlay.
- **Success criteria**:
  - A canonical policy doc states that `superpowers:*` skills are used for reasoning/process guidance only; their artifact-location and git-commit defaults are always superseded by gin-workflow conventions.
  - `AGENTS.md` points to that doc, matching its existing pointer-layer pattern.
  - `discovering-work`'s overlay explicitly redirects brainstorming's design-doc output to `.planning/specs/` and removes the unconditional auto-commit, matching the pattern already used by `writing-plans` and `using-git-worktrees`.
  - The 3 existing misplaced files move to `.planning/specs/` with history preserved; `docs/superpowers/` no longer exists.
- **Constraints**:
  - Only hand-edit `plugins/gin-workflow/src/`. `plugins/gin-workflow/dist/*` and `.codex/skills/*` are build outputs of `install.sh` — confirmed identical to `dist/codex/*` — and must not be hand-edited or manually kept in sync as part of this plan.
  - Do not commit or push without explicit user authorization (`AGENTS.md`), including for this plan's own execution.
- **Non-goals**:
  - No changes to `writing-plans`, `using-git-worktrees`, `executing-plans`, or `finishing-a-development-branch` — they already redirect their base skill's artifact paths correctly.
  - No changes to `requesting-code-review` or `subagent-driven-development` — their `docs/superpowers/plans/...` mentions are illustrative example text, not real write targets exercised in this repo.
  - No rebuild/reinstall of `dist/`/`.codex` as part of this plan; that is a separate, user-triggered `install.sh` run outside this scope.
  - No edits to the vendored `superpowers` plugin itself (outside this repo, reinstalled on updates).

## Approach Options
### Option 1: Point-fix only
- Summary: Patch only `discovering-work`'s overlay to redirect the spec path and drop auto-commit. No standing rule written anywhere.
- Pros: Smallest possible change.
- Cons: The principle stays implicit; the next overlay added for a new superpowers skill can reintroduce the exact same gap with no documented rule to catch it in review.

### Option 2: Standing rule + point fix
- Summary: Add a short canonical doc (`docs/superpowers-integration-policy.md`) stating the reasoning-only principle and the artifact/commit supersession rule, pointed to from `AGENTS.md`. Then fix `discovering-work`'s overlay to comply, and migrate the 3 stray files already misplaced under the old default.
- Pros: Fixes the reported bug, gives future overlay authors (and reviewers) a durable rule to check against, and cleans up the artifacts the bug already produced.
- Cons: One more file to maintain — mitigated by keeping it short and referencing it rather than duplicating it per-skill.

### Option 3: Bake the rule into `using-superpowers` or global `CLAUDE.md`
- Summary: Add the rule to the superpowers meta-skill or the user's global `~/.claude/CLAUDE.md`.
- Pros: Would apply everywhere superpowers is used.
- Cons: `using-superpowers` is vendored superpowers content, reinstalled/overwritten on plugin updates — not safe to hand-edit. Global `CLAUDE.md` applies to all projects, not just this repo's `.planning/` convention — wrong scope for a repo-specific path rule.

### Recommended Approach
- Selected option: Option 2.
- Reasoning: Matches the existing repo pattern (AGENTS.md as a pointer layer to canonical docs under `docs/`), fixes the concrete reported bug, and is durable against future overlay additions without touching vendored/out-of-repo files.

## Scope
- In scope:
  - `docs/superpowers-integration-policy.md` (new)
  - `AGENTS.md` (add one pointer bullet)
  - `plugins/gin-workflow/src/skills/discovering-work/SKILL.md` (overlay fix)
  - `.planning/specs/` (new directory, populated by migration)
  - `docs/superpowers/` (removed after migration)
- Out of scope: any other overlay skill file, `dist/`, `.codex/`, vendored superpowers plugin files, rebuilding/reinstalling the plugin.

## Tasks

### Track 1: Write the standing policy doc and wire it into AGENTS.md
- **Dependencies**: none
- **Files**:
  - Create `docs/superpowers-integration-policy.md`
  - Modify `AGENTS.md` (pointer list under "This repository separates responsibilities intentionally")
- **Model class**: `standard_impl`
- **Acceptance criteria**:
  - `docs/superpowers-integration-policy.md` exists and states, at minimum: (a) `superpowers:*` skills invoked directly or via a gin-workflow overlay are used for reasoning/process guidance only; (b) any artifact-location, file-naming, or git-commit default in the base skill is superseded by gin-workflow conventions — durable artifacts live under `.planning/...`, never `docs/superpowers/...`; (c) git commit/push from within any skill remains subject to the repo's explicit-authorization rule regardless of what the base skill instructs; (d) overlay skill authors must state the concrete redirected path/behavior explicitly in their own "Gin Workflow Overlay" section rather than relying on this doc alone (defense in depth, matching existing overlays).
  - `AGENTS.md`'s existing bullet list gains exactly one new line: `` `docs/superpowers-integration-policy.md`: rule for using superpowers:* skills as reasoning guidance only. `` No other line in `AGENTS.md` changes.
- **Estimated complexity**: low

### Track 2: Fix `discovering-work`'s overlay
- **Dependencies**: Track 1
- **Files**: Modify `plugins/gin-workflow/src/skills/discovering-work/SKILL.md`
- **Model class**: `standard_impl`
- **Acceptance criteria**:
  - The "Gin Workflow Overlay" section gains explicit rules (numbered, consistent with the existing list style) stating: if a design/spec doc is produced per brainstorming's checklist, save it to `.planning/specs/YYYY-MM-DD-<topic>-design.md`, not `docs/superpowers/specs/...`; do not auto-commit it — committing follows the repo's normal explicit-authorization rule, not brainstorming's default.
  - The overlay references `docs/superpowers-integration-policy.md` as the source of the general rule (link or plain path mention), avoiding restating the full rationale inline.
  - No other section of the file (Execution Rules, Exit Standard) is altered beyond what's needed for consistency with the new rule.
- **Estimated complexity**: low

### Track 3: Migrate misplaced spec files
- **Dependencies**: Track 2
- **Files**:
  - `git mv docs/superpowers/specs/2026-07-11-beads-status-recommendations-design.md .planning/specs/2026-07-11-beads-status-recommendations-design.md`
  - `git mv docs/superpowers/specs/2026-07-18-make-claude-plugin-installable-design.md .planning/specs/2026-07-18-make-claude-plugin-installable-design.md`
  - `git mv docs/superpowers/specs/2026-07-18-cross-agent-code-review-design.md .planning/specs/2026-07-18-cross-agent-code-review-design.md`
  - Remove the now-empty `docs/superpowers/` directory tree.
- **Model class**: `cheap_simple`
- **Acceptance criteria**:
  - `.planning/specs/` contains all 3 files, byte-identical content, unchanged filenames.
  - `docs/superpowers/` no longer exists anywhere in the working tree.
  - `git status` shows these as renames, not delete+add pairs (i.e., use `git mv`, not manual copy+delete).
- **Estimated complexity**: low

## Integration
- **Branch**: none required — docs-only change, no worktree needed given the small, non-parallel blast radius.
- **Merge strategy**: sequential (Track 1 → Track 2 → Track 3, per stated dependencies).

## Validation
- [ ] `docs/superpowers-integration-policy.md` exists and is referenced from `AGENTS.md`
- [ ] `discovering-work/SKILL.md` overlay redirects the spec path to `.planning/specs/` and states commits require explicit authorization
- [ ] All 3 previously misplaced files exist under `.planning/specs/`; `docs/superpowers/` is gone
- [ ] `grep -rn "docs/superpowers/specs" plugins/gin-workflow/src docs AGENTS.md` returns no hits
- [ ] `git status` / `git log --follow` on the migrated files shows preserved rename history

## Notes
- Model guidance is planning metadata, not Beads state.
- If omitted, agents should assume `standard_impl`.
- This plan intentionally does not touch `dist/` or `.codex/` — those are regenerated by `install.sh` from `plugins/gin-workflow/src/` and are out of scope here.

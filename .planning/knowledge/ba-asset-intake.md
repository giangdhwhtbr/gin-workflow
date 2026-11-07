# BA asset intake: `gin specs assets add|confirm`, freeze checked by lint against the base

**Context**
Epic `gin-workflow-tp83` (2026-11-07). Dated asset folders were built by hand by the gin-ba skills and SDD discuss. No code read `Kind:`, `Previous:`, or `Confirmed:`, so a confirmed folder was frozen only in skill text, and a misnamed capability folder was skipped silently by lint.

**Decision/Solution**
- `workflow_core/specs_assets.py` holds `add`, `confirm`, and `lint`, behind the nested subcommand `gin specs assets add|confirm` (SDD layout only). `add` validates the capability (close-match suggestion, `--new-capability` to create), copies files from anywhere on disk, writes `description.md` when missing, and does every write in one `atomic_write_many` call. Originals stay in place.
- The freeze has two checks. `assets add` refuses a folder whose `description.md` has a confirmed date. `specs lint` compares the working tree with the base (`--against`, else `default_base`) and reports any modified, deleted, added, or untracked path under a folder confirmed on that base.
- Both lint checks (`Confirmed:` value, frozen folders) run in the `specs lint` command, with and without `--change`. `specs archive` calls `lint_change` and does not run them.
- Without a base, lint warns on stderr and skips the frozen check, so a shallow CI clone does not fail on it.

**Consequences**
- A folder confirmed only on the current branch is not covered by lint until it reaches the base; `assets add` still refuses it.
- `description.md` is a reserved name: `assets add` refuses a source with that name, because it would overwrite the folder description.
- The git calls in `frozen_findings` pass `-c core.quotepath=off`; without it, non-ASCII paths come back quoted and octal-escaped, and a non-ASCII spec directory fails the path match.
- The scoped commit for BAs and testers is a separate epic, `gin-workflow-yasu`.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/specs_assets.py`, `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py`, `tests/workflow_core/test_specs_assets.py`
- `plugins/gin-ba/src/skills/capture/SKILL.md`, `plugins/gin-ba/src/skills/mockup/SKILL.md`, `plugins/gin-workflow/src/skills/sdd/SKILL.md`
- `.planning/specs/2026-11-07-ba-asset-intake-design.md`, `.planning/plans/2026-11-07-ba-asset-intake.md`
- Beads: `gin-workflow-tp83`, `gin-workflow-tp83.1`, `gin-workflow-tp83.2`, `gin-workflow-tp83.3`

**Scope**
SDD layout only: the `specs` CLI and lint, the capture, mockup, and sdd skills, the `iteration.md` template, and the BA and SDD guides.

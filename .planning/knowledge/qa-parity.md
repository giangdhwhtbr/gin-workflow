# Legacy parity: the Legacy case field, assets list, and one owner

**Context**
Epic `gin-workflow-qa-parity` (2026-11-12, spec `.planning/specs/2026-11-12-qa-parity-design.md`). The brownfield starter gave parity tests to two people and no build; cases could not point at the legacy behaviour they check; `/gin-qa:cases` ignored the BA's confirmed legacy captures.

**Decision/Solution**
- `Legacy:` is a known gin-qa case field (`cases.LEGACY_FIELD` in `KNOWN_FIELDS`): it does not change `hash8` and is exported as `legacy` (a list). References are comma-separated relative paths, optionally `#<screen>`; `cases check` refuses an empty list, an absolute path, a Windows drive, or a `..` part before the `#`.
- `gin specs assets list` is the one reader of asset-folder state for other tools; gin-qa calls it by command and never imports gin-workflow.
- Recorded legacy payloads live in the QA home under `legacy/<capability>/`, not in asset folders (`assets add --legacy` stays images only).
- The starter names the tester as the only parity owner (a team convention): parity tests are `api` cases with `Legacy:`, run with `/gin-qa:tests --type api` against the pull-request build and payloads recorded once from legacy staging.

**Consequences**
- A case that already used `Legacy:` as a free field changed its `hash8` once; its test shows `stale` until re-pinned.
- Open review suggestions: `..\x` (backslash) and a `#screen`-only reference pass `cases check`; `### ` inside a fenced block under `## As-is behaviour` counts as a screen; a non-UTF-8 `description.md` error does not name the file.
- A `docs/*.md` change with a `.vi.md` mirror needs both in the track's Files; review of `.3` caught `roles.vi.md`.

**References**
- `plugins/gin-qa/src/scripts/gin_qa/cases.py` (`legacy_refs`, `_parse_block`, `as_dict`), `plugins/gin-workflow/src/scripts/workflow_core/specs_assets.py` (`listing`, `_screens`), `specs_cli.py`, `plugins/gin-qa/src/skills/cases/SKILL.md`, `docs/starters/brownfield.md`, `docs/roles.md`
- Beads: `gin-workflow-qa-parity.1` to `.3`
- Related: [spec-asset-iterations](spec-asset-iterations.md), [gin-qa-case-files](gin-qa-case-files.md), [qa-evidence](qa-evidence.md)

**Scope**
gin-qa case format and cases skill, gin-workflow asset listing, brownfield starter.

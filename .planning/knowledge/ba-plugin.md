# BA add-on `gin-ba`: skills only, confirmed inputs cited with `Source:`

**Context**
Epic `gin-workflow-ba-plugin` (2026-11-06). Since `gin-workflow-spec-iterations`, a capability's inputs live in dated folders `<specs>/<cap>/assets/<YYYY-MM-DD>/` with a `description.md`, but nothing produced a mockup or described a legacy screen, and SDD discuss did not read those inputs or say which requirement came from which input.

**Decision/Solution**
- A fourth plugin, `gin-ba`, with two skills and no CLI or launcher: `/gin-ba:capture` writes a `Kind: legacy` `description.md` from screenshots under `legacy/`; `/gin-ba:mockup` writes one self-contained `mockup/index.html` (inline CSS and JS, no network, one `<section id>` per screen routed by URL hash, an unknown hash falls back to the first screen). A BA CLI (`specs assets new`), a `gin-ba:change` skill, Figma import, and lints were left out: a dated folder is a `mkdir` plus `gin specs template iteration.md`.
- `iteration.md` carries `Confirmed: no` after `Previous:`; only the BA's explicit answer sets `Confirmed: <date>`, and a confirmed folder is frozen (the skills stop and ask for a new date). The skills never commit.
- SDD discuss reads `description.md` and `mockup/index.html` of each dated folder, cites only confirmed folders, turns `## Open questions` into questions or assumptions, and writes a `Source:` line per requirement with backticked paths (`#<screen-id>` for a screen). `specs archive` and `specs export` carry the line through unchanged.
- Mockup look, in order: the repository's existing UI, then `frontend-design` when the harness provides it, then `references/mockup-html.md`; a missing `frontend-design` is not an error.
- Installer: `--plugin gin-ba` (and `all`) installs the skills only and warns like gin-qa when `gin` is missing (`warn_if_gin_missing` / `Write-GinMissingWarning`); the add-on refresh loop stays limited to add-ons with a launcher.

**Consequences**
- The build always creates empty `scripts/`, `agents/`, and `commands/` in each dist, so tests that prove "no launcher" assert the absence of `scripts/gin-ba`, not of `scripts/`.
- The PowerShell installer changes were reviewed by reading only (no pwsh on the dev host); the Windows CI job is their first run.
- The end-to-end BA walkthrough (capture, mockup, confirm, discuss with `Source:` lines) needs a real BA in an interactive session and was not run in the epic.
- Uninstalling any add-on still unregisters the PATH entry while `gin` stays installed; this predates the epic.
- Since `gin-workflow-tp83`, the skills call `gin specs assets add` and `confirm`, and lint enforces the freeze against the base, replacing the "no BA CLI, no lints" decision above; see [ba-asset-intake](ba-asset-intake.md).

**References**
- `plugins/gin-ba/src/skills/mockup/`, `plugins/gin-ba/src/skills/capture/`, `plugins/gin-workflow/src/skills/sdd/SKILL.md`, `plugins/gin-workflow/src/templates/iteration.md`, `install.sh`, `install.ps1`, `docs/guides/ba.md`
- `.planning/specs/2026-11-06-ba-plugin-design.md`, `.planning/plans/2026-11-06-ba-plugin.md`
- Beads: `gin-workflow-ba-plugin`, `.1` to `.4`
- Related: [spec-asset-iterations](spec-asset-iterations.md), [ba-capability-placement](ba-capability-placement.md), [srs-export](srs-export.md)

**Scope**
The gin-ba plugin, the iteration template, SDD discuss, the installers, and the BA guide.

# Upkeep: weekly upstream check, leaving gin, one release procedure

**Context**
Epic `gin-workflow-upkeep` (2026-11-27, spec `.planning/specs/2026-11-27-upkeep-design.md`). gin-workflow has one maintainer and two upstreams that change weekly: Claude Code 2.1.330 reserved the `ship` command name and Beads 1.4.0 migrates its database one way, and both were found by chance. The release steps disagreed across `docs/contributing.md`, [release-versioning](release-versioning.md), and the maintainer's notes. A project that drops gin had every commit and push blocked by the gin hooks.

**Decision/Solution**
- `scripts/upstream_watch.py` is maintainer tooling in the repository's `scripts/`, not part of the plugin, standard library only. It reads the raw Claude Code `CHANGELOG.md` and the Beads GitHub releases (prereleases included and marked), matches each new line against `scripts/upstream_surfaces.json`, and files one `upstream` bead per run through `gin task create`, plus one per source or state file it cannot read. Exit 0, 1 (a failure bead was filed), 2 (a bead could not be filed).
- A Claude Code cloud scheduled task was rejected: it runs on a fresh clone and cannot reach the Beads database on the maintainer's machine. A local cron line runs the script on Mondays at 08:17 from the main checkout, logging to `~/.local/state/gin/upstream-watch.log`.
- The state lives in `.agent-workflow/runtime/upstream-watch.json` of the main checkout: the last Claude Code version and the last Beads `published_at`. "First run" is decided per source: a source without a key records its baseline and reports nothing; a source that fails writes no key. An invalid state file files a bead and is replaced by a new baseline. Baseline recorded on 2026-11-27: Claude Code 2.1.332, Beads 2026-11-20.
- `gin hooks uninstall [--all-repos]` removes only the `pre-commit` and `pre-push` hooks carrying the `install` marker, reports a chained hook (exit 1) and leaves a foreign one, and never touches `core.sshCommand` or the team `commit-msg` hook, which needs no `gin`.
- The Releasing section of `docs/contributing.md` is the one release procedure, including the suite with `bd` off `PATH`, the installer smoke test, the rerun of a failed Pages upload, and reinstalling after the push. `docs/guides/leaving-gin.md` (and `.vi.md`) lists what gin leaves in a project and how to remove it.
- The `github-pages` environment allows the `v*` tag policy since 2026-11-27, so the `pages` job of a tag run is no longer rejected.

**Consequences**
- Keyword matching is noisy: a digest bead can be closed when nothing needs work, and `scripts/upstream_surfaces.json` is the list to tune. A quiet week means no matching line, not that nothing changed.
- `workflow_core` starts other tools through the same variable names it uses for `bd` (`executable` in `specs_trace_all.py` and `hosts/gitea.py`), so the guard test of the surface list keeps an exclusion set and asserts the subcommands it must find. A call whose literal subcommand is on another line than the call name is not seen.
- Track 3 of the plan first dropped the installer smoke test from the release; release.yml does not run it, and `test.yml` runs it only by hand, so the procedure names it explicitly.
- The plan's script code had three defects a review caught (a partial baseline flooding the next run, a crash on a corrupt state file, a narrow guard regex). Code given in a plan still needs its edge cases reviewed.
- `gin goal` asked for `implementation_complete` while telling the agent not to start the human-gate track, so the `/goal` Stop hook could never clear (bead `gin-workflow-y0bf`).

**References**
- `scripts/upstream_watch.py`, `scripts/upstream_surfaces.json`, `tests/test_upstream_watch.py`
- `plugins/gin-workflow/src/scripts/workflow_core/hooks.py` (`uninstall`), `tests/workflow_core/test_hooks.py`
- Docs: `docs/contributing.md` (Releasing), `docs/guides/leaving-gin.md`, `docs/guides/leaving-gin.vi.md`, `docs/reference/cli.md` (`gin hooks`)
- Spec and plan: `.planning/specs/2026-11-27-upkeep-design.md`, `.planning/plans/2026-11-27-upkeep.md`
- Beads: `gin-workflow-upkeep`, `.1` to `.4`; `gin-workflow-6ujv` (marketplace install), `gin-workflow-y0bf` (`gin goal`)

**Scope**
Maintainer upkeep: the upstream check, the release procedure, the GitHub Pages environment, and leaving gin.

# One release version, the .ginrc pin, and the changelog

**Context**
Epic `gin-workflow-b7ip` (2026-11-15), the preparation of release 3.1.0. Before it, each plugin had its own version (gin 3.0.0, gin-qa 0.11.0, gin-orchestrator 0.2.0, gin-ba 0.1.0), the CLIs printed other numbers (`gin 3.0`), the installers pinned three launcher versions, a release bumped about twenty places by hand, nothing told a member that their gin was older than the project needed, and there was no changelog.

**Decision/Solution**
- One version for the whole set. The reference is `"version"` in `plugins/gin-workflow/plugin.meta.json`; the nine manifests, `CLI_VERSION`, gin-qa `VERSION`, and the four installer launcher pins equal it (twelve manifests, `ORCHESTRATOR_VERSION`, and six pins before gin 3.3.0 removed gin-orchestrator). `tests/test_version_pins.py` names a location that differs and a manifest missing from the list. `python3 scripts/bump_version.py X.Y.Z` writes them all. Other tests and the smoke scripts read the reference instead of a literal.
- Not merged into it: the config schema version (`schema_version`, `workflow_version`, `setup_cli_version`, `2.11` since gin 3.3.0). It versions a format. The gin-orchestrator contract version (`CONTRACT_VERSION`, `REQUIRES_GIN_WORKFLOW`) went with that extension in 3.3.0.
- `.ginrc` at the project root holds one line, the minimum version `X.Y.Z` (`workflow_core/version_pin.py`). Same major version and installed at least the pin is compatible; installed lower is refused; an installed newer major version is refused except for `gin setup`. No file means no check.
- The check runs once in `workflow_core/cli.py` `main()` before the dispatch, for every command except `paths` and `version` (and `--version`). The start directory is `--repository` in any abbreviation argparse accepts, else the working directory. The file is found by walking up, but not in the home directory or above when the start is inside it.
- `gin setup init` writes `.ginrc` with the installed version; `gin setup update` proposes raising it and writes it with `--approve`, also when no migration is due; `gin setup doctor` reports a missing pin, a pin of an older major version, and a gin-qa or gin-orchestrator whose version differs.
- `gin version` reports the state; `gin version --hook` prints nothing when compatible, one line otherwise, always exits 0, loads no YAML, and starts no subprocess. The Claude Code hooks file that `install.sh` and `install.ps1` generate has a `SessionStart` entry that runs it.
- `docs/changelog.md` is the one home of release changes; `python3 scripts/release_notes.py X.Y.Z` prints one section and `release.yml` publishes it as the GitHub release notes, failing without one. `docs/guides/upgrading.md` (with a Vietnamese twin) is the upgrade guide.
- The release steps live in the Releasing section of docs/contributing.md; this record keeps the decisions behind them.

**Consequences**
- Upgrade order matters. gin 3.0 rejects a configuration at schema 2.10 and ignores `.ginrc`, so every member updates gin before the lead runs `gin setup update --approve`. Proven on a v3.0.0 project.
- The pin is the lead's installed version, and each later `gin setup update --approve` raises it to the version installed then.
- The refusal also stops `gin hooks run`, so git commit and push hooks fail in an incompatible project.
- A `.ginrc` that is not UTF-8 (PowerShell 5.1 writes UTF-16) is `invalid`, never a crash; a UTF-8 byte order mark is accepted.
- `cli.py` imports its heavy modules lazily, because `task_markdown.py` imports `yaml` at import time through `setup_service`.
- `tests/gin_qa/test_packaging.py::test_core_never_refers_to_gin_qa` has a second allowed file, `workflow_core/version_pin.py`: the one core module that names the QA extension, to probe its version.
- `plugins/gin-workflow/src/hooks/hooks.json` has no session-start hook, because marketplace installs of other harnesses load it. A Claude Code plugin installed only from the marketplace, and every other harness, shows the refusal at the first `gin` command.
- The launcher directory is the full version (`~/.local/lib/gin/3.1.0/`); older directories stay on disk and the link is repointed.
- `./install.sh --plugin <name>` installs only that add-on and does not update gin; the default run updates gin and refreshes installed add-ons.
- The docs test that bans the words of the removed outbound notifications feature also applies to the changelog; its Removed entry names the `notify` command and the `notifications` key without matching the pattern.
- Not verified on the build machine: `install.ps1` and the PowerShell smoke test (no PowerShell), `mkdocs build --strict` and the release workflow (they run on GitHub).
- Open minors: `scripts/release_notes.py` tracks code fences without their type; the bash smoke test checks the session-start entry for the global install only.
- Not built: session-start hooks for Codex, Copilot, Antigravity, and OpenCode; detecting a plugin copy that differs from the CLI; changelog sections before 3.1.0; a Vietnamese changelog page.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{version_pin,cli,setup_service}.py`; `scripts/{bump_version,release_notes}.py`; `install.sh`, `install.ps1`; `.github/workflows/release.yml`
- Tests: `tests/test_version_pins.py`, `tests/test_bump_version.py`, `tests/test_release_notes.py`, `tests/workflow_core/{test_version_pin,test_setup_cli}.py`, `tests/workflow_core/test_harness_packaging.py` (under `tests/gin_orchestrator/` before gin 3.3.0), `tests/install_smoke_test.sh`
- Docs: `docs/changelog.md`, `docs/guides/upgrading.md` (and `.vi.md`), `docs/reference/{cli,config,troubleshooting}.md`, `docs/guides/team.md`, `docs/contributing.md` ("Releasing")
- `.planning/specs/2026-11-15-release-version-pin-design.md`, `.planning/plans/2026-11-15-release-version-pin.md`
- Beads: `gin-workflow-b7ip`, `.1` to `.7`
- Related: [docs-site-mkdocs](docs-site-mkdocs.md), [remove-telegram](remove-telegram.md), [windows-cmd-shims-and-hook-port](windows-cmd-shims-and-hook-port.md)

**Scope**
Versions of the plugins and CLIs, the project version pin and its checks, the changelog, and the release steps.

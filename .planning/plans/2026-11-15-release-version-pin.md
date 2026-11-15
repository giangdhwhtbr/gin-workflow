# Plan: One version for the whole set, a project version pin, and a changelog

Spec: .planning/specs/2026-11-15-release-version-pin-design.md
Epic: gin-workflow-b7ip

## Objective

gin, gin-qa, gin-orchestrator, and gin-ba carry one version, 3.1.0, held equal by one test and written by `scripts/bump_version.py`. A project pins its minimum version in `.ginrc`; an incompatible `gin` refuses to run, `gin version` reports the state, and the Claude Code hooks file the installers generate tells the agent at session start. `docs/changelog.md` and `docs/guides/upgrading.md` exist, the GitHub release takes its notes from the changelog, and the repository is ready for the tag `v3.1.0`.

**Goal** (spec): The four plugins and three CLIs of this repository carry one release version. A project records the minimum version it needs in `.ginrc`, an older `gin` refuses to run there, and in Claude Code a session-start hook tells the agent at once. The documentation site has a changelog page, the GitHub release takes its notes from it, and version 3.1.0 ships.

**Architecture**:
- Version unity: the version in `plugins/gin-workflow/plugin.meta.json` is the reference. The twelve manifests, the three CLI constants (`CLI_VERSION`, gin-qa `VERSION`, `ORCHESTRATOR_VERSION`), and the six installer launcher pins equal it. `tests/test_version_pins.py` checks all of them; other tests and the smoke scripts read the value instead of repeating it. `scripts/bump_version.py` rewrites the locations.
- Version pin: a new module `workflow_core/version_pin.py` parses versions, finds `.ginrc` by walking up from the start directory, and returns a verdict. `workflow_core/cli.py` checks it once in `main()` before the dispatch and owns the new `version` command. `setup_service.py` writes `.ginrc` in `init` and `update` and reports it in `doctor`.
- Session start: the Claude branch of the installers' hook templates gains a `SessionStart` entry that runs `gin version --hook`. The shared `src/hooks/hooks.json` stays as it is.
- Changelog and release: `docs/changelog.md` holds one section per release; `scripts/release_notes.py` prints one section; `release.yml` publishes it.
- Docs: `docs/guides/upgrading.md` (with a Vietnamese twin) is the upgrade guide; the reference pages describe the command, the file, and the refusal.

**Tech Stack**: Python 3 standard library, PyYAML; bash and PowerShell installers; unittest/pytest (`tests/test_version_pins.py`, `tests/workflow_core/test_setup_cli.py` with `run_cli`, `tests/gin_orchestrator/test_harness_packaging.py`, `tests/install_smoke_test.sh`, `tests/install_smoke_test.ps1`); MkDocs Material with `mkdocs-static-i18n`; `gin docs check`.

**Global Constraints** (spec "Errors and compatibility", verbatim):
- A project without `.ginrc` behaves as today. Nothing forces an existing project to add one.
- A gin older than 3.1.0 does not read `.ginrc`. The pin protects members from 3.1.0 on; an older gin still fails only on a configuration it cannot read.
- `gin --version` changes from `gin 3.0` to `gin 3.1.0`, and gin-qa and gin-orchestrator jump to 3.1.0. A script that parses those outputs must expect three parts.
- The launcher version of the installers becomes the full release version. An install over an older launcher must keep working and must not leave the old CLI linked.
- The session-start hook never fails a session: it exits 0 in every case, and without `gin` on PATH it does nothing.
- `gin-qa` reaches a project through `gin`, so it shows gin's refusal message.
- The release workflow fails on a tag whose changelog section is missing. That is intended.
- Pushing the tag publishes a GitHub release and deploys the site; it needs the user's approval each time.

## Route Rubric
- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis
- Problem statement: four plugin versions, three CLI versions, and three launcher pins are bumped by hand; nothing tells a member that their gin is older than the project needs; nothing runs at session start; there is no changelog (spec "Problem", with `file:line` evidence).
- Success criteria: R1 to R17 and the acceptance criteria of US-1 to US-6.
- Constraints: `main()` of `workflow_core/cli.py` has no shared step before its dispatch, and each command group resolves its own root; `doctor`'s status depends only on its `checks` booleans; `update` returns early when the configuration is up to date; about 25 assertions hard-code version numbers; a new top-level command needs a heading in `docs/reference/cli.md`; a new docs page needs a `nav` entry, a README row, and a `nav_translations` title; docs may not contain the words that `test_no_doc_or_skill_mentions_notifications` bans.
- Non-goals: session-start hooks for Codex, Copilot, Antigravity, and OpenCode; detecting a plugin copy that differs from the CLI; changelog sections before 3.1.0; a Vietnamese changelog page; merging the config schema version or the orchestrator contract version into the release version.

## Approach Options
### Option 1: `.ginrc` checked by the CLI against its own release version (confirmed)
- Summary: one release version for the set; a one-line `.ginrc`; `gin` refuses when incompatible; a silent hook for Claude Code.
- Pros: the CLI can always read its own version; the file is readable before any configuration; one number per release.
- Cons: a gin older than 3.1.0 ignores the file.

### Option 2: a version key in `.agent-workflow/config.yaml`
- Summary: the minimum version is a key of the configuration.
- Pros: no new file.
- Cons: an older gin may fail to read a newer configuration before it reaches the key; the hook would need YAML.

### Option 3: compare the plugin manifest of each harness
- Summary: the pin is checked against the plugin copy the harness loaded.
- Pros: catches a stale plugin.
- Cons: each harness keeps its own copy and the CLI cannot read them.

### Recommended Approach
- Selected option: Option 1.
- Rationale: confirmed by the user on 2026-11-15.

## Scope
- In scope: everything under "In scope" in the spec.
- Out of scope: everything under "Out of scope" in the spec.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Each track builds on the one before it (the version, the pin, the hook, the pages that describe them), and several tracks edit the same installers and reference pages.
```

## Tasks

The tracks commit one after another on `feat/release-version-pin` in `.claude/worktrees/release-version-pin`. Run the CLIs under test from the source tree (`python3 plugins/gin-workflow/src/scripts/gin ...`); the installed ones are older.

### Track 1: One version for the whole set
- **Dependencies**: none
- **Files**:
  - Create `scripts/bump_version.py`
  - Modify `plugins/gin-workflow/plugin.meta.json`, `plugins/gin-workflow/src/.claude-plugin/plugin.json`, `plugins/gin-workflow/src/.codex-plugin/plugin.json`
  - Modify `plugins/gin-qa/plugin.meta.json`, `plugins/gin-qa/src/.claude-plugin/plugin.json`, `plugins/gin-qa/src/.codex-plugin/plugin.json`
  - Modify `plugins/gin-orchestrator/plugin.meta.json`, `plugins/gin-orchestrator/src/.claude-plugin/plugin.json`, `plugins/gin-orchestrator/src/.codex-plugin/plugin.json`
  - Modify `plugins/gin-ba/plugin.meta.json`, `plugins/gin-ba/src/.claude-plugin/plugin.json`, `plugins/gin-ba/src/.codex-plugin/plugin.json`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/cli.py:19` (`CLI_VERSION`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:15` (`VERSION`)
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/cli.py:50` (`ORCHESTRATOR_VERSION`)
  - Modify `install.sh:12-14`, `install.ps1:18-20` (the launcher versions)
  - Modify `docs/reference/orchestrator-contract.md:18`, `docs/reference/troubleshooting.md:14` (the quoted versions)
  - Test `tests/test_version_pins.py`
  - Test `tests/test_bump_version.py`
  - Test `tests/install_smoke_test.sh`, `tests/install_smoke_test.ps1`
  - Test `tests/gin_orchestrator/test_harness_packaging.py`, `tests/gin_orchestrator/test_orchestrator_packaging.py`, `tests/gin_orchestrator/test_contract_cli.py`, `tests/gin_orchestrator/test_contract_v2.py`
  - Test `tests/gin_ba/test_ba_packaging.py`, `tests/workflow_core/test_setup_cli.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** mechanical in each file but wide: about forty locations in JSON, Python, bash, and PowerShell, with two long smoke scripts that must keep passing.
- **Interfaces**:
  - The reference is `"version"` in `plugins/gin-workflow/plugin.meta.json`. After this track it is `3.1.0` everywhere: the twelve manifests, `CLI_VERSION = "3.1.0"`, gin-qa `VERSION = "3.1.0"`, `ORCHESTRATOR_VERSION = "3.1.0"`, `LAUNCHER_VERSION`, `QA_LAUNCHER_VERSION`, `ORCH_LAUNCHER_VERSION` in `install.sh`, and `$LauncherVersion`, `$QaLauncherVersion`, `$OrchLauncherVersion` in `install.ps1`. `CONTRACT_VERSION` and `REQUIRES_GIN_WORKFLOW` of gin-orchestrator do not change.
  - `scripts/bump_version.py`: `locations(root: Path) -> list[tuple[Path, re.Pattern]]` lists every file with the pattern whose group 1 is the version; `bump(root: Path, version: str) -> list[Path]` validates `^\d+\.\d+\.\d+$` (else `ValueError`, nothing written), replaces group 1 in every location, and returns the changed files; a location whose pattern does not match raises `ValueError` naming the file, before any write. `main(argv)` prints the changed files and exits 0, or prints `error: <message>` on stderr and exits 2. Run as `python3 scripts/bump_version.py X.Y.Z`.
  - `tests/test_version_pins.py` imports `locations` from the script (as `tests/workflow_core/test_benchmark_summary.py` loads `scripts/benchmark/summarize_usage.py`) and asserts that every location holds the reference version, naming the file that differs. It also asserts that no tracked `plugin.meta.json` or `plugin.json` under `plugins/*/` is missing from `locations`.
  - Tests that hard-code a number read the reference instead: `test_harness_packaging.py:263`, `test_orchestrator_packaging.py:27`, `test_contract_cli.py:71`, `test_contract_v2.py:87`, `test_ba_packaging.py:22`, `test_setup_cli.py:44`. The smoke scripts read it once at the top (`python3 -c` on `plugin.meta.json` in the bash script, `ConvertFrom-Json` in the PowerShell script) and use that variable for the current version, the launcher directories, and the `--version` outputs. The old-version fixtures (`2.1`, `0.4`, `0.0`) stay literals.
  - Installers: the launcher directory becomes `~/.local/lib/<name>/3.1.0/`. `is_managed_launcher_link` and `Test-ManagedLauncherShim` accept any single path segment, so they need no change; an older directory stays on disk and the link is repointed, as today.
  - Error handling: `ValueError` for a bad version or an unmatched location; `OSError` from reading or writing propagates to `main`, which reports it and exits 2. No `except Exception`.
- **Steps**:
  1. Failing tests: `tests/test_version_pins.py` rewritten per the interfaces (it fails because the locations differ and the script does not exist); `tests/test_bump_version.py`: on a copy of the listed files in a temporary tree, `bump(tmp, "9.8.7")` changes every location and a second run changes nothing; `bump(tmp, "3.1")` raises and leaves every file untouched; a file whose pattern no longer matches raises and names it; `main` exits 2 on a bad value.
  2. Run `timeout 300 python3 -m pytest tests/test_version_pins.py tests/test_bump_version.py -q` → fail.
  3. Write `scripts/bump_version.py`, then run `python3 scripts/bump_version.py 3.1.0`. Replace the hard-coded numbers in the listed tests and the two smoke scripts, and the two quoted versions in the docs.
  4. Run step 2 → pass; `timeout 900 python3 -m pytest tests/gin_orchestrator tests/gin_ba tests/workflow_core/test_setup_cli.py tests/gin_qa/test_packaging.py -q -n auto` → pass; `timeout 900 bash tests/install_smoke_test.sh` → pass (keep its last lines); `python3 plugins/gin-workflow/src/scripts/gin --version` → `gin 3.1.0`; `python3 plugins/gin-workflow/src/scripts/gin docs check docs/reference/orchestrator-contract.md docs/reference/troubleshooting.md` → ok. Report that `tests/install_smoke_test.ps1` was changed but not run when PowerShell is not installed.
  5. Commit: `feat(release): one version for the whole set, pinned by one test and written by one script (gin-workflow-b7ip)`.
- **Acceptance criteria**: R1, R2, R3; US-3; the 3.1.0 bump of R17.
- **Estimated complexity**: medium

### Track 2: `.ginrc`, the refusal, and `gin version`
- **Dependencies**: Track 1
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/version_pin.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/cli.py:19-21,88-187` (`TOP_COMMANDS`, `main`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py:36-45,175-287,426-617,649-727` (`INIT_ACTIONS`, `initialize`, `doctor`, `update`)
  - Modify `docs/reference/cli.md` (a `gin version` section, the refusal, the `gin setup` rows)
  - Modify `docs/reference/config.md` (a `.ginrc` section under "Versions and migration")
  - Test `tests/workflow_core/test_version_pin.py`
  - Test `tests/workflow_core/test_setup_cli.py`
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** a check in front of every command group, a root lookup that differs from the existing one, and three setup commands whose result shapes existing tests pin.
- **Interfaces**:
  - `version_pin.FILE = ".ginrc"`; `GUIDE = "https://giangdhwhtbr.github.io/gin-workflow/guides/upgrading/"`.
  - `version_pin.parse(text: str) -> tuple[int, int, int]`: the stripped text must match `^\d+\.\d+\.\d+$`, else `PinError(ValueError)`.
  - `version_pin.find(start: Path) -> Path | None`: the nearest `.ginrc` in `start` or one of its parents. This covers a subdirectory, a linked worktree (it has its own tracked copy), a workspace child and its track worktrees (both lie under the parent).
  - `version_pin.verdict(installed: str, start: Path) -> Verdict` with `status` one of `none`, `compatible`, `older`, `newer_major`, `invalid`, plus `required: str | None` and `path: Path | None`. Same major and installed at least the pin: `compatible`. Installed lower, in any part order: `older`. Installed major higher: `newer_major`. A different, lower major is `older`.
  - `version_pin.message(verdict, installed) -> str`, one line: for `older`, `gin <installed> is older than this project needs (<required>, <path>); update gin: <GUIDE>`; for `newer_major`, `gin <installed> is a newer major version than this project uses (<required>, <path>); upgrade the project with gin setup update --approve: <GUIDE>`; for `invalid`, `<path> must hold one version X.Y.Z`.
  - `cli.main`: `"version"` joins `TOP_COMMANDS`. After the command name is validated and before the dispatch, for every command except `paths` and `version`: the start directory is the value of `--repository` when `argv` has one (`--repository X` or `--repository=X`), else the current directory; `older` and `invalid` print `error: <message>` on stderr and return 2; `newer_major` does the same unless the command is `setup`. The module stays free of YAML at import time.
  - `gin version [--repository DIR] [--format text|json] [--hook]`: text prints `gin <installed>`, then `project: <required> (<path>)` and `compatible: yes|no` when there is a `.ginrc`, then `gin-qa <version>` and `gin-orchestrator <version>` for each companion found on PATH (`gin-qa --version`, and `gin-orchestrator version --json` key `orchestrator_version`; a companion that is missing or fails is left out). JSON: `{"installed", "required", "path", "status", "compatible", "companions": {...}}`. Exit 0 for `none` and `compatible`, 1 otherwise.
  - `gin version --hook`: prints nothing for `none` and `compatible`; otherwise prints `message(...)` followed by ` Tell the user before any other work.` on one line. It starts no subprocess and always returns 0, also on `OSError`.
  - `setup_service.initialize`: the fresh-init `writes` include `root / ".ginrc"` with the installed version and a newline, and `INIT_ACTIONS` gains `create .ginrc`. An existing `.ginrc` is left as it is.
  - `setup_service.update`: when `.ginrc` is missing or lower than the installed version, the proposal gains the action `write .ginrc <old or none> -> <installed>` and a status of `up_to_date` becomes `migration_available`, as the local actions do today; with `--approve` the file is written with the other writes, also when no configuration migration applies. A `.ginrc` at or above the installed version adds nothing.
  - `setup_service.doctor`: without `.ginrc`, the action `version: no .ginrc; run gin setup update --approve`, and `checks_details["version"] = {"installed", "required", "status"}`. A companion on PATH whose version differs from gin's adds `version: <name> <its version> differs from gin <installed>; run ./install.sh --plugin <plugin>` (the orchestrator's from `orchestrator_client.status()`, gin-qa's from `gin-qa --version`). These are actions only: `status` stays driven by `checks`.
  - Error handling: `PinError` for bad content; `OSError` when reading `.ginrc` is reported as `invalid` with the OS message, except under `--hook`, where it prints nothing; a companion probe catches `OSError`, `subprocess.TimeoutExpired`, and `ValueError` and leaves that companion out. No `except Exception`.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_version_pin.py` (through the launcher, with a temporary git repository and a `.ginrc` written by the test; the installed version comes from `workflow_core.cli.CLI_VERSION`):
     - each row of R5 for `gin state --format json`: no file, equal, lower pin, higher pin (exit 2, the message names both versions and the guide), higher major installed than pinned (exit 2), invalid content (exit 2);
     - `gin --version`, `gin paths`, and `gin version` run in every one of those cases;
     - with a pin of a lower major version, `gin setup doctor` runs and `gin state` is refused;
     - the lookup: from a subdirectory, from a linked worktree, and with `--repository <dir>` from another directory;
     - `gin version` text and JSON for compatible, older, and no file; exit codes 0 and 1;
     - `gin version --hook`: empty output and exit 0 for no file and compatible; one line ending with `Tell the user before any other work.` and exit 0 for older and for invalid.
  2. Failing tests in `tests/workflow_core/test_setup_cli.py` (with `run_cli`): `init --approve` writes `.ginrc` with the installed version and lists `create .ginrc`; `init` keeps an existing `.ginrc`; `update` without `--approve` lists `write .ginrc ...` and reports `migration_available` for a project whose configuration is current but has no `.ginrc`; `update --approve` writes it; `update` with a current `.ginrc` reports `up_to_date`; `doctor` reports the missing file and, with a fake `gin-qa` on PATH that prints another version, the companion finding. Update the existing assertions on `actions` that the new entries change.
  3. Run `timeout 600 python3 -m pytest tests/workflow_core/test_version_pin.py tests/workflow_core/test_setup_cli.py -q` → fail.
  4. Implement per the interfaces. Add `## \`gin version\`` to `docs/reference/cli.md`, the refusal and its exit code where the page lists exit codes, and the `.ginrc` actions in the `gin setup` section; add the `.ginrc` section to `docs/reference/config.md` (the file, the rule of R5, who writes it), linking to the CLI reference for the messages.
  5. Run step 3 → pass; `timeout 900 python3 -m pytest tests/workflow_core -q -n auto -k "setup or cli or docs or rename or version or lifecycle or workspace"` → pass; `timeout 600 python3 -m pytest tests/gin_qa -q -n auto` → pass; `python3 plugins/gin-workflow/src/scripts/gin docs check docs/reference/cli.md docs/reference/config.md` → ok. Time the hook path once: `time python3 plugins/gin-workflow/src/scripts/gin version --hook` in a directory without `.ginrc`, and report it.
  6. Commit: `feat(version): .ginrc pins the version a project needs; gin refuses when incompatible; gin version (gin-workflow-b7ip)`.
- **Acceptance criteria**: R4 to R9, R11, the CLI and configuration part of R15; US-1 criteria 2 to 4; US-2.
- **Estimated complexity**: high

### Track 3: Claude Code session-start hook
- **Dependencies**: Track 2
- **Files**:
  - Modify `install.sh:323-342` (`template_hooks_for_claude`)
  - Modify `install.ps1:136-176` (`New-HooksFile`, the `claude` branch)
  - Test `tests/install_smoke_test.sh`, `tests/install_smoke_test.ps1`
  - Test `tests/gin_orchestrator/test_harness_packaging.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one entry in two installer templates, with assertions in three test files that must tell Claude's file from the other harnesses' files.
- **Interfaces**:
  - The Claude hooks file gains, next to `PreToolUse`, the event `SessionStart` with one entry: `{"hooks": [{"type": "command", "command": <command>, "timeout": 10}]}`.
  - `<command>` in `install.sh`: `if command -v gin >/dev/null 2>&1; then gin version --hook; fi; exit 0`. In `install.ps1`, the form the existing Claude template uses for its command, written so that a missing `gin` gives no output and exit 0.
  - The Codex, Antigravity, and Copilot templates and `plugins/gin-workflow/src/hooks/hooks.json` do not change.
  - Before writing, confirm the event name and entry shape against the Claude Code hooks reference (`https://code.claude.com/docs/en/hooks`); if it differs from the interface above, stop and report `needs_clarification` with the quoted reference.
- **Steps**:
  1. Failing assertions: in `tests/install_smoke_test.sh`, next to the Claude hooks assertion (~350), assert that the installed Claude `hooks/hooks.json` contains `"SessionStart"` and `gin version --hook`, and that the Codex and Copilot hooks files do not contain `SessionStart`; the same in `tests/install_smoke_test.ps1` for the Claude file; in `tests/gin_orchestrator/test_harness_packaging.py`, a test that the generated Claude hooks file has exactly the events `PreToolUse` and `SessionStart` and that the other harness files have no `SessionStart`.
  2. Run `timeout 300 python3 -m pytest tests/gin_orchestrator/test_harness_packaging.py -q` and `timeout 900 bash tests/install_smoke_test.sh` → fail on the new assertions.
  3. Edit the two templates.
  4. Run step 2 → pass. In a temporary project with a `.ginrc` above the installed version, run the generated command by hand with the source `gin` first on PATH and keep its one-line output; in a project without `.ginrc`, show that it prints nothing and exits 0.
  5. Commit: `feat(hooks): the Claude Code hooks file tells the agent at session start when gin is older than the project needs (gin-workflow-b7ip)`.
- **Acceptance criteria**: R10; US-1 criteria 1 and 3.
- **Estimated complexity**: medium

### Track 4: Changelog page with the 3.1.0 section
- **Dependencies**: Track 1, Track 2, Track 3
- **Files**:
  - Create `docs/changelog.md`
  - Modify `mkdocs.yml` (`nav`, `nav_translations`)
  - Modify `README.md:9-19` (the documentation table)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** one page, but its 3.1.0 section condenses 35 shipped epics and about fifteen quick fixes into grouped entries that must each be true to the code.
- **Interfaces**:
  - Page shape: `# Changelog`; one intro paragraph (what the page holds, that releases before 3.1.0 are on the GitHub releases page, with the link `https://github.com/giangdhwhtbr/gin-workflow/releases`); then `## [3.1.0] - 2026-11-15` with `### Upgrade notes`, `### Added`, `### Changed`, `### Fixed`, `### Removed`. A group with no entry is left out. Newest release first.
  - Sources for the 3.1.0 section: `git log --merges --format='%s' v3.0.0..HEAD`; the closed epics with `closed_at` after `2026-11-08T23:10` (`gin task list --status closed --type epic --json`, fields `title`, `close_reason`); their specs under `.planning/specs/` dated 2026-11-09 or later; and this epic's own tracks. One entry per user-visible change, in a user's terms, naming the command, key, or skill; internal refactors and test work are left out.
  - Upgrade notes cover: one version for the whole set and the new `--version` outputs; `.ginrc` and the refusal; configuration schema 2.10 and `gin setup update --approve`; the full suite running at push by default for `easy` and `standard` rigor (`verify.run_at`); `gin hooks install` when hooks changed. They link to `guides/upgrading.md`, which Track 6 creates: write the link as plain text `the upgrade guide` in this track and make it a link in Track 6.
  - `mkdocs.yml`: `- Changelog: changelog.md` as the last top-level `nav` entry, and `Changelog: Nhật ký thay đổi` under `nav_translations`. `README.md`: a row `| [Changelog](docs/changelog.md) | what changed in each release |` in the documentation table.
  - Rules: true to code (check each entry against the code or the reference pages); no em or en dashes; no list item that opens with a bold label; no numbered heading; sentences of at most 35 words; no word that `tests/workflow_core/test_docs_coverage.py::test_no_doc_or_skill_mentions_notifications` bans (name that removal as the removal of the event messages feature and the configuration key it used, without the banned words).
- **Steps**:
  1. Collect the sources and group the changes; check each entry against the code.
  2. Write the page and the three wiring edits.
  3. Run `python3 plugins/gin-workflow/src/scripts/gin docs check docs/changelog.md README.md` → ok; `timeout 300 python3 -m pytest tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_docs_check.py -q` → pass. When `mkdocs` is installed, run `mkdocs build --strict` and keep its last lines; otherwise say it was not run.
  4. Commit: `docs(changelog): a changelog page with the 3.1.0 section (gin-workflow-b7ip)`.
- **Acceptance criteria**: R12, the changelog part of R17; US-4 criteria 1 and 2.
- **Estimated complexity**: medium

### Track 5: Release notes from the changelog
- **Dependencies**: Track 4
- **Files**:
  - Create `scripts/release_notes.py`
  - Modify `.github/workflows/release.yml:40-44`
  - Modify `docs/contributing.md:118-124` ("Releasing")
  - Test `tests/test_release_notes.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** a small text-slicing script with a clear contract, one workflow step, and one docs section.
- **Interfaces**:
  - `scripts/release_notes.py`: `section(text: str, version: str) -> str` returns the lines after the heading `## [<version>]` up to the next `## [` heading or the end, stripped; it raises `ValueError(f"docs/changelog.md has no section for {version}")` when the heading is missing or the section is empty. `main(argv)`: `python3 scripts/release_notes.py X.Y.Z [--file PATH]` prints the section and exits 0, or prints `error: <message>` on stderr and exits 1. The default file is `docs/changelog.md` next to the script's repository root.
  - `release.yml`: before "Create the release", a step writes `python3 scripts/release_notes.py "${GITHUB_REF_NAME#v}" > release-notes.md` (it fails the job when there is no section); the release step uses `--notes-file release-notes.md` in place of `--generate-notes`.
  - `docs/contributing.md`, "Releasing": step 1 becomes `python3 scripts/bump_version.py X.Y.Z` (the test of version unity names every location); a new step writes the changelog section from the epics closed since the previous tag and its upgrade notes; a new step raises this repository's `.ginrc` with `gin setup update --approve` when the release needs it; the tag step says the workflow takes the release notes from the changelog and fails without a section.
- **Steps**:
  1. Failing tests in `tests/test_release_notes.py` (load the script as `test_benchmark_summary.py` loads its script): a text with two sections returns the first without the second; a missing version raises; an empty section raises; `main` exits 1 for a missing version; the real `docs/changelog.md` has a section for the version in `plugins/gin-workflow/plugin.meta.json`.
  2. Run `timeout 300 python3 -m pytest tests/test_release_notes.py -q` → fail.
  3. Write the script, the workflow step, and the docs section.
  4. Run step 2 → pass; `python3 scripts/release_notes.py 3.1.0 | head -5` prints the start of the section; `python3 plugins/gin-workflow/src/scripts/gin docs check docs/contributing.md` → ok; `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"` → no error.
  5. Commit: `feat(release): GitHub release notes come from the changelog; release steps use the bump script (gin-workflow-b7ip)`.
- **Acceptance criteria**: R13, R14; US-4 criteria 3 and 4.
- **Estimated complexity**: low

### Track 6: Upgrade guide and user docs
- **Dependencies**: Track 2, Track 3, Track 4
- **Files**:
  - Create `docs/guides/upgrading.md`, `docs/guides/upgrading.vi.md`
  - Modify `mkdocs.yml` (`nav`, `nav_translations`)
  - Modify `README.md` (the Guides row)
  - Modify `docs/changelog.md` (the link to the guide)
  - Modify `docs/reference/troubleshooting.md` (an entry for the refusal; a link from the 2.x section)
  - Modify `docs/guides/team.md`, `docs/guides/team.vi.md` (the lead raises `.ginrc`)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one new guide with a Vietnamese twin and three small edits; every command must be checked against the code of Tracks 1 to 3.
- **Interfaces** (the facts; check each against the code, `docs/reference/cli.md`, and `docs/reference/config.md`):
  - `docs/guides/upgrading.md` opens with what 3.1 is: the baseline, the first version with one number for the whole set and with `.ginrc`. Sections: a machine; a project; a member; what changes at 3.1.
  - A machine: the clone route (`git pull` in the clone, `./install.sh --platform all`, with `--plugin all` for the extensions) and the one-line route (`remote-install.sh`, as in `README.md`); a marketplace plugin is updated through its harness, and the CLIs still need the installer. State an in-place marketplace update command only when `claude plugin --help` on this machine shows one; otherwise give the uninstall and install commands the 2.x section uses. Check the result with `gin version`.
  - A project: the lead runs `gin setup update --approve` (the configuration migration and `.ginrc`), `gin hooks install`, commits `.agent-workflow/config.yaml` and `.ginrc`, and tells the team; in a workspace only in the parent.
  - A member: the refusal message of `gin` and the session-start line of an installer-made Claude Code install, both quoted from the code, and the machine steps that clear them. Other harnesses show the refusal at the first `gin` command.
  - What changes at 3.1: gin-qa, gin-orchestrator, and gin-ba move to 3.1.0; `--version` prints three parts; configuration schema 2.10; the full suite at push by default (`verify.run_at`); a gin older than 3.1 ignores `.ginrc`, so every member must reach 3.1 once.
  - `mkdocs.yml`: `- Upgrading: guides/upgrading.md` at the end of Guides, and `Upgrading: Nâng cấp` under `nav_translations`. `README.md`: `[upgrading](docs/guides/upgrading.md)` in the Guides row. `docs/changelog.md`: `the upgrade guide` becomes a link to `guides/upgrading.md`.
  - `docs/reference/troubleshooting.md`: a section for the refusal (`gin X is older than this project needs ...`) that links to the guide; the 2.x section gains one sentence that points to the guide for 3.1.
  - `docs/guides/team.md` and its twin: a short section that the lead raises `.ginrc` with `gin setup update --approve` after updating, commits it, and that members with an older gin are refused until they update.
  - Vietnamese pages: read `~/.claude/plugins/marketplaces/vietnamese-language-skill/skills/vietnamese-tech-writing/SKILL.md` first; keep anchors, identifiers, commands, and paths verbatim; the same facts as the English page.
- **Steps**:
  1. Read the code and reference pages of Tracks 1 to 3, the install section of `README.md`, and the 2.x section of the troubleshooting page.
  2. Write the guide, its twin, and the edits: sentence-case headings, no em or en dashes, no bold-label list items, sentences of at most 35 words, team practices called conventions.
  3. Prove the project steps: export the `v3.0.0` tree to a temporary directory (`git archive v3.0.0 plugins | tar -x -C <tmp>`), create a temporary git repository, run that old launcher's `setup init --approve --non-interactive` in it, then run this branch's `gin setup update --approve` there; show that `.ginrc` holds `3.1.0` and the configuration says schema `2.10`. Keep the output.
  4. Run `python3 plugins/gin-workflow/src/scripts/gin docs check docs/guides/upgrading.md docs/guides/upgrading.vi.md docs/changelog.md docs/reference/troubleshooting.md docs/guides/team.md docs/guides/team.vi.md README.md` → ok; `timeout 300 python3 -m pytest tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_walkthrough_docs.py tests/workflow_core/test_rename_sweep.py -q` → pass. When `mkdocs` is installed, run `mkdocs build --strict`.
  5. Commit: `docs(upgrade): a guide for moving machines and projects to the 3.1 baseline (gin-workflow-b7ip)`.
- **Acceptance criteria**: R15, R16; US-5.
- **Estimated complexity**: medium

### Track 7: Release 3.1.0 in the repository
- **Dependencies**: Track 1, Track 2, Track 3, Track 4, Track 5, Track 6
- **Files**:
  - Create `.ginrc`
  - Modify `docs/changelog.md` (the release date of the 3.1.0 heading, entries for anything the earlier tracks changed)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** two small file changes and the release checks of the contributing guide, run once on the whole branch.
- **Interfaces**:
  - `.ginrc` at the repository root holds `3.1.0` and a newline, written by `python3 plugins/gin-workflow/src/scripts/gin setup update --approve` (not by hand).
  - The 3.1.0 heading of `docs/changelog.md` carries the date of this track's commit, and the section names what Tracks 1 to 6 delivered.
- **Steps**:
  1. Run `python3 plugins/gin-workflow/src/scripts/gin setup update` and show the proposal; run it with `--approve`; show `cat .ginrc` and `git status --porcelain` (only `.ginrc` and, when the migration wrote one, files under ignored folders).
  2. Set the date in the changelog heading and complete the section.
  3. Release checks: `timeout 300 python3 -m pytest tests/test_version_pins.py tests/test_release_notes.py tests/workflow_core/test_version_pin.py tests/workflow_core/test_docs_coverage.py -q` → pass; `python3 scripts/release_notes.py 3.1.0 | head -8`; `python3 plugins/gin-workflow/src/scripts/gin version` → `compatible: yes`; `timeout 900 bash tests/install_smoke_test.sh` → pass; `python3 plugins/gin-workflow/src/scripts/gin docs check docs/changelog.md` → ok.
  4. Commit: `chore(release): 3.1.0 (gin-workflow-b7ip)`.
- **Acceptance criteria**: R17 up to the tag; US-6 criterion 1.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/release-version-pin`
- **Merge strategy**: sequential
- After ship merges the branch into `master` and pushes it, and after the user approves, tag that commit `v3.1.0` and push the tag. The release workflow then tests, publishes the GitHub release with the changelog section, and deploys the site. When the `pages` job is rejected on the tag run, rerun the workflow with `workflow_dispatch` on `master`. The epic closes after the tag (US-6 criteria 2 and 3).

## Validation
- [ ] Each track's targeted tests pass (the commands in its steps).
- [ ] `bash tests/install_smoke_test.sh` passes after Tracks 1, 3, and 7.
- [ ] `gin docs check` is ok on every changed page.
- [ ] The full suite passes once at ship (`gin evidence run` on `feat/release-version-pin`, `project.run_at: push`).
- [ ] After the tag: the GitHub release `v3.1.0` shows the changelog section and the site shows the changelog and the upgrade guide.

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- This epic runs with the project's settings: no track worktrees, no review ledger, an independent reviewer per track, and the tests of the changed code per track.
- `tests/install_smoke_test.ps1` is edited with its bash twin; it runs only where PowerShell is installed, and the release workflow does not run it.
- Old launcher directories under `~/.local/lib/<name>/` stay on disk after an install, as today; only the link moves.
- Deliverable merge-holds apply only to the parent bead `gin-workflow-b7ip`; track beads close after their tests and review pass.

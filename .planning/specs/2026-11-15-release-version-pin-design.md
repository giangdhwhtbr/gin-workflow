# One version for the whole set, a project version pin, and a changelog

Epic: gin-workflow-b7ip
Kind: capability
Status: draft for user review.

## Goal and scope

The four plugins and three CLIs of this repository carry one release version. A project records the minimum version it needs in `.ginrc`, an older `gin` refuses to run there, and in Claude Code a session-start hook tells the agent at once. The documentation site has a changelog page, the GitHub release takes its notes from it, and version 3.1.0 ships.

Problem:
- Each plugin has its own version: gin 3.0.0, gin-qa 0.11.0, gin-orchestrator 0.2.0, gin-ba 0.1.0 (`plugins/*/plugin.meta.json:3`). The CLIs print other numbers again: `CLI_VERSION = "3.0"` (`workflow_core/cli.py:19`), `VERSION = "0.11"` (`gin_qa/cli.py:15`), `ORCHESTRATOR_VERSION = "0.2.0"` (`gin_orchestrator/cli.py:50`). The installers pin three launcher versions (`install.sh:12-14`).
- A release bumps these by hand in about twenty places (`docs/contributing.md`, "Releasing", step 1), and tests hard-code the numbers (`tests/gin_orchestrator/test_harness_packaging.py:263`).
- Nothing tells a member that their gin is older than the project needs. A config newer than the CLI fails with `unsupported schema_version ...` (`workflow_core/configuration.py:209`), which does not say to update gin, and a change that leaves the config schema alone gives no signal at all. The docs can only ask: "Every member must update gin before the lead runs it" (`docs/concepts/lifecycle.md:55`).
- Nothing runs when a session starts: the plugin registers one `PreToolUse` hook (`plugins/gin-workflow/src/hooks/hooks.json`).
- There is no changelog. The release workflow publishes generated notes (`.github/workflows/release.yml:44`), and 35 epics have closed since `v3.0.0` (2026-11-08).

In scope:
- One version for gin, gin-qa, gin-orchestrator, and gin-ba, held equal by a test and written by a bump script.
- `.ginrc`, the comparison rule, the refusal in the `gin` CLI, and `gin setup` writing the file.
- A `gin version` command and a Claude Code session-start hook that calls it.
- `docs/changelog.md`, the release notes taken from it, and the rewritten release steps.
- A guide for upgrading a machine and a project to 3.1, the baseline version.
- The 3.1.0 release.

Out of scope:
- A session-start hook for Codex, Copilot, Antigravity, and OpenCode. There the first `gin` command of a session refuses. A later epic can add their hooks.
- Detecting that a harness holds a plugin copy newer or older than the installed CLI.
- Changelog entries for releases before 3.1.0, and a Vietnamese changelog page.
- Merging the config schema version (`schema_version`, `workflow_version`, `setup_cli_version`) or the gin-orchestrator contract version into the release version. They version formats, not the product.
- Blocking on a companion CLI whose version differs; that is a warning.

Confirmed decisions (user, 2026-11-15): the whole set shares one version; `.ginrc` holds a minimum, an older installed version is refused, and a different major version is always incompatible; the check lives in the CLI, with a silent session-start hook for Claude Code first; an incompatible `gin` refuses to run; the changelog is one docs page written at release time; the next version is 3.1.0; the docs carry a guide for upgrading to the 3.1 baseline.

Comments considered: 2, latest 2026-11-15T08:18:53Z
Confirmed summary (user, 2026-11-15): the goal and scope above. The two `[gin ship]` comments say `gin-workflow-quick-team` (merge `214c9b29`) and `gin-workflow-8gal` (merge `20612a5e`) shipped; they change nothing in this epic and are entries for the changelog. The release no longer waits for another epic.

Assumptions:
- An earlier spec dropped a session-start hook because its output entered every session and cost tokens and start-up time (`.planning/specs/2026-10-30-reliability-core-design.md:23`). This hook prints nothing when the versions are compatible, so that reason does not apply.
- The installed CLI is what a project is checked against, because only the CLI can read its own version at run time and it is what records gates and data.

## Requirements

R1. One release version. gin, gin-qa, gin-orchestrator, and gin-ba carry the same version `X.Y.Z`. It is the value of every `plugin.meta.json`, every `src/.claude-plugin/plugin.json` and `src/.codex-plugin/plugin.json`, the version each CLI prints (`gin --version`, `gin-qa --version`, and the version gin-orchestrator reports), and the launcher versions of `install.sh` and `install.ps1`.

R2. One test holds every location of R1 equal to the version in `plugins/gin-workflow/plugin.meta.json` and names the file that differs. Tests that hard-code a version number read that value instead.

R3. `python3 scripts/bump_version.py X.Y.Z` writes the version to every location of R1. It refuses a value that is not `X.Y.Z` and changes nothing then. After it runs, the test of R2 passes.

R4. `.ginrc` is a file at the project root, tracked in git, with one line: the minimum version `X.Y.Z` the project needs. In a workspace only the parent has one. Content that is not one version is an error.

R5. Comparison of the installed version with `.ginrc`:
- same major version and installed equal or newer: compatible;
- installed older: incompatible, the user must update gin;
- installed major version newer: incompatible, the project must be upgraded with `gin setup update`;
- no `.ginrc`: no check, as today.

R6. Refusal. Every `gin` command that reads a project checks `.ginrc` before it loads the configuration. When incompatible it exits 2 with one message that names the installed version, the version the project needs, and what to do. `gin --version`, `gin paths`, and `gin version` are not refused. With a newer installed major version, `gin setup` commands still run, so the project can be upgraded. An invalid `.ginrc` exits 2 and says what the file must hold.

R7. Writing `.ginrc`. `gin setup init --approve` creates it with the installed version. `gin setup update` proposes raising it to the installed version, alone or with a configuration migration, and writes it with `--approve`. `gin setup doctor` reports a project that has no `.ginrc` and names that command.

R8. `gin version` prints the installed version, the project's `.ginrc` version when there is one, whether they are compatible, and the versions of `gin-qa` and `gin-orchestrator` found on PATH. `--format json` gives the same as an object. It exits 0 when compatible or when there is no `.ginrc`, and 1 when incompatible.

R9. `gin version --hook` prints nothing when compatible or when there is no `.ginrc`. When incompatible, or when `.ginrc` is invalid, it prints one line: the installed version, the needed version, what to do, and that the agent tells the user before any other work. It always exits 0. It reads `.ginrc` and compares two versions without loading the configuration, the task tracker, or YAML.

R10. Claude Code session-start hook. The Claude hooks file that `install.sh` and `install.ps1` generate registers a session-start hook that runs `gin version --hook` when `gin` is on PATH and does nothing otherwise. `plugins/gin-workflow/src/hooks/hooks.json` does not change: marketplace installs of other harnesses load that file, and their hooks are out of scope.

R11. Companion versions. `gin setup doctor` reports a `gin-qa` or `gin-orchestrator` on PATH whose version differs from gin's, with the reinstall command. It is a finding, never a refusal.

R12. `docs/changelog.md` is the one home of release changes. Each release has a section `## [X.Y.Z] - YYYY-MM-DD`, newest first, with the groups of the `write-doc` changelog template (Added, Changed, Fixed, Removed) and, when a user must act or a default changed, upgrade notes. The page is in the site navigation and in the documentation table of `README.md`. Releases before 3.1.0 are not written up; the page links to the GitHub releases for them.

R13. Release notes. `python3 scripts/release_notes.py X.Y.Z` prints the changelog section of that version and exits with an error when there is none. `.github/workflows/release.yml` publishes that text as the notes of the GitHub release and fails when `docs/changelog.md` has no section for the tag.

R14. `docs/contributing.md`, "Releasing", describes the new steps: `scripts/bump_version.py`, the changelog section written from the epics closed since the previous tag, the project's own `.ginrc`, and the tag.

R15. User docs. `docs/reference/config.md` describes `.ginrc` and the rule of R5; `docs/reference/cli.md` describes `gin version` and the refusal; `docs/reference/troubleshooting.md` names the refusal and links to the upgrade guide; the team guide says that the lead raises `.ginrc` and what members then see. Vietnamese twins of changed pages carry the same facts.

R16. Upgrade guide. `docs/guides/upgrading.md`, with a Vietnamese twin, says how to move to 3.1, the baseline: the first version that carries one number for the whole set and reads `.ginrc`. It covers:
- a machine: updating the plugins and the CLIs together, for a clone install and for a marketplace install, and checking the result with `gin version`;
- a project: the lead runs `gin setup update --approve` (the configuration migration and `.ginrc`), commits the result, and tells the team; in a workspace this happens in the parent only;
- a member: what the refusal and the session-start line look like and how to clear them;
- what changes at 3.1: the version numbers of gin-qa, gin-orchestrator, and gin-ba, the output of `--version`, configuration schema 2.10, and the full suite running at push by default;
- that a gin older than 3.1 ignores `.ginrc`, so every member must reach 3.1 once.
The page is in the site navigation and the documentation table of `README.md`. The refusal message, the changelog's upgrade notes, and the troubleshooting page link to it; the existing section on upgrading from 2.x stays where it is.

R17. Release 3.1.0. The whole set is bumped to 3.1.0. The changelog has the 3.1.0 section, written from the epics closed after `v3.0.0`, with upgrade notes for configuration schema 2.10, the full suite running at push by default, and `.ginrc`. This repository gets a `.ginrc`. After the merge to `master` is pushed, the tag `v3.1.0` is put on that commit and pushed once the user approves it; the epic closes after the tag.

## User Stories

### US-1: A member with an old gin is told at once
As a team member, I want my agent to tell me when my gin is older than the project needs, so that I update before I record anything with an old version.

Acceptance criteria:
- In a project whose `.ginrc` names a newer version than the installed one, a new Claude Code session on an installer-made install shows one line that names both versions and what to do.
- In that project `gin state` exits 2 with a message that names both versions and what to do.
- With a compatible version, or without `.ginrc`, the session-start hook prints nothing and `gin state` behaves as today.
- `gin --version`, `gin paths`, and `gin version` run in every case.

### US-2: A lead raises the version a project needs
As a tech lead, I want to set the version my project needs, so that every member runs a compatible gin.

Acceptance criteria:
- `gin setup init --approve` in a new project writes `.ginrc` with the installed version.
- `gin setup update` in a project whose `.ginrc` is older than the installed version proposes the new value, and `--approve` writes it.
- `gin setup doctor` in a project without `.ginrc` reports it and names the command that creates it.
- With an installed major version newer than `.ginrc`, `gin state` is refused and `gin setup update` still runs.

### US-3: One version for the whole set
As a maintainer, I want every plugin and CLI to carry the release version, so that a release is one number.

Acceptance criteria:
- `gin --version` and `gin-qa --version` print the same `X.Y.Z` as `plugins/gin-workflow/plugin.meta.json`.
- `python3 scripts/bump_version.py 3.1.1` changes every version location, and the test of R2 passes afterwards.
- With one location changed by hand, the test of R2 fails and names that file.
- `python3 scripts/bump_version.py 3.1` exits with an error and changes no file.

### US-4: A changelog the team can update
As a team member, I want one page that lists what changed in each release, so that I know what an update brings and what I must do after it.

Acceptance criteria:
- The documentation site and the documentation table of `README.md` link to the changelog page.
- The 3.1.0 section lists the changes since 3.0.0 in groups and has upgrade notes.
- The script of R13 prints the 3.1.0 section for `3.1.0` and exits with an error for a version that has no section.
- The release workflow uses that text as the release notes.

### US-5: A team moves to the 3.1 baseline
As a tech lead of an existing project, I want one guide for moving my machines and my project to 3.1, so that the whole team ends on one version.

Acceptance criteria:
- The upgrade guide gives the steps for a machine, for a project, and for a member, each with the exact commands.
- Following the project steps in a 3.0 project leaves a migrated configuration and a `.ginrc` with `3.1.0`.
- The refusal message of `gin` names the guide.
- The guide exists in English and Vietnamese and is linked from the site navigation, `README.md`, and the 3.1.0 changelog section.

### US-6: Version 3.1.0 is released
As the owner, I want version 3.1.0 tagged and published, so that teams can install it.

Acceptance criteria:
- Every version location says 3.1.0 and this repository has a `.ginrc` with `3.1.0`.
- The tag `v3.1.0` exists on the merge commit, and the GitHub release shows the 3.1.0 changelog section.
- The documentation site shows the changelog page.

## Errors and compatibility

- A project without `.ginrc` behaves as today. Nothing forces an existing project to add one.
- A gin older than 3.1.0 does not read `.ginrc`. The pin protects members from 3.1.0 on; an older gin still fails only on a configuration it cannot read.
- `gin --version` changes from `gin 3.0` to `gin 3.1.0`, and gin-qa and gin-orchestrator jump to 3.1.0. A script that parses those outputs must expect three parts.
- The launcher version of the installers becomes the full release version. An install over an older launcher must keep working and must not leave the old CLI linked.
- The session-start hook never fails a session: it exits 0 in every case, and without `gin` on PATH it does nothing.
- `gin-qa` reaches a project through `gin`, so it shows gin's refusal message.
- The release workflow fails on a tag whose changelog section is missing. That is intended.
- Pushing the tag publishes a GitHub release and deploys the site; it needs the user's approval each time.

## Testing

- Version unity: one test over every location of R1; the bump script on a copy of the tree (valid value, invalid value).
- Comparison and refusal through the CLI: each row of R5, the commands that are never refused, `gin setup` under a newer major version, and an invalid `.ginrc`.
- `gin setup init`, `update`, and `doctor` for `.ginrc`.
- `gin version` in text and JSON, and `--hook`: silent when compatible or without `.ginrc`, one line when incompatible or invalid, exit 0 always.
- The Claude hook: the hooks file the installers generate for Claude Code has the session-start hook, the files for other harnesses do not, and the install smoke tests still pass.
- The release-notes script: a present section, a missing one.
- Docs: `gin docs check` on every changed page, the README map test, and the style rules for the two new pages. The project steps of the upgrade guide are run once against a copy of a 3.0 project.
- The full suite runs once, at ship (`project.run_at: push`).

## Open Technical Questions

# Upkeep for one maintainer

Epic: gin-workflow-upkeep
Kind: technical
Points: 5 (one watch script with its surface list and tests, one new `gin hooks` action, a rewritten release section, one guide in two languages; same size as gin-workflow-05e5 = 5)
Status: confirmed by the user on 2026-11-27.

## Goal and scope

gin-workflow has one maintainer, and two upstream projects change under it every week. Claude Code 2.1.330 reserved the `ship` command name, and Beads 1.4.0 (release candidates since 2026-11-20) migrates its database one way. Both were found by chance. The release procedure lives in four places that disagree: `docs/contributing.md`, `.planning/knowledge/release-versioning.md`, and two memory notes of the maintainer. A project that stops using gin has no page that says what keeps working, and the git hooks gin installs block every commit and push once the `gin` command is gone.

This epic gives the maintainer a weekly upstream check, one written release procedure, and a guide for leaving gin.

In scope:

- `scripts/upstream_watch.py` and its surface list `scripts/upstream_surfaces.json`, run weekly by cron on the maintainer's machine.
- `gin hooks uninstall [--all-repos]`.
- The Releasing section of `docs/contributing.md`, rewritten as the one release procedure.
- `docs/guides/leaving-gin.md` and `docs/guides/leaving-gin.vi.md`, linked from `mkdocs.yml` and `README.md`.
- Tests for the script and the new action; `docs/reference/cli.md` for the new action.

Out of scope:

- Freezing or removing any mode or feature.
- Acting on what the check finds: each finding is a bead of its own work.
- A Claude Code cloud scheduled task: it runs on a fresh clone and cannot reach the Beads database on the maintainer's machine.
- The other harness builds, which the roadmap leaves as they are.
- The marketplace install problems found during this discuss: bead `gin-workflow-6ujv`.

Assumptions:

- The maintainer's machine is on at the scheduled time. A week whose run did not happen shows in the cron log; the next run reads everything since the last version it read, so nothing is skipped.
- Beads release candidates count: Beads 1.4.0 is breaking and shipped as release candidates first. They are marked as such in the bead.
- `.agent-workflow/runtime/` is git-ignored and local, so the last versions read are local to the machine that runs the check.
- The check reads two public URLs without a token: `https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md` and `https://api.github.com/repos/gastownhall/beads/releases`. One unauthenticated call per week is far below GitHub's limit of 60 per hour.
- In team mode nothing changes for members: the check and the release procedure are the maintainer's. The guide covers the files `gin team init` writes, and `gin hooks uninstall` leaves the team `commit-msg` hook alone, because that hook needs no `gin`.

## Approach

### Upstream check

`scripts/upstream_watch.py` lives in the repository's `scripts/`, next to `bump_version.py`, and is not part of the plugin. It uses the Python standard library only.

1. It reads the Claude Code changelog and splits it on `## <version>` headings, newest first. It reads the Beads releases (tag, name, body, `prerelease`) from the GitHub releases API.
2. It takes the entries newer than the last version it read of each source, from `.agent-workflow/runtime/upstream-watch.json` in the main checkout. Without that file it records the newest version of each source as the baseline and files nothing.
3. It matches each changelog line and each release-note line against `scripts/upstream_surfaces.json`: per source, named groups of case-insensitive keywords for the surfaces gin uses. Claude Code groups cover skill and agent frontmatter, hook events, plugin manifests and marketplaces, command names that can collide, environment variables, the `Agent` and `Skill` tools, `/goal`, worktrees, and permission modes. The Beads group covers each `bd` subcommand and flag gin calls and the JSON fields it reads.
4. With one or more matching lines, it files one bead through `gin task create --type task -l upstream`. The title names the version ranges read. The description lists each matching line under its source and version, with the groups it matched. A Beads release candidate is marked `(release candidate)`.
5. It writes the newest versions read into the state file only after the bead is filed, or when nothing matched.
6. When a source cannot be read or parsed, it files one bead labelled `upstream` that names the source and the cause, keeps the state of that source, and exits 1. The next run reads the same range again.
7. `--dry-run` prints what it would file and writes nothing.

The runbook gives the cron line, Monday 08:17 local time, with output appended to `~/.local/state/gin/upstream-watch.log`. The maintainer adds it with `crontab -e`.

### `gin hooks uninstall`

`gin hooks uninstall [--repository PATH] [--all-repos]` removes the `pre-commit` and `pre-push` hooks of the active hooks directory whose content is exactly what `gin hooks install` writes, recognised as `install` already does (`_ours`, `workflow_core/hooks.py:39`). A hook that chains `gin hooks run` inside other content is left in place, and the command prints the line to remove. Any other hook is left alone. It never touches `core.sshCommand` or the team `commit-msg` hook. The output is JSON like `install`: each hook as `removed`, `chained`, `absent`, or `foreign`. `--all-repos` applies it to each cloned repository of a workspace, as `install --all-repos` does.

### Release procedure

The Releasing section of `docs/contributing.md` becomes the one procedure, in order: bump the version; write the changelog section; raise `.ginrc` when members must update; run the suite with `bd` off `PATH`, because the release runner has no `bd`; merge and push with approval; tag and push the tag; check the release and Pages runs and rerun a failed upload with `gh run rerun <id> --failed`; reinstall. A one-time setup paragraph says that the `github-pages` environment must allow `v*` tags, a repository setting the maintainer makes once (Settings, Environments, `github-pages`, deployment branches and tags). `.planning/knowledge/release-versioning.md` then points to it instead of restating it.

### Guide for leaving gin

`docs/guides/leaving-gin.md` opens with the one command that unblocks commits and pushes (`gin hooks uninstall`, or `--all-repos` in a workspace). Then it lists each thing gin leaves in a project and in the maintainer's home, what keeps working without gin, what stops, and how to remove it:

- the git hooks;
- the block in `AGENTS.md` and the `@AGENTS.md` line in `CLAUDE.md`;
- `.agent-workflow/` and `.ginrc`;
- `.planning/` and the review checkpoint refs `refs/gin/review/<bead>`;
- worktrees under `.planning/worktrees/`;
- Beads and the gate metadata on beads;
- in team mode, CODEOWNERS, the pull request template, `.githooks/commit-msg`, and the CI job;
- the plugin registrations per harness, where `./install.sh --uninstall` leaves the Claude Code, Codex, and Antigravity registrations for manual removal.

The Vietnamese twin follows the same structure.

## Risks and rollback

- Keyword matching gives false positives and misses entries that name a surface differently. The digest bead makes false positives cheap to close, and the surface list is a file the maintainer edits. A week with no bead means no matching line, not that nothing changed.
- GitHub may change the raw URL or the API, or rate-limit an unauthenticated call. Each failure files a bead, so the check does not go silent.
- `gin hooks uninstall` deletes files in `.git/hooks` or the `core.hooksPath` directory. It deletes only content that `install` wrote, so a user hook is never removed.
- The Pages fix is a repository setting outside the code. Until the maintainer makes it, the runbook's rerun step still applies.
- Rollback: revert the commits and delete the cron line. The state file and the beads filed stay and are harmless.

## Testing

- `tests/test_upstream_watch.py` (no network: the fetch functions take a fixture text or JSON):
  - the first run records the baseline and files nothing;
  - a later run files one bead listing only the matching lines newer than the state, with their versions and groups;
  - a Beads release candidate is marked;
  - no matching line files nothing and advances the state;
  - a source that fails files a bead naming it, keeps its state, and exits 1;
  - `--dry-run` files and writes nothing;
  - `scripts/upstream_surfaces.json` names every `bd` subcommand that `workflow_core` calls, so a new call without a keyword fails the test.
- `tests/workflow_core/test_hooks.py`:
  - `uninstall` removes both hooks that `install` wrote and reports `removed`;
  - it leaves a chained hook and reports the line;
  - it leaves a foreign hook unchanged;
  - it reports `absent` when no hook exists;
  - `--all-repos` covers each cloned repository of a workspace.
- The docs tests (coverage, style, mkdocs strict build) pass with the new guide and its twin.
- The full suite runs once before the push (`verify.run_at: push`).

## Open Technical Questions

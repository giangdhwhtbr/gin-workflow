# Upgrading to 3.1

Version 3.1 is the baseline for one number across the whole set: gin, gin-qa, gin-orchestrator, and gin-ba are all 3.1.0. It is also the first version that reads `.ginrc`, the file that pins the lowest gin version a project needs. The full list of changes is in the [changelog](../changelog.md#310-2026-11-15).

A team upgrades in this order, and the order matters:

1. Every member updates gin on their machine.
2. Only then does the lead run `gin setup update --approve` in the project and commit the result.
3. From then on, a member whose gin is older than the pin is refused.

Gin 3.0 rejects a configuration at schema 2.10 (`configuration validation failed at schema_version: '2.10' is not one of [...]`) and does not read `.ginrc`. A lead who runs step 2 first locks out every member who is still on 3.0.

## Update a machine

Update gin on each machine, whichever harness you use. Run one of these two routes.

From a clone of this repository:

```bash
git pull
./install.sh --platform all
```

Or with the launcher, which clones `master` and runs `install.sh`:

```bash
curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- --platform all
```

The default run updates gin and refreshes the add-ons already installed: gin-qa when the installer installed its launcher, and gin-ba when `~/.claude/skills/gin-ba` exists. `--plugin all` installs gin and every add-on. `--plugin gin-qa` or `--plugin gin-ba` installs only that add-on and does not update gin, so run it after the default run. On Windows, run `install.ps1` as [the Windows guide](windows.md) describes.

A plugin from a marketplace is updated through its harness, and the marketplace install does not install the CLIs, so run the installer as well. On Claude Code, run `claude plugin update gin@gin-workflow-marketplace` and restart Claude Code. Codex has no command that updates a plugin in place; `codex plugin marketplace upgrade` refreshes the marketplace, and the installer updates the CLIs.

Check the result:

```bash
gin version
```

It prints the installed version, the pin of the project you are in, `compatible: yes` or `no`, and the version of gin-qa when it finds it. `gin --version` prints `gin 3.1.0`. `gin setup doctor` also reports a gin-qa whose version differs from gin's; reinstall that add-on with `./install.sh --plugin <name>`.

## Update a project

The lead does this once per project, after every member has updated gin:

1. Run `gin setup update` to read the proposal, then `gin setup update --approve`. It migrates the configuration to schema 2.11 and writes `.ginrc` with the installed version. It writes `.ginrc` even when no migration is due.
2. Commit `.agent-workflow/config.yaml` and `.ginrc`, and tell the team that the pull request needs the gin version written in `.ginrc`. The pin is the lead's installed version, and a later `gin setup update --approve` raises it to the version installed then.

In a workspace, do this only in the parent. The children and the worktrees find the parent's `.ginrc`. The [configuration reference](../reference/config.md#ginrc) gives the file format and where gin looks for it. A project without `.ginrc` is not checked at all, and `gin setup doctor` reports it.

## A member who is refused

Suppose a project pins `3.2.0` and your gin is 3.1.0. Every `gin` command that reads the project then stops and exits 2, `gin hooks run` included. Your git commit and push hooks therefore fail in that project until you update gin. A member still on 3.0 does not get this message. Gin 3.0 ignores `.ginrc` and fails on the configuration schema instead, which is why every member updates first. A member who sees `configuration validation failed at schema_version: '2.10'` updates the machine as described above. The refusal message reads:

```text
error: gin 3.1.0 is older than this project needs (3.2.0, /path/to/project/.ginrc); update gin: https://giangdhwhtbr.github.io/gin-workflow/guides/upgrading/
```

Two other messages exist. A gin of a newer major version than the pin says `upgrade the project with gin setup update --approve`, and `gin setup` commands still run so the lead can do it. A `.ginrc` that is not one version `X.Y.Z` says `<path> must hold one version X.Y.Z`. The [CLI reference](../reference/cli.md) lists all three.

On Claude Code, the hooks file that `install.sh` or `install.ps1` generates also runs `gin version --hook` at the start of a session. The agent then sees the same message followed by `Tell the user before any other work.` A Claude Code plugin installed only from the marketplace has no such hook, and neither do the other harnesses; they show the refusal at the first `gin` command.

To clear the refusal, [update your machine](#update-a-machine), then run `gin version` and check for `compatible: yes`.

## What changes at 3.1

The changelog lists everything in its [upgrade notes](../changelog.md#upgrade-notes). Act on these points:

- gin older than 3.1 ignores `.ginrc`, so every member must reach 3.1 once before the pin protects anyone.
- The configuration moves to schema 2.10, which drops the `notifications` key.
- The other points, such as the `verify.run_at` default, team settings, and add-on reinstalls, are in the [upgrade notes](../changelog.md#upgrade-notes).

## What changes at 3.3

gin 3.3 runs every stage in the harness you opened and removes the gin-orchestrator extension. Every `./install.sh` run removes the launcher it installed and the plugin folders of the selected harnesses. It keeps a launcher it did not install, with a warning, and a dry run removes nothing. The config keys `orchestrator`, `provider_mode`, and `routing.review.independence` go with it, and so do `gin setup models`, `--probe`, and `--provider`. The lead runs this once per project, after every member has updated gin:

```bash
gin setup update --to-version 2.11 --approve
```

A project that skips the update keeps working, and `gin state` warns once. The update backs up and deletes `.agent-workflow/orchestrator.local.yaml`, and `gin setup rollback --backup <dir>` restores it. Review is always a fresh session or subagent of the same harness. What runs where depends on the harness.

| Step | Claude Code, Antigravity | Codex, OpenCode, Copilot |
|---|---|---|
| Execute a track | native `gin:developer` subagent | the session implements the track and notes `in_session` on the bead |
| Review | native `gin:code-reviewer` subagent | stops for you to open a fresh session; self-review only with `allow_self_review_fallback` |
| Research in `discuss` and `plan`; scouts, writers, and reviewers in `tech-doc` | native subagent | one after another in the session |

The changelog lists the rest in its [upgrade notes](../changelog.md#330-2026-11-21). [Providers](../concepts/providers.md) describes the roles, the models, and the review.

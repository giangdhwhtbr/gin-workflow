# Gin Workflow (`gin-workflow`)

A workflow plugin for **Claude Code**, **Codex CLI**, **Antigravity CLI**, and **OpenCode** that takes a change from requirement to merge through recorded gates: discuss → plan → orchestrate → execute → verify → ship. Tasks are tracked in local Markdown files or, optionally, in Beads. Tracks get an independent review at `standard` and `strict` rigor, and nothing is merged without your approval. A `/quick` path handles small changes.

## Documentation

| Start here | |
|---|---|
| [Getting started](docs/getting-started.md) | one feature from idea to merge with Claude Code |
| Starters | [greenfield](docs/starters/greenfield.md), [brownfield & modernization](docs/starters/brownfield-modernize.md), [brownfield walkthrough](docs/starters/brownfield-walkthrough.md) |
| [Architecture](docs/concepts/architecture.md) | how the pieces fit, with flow diagrams |
| Concepts | [lifecycle and gates](docs/concepts/lifecycle.md), [state model](docs/concepts/state-model.md), [providers and routing](docs/concepts/providers.md) |
| [Team roles](docs/roles.md) | who owns what in a team, and what each role reads |
| Guides | [use cases](docs/guides/use-cases.md), [customizing templates](docs/guides/customizing-templates.md), [recommended tools](docs/guides/recommended-tools.md), [Windows](docs/guides/windows.md), [rule packs](docs/guides/rules.md), [SDD living specs](docs/guides/sdd.md), [team mode](docs/guides/team.md), [QA add-on](docs/guides/qa.md), [AI usage report](docs/guides/usage-report.md) |
| Orchestrator | [worker harnesses (gin-orchestrator)](docs/orchestrator/README.md), [routing and configuration](docs/orchestrator/routing.md) |
| Reference | [skills](docs/reference/skills.md), [CLI](docs/reference/cli.md), [configuration](docs/reference/config.md), [troubleshooting](docs/reference/troubleshooting.md), [orchestrator contract](docs/reference/orchestrator-contract.md), [upgrading to 2.0](docs/reference/upgrade-2.0.md), [upgrading to 2.1](docs/reference/upgrade-2.1.md), [ADLC deck](docs/presentations/adlc.html) ([PPTX](docs/presentations/adlc.pptx)), [Modernization deck](docs/presentations/brownfield-modernization.html) ([PPTX](docs/presentations/brownfield-modernization.pptx), [script](docs/presentations/brownfield-modernization-script.md)) |
| [Contributing](docs/contributing.md) | build, test, release |

## Installation

### Dependencies

| Need | For | Install |
|---|---|---|
| Python 3.11 or later with PyYAML | the `gin-workflow` CLI | `python3 -m pip install PyYAML` |
| git | branches, worktrees, review checkpoints | your package manager |
| jq, optional | the safety hook's JSON parsing; without it the hook uses `python3` | `brew install jq`, `apt install jq`, or `winget install jqlang.jq` |
| Git Bash (Windows only) | the `.sh` hook scripts | [Git for Windows](https://gitforwindows.org/) or `winget install Git.Git` |
| [Beads](https://github.com/gastownhall/beads) (`bd`), optional | task tracking; without it, `/setup` offers local Markdown tasks (`providers.task_tracking: markdown`) | `brew install beads`, `npm install -g @beads/bd`, or `curl -fsSL https://raw.githubusercontent.com/gastownhall/beads/main/scripts/install.sh \| bash` |
| A harness | running the skills | Claude Code, Codex CLI, Antigravity CLI (`agy`), or OpenCode |

Optional, per feature: [CodeGraph](docs/guides/recommended-tools.md#codegraph) for faster code lookup by agents; [gin-orchestrator](docs/orchestrator/README.md) with `codex`, `agy`, or `opencode` next to your main harness for worker routing; `gh` or `glab` for [team mode](docs/guides/team.md); Node with `@playwright/test` 1.49 or later for [QA end-to-end specs](docs/guides/qa.md). Install and configuration: [recommended tools](docs/guides/recommended-tools.md).

Then, in each repository, run `/gin-workflow:setup` once ([getting started](docs/getting-started.md)); if you chose Beads, run `bd init` first.

### The plugin

Skills call the `gin-workflow` CLI, so it must be on `PATH` (`~/.local/bin`). The installer links it; a marketplace install alone does not ([fix](docs/reference/troubleshooting.md#gin-workflow-command-not-found-after-a-marketplace-install)).

**Any harness, with the launcher** (clones this repository and runs `install.sh`):

```bash
curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- --platform all
```

Use `--platform claude`, `codex`, `antigravity`, `opencode`, or `copilot` for one harness, and `--plugin all` to add every extension. On Windows use `install.ps1` ([contributing](docs/contributing.md#windows-powershell-7)).

**Claude Code marketplace:**

```bash
claude plugin marketplace add giangdhwhtbr/gin-workflow
claude plugin install gin-workflow@gin-workflow-marketplace
```

**Codex marketplace:**

```bash
codex plugin marketplace add giangdhwhtbr/gin-workflow --ref master
codex plugin add gin-workflow@gin-workflow-marketplace
```

Antigravity has no git-based install; use the installer above. OpenCode has no plugin marketplace either; the installer writes the skill bundle to `~/.config/opencode/skills/gin-workflow`, where OpenCode discovers it automatically. In OpenCode, invoke a skill with `@<skill>` (for example `@setup` or `@workflow`); the lifecycle stages still run through the `gin-workflow` CLI. The usage-report skill is `@gin-workflow-report` in OpenCode, so OpenCode's own built-in `report` skill is left intact.

GitHub Copilot CLI: `--platform copilot` builds `dist/copilot/<plugin>` and registers it with `copilot plugin install`. Copilot loads the skills and the safety hook, but it cannot be the configured harness; workers and reviews still need `claude`, `codex`, `agy`, or `opencode` (workers also need gin-orchestrator). The hook needs `bash` and finds its script only after a local install ([troubleshooting](docs/reference/troubleshooting.md#gin-workflow-pathscriptssafety-checksh-not-found-hook-skipped)).

## Extensions

gin-workflow works alone. Two add-ons install from the same clone:

| Extension | Install | Adds |
|---|---|---|
| gin-qa | `./install.sh --plugin gin-qa` | [QA cases and end-to-end specs](docs/guides/qa.md) |
| gin-orchestrator | `./install.sh --plugin gin-orchestrator` (installs gin-workflow too) | [worker harnesses](docs/orchestrator/README.md): route tracks and reviews to other harnesses |

## Quickstart

```text
/gin-workflow:setup                         once per repository
/gin-workflow:discuss <what you want>       confirm the design → spec
/gin-workflow:plan <feature>                approve the plan → tracks
/gin-workflow:orchestrate <feature>         tasks, routes, worktree
/gin-workflow:execute                       one track: test first, review, close
/gin-workflow:ship                          merge, PR, keep, or discard
```

`/gin-workflow:workflow` runs whichever stage comes next; `/gin-workflow:quick <change>` handles a small change; `/gin-workflow:progress` shows status; `/gin-workflow:report` shows AI cost and rework. Codex uses `$gin-workflow:<skill>`.

## Skills

| Skill | Purpose |
|---|---|
| `setup` | configure a repository once |
| `discuss`, `plan`, `orchestrate`, `execute`, `ship` | the lifecycle stages |
| `review` | independent review in the review ledger |
| `workflow`, `progress` | route to the next stage; show status |
| `quick` | small change without plan or tasks |
| `report` | AI usage per bead or epic |

All skills, including the support skills and the `gin-qa` add-on: [skills reference](docs/reference/skills.md).

## License

[MIT](LICENSE).

## Credits

The `lean` rule pack's ideas come from [ponytail](https://github.com/dietrichgebert/ponytail) (MIT).

The lifecycle skills (discuss, plan, debugging, worktrees, review response, parallel agents) started as forks of [superpowers](https://github.com/obra/superpowers) (MIT).

The documentation style rules come from [technical-writer](https://github.com/riekelt/technical-writer) (MIT).

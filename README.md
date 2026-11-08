# Gin Workflow (gin-workflow)

A workflow plugin for **Claude Code**, **Codex CLI**, **Antigravity CLI**, **OpenCode**, and **GitHub Copilot CLI** that takes a change from requirement to merge through recorded gates: discuss → plan → orchestrate → execute → ship. Tasks are tracked in local Markdown files or, optionally, in Beads. Tracks get an independent review at `standard` and `strict` rigor, and nothing is merged without your approval. A `/quick` path handles small changes.

## Documentation

Read it on the [documentation site](https://giangdhwhtbr.github.io/gin-workflow/) in English or Vietnamese, or start from the [home page](docs/index.md) in this repository:

| Start here | |
|---|---|
| [Getting started](docs/getting-started.md) | one feature from idea to merge with Claude Code |
| Starters | [greenfield](docs/starters/greenfield.md), [brownfield](docs/starters/brownfield.md) |
| [Architecture](docs/concepts/architecture.md) | how the pieces fit, with flow diagrams |
| Concepts | [lifecycle and gates](docs/concepts/lifecycle.md), [state model](docs/concepts/state-model.md), [providers and routing](docs/concepts/providers.md) |
| [Team roles](docs/roles.md) | who owns what in a team, and what each role reads |
| Guides | [use cases](docs/guides/use-cases.md), [using AI effectively](docs/guides/ai-strategy.md), [working with Claude Code](docs/guides/claude-workflow.md), [customizing templates](docs/guides/customizing-templates.md), [recommended tools](docs/guides/recommended-tools.md), [Windows](docs/guides/windows.md), [rule packs](docs/guides/rules.md), [SDD living specs](docs/guides/sdd.md), [team mode](docs/guides/team.md), [team git agreement](docs/guides/git-flow.md), [workspace](docs/guides/workspace.md), [QA add-on](docs/guides/qa.md), [business analyst](docs/guides/ba.md), [AI usage report](docs/guides/usage-report.md) |
| Orchestrator | [worker harnesses (gin-orchestrator)](docs/orchestrator/README.md), [routing and configuration](docs/orchestrator/routing.md) |
| Reference | [skills](docs/reference/skills.md), [CLI](docs/reference/cli.md), [configuration](docs/reference/config.md), [troubleshooting](docs/reference/troubleshooting.md), [orchestrator contract](docs/reference/orchestrator-contract.md) |
| [Contributing](docs/contributing.md) | build, test, release |

## Installation

### Dependencies

| Need | For | Install |
|---|---|---|
| Python 3.11 or later with PyYAML | the `gin` CLI | `python3 -m pip install PyYAML` |
| git | branches, worktrees, review checkpoints | your package manager |
| [Beads](https://github.com/gastownhall/beads) (`bd`), optional | task tracking; without it, `/setup` offers local Markdown tasks (`providers.task_tracking: markdown`) | `brew install beads`, `npm install -g @beads/bd`, or `curl -fsSL https://raw.githubusercontent.com/gastownhall/beads/main/scripts/install.sh \| bash` |
| A harness | running the skills | Claude Code, Codex CLI, Antigravity CLI (`agy`), OpenCode, or GitHub Copilot CLI (`copilot`) |

Optional, per feature: [CodeGraph](docs/guides/recommended-tools.md#codegraph) for faster code lookup by agents; [gin-orchestrator](docs/orchestrator/README.md) with `codex`, `agy`, `opencode`, or `copilot` next to your main harness for worker routing; `gh` or `glab` for [team mode](docs/guides/team.md); Node with `@playwright/test` 1.49 or later for [QA end-to-end specs](docs/guides/qa.md). Install and configuration: [recommended tools](docs/guides/recommended-tools.md).

Then, in each repository, run `/gin:setup` once ([getting started](docs/getting-started.md)); if you chose Beads, run `bd init` first.

### The plugin

Skills call the `gin` CLI, so it must be on `PATH` (`~/.local/bin`). The installer links it and adds `~/.local/bin` to your shell startup file (`--no-modify-path` to opt out); a marketplace install alone does not ([fix](docs/reference/troubleshooting.md#gin-command-not-found-after-a-marketplace-install)).

Upgrading from 2.x: see [Upgrading from gin-workflow 2.x](docs/reference/troubleshooting.md#upgrading-from-gin-workflow-2x).

**Any harness, with the launcher** (clones this repository and runs `install.sh`):

```bash
curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- --platform all
```

Use `--platform claude`, `codex`, `antigravity`, `opencode`, or `copilot` for one harness, and `--plugin all` to add every extension. On Windows use `install.ps1` ([contributing](docs/contributing.md#windows-powershell-7)).

**Claude Code marketplace:**

```bash
claude plugin marketplace add giangdhwhtbr/gin-workflow
claude plugin install gin@gin-workflow-marketplace
```

**Codex marketplace:**

```bash
codex plugin marketplace add giangdhwhtbr/gin-workflow --ref master
codex plugin add gin@gin-workflow-marketplace
```

Antigravity has no git-based install; use the installer above. OpenCode has no plugin marketplace either; the installer writes the skill bundle to `~/.config/opencode/skills/gin`, where OpenCode discovers it automatically. In OpenCode, invoke a skill with `@<skill>` (for example `@setup` or `@workflow`); the lifecycle stages still run through the `gin` CLI. Eight generic skills carry a `gin-` prefix in OpenCode (`@gin-learn`, `@gin-sdd`, `@gin-team`, `@gin-worktrees`, `@gin-debugging`, `@gin-review-response`, `@gin-parallel-agents`, `@gin-report`), so OpenCode's own built-in `report` skill is left intact.

GitHub Copilot CLI: `--platform copilot` builds `dist/copilot/<plugin>` and registers it with `copilot plugin install`. Copilot loads the skills and the safety hook and can be the main harness; `gin setup` detects it from `.github/agents`. gin-orchestrator can also route workers and reviews to it. The hook runs through Copilot's `bash` hook type and finds its script only after a local install ([troubleshooting](docs/reference/troubleshooting.md#gin-pathscriptssafety_checkpy-not-found-hook-skipped)).

## Extensions

gin-workflow works alone. Three add-ons install from the same clone:

| Extension | Install | Adds |
|---|---|---|
| gin-qa | `./install.sh --plugin gin-qa` | [QA cases and end-to-end specs](docs/guides/qa.md) |
| gin-ba | `./install.sh --plugin gin-ba` | [BA mockups and legacy descriptions](docs/guides/ba.md) for spec inputs |
| gin-orchestrator | `./install.sh --plugin gin-orchestrator` (installs gin-workflow too) | [worker harnesses](docs/orchestrator/README.md): route tracks and reviews to other harnesses |

## Quickstart

```text
/gin:setup                         once per repository
/gin:discuss <what you want>       confirm the design → spec
/gin:plan <feature>                approve the plan → tracks
/gin:orchestrate <feature>         tasks, routes, worktree
/gin:execute                       one track: test first, review, close
/gin:ship                          merge, PR, keep, or discard
```

`/gin:workflow` runs whichever stage comes next; `/gin:quick <change>` handles a small change; `/gin:progress` shows status; `/gin:report` shows AI cost and rework. Codex uses `$gin:<skill>`.

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

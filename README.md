# Gin Workflow (`gin-workflow`)

A workflow plugin for **Claude Code**, **Codex CLI**, and **Antigravity CLI** that takes a change from requirement to merge through recorded gates: discuss → plan → orchestrate → execute → verify → ship. Beads tracks the work, every track gets an independent review, and nothing is merged without your approval. A `/quick` path handles small changes.

## Documentation

| Start here | |
|---|---|
| [Getting started](docs/getting-started.md) | one feature from idea to merge ([tiếng Việt](docs/huong-dan.md)) |
| [Architecture](docs/concepts/architecture.md) | how the pieces fit, with flow diagrams |
| Concepts | [lifecycle and gates](docs/concepts/lifecycle.md), [state model](docs/concepts/state-model.md), [providers and routing](docs/concepts/providers.md) |
| Guides | [use cases](docs/guides/use-cases.md), [recommended tools](docs/guides/recommended-tools.md), [rule packs](docs/guides/rules.md), [SDD living specs](docs/guides/sdd.md), [team mode](docs/guides/team.md), [QA add-on](docs/guides/qa.md), [AI usage report](docs/guides/usage-report.md) |
| Reference | [skills](docs/reference/skills.md), [CLI](docs/reference/cli.md), [configuration](docs/reference/config.md), [troubleshooting](docs/reference/troubleshooting.md) |
| [Contributing](docs/contributing.md) | build, test, release |

## Installation

### 1. Dependencies

| Need | For | Install |
|---|---|---|
| Python 3 with PyYAML | the `gin-workflow` CLI | `python3 -m pip install PyYAML` |
| git | branches, worktrees, review checkpoints | your package manager |
| [Beads](https://github.com/gastownhall/beads) (`bd`) | task tracking | `brew install beads`, `npm install -g @beads/bd`, or `curl -fsSL https://raw.githubusercontent.com/gastownhall/beads/main/scripts/install.sh \| bash` |
| A harness | running the skills | Claude Code, Codex CLI, or Antigravity CLI (`agy`) |

Optional, per feature: [CodeGraph](docs/guides/recommended-tools.md#codegraph) for faster code lookup by agents; `codex` or `agy` next to your main harness for multi-provider routing; `gh` or `glab` for [team mode](docs/guides/team.md); Node with `@playwright/test` 1.49 or later for [QA end-to-end specs](docs/guides/qa.md). Install and configuration: [recommended tools](docs/guides/recommended-tools.md).

Then, in each repository: `bd init` once, and `/gin-workflow:setup` once ([getting started](docs/getting-started.md)).

### 2. The plugin

Skills call the `gin-workflow` CLI, so it must be on `PATH` (`~/.local/bin`). The installer links it; a marketplace install alone does not ([fix](docs/reference/troubleshooting.md#gin-workflow-is-not-on-path-after-a-marketplace-install)).

**Any harness, with the launcher** (clones this repository and runs `install.sh`):

```bash
curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- --platform all
```

Use `--platform claude`, `codex`, or `antigravity` for one harness, and `--plugin all` to add the QA add-on. On Windows use `install.ps1` ([contributing](docs/contributing.md#windows-powershell-7)).

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

Antigravity has no git-based install; use the installer above.

## Quickstart

```text
/gin-workflow:setup                         once per repository
/gin-workflow:discuss <what you want>       confirm the design → spec
/gin-workflow:plan <feature>                approve the plan → tracks
/gin-workflow:orchestrate <feature>         beads, routes, worktree
/gin-workflow:execute                       one track: test first, review, close
/gin-workflow:verify                        fresh evidence for every claim
/gin-workflow:ship                          merge, PR, keep, or discard
```

`/gin-workflow:workflow` runs whichever stage comes next; `/gin-workflow:quick <change>` handles a small change; `/gin-workflow:progress` shows status; `/gin-workflow:report` shows AI cost and rework. Codex uses `$gin-workflow:<skill>`.

## Skills

| Skill | Purpose |
|---|---|
| `setup` | configure a repository once |
| `discuss`, `plan`, `orchestrate`, `execute`, `verify`, `ship` | the lifecycle stages |
| `review` | independent review in the review ledger |
| `workflow`, `progress` | route to the next stage; show status |
| `quick` | small change without plan or beads |
| `report` | AI usage per bead or epic |

All skills, including the support skills and the `gin-qa` add-on: [skills reference](docs/reference/skills.md).

## Credits

The `lean` rule pack's ideas come from [ponytail](https://github.com/dietrichgebert/ponytail) (MIT).

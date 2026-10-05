# Getting Started

This walks one small feature from idea to merge. It assumes a git repository and one harness (Claude Code, Codex, or Antigravity). Commands are shown as Claude Code slash commands; Codex uses `$gin-workflow:<skill>`.

## 1. Prerequisites

- Python 3 with PyYAML, git, and [Beads](https://github.com/gastownhall/beads) (`bd`), installed as listed in [Installation](../README.md#1-dependencies); Beads initialized in the repository (`bd init`).
- The plugin and its `gin-workflow` launcher installed ([Installation](../README.md#installation)). Check with `gin-workflow --version`.

## 2. Set up the repository once

```
/gin-workflow:setup
```

Setup detects the project (stage, shape, stack, verify commands) and asks one question at a time: project type, rigor (`easy`, `standard`, `strict`), provider mode (`single` for one harness, `multi` to route work to other CLIs), and the lint, typecheck, test, build, and e2e commands. It shows the proposed configuration, waits for your approval, then writes `.agent-workflow/config.yaml` (commit it) and the gitignored machine-local files. See [Configuration](reference/config.md).

## 3. Discuss

```
/gin-workflow:discuss Add a "last login" column to the admin user list
```

The agent reads the relevant code, asks clarifying questions one at a time, proposes two or three approaches with a recommendation, and presents the design in sections for you to confirm. It writes the spec to `.planning/specs/<date>-<topic>-design.md` on a feature branch and asks you to review it. When you confirm, it records `requirement-confirmed`. Nothing is planned or coded before that.

## 4. Plan

```
/gin-workflow:plan last-login-column
```

The plan in `.planning/plans/` splits the work into tracks: each with its files, interfaces, test-first steps, a provider role, and a reasoning tier. Review it; when you approve, the agent records `plan-approved`.

## 5. Orchestrate

```
/gin-workflow:orchestrate last-login-column
```

The agent resolves a provider route for every track, creates an epic and one bead per track with their dependencies, creates a worktree under `.planning/worktrees/`, checks that the tests pass there, and records `orchestration-ready`.

## 6. Execute

```
/gin-workflow:execute
```

For each ready track the agent claims the bead, writes a failing test, implements until it passes, and asks an independent reviewer (another provider, or a fresh session) to review the diff in the review ledger. Findings are fixed or answered; once approved, the track's AI usage is collected and the bead closes, which makes the next track ready. Run it again for the next track. The branch is pushed; nothing is merged.

## 7. Verify

```
/gin-workflow:verify
```

Fresh evidence only: every review ledger validates, the verify commands for your rigor pass, and every line of the spec and plan is checked against the code. Then `verification-passed` is recorded.

## 8. Ship

```
/gin-workflow:ship
```

Choose: merge locally, push and open a pull request, keep the branch, or discard. Merging or opening a pull request needs your explicit approval. After a merge the agent re-runs the tests, removes the worktree and branch, collects the epic's usage, closes the epic (which marks it shipped), and lists what is ready next.

## Shortcuts and status

- `/gin-workflow:workflow` reads the state and runs whichever stage comes next.
- `/gin-workflow:quick <change>` handles a small, low-risk change without spec, plan, or beads ([use cases](guides/use-cases.md#small-change)).
- `/gin-workflow:progress` shows ready, active, and blocked work; `gin-workflow state` explains a held workflow and its remedies.
- `/gin-workflow:report --epic <epic>` shows what the AI work cost per model and stage, next to review and rework signals ([usage report](guides/usage-report.md)).

## Next

- [Architecture](concepts/architecture.md): how the pieces fit, in diagrams.
- [Lifecycle](concepts/lifecycle.md): gates, waivers, verification, and handoff in detail.
- Optional features: [rule packs](guides/rules.md), [SDD living specs](guides/sdd.md), [team mode](guides/team.md), [QA add-on](guides/qa.md).
- [Skills](reference/skills.md) and [CLI](reference/cli.md) reference.

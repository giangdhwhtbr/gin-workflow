# Getting started

This guide takes one feature from idea to merge using Claude Code and `gin-workflow`.

Every change moves through recorded quality gates:
`discuss` → `plan` → `orchestrate` → `execute` → `ship`.

---

## Prerequisites

1. Python 3 (with PyYAML) and Git.
2. Claude Code and the `gin-workflow` plugin:
   ```bash
   curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- --platform claude
   ```
   On Windows PowerShell, see the [Windows guide](guides/windows.md) to use `install.ps1`.
3. Optional: [Beads](https://github.com/gastownhall/beads) (`bd`) for task tracking (`brew install beads` or `npm install -g @beads/bd`, then `bd init` in your repository). Without it, tasks are local Markdown files.
4. Optional: [recommended tools](guides/recommended-tools.md) such as CodeGraph, which gives agents faster code lookup.

---

## One-time setup

Run setup inside Claude Code to configure your project:

```text
/gin-workflow:setup
```

Setup asks one question at a time and generates `.agent-workflow/config.yaml`:
- Project type: stage and shape, detected from your repository.
- Rigor: setup suggests `standard` for an existing codebase (Git worktrees for parallel work and independent review) and `easy` for a new one; `strict` always uses a worktree and a review ledger.
- Verify commands: your lint, typecheck, test, build, and e2e commands (a new project is asked for its stack instead).
- Code index: for an existing codebase, an offer to run `codegraph init` when CodeGraph is installed.
- Task tracking: `markdown` (the default; local files under `.planning/tasks/`) or `beads` (needs `bd`).

Everything runs in the harness you opened (`provider_mode: single`). Worker harnesses are the optional [gin-orchestrator](orchestrator/README.md) extension.

Commit `.agent-workflow/config.yaml` to git.

---

## Feature workflow

### Discuss
```text
/gin-workflow:discuss Add an export-to-csv button on the user list
```
Claude reads the existing code, asks clarifying questions one at a time, proposes approaches, and writes a specification to `.planning/specs/<date>-<topic>-design.md` (or `docs/changes/` in SDD mode). Confirm the design to pass the `requirement_confirmed` gate.

### Plan
```text
/gin-workflow:plan export-csv-button
```
Claude breaks the confirmed spec into tracks in `.planning/plans/`, each with files, interfaces, and test-first steps. Approve the plan to pass the `plan_approved` gate.

### Orchestrate
```text
/gin-workflow:orchestrate export-csv-button
```
Claude creates an epic and task items in your task tracker (Markdown or Beads) and an isolated Git worktree. This passes the `orchestration_ready` gate.

### Execute
```text
/gin-workflow:execute
```
Claude claims the next ready track, writes a failing test first, implements until the tests pass, and runs an independent review in the review ledger. After approval the track closes. Repeat `/gin-workflow:execute` until all tracks are done.

Quality checks do not need a stage: `pre-commit` runs lint and typecheck, `pre-push` runs the tests (plus the build at `standard` and `strict`, and e2e at `strict`), and CI is the backstop (`gin-workflow hooks install`, see the [CLI reference](reference/cli.md#gin-workflow-hooks)).

### Ship
```text
/gin-workflow:ship
```
Claude offers four options: merge locally, push and open a pull request, keep the branch, or discard. After your approval it integrates the work, removes the worktree, and closes the epic (`shipped`). Ship runs no tests; the git hooks and CI do.

---

## Shortcuts

- `/gin-workflow:workflow`: detects the current state and runs the next stage.
- `/gin-workflow:quick <change>`: handles a small change (up to 5 files in one module by default) without specs or tasks.
- `/gin-workflow:progress`: shows active, ready, and blocked tasks.

---

## Starters and guides

- New project: the [greenfield starter](starters/greenfield.md).
- Legacy codebase: the [brownfield modernization starter](starters/brownfield-modernize.md).
- Team: [team roles](roles.md).
- Multi-harness worker routing: the [gin-orchestrator](orchestrator/README.md) extension.
- The lifecycle on slides: the [ADLC deck](presentations/adlc.html) ([PPTX](presentations/adlc.pptx)).

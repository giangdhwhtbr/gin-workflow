# Getting Started

This guide walks you through delivering a feature from initial idea to final merge using **Claude Code** and **`gin-workflow`**.

Every change moves through recorded quality gates:
**`discuss` → `plan` → `orchestrate` → `execute` → `ship`**.

---

## 1. Quick Prerequisites

1. **Python 3** (with PyYAML) and **Git**.
2. **Claude Code** and the `gin-workflow` plugin:
   ```bash
   curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- --platform claude
   ```
   *(On Windows PowerShell, see the [Windows Guide](guides/windows.md) to use `install.ps1`)*
3. Optional: [Beads](https://github.com/gastownhall/beads) (`bd`) for task tracking (`brew install beads` or `npm install -g @beads/bd`, then `bd init` in your repository). Without it, tasks are local Markdown files.
4. Optional: [recommended tools](guides/recommended-tools.md) such as CodeGraph, which gives agents faster code lookup.

---

## 2. One-Time Setup (`/setup`)

Run setup inside Claude Code to configure your project:

```text
/gin-workflow:setup
```

Setup asks simple questions to generate `.agent-workflow/config.yaml`:
- **Project type:** stage and shape, detected from your repository.
- **Rigor:** `standard` (recommended: Git worktrees for parallel work, independent review, and lint, typecheck, test, and build checks).
- **Verify commands:** Confirms your test and build commands.
- **Task tracking:** `markdown` (the default; local files under `.planning/tasks/`) or `beads` (needs `bd`).

Everything runs in the harness you opened (`provider_mode: single`). Worker harnesses are the optional [gin-orchestrator](orchestrator/README.md) extension.

Commit `.agent-workflow/config.yaml` to git.

---

## 3. The 6-Stage Feature Workflow

### Stage 1: Discuss
```text
/gin-workflow:discuss Add an export-to-csv button on the user list
```
Claude analyzes existing code, asks clarifying questions one at a time, proposes architectural approaches, and writes a specification to `.planning/specs/<date>-<topic>-design.md` (or `docs/changes/` in SDD mode). Confirm the design to pass the `requirement_confirmed` gate.

### Stage 2: Plan
```text
/gin-workflow:plan export-csv-button
```
Claude breaks the confirmed spec into implementation tracks in `.planning/plans/` (defining files, interfaces, and test-first steps). Review the plan and approve it to pass the `plan_approved` gate.

### Stage 3: Orchestrate
```text
/gin-workflow:orchestrate export-csv-button
```
Claude creates an epic and task items in your task tracker (Markdown or Beads), then creates an isolated Git worktree for clean implementation. Passes the `orchestration_ready` gate.

### Stage 4: Execute
```text
/gin-workflow:execute
```
Claude claims the next ready track, writes a failing test first, implements the solution until tests pass, and conducts an independent code review in the review ledger. Once approved, the track closes. Repeat `/gin-workflow:execute` until all tracks are done.

Quality checks do not need a stage: `pre-commit` runs lint and typecheck, `pre-push` runs the tests, and CI is the backstop (`gin-workflow hooks install`, see the [CLI reference](reference/cli.md#gin-workflow-hooks)).

### Stage 5: Ship
```text
/gin-workflow:ship
```
Claude offers four integration options: **Merge locally**, **Push & open Pull Request**, **Keep branch**, or **Discard**. After your approval, it integrates the work, re-tests on the merged result, removes the worktree, and closes the epic (`shipped`).

---

## 4. Helpful Shortcuts

- `/gin-workflow:workflow`: Automatically detects the current state and runs whichever stage is next.
- `/gin-workflow:quick <change>`: Fast-tracks small changes (up to 5 files in one module by default) without requiring specs or tasks.
- `/gin-workflow:progress`: Inspects active, ready, or blocked tasks.

---

## 5. Tailored Starters & Guides

- 🚀 **Starting a new project?** Read the [Greenfield Project Starter](starters/greenfield.md).
- 🔄 **Refactoring a legacy codebase?** Read the [Brownfield & Modernization Starter](starters/brownfield-modernize.md).
- 👥 **Working in a team?** Read the [Team Roles Guide](starters/team-roles.md) and individual role handbooks ([PM](guides/pm-guide.md), [BA](guides/ba-guide.md), [Dev](guides/dev-guide.md), [QA](guides/qa-guide.md)).
- ⚡ **Looking for multi-agent / multi-model routing?** Install the gin-orchestrator extension: see [Orchestrator](orchestrator/README.md).
- 🎞️ **Want the whole lifecycle on slides?** Open the [ADLC deck](presentations/adlc.html) ([PPTX](presentations/adlc.pptx)).

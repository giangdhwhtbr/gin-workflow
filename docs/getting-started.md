# Getting Started

This guide walks you through delivering a feature from initial idea to final merge using **Claude Code** and **`gin-workflow`**.

Every change moves through recorded quality gates:
**`discuss` → `plan` → `orchestrate` → `execute` → `verify` → `ship`**.

---

## 1. Quick Prerequisites

1. **Python 3** (with PyYAML) and **Git**.
2. **Beads (`bd`)** for durable task tracking:
   ```bash
   brew install beads       # or: npm install -g @beads/bd
   ```
3. **Claude Code** and the `gin-workflow` plugin:
   ```bash
   curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- --platform claude
   ```
4. Initialize Beads in your repository:
   ```bash
   bd init
   ```
5. Optional: [recommended tools](guides/recommended-tools.md) such as CodeGraph, which gives agents faster code lookup.

---

## 2. One-Time Setup (`/setup`)

Run setup inside Claude Code to configure your project:

```text
/gin-workflow:setup
```

Setup asks simple questions to generate `.agent-workflow/config.yaml`:
- **Rigor:** `standard` (recommended: isolates tracks in Git worktrees and checks lint, typecheck, test, and build).
- **Provider mode:** `single` (standard baseline using Claude Code).
- **Verify commands:** Confirms your test and build commands.

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
Claude creates an epic and task beads in Beads (`bd`), then creates an isolated Git worktree for clean implementation. Passes the `orchestration_ready` gate.

### Stage 4: Execute
```text
/gin-workflow:execute
```
Claude claims the next ready track bead, writes a failing test first, implements the solution until tests pass, and conducts an independent code review in the review ledger. Once approved, the bead closes. Repeat `/gin-workflow:execute` until all tracks are done.

### Stage 5: Verify
```text
/gin-workflow:verify
```
Claude re-runs all verification commands with fresh evidence and audits the code line-by-line against every requirement in the spec and plan. Passes the `verification_passed` gate.

### Stage 6: Ship
```text
/gin-workflow:ship
```
Claude offers four integration options: **Merge locally**, **Push & open Pull Request**, **Keep branch**, or **Discard**. After your approval, it integrates the work, re-tests on the merged result, removes the worktree, and closes the epic (`shipped`).

---

## 4. Helpful Shortcuts

- `/gin-workflow:workflow`: Automatically detects the current state and runs whichever stage is next.
- `/gin-workflow:quick <change>`: Fast-tracks small, single-file changes without requiring specs or beads.
- `/gin-workflow:progress`: Inspects active, ready, or blocked tasks.

---

## 5. Tailored Starters & Guides

- 🌐 **Interactive Visualizer:** Open the [Interactive Simulator](interactive/index.html) for a visual walkthrough of team roles and modernization.
- 🚀 **Starting a new project?** Read the [Greenfield Project Starter](starters/greenfield.md).
- 🔄 **Refactoring a legacy codebase?** Read the [Brownfield & Modernization Starter](starters/brownfield-modernize.md).
- 👥 **Working in a team with BA, Dev, and Tester?** Read the [Team Roles Guide](starters/team-roles.md).
- ⚡ **Looking for multi-agent / multi-model routing?** See [Multi-Agent Routing](advanced/multi-agent-routing.md).

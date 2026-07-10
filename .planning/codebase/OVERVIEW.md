# Codebase Overview

**Analysis Date:** 2026-07-10
**Scope:** Full repository (`/home/gin/gin-workflow`)
**Evidence:** 
- [README.md](file:///home/gin/gin-workflow/README.md)
- [AGENTS.md](file:///home/gin/gin-workflow/AGENTS.md)
- [CLAUDE.md](file:///home/gin/gin-workflow/CLAUDE.md)
- [docs/agent-task-lifecycle.md](file:///home/gin/gin-workflow/docs/agent-task-lifecycle.md)
- [docs/orchestration-state-model.md](file:///home/gin/gin-workflow/docs/orchestration-state-model.md)
- [docs/verification-and-handoff-workflow.md](file:///home/gin/gin-workflow/docs/verification-and-handoff-workflow.md)
- [plugins/gin-workflow/plugin.meta.json](file:///home/gin/gin-workflow/plugins/gin-workflow/plugin.meta.json)
**Index Use:** Direct inspection was used (no repository index present).

## Project Purpose
`gin-workflow` is a workflow plugin designed for **Claude Code**, **Antigravity CLI**, and **Codex CLI**. It combines durable planning with Beads-backed (`bd`) execution tracking to manage developer and agent task lifecycles systematically.

## Scope and Capabilities
- **Durable Task Management**: Beads (`bd`) acts as the state database and dependency manager for active and queued tasks.
- **Structured Planning**: Approved task plans are written as markdown documents under `.planning/plans/` to document scope, trade-offs, and verification criteria.
- **Isolated Implementation**: Support for Git worktrees under `.planning/worktrees/` to isolate feature branches.
- **Safety Checks**: Pre-tool-use hooks that prevent recursive file destruction and restrict execution paths inside worktrees.
- **Multi-Platform Support**: Built to target multiple AI developer tools (Claude Code, Antigravity, and Codex).

## User-Facing Workflows
1. **Discover & Claim**: Finding open tasks using `bd ready` and claiming them with `bd update <id> --claim`.
2. **Plan**: Formulating step-by-step goals under `.planning/plans/` before making edits.
3. **Implement**: Isolating work in a worktree if needed and writing code.
4. **Verify**: Running tests and smoke tests.
5. **Handoff & Close**: Documenting outcomes, checking status with `git status`, and closing the bead via `bd close <id>`.

## Non-Goals
- Real-time status sync via external APIs (all task tracking is local and file-based using Beads).
- Automatic code committing/pushing (all git actions are strictly manual or explicitly authorized).

---

*Verified Facts:*
- The plugin targets three agent platforms: Claude Code, Antigravity, and Codex.
- Tasks are tracked in Beads (`.beads/`), planning is written in `.planning/plans/`, and lifecycle specifications reside in `docs/`.

*Inference and Uncertainty:*
- The exact versions of target agent platforms (Claude Code, Antigravity) are not hardcoded, but manifest structures target their plugin specifications.

*Follow-up:*
- None identified.

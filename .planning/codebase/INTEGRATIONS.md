# External Integrations

**Analysis Date:** 2026-07-10
**Scope:** Full repository (`/home/gin/gin-workflow`)
**Evidence:** 
- [plugins/gin-workflow/src/hooks/hooks.json](file:///home/gin/gin-workflow/plugins/gin-workflow/src/hooks/hooks.json)
- [plugins/gin-workflow/src/scripts/safety-check.sh](file:///home/gin/gin-workflow/plugins/gin-workflow/src/scripts/safety-check.sh)
- [README.md](file:///home/gin/gin-workflow/README.md)
**Index Use:** Direct inspection was used (no repository index present).

## APIs & External Services

**Task Manager (Local CLI):**
- Beads CLI (`bd` command) — Manages task workflows, ready lists, dependencies, and closures.
  - SDK / Client: Native executable `/usr/bin/bd` or system command
  - Auth: None (local file-based SQLite/Dolt database)

**Agent Platforms:**
- Claude Code / Antigravity CLI / Codex CLI — The plugin integrates with these hosts using manifest declarations, command registration, and toolhooks.
  - SDK / Client: Host platform execution hooks

## Data Storage

**Databases:**
- Beads Local DB (stored in `.beads/`)
  - Connection: Local disk path
  - Client: SQLite / Dolt engine wrapped by the `bd` binary

**File Storage:**
- Local filesystem only
  - Worktrees are created under `.planning/worktrees/`
  - Plans are written to `.planning/plans/`

**Caching:**
- None

## Authentication & Identity

**Auth Provider:**
- None (Local execution model only)

## Monitoring & Observability

**Error Tracking:**
- None

**Logs:**
- Exit codes and standard error (stderr) redirection from shell script commands (e.g. `safety-check.sh`).

## CI/CD & Deployment

**Hosting:**
- GitHub (source repository: `https://github.com/giangdhwhtbr/gin-workflow`)

**CI Pipeline:**
- None detected (no `.github/workflows/` or other CI definitions in workspace root).

## Environment Configuration

**Required env vars:**
- `WORKTREE_PATH` — Used in `safety-check.sh` to determine if a running terminal command is contained within the assigned worktree.
- `PLUGIN_ROOT` — Resolves the script path for hooks executing plugin scripts.

**Secrets location:**
- Not applicable (no secret credentials or API keys are stored or managed by the codebase).

## Webhooks & Callbacks

**Incoming:**
- PreToolUse — Hook payload sent as JSON to stdin of `safety-check.sh`.
- PostToolUse — Hook payload sent as JSON to stdin of `post-edit.sh`.

**Outgoing:**
- None

---

*Verified Facts:*
- The plugin relies entirely on local execution and has no external network integration or online databases.
- The `WORKTREE_PATH` environment variable controls safety directory containment checks in `safety-check.sh`.

*Inference and Uncertainty:*
- Host tool interfaces (Codex hook payloads) are parsed under the assumption that `jq` is present on the path.

*Follow-up:*
- None identified.

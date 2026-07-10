# Technology Stack

**Analysis Date:** 2026-07-10
**Scope:** Full repository (`/home/gin/gin-workflow`)
**Evidence:** 
- [install.sh](file:///home/gin/gin-workflow/install.sh)
- [tests/install_smoke_test.sh](file:///home/gin/gin-workflow/tests/install_smoke_test.sh)
- [plugins/gin-workflow/plugin.meta.json](file:///home/gin/gin-workflow/plugins/gin-workflow/plugin.meta.json)
**Index Use:** Direct inspection was used (no repository index present).

## Languages

**Primary:**
- Bash / Shell Scripting (POSIX-compliant sh / Bash 4+) — Used in installation scripts (`install.sh`, `remote-install.sh`), verification (`tests/install_smoke_test.sh`), hooks (`safety-check.sh`, `post-edit.sh`), and worktree helpers.
- Markdown with YAML frontmatter — Used to define plugin commands and skills for the developer platforms.

**Secondary:**
- Python 3 — Used for helper utilities during build/manifest generation in [install.sh](file:///home/gin/gin-workflow/install.sh#L112-L125) and for schema testing in [tests/install_smoke_test.sh](file:///home/gin/gin-workflow/tests/install_smoke_test.sh#L44-L63).

## Runtime

**Environment:**
- POSIX-compliant Shell Environment (Linux / macOS)
- Python 3 Interpreter

**Package Manager:**
- None for the plugin source itself (does not use npm or pip package managers directly). Plugin distribution is managed by git and custom install scripts.
- Lockfile: missing (not applicable).

## Frameworks

**Core:**
- Claude Code, Antigravity CLI, and Codex CLI plugin runtime environments.

**Testing:**
- Custom Bash Asserting Routines — Lightweight smoke testing system defined in [tests/install_smoke_test.sh](file:///home/gin/gin-workflow/tests/install_smoke_test.sh#L8-L41).

**Build / Dev:**
- Custom `install.sh` Compiler — Handles platform-specific templating and plugin distribution.

## Key Dependencies

**Critical:**
- Beads (`bd` CLI tool) — Durable task and dependency tracking.
- Git (system-level) — Worktree operations, branch isolation, and integration merging.
- `jq` — JSON command-line processor, required by hooks to parse input payloads from the hook runners.

**Infrastructure:**
- Python 3 `json` module — Used for metadata and configuration validation during installations and testing.

## Configuration

**Environment:**
- Configured via environment variables (e.g. `WORKTREE_PATH` to enforce safety checks).
- Active Beads state configuration in `.beads/` (issues database).

**Build:**
- [plugins/gin-workflow/plugin.meta.json](file:///home/gin/gin-workflow/plugins/gin-workflow/plugin.meta.json) defines manifest metadata.
- `install.sh` manages build arguments (`--platform`, `--plugin`, `--link`, `--uninstall`, `--dry-run`).

## Platform Requirements

**Development:**
- Linux or macOS with `bash` (4+), `git`, `python3`, and `jq` installed.
- Target agent platforms (Claude Code, Antigravity CLI, or Codex CLI).

**Production:**
- Installed globally into target agent plugin directories (e.g. `~/.gemini/antigravity-cli/` or equivalent configuration paths).

---

*Verified Facts:*
- The plugin utilizes Shell scripts and Python 3.
- It relies on `jq` for hook payload parsing, and standard Git for branch/worktree management.
- There are no npm or pip package manifests required for runtime.

*Inference and Uncertainty:*
- The requirement for specific Python 3 minor versions is not stated; standard Python 3.8+ is assumed.

*Follow-up:*
- None identified.

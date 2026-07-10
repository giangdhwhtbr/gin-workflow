# Coding Conventions

**Analysis Date:** 2026-07-10
**Scope:** Full repository (`/home/gin/gin-workflow`)
**Evidence:** 
- [AGENTS.md](file:///home/gin/gin-workflow/AGENTS.md)
- [CLAUDE.md](file:///home/gin/gin-workflow/CLAUDE.md)
- [plugins/gin-workflow/src/scripts/safety-check.sh](file:///home/gin/gin-workflow/plugins/gin-workflow/src/scripts/safety-check.sh)
**Index Use:** Direct inspection was used (no repository index present).

## Naming Patterns

**Files:**
- Use lowercase with hyphens for shell scripts (`safety-check.sh`).
- Use lowercase with hyphens for documentation files (`agent-task-lifecycle.md`).

**Functions:**
- Use snake_case or lowercase with underscores in scripts (`assert_exists`, `matches_platform`).

**Variables:**
- Use UPPER_SNAKE_CASE for global shell environment variables (`WORKTREE_PATH`, `PLUGIN_ROOT`, `BRANCH_NAME`).
- Use lowercase or snake_case for local variables (`quoted_re`, `real_target`).

## Code Style

**Formatting:**
- Shell scripts use standard formatting with 2-space indentation.
- Markdown files use standard headers (`#`, `##`) with visual tables.

**Linting:**
- Script code exits immediately on error (`set -e`) and handles unset variables (`set -u`).
- Shell scripts use `set -o pipefail` to ensure pipeline failures propagate correctly.

## Import Organization

**Order:**
- Since Javascript is not used in the source plugins (they are defined in markdown files and shell scripts), there are no typescript/javascript imports.
- Shell scripts import environments by fetching local script roots or parsing path files.

**Path Aliases:**
- `${PLUGIN_ROOT}` represents the current plugin directory root inside hook operations.

## Error Handling

**Patterns:**
- Shell scripts must use standard exit codes (`exit 1` for general error, `exit 2` for validation block).
- All command executions must handle command substitution errors carefully (e.g. `realpath -q "$CWD" || true`).

## Logging

**Framework:** Standard console output (stdout/stderr).

**Patterns:**
- Critical errors are logged directly to `stderr` (e.g. `echo "Error: ..." >&2`).
- Validation success or warning messages print to `stdout`.

## Comments

**When to Comment:**
- Add short header blocks in shell scripts declaring the filename and purpose.
- Document safety-check regex bounds or parsing constraints.

**JSDoc / TSDoc:**
- None.

## Function Design

**Size:** Keep functions small and focused (e.g. assert validation helpers).
**Parameters:** Rely on standard shell positioning (`$1`, `$2`) or default checks.
**Return Values:** Return 0 on success, and non-zero on failure.

## Module Design

**Exports:**
- Command modules are packaged under `plugins/gin-workflow/src/commands/` and parsed by the plugin manager.
- Helper scripts are exported as executable scripts under `plugins/gin-workflow/src/scripts/`.

---

*Convention analysis: 2026-07-10*

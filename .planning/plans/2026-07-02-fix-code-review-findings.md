# Plan: Fix Code Review Findings in install.sh

## Objective
Address the 8 findings from the code review of `install.sh` — 2 CONFIRMED bugs, 2 PLAUSIBLE issues, and 4 cleanup opportunities — identified during the plugin split refactor (core/advanced split).

## Scope
- **In scope**: `install.sh` — correctness fixes, path reliability, hardening, and structural cleanup
- **Out of scope**: `README.md`, `.gitignore`, plugin source files, `remote-install.sh`, the advanced plugin skills content itself

## Tasks

### Track 1: Fix mktemp exit code masking (CONFIRMED HIGH)
- **Dependencies**: none
- **Files**: `install.sh`
- **Acceptance criteria**: 
  - `local tmp_file=$(mktemp)` at both lines 253 and 295 is split into separate `local tmp_file` declaration and `tmp_file=$(mktemp)` assignment so `set -e` catches mktemp failures
  - `shellcheck` on install.sh produces no SC2155 warnings
- **Estimated complexity**: low

### Track 2: Restore PROJECT_DIR validation and normalization (CONFIRMED MEDIUM)
- **Dependencies**: none
- **Files**: `install.sh`
- **Acceptance criteria**:
  - `install_plugin()` validates `$PROJECT_DIR` exists (`[ -d "$PROJECT_DIR" ]`) before proceeding
  - `$PROJECT_DIR` is resolved to an absolute path (via `realpath` or `cd && pwd`) before use in `$cl_target`, `$ag_target`, `$cx_target`
  - Invalid `--project` paths exit with a clear error message, matching old behavior
- **Estimated complexity**: low

### Track 3: Fix Antigravity global-dist hardcoded install path (PLAUSIBLE LOW-MED)
- **Dependencies**: none
- **Files**: `install.sh`
- **Acceptance criteria**:
  - `template_hooks_for_antigravity` at line 322 uses `${PLUGIN_ROOT}` (Antigravity's runtime env var) instead of the hardcoded `${HOME}/.gemini/config/plugins/$p_name`
  - Or: if the hardcoded path is intentional (matching agy's actual install layout), add a comment documenting why `${PLUGIN_ROOT}` is NOT used
- **Estimated complexity**: low

### Track 4: Harden Python inline scripts against special chars in paths (PLAUSIBLE LOW)
- **Dependencies**: none
- **Files**: `install.sh`
- **Acceptance criteria**:
  - The three `python3 -c "..."` blocks (lines 300, 325, 350) pass `$p_dir` and `$dist_dir` as command-line arguments (`python3 - "$p_dir" "$dist_dir" <<'EOF' ...`) or use a heredoc approach that doesn't interpolate path values directly into Python string literals
  - Plugin names containing single quotes or other special characters do not cause Python SyntaxError
- **Estimated complexity**: low

### Track 5: Extract helpers and reduce duplication (CLEANUP)
- **Dependencies**: Track 1–4 (runs last to avoid merge conflicts with fix tracks)
- **Files**: `install.sh`
- **Acceptance criteria**:
  - Three duplicated `python3 -c` manifest blocks extracted into a single `generate_manifest()` helper parameterized by platform
  - Nine repeated platform-condition blocks extracted into a `matches_platform()` helper
  - Duplicated project-level vs global-dist install blocks unified into a single code path parameterized by target directory
  - `TARGET_PLUGIN` values are validated against a known set; unrecognized values produce an error
  - `bash -n install.sh` passes; `shellcheck install.sh` produces no new warnings
- **Estimated complexity**: medium

## Integration
- **Branch**: `fix/code-review-install-sh` (ephemeral worktree branch)
- **Merge strategy**: sequential — Track 1 → Track 2 → Track 3 → Track 4 → Track 5 (Track 5 depends on 1–4 to avoid conflicts; 1–4 are independent but sequential is safer for a single file with tightly coupled changes)

## Validation
- [ ] `bash -n install.sh` passes syntax check
- [ ] `shellcheck install.sh` shows no SC2155 or new warnings
- [ ] `./install.sh --plugin core --dry-run` completes without error
- [ ] `./install.sh --plugin advanced --dry-run` completes without error
- [ ] `./install.sh --plugin all --dry-run` completes without error
- [ ] `./install.sh --project /nonexistent` exits with clear error (Track 2)
- [ ] `./install.sh --project . --dry-run` uses absolute paths in generated hooks.json (Track 2)
- [ ] `./install.sh --plugin invalid-name` exits with error (Track 5)
- [ ] Generated `hooks.json` for Antigravity global-dist uses `${PLUGIN_ROOT}` or has documented reason for hardcoded path (Track 3)
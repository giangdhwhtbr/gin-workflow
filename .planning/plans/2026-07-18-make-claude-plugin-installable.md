# Plan: Make Claude Code Plugin Installable Globally

## Objective
Make the `gin-workflow` plugin globally installable for the Claude Code CLI, automatically loading it without requiring the `--plugin-dir` flag on every session startup.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `brainstorm`: `high_reasoning`
  - `design`: `high_reasoning`
  - `plan`: `standard_impl`
  - `implement`: `standard_impl`
  - `verify`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`

## Requirement Analysis
- **Problem statement**: Currently, `./install.sh` builds the Claude Code plugin structure into a local `dist/claude-code` folder, forcing users to start Claude Code with `claude --plugin-dir ...` on every run.
- **Success criteria**:
  1. `./install.sh --platform claude` (with or without `--link`) successfully copies/links the built plugin files from `dist/claude-code` to the global directory `~/.claude/skills/gin-workflow`.
  2. The installer automatically toggles `"gin-workflow@skills-dir": true` in `~/.claude/settings.json`.
  3. The installer gives clean user feedback confirming global setup.
  4. The existing `tests/install_smoke_test.sh` tests continue to pass successfully.
- **Constraints**:
  - Do not break existing dry-run and local-build outputs checked by `install_smoke_test.sh`.
  - Perform edits programmatically in `install.sh` without requiring interactive user input.
- **Non-goals**: Modifying other platforms (Codex/Antigravity) unless needed for consistency, or configuring local project plugins inside `.claude` unless explicitly requested.

## Approach Options
### Option 1: Copy/Symlink built files to global skills directory (Selected)
- **Summary**: Build local plugin under `dist/claude-code`, then copy or symlink it to `~/.claude/skills/gin-workflow` and update settings.
- **Pros**:
  - Keeps tests fully compatible since the local `dist/` directory is still created exactly as expected.
  - Consistent with the Antigravity installation workflow.
  - Clean dev workflow via symlink mapping when using `--link`.
- **Cons**: None.

### Option 2: Generate custom marketplace and register via database files
- **Summary**: Directly modify Claude Code's internal database files (`installed_plugins.json` and `known_marketplaces.json`).
- **Pros**: None.
- **Cons**: Brittle, subject to format changes, and undocumented internals.

## Scope
- **In scope**:
  - Modifying `install.sh` to implement global installation for Claude Code.
  - Adding `enable_claude_plugin` helper in `install.sh` using Python.
  - Adding assertions to `tests/install_smoke_test.sh` to cover global registration output and verify settings.json toggle.
- **Out of scope**: Modifying Claude Code binary or CLI settings commands.

## Tasks
### Track 1: Update `install.sh`
- **Dependencies**: None
- **Files**:
  - Modify: `install.sh`
- **Model class**: `standard_impl`
- **Acceptance criteria**:
  - Adds the `enable_claude_plugin` function to update `~/.claude/settings.json`.
  - In `install_plugin`, checks if `platform` is `claude`, targets `~/.claude/skills/gin-workflow`, copies or links the built files, and calls the settings toggle.
  - Prints installation success message instead of manual CLI instructions.
- **Estimated complexity**: medium

### Track 2: Update and run smoke tests
- **Dependencies**: Track 1
- **Files**:
  - Modify: `tests/install_smoke_test.sh`
- **Model class**: `standard_impl`
- **Acceptance criteria**:
  - Validate that `tests/install_smoke_test.sh` passes successfully.
  - Add assertions verifying that settings are updated correctly.
- **Estimated complexity**: low

## Integration
- **Branch**: master
- **Merge strategy**: sequential

## Validation
- [ ] `./install.sh --platform claude --dry-run` shows output: `(dry-run) would install global Claude Code plugin to /home/gin/.claude/skills/gin-workflow`
- [ ] `./install.sh --platform claude` copies plugin to `~/.claude/skills/gin-workflow`
- [ ] `~/.claude/settings.json` has `"gin-workflow@skills-dir": true`
- [ ] `./tests/install_smoke_test.sh` runs and passes successfully

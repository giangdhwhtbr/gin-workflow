# CLI `gin` and the `gin:` namespace (3.0)

## Context

Up to 2.x the CLI was `gin-workflow` and the plugin id was `gin-workflow`, so commands read `gin-workflow task ready` and `/gin-workflow:discuss`, and several skills repeated the prefix (`gin-workflow:gin-sdd`).

## Decision

Version 3.0 is a clean cut: the CLI is `gin` (launcher `~/.local/bin/gin` linked to `~/.local/lib/gin/3.0/gin`), the plugin id is `gin`, and the skills lost their `gin-` prefix (`gin-knowledge` became `learn`). No `gin-workflow` alias is installed. On OpenCode, where a skill id is its bare folder name, the installers rename the eight generic skills to `gin-<name>` (`gin-learn`, `gin-sdd`, ..., `gin-report`).

Names that stay on purpose: the repository, `plugins/gin-workflow/`, `GIN_WORKFLOW_*` variables, `gin-workflow-marketplace`, `.gin-workflow-src.json`, `gin-workflow-bundle.json`, the team CI file `gin-workflow.yml`, `.agent-workflow/`, and the orchestrator task-tracking provider id `gin-workflow`.

## Consequences

- The CLI still recognises what 2.x wrote into user repositories: hooks with the old marker or `gin-workflow hooks run` are `stale` and rewritten by `gin hooks install`; an `AGENTS.md` block under `gin-workflow:start` markers is replaced by `gin setup refresh`; `gin team init` rewrites its old-marker files. The legacy constants live in `workflow_core/hooks.py`, `agents_block.py`, and `team_init.py`.
- `install.sh` and `install.ps1` remove the managed `gin-workflow` launcher and the old plugin installs per harness; they stop before removing anything when `~/.claude/settings.json` cannot be parsed.
- `tests/workflow_core/test_rename_sweep.py` fails on `gin-workflow <command>` or `gin-workflow:` in `plugins/*/src`, `tests/`, `docs/`, `README.md`, and `AGENTS.md`, outside its allow list.
- Records, specs, and plans under `.planning/` written before 3.0 keep the old names; read `gin-workflow <cmd>` there as `gin <cmd>`.
- gin-console reads state through `gin-workflow state` until its bead `gin-console-e1z` moves it to `gin`.
- `install.ps1` and `tests/install_smoke_test.ps1` were not run locally (no `pwsh`); Windows CI verifies them.

## References

- Spec `.planning/specs/2026-11-06-rename-gin-design.md`, plan `.planning/plans/2026-11-06-rename-gin.md`
- Beads `gin-workflow-rename-gin` (.1 to .4), `gin-console-e1z`
- Upgrade steps: `docs/reference/troubleshooting.md#upgrading-from-gin-workflow-2x`

## Scope

The whole repository and every installed harness.

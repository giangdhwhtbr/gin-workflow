---
name: setup
description: Use when a repository needs first-time gin-workflow configuration or explicitly requested setup maintenance.
---

# Setup Skill

Coordinate one setup session outside the lifecycle. Do not require generated configuration, a context manifest, or a durable approval record before initial setup; they are unavailable until bootstrap completes. CLI: `gin-workflow setup <subcommand>`.

## Quick setup (default)

Setup runs with one main harness; worker harnesses come from gin-orchestrator (`/gin-orchestrator:providers`).

Ask exactly one question at a time and wait for its answer. Do not infer required answers or combine questions.

1. **Project type** — Show the `project` block of `gin-workflow setup detect --format json` (stage, shape, monorepo, stack, packages); confirm or edit. Never propose `legacy` unless the user says so.
2. **Rigor** — Suggest `suggested_rigor`. `easy`: no worktree, self-check review; `standard`: worktree for parallel work, independent review; `strict`: always a worktree, independent review with a review ledger.
3. **Verify commands** — Confirm the detected lint, typecheck, test, build, and e2e commands; the user may edit any. On greenfield, ask for `stack_intent` instead.
4. **Code index** — Brownfield or legacy only. When `codegraph.installed` is true and it is not `indexed`: offer `codegraph init`, and run it only on approval. When `codegraph.installed` is false: print one line suggesting CodeGraph with https://github.com/giangdhwhtbr/gin-workflow/blob/master/docs/guides/recommended-tools.md; do not ask, install, or wait.
5. **Task tracking** — `markdown` (default) or `beads` (needs `bd`), passed as `--task-tracking`.

Then:
1. `gin-workflow setup preset --project-stage S --project-shape X --rigor R --task-tracking T [--monorepo] [--stack-intent TEXT] --format json` returns the assignments; add any user edits as extra `--set` assignments.
2. Run `init --dry-run` with the harness and every assignment. Present `configuration`, the proposed `rule_packs` (the user may add or remove packs as an extra `--set rules.packs=[...]`), each `rule_tool_checks` item with its `suggest` snippet (suggestions only; setup never edits lint or type configs), the exact files/actions, and any validation error. Do not write on dry-run.
3. Obtain explicit native-harness approval for the proposal.
4. Run one approved `init` with the same harness and same assignments. The CLI validates before any atomic write.
5. When `verify.checks` is configured, run `gin-workflow hooks install` (quality checks run in `pre-commit`/`pre-push`, not in a lifecycle stage). If it reports `occupied` or `missing`, show the user the printed instruction; never overwrite a hook.
6. Report the structured result and stop. Do not invoke `discuss` or any other lifecycle stage.

Answers become `--set` assignments in `.agent-workflow/config.yaml`.

One `/setup` invocation completes initial setup. Repeated identical `init` calls are idempotent; lifecycle stages never call setup automatically.

## Explicit maintenance

On an initialized repository, run only the maintenance action the user requested: `detect`, `preset`, `models`, `configure`, `refresh`, `update`, `doctor` (`--probe` for active model health; also reports missing git hooks and missing verify commands, a stale codegraph index, and a greenfield stage that now has sources), `status`, `diff`, `rollback`, `export-bundle`, or `verify-bundle`. Present dry-run output before user-authored configuration changes, upgrades, rollback, or data movement. After bootstrap, protected mutations use the approval and evidence capabilities.

The CLI must not prompt, choose policy, or manufacture approval.

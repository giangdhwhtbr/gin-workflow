---
name: setup
description: Use when a repository needs first-time gin-workflow configuration or explicitly requested setup maintenance.
---

# Setup Skill

Coordinate one setup session outside the lifecycle. Do not require generated configuration, a context manifest, or a durable approval record before initial setup; they are unavailable until bootstrap completes. CLI: `gin-workflow setup <subcommand>`.

## Quick setup (default)

Ask exactly one question at a time and wait for its answer. Do not infer required answers or combine questions.

1. **Project type** — Show the `project` block of `gin-workflow setup detect --format json` (stage, shape, monorepo, stack, packages); confirm or edit. Never propose `legacy` unless the user says so.
2. **Rigor** — Suggest `suggested_rigor`. `easy`: no worktree, self-check review; `standard`: worktree for parallel work, independent review; `strict`: always a worktree, independent review with a review ledger.
3. **Provider mode** — `single` (the current harness does everything; default) or `multi` (continue with Advanced setup groups 2–9).
4. **Verify commands** — Confirm the detected lint, typecheck, test, build, and e2e commands; the user may edit any. On greenfield, ask for `stack_intent` instead.
5. **Code index** — Only when `codegraph.installed` is true, it is not `indexed`, and the stage is brownfield or legacy: offer `codegraph init`, and run it only on approval.

Optional: a model per tier for the current harness from `gin-workflow setup models --provider <harness> --format json`. Suggest fast/cheap models for `low` and frontier models for `high`; an `agy` id suffix (`-low`/`-medium`/`-high`) matches its tier. Always allow manual entry; an empty list means manual entry. Model choices become `--provider-set` assignments.

Then:
1. `gin-workflow setup preset --project-stage S --project-shape X --rigor R --provider-mode M [--monorepo] [--stack-intent TEXT] --format json` returns the assignments; add any user edits as extra `--set` assignments.
2. Run `init --dry-run` with the harness and every assignment. Present both `configuration` and `provider_configuration`, the exact files/actions, and any validation error. Do not write on dry-run.
3. Obtain explicit native-harness approval for the complete two-layer proposal.
4. Run one approved `init` with the same harness and same assignments. The CLI validates both layers before any atomic write.
5. Report the structured result and stop. Do not invoke `discuss` or any other lifecycle stage.

Portable answers become `--set` assignments in `.agent-workflow/config.yaml`; executable/model answers become `--provider-set` assignments in the gitignored `.agent-workflow/providers.local.yaml`.

## Advanced setup

Used for `/setup --advanced` or `multi` provider mode: the five quick questions above, then these groups, one at a time.

1. **Main harness** — Which harness opened and will coordinate this workflow: Claude, Codex, or Antigravity?
2. **Enabled native providers** — Which installed, already-authenticated native CLIs may execute work, and what executable name/path identifies each?
3. **Preferred provider roles** — For each user-defined role such as backend, frontend, review, docs, or general, what is the ordered preferred provider list?
4. **Reasoning-to-model mappings** — For every enabled provider, which model maps to `low`, `medium`, and `high`? Offer the list from `gin-workflow setup models --provider <p>`. (For Codex, each tier can also set a reasoning effort; for Antigravity, `provider_default` is allowed.)
5. **Ordered fallbacks** — Which providers, including optional `main_harness`, may handle each role when preferred capacity is unavailable?
6. **Provider concurrency** — What maximum concurrent worker count applies to each provider?
7. **Queue and worker limits** — What are queue wait seconds, worker timeout seconds, and maximum retries?
8. **Circuit breaker** — What failure threshold, cooldown seconds, and half-open probe limit should apply?
9. **Independent review** — Which review role is used, must review differ from implementation, may self-review be a fallback, and what is the maximum cycle count (suggest 2)?

Use `plugins/gin-workflow/src/examples/config.full.yaml` and `providers.local.example.yaml` as a reference, never as silently accepted answers. Credentials remain owned by each native CLI login and are never questionnaire values.

One `/setup` invocation completes initial setup. Repeated identical `init` calls are idempotent; lifecycle stages never call setup automatically.

## Explicit maintenance

On an initialized repository, run only the maintenance action the user requested: `detect`, `preset`, `models`, `configure`, `refresh`, `update`, `doctor` (`--probe` for active model health; also reports missing verify commands, a stale codegraph index, and a greenfield stage that now has sources), `status`, `diff`, `rollback`, `export-bundle`, or `verify-bundle`. Present dry-run output before user-authored configuration changes, upgrades, rollback, or data movement. After bootstrap, protected mutations use the approval and evidence capabilities.

The CLI must not prompt, choose policy, or manufacture approval.

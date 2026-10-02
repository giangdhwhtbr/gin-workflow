---
name: setup
description: Use when a repository needs first-time gin-workflow configuration or explicitly requested setup maintenance.
---

# Setup Skill

Coordinate one setup session outside the lifecycle.

## Initial setup inputs

- repository target
- native harness context, when detected
- user-selected portable settings

Do not require generated configuration, a context manifest, or a durable
approval record before initial setup. They are unavailable until bootstrap
completes.

## First-time execution

1. Detect the repository and harness, then run the questionnaire below. Ask exactly one question group at a time and wait for its answer before continuing.
2. Convert portable answers to repeatable `--set` assignments and executable/model answers to repeatable `--provider-set` assignments.
3. Run `init --dry-run` with the selected harness and every assignment.
4. Present both `configuration` and `provider_configuration`, the exact files/actions, and any validation error. Do not write on dry-run.
5. Obtain explicit native-harness approval for the complete two-layer proposal.
6. Run one approved `init` with the same harness and same assignments. The CLI validates both complete layers before any atomic write.
7. Report the structured result and stop. Do not invoke `discuss` or any other lifecycle stage.

## Routed worker questionnaire

Do not infer required answers or combine groups into one large prompt.

1. **Main harness** — Which harness opened and will coordinate this workflow: Claude, Codex, or Antigravity?
2. **Enabled native providers** — Which installed, already-authenticated native CLIs may execute work, and what executable name/path identifies each?
3. **Preferred provider roles** — For each user-defined role such as backend, frontend, review, docs, or general, what is the ordered preferred provider list?
4. **Reasoning-to-model mappings** — For every enabled provider, which local model alias maps to `low`, `medium`, and `high`? (For Codex, each tier can specify both model and optional reasoning effort, e.g. `gpt-6-astra` with `low`/`medium`/`high` effort; for Antigravity, `gemini-3.8-flash` is recommended or `provider_default`).
5. **Ordered fallbacks** — Which providers, including optional `main_harness`, may handle each role when preferred capacity is unavailable?
6. **Provider concurrency** — What maximum concurrent worker count applies to each provider?
7. **Queue and worker limits** — What are queue wait seconds, worker timeout seconds, and maximum retries?
8. **Circuit breaker** — What failure threshold, cooldown seconds, and half-open probe limit should apply?
9. **Independent review** — Which review role is used, must review differ from implementation, may self-review be a fallback, and what is the maximum cycle count (suggest 2)?

Use `plugins/gin-workflow/src/examples/config.full.yaml` and `providers.local.example.yaml` as a reference, never as silently accepted answers. Credentials remain owned by each native CLI login and are never questionnaire values.

One `/setup` invocation completes initial repository setup and configuration.
Repeated identical `init` calls are idempotent, but lifecycle stages never call
setup automatically.

## Explicit maintenance

On an initialized repository, select only the maintenance action the user
requested: `detect`, `configure`, `refresh`, `update`, `doctor` (optionally `--probe` for active model health verification), `status`,
`diff`, `rollback`, `export-bundle`, or `verify-bundle`. Present dry-run output
before user-authored configuration changes, upgrades, rollback, or data
movement. After bootstrap, protected mutations use the approval and evidence
capabilities.

The CLI must not prompt, choose policy, or manufacture approval. Optional notifications use the configured notification capability.

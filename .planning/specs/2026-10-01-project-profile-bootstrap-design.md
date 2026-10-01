# Project Profile Bootstrap, Frontend Support, Quick Path (Sub-project B+C) — Design

Date: 2026-10-01
Status: awaiting user confirmation
Depends on: sub-project A (`.planning/specs/2026-10-01-workflow-token-optimization-design.md`) — uses `references/stage-contract.md`, merged skills/agents, the token budget test, and `gin-workflow record`.
Followed by: sub-project D (best-practice rules), which loads rules through the shape/stack mechanism defined here.

## Problem (verified in repository)

- `setup detect` (`scripts/workflow_core/setup_service.py:detect`) only detects harness markers (`.claude`, `.codex`, `.agents`). No stack, shape, maturity, verify-command, provider-CLI, or codegraph detection.
- Setup always asks 9 routing question groups; most users accept defaults and use a single provider.
- Advanced setup asks users to type model aliases from memory.
- Review independence is provider-based (`review_coordinator.py`: reviewer must have `provider != implementation provider`); with a single provider this raises `independent reviewer route is unavailable` unless self-review fallback is enabled.
- One generic `full-stack-developer` agent; frontend-only projects load backend guidance. No frontend verification gates; verify does not know project commands.
- Every change, however small, goes through plan → orchestrate → execute → verify → review.
- `codebase-mapper` + `tech-doc` duplicate what codegraph provides and produce documents that go stale.
- The existing "profile" in `configuration.py` (`GIN_WORKFLOW_USER_PROFILE`, organization profile) is a config overlay, not a project type; the new concept is named `project` to avoid collision.

## Decisions

| Topic | Decision |
|---|---|
| Classification | Two axes: `stage` (greenfield/brownfield/legacy) × `shape` (frontend/backend/fullstack/library) + `monorepo` flag. Auto-detected, user confirms. |
| Setup flow | Quick setup (default, ~5 questions) + `/setup --advanced` (all 9 routing groups + project questions). |
| Provider mode | `single` default (current harness); `multi` optional and the only mode that opens routing questions. |
| Rigor | `easy` / `standard` / `strict`; default suggested by stage (greenfield→easy, brownfield→standard, legacy→strict), user can change. |
| Verify commands | Detected at setup, stored in `verify.commands`; runtime reads config only; per-package in monorepo. |
| Greenfield | No scaffolding. Store `project.stack_intent`; first task sets up lint/typecheck/test; `doctor` suggests moving to brownfield with user consent. |
| Code mapping | Remove `codebase-mapper`. Codegraph recommended, optional with grep/read fallback. `tech-doc` kept, slimmed, codegraph-backed, on demand only. |
| Implementer agent | Single `developer` agent + shape appendices. |
| Model selection | List real models from provider CLIs; manual entry always available. |
| Benchmark | Documented manual protocol + summarizer script; not in CI. |

## Design

### 1. Configuration (schema 2.3 → 2.4)

Added to `.agent-workflow/config.yaml`:

```yaml
project:
  stage: brownfield          # greenfield | brownfield | legacy
  shape: frontend            # frontend | backend | fullstack | library
  monorepo: false
  rigor: standard            # easy | standard | strict
  stack_intent: ""           # greenfield only, e.g. "React + TypeScript + Vite"
  packages: []               # monorepo: [{path, shape, verify: {commands: {...}}}]
provider_mode: single        # single | multi
verify:
  commands:
    lint: ""
    typecheck: ""
    test: ""
    build: ""
    e2e: ""                  # run only at strict
routing:
  review:
    independence: session    # provider | session
```

- Missing `project:` section ⇒ `shape: fullstack`, `rigor: standard`, `provider_mode: multi`, `independence: provider` — existing repos keep current behavior.
- Presets derived from the answers are written explicitly into config at setup (roles, `max_cycles`, `worktree: always|parallel|never`, review-ledger requirement); skills never infer them at runtime.
- Shape → roles: `frontend` ⇒ `frontend, review, docs, general`; `backend` ⇒ `backend, review, docs, general`; `fullstack`/`library` ⇒ current set.
- Rigor → presets:

| | easy | standard | strict |
|---|---|---|---|
| Default path | `/quick` | `/quick` small, lifecycle for features | lifecycle always |
| Plan + orchestrate | skipped | multi-track features | required |
| Review | self-check checklist | 1 independent review, `max_cycles: 2` | independent, `max_cycles: 2`, review-ledger required |
| Worktree | `never` | `parallel` | `always` |
| Verify gates | lint, typecheck, tests for changed files | lint, typecheck, test, build | all + e2e/a11y when configured |

- Migration 2.3 → 2.4 adds version fields and defaults only; never overwrites existing values.
- Schema validation in `schemas.py` covers the new keys and enums.

### 2. Detection (`setup detect`, deterministic, no LLM)

- **Shape/stack:** `package.json` dependencies (react/vue/svelte/next/nuxt/angular ⇒ frontend; express/nestjs/fastify/koa ⇒ backend; both ⇒ fullstack), `pyproject.toml`/`requirements.txt` (fastapi/django/flask ⇒ backend), `go.mod`, `Cargo.toml`; `bin`/library markers ⇒ library. Workspaces (`pnpm-workspace.yaml`, `package.json#workspaces`, `turbo.json`, `nx.json`) ⇒ `monorepo` with per-package detection.
- **Package manager:** from lockfile (pnpm/yarn/npm/bun; uv/poetry/pip).
- **Verify commands:** `package.json#scripts` (`lint`, `typecheck`/`type-check`, `test`, `build`, `test:e2e`/`e2e`), else known tools present in config (`tsc` with `tsconfig.json` ⇒ `<pm> tsc --noEmit`; `ruff`, `mypy`, `pytest` from `pyproject.toml`). Missing commands stay empty and produce a dry-run warning.
- **Stage:** near-empty repo (no manifest and few source files) ⇒ `greenfield`; otherwise `brownfield`. `legacy` is never auto-assigned.
- **Providers:** `claude`, `codex`, and Antigravity's executable `agy`, resolved through `executable_resolver.py` `PROVIDER_EXE_ALIASES` (no second hardcoded mapping).
- **Codegraph:** `codegraph` on PATH and `.codegraph/` presence/staleness.

Detection output is a proposal; nothing is written until the approved `init`.

### 3. Setup flow

Quick setup (default), one question at a time:
1. Confirm or edit project type (stage + shape + monorepo).
2. Rigor (suggested from stage).
3. Provider mode: single (current harness) or multi. Multi continues into the advanced routing groups.
4. Confirm detected `verify.commands`; for greenfield ask `stack_intent` instead.
5. Brownfield/legacy with codegraph installed but no index: offer `codegraph init` (runs only on approval).

Optional in quick setup: pick a model per tier for the current harness (default `provider_default`).

Then: dry-run of both config layers → explicit approval → single `init` (unchanged mechanics). `/setup --advanced` runs all 9 existing groups plus the project questions.

### 4. Model discovery

- `list_models(provider)` in `workflow_providers/native_cli.py` returns `[{id, label, description, reasoning_levels}]`:
  - `codex`: `codex debug models` (JSON), keep `visibility: list`, map `supported_reasoning_levels`; 30 s timeout.
  - `claude`: static aliases `opus`, `sonnet`, `haiku` (CLI has no list command; aliases track latest).
  - `antigravity` (`agy`): `agy models`, parse `<id>\t<label>` lines, skip the `Fetching available models...` header; reasoning taken from id suffix `-low|-medium|-high`.
  - Unknown provider or any failure/parse error ⇒ empty list.
- New read-only CLI: `gin-workflow setup models --provider <p> --format json`.
- Setup skill presents choices per tier with suggestions (fast/cheap ⇒ low, frontier ⇒ high; `agy` suffix matches tier) and always offers manual entry; empty list ⇒ manual entry, never blocks setup.
- Selections are written only to gitignored `providers.local.yaml`; `/setup doctor --probe` validates them.

### 5. `/quick` fast path

- `commands/quick.md` + skill `quick`; load chain ≤ 8,000 chars (added to the token budget test).
- Flow: restate requirement in 1–3 lines and get confirmation → implement → run `verify.commands` per rigor → at `standard`, one independent review → report (change summary + verify output).
- No plan, no beads, no lifecycle gates, never commit/push. Records `quick.completed` event with evidence (via `gin-workflow record quick-completed`), shown by `progress`.
- `strict`: refuses and points to `/discuss` unless a waiver is recorded with `gin-workflow unblock`.
- Escalation: if the change exceeds `quick.max_files` (default 5) or spans multiple top-level modules/packages, stop and recommend the full lifecycle.

### 6. Review independence in single-provider mode

- `routing.review.independence: provider | session`.
- `session`: reviewer is a fresh subagent/session of the same provider with clean context, receiving only diff, plan/requirement, and acceptance criteria. `review_coordinator.py` checks reviewer actor/session id differs from the implementer's instead of provider.
- `provider`: current behavior.
- Single mode defaults to `session`; multi defaults to `provider`.

### 7. Developer agent and shape appendices

- Remove `agents/full-stack-developer.md`; add `agents/developer.md` (≤ 4,000 chars).
- `references/shape-frontend.md` (≤ 1,500): component boundaries, state management, accessibility basics, no hardcoded user-facing strings when i18n exists, visual check at strict (Playwright screenshot when configured).
- `references/shape-backend.md` (≤ 1,500): API contracts, validation, error handling, migrations, data access.
- Loading: `project.shape` selects the appendix; `fullstack` selects by task file scope. Sub-project D attaches language/framework rules through the same mechanism.
- Routing roles `frontend`/`backend` keep mapping to providers; agent choice no longer depends on role.

### 8. Codegraph and tech-doc

- Delete `agents/codebase-mapper.md`; remove `.planning/codebase/*` references from `agent-researcher` and other files.
- `tech-doc` slimmed: uses `codegraph files` / `codegraph explore` when available, grep/read otherwise; runs only on `/tech-doc`. Existing `.planning/codebase/` directories in consumer repos are left untouched.
- `stage-contract.md` (from A) states lookup order: codegraph when `.codegraph/` exists, else grep/read.
- `doctor` warns when the index is older than HEAD and suggests `codegraph sync`.

### 9. Benchmark

- `docs/benchmarks/README.md`: protocol — pinned React + TypeScript + Vite sample repo commit; tasks (a) small bug fix, (b) medium feature with component, state, tests; configurations: gin `easy` (`/quick`), gin `standard`, superpowers, spec-kit; same harness (Claude Code) and model.
- Metrics: input/output/cache tokens, tool calls, wall time, tests pass. A run that fails tests is reported as failed, not as cheaper.
- `scripts/benchmark/summarize_usage.py`: reads Claude Code transcript JSONL (`usage` fields) for given session ids and prints a comparison table.
- Results stored under `docs/benchmarks/` with date and framework versions. Not in CI.

## Testing

- Detection fixtures for: empty repo (greenfield), React+Vite (frontend), FastAPI (backend), Next.js + API (fullstack), pnpm workspace (monorepo), library; assert shape, stage, package manager, verify commands.
- Schema 2.4 validation and 2.3 → 2.4 migration preserving existing values; repo without `project:` resolves to legacy-compatible defaults.
- Preset generation per shape × rigor.
- `list_models` parsing for codex JSON and `agy` text (recorded fixtures) and failure fallback to empty list.
- Review coordinator: `session` independence accepts same provider with different session and rejects same session.
- `/quick`: escalation threshold logic and strict refusal (where implemented in code); token budget test covers `quick`.
- Packaging tests updated for added/removed agents, commands, skills; full suite and install smoke tests pass for claude-code, codex, antigravity.

## Out of scope

- Language/framework best-practice rules (sub-project D).
- Project scaffolding for greenfield.
- Automated/headless benchmark runs and CI benchmarking.
- Changes to lifecycle gates beyond `quick.completed` recording.

## Acceptance criteria

1. Quick setup on a React+TS repo with only one provider completes in ≤ 5 questions and produces `shape: frontend`, correct `verify.commands`, frontend-only roles, and `independence: session`.
2. Existing 2.3 configs migrate to 2.4 without behavior change.
3. `gin-workflow setup models` lists real models for `codex` and `agy`, aliases for `claude`, and falls back to manual entry on failure.
4. Single-provider review runs without self-review fallback.
5. `/quick` works per rigor, escalates over threshold, refuses at strict without waiver, never commits.
6. `codebase-mapper` and `full-stack-developer` removed; `developer` + shape appendices in place; budgets pass.
7. Benchmark protocol and summarizer exist and the summarizer is tested on a fixture transcript; recording actual benchmark runs is not required for acceptance.
8. `gin-workflow record` (from A) gains the `quick-completed` event type.

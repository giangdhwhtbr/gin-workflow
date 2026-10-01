# Best-Practice Rules (Sub-project D) — Design

Date: 2026-10-01
Status: awaiting user confirmation
Depends on:
- A (`.planning/specs/2026-10-01-workflow-token-optimization-design.md`): token budget test, merged `execute`/`review` skills.
- B+C (`.planning/specs/2026-10-01-project-profile-bootstrap-design.md`): `setup detect`, schema 2.4, `developer` agent, `stack_intent`, `/quick`, `doctor` extensions.

## Goal

Agents consistently follow language/framework best practices without raising per-task token cost beyond a fixed budget.

## Decisions

| Topic | Decision |
|---|---|
| Enforcement | Two layers: tooling (linters/typecheck, verified by `verify.commands`) first; short imperative text only for what tooling cannot check. Review uses the same packs as checklist. |
| First packs | 7: `core`, `typescript`, `python`, `react`, `nextjs`, `fastapi`, `node-api`. |
| Precedence | Project rules > framework > language > core. Packs selectable/disable-able in config. `CLAUDE.md`/`AGENTS.md` are not copied (harness loads them); conflicts only warned. |
| Loading | Deterministic CLI selects packs by task file scope; injected only into `developer` (execute, `/quick`) and reviewer prompts; ≤ 4,000 chars per task. |
| Tooling layer | Report and suggest only (`doctor`, setup dry-run). Setup never edits lint/tsconfig; changes go through `/quick` or a task. |

## Design

### 1. Pack format

One file per pack: `plugins/gin-workflow/src/rules/<pack>.md`.

```markdown
---
id: react
tier: framework            # core | language | framework
requires: [typescript]     # optional; co-load and ordering
applies_to: ["**/*.tsx", "**/*.jsx"]
detect: {package_json_deps: [react]}
conflict_keywords:
  - {pack_says: "named export", project_conflict: "default export"}
tool_checks:
  - id: react-hooks-lint
    check: {eslint_rule: "react-hooks/rules-of-hooks"}
    suggest: |
      // eslint.config.js snippet
---
- Imperative bullet rules, each with a stable anchor id, e.g. `state-location`.
```

- Body ≤ 1,500 chars; `core` ≤ 1,000. Bullets only, no rationale prose.
- Each bullet carries a stable anchor so review findings can cite `<pack>#<anchor>`.
- Content covers only what tooling cannot check (boundaries, state placement, error handling, naming, module splitting, testing approach).
- Supported `detect` keys: `package_json_deps`, `pyproject_deps`, `files_exist`. Supported `check` kinds: `tsconfig_option`, `eslint_rule` (static scan of eslint config files), `pyproject_tool` (e.g. `tool.ruff`, `tool.mypy`), `file_exists`. Unparseable configs report `unknown`, never fail.

### 2. Project rules

`.agent-workflow/rules/*.md` in the consumer repo, same frontmatter (minimum `applies_to`; `id` defaults to file stem), body ≤ 1,500 chars, highest precedence.

### 3. Configuration

```yaml
rules:
  packs: [core, typescript, react]   # proposed by setup from detect/stack_intent, user confirms
  disabled: []
```

- Missing `rules:` ⇒ `core` only.
- Added in schema 2.4 if D ships in the same release as B+C; otherwise schema 2.5 with a defaults-only migration.

### 4. CLI

- `gin-workflow rules --files <paths...> [--format text|json]`: select enabled packs and project rules whose `applies_to` matches any path (plus `requires`, plus `core`), order by precedence, concatenate. If total > 4,000 chars, print a warning to stderr and still return output.
- `gin-workflow rules --list`: enabled packs, source (plugin/project), size.

### 5. Stage integration

- `execute` and `/quick`: orchestrator runs `gin-workflow rules --files <task scope>` and injects the result into the `developer` prompt.
- `review`: same rule set injected as checklist; findings for violations cite `<pack>#<anchor>`.
- `discuss`, `plan`, `orchestrate`, `verify`, `ship`: no rules loaded.

### 6. Setup and doctor

- Setup dry-run proposes `rules.packs` from `detect` (greenfield: from `stack_intent`) and lists missing tool checks with suggested snippets.
- `/setup doctor`: runs `tool_checks` for enabled packs (read-only) and keyword-based conflict warnings between `conflict_keywords` and `CLAUDE.md`/`AGENTS.md`.
- Greenfield's first task (from B+C) uses the suggested snippets when setting up lint/typecheck/test.

## Testing

- Budget test (extends A): each pack body ≤ 1,500 (`core` ≤ 1,000); project-rule size check in `rules --list`.
- Selection: Python-only file scope gets `core`+`python`(+`fastapi` when enabled), never `react`; project rule ordered first; `disabled` honored; `requires` co-loaded; > 4,000 warns without failing.
- Detect proposes correct packs on B+C fixtures (React+Vite ⇒ core, typescript, react; FastAPI ⇒ core, python, fastapi; Next.js ⇒ + nextjs).
- `tool_checks` on fixtures: tsconfig without `strict`, pyproject without ruff, eslint config missing react-hooks; unparseable config ⇒ `unknown`.
- Frontmatter lint: every pack has `id`, `tier`, `applies_to`, unique anchors.
- Packaging tests include `rules/` in all three harness dists.

## Out of scope

- Packs beyond the initial 7 (Go, Rust, Vue, Django, testing-specific, …) — addable later without code changes.
- Automatically editing project lint/type configs.
- LLM-based conflict detection.

## Acceptance criteria

1. 7 packs exist within budget, each body limited to rules tooling cannot enforce.
2. `gin-workflow rules --files` returns only relevant packs in precedence order; project rules override.
3. `developer` and reviewer receive rules via injection in `execute`, `/quick`, `review`; other stages load none.
4. Setup proposes packs; `doctor` reports missing tooling with snippets and keyword conflicts, read-only.
5. Full test suite, token budget test, and install smoke tests pass for claude-code, codex, antigravity.

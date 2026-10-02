# Best-Practice Rules (Sub-project D) — Design

Date: 2026-10-01 (revised 2026-10-02)
Status: awaiting user confirmation
Depends on:
- A (`.planning/specs/2026-10-01-workflow-token-optimization-design.md`): token budget test, merged `execute`/`review` skills.
- B+C (`.planning/specs/2026-10-01-project-profile-bootstrap-design.md`, shipped as schema 2.4): `setup detect`, `developer` agent, `stack_intent`, `/quick`, `doctor` extensions.

## Goal

Agents consistently follow language/framework best practices without raising per-task token cost beyond a fixed budget.

## Decisions

| Topic | Decision |
|---|---|
| Enforcement | Two layers: tooling (linters/typecheck, verified by `verify.checks`) first; short imperative text only for what tooling cannot check. Review uses the same packs as checklist. |
| First packs | 7: `core`, `typescript`, `python`, `react`, `nextjs`, `fastapi`, `node-api`. |
| Precedence | Project rules > framework > language > core. Packs selectable/disable-able in config. `CLAUDE.md`/`AGENTS.md` are not copied (harness loads them); conflicts only warned. |
| Impact | Every bullet has an impact level `critical`, `high`, or `medium`. Over budget, `medium` then `high` bullets are trimmed; `critical` is never trimmed. |
| Rationale | Each pack keeps a `## Why` section for maintainers. It is never injected and does not count toward the budget. |
| Loading | Deterministic CLI selects packs by task file scope; injected only into `developer` (execute, `/quick`) and reviewer prompts; ≤ 4,000 chars per task. |
| Tooling layer | Report and suggest only (`doctor`, setup dry-run). Setup never edits lint/tsconfig; changes go through `/quick` or a task. |
| Schema | 2.5, with a defaults-only migration from 2.4. |

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
- [critical] `state-location`: Keep server state in the data layer, not in components.
- [high] `effect-deps`: List every value an effect reads in its dependency array.
- `file-size`: Split a component file once it holds more than one exported component.

## Why
- `state-location`: Components that own server state duplicate caching and drift. https://react.dev/learn/...
- `effect-deps`: Missing dependencies cause stale closures.
```

- **Rule body** = every line before `## Why`. Bullets only, no rationale prose. Each bullet is `- [<impact>] \`<anchor>\`: <imperative text>`; `[<impact>]` is optional and defaults to `medium`.
- Each anchor is stable and unique within the pack, so review findings can cite `<pack>#<anchor>`.
- Body ≤ 1,500 chars; `core` ≤ 1,000. The `## Why` section is excluded from both the budget and CLI output. It holds at most one line per anchor, and only for anchors in the body.
- Content covers only what tooling cannot check (boundaries, state placement, error handling, naming, module splitting, testing approach).
- Supported `detect` keys: `package_json_deps`, `pyproject_deps`, `files_exist`. Supported `check` kinds: `tsconfig_option`, `eslint_rule` (static scan of eslint config files), `pyproject_tool` (e.g. `tool.ruff`, `tool.mypy`), `file_exists`. Unparseable configs report `unknown`, never fail.
- Maintenance policy (in `plugins/gin-workflow/src/rules/README.md`): add a rule when the same correction was needed more than twice; remove a rule once tooling enforces it or it is obsolete, naming the replacement in the commit message.

### 2. Project rules

`.agent-workflow/rules/*.md` in the consumer repo, same format (frontmatter minimum `applies_to`; `id` defaults to file stem; optional `## Why`), body ≤ 1,500 chars, highest precedence.

### 3. Configuration

```yaml
rules:
  packs: [core, typescript, react]   # proposed by setup from detect/stack_intent, user confirms
  disabled: []
```

- Missing `rules:` ⇒ `core` only.
- Schema 2.5. The 2.4 → 2.5 migration only adds defaults (no `rules:` key is written; absence means `core` only). Config readers accept 2.3, 2.4, and 2.5 (`SUPPORTED_CONFIG_VERSIONS`).

### 4. CLI

- `gin-workflow rules --files <paths...> [--format text|json]`: select enabled packs and project rules whose `applies_to` matches any path (plus `requires`, plus `core`), order by precedence, and concatenate rule bodies without `## Why`.
- Budget trimming when the total exceeds 4,000 chars. Stop as soon as the total fits:
  1. Remove `medium` bullets, from the lowest-precedence source upward (core, language, framework, then project rules last).
  2. Remove `high` bullets in the same order.
  3. Never remove `critical` bullets. If the total still exceeds 4,000 chars, return it anyway.
  Each trim step and any remaining overrun prints a warning to stderr naming the removed anchors. The exit code stays 0.
- `--format json` returns, per pack, `id`, `source` (plugin/project), the included bullets with `anchor` and `impact`, and the trimmed anchors.
- `gin-workflow rules --list`: enabled packs, source (plugin/project), body size, and bullet count per impact level.

### 5. Stage integration

- `execute` and `/quick`: orchestrator runs `gin-workflow rules --files <task scope>` and injects the result into the `developer` prompt.
- `review`: same rule set injected as checklist; the reviewer checks `critical` and `high` rules first. Findings for violations cite `<pack>#<anchor>`; a `critical` violation defaults to finding severity `high`.
- `discuss`, `plan`, `orchestrate`, `verify`, `ship`: no rules loaded.

### 6. Setup and doctor

- Setup dry-run proposes `rules.packs` from `detect` (greenfield: from `stack_intent`) and lists missing tool checks with suggested snippets.
- `/setup doctor`: runs `tool_checks` for enabled packs (read-only) and keyword-based conflict warnings between `conflict_keywords` and `CLAUDE.md`/`AGENTS.md`.
- Greenfield's first task (from B+C) uses the suggested snippets when setting up lint/typecheck/test.

## Testing

- Budget test (extends A): each pack body ≤ 1,500 (`core` ≤ 1,000), measured without `## Why`; project-rule size check in `rules --list`.
- Selection: Python-only file scope gets `core`+`python`(+`fastapi` when enabled), never `react`; project rule ordered first; `disabled` honored; `requires` co-loaded.
- Trimming: over-budget fixture removes `medium` before `high`, lowest precedence first, project rules last; `critical` bullets always survive; critical-only overrun returns full output with a warning and exit 0; trimmed anchors appear in stderr and in JSON.
- `## Why` never appears in `rules --files` output (text or JSON) and does not count toward size.
- Detect proposes correct packs on B+C fixtures (React+Vite ⇒ core, typescript, react; FastAPI ⇒ core, python, fastapi; Next.js ⇒ + nextjs).
- `tool_checks` on fixtures: tsconfig without `strict`, pyproject without ruff, eslint config missing react-hooks; unparseable config ⇒ `unknown`.
- Frontmatter and body lint: every pack has `id`, `tier`, `applies_to`; anchors unique; impact values valid; every `## Why` line names an anchor present in the body, at most once.
- Migration: a 2.4 config migrates to 2.5 unchanged apart from the version; a 2.3 config chains through 2.4 to 2.5; 2.3 and 2.4 configs still load.
- Packaging tests include `rules/` in all three harness dists.

## Out of scope

- Packs beyond the initial 7 (Go, Rust, Vue, Angular, Java/Spring, Django, testing-specific, …) — addable later without code changes.
- Suggesting new project rules from recurring review findings.
- Automatically editing project lint/type configs.
- LLM-based conflict detection.

## Acceptance criteria

1. 7 packs exist within budget, each body limited to rules tooling cannot enforce, every bullet with a valid impact and anchor.
2. `gin-workflow rules --files` returns only relevant packs in precedence order, project rules override, `## Why` is excluded, and over-budget output is trimmed by impact without ever dropping `critical` bullets.
3. `developer` and reviewer receive rules via injection in `execute`, `/quick`, `review`; reviewer prioritizes `critical`/`high`; other stages load none.
4. Setup proposes packs; `doctor` reports missing tooling with snippets and keyword conflicts, read-only.
5. Schema 2.5 with a defaults-only migration from 2.4.
6. Full test suite, token budget test, and install smoke tests pass for claude-code, codex, antigravity.

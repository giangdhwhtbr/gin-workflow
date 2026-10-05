# Rule Packs

Rule packs are short, best-practice checklists the agent follows when it writes code and the reviewer checks when it reviews. `gin-workflow rules --files <paths>` picks the packs that apply to the files in scope; `execute` gives the output to the `developer` agent, `/quick` follows it, and `review` includes it as the reviewer's checklist.

## Packs

| Pack | Tier | Applies to | Enabled |
|---|---|---|---|
| `core` | core | every file | always, unless disabled |
| `lean` | core | every file | always, unless disabled |
| `typescript` | language | `*.ts`, `*.tsx`, `*.mts`, `*.cts` | via `rules.packs` |
| `python` | language | `*.py` | via `rules.packs` |
| `react` | framework (needs `typescript`) | `*.tsx`, `*.jsx` | via `rules.packs` |
| `nextjs` | framework (needs `react`) | `app/`, `pages/`, `middleware.ts` | via `rules.packs` |
| `node-api` | framework | `*.ts`, `*.js` and variants | via `rules.packs` |
| `fastapi` | framework (needs `python`) | `*.py` | via `rules.packs` |

Setup proposes language and framework packs from what it detects (dependencies, `tsconfig.json`, `pyproject.toml`). `core` covers scope, secrets, error handling, input validation, behavior tests, reuse, naming, and single-purpose functions. `lean` asks for the shortest correct solution: reuse what exists, prefer the standard library, the platform, and installed dependencies, add nothing speculative, and never cut validation, error handling, security, accessibility, or required tests. Its ideas come from [ponytail](https://github.com/dietrichgebert/ponytail) (MIT).

## Configure

```yaml
rules:
  packs: [typescript, react]   # add packs
  disabled: [lean]             # turn a pack off, including core or lean
```

Project-specific packs go in `.agent-workflow/rules/<id>.md` and take precedence over plugin packs. `gin-workflow rules --list` shows every enabled pack with its size and rule counts.

## Format

A pack is Markdown with frontmatter (`id`, `tier`, `applies_to` globs, optional `requires`, `detect`, `tool_checks`) and one bullet per rule:

```markdown
- [critical] `scope`: Change only files in the task scope; report needed changes elsewhere instead of making them.
```

- Impact is `critical`, `high`, or `medium` (the default). Anchors are stable, and findings cite them as `<pack>#<anchor>`.
- Only the bullets before `## Why` are injected; `## Why` explains each rule in one line and is never sent.
- Rules cover only what linters and type checkers cannot enforce. Enforceable rules go in `tool_checks`, which setup reports as suggested lint or type configuration (setup never edits those configs).
- A pack body stays under 1,500 characters (`core` and `lean` under 1,000).

## Precedence and budget

Project packs win over framework, then language, then core. The rules for one task are capped at 4,000 characters: over the cap, `medium` and then `high` bullets are trimmed from the lowest precedence first. `critical` rules are never trimmed.

## How review grades findings

The reviewer checks `critical` and `high` rules first and cites violations as `<pack>#<anchor>`. A `critical` violation is recorded at `IMPORTANT` or higher. `lean` findings are graded by impact: a `high` lean rule at `IMPORTANT`, any other at `MINOR`; the finding names what to cut and what replaces it. A simplification marked with a `simplified:` comment (naming its limit and upgrade path) is not flagged.

## Maintaining packs

Add a rule when the same correction was needed more than twice; remove it once tooling enforces it or it is obsolete, naming the replacement in the commit message.

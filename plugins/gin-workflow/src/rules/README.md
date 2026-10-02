# Rule packs

Best-practice packs injected by `gin-workflow rules --files <paths>` into the `developer` agent and the reviewer. Only the bullets before `## Why` are injected.

## Format
- Frontmatter: `id` (= file stem), `tier` (`core` | `language` | `framework`), `applies_to` (globs), optional `requires`, `detect`, `conflict_keywords`, `tool_checks`.
- Body: one bullet per rule, `- [critical|high|medium] \`anchor\`: Imperative text.` Impact defaults to `medium`. Anchors are stable; findings cite `<pack>#<anchor>`.
- Body ≤ 1,500 chars (`core` ≤ 1,000). `## Why` holds at most one line per anchor and is never injected; every `critical` rule has one.
- Only rules that linters and type checkers cannot enforce. Enforceable rules belong in `tool_checks`.

## Precedence
Project rules (`.agent-workflow/rules/*.md`) > framework > language > core. Over the 4,000-char task budget, `medium` then `high` bullets are trimmed from the lowest precedence first; `critical` is never trimmed.

## Maintenance
- Add a rule when the same correction was needed more than twice.
- Remove a rule once tooling enforces it or it is obsolete; name the replacement in the commit message.

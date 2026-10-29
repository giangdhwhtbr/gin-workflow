# Docs style

How gin-workflow writes and reviews Markdown. The `docs` rule pack is the checklist; this page explains it. Condensed from [technical-writer](https://github.com/riekelt/technical-writer) (MIT).

## Truth

- Every claim traces to code, configuration, tests, or a named source. Label inference as inference.
- A team practice the code does not enforce is a convention, and the page says so.
- Each fact has one home; other pages link to it.
- Each page has one class: normative (what must be), descriptive (what the code does at HEAD), historical (dated, never updated), runbook (steps someone runs), reference (complete over its scope).

## Sentences and headings

- Conclusion first. One claim per sentence, at most 35 words, active voice with a named actor.
- One term per concept. A number or a named property instead of an adjective. Plain verbs (use, not leverage).
- Headings are sentence-case noun phrases; an imperative above a procedure; the verbatim error above a troubleshooting entry. No numbers; no questions outside a FAQ.
- A table only when items share two or more properties. No heading above every paragraph.

## Banned constructions

| Pattern | Repair |
|---|---|
| Antithesis ("not X, but Y") | State Y |
| Importance or recap ("It is worth noting", "In summary") | Delete; state the fact |
| Throat clearing, filler ("basically", "simply") | Delete |
| Promotional or inflated words ("powerful", "seamless", "robust") | A number or a named property |
| Trailing participle ("..., ensuring reliability") | A separate sentence with evidence, or delete |
| Stacked hedges ("might possibly") | One hedge, or the fact |
| Vague attribution ("experts say") | Name the source |
| Em or en dashes, bold-label list items, emoji | Commas, colons, plain items |
| Assistant residue ("Let me", "I hope this helps") | Delete |
| Plan or prompt wording copied into the page | Write the content it asked for |

## Runbooks

- A procedure is numbered steps, each one action with its expected result.
- A troubleshooting entry starts from the verbatim symptom, then the cause, then the fix.
- A migration guide has a table mapping old to new, and a rollback section.

## Reviewing docs

- Check each claim against the code, not only the diff, and cite `file:line`.
- A claim the code contradicts, a practice written as tool behavior, a fact restated instead of linked, copied plan wording, or a missing required section: `IMPORTANT` or higher.
- A style rule: `MINOR`, unless it changes the meaning.
- Do not flag quoted material, code blocks, an example that shows a banned phrase, or a section a template requires.

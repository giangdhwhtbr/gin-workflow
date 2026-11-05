# Codebase glossary for legacy migrations

Workflow: codebase-glossary
Status: draft for user review.

## Goal and scope

A team rebuilds a legacy system whose code, UI, and database use Korean (later possibly other languages) as a new application that must match it one to one. Both live in one monorepo: `legacy/` holds several legacy repositories, the new application holds several new repositories, and specs, plans, and codebase docs sit at the monorepo root. Every epic of the new application must name the same business concept with the same English term. Today nothing in gin-workflow collects those terms: `/tech-doc` checks that its own pages use consistent terms (step 7) but writes no glossary, and `skills/tech-doc/SKILL.md` states that other stages look code up on demand instead of reading its pages, so a glossary written there would never reach `discuss`, `plan`, or `execute`.

This spec adds:
- an eleventh page in the tech-doc set, `11-GLOSSARY.md`, collected by the existing scouts and merged across runs into one file for the whole monorepo;
- a plugin rule pack `glossary` that makes developers and reviewers use the confirmed English terms;
- one line each in `discuss` and `plan` so specs and plans use the same terms.

Out of scope:
- A separate `/glossary` skill or a second pass over the legacy code.
- A machine-readable copy (YAML, CSV) or code generation from the glossary, such as i18n keys. Add it when the new application needs one.
- A CLI command to confirm terms. The user edits the file.
- A column for code identifiers in the new application. Identifiers derive from the `English` column under each new repository's `08-CONVENTIONS.md`.
- Enabling the pack automatically. A project opts in with `rules.packs`.
- Version bumps of the CLI or launcher. They happen at release, per `docs/contributing.md`.

## Requirements

### R1. Template `11-GLOSSARY.md`

New file `plugins/gin-workflow/src/templates/codebase/11-GLOSSARY.md`, read through `gin-workflow specs template codebase/11-GLOSSARY.md` like the other pages, so `.agent-workflow/templates/` overrides apply. It keeps the shared header (`Analysis Date`, `Scope`, `Evidence`, `Index Use`) and footer (`Inference And Uncertainty`, `Follow-up`), with two tables between them:

```
## Terms

| Term | Lang | English | Meaning | Legacy identifiers | Evidence | Status |
|---|---|---|---|---|---|---|

## Conflicts

| Term | Lang | Existing English | Candidate | Evidence |
|---|---|---|---|---|
```

- `Term` is the source-language term as the legacy system writes it; `Lang` is its ISO 639-1 code (`ko`). A new language needs no other change.
- `Legacy identifiers` lists code, table, and column names that carry the term (romanized identifiers included).
- `Evidence` cites `file:line`.
- `Status` is `proposed` or `confirmed`.
- Rows sort by `Lang`, then `Term`.

### R2. Collection and merge in `/tech-doc`

`plugins/gin-workflow/src/skills/tech-doc/SKILL.md` changes:
- The split-set table gains the row `11-GLOSSARY.md`: business concepts, statuses, roles, screen names, and field labels in a non-English source language, with the proposed English term. It is written only when the scope contains such terms; otherwise its number stays unused, as for `05-API.md`.
- Scouts tag notes `glossary` for terms found in UI strings and i18n files, table and column names and comments, enum values, romanized identifiers, and code comments. Not every UI string is a term: only names of business concepts.
- The writer route for `11-GLOSSARY.md` is the middle model.
- The glossary always lives at the root of the codebase folder (`.planning/codebase/`, or `artifacts.codebase` with the SDD layout), also when the run covers one subsystem and its other pages go to `<scope-slug>/`. One file serves the whole monorepo.
- Merge rules when the file exists: one row per (`Term`, `Lang`); a new row is always `proposed`; a `confirmed` row's `English` never changes, and a run only adds `Evidence` and `Legacy identifiers` to it; a different meaning or translation found for an existing row goes to `Conflicts` instead of changing the row; `Scope` accumulates the scopes that contributed.
- Regrounding fixes `Evidence` citations. A row left without evidence moves to `Follow-up`; it is never deleted.
- Step 7 reports the number of new `proposed` rows and of `Conflicts`, and, when `glossary` is not in `rules.packs`, tells the user to add it.

The user confirms a translation by editing `Status` to `confirmed` and committing. A conflict is resolved by the user, for example by splitting the term into two rows whose `Meaning` names the context.

### R3. Rule pack `glossary`

New file `plugins/gin-workflow/src/rules/glossary.md`:
- frontmatter `id: glossary`, `tier: framework`, `applies_to: ["**/*"]`, `detect: {files_exist: [.planning/codebase/11-GLOSSARY.md, docs/codebase/11-GLOSSARY.md]}`, so `/setup` proposes it once the glossary exists;
- `[critical] glossary-names`: name business concepts in code identifiers, UI text, and docs with the `English` of their row in `11-GLOSSARY.md` of the codebase docs folder;
- `[high] glossary-gaps`: a concept with no row, or only a `proposed` one, is reported in the handoff, not named freely; the developer does not edit the glossary (outside the task scope, `core#scope`);
- a `## Why` section, and a body under 1,500 characters.

A project enables it with `rules.packs: [glossary]`. A custom `artifacts.codebase` path is not detected; the project adds the pack by hand.

### R4. `discuss` and `plan`

- `plugins/gin-workflow/src/skills/discuss/SKILL.md`: when `11-GLOSSARY.md` exists in the codebase docs folder, the spec names business concepts with its `confirmed` English terms; a missing term is added to the glossary as `proposed` and listed in the spec's assumptions.
- `plugins/gin-workflow/src/skills/plan/SKILL.md`: track briefs use the glossary's `confirmed` English terms.
- Each stage stays within the 12,000-character stage budget (`tests/workflow_core/test_token_budget.py`); today `discuss` is 8,154 and `plan` 10,685.

### R5. Documentation and builds

- `docs/guides/rules.md`: a `glossary` row in the pack table (any file; via `rules.packs`; proposed by setup when the glossary exists).
- `docs/starters/brownfield-walkthrough.md`: the tech-doc step lists `GLOSSARY` among the files it produces, and says when the legacy system uses a non-English language: review `11-GLOSSARY.md`, set the translations you accept to `confirmed`, resolve `Conflicts`, and enable `rules.packs: [glossary]` before the first `/discuss`.
- `docs/reference/skills.md`: the `tech-doc` row names the glossary among the pages it writes.
- No other page describes the tech-doc set, the plugin pack list, or what `discuss` and `plan` read; the only translation, `docs/index.vi.md`, does not either, so it is unchanged.
- Rebuild `plugins/*/dist/` so every harness ships the template, the pack, and the skill text.

## User Stories

### US-1: Collect legacy terms into one glossary
As a migration lead, I want `/tech-doc` to collect the business terms of every legacy repository into one glossary with a proposed English term and a citation each, so that I review translations once for the whole monorepo.

Acceptance criteria:
- Running `/tech-doc` on a legacy subsystem writes or updates `.planning/codebase/11-GLOSSARY.md`, not a file under `<scope-slug>/`.
- Every new row has `Status` `proposed` and a `file:line` in `Evidence`.
- Running it on a second legacy repository adds rows to the same file and lists both scopes in `Scope`.

### US-2: Keep confirmed translations across runs
As a migration lead, I want my confirmed translations to survive later runs, so that a re-run never changes a term the new application already uses.

Acceptance criteria:
- A re-run never changes the `English` of a `confirmed` row.
- A different meaning or translation found for an existing term appears in `Conflicts`, and the existing row is unchanged.
- Regrounding moves a row without evidence to `Follow-up` instead of deleting it.

### US-3: New application uses the confirmed terms
As a developer of the new application, I want specs, plans, code, and reviews to use the confirmed English terms, so that every epic names the same concept the same way.

Acceptance criteria:
- With `rules.packs: [glossary]`, `gin-workflow rules --files <any file>` prints the `glossary-names` rule.
- `/setup` proposes the `glossary` pack when `.planning/codebase/11-GLOSSARY.md` or `docs/codebase/11-GLOSSARY.md` exists, and not otherwise.
- `discuss` and `plan` name business concepts with the glossary's `confirmed` terms, and `discuss` adds a missing term as `proposed`.
- A developer who meets a term without a confirmed row reports it in the handoff and leaves the glossary unchanged.

## Errors and compatibility

- No glossary: `discuss` and `plan` skip the step, and setup does not propose the pack. Projects without non-English terms see no change.
- Existing tech-doc folders keep their files; `11-GLOSSARY.md` is added only when the scope has such terms. Numbers 01 to 10 do not change.
- Size: one Markdown file stays greppable at a few thousand rows. Beyond that, split by `Lang`.
- `tier: framework` only sets precedence and trimming order; `glossary-names` is critical and never trimmed.

## Testing

- `tests/workflow_core/test_tech_doc_skill.py`: `READING_ORDER` gains `GLOSSARY`; new assertions that the skill writes the glossary at the codebase folder root for subsystem runs and never changes a `confirmed` row's `English`.
- `tests/workflow_core/test_token_budget.py`: the plugin pack set includes `glossary`, its body is within budget, and `discuss` and `plan` stay within 12,000 characters.
- `tests/workflow_core/test_rules_checks.py`: `propose_packs` includes `glossary` for a repository with `.planning/codebase/11-GLOSSARY.md` or `docs/codebase/11-GLOSSARY.md`, and not without.
- `tests/workflow_core/test_rules.py`: with `rules.packs: [glossary]`, the rules for any path include `glossary`.
- `gin-workflow docs check` on the three changed pages exits 0, and `mkdocs build --strict` passes.
- Full suite `python3 -m pytest -n auto`, including the harness packaging tests over `dist/`.

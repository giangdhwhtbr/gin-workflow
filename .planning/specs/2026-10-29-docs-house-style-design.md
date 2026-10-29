# Docs house style and grounding in gin-workflow core

Epic: gin-workflow-46ns
Status: draft for user review.

## Goal and scope

gin-workflow writes and reviews documentation with its own rules, so the technical-writer plugin (github.com/riekelt/technical-writer, MIT, v1.8.4) can be uninstalled. The useful parts of that plugin move into gin-workflow's existing mechanisms: a rule pack, a shared reference file, and the `tech-doc` skill. README Credits already name technical-writer.

Evidence for what to port comes from epic `gin-workflow-tvf5` (notes on this epic). Its prose reviews caught 7 warnings that style greps missed. Most were claims the code does not back, practices written as behavior, and one fact stated in two places that drifted. The rules below put those checks first.

Out of scope:
- A CLI command, git hook or test that checks Markdown style. The reviewer checks the mechanical rules (dashes, bold-label list items, emoji, numbered headings); this repository's own docs get a test in epic `gin-workflow-9pl2`.
- A new agent or skill set; design-doc, issue, ADR, changelog and postmortem formats; PlantUML or ArchiMate diagrams (docs use Mermaid).
- Restyling existing pages. Epic `gin-workflow-9pl2` applies the rules to the docs after this epic ships.

## Requirements

### R1. A `docs` rule pack, loaded by default for Markdown

- New pack `plugins/gin-workflow/src/rules/docs.md`: `id: docs`, `tier: core`, `applies_to: ["**/*.md"]`. Its body is at most 1,500 characters (the default limit) and follows the pack format in `plugins/gin-workflow/src/rules/README.md`.
- `workflow_core/rules.py`: `DEFAULT_PACKS` becomes `("core", "lean", "docs")`. The pack is selected only when a file in scope matches `**/*.md`. `rules.disabled: [docs]` turns it off, like `core` and `lean`.
- The bullets, most important first:
  - `[critical]` every statement matches the code, configuration or tests; commands, paths, flags and defaults are checked against them;
  - `[high]` a team practice the code does not enforce is labelled a convention;
  - `[high]` each fact lives on one page, and other pages link to it;
  - `[high]` a plan step or prompt describes the content to write; its wording is not copied into the page;
  - the conclusion comes first in each section, one claim per sentence, at most 35 words;
  - headings are sentence-case noun phrases, without numbers or questions;
  - no promotional, inflated or filler words; a number or a named property replaces an adjective;
  - no em or en dashes, no list items that open with a bold label, no emoji markers;
  - one term per concept throughout a page.
- `## Why` explains the critical rule. The exact wording is set in the plan, within the character limit.

### R2. A shared reference, `plugins/gin-workflow/src/references/docs-style.md`

A condensed rewrite (not a copy) of technical-writer's style, truth and review rules, with a credit line. The `review` skill links it, so it counts toward the review stage's 12,000-character instruction budget (`tests/workflow_core/test_token_budget.py`); the review chain is 7,944 characters today, so the file stays under 3,500 characters. Sections:
- Truth: every claim traces to code, configuration, tests or a named source; inference is labelled; practices are labelled conventions; one fact, one home; the document classes, each with its rule: normative (states what must be), descriptive (matches the code at HEAD), historical (dated, not updated), runbook (ordered steps someone executes), reference (complete over its scope).
- Sentences and headings: conclusion first, one claim per sentence, active voice with a named actor, one term per concept, numbers over adjectives, plain verbs; headings are noun phrases by default, imperative above a procedure, the verbatim symptom in a troubleshooting entry, no question headings outside a FAQ; tables only when items have two or more properties to compare; no heading above every paragraph.
- Banned constructions: one table of pattern and repair. It covers antithesis, importance announcements, recap sentences, throat clearing, filler, inflated and promotional words, trailing participle analysis, stacked hedging, vague attribution, dashes, bold-label list items, emoji markers, assistant residue, and copied plan or prompt wording.
- Runbooks: a procedure is numbered steps with expected results; troubleshooting entries start from the symptom the reader sees (the verbatim error), then cause, then fix; a migration guide has a mapping table from old to new and a rollback section.
- Reviewing docs: severities (a claim the code contradicts, a practice written as tool behavior, or a missing required section is IMPORTANT or higher; a style rule is MINOR unless it changes meaning), and what not to flag (quoted material, code blocks, examples that show a banned phrase, template-required sections).

### R3. Writers and reviewers load the rules

- `skills/tech-doc/SKILL.md`: before writing, run `gin-workflow rules --files <pages to write>` and read `references/docs-style.md`.
- `agents/docs-writer.md`: follow the rules checklist passed in the handoff and the plugin reference `references/docs-style.md`. The agent has no shell, so it asks for the checklist when none was passed.
- `skills/review/SKILL.md`: one line in the reviewer steps: for Markdown files, check each factual claim against the code and grade findings per `references/docs-style.md`.

### R4. Regrounding mode in `/tech-doc`

`/tech-doc` gains a mode for existing documentation, started when the user asks to reground (re-check) pages or a docs folder. For each page:
1. List its factual claims (commands, flags, paths, defaults, behavior).
2. Check each claim against the code at HEAD and note the evidence as `file:line`, or note that nothing backs it.
3. Fix a wrong claim, remove a claim nothing backs, or label it a convention when it describes team practice.
4. Report per page: claims checked, claims fixed, claims removed, and open questions.

The mode writes only the pages in scope; it does not add sections or restyle pages beyond the claims it fixes, unless the request says so.

### R5. Documentation of the change

- `docs/guides/rules.md`: a `docs` row in the packs table (tier core, applies to `*.md`, always unless disabled), one sentence on what it covers, and its credit to technical-writer. The Configure example's `disabled` comment names `docs` with `core` and `lean`.
- `docs/reference/skills.md`: the `tech-doc` row mentions the regrounding mode.
- `plugins/gin-workflow/src/rules/README.md`, `docs/reference/cli.md` (`rules`) and `docs/reference/config.md` (`rules`): `core`, `lean` and `docs` load by default.

## User Stories

### US-1: Docs rules reach the developer and the reviewer
As a developer running a track that edits Markdown, I want the docs rules in my rules checklist, so that I write pages that match the code and the house style without a separate plugin.

Acceptance criteria:
- `gin-workflow rules --files README.md` includes the `docs` pack; `gin-workflow rules --files src/app.py` does not.
- With `rules.disabled: [docs]` in `.agent-workflow/config.yaml`, `gin-workflow rules --files README.md` omits it.
- `gin-workflow rules --list` shows `docs` as enabled by default.

### US-2: One reference for writing and reviewing docs
As an agent writing or reviewing documentation, I want one reference with the style, truth and review rules, so that writer and reviewer apply the same rules.

Acceptance criteria:
- `references/docs-style.md` exists in the plugin and has the sections of R2.
- `tech-doc`, `docs-writer` and `review` each link to it, and the link resolves in the plugin tree.

### US-3: Reground existing docs
As a maintainer, I want `/tech-doc` to check existing pages against the code, so that stale or invented claims are found and fixed with evidence.

Acceptance criteria:
- `tech-doc/SKILL.md` describes the regrounding mode with the four steps and the per-page report of R4.
- `docs/reference/skills.md` mentions the mode.

## Errors and compatibility

- Existing projects get the `docs` pack on their next tasks that touch Markdown, because it is on by default. It uses up to 1,500 of the 4,000-character task budget. As a `core`-tier pack it is trimmed before project, framework and language packs; its critical rule is never trimmed. `rules.disabled: [docs]` restores the old behavior.
- Tests that assert the default pack list (`core`, `lean`) change to include `docs`.
- A malformed pack fails `test_rule_packs`, as for every packaged pack.

## Testing

- `tests/workflow_core/test_rule_packs.py`: the docs pack passes the existing format checks. A new check asserts it applies to `**/*.md` only and is in `DEFAULT_PACKS`.
- `tests/workflow_core/test_rules.py`: `--files README.md` selects `docs`; `--files src/app.py` does not; `rules.disabled: [docs]` removes it; `--list` shows it.
- A test asserts that `tech-doc/SKILL.md`, `agents/docs-writer.md` and `review/SKILL.md` link to `references/docs-style.md`, and that the file exists.
- `tests.workflow_core.test_docs_coverage` passes with the doc updates.
- Full suite: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all`.

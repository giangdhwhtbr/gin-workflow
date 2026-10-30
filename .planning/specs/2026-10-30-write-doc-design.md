# Write-doc skill

Epic: none
Workflow: write-doc
Status: draft for user review.

## Goal and scope

Add one general-purpose skill, `write-doc`, that writes or updates a repository document on request: README, runbook, setup guide, ADR, or a document of another shape the user describes. It is not part of the lifecycle: it reads no workflow state, creates no Beads task, and records no gate. It can run at any time, on any branch.

Out of scope:
- Repository analysis for legacy migration (sub-project B: screen inventory, controller and API mapping, complexity, dependency map). It gets its own spec.
- A reviewer agent. Self-review only.
- Changes to `tech-doc`. It keeps producing codebase documentation under `.planning/codebase/`.
- Changes to the CLI.

## Requirements

- R-1: `write-doc` takes a free-form request and a target path (optional).
- R-2: It selects the document type from the table below. A request that matches no type is written in the shape the user describes, with the same rules.
- R-3: It loads the template for the chosen type with `gin-workflow specs template <name>`, which honors `.agent-workflow/templates/` overrides. It loads the style rules from `references/docs-style.md`, already in the plugin and already condensed from technical-writer.
- R-4: If the target file exists, it updates the file in place and keeps sections the request did not name. It does not overwrite the whole file.
- R-5: Before reporting, it checks the draft against the `docs` rule pack (`gin-workflow rules --files <path>`) and against the self-review checklist below.
- R-6: It reports the file written and the checklist result. It does not commit unless the user asks.

Document types:

| Type | Template | Status |
|---|---|---|
| README | `readme.md` | New template |
| Runbook (including setup guides) | `runbook.md` | New template |
| ADR | `adr.md` | Exists |
| Other | none | Shape from the user's request |

Self-review checklist:
- No placeholder text (TBD, TODO, `{{`).
- Every link resolves to a file or anchor that exists.
- Every command is marked as run (with its output summarized) or not run.
- Every factual claim cites a file and line, or is labeled as inference.
- Style rules from `docs-style.md` pass.

## User Stories

### US-1: Update a README

As a maintainer, I want to ask for a README update, so that the page matches the current code without my writing it by hand.

Acceptance criteria:
- Given a request "update README install section", when the skill runs, then only the install section changes and the other sections stay byte-identical.
- Given the README lists a command that the repository no longer has, when the checklist runs, then the skill removes the command or marks it as stale, and says which one.

### US-2: Write a runbook

As an operator, I want a numbered runbook for a procedure, so that someone can execute it under time pressure.

Acceptance criteria:
- Given a request "write the release runbook", when the skill runs, then the file uses the `runbook.md` template and each step has one action and one expected result.
- Given a troubleshooting entry, when the skill writes it, then the verbatim symptom comes first, then the cause, then the fix.

### US-3: Write an ADR

As a team member, I want a decision recorded, so that the reason for it survives after the chat ends.

Acceptance criteria:
- Given a decision with no file, when the skill runs, then it creates `docs/adr/NNNN-<slug>.md` from `adr.md`, with the next free number.
- Given a request for a type the table does not list, when the skill runs, then it asks one question about the expected shape and writes nothing until the user answers.

## Errors and compatibility

- Template missing for a listed type: stop and report the missing name. Do not invent the template structure.
- Target path exists and the request does not name a section: ask which section to change before writing.
- The skill never runs `gin-workflow record` and never changes state, so it works in a repository that has no effective config. It does not stop for `/setup`.
- Existing `tech-doc` output and `docs-style.md` stay unchanged except for the two new templates.
- `docs/reference/skills.md` gets one row for `write-doc` in a new "Documentation" section.

## Testing

- Unit: the template selection table maps each listed type to its template name, and an unknown type returns the ask-one-question path. Keep it to a small `assert`-based check in `tests/`, following the existing tests under `tests/workflow_core/`.
- Fixture run: on a fixture repository, run each US acceptance criterion once and inspect the output. Check that US-1 leaves other sections byte-identical.
- Template check: `gin-workflow specs template readme.md` and `runbook.md` return the new templates, and an override in `.agent-workflow/templates/` replaces them.
- Rules check: `gin-workflow rules --files docs/...` runs against a generated document without error.

## Inference And Uncertainty

- Assumed: the plugin discovers a new skill folder under `plugins/gin-workflow/src/skills/` without a manifest edit. Verify against an existing skill's registration before implementation.
- Assumed: the `docs` rule pack already covers README and runbook shapes. Verify with `gin-workflow rules --files docs/README.md`.

## Follow-up

- Sub-project B (legacy migration analysis) needs its own discussion. Its output set (screen inventory, controller and API map, complexity, screen dependency map, migration checklist) is not in this spec.

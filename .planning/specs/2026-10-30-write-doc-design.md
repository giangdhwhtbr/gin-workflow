# Write-doc skill and docs check command

Workflow: write-doc
Status: draft for user review.

## Goal and scope

Every team member who asks for a standalone document gets the same structure and the same checks, from one plugin. Epic `gin-workflow-46ns` moved technical-writer's style into gin-workflow (`references/docs-style.md`, the `docs` rule pack, regrounding in `/tech-doc`) and left document formats and a standalone writing entry point out of scope. This spec adds them.

Output is stable when three things hold: the same request reaches the same skill, each document type starts from a fixed template, and "done" is a check a machine runs with the same result for everyone. This spec delivers one item for each:
- one skill, `write-doc`, that triggers on requests to write or update a README, runbook or guide, ADR, or changelog;
- templates `readme.md`, `runbook.md`, and `changelog.md` beside the existing `adr.md`;
- a command, `gin-workflow docs check`, that reports mechanical findings as `file:line: rule`.

Out of scope:
- The migration inventory for legacy code (sub-project 2, see Follow-up). It gets its own spec and plan.
- Specs and plans (`discuss`, `plan`), codebase documentation (`tech-doc`), and issues (Beads).
- A reviewer agent. The machine check plus one read-through by the writing agent closes the loop.
- Uninstalling technical-writer. Teams remove it so that `write-doc` is the only skill that answers a docs request; this is a convention, and no code enforces it.
- Version bumps of the CLI or launcher. They happen at release, per `docs/contributing.md`.

## Requirements

### R1. Skill `write-doc`

`plugins/gin-workflow/src/skills/write-doc/SKILL.md`. Its frontmatter description triggers on requests to write or update a README, runbook, setup or how-to guide, troubleshooting page, migration guide, ADR, changelog, or release notes, and names what it does not handle: specs and plans, codebase documentation (`/tech-doc`), issues, and docs edits inside a lifecycle track. The description stays at or under 350 characters (all skill descriptions share a 4,000-character budget; 3,074 are used).

The skill runs these steps:
1. Classify the request: document type (table below), target path, and new file or update. Ask one question only when the type or the target cannot be inferred. A request that describes a shape outside the table is written without a template, under the same rules.
2. Gather evidence from the code, configuration, and scripts the document describes: `codegraph explore` when `.codegraph/` exists, otherwise grep and read. Check every command, path, flag, and default the document states against the repository.
3. Load the template with `gin-workflow specs template <name>`, the rules with `gin-workflow rules --files <target>`, and `references/docs-style.md`.
4. Write. A new file starts from the template. In an existing file, change only the sections the request names and leave every other line unchanged; do not restructure the file unless the request asks for it.
5. Run `gin-workflow docs check <target>`, with `--template <name>` for a new file, and fix every finding until it exits 0. Then read the page once against `docs-style.md` for the rules a machine cannot check, first of all that each claim matches the code.
6. Report: the file written, the sections changed, the evidence files, the commands checked against the repository and those that were not, and the `docs check` output.

The skill never records a gate, never creates a Beads task, never stops for `/setup`, and commits only when the user asks.

| Type | Template | Default target |
|---|---|---|
| README | `readme.md` | `README.md` in the repository or module root |
| Runbook or guide (setup, procedure, troubleshooting, migration guide) | `runbook.md` | `docs/runbooks/<slug>.md` |
| ADR | `adr.md` (exists) | `artifacts.adr` from `.agent-workflow/config.yaml`, default `docs/adr`; file `NNNN-<slug>.md` with the next free number |
| Changelog or release notes | `changelog.md` | `CHANGELOG.md` in the repository root; a new entry goes above the previous ones |
| Other | none | the path the user gives |

### R2. Templates

New files under `plugins/gin-workflow/src/templates/`. Headings follow the `docs` rule pack: sentence case, no numbers, no questions. `docs check --template` requires the `##` headings with literal text; a heading with a placeholder (the changelog entry) varies per page and is not required.
- `readme.md`: `# {{title}}`, then `## Purpose`, `## Install`, `## Usage`, `## Configuration`, `## Development`, `## License`.
- `runbook.md`: `# {{title}}`, then `## Purpose`, `## Prerequisites`, `## Steps` (numbered; each step one action and its expected result), `## Verification`, `## Rollback`, `## Troubleshooting` (each entry: the verbatim symptom as a `###` heading, then cause, then fix). A comment in the template says that a migration guide adds `## Old to new` with a mapping table before `## Steps`.
- `changelog.md`: `# Changelog`, then one entry `## [{{version}}] - {{date}}` with `### Added`, `### Changed`, `### Fixed`, `### Removed`. The bracketed version keeps the heading from starting with a digit.

### R3. Command `gin-workflow docs check`

`gin-workflow docs check <file>... [--template NAME] [--repository PATH] [--format text|json]`, in a new module `plugins/gin-workflow/src/scripts/workflow_core/docs_check.py`, registered as the top command `docs` in `workflow_core/cli.py`.

Checks, all outside fenced code blocks:
- style: the four mechanical rules now in `tests/workflow_core/test_docs_coverage.py` (`dash`, `bold-label item`, `emoji`, `numbered heading`). `STYLE_RULES` and `style_violations` move into `docs_check.py` unchanged, and the test imports them from there.
- `placeholder`: `{{...}}`, or `TBD` or `TODO` as a whole word, with inline code spans removed first.
- `dead link`: a relative Markdown link whose file part does not exist relative to the page; links with a scheme (`https:`, `mailto:`) and anchor-only links are skipped. Same logic as `test_relative_links_resolve`.
- `missing section`: with `--template NAME`, each `##` heading line of the template without a `{{` placeholder (from `specs.template_text`, so overrides in `.agent-workflow/templates/` apply) that does not appear as a line in the file.

Output: text lines `<file>:<line>: <rule>` (`<file>: missing section: <heading>` for the template check), or with `--format json` `{"status": "ok"|"findings", "findings": [...]}` as `specs` prints. Exit 0 when no findings, 1 when findings, 2 when a file does not exist or the template is unknown (message on stderr). The command reads no workflow configuration, so it runs in a repository without `.agent-workflow/`.

### R4. Documentation

- `docs/reference/skills.md`: a new section `## gin-workflow: documentation` after the setup and maintenance table, holding the `tech-doc` row (moved from setup and maintenance) and a new `write-doc` row.
- `docs/reference/cli.md`: a `` ## `gin-workflow docs` `` section after `gin-workflow specs`, with the synopsis, the four checks, the output format, and the exit codes.

## User Stories

### US-1: Update a README section
As a maintainer, I want to ask in plain words for a README update, so that the page matches the current code without my writing it by hand.

Acceptance criteria:
- A request "update the install section of README.md" triggers `write-doc` without a slash command.
- Only the install section changes; every other line of the file is unchanged.
- A command the section lists that the repository no longer has is removed or reported, by name, in the skill's report.

### US-2: Write a runbook
As an operator, I want a runbook in a fixed shape, so that someone can follow it under time pressure and every team member's runbook looks the same.

Acceptance criteria:
- A new runbook has the sections of `runbook.md`, and `gin-workflow docs check <file> --template runbook.md` exits 0 on it.
- Each step in `## Steps` has one action and one expected result.
- Each troubleshooting entry opens with the verbatim symptom, then the cause, then the fix.

### US-3: Record a decision
As a team member, I want a decision written as an ADR, so that the reason survives after the chat ends.

Acceptance criteria:
- The ADR is created under `artifacts.adr` when the config sets it, otherwise under `docs/adr`, as `NNNN-<slug>.md` with the next free number.
- The file has every `##` section of `adr.md`.

### US-4: Add a changelog entry
As a release owner, I want a changelog entry in one format, so that release notes read the same from release to release.

Acceptance criteria:
- The entry is added above the previous entries of `CHANGELOG.md`, and the file is created from `changelog.md` when it does not exist.
- The entry heading is `## [<version>] - <date>` and groups changes under `Added`, `Changed`, `Fixed`, and `Removed`, leaving out empty groups.

### US-5: One check for everyone
As a team lead, I want a command that gives every member the same verdict on a page, so that "done" does not depend on who ran the agent.

Acceptance criteria:
- `gin-workflow docs check` reports each of the seven rules with `file:line` (or the missing heading), nothing inside fenced code, and no placeholder or link inside inline code.
- It exits 0, 1, or 2 as R3 states, in a repository with and without `.agent-workflow/`.
- `tests/workflow_core/test_docs_coverage.py` imports `style_violations` from `workflow_core.docs_check`, and its existing tests pass unchanged.

## Errors and compatibility

- Unknown template name: `docs check` exits 2; the skill stops and names the template instead of inventing its structure.
- An existing file that does not follow its template is updated in place; `--template` is not passed for it, so its missing sections are not reported.
- Adding `docs` to `TOP_COMMANDS` adds it to the usage line; `test_every_cli_subcommand_has_a_heading` then requires the R4 heading in `cli.md`.
- `test_every_skill_is_in_the_skills_reference` requires the `write-doc` row.
- Existing projects get the new skill and command on the next `install.sh`; nothing in their configuration changes.
- Epic `gin-workflow-rm-process-hygiene` lists "an ADR template for the legacy layout". After this ships, `write-doc` places ADRs under `artifacts.adr` in either layout; that item is narrowed to whatever remains.

## Testing

- `tests/workflow_core/test_docs_check.py` (new):
  - each of the seven rules reported with the right line; none reported inside a fenced block, and no placeholder or link reported inside inline code;
  - a relative link to an existing file, an `https:` link, and an anchor-only link are not reported;
  - `--template runbook.md` reports a missing `## Rollback` and passes when it is present; a project override in `.agent-workflow/templates/runbook.md` changes the required headings;
  - CLI through the launcher: exit 0 on a clean page, 1 with `file:line: rule` text, 2 for a missing file and for an unknown template, JSON shape with `--format json`, run in a temporary repository with no `.agent-workflow/`.
- `tests/workflow_core/test_specs.py`: `readme.md`, `runbook.md`, and `changelog.md` join the shipped-templates loop in `test_pm_and_ba_templates_ship_and_can_be_overridden`.
- A test asserts that each new template passes `docs check` on its own headings once its placeholders are filled, so the templates obey the rules they enforce.
- `tests/workflow_core/test_write_doc_skill.py` (new), in the style of `test_tech_doc_skill.py`: the skill names the four templates, `specs template`, `rules --files`, `docs-style.md`, `docs check`, `artifacts.adr`, and the update-in-place rule; its description stays at or under 350 characters.
- `tests/install_smoke_test.sh`: the built Claude Code plugin contains `skills/write-doc/SKILL.md`.
- Full suite: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py`, and `bash tests/install_smoke_test.sh`.

## Follow-up

Sub-project 2, migration inventory for legacy code, needs its own `/discuss`. Re-evaluated requirement, from the legacy Java JSP to React case:
- Root cause in `tech-doc` today: scout recipes for screens look for SPA calls (`fetch`, axios, GraphQL) and miss JSP pages, `web.xml` and `struts-config.xml` mappings, Spring `@RequestMapping`, form posts, `jsp:include`, forwards, and redirects; output is split by topic, not by screen; no rule scores complexity; only the API has a completeness check.
- Needed output: a screen inventory with stable IDs; per screen, the trace URL to controller or action to service to API or data, each with `file:line`; complexity from a fixed counting rubric so two members score a screen the same; a navigation graph (forward, redirect, include, link, form target) as an adjacency table plus Mermaid per module; a coverage ledger reconciling counts (JSP files, action mappings, controllers) against inventory rows; a migration status column; output that `/roadmap` can turn into epics.

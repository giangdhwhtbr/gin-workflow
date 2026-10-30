---
name: write-doc
description: Use when asked to write or update a standalone document - README, runbook, setup or how-to guide, troubleshooting page, migration guide, ADR, changelog, or release notes. Not for specs or plans, codebase docs (/tech-doc), issues, or docs edits inside a lifecycle track.
---

# Write Doc

Write or update one standalone document so that every team member gets the same structure and the same checks. This skill sits outside the lifecycle: it never records a gate, never creates a Beads task, never stops for `/setup`, and commits only when the user asks.

## Document types

| Type | Template | Default target |
|---|---|---|
| README | `readme.md` | `README.md` in the repository or module root |
| Runbook or guide (setup, procedure, troubleshooting, migration guide) | `runbook.md` | `docs/runbooks/<slug>.md` |
| ADR | `adr.md` | `artifacts.adr` from `.agent-workflow/config.yaml`, default `docs/adr`; file `NNNN-<slug>.md` with the next free number |
| Changelog or release notes | `changelog.md` | `CHANGELOG.md` in the repository root; a new entry goes above the previous ones |
| Other | none | the path the user gives |

## Steps

1. Classify the request: document type, target path, and new file or update. Ask one question only when the type or the target cannot be inferred. A request that describes a shape outside the table is written without a template, under the same rules.
2. Gather evidence from the code, configuration, and scripts the document describes: `codegraph explore "<question>"` when `.codegraph/` exists, otherwise grep and read. Check every command, path, flag, and default the document states against the repository.
3. Load the template with `gin-workflow specs template <name>`, the rules with `gin-workflow rules --files <target>`, and [references/docs-style.md](../../references/docs-style.md).
4. Write. A new file starts from the template; fill every placeholder. In an existing file, change only the sections the request names and leave every other line unchanged; restructure the file only when the request asks for it.
5. Run `gin-workflow docs check <target>`, adding `--template <name>` for a new file, and fix every finding until it exits 0. Then read the page once against `docs-style.md` for what the command cannot check, first of all that each claim matches the code.
6. Report: the file written, the sections changed, the evidence files, the commands checked against the repository and those that were not, and the `docs check` output.

When a template is unknown, `docs check` exits 2: stop and name the template instead of inventing its structure.

---
name: explain
description: Write one interactive HTML page explaining an SDD capability or change, with a short narrative.
---

# Explain

On `/explain <capability|change>` only. It writes one generated page under `.agent-workflow/runtime/explain/`, which `gin setup` ignores.

1. Run `gin state --format json`. Unless it reports `project.layout: sdd`, stop and name `/gin:migrate-specs`.
2. Read the target. A capability: `<specs>/<name>/spec.md`, its `diagrams/`, and the `description.md` of each dated folder under `assets/`. A change: its `01-proposal.md`, `02-spec-delta.md`, and `03-design.md`.
3. Write `.agent-workflow/runtime/explain/<name>.narrative.md`, 150 to 300 words of Markdown: what it does and for whom, the main flow, the key rules or decisions, and what is still open (dated folders with `Confirmed: no`, `## Open questions`, `?` values). Cite REQ-IDs. State nothing the files do not say.
4. Run `gin specs explain <name> --narrative .agent-workflow/runtime/explain/<name>.narrative.md`. Report the page path it prints and each `missing image:` line. On exit 2, report the error and stop.
5. Never commit, and never edit the specs or the dated folders.

---
name: explain
description: Write interactive HTML pages explaining an SDD capability or change, or the legacy code of a capability in frozen workspace apps, with a short narrative.
---

# Explain

On `/explain <capability|change> [--legacy [APP...]] [--lang LANGUAGE]` only. Pages go under `<explain>`, the `artifacts.explain` of the project config (`.agent-workflow/config.yaml`; default `.agent-workflow/runtime/explain`), which `gin setup` ignores: `<explain>/<name>/<name>.html`, and `<explain>/legacy/<APP>/<cap>/<cap>.html` with `--legacy`.

1. Run `gin state --format json`. Unless it reports `project.layout: sdd`, stop and name `/gin:migrate-specs`.
2. Language: `--lang`, else the language the user asks for, else the response language in the repository's `CLAUDE.md` or `AGENTS.md`, else English. Keep code, paths, and REQ-IDs verbatim.
3. Without `--legacy`, read the target. A capability: `<specs>/<name>/spec.md`, its `diagrams/`, and the `description.md` of each dated folder under `assets/`. A change: its `01-proposal.md`, `02-spec-delta.md`, and `03-design.md`. Write `<explain>/<name>/<name>.md`, 150 to 300 words: what it does and for whom, the main flow, the key rules or decisions, and what is still open (dated folders with `Confirmed: no`, `## Open questions`, `?` values). Cite REQ-IDs. State nothing the files do not say. Run `gin specs explain <name> --narrative <explain>/<name>/<name>.md`.
4. With `--legacy` (capabilities only), the apps are the `workspace.repos` entries with `frozen: true`, by last path component, or the named APPs. No workspace or no frozen entry: stop and say so. For each app, read the code that implements the capability, starting from paths cited by its confirmed `Kind: legacy` dated folders, then searching the app for the capability's terms. Create the folder `<explain>/legacy/<APP>/<cap>/` before writing its narrative, `<explain>/legacy/<APP>/<cap>/<cap>.md`, 150 to 300 words: the behaviour, rules, and fields the code shows, each with `file:line`, and what the code leaves unclear. State nothing the code does not show. Run `gin specs explain <cap> --legacy <APP> --narrative <that file>`. Skip an app with no related code, and name it.
5. Report each page path the command prints and each `missing image:` line. On exit 2, report the error and stop for that page.
6. Never commit, and never edit the specs, the dated folders, or legacy code.

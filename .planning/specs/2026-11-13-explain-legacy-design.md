# Explain pages for legacy code, in a configurable folder

Workflow: explain-legacy
Status: draft for user review.

## Goal and scope

A BA or developer can explain a capability as the legacy code implements it, next to the explain page of its spec, and keep both pages as an internal reference in a folder of their choice, such as an internal repository in the workspace.

In scope: a config key `artifacts.explain`; `gin specs explain` (`workflow_core/specs_explain.py`, `specs_cli.py`, `schemas.py`) with per-target folders and a `--legacy APP` option; the `/gin:explain` skill; docs (`docs/reference/config.md`, `docs/reference/cli.md`, `docs/guides/ba.md`, `docs/guides/sdd.md` and their `.vi.md` versions, `docs/guides/customizing-templates.md`); tests.

Out of scope: a page that diffs legacy against the spec; changes to the explain HTML template; committing pages (the user commits them).

## Requirements

1. Config: `artifacts.explain` (a relative path from the project root, the workspace parent in a workspace) names the explain folder; default `.agent-workflow/runtime/explain`.
2. Folders: `gin specs explain NAME` writes a capability page to `<explain>/<cap>/<cap>.html` and a change page to `<explain>/<change>/<change>.html`, replacing the flat `<explain>/<name>.html`. `--out` still overrides the path and must stay inside the project root.
3. `--legacy APP`: writes `<explain>/legacy/<APP>/<cap>/<cap>.html`. `APP` is the last path component of a `frozen` entry of `workspace.repos`. The page's kind line reads `legacy capability (<APP>)`. Exit 2 when there is no workspace, when `APP` names no frozen entry (the message lists the frozen apps), or when NAME is a change.
4. Narrative file: the skill writes the narrative Markdown as `<cap>.md` (or `<change>.md`) in the same folder as the page, so each folder holds `<name>.html` and `<name>.md`.
5. Skill `/gin:explain <capability|change> [--legacy [APP...]] [--lang LANGUAGE]`:
   - Without `--legacy`: as today, from the spec, diagrams, and dated asset folders.
   - With `--legacy`: the apps are the frozen workspace entries (only the named ones when APPs are given). For each app it reads the source code that implements the capability, starting from paths cited by the capability's confirmed `Kind: legacy` asset folders, then searching the app for the capability's terms. The narrative states only what the code shows (behaviour, rules, fields, with `file:line`) and runs `gin specs explain <cap> --legacy APP --narrative <folder>/<cap>.md`. An app with no related code is skipped and named; no workspace or no frozen entry stops with that reason.
   - Language: `--lang` or the language the user asks for; else the response language stated in the repository's `CLAUDE.md` or `AGENTS.md`; else English. Code, paths, and REQ-IDs stay verbatim.
   - It never commits and never edits specs, dated folders, or legacy code.

## User Stories

### US-1: Explain pages in a folder the team keeps
As a BA, I want explain pages written to a folder I configure, so that I can keep them in an internal repository as a reference.

Acceptance criteria:
- With `artifacts.explain: internal-docs/explain`, `gin specs explain catalog` writes `internal-docs/explain/catalog/catalog.html`.
- Without the key, it writes `.agent-workflow/runtime/explain/catalog/catalog.html`.
- A change page goes to `<explain>/<change>/<change>.html`.

### US-2: Explain the legacy implementation of a capability
As a BA, I want a page that explains a capability as the legacy code implements it, so that I can compare it with the page of the spec.

Acceptance criteria:
- In a workspace with a frozen entry `legacy/shop-portal`, `gin specs explain catalog --legacy shop-portal` writes `<explain>/legacy/shop-portal/catalog/catalog.html` and its kind line reads `legacy capability (shop-portal)`.
- `--legacy` with an unknown app exits 2 and lists the frozen apps; without a workspace, or for a change, it exits 2.
- `/gin:explain catalog --legacy` writes one page and one `catalog.md` per frozen app with related code, cites `file:line`, and names the apps it skipped.

### US-3: The narrative in the team's language
As a BA, I want the narrative in the language my repository works in, so that I do not have to ask for it each time.

Acceptance criteria:
- With no language request, the narrative follows the response language stated in `CLAUDE.md` or `AGENTS.md`, else English.
- `--lang` or an explicit request overrides it.

## Errors and compatibility

- The default page path moves from `<explain>/<name>.html` to `<explain>/<name>/<name>.html`; pages are generated files, so no migration is provided. `docs/guides/ba.md` and `sdd.md` list the new paths.
- `artifacts.explain` is a new optional key under `artifacts`; existing configurations stay valid.
- An `artifacts.explain` path outside the project root, or an `--out` outside it, exits 2.

## Testing

- `tests/workflow_core/test_specs_explain.py`: config folder, default folder, capability and change paths, `--legacy` with a frozen app (path and kind line), unknown app, no workspace, a change with `--legacy`, `--out` override.
- Schema test for `artifacts.explain` (accepted string; existing configs still valid).
- `tests/workflow_core/test_skill_routing.py`: the explain skill names `--legacy`, `<name>.md`, and the language rule.
- `gin docs check` on the changed docs; full suite `python3 -m pytest -n auto` passes.

## Open Technical Questions

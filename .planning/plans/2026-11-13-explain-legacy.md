# Plan: Explain pages for legacy code, in a configurable folder

Spec: .planning/specs/2026-11-13-explain-legacy-design.md
Workflow: explain-legacy

## Objective

`gin specs explain` writes each page into `<artifacts.explain>/<name>/<name>.html` and, with `--legacy APP`, into `<artifacts.explain>/legacy/<APP>/<cap>/<cap>.html` with the kind line `legacy capability (<APP>)`; `/gin:explain` writes `<name>.md` beside each page, explains frozen legacy apps on `--legacy`, and writes in the repository's language.

**Goal** (spec): a BA or developer can explain a capability as the legacy code implements it, next to the explain page of its spec, and keep both pages as an internal reference in a folder of their choice, such as an internal repository in the workspace.

**Architecture**: `artifacts.explain` joins `specs.SDD_DEFAULTS` (so `cfg["explain"]` exists wherever specs commands read `cfg`) and the `artifacts` schema enum. `specs_explain.explain` gains `legacy: str | None`, computes the default path from `cfg["explain"]`, and resolves `APP` against the frozen entries of `workspace.locate(root).workspace`. The skill computes the narrative path as the page path with `.md`.

**Tech Stack**: Python 3 standard library; unittest/pytest (`tests/workflow_core/test_specs_explain.py`, `test_workspace.py` fixtures, `test_skill_routing.py`); Markdown docs.

**Global Constraints** (spec, verbatim):
- Out of scope: a page that diffs legacy against the spec; changes to the explain HTML template; committing pages (the user commits them).
- The default page path moves from `<explain>/<name>.html` to `<explain>/<name>/<name>.html`; pages are generated files, so no migration is provided. `docs/guides/ba.md` and `sdd.md` list the new paths.
- `artifacts.explain` is a new optional key under `artifacts`; existing configurations stay valid.
- An `artifacts.explain` path outside the project root, or an `--out` outside it, exits 2.

## Route Rubric
- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis
- Problem statement: explain pages land in a fixed runtime folder, and nothing explains the legacy implementation for comparison.
- Success criteria: spec requirements 1–5 and US-1 to US-3; `python3 -m pytest -n auto` passes.
- Constraints: Global Constraints above.
- Non-goals: a diff page; template changes.

## Approach Options
### Option 1: config key, per-target folders, `--legacy APP` in the CLI (selected in `/discuss`)
- Summary: as the spec.
- Pros: the path rule lives in one place (the CLI); the skill only names the app.
- Cons: the default path changes.

### Option 2: the skill computes every path and passes `--out`
- Summary: no CLI change beyond the config key.
- Pros: smaller code change.
- Cons: path rules and app validation duplicated in prose; no exit-2 checks.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-13).
- Rationale: validation and paths are testable in code.

## Scope
- In scope: spec requirements 1–5.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: the skill and guides describe the paths and option Track 1 ships; one lane.
```

## Tasks

`W` is `plugins/gin-workflow/src/scripts/workflow_core`. Run tests from the repository root.

### Track 1: `artifacts.explain`, per-target folders, and `--legacy APP`
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py:21-24` (`SDD_DEFAULTS` gains `"explain": ".agent-workflow/runtime/explain"`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/schemas.py:125-128` (`"explain"` in the `artifacts` property-name enum)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_explain.py:14,222-245` (path rule, `legacy`, kind line)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py:44-47,178-183` (`--legacy APP`)
  - Modify `docs/reference/config.md:95-106` (`explain` row), `docs/reference/cli.md:146` (explain row), `docs/guides/customizing-templates.md:127` (`{{kind}}` values)
  - Test `tests/workflow_core/test_specs_explain.py`; the existing artifacts schema test (find it with `grep -rln "test_globs" tests/workflow_core`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change to one command with its config default and one workspace lookup; edge cases listed.
- **Interfaces**:
  - `specs_explain.explain(root, cfg, name, narrative=None, out=None, today=None, legacy: str | None = None) -> dict`: default path `root / cfg["explain"] / <folder> / <folder>.html` without `legacy`, `root / cfg["explain"] / "legacy" / legacy / <cap> / <cap>.html` with it; the page's `kind` is `f"legacy capability ({legacy})"` with `legacy`, else `capability` or `change` as today. Raises `specs.SpecsError` (exit 2) when: the resolved path is outside `root` (message names `--out` when given, else `artifacts.explain`); `legacy` is set and the target is a change (`--legacy explains a capability, not a change`); `legacy` is set and `workspace.locate(root).workspace` is `None` (`--legacy needs a workspace with frozen entries`); `legacy` matches no frozen entry's last path component (`no frozen app <legacy>; frozen apps: <a>, <b>` or `none`). Checks run before anything is written.
  - CLI: `gin specs explain NAME [--narrative FILE] [--out FILE] [--legacy APP]`.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_specs_explain.py`:
     - Change `page(root, name)` to read `root / OUT / name / f"{name}.html"`, and run the existing tests to see them fail on the new path (they pass after step 3).
     - `test_artifacts_explain_sets_the_folder`: config with `artifacts: {explain: internal-docs/explain}` (write it into the repo's `.agent-workflow/config.yaml` the way other tests set `artifacts`); `specs explain auth` writes `internal-docs/explain/auth/auth.html`.
     - `test_change_page_has_its_own_folder`.
     - `test_legacy_app_page_path_and_kind`: a workspace parent (reuse `make_workspace` from `test_workspace.py` or write the `workspace.repos` manifest the same way) with an entry `{path: legacy/shop-portal, url: u, frozen: true}` and the SDD capability in the parent; `specs explain auth --legacy shop-portal` exits 0, writes `<OUT>/legacy/shop-portal/auth/auth.html`, and the page contains `legacy capability (shop-portal)`.
     - `test_legacy_refusals_exit_2_and_write_nothing`: unknown app (stderr names `shop-portal` as a frozen app), no workspace, `--legacy` with a change name; nothing under `<OUT>`.
     - `test_artifacts_explain_outside_the_repository_exits_2` (`explain: ../out`).
     - In the artifacts schema test: `artifacts: {explain: x}` validates.
     Run `python3 -m pytest tests/workflow_core/test_specs_explain.py -q` → the new tests fail.
  2. `specs.py`: add the default; `schemas.py`: add `"explain"` to the enum.
  3. `specs_explain.py`: drop `OUT_DIR` (update the test's `OUT` constant to `.agent-workflow/runtime/explain` literally, it is the default); implement the path rule, the refusals (import `workspace` lazily inside the function, as other modules do), and the kind line; keep `--out` behaviour.
  4. `specs_cli.py`: `item.add_argument("--legacy")`; pass `legacy=args.legacy`.
  5. Docs: `config.md` table row `| \`explain\` | \`.agent-workflow/runtime/explain\` | folder for \`specs explain\` pages: \`<explain>/<name>/<name>.html\`, and \`<explain>/legacy/<app>/<cap>/<cap>.html\` with \`--legacy\` |`; `cli.md` explain row: new default path, `--legacy APP` (frozen workspace entry, capability only, kind line, exit 2 cases); `customizing-templates.md`: `{{kind}}` is `capability`, `change`, or `legacy capability (<app>)`.
  6. `python3 -m pytest tests/workflow_core -q -n auto` → pass; `gin docs check docs/reference/config.md docs/reference/cli.md docs/guides/customizing-templates.md` → ok.
  7. Commit: `feat(specs): explain pages per folder under artifacts.explain, and --legacy APP (explain-legacy)`.
- **Acceptance criteria**: spec requirements 1–3; US-1; US-2 bullets 1–2.
- **Estimated complexity**: medium

### Track 2: the explain skill and the guides
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/explain/SKILL.md`
  - Modify `docs/guides/ba.md:87-90,124`, `docs/guides/ba.vi.md` (same places), `docs/guides/sdd.md:136`, `docs/guides/sdd.vi.md` (same place)
  - Test `tests/workflow_core/test_skill_routing.py:99-103`
- **Provider role**: `docs`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** skill and guide text with the wording below, guarded by the routing test and the docs check.
- **Steps**:
  1. `test_skill_routing.py` `test_explain_skill_runs_the_cli_with_a_narrative`: replace the needle `.agent-workflow/runtime/explain/<name>.narrative.md` with `<name>.md`, and add needles `--legacy`, `frozen`, `CLAUDE.md`. Run it → fails.
  2. Rewrite `explain/SKILL.md` (keep the frontmatter; update the description to mention legacy code; keep "Cite REQ-IDs" and "Never commit"):
     - Usage: `/explain <capability|change> [--legacy [APP...]] [--lang LANGUAGE]`. Pages go under `artifacts.explain` (default `.agent-workflow/runtime/explain`): `<explain>/<name>/<name>.html`, and `<explain>/legacy/<APP>/<cap>/<cap>.html` with `--legacy`.
     - Step 1 unchanged (`project.layout: sdd`, else `/gin:migrate-specs`).
     - Language: write the narrative in `--lang` or the language the user asked for; else the response language that the repository's `CLAUDE.md` or `AGENTS.md` states; else English. Keep code, paths, commands, and REQ-IDs verbatim.
     - Without `--legacy`: read the target as today; write `<explain>/<name>/<name>.md` (150 to 300 words: what it does and for whom, the main flow, key rules or decisions, what is still open); cite REQ-IDs; run `gin specs explain <name> --narrative <explain>/<name>/<name>.md`.
     - With `--legacy` (capability only): `gin state --format json` gives `workspace`; the apps are its `frozen` entries (last path component), or the named APPs. No workspace or no frozen entry: stop and say so. For each app, read the code that implements the capability: start from paths cited in the capability's confirmed `Kind: legacy` dated folders, then search the app for the capability's terms. Write `<explain>/legacy/<APP>/<cap>/<cap>.md` (150 to 300 words): behaviour, rules, and fields the code shows, each with `file:line`, and what the code leaves unclear; state nothing the code does not show. Run `gin specs explain <cap> --legacy <APP> --narrative <that file>`. Skip and name an app with no related code.
     - Report each page path and each `missing image:` line; on exit 2 report the error and stop for that page.
     - Never commit, and never edit the specs, the dated folders, or legacy code.
     Keep the skill short; check `tests/workflow_core/test_token_budget.py` for a limit on this skill.
  3. `ba.md` "Export and explain" and the paths table (`/gin:explain <cap>` → `<explain>/<cap>/<cap>.html`; add `/gin:explain <cap> --legacy` → `<explain>/legacy/<app>/<cap>/<cap>.html`): one paragraph saying the legacy page explains what a frozen legacy app's code does, so a BA can compare it with the spec page; `artifacts.explain` can point at an internal repository of the workspace, which the team commits. Mirror in `ba.vi.md` (Vietnamese prose, code verbatim). `sdd.md:136` and `sdd.vi.md`: the new page path and one sentence on `--legacy`.
  4. `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_coverage.py -q` → pass; `gin docs check docs/guides/ba.md docs/guides/sdd.md` → ok; `python3 -m pytest -n auto` → pass.
  5. Commit: `docs(explain): legacy pages, per-folder paths, and the narrative language (explain-legacy)`.
- **Acceptance criteria**: spec requirements 4 and 5; US-2 bullet 3; US-3.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/explain-legacy`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes
- [ ] `gin docs check` passes on the changed docs

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- Deliverable merge-holds apply only to the Parent Bead; track beads close once tests and review pass.

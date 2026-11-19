# Plan: Offline diagrams: embed Mermaid in the SRS and explain pages

Epic: gin-workflow-1w5p
Workflow: gin-workflow-1w5p
Spec: `.planning/specs/2026-11-19-offline-diagrams-design.md`

## Objective

`gin specs export` and `gin specs explain` embed a vendored copy of Mermaid 11.4.1 in the page when it holds a diagram, instead of loading Mermaid from jsDelivr, so the SRS and the explain page draw their diagrams offline and print with them.

Architecture: the vendored `mermaid.min.js` lives in the plugin's `templates/vendor/` folder (installed recursively with the templates by `install.sh` and `install.ps1`). A new `specs_export.mermaid_script(body)` returns `<script>` + the file + `</script>` when `body` holds `<pre class="mermaid">`, else `""`. `srs.html` and `explain.html` replace their CDN `<script src>` with `{{mermaid}}`; `export` and `specs_explain.explain` compute the other placeholder values first and pass their concatenation to `mermaid_script`, then fill once.

Tech stack: Python standard library; Node Playwright (`NODE_PATH=/home/gin/scotty/node_modules`) only for the manual browser check.

## Global Constraints

Copied from the spec:

- Embed the Mermaid library in the page instead of pre-rendering SVG: the `gin` CLI stays standard-library Python, with no Node, mermaid-cli, or Chromium needed to export, on any platform.
- Always embed when the page holds a diagram; no flag.
- Both the SRS and the `/gin:explain` page.
- The vendored copy is `mermaid.min.js` 11.4.1, the file the CDN serves today (sha384 `rbtjAdnIQE/aQJGEgXrVUlMibdfTSa4PQju4HDhN3sR2PmaKFzhEafuePsl9H/9I`, 2,571,900 bytes, MIT licence), so the drawings do not change. Upgrading it is a manual replacement of the file and its pinned hash.
- A page with a diagram grows by about 2.5 MB; a page without one does not grow.
- A project template override that still holds the CDN `<script src>` keeps working online, unchanged; no lint or doctor warning for it.
- Out of scope: pre-rendered SVG, the gin-qa report, Mermaid versions other than 11.4.1.

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
- Problem statement: diagrams in the SRS and explain pages need jsDelivr; offline they show Mermaid source.
- Success criteria: US-1 to US-3 pass as tests; the browser check with the network blocked draws every diagram; full suite green.
- Constraints: Global Constraints above.
- Non-goals: the out-of-scope list above.

## Approach Options
### Option 1: Vendor and inline the Mermaid library (confirmed at discuss)
- Summary: ship `mermaid.min.js` with the plugin; export inlines it through a `{{mermaid}}` placeholder.
- Pros: no new tool at export time; works on every platform; drawings identical to today.
- Cons: about 2.5 MB per page with diagrams and in the repository.

### Option 2: Pre-render SVG with mermaid-cli or Playwright
- Summary: export runs a headless browser to turn each block into SVG.
- Pros: no JavaScript when the page opens.
- Cons: Node and Chromium on every exporting machine; rejected at discuss.

### Recommended Approach
- Selected option: Option 1.

## Scope
- In scope: R1 to R5 of the spec.
- Out of scope: Global Constraints' out-of-scope list.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 documents what Track 1 builds; they run one after another on feat/offline-diagrams.
```

## Tasks

### Track 1: Vendored Mermaid embedded in the SRS and explain pages (R1, R2, R3, R4)
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/templates/vendor/mermaid.min.js` (downloaded, not hand-written)
  - Create `plugins/gin-workflow/src/templates/vendor/README.md`
  - Modify `.gitattributes` (keep the vendored file byte-exact)
  - Modify `plugins/gin-workflow/src/templates/srs.html` (lines 94-96: the CDN `<script src>` element)
  - Modify `plugins/gin-workflow/src/templates/explain.html` (lines 60-62: the CDN `<script src>` element)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_export.py` (new `mermaid_script`; `export` fill around line 525)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_explain.py` (import `mermaid_script`; fill around line 270)
  - Test `tests/workflow_core/test_specs_export.py` (lines 179-196 and 545-556 assert the CDN today), `tests/workflow_core/test_specs_explain.py` (lines 66-80 assert the CDN today)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change in two exporters with a clear rule; the care points are filling once so spec text is never substituted, the exact-bytes vendored file, and the existing tests that pin the CDN.
- **Interfaces consumed**: `specs.plugin_templates_dir() -> Path`, `specs.SpecsError`, `specs_export.fill(template, values)`.
- **Interfaces produced**:
  - `specs_export.MERMAID_SHA384 = "rbtjAdnIQE/aQJGEgXrVUlMibdfTSa4PQju4HDhN3sR2PmaKFzhEafuePsl9H/9I"`.
  - `specs_export.mermaid_script(body: str) -> str`: `""` when `'<pre class="mermaid">'` is not in `body`; otherwise `"<script>" + text + "</script>"` with `text` read (UTF-8) from `specs.plugin_templates_dir() / "vendor" / "mermaid.min.js"`; an `OSError` raises `specs.SpecsError(f"vendored Mermaid missing: {path}: {error}")`.
  - Templates: `{{mermaid}}` in `srs.html` and `explain.html` where the CDN element was.
- **Steps**:
  1. Vendor the file:
     ```bash
     mkdir -p plugins/gin-workflow/src/templates/vendor
     curl -sSfo plugins/gin-workflow/src/templates/vendor/mermaid.min.js https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js
     openssl dgst -sha384 -binary plugins/gin-workflow/src/templates/vendor/mermaid.min.js | openssl base64 -A
     ```
     Expected: `rbtjAdnIQE/aQJGEgXrVUlMibdfTSa4PQju4HDhN3sR2PmaKFzhEafuePsl9H/9I`, 2571900 bytes. Add to `.gitattributes` under a `# Vendored` comment: `plugins/gin-workflow/src/templates/vendor/mermaid.min.js -text -diff`. Write `vendor/README.md`: source URL, version 11.4.1, the sha384, licence MIT (Mermaid's licence), why it is vendored (offline SRS and explain pages), and how to upgrade (replace the file, update `MERMAID_SHA384` and the version in this README, run the tests).
  2. Failing tests:
     - `test_specs_export.py`, new class `MermaidEmbedTests`:
       - `test_vendored_file_is_pinned`: sha384 (base64) of `plugins/gin-workflow/src/templates/vendor/mermaid.min.js` equals `specs_export.MERMAID_SHA384`, and `"</script"` is not in its lowercased text.
       - `test_mermaid_script_only_with_a_diagram`: `mermaid_script("<p>x</p>") == ""`; `mermaid_script('<pre class="mermaid">flowchart TD</pre>')` starts with `"<script>"`, ends with `"</script>"`, and has the vendored text between.
       - `test_missing_vendored_file_raises`: with `unittest.mock.patch.object(specs, "plugin_templates_dir", return_value=<empty tmp dir>)`, `mermaid_script('<pre class="mermaid">x</pre>')` raises `specs.SpecsError` whose message contains `vendor/mermaid.min.js` (as `Path` text, so compare with `str(Path("vendor") / "mermaid.min.js")`).
     - `test_one_capability_holds_purpose_diagrams_requirements_and_assets`: replace the needles `"mermaid@11.4.1/dist/mermaid.min.js"` and `'integrity="sha384-'` with assertions that `cdn.jsdelivr.net` is not in the html and that the vendored text's first 200 characters occur exactly once.
     - New `test_export_without_diagrams_embeds_no_library`: a repo whose spec has no mermaid block and no use cases; `srs-<cap>.html` holds neither `cdn.jsdelivr.net` nor the vendored text's first 200 characters, and holds no `{{mermaid}}`.
     - New `test_override_without_placeholder_keeps_its_script`: `.agent-workflow/templates/srs.html` copied from the plugin template with `{{mermaid}}` replaced by the old CDN element (`<script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"></script>`); export keeps that element and does not hold the vendored text.
     - `test_srs_templates_print_their_placeholders`: the regex on the CDN becomes `assertIn("{{mermaid}}", document)` and `assertNotIn("cdn.jsdelivr.net", document)`.
     - `test_specs_explain.py` `test_tabs_requirements_grouped_by_section_and_diagrams`: drop the `"mermaid@11.4.1"` and `integrity=` needles; assert `cdn.jsdelivr.net` not in html and the vendored text's first 200 characters occur exactly once. New `test_page_without_diagrams_embeds_no_library` (a spec without a mermaid block): neither the CDN nor the vendored text.
     Run `timeout 300 python3 -m pytest tests/workflow_core/test_specs_export.py tests/workflow_core/test_specs_explain.py -q`: the new and changed tests fail.
  3. Code:
     - `srs.html` lines 94-96 and `explain.html` lines 60-62: replace the `<script src=... integrity=... crossorigin=...></script>` element with `{{mermaid}}`. Keep the initialisation scripts after it.
     - `specs_export.py`: add `MERMAID_SHA384` and `mermaid_script` (Interfaces). In `export`, build the values dict passed to `fill` into a variable, then `values["mermaid"] = mermaid_script("".join(values.values()))`, then `html = fill(document, values)`.
     - `specs_explain.py`: import `mermaid_script` from `.specs_export`; same pattern with its values dict.
     Run the tests from step 2: pass.
  4. Run `timeout 300 python3 -m pytest tests/workflow_core/test_specs_export.py tests/workflow_core/test_specs_explain.py tests/workflow_core/test_specs_matter.py tests/workflow_core/test_specs.py -q`: pass.
  5. Browser check (manual evidence): in a scratch SDD repo with two capabilities, use cases, and an activity diagram, run `gin specs export --all` and `gin specs explain <cap>` with the worktree's launcher. With Node Playwright, open each page with `page.route('**/*', r => r.request().url().startsWith('file:') ? r.continue() : r.abort())`; wait for Mermaid; assert the `svg` count inside `pre.mermaid` equals the `pre.mermaid` count and the page text holds no `Syntax error`; for explain, click each tab before counting. Print the SRS with `page.pdf()` and take a screenshot of one diagram. Keep the script and outputs in the scratchpad.
  6. Commit: `feat(specs): embed the vendored Mermaid library so SRS and explain pages draw diagrams offline (gin-workflow-1w5p.1)`.
- **Acceptance criteria**: R1 to R4; US-1 to US-3 as tests; the browser check draws every diagram with the network blocked; review approved.
- **Estimated complexity**: low

### Track 2: Documentation (R5)
- **Dependencies**: Track 1
- **Files**:
  - Modify `docs/guides/sdd.md`, `docs/guides/sdd.vi.md` (section "Exporting an SRS")
  - Modify `docs/guides/ba.md`, `docs/guides/ba.vi.md` (where the SRS is sent or printed)
  - Modify `docs/guides/customizing-templates.md` (lines 109 and 127), `docs/guides/customizing-templates.vi.md` (matching lines)
  - Modify `docs/reference/cli.md` (the `specs export` and `specs explain` rows)
  - Modify `.planning/knowledge/srs-export.md` (its CDN statement)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** documentation of behaviour built in Track 1, checked against the code.
- **Steps**:
  1. Read `specs_export.mermaid_script`, the `export` and `specs_explain.explain` fills, `templates/srs.html`, `templates/explain.html`, and `templates/vendor/README.md`.
  2. `sdd.md` (and `.vi.md`): the SRS embeds Mermaid when it has a diagram, so it opens and prints with its diagrams offline; a page without a diagram does not grow.
  3. `ba.md` (and `.vi.md`): the file can be sent and printed offline; link to sdd.md for the rule.
  4. `customizing-templates.md` (and `.vi.md`): `{{mermaid}}` in `srs.html` and `explain.html`; an override that keeps a CDN script and no `{{mermaid}}` draws diagrams only online.
  5. `cli.md`: the two rows say the page embeds Mermaid when it holds a diagram.
  6. `.planning/knowledge/srs-export.md`: replace the CDN statement with the vendored library and point to `templates/vendor/README.md` for upgrades.
  7. Run `gin docs check docs/guides/sdd.md docs/guides/sdd.vi.md docs/guides/ba.md docs/guides/ba.vi.md docs/guides/customizing-templates.md docs/guides/customizing-templates.vi.md docs/reference/cli.md` and `timeout 300 python3 -m pytest tests/workflow_core/test_docs*.py -q`: pass.
  8. Commit: `docs(specs): SRS and explain pages draw diagrams offline (gin-workflow-1w5p.2)`.
- **Acceptance criteria**: R5; every claim matches the code; docs check exits 0; review approved.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/offline-diagrams`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes (pre-push hook).
- [ ] `gin docs check` on the changed pages exits 0.
- [ ] Manual: the browser check of Track 1 step 5.

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- Deliverable merge-holds apply only to the Parent Bead `gin-workflow-1w5p`; track beads close when their tests and review pass.
- Track IDs in commit messages (`gin-workflow-1w5p.N`) are the beads orchestrate creates; use the real IDs.

# SDD team flow: in-flight MODIFIED, workspace trace, asset folders with the spec

**Context**
Epic `gin-workflow-sdd-team-flow` (2026-11-11), process review clusters "SDD layout in the brownfield starter" and "SDD change flow for a team workspace" (BA-1, QA-11, BA-17, BA-6, BA-8, BA-9, BA-11, BA-12, BA-19). A `MODIFIED` block could only target a living requirement, so a business change to a requirement another epic added but had not shipped had no working flow; `specs trace` saw one repository; the brownfield starter left the layout `legacy` and told the team to write legacy behaviour as living specs.

**Decision/Solution**
- `specs.in_flight_blocks(root, cfg, exclude=)`: `ADDED` blocks of open change folders whose REQ is not living. `lint_change` accepts `MODIFIED`/`REMOVED` on such a REQ (one adder); `requirement_hash` returns `(block, hash, change|None)` and falls back to the in-flight block; `archive` stops with `<REQ> is added by <change>; archive <change> first`. Two open adders: `<REQ> is added by <a> and <b>; renumber one`. The approved change folder is never edited.
- `specs_trace.trace` adds every cloned workable child of `workspace.load(root)` (not frozen, not beads); globs match the child-relative path, sources carry the child path; uncloned children or a failing `git ls-files` go to `skipped` (JSON key, always present).
- REQ-IDs live only in the parent's specs in a workspace; children reference them. Collisions are caught by `specs lint --against <base>` (discuss step 4 and ship in the `sdd` skill) and fixed with `specs renumber`.
- Asset folders have no branch of their own: discuss commits a confirmed folder with the change folder that cites it. During a rewrite living specs describe the new system; legacy behaviour stays in `Kind: legacy` folders cited by `Source:`. The BA reviewing the archive diff is a team convention.
- The brownfield starter sets `artifacts.layout: sdd` and `test_globs` in config (setup never asks about the layout), and adds a "Capture and mockup (BA)" step before discuss.

**Consequences**
- A configured `artifacts.test_globs` replaces `DEFAULT_TEST_GLOBS` (`sdd_config`), so a project adding the Maven tree must repeat the defaults; review caught the starter dropping `**/*_test.py`.
- `/gin:setup` has no spec-layout question for brownfield projects; docs must not claim it does.
- `trace --repository <repo>` now reads the workspace manifest, so a malformed `workspace` block stops trace with the manifest error (no test pins this yet).
- `sdd/SKILL.md` is 5,966 of 6,000 characters after this epic.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{specs.py,specs_archive.py,specs_cli.py,specs_trace.py}`; `plugins/gin-workflow/src/skills/sdd/SKILL.md`; `plugins/gin-qa/src/skills/setup/SKILL.md`
- Tests: `tests/workflow_core/test_specs.py`, `tests/workflow_core/test_specs_archive_trace.py` (`TestTraceWorkspace`)
- Docs: `docs/guides/{sdd,git-flow,ba,workspace}.md`, `docs/roles.md`, `docs/starters/brownfield.md`, `docs/reference/cli.md`, and `.vi.md` pairs
- `.planning/specs/2026-11-11-sdd-team-flow-design.md`, `.planning/plans/2026-11-11-sdd-team-flow.md`
- Beads: `gin-workflow-sdd-team-flow`, `.1` to `.4`
- Related: [spec-asset-iterations](spec-asset-iterations.md), [ba-plugin](ba-plugin.md), [workspace](workspace.md), [qa-lifecycle](qa-lifecycle.md), [process-review](process-review.md)

**Scope**
SDD layout: requirement changes after plan approval, traceability in a workspace, asset folder commits, and the brownfield starter.

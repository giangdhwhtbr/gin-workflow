# Requirement types: non-functional requirements and business rules as typed REQ blocks

**Context**
Epic `gin-workflow-ngiz` (2026-11-19), group B of the BA review follow-ups of `gin-workflow-cyb8`. A BA's SRS separates non-functional requirements (measurable quality attributes) and business rules from functional requirements; the SDD layout had one kind of `### REQ-<CAP>-<NNN>` block.

**Decision/Solution**
- No new ID families: a REQ block gains optional `Type:` (`functional` default, `non-functional`, `business-rule`), `Category:` for non-functional (`specs.NFR_CATEGORIES`, based on ISO/IEC 25010 plus `constraint`), and `Measure:`. `Block.type`/`category`/`measure` read them before the first `####` scenario with `line_value` (comments ignored); `specs.type_of` maps an invalid type to functional for rendering; `specs.statement` gives the first SHALL/MUST line. next-id, hash, delta, renumber, archive, trace, and gin-qa are unchanged. A separate NFR-/BR- numbering was rejected at discuss as touching every reader of REQ-IDs.
- Lint (`lint_block`): unknown type; non-functional needs a listed category; `Category:`/`Measure:` only on non-functional; a non-functional block needs a scenario or a `Measure:` value, other types still need a scenario.
- `_feature_diagram_findings` ignores non-functional blocks in both branches: adding an NFR does not change a flow, so it asks for no activity diagram (asked for by the user after discuss). Business rules still count.
- `gin specs reqs` rows add `type` and `category`; `specs_matter.traceability` adds `type`; `specs_matter.nonfunctional` and `business_rules` feed two SRS catalogues (`{{nfr}}`, `{{business_rules}}`, after the actors). A chapter groups its requirements by type only when it has a non-functional or business-rule block, otherwise it renders as before; requirement anchors and the table of contents keep file order. `Type`/`Category`/`Measure` render as a `requirement-fields` table through `_header_fields`, shared with the use case header table.
- Writing guidance is in the `spec-delta.md` comment and the docs; `skills/sdd/SKILL.md` was not changed (5,996 of 6,000 characters).

**Consequences**
- Existing specs need no change; reclassifying a requirement is a `MODIFIED` block with its `base:` hash, since the type lines are part of the block text (an unchanged block keeps hash `8f31b417` for the test fixture).
- Open MINOR items: the use case citation loop is duplicated in `business_rules` and `traceability`; `_header_fields` now skips the first line for use cases too (only matters for a use case file starting with `## `); a comment containing a `\n#### ` line would cut a block's head early.
- Execution lesson: a worker that writes code before tests is checked by running its tests on a detached worktree of the previous commit; they must fail there.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/specs.py`, `specs_reqs.py`, `specs_matter.py`, `specs_export.py`; `plugins/gin-workflow/src/templates/spec-delta.md`, `srs.html`
- Tests: `tests/workflow_core/test_specs.py`, `test_specs_reqs.py`, `test_specs_matter.py`, `test_specs_export.py`
- Docs: `docs/guides/sdd.md` (Requirement types), `ba.md`, `customizing-templates.md`, their `.vi.md` pairs, `docs/reference/cli.md`
- `.planning/specs/2026-11-18-srs-requirement-types-design.md`, `.planning/plans/2026-11-18-srs-requirement-types.md`
- Beads: `gin-workflow-ngiz`, `.1` to `.3`
- Related: [srs-document-matter](srs-document-matter.md), [spec-diagrams](spec-diagrams.md), [srs-export](srs-export.md)

**Scope**
SDD layout only: requirement blocks, `specs lint`, `specs reqs`, the SRS export, and the SDD, BA, and template guides.

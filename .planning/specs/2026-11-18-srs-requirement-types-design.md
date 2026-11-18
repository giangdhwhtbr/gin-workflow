# SRS requirement types: non-functional requirements and business rules

Epic: gin-workflow-ngiz
Workflow: gin-workflow-ngiz
Kind: capability
Status: confirmed by the user on 2026-11-18 (extended: non-functional blocks need no activity diagram).

## Goal and scope

With the SDD layout, every requirement is a `### REQ-<CAP>-<NNN>` block with a SHALL or MUST statement and at least one GIVEN/WHEN/THEN scenario (`specs.parse_blocks`, `specs.lint_block`). The SRS prints them in one list per capability. A BA's SRS also separates non-functional requirements (NFRs: performance, security, and the like, each measurable) and business rules (the policies use cases follow), and lists each kind across the whole document. Group B of the BA review follow-ups of `gin-workflow-cyb8`, split from `gin-workflow-414v`.

Confirmed decisions (2026-11-18):

- NFRs and business rules stay `### REQ-<CAP>-<NNN>` blocks with a `Type:` line (`functional`, `non-functional`, `business-rule`; default `functional`). No new ID families: next-id, hash, delta, renumber, archive, trace, and gin-qa keep working unchanged.
- A non-functional block has a `Category:` from a fixed list based on ISO/IEC 25010: `performance`, `security`, `reliability`, `usability`, `compatibility`, `maintainability`, `portability`, plus `constraint`.
- A non-functional block needs a full scenario or a `Measure:` line; functional and business-rule blocks keep needing a scenario.
- A non-functional block does not count toward the per-capability activity diagram rule of `specs lint --change` (added at discuss after review, 2026-11-18): adding an NFR does not change a flow. Business rules still count.
- In the SRS, each chapter groups its requirements by type (NFRs by category), the document gains a non-functional requirements catalogue and a business rules catalogue after the actors, and the traceability matrix gains a Type column.

Assumptions (defaults, not asked):

- `Type:`, `Category:`, and `Measure:` are lines of the block body outside scenarios, read with `specs.line_value` (comments ignored). A block without `Type:` is functional, so existing specs keep their lint results and hashes.
- These lines are part of the block text, so changing them is a `MODIFIED` block with a new hash, like any edit.
- `gin specs reqs` adds `type` and `category` to each row; consumers that ignore unknown keys (gin-qa, gin-console) are unaffected.
- Writing guidance goes in the comment of `templates/spec-delta.md` and the docs; `skills/sdd/SKILL.md` is not changed (it is at 5,996 of 6,000 characters).
- The business rules catalogue lists the use cases whose `Requirements:` line names the rule.

Out of scope:
- `/gin:explain` pages.
- Checking that an NFR is actually measured: coverage status stays as for any requirement (a test or QA case citing it).
- Configurable categories.
- The legacy layout.

## Requirements

### R1. Requirement type, category, and measure

`specs.REQ_TYPES = ("functional", "non-functional", "business-rule")` and `specs.NFR_CATEGORIES = ("performance", "security", "reliability", "usability", "compatibility", "maintainability", "portability", "constraint")`. `Block` gains read-only properties `type` (the `Type:` value, else `functional`), `category` (the `Category:` value, else `""`), and `measure` (the `Measure:` value, else `""`), each read from the block text outside `####` scenario sections.

### R2. Lint

`specs.lint_block` (living blocks and `ADDED`/`MODIFIED` delta blocks) adds, with the block's REQ-ID in front like its other findings:

- a `Type:` value not in `REQ_TYPES`: `REQ-AUTH-004: Type must be one of functional, non-functional, business-rule`;
- a non-functional block without a `Category:` value, or with one not in `NFR_CATEGORIES`: `REQ-AUTH-004: Category must be one of performance, security, reliability, usability, compatibility, maintainability, portability, constraint`;
- a `Category:` or `Measure:` line on a block that is not non-functional: `REQ-AUTH-005: Category and Measure are only for Type: non-functional`;
- a non-functional block needs at least one scenario with GIVEN, WHEN, and THEN, or a `Measure:` line with a value; with a `Measure:` line and no scenario, the existing "needs at least one '#### Scenario:'" finding is not raised. A scenario that is present is still checked for GIVEN, WHEN, and THEN.

The SHALL/MUST statement stays required for every type. A block without `Type:` gets exactly the findings it gets today.

In `specs lint --change` (`_feature_diagram_findings`), the per-capability activity diagram rule counts only blocks whose type is not `non-functional`: with `--against`, a capability whose `ADDED` blocks are all non-functional needs no added or changed activity diagram; without `--against`, a capability whose `ADDED` and `MODIFIED` blocks are all non-functional needs no activity diagram. The use case and decision-label rules do not change.

### R3. Requirements as data

- `gin specs reqs` rows gain `type` and `category`.
- `specs_matter.traceability` rows gain `type`.
- `specs_matter.nonfunctional(root, cfg, cap=None)` returns one row per non-functional living requirement: `id`, `title`, `capability`, `category`, `measure`, sorted by the order of `NFR_CATEGORIES`, then capability, then REQ-ID number.
- `specs_matter.business_rules(root, cfg, cap=None)` returns one row per business-rule living requirement: `id`, `title`, `capability`, `statement` (the first prose line holding SHALL or MUST), `use_cases` (`<cap>/<slug>` of each use case whose `Requirements:` line names it), sorted by capability, then REQ-ID number.

A value that fails lint (an unknown type) is treated as functional by these functions, so rendering never fails on it.

### R4. SRS

- In each chapter, the requirements are grouped under `<h3>Functional requirements</h3>`, `<h3>Non-functional requirements</h3>` (with an `<h4>` per category present, in `NFR_CATEGORIES` order), and `<h3>Business rules</h3>`, each group only when it has a block. A chapter whose requirements are all functional renders exactly as today, without group headings. Requirement anchors (`id="<REQ-ID>"`) and table-of-contents entries do not change.
- `templates/srs.html` gains the placeholders `nfr` and `business_rules`, in sections `id="nfr"` ("Non-functional requirements") and `id="business-rules"` ("Business rules") after the actors section, linked from the table of contents like the other document sections. Empty: "No non-functional requirements." and "No business rules.".
  - Non-functional table columns: Category, Requirement (`<a href="#<REQ-ID>"><REQ-ID></a>: <title>`), Capability, Measure.
  - Business rules table columns: Rule (same link form), Capability, Statement, Use cases (linked as in the actor catalogue).
- In a requirement block, the `Type:`, `Category:`, and `Measure:` lines render as a two-column table under its heading, the way use case header lines do, instead of running into the statement.
- The traceability matrix gains a Type column after Capability.
- A one-capability export limits both catalogues to that capability. An overridden `srs.html` without the new placeholders exports without those sections and without an error.

### R5. Template and documentation

- `templates/spec-delta.md` comment: the optional `Type:`, `Category:` (with the list), and `Measure:` lines, with no `--` inside the comment.
- `docs/guides/sdd.md` and `.vi.md`: writing NFRs and business rules, the lint rules, and the SRS grouping and catalogues.
- `docs/guides/ba.md` and `.vi.md`: when to write a requirement as non-functional or as a business rule, with one example each; link to sdd.md for the rules.
- `docs/guides/customizing-templates.md` and `.vi.md`: the `nfr` and `business_rules` placeholders.
- `docs/reference/cli.md`: the `lint`, `reqs`, and `export` rows.

## User Stories

### US-1: Write a measurable non-functional requirement
As a business analyst, I want to mark a requirement as non-functional with a category and a measure, so that the SRS shows quality attributes the customer can verify.

Acceptance criteria:
- A block with `Type: non-functional`, `Category: performance`, a SHALL statement, and `Measure: p95 below 300 ms` passes `specs lint` without a scenario.
- The same block without `Category:`, or with `Category: speed`, fails lint naming the REQ-ID and the allowed categories.
- A non-functional block with neither a scenario nor a `Measure:` value fails lint.
- A functional block with `Measure:` fails lint.
- `specs lint --change <epic> --against <base>` passes a change whose only `ADDED` block for a capability is non-functional without an added or changed activity diagram; adding a business-rule block instead still needs one.

### US-2: Write business rules as requirements
As a business analyst, I want to mark a requirement as a business rule, so that use cases cite rules by REQ-ID and the SRS lists every rule in one place.

Acceptance criteria:
- A block with `Type: business-rule`, a MUST statement, and a full scenario passes lint; without a scenario it fails as a functional block would.
- `Type: policy` fails lint naming the allowed types.
- A spec without any `Type:` line gets the same lint findings and block hashes as before.

### US-3: Read requirements by type in the SRS
As a customer, I want each chapter to separate functional requirements, non-functional requirements by category, and business rules, and the document to list all NFRs and all business rules, so that I can review each kind together.

Acceptance criteria:
- A chapter with one functional, one performance, and one business-rule block shows the three group headings, a `performance` sub-heading, and the blocks under them; a chapter with only functional blocks has no group headings.
- The NFR catalogue lists the performance requirement with its measure; the business rules catalogue lists the rule with its statement and the use cases citing it.
- The traceability matrix shows each requirement's type.
- `export <cap>` limits both catalogues to that capability; without such requirements the sections read "No non-functional requirements." and "No business rules.".
- `gin specs reqs` rows carry `type` and `category`.

## Errors and compatibility

- Specs written before this change have no `Type:` line: they lint, hash, archive, trace, and export as before, except the SRS gains the two catalogue sections ("No …" lines) and the Type column.
- Invalid type or category values are lint findings (exit 1); export treats an invalid type as functional.
- A project's overridden `srs.html` without the new placeholders exports without the new sections.
- `gin specs reqs` gains two keys; no key is removed or renamed.
- `dist/` is regenerated by the build; no hand edits there.

## Testing

- `tests/workflow_core/test_specs.py`: each R2 finding, the activity diagram rule skipping non-functional blocks (with and without `--against`) and still counting business rules, the `Measure:` alternative to a scenario, a present scenario still checked, `Block.type`/`category`/`measure`, a spec without `Type:` unchanged (findings and `block_hash`), the `spec-delta.md` template naming the three lines and holding no `--` inside its comment.
- `tests/workflow_core/test_specs_reqs.py`: `type` and `category` in `gin specs reqs`.
- `tests/workflow_core/test_specs_matter.py`: `nonfunctional`, `business_rules` (order, `cap` filter, use cases, statement), `traceability` `type`.
- `tests/workflow_core/test_specs_export.py`: chapter grouping with and without non-functional or rule blocks, both catalogues and their empty lines, the Type column, a one-capability export, an override without the placeholders.
- A browser render of an exported SRS with each type.
- `gin docs check` on the changed pages; full suite through the pre-push hook.

## Open Technical Questions

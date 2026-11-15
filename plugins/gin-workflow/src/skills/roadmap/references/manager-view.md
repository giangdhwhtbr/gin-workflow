# Manager view: summary, outcome, demo, and legacy coverage

Read on `/roadmap` when presenting and writing the roadmap (steps 4, 5, and 7).

## Wording
Write `Goal:`, `Outcome:`, `Demo:`, and `Features:` for a manager: business words, no file paths, no code identifiers. Paths stay in `Evidence:` and `Legacy:`.

## Summary
`## Summary` has one row per `## Milestone:` block of the file, in `end` order: its period (`start` to `end`), the `Outcome:` and `Demo:` of the block, and the titles of its epics. A last row `Unassigned` lists the epics without a milestone, with an empty outcome and demo. A plain `/roadmap` without a milestone plan writes only that row.

## Outcome and Demo
`Outcome:` says what exists at the end of the milestone. `Demo:` names the user flows that can be shown to the customer, each backed by an epic of this milestone or an earlier one. Both are written only under a milestone heading, in the roadmap file, never in Beads. The demo belongs to a milestone, not to an epic: a technical epic has nothing to show, and a customer demo crosses several epics. `Result:` under a milestone heading is written by `/milestone-close` when the milestone closes; a `/roadmap` run keeps it and the lines under it unchanged. `/roadmap --milestone <id>` asks for, or proposes, both the `Outcome:` and the `Demo:` of the milestone before it proposes the adoption.

## Features and Legacy
`Features:` lists the features the epic delivers, by their names in the Capability Map of `13-CAPABILITIES.md`, else the Feature Catalog of `02-FEATURES.md`, else the brief. `Legacy:` names what the epic replaces in the old system, with counts and the tech-doc section, for example `12 screens, 31 endpoints, 9 tables (13-CAPABILITIES.md#Capability Map: orders)`. It is `none` for new behaviour. Step 6 copies both lines to the epic's Beads description.

## Legacy coverage
`## Legacy coverage` is written only when `13-CAPABILITIES.md` exists. It has one row per capability of its Capability Catalog: the screen count from `Migration Inventory`, the epics whose `Capabilities:` name it, their milestone, and `Status`. `Status` is one of:
- `planned`: an epic covers the capability.
- `not migrated: <reason>`: the PM confirmed the capability is left out.
- `unplanned`: no epic covers it and the PM made no decision.

When presenting, ask the PM about every `unplanned` capability once, in one question that lists them all. This question does not count against `project.max_questions`.

Rows use the names of the Capability Catalog. An epic covers a row when its `Capabilities:` names the catalog name or a name mapped to it. With `project.layout: sdd`, each name of `docs/specs/README.md` that matches no catalog name goes into the same question, for the PM to map to a catalog name; the report lists each name left unmapped.

## Report
Step 7 reports the number of capabilities and how many are `planned`, `not migrated`, and `unplanned`, and names each `unplanned` capability. Without `13-CAPABILITIES.md` it reports no counts. With a milestone plan, it also names each milestone the run created and the epics it set into each one.

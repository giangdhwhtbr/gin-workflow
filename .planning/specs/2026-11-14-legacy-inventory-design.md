# Legacy inventory in tech-doc and a manager-readable roadmap

Epic: gin-workflow-legacy-inventory
Kind: capability
Status: draft for user review.

## Goal and scope

A migration has to prove that no capability, screen, or table of the old system is missed, and the manager has to read the roadmap without reading code. Today tech-doc has no database document and no capability concept (`/roadmap` takes capability names from the Feature Catalog of `02-FEATURES.md`), and the roadmap file says nothing about what a milestone delivers, what can be shown to the customer, or how an epic compares with the old system.

In scope:

- Tech-doc writes two more documents, `12-DATABASE.md` and `13-CAPABILITIES.md`, and scouts the JVM data layer from a new reference `jvm-data.md`.
- `/roadmap` reads `13-CAPABILITIES.md` and writes a roadmap file with a summary table, an outcome and a demo per milestone, the features and the legacy items of each epic, and a legacy coverage table.
- A plain `/roadmap` takes a milestone plan and proposes the allocation of every epic to those milestones in one table.
- The four wording changes of `gin-workflow-87kq` (child bead of this epic).

Out of scope:

- A CLI command that checks coverage. The skills do the comparison; a command is a later epic if practice needs one.
- Renumbering the existing tech-doc files.
- Closing a milestone with a spillover summary and the move of open epics to the next milestone (`gin-workflow-milestone-close`).
- New `gin milestone` commands or fields. The allocation uses `gin milestone create`, `move`, and `estimate` as they are.
- A milestone field in Beads for the outcome or the demo. Both live in the roadmap file only.
- An HTML export of the roadmap, and showing the new data in gin-console (`gin-console-workflow-catchup`).
- Changes to the `gin-ba` skills and `/allocate`. A BA reads `13-CAPABILITIES.md` and the `Legacy:` line of an epic.
- A data scouting reference for stacks other than the JVM. The skill gives them one general sentence.

Assumptions:

- A feature stays the code-level unit in `02-FEATURES.md`. A capability is a group of features that serves one business purpose.
- The demo belongs to a milestone, not to an epic: a technical epic has nothing to show, and a customer demo is a flow across several epics.

## Requirements

### Tech-doc: `12-DATABASE.md`

- New template `templates/codebase/12-DATABASE.md` with the standard header and footer of the set and these sections:
  - `Datastores`: name, engine and version, where it is configured.
  - `Tables`: table or entity, purpose, owning service or module, key columns.
  - `Relationships`: a Mermaid `erDiagram`.
  - `Access Matrix`: one row per table, one column per service or module, each cell `R`, `W`, `RW`, or empty.
  - `Stored Logic`: procedures, triggers, views, and scheduled or batch jobs that read or write data.
  - `Migration Notes`: tables written by more than one service, tables no code references, business rules that live in the database.
- Every row of `Tables`, `Access Matrix`, and `Stored Logic` cites `file:line`; a cell without a citation is marked as inference.
- Not written when the scope has no datastore. A subsystem run writes it in the `<scope-slug>/` subfolder like the other files.
- Writer route: middle model.
- New reference `skills/tech-doc/references/jvm-data.md`: where a scout finds the data layer in JVM code (DDL files, Flyway and Liquibase migrations, `@Entity` and `@Table`, Hibernate `*.hbm.xml`, MyBatis mapper XML and annotations, SQL in JDBC and `JdbcTemplate` calls, datasource configuration in properties, `context.xml`, and JNDI). Notes are tagged `data`.
- For other stacks the skill tells scouts to read migrations, ORM models, and schema files.

### Tech-doc: `13-CAPABILITIES.md`

- New template `templates/codebase/13-CAPABILITIES.md` with the standard header and footer and these sections:
  - `Capability Catalog`: `Capability` (a `[a-z][a-z0-9-]*` name), `Summary` in business words, `Actors`, `Services`, `Status` (`proposed` or `confirmed`), `Scope`.
  - `Capability Map`: one row per feature: `Capability`, `Feature` (the name in the Feature Catalog of `02-FEATURES.md`), `Screens`, `Endpoints`, `Tables`. The cells hold names and link to `02-FEATURES.md`, `05-API.md`, and `12-DATABASE.md`, which hold the `file:line` evidence.
  - `Migration Inventory`: one row per capability with the number of screens, endpoints, tables, batch jobs, reports or exports, and outbound messages (email, SMS, push), and a total row.
  - `Unmapped`: features in no capability, tables no feature touches, and the screens and endpoints that `Coverage Gaps` of `02-FEATURES.md` lists without a feature.
  - `Conflicts`.
- The file always lives at the root of the output folder, also for a subsystem run, like `11-GLOSSARY.md`: a capability can span services.
- The writer merges into an existing file: a new capability is `proposed`; a `confirmed` row keeps its name and summary, and a run only adds features, services, and scopes to it; a different grouping or meaning for a `confirmed` capability goes to `Conflicts`, never into the row. Only the user sets `confirmed`.
- The writer starts after `02-FEATURES.md`, `05-API.md`, and `12-DATABASE.md`. Route: strongest model.
- Written when the scope has at least one feature.
- The report of the run names the number of new `proposed` capabilities, of `Conflicts` rows, and of `Unmapped` items.

### Roadmap

- Capability names come from `docs/specs/README.md` (SDD layout), else the Capability Catalog of `13-CAPABILITIES.md`, else the Feature Catalog of `02-FEATURES.md`, else the brief. With `13-CAPABILITIES.md` the `Capabilities:` line is written with the legacy layout too.
- `templates/roadmap.md` gains:
  - `## Summary`, after `## Goals`: a table `Milestone | Period | Outcome | Demo | Epics`, one row per milestone in the file, and one row `Unassigned` for epics without a milestone.
  - Under each `## Milestone:` heading: `Outcome:` (what exists at the end of the milestone, in business words) and `Demo:` (the flows that can be shown to the customer).
  - In each epic block: `Features:` (the features it delivers, by their names in the Capability Map or the brief) and `Legacy:` (the screens, endpoints, and tables of the old system it replaces, with their counts and the tech-doc section; `none` for new behaviour).
  - `## Legacy coverage`, written only when `13-CAPABILITIES.md` exists: a table `Capability | Legacy screens | Epics | Milestone | Status`. `Status` is `planned`, `not migrated: <reason>`, or `unplanned`. Every capability of the catalog has one row.
- `Goal:`, `Outcome:`, `Demo:`, and `Features:` are written for a manager: no file paths and no code identifiers. Paths stay in `Evidence:` and `Legacy:`.
- `/roadmap --milestone <id>` asks the PM for the demo of that milestone, or proposes one from the capabilities of the adopted epics. It proposes for adoption the epics the demo needs, and warns when the demo needs an epic that is left out, belongs to a later milestone, or does not fit the capacity.
- A plain `/roadmap` without a milestone plan writes `## Summary` with the `Unassigned` row and no `Outcome:` or `Demo:`.
- Milestone plan in a plain `/roadmap`:
  - In step 2 the skill asks for the milestone plan once: none, the open milestones of `gin milestone list --json`, or a list from the PM (title, start, end per milestone). The question does not count against `project.max_questions`.
  - In step 4 the skill proposes one allocation table: each milestone with its period, capacity (lanes times working days), `Outcome:`, `Demo:`, the epics with their estimates, and the sum of the estimates. It fills milestones in `end` order by dependency layer and capacity, as the adoption rule of `--milestone` does, and puts the foundation epics in the first milestone. The PM may state the demo of a milestone first; the epics that demo needs go into that milestone or an earlier one.
  - An epic that fits no milestone stays under `## Unassigned` with the reason (blocked, or over capacity). When the allocation ends after `Deadline:`, the skill names the overflow in working days.
  - The PM revises the table (moves epics, changes estimates, demos, and outcomes) until confirmed. Nothing is written before that.
  - In step 6, after the sync, the skill creates each milestone of the plan that Beads lacks with `gin milestone create`, then runs `gin milestone move` and `gin milestone estimate` per milestone, with the failure rules of `--milestone` step 5.
  - On a re-run, Beads wins for membership and estimates, as with `--milestone`; the skill reports each difference and proposes an allocation only for the epics without a milestone.
  - `/roadmap --milestone <id>` stays, for a later change to one milestone.
- `templates/epic.md` (the Beads description) gains `Features:` and `Legacy:`. `Outcome:` and `Demo:` are not written to Beads.
- The report of step 7 adds the number of capabilities, and how many are `planned`, `not migrated`, and `unplanned`.
- A capability that the PM does not confirm as `not migrated` and that no epic covers stays `unplanned`; the report names each one.

### Wording follow-ups (gin-workflow-87kq)

- `jvm-routes.md`, Velocity: `VelocityViewResolver` exists in Spring 4 and earlier (deprecated in 4.3, removed in 5); name `VelocityLayoutViewResolver` too.
- `webview-shells.md`: app-to-web calls (`evaluateJavascript` on Android, `evaluateJavaScript` on iOS) and the bridge object name from `addJavascriptInterface(obj, "<name>")`.
- Rule `money-bigdecimal`: construct from a `String` or `valueOf`, not a `double`. Rule `csrf-token`: the server must verify the token.

### Documentation

- The split-set table of the tech-doc skill, `docs/starters/brownfield.md` and `.vi.md`, and `docs/reference/skills.md` and `.vi.md` name the two new documents and the new roadmap sections.

## User Stories

### US-1: Database document of the old system
As a tech lead of a migration, I want tech-doc to describe the datastores, tables, and which service reads or writes each table, so that I can plan the data migration and see the tables that services share.

Acceptance criteria:
- A `/tech-doc` run on a scope with a datastore writes `12-DATABASE.md` with the six sections.
- Each row of `Tables`, `Access Matrix`, and `Stored Logic` has a `file:line` citation or is marked as inference.
- A table written by two services appears in `Migration Notes`.
- A scope without a datastore gets no `12-DATABASE.md`, and the other files keep their numbers.

### US-2: Capability inventory of the old system
As a manager of a 1-1 migration, I want a list of the capabilities of the old system with the features, screens, endpoints, and tables of each, so that I can count what has to be migrated and check that nothing is missed.

Acceptance criteria:
- A `/tech-doc` run writes `13-CAPABILITIES.md` at the root of the output folder with the catalog, the map, the inventory, and `Unmapped`.
- Every feature of the Feature Catalog of `02-FEATURES.md` is in exactly one row of the Capability Map or in `Unmapped`.
- The `Migration Inventory` counts of a capability equal the number of distinct screens, endpoints, and tables in its Capability Map rows.
- A new capability has the status `proposed`.

### US-3: Confirmed capabilities survive a re-run
As a BA, I want the capabilities I confirmed to keep their name and summary when tech-doc runs again, so that the analysis I based on them stays valid.

Acceptance criteria:
- After a re-run, a `confirmed` row has the same `Capability` and `Summary` as before.
- A re-run that groups the features of a `confirmed` capability differently adds a `Conflicts` row and leaves the catalog row unchanged.
- A re-run never sets `confirmed`.

### US-4: Roadmap a manager can read
As a manager, I want the roadmap file to say what each milestone delivers and what can be shown to the customer, and which features each epic delivers, so that I can report progress and prepare demos without reading code.

Acceptance criteria:
- The roadmap file has a `## Summary` table with one row per milestone and an `Unassigned` row.
- After `/roadmap --milestone <id>`, the block of that milestone has an `Outcome:` and a `Demo:` line, and its `Summary` row repeats them.
- Every epic block has a `Features:` line.
- `Goal:`, `Outcome:`, `Demo:`, and `Features:` hold no file path.

### US-5: Roadmap compared with the old system
As a manager of a migration, I want to see which epic replaces which part of the old system and which capabilities no epic covers, so that I can prove the plan misses nothing.

Acceptance criteria:
- With `13-CAPABILITIES.md` present, the roadmap file has `## Legacy coverage` with one row per capability of the catalog.
- Each row has the status `planned`, `not migrated: <reason>`, or `unplanned`.
- Every epic block has a `Legacy:` line that names the legacy items it replaces, or `none`.
- The `/roadmap` report names each `unplanned` capability.
- Without `13-CAPABILITIES.md` the roadmap file has no `## Legacy coverage` section.

### US-6: Demo-driven milestone
As a PM, I want to state the demo of a milestone and have `/roadmap --milestone` propose the epics that demo needs, so that each milestone ends with something to show.

Acceptance criteria:
- `/roadmap --milestone <id>` asks for the demo of the milestone or proposes one before it proposes the adoption.
- The proposed adoption contains the epics the demo needs, or a warning that names each one left out and why.

### US-8: Whole roadmap allocated to milestones in one run
As a PM who knows the milestones and the deadline of the project, I want a plain `/roadmap` to propose which epics go into which milestone, so that I confirm the whole plan in one table instead of one run per milestone.

Acceptance criteria:
- A plain `/roadmap` asks for the milestone plan and accepts a list of milestones with a title, a start, and an end.
- Before anything is written, the skill shows one table with every milestone, its capacity, its outcome and demo, its epics, and the sum of their estimates.
- After the PM confirms, each milestone of the plan exists in Beads, each allocated epic is a member of its milestone, and the roadmap file lists the epics under their `## Milestone:` headings.
- An epic that fits no milestone is under `## Unassigned` with a reason.
- An allocation that ends after `Deadline:` is reported with the overflow in working days.
- No epic is in a milestone that ends before the milestone of an epic it depends on.

### US-7: Epic description for discuss and the BA
As a BA starting `/discuss <epic-id>`, I want the epic bead to name the features and the legacy items of the epic, so that I know which screens to capture.

Acceptance criteria:
- An epic bead created by `/roadmap` has `Features:` and `Legacy:` lines in its description.
- An `in_progress` epic keeps its description on a re-run and gets one `[gin roadmap]` comment that names the difference.

## Errors and compatibility

- A roadmap file written before this change stays valid input: the new lines and sections are optional for `roadmap_file.py`, which reads only `Deadline:` and the number that starts `AI capacity:`.
- On the first re-run of `/roadmap` after this change, the new lines are presented as differences for the PM to confirm. An `in_progress`, closed, or adopted epic keeps its Beads description; the existing comment rule reports the added `Features:` and `Legacy:` lines once.
- A tech-doc folder written before this change stays valid: the next run adds `12-DATABASE.md` and `13-CAPABILITIES.md` and renames nothing.
- Regrounding does not create the two documents; it checks the pages that exist. In `13-CAPABILITIES.md` a row left without evidence moves to `Follow-up` and is never deleted, as in the glossary.
- A project override of `roadmap.md` or `epic.md` in `.agent-workflow/templates/` keeps working and does not get the new lines until the project updates it.
- gin-console reads neither the roadmap file nor the tech-doc folder, so nothing changes there.

## Testing

- `tests/workflow_core/test_tech_doc_skill.py`: the split-set table and the templates list `12-DATABASE.md` and `13-CAPABILITIES.md`; the skill names `jvm-data.md`, the merge rule, and the root location of `13-CAPABILITIES.md`; the 87kq wording is present.
- Roadmap skill tests: the skill names the milestone plan question, the allocation table, and the order create, move, estimate.
- Roadmap skill and template tests: the template has `## Summary`, `Outcome:`, `Demo:`, `Features:`, `Legacy:`, and `## Legacy coverage`; `epic.md` has `Features:` and `Legacy:`; the skill names the capability source order and the three coverage statuses.
- `roadmap_file.py` tests: a file with the new sections gives the same `Deadline` and lanes.
- Packaging and skill-routing tests pass with the new reference and templates in every harness build.
- Rule pack tests pass with the two reworded rules.

## Open Technical Questions

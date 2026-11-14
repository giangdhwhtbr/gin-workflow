# Plan: Legacy inventory in tech-doc and a manager-readable roadmap

Epic: gin-workflow-legacy-inventory
Spec: `.planning/specs/2026-11-14-legacy-inventory-design.md`

## Objective

A `/tech-doc` run writes `12-DATABASE.md` and `13-CAPABILITIES.md`. A `/roadmap` run reads the capability document, allocates every epic to the milestones of a plan in one confirmed table, and writes a roadmap file with a summary table, an outcome and a demo per milestone, the features and legacy items of each epic, and a legacy coverage table. The four wording changes of `gin-workflow-87kq` are in.

Goal: the old system can be counted (capabilities, screens, endpoints, tables) and the roadmap shows a manager what each milestone delivers and that no capability is missed.

Architecture: only instruction files change (templates, skills, skill references, rule packs) plus their tests and the user documentation. No Python script changes: `roadmap_file.py` already ignores unknown lines, and the allocation uses `gin milestone create`, `move`, and `estimate` as they are.

Tech stack: Markdown templates and skills under `plugins/gin-workflow/src/`, `unittest` tests run by `pytest`.

Global constraints (from the spec):

- A roadmap file and a tech-doc folder written before this change stay valid input. Nothing is renamed.
- `13-CAPABILITIES.md` lives at the root of the output folder and merges on a re-run; only the user sets `confirmed`.
- `Outcome:` and `Demo:` live in the roadmap file only, never in Beads. The demo belongs to a milestone, not to an epic.
- No new `gin` command, flag, or Beads field.
- `skills/roadmap/SKILL.md` stays within 12,000 characters (`tests/workflow_core/test_token_budget.py:81`); it has 11,985 today, so the new roadmap rules live in reference files.

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
- Problem statement: tech-doc has no database document and no capability concept, so a migration has nothing countable to check against; the roadmap file does not say what a milestone delivers, what can be demonstrated, or how an epic compares with the old system; a plain `/roadmap` cannot allocate epics to known milestones.
- Success criteria: the acceptance criteria of US-1 to US-8 of the spec; the test files named in each track pass; `python3 -m pytest -n auto` passes at the end.
- Constraints: the global constraints above.
- Non-goals: a CLI coverage check; renumbering tech-doc files; closing a milestone (`gin-workflow-milestone-close`); an HTML export; gin-console; changes to `gin-ba` skills and `/allocate`; a data scouting reference for stacks other than the JVM.

## Approach Options
### Option 1: Rules in the skills, long rules in references
- Summary: two new templates and one new reference for tech-doc; for roadmap, the template changes plus two new references (`manager-view.md`, `milestone-plan.md`) that `SKILL.md` links from short sentences.
- Pros: keeps `roadmap/SKILL.md` within its 12,000 character limit; each reference has one topic; follows `way-of-working.md` and `capability-epics.md`.
- Cons: a `/roadmap` run reads two more files.

### Option 2: Everything in the two SKILL.md files
- Summary: write all new rules into `tech-doc/SKILL.md` and `roadmap/SKILL.md`.
- Pros: one file per skill.
- Cons: breaks the roadmap budget test, or needs the limit raised.

### Recommended Approach
- Selected option: Option 1.
- Rationale: the budget test is an enforced invariant, and the references pattern already exists in both skills.

## Scope
- In scope: `templates/codebase/12-DATABASE.md`, `templates/codebase/13-CAPABILITIES.md`, `skills/tech-doc/` (skill, `jvm-data.md`, wording in `jvm-routes.md` and `webview-shells.md`), rules `java.md` and `jvm-templates.md`, `templates/roadmap.md`, `templates/epic.md`, `skills/roadmap/` (skill, two references), their tests, and the user documentation.
- Out of scope: the non-goals above; any file under `plugins/*/dist/` (built by `install.sh`).

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 names the files Track 1 creates, Track 3 documents both, and Tracks 1 and 2 both edit the packaging test, so one track at a time avoids conflicts.
```

## Tasks

### Track 1: Tech-doc database and capability documents
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/templates/codebase/12-DATABASE.md`
  - Create `plugins/gin-workflow/src/templates/codebase/13-CAPABILITIES.md`
  - Create `plugins/gin-workflow/src/skills/tech-doc/references/jvm-data.md`
  - Modify `plugins/gin-workflow/src/skills/tech-doc/SKILL.md` (roles table, steps 3, 4, 5, 7, split-set table, regrounding)
  - Modify `plugins/gin-workflow/src/skills/tech-doc/references/jvm-routes.md:54` (Velocity resolver wording)
  - Modify `plugins/gin-workflow/src/skills/tech-doc/references/webview-shells.md` (app-to-web calls, bridge object name)
  - Modify `plugins/gin-workflow/src/rules/java.md:10` (`money-bigdecimal`)
  - Modify `plugins/gin-workflow/src/rules/jvm-templates.md:9` (`csrf-token`)
  - Test `tests/workflow_core/test_tech_doc_skill.py`
  - Test `tests/gin_orchestrator/test_harness_packaging.py:34-35,68-70` (new reference and templates in the expected file list)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded edits to instruction files with exact text given below; the judgement is keeping the existing tested phrases intact.
- **Acceptance criteria**: US-1, US-2, US-3 of the spec, and the wording follow-ups; the tests below pass.
- **Estimated complexity**: medium

Steps:

1. Failing tests first, in `tests/workflow_core/test_tech_doc_skill.py`:
   - Extend `READING_ORDER` with `"DATABASE", "CAPABILITIES"`.
   - In `test_writer_routes_for_documents` add `self.assertIn("`DATABASE`", groups["middle"])` and `self.assertIn("`CAPABILITIES`", groups["strongest"])`.
   - Add:
     ```python
     def test_capabilities_start_after_features_api_and_database(self):
         self.assertIn("`13-CAPABILITIES.md` starts after `02-FEATURES.md`, `05-API.md`, and `12-DATABASE.md`", self.text)

     def test_capabilities_live_at_output_root_and_keep_confirmed_rows(self):
         self.assertIn("`11-GLOSSARY.md` and `13-CAPABILITIES.md` are the exceptions: they always live at the root of the output folder", self.text)
         self.assertIn("a `confirmed` capability keeps its name and `Summary`", self.text)
         self.assertIn("a different grouping or meaning for a `confirmed` capability goes to `Conflicts`", self.text)

     def test_database_rows_cite_evidence_and_file_is_skipped_without_datastore(self):
         self.assertIn("Every `Tables`, `Access Matrix`, and `Stored Logic` row of `12-DATABASE.md` cites `file:line`", self.text)
         self.assertIn("Not written when the scope has no datastore", self.text)

     def test_database_and_capability_templates_have_their_sections(self):
         database = (TEMPLATES / "12-DATABASE.md").read_text(encoding="utf-8")
         for heading in ("## Datastores", "## Tables", "## Relationships", "## Access Matrix", "## Stored Logic",
                         "## Migration Notes", "## Inference And Uncertainty", "## Follow-up"):
             self.assertIn(heading, database)
         self.assertIn("erDiagram", database)
         capabilities = (TEMPLATES / "13-CAPABILITIES.md").read_text(encoding="utf-8")
         self.assertIn("| Capability | Summary | Actors | Services | Scope | Status |", capabilities)
         self.assertIn("| Capability | Feature | Screens | Endpoints | Tables |", capabilities)
         self.assertIn("| Capability | Screens | Endpoints | Tables | Batch jobs | Reports | Outbound messages |", capabilities)
         for heading in ("## Capability Catalog", "## Capability Map", "## Migration Inventory", "## Unmapped",
                         "## Conflicts", "## Inference And Uncertainty", "## Follow-up"):
             self.assertIn(heading, capabilities)
     ```
   - In `test_glossary_lives_at_output_root_and_keeps_confirmed_terms` replace the first assertion by the new sentence of `test_capabilities_live_at_output_root_and_keep_confirmed_rows` (the old sentence changes).
   - In `test_scouting_references_are_linked_and_name_their_apis` add `self.assertIn("[jvm-data.md](references/jvm-data.md)", self.text)` and extend `expected` with `"jvm-data.md": ("@Entity", "hbm.xml", "Liquibase", "JdbcTemplate", "mapper")`, add `"VelocityLayoutViewResolver"` to the `jvm-routes.md` tuple and `"evaluateJavascript"`, `"evaluateJavaScript"` to the `webview-shells.md` tuple.
   - In `tests/gin_orchestrator/test_harness_packaging.py` add `"skills/tech-doc/references/jvm-data.md"`, `"templates/codebase/12-DATABASE.md"`, and `"templates/codebase/13-CAPABILITIES.md"` to the expected list next to lines 34 and 68.
   - Run `python3 -m pytest tests/workflow_core/test_tech_doc_skill.py`; expected: the new and changed tests fail.

2. Create `templates/codebase/12-DATABASE.md`:
   ````markdown
   # DATABASE

   Analysis Date: {{date}}
   Scope: {{scope}}
   Evidence:
   Index Use:

   ## Datastores

   | Datastore | Engine and version | Configured in (file:line) |
   |---|---|---|

   ## Tables

   | Table or entity | Purpose | Owner (service/module) | Key columns | Evidence (file:line) |
   |---|---|---|---|---|

   ## Relationships

   ```mermaid
   erDiagram
   ```

   ## Access Matrix

   <!-- One column per service or module. A cell is R, W, RW, or empty, with file:line; a cell without a citation is marked as inference. -->

   | Table | Service or module |
   |---|---|

   ## Stored Logic

   | Name | Kind (procedure, trigger, view, job) | Reads | Writes | Evidence (file:line) |
   |---|---|---|---|---|

   ## Migration Notes

   <!-- Tables written by more than one service, tables no code references, business rules that live in the database. -->

   ## Inference And Uncertainty

   ## Follow-up
   ````

3. Create `templates/codebase/13-CAPABILITIES.md`:
   ```markdown
   # CAPABILITIES

   Analysis Date: {{date}}
   Scope: {{scope}}
   Evidence:
   Index Use:

   <!-- A capability groups the features that serve one business purpose. A new row is proposed; only the user sets confirmed.
        Map cells hold names and link to 02-FEATURES.md, 05-API.md, and 12-DATABASE.md, which hold the file:line evidence. -->

   ## Capability Catalog

   | Capability | Summary | Actors | Services | Scope | Status |
   |---|---|---|---|---|---|

   ## Capability Map

   | Capability | Feature | Screens | Endpoints | Tables |
   |---|---|---|---|---|

   ## Migration Inventory

   | Capability | Screens | Endpoints | Tables | Batch jobs | Reports | Outbound messages |
   |---|---|---|---|---|---|---|
   | Total | | | | | | |

   ## Unmapped

   <!-- Features in no capability, tables no feature touches, and the screens and endpoints that Coverage Gaps of 02-FEATURES.md lists without a feature. -->

   ## Conflicts

   | Capability | Existing | Candidate | Evidence |
   |---|---|---|---|

   ## Inference And Uncertainty

   ## Follow-up
   ```

4. Create `skills/tech-doc/references/jvm-data.md`, in the style of `jvm-routes.md` (one `##` block per source, bullets that start with a verb):
   - Opening: use when the code area is Java, Kotlin, or Groovy on the JVM; tag notes `data` (for `12-DATABASE.md`) and `features` when a table belongs to a feature; every note carries `file:line`.
   - `## Schema files`: search `*.sql` DDL, Flyway `V*__*.sql` under `db/migration`, Liquibase changelogs (`databaseChangeLog` in XML, YAML, or JSON); record each `CREATE TABLE`, key, index, view, procedure, and trigger; the latest migration wins.
   - `## JPA and Hibernate`: search `@Entity`, `@Table`, `@Column`, `@Id`, `@OneToMany`, `@ManyToOne`, `@ManyToMany`, `@JoinColumn`; read `*.hbm.xml` (`<class table>`, `<property column>`, `<many-to-one>`, `<set>`); read `persistence.xml` and `hibernate.cfg.xml` for the unit and dialect; an entity without a `@Table` name maps to its class name, marked as inference.
   - `## MyBatis`: read mapper XML (`<mapper namespace>`, `<select>`, `<insert>`, `<update>`, `<delete>`) and `@Select`, `@Insert`, `@Update`, `@Delete`; record the tables each statement reads and writes.
   - `## JDBC`: search `JdbcTemplate`, `NamedParameterJdbcTemplate`, `PreparedStatement`, `createStatement`, and `CallableStatement`; read the SQL string for its tables; a `CallableStatement` or `{call ...}` names a stored procedure; SQL built at runtime is recorded with its pattern and marked as inference.
   - `## Datasources`: read `application.properties` and `application.yml` (`spring.datasource.*`), `context.xml` and `server.xml` (`<Resource>`), `web.xml` (`<resource-ref>`), and JNDI lookups; record the engine from the driver class or URL, never a password or a full URL with credentials.
   - `## Batch and scheduled jobs`: search `@Scheduled`, Quartz `Job` classes and `quartz.properties`, Spring Batch `Job` and `Step` beans, and cron entries in deployment files; record the tables each job reads and writes.
   - `## Matching`: an access-matrix cell comes from a statement or an entity use in that service; `R` for a read, `W` for a write; a table in the schema that no code references goes to `Migration Notes`; a table written by two services goes there too.

5. Edit `skills/tech-doc/SKILL.md`. Keep every phrase the existing tests assert.
   - Roles table, Writer row: add `DATABASE` to the middle-model list and `CAPABILITIES` to the strongest-model list; change the ordering sentence to: "`02-FEATURES.md` starts after `05-API.md`; `13-CAPABILITIES.md` starts after `02-FEATURES.md`, `05-API.md`, and `12-DATABASE.md`; the other writers run in parallel."
   - Scout row: add `data` to the example topics.
   - Step 3, after the JVM and WebView sentence, add: "For `12-DATABASE.md`, scouts tag `data` notes for datastores, tables, relations, the statements that read or write each table, and stored logic, from migrations, ORM models, and schema files; for JVM code, follow [jvm-data.md](references/jvm-data.md)."
   - Step 4: replace "`11-GLOSSARY.md` is the exception: it always lives at the root of the output folder, also for a subsystem run, so one glossary serves the whole repository." by "`11-GLOSSARY.md` and `13-CAPABILITIES.md` are the exceptions: they always live at the root of the output folder, also for a subsystem run, so one glossary and one capability catalog serve the whole repository."
   - Step 5, after the glossary merge sentences, add: "Every `Tables`, `Access Matrix`, and `Stored Logic` row of `12-DATABASE.md` cites `file:line`. The `13-CAPABILITIES.md` writer groups the features of `02-FEATURES.md` by business purpose and merges into the existing file: every feature is in one Capability Map row or in `Unmapped`; a new capability is `proposed`; a `confirmed` capability keeps its name and `Summary`, and a run only adds features, services, and scopes to it; a different grouping or meaning for a `confirmed` capability goes to `Conflicts`, never into the row; the `Migration Inventory` counts the distinct screens, endpoints, and tables of the capability's map rows."
   - Step 7, add: "For `13-CAPABILITIES.md`, report the number of new `proposed` capabilities, of `Conflicts` rows, and of `Unmapped` items."
   - Split-set table, two rows after `11-GLOSSARY.md`:
     - `12-DATABASE.md`: "datastores, tables and their owners, relations, which service reads or writes each table, stored logic, migration notes. Not written when the scope has no datastore"
     - `13-CAPABILITIES.md`: "capability catalog (`proposed` or `confirmed`), map of each capability to its features, screens, endpoints, and tables, migration inventory counts, unmapped items, conflicts. Written when the scope has a feature; always at the root of the output folder"
   - Regrounding step 2: change "In `11-GLOSSARY.md`, a row left without evidence" to "In `11-GLOSSARY.md` and `13-CAPABILITIES.md`, a row left without evidence" (the rest of the sentence, "moves to `Follow-up`; it is never deleted", stays).

6. Wording follow-ups (87kq):
   - `jvm-routes.md:54`: "For Spring 4 and earlier, read the `VelocityViewResolver` or `VelocityLayoutViewResolver` bean and record its `prefix` and `suffix`; join them to each returned view name. Spring 4.3 deprecated both and Spring 5 removed them; on Spring 5 or later look for a project-owned resolver class instead."
   - `webview-shells.md`, Android: change the bridge bullet to record the object name: "Search `addJavascriptInterface(obj, "<name>")` and the `@JavascriptInterface` methods on the bound object. Record `<name>`; each method is a bridge method." Add: "Search `evaluateJavascript` and `loadUrl("javascript:...")` for app-to-web calls; record the function each one calls." iOS: add "Search `evaluateJavaScript` for app-to-web calls; record the function each one calls."
   - `java.md:10`: "... with BigDecimal built from a String or `BigDecimal.valueOf`, with an explicit scale and RoundingMode; never use float or double, and never `new BigDecimal(double)`."
   - `jvm-templates.md:9`: append "; the server verifies the token on each such request."
   - Check each pack stays within its body limit: `python3 -m pytest tests/workflow_core/test_token_budget.py -k rule_pack`.

7. Run `python3 -m pytest tests/workflow_core/test_tech_doc_skill.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_rules.py tests/workflow_core/test_rules_checks.py tests/workflow_core/test_skill_routing.py tests/workflow_core/test_specs.py tests/gin_orchestrator/test_harness_packaging.py`; expected: all pass. Commit: `feat(tech-doc): database and capability documents, JVM data scouting (gin-workflow-legacy-inventory)`.

### Track 2: Roadmap template, manager view, and milestone plan
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/templates/roadmap.md`
  - Modify `plugins/gin-workflow/src/templates/epic.md`
  - Create `plugins/gin-workflow/src/skills/roadmap/references/manager-view.md`
  - Create `plugins/gin-workflow/src/skills/roadmap/references/milestone-plan.md`
  - Modify `plugins/gin-workflow/src/skills/roadmap/SKILL.md` (steps 2, 4, 5, 6, 7; `--milestone` steps 2 and 4)
  - Test `tests/workflow_core/test_skill_routing.py:60-65`
  - Test `tests/workflow_core/test_specs.py:362-388`
  - Test `tests/workflow_core/test_token_budget.py:81-85`
  - Test `tests/workflow_core/test_roadmap_file.py`
  - Test `tests/gin_orchestrator/test_harness_packaging.py` (the two references in the expected list)
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `medium`
- **Why:** the skill is 15 characters under its limit and several tests assert its sentences, so text has to move to references without losing a rule; the allocation rule must agree with the existing adoption, sync, and re-run rules.
- **Acceptance criteria**: US-4 to US-8 of the spec; the tests below pass; `skills/roadmap/SKILL.md` has at most 12,000 characters.
- **Estimated complexity**: high

Steps:

1. Failing tests first:
   - `tests/workflow_core/test_specs.py`, next to line 388, assert on `run_specs(root, "template", "roadmap.md").stdout`: `"## Summary"`, `"| Milestone | Period | Outcome | Demo | Epics |"`, `"Outcome:"`, `"Demo:"`, `"Features:"`, `"Legacy:"`, `"## Legacy coverage"`, `"| Capability | Legacy screens | Epics | Milestone | Status |"`; and on `epic.md`: `"Features: {{features}}"`, `"Legacy: {{legacy}}"`, and that `"Demo:"` and `"Outcome:"` are absent.
   - `tests/workflow_core/test_skill_routing.py`, new test `test_roadmap_manager_view_and_milestone_plan`: `SKILL.md` contains `[manager view](references/manager-view.md)`, `[milestone plan](references/milestone-plan.md)`, `` `Features:` ``, `` `Legacy:` ``, and `13-CAPABILITIES.md`; `text.index("13-CAPABILITIES.md") < text.index("02-FEATURES.md")` within the `Capabilities:` sentence of step 4; `manager-view.md` contains `## Legacy coverage`, `` `planned` ``, `` `not migrated: <reason>` ``, `` `unplanned` ``, `no file paths`, and `never in Beads`; `milestone-plan.md` contains `gin milestone create`, `gin milestone move`, `gin milestone estimate`, `Beads wins`, `## Unassigned`, and `Deadline:`, with `create` before `move` before `estimate` in the write block.
   - `tests/workflow_core/test_token_budget.py:81`: add both new references with a limit of 4,000 characters each.
   - `tests/workflow_core/test_roadmap_file.py`: a new case that reads a roadmap file with `## Summary`, `Outcome:`, `Demo:`, `Features:`, `Legacy:`, and `## Legacy coverage` and gets the same deadline and lanes as the same file without them (follow the existing cases of the file for the helper it uses).
   - `tests/gin_orchestrator/test_harness_packaging.py`: add `"skills/roadmap/references/manager-view.md"` and `"skills/roadmap/references/milestone-plan.md"`.
   - Run those five files; expected: the new assertions fail, the `roadmap_file` case passes (no code change is needed there; it guards compatibility).

2. `templates/roadmap.md`:
   - In the header comment add: "Summary, Outcome:, Demo:, Features:, Legacy:, and Legacy coverage are written per the skill's references/manager-view.md; Outcome: and Demo: need a milestone; Legacy coverage needs 13-CAPABILITIES.md. Older files without them stay valid."
   - After `## Goals` add:
     ```markdown
     ## Summary

     | Milestone | Period | Outcome | Demo | Epics |
     |---|---|---|---|---|
     ```
   - In the milestone block, right under the `## Milestone:` heading and before `Spec ready by:`, add `Outcome:` and `Demo:` lines (empty values).
   - In the epic block add `Features:` after `Out of scope:` and `Legacy:` after `Capabilities:`.
   - After `## Unassigned` add:
     ```markdown
     ## Legacy coverage

     | Capability | Legacy screens | Epics | Milestone | Status |
     |---|---|---|---|---|
     ```

3. `templates/epic.md`: add `Features: {{features}}` after `Out of scope:` and `Legacy: {{legacy}}` after `Capabilities:`.

4. Create `skills/roadmap/references/manager-view.md` (at most 4,000 characters), opening "Read on `/roadmap` when presenting and writing the roadmap (steps 4, 5, and 7).", with these blocks:
   - `## Wording`: `Goal:`, `Outcome:`, `Demo:`, and `Features:` are written for a manager: business words, no file paths, no code identifiers. Paths stay in `Evidence:` and `Legacy:`.
   - `## Summary`: one row per `## Milestone:` block in `end` order with its period, `Outcome:`, `Demo:`, and epic titles; a last row `Unassigned` with the epics without a milestone and empty outcome and demo.
   - `## Outcome and Demo`: `Outcome:` says what exists at the end of the milestone; `Demo:` names the user flows that can be shown to the customer, each backed by an epic of this milestone or an earlier one. Written only under a milestone heading, in the roadmap file, never in Beads. The demo belongs to a milestone, not to an epic.
   - `## Features and Legacy`: `Features:` lists the features the epic delivers, by their names in the Capability Map of `13-CAPABILITIES.md`, else the Feature Catalog, else the brief. `Legacy:` names what the epic replaces in the old system with counts and the tech-doc section, for example "12 screens, 31 endpoints, 9 tables (13-CAPABILITIES.md#Capability Map: orders)"; `none` for new behaviour. Both are copied to the epic's Beads description.
   - `## Legacy coverage`: written only when `13-CAPABILITIES.md` exists; one row per capability of its catalog: the screen count from `Migration Inventory`, the epics whose `Capabilities:` name it, their milestone, and `Status`: `planned` (an epic covers it), `not migrated: <reason>` (the PM confirmed it is left out), or `unplanned` (no epic and no decision). Ask the PM about each `unplanned` capability once, together, when presenting; this does not count against `project.max_questions`.
   - `## Report`: the number of capabilities and how many are `planned`, `not migrated`, and `unplanned`, naming each `unplanned` one.

5. Create `skills/roadmap/references/milestone-plan.md` (at most 4,000 characters), opening "Read on a plain `/roadmap` (no `--milestone`).", with these blocks:
   - `## Estimates`: the measured-pace text moved out of `--milestone` step 2 of `SKILL.md`, unchanged in meaning (from "List the closed `roadmap` epics" to "Revise them on request").
   - `## Plan`: in step 2 ask once for the milestone plan: none; the open milestones of `gin milestone list --json`; or a list from the PM with a title, a start, and an end per milestone. The question does not count against `project.max_questions`. With none, every epic stays under `## Unassigned` and the rest of this reference does not apply.
   - `## Allocation`: in step 4 present one table: per milestone its period, capacity (lanes times working days, per the Load block of way of working), `Outcome:`, `Demo:`, its epics with estimates, and the sum of the estimates. Fill milestones in `end` order by dependency layer: epics with no open blocker first; an epic never goes into a milestone that ends before the milestone of an epic it depends on; foundation epics go into the first milestone; stop filling a milestone when the sum reaches its capacity. When the PM states the demo of a milestone first, the epics that demo needs go into that milestone or an earlier one; name each one that does not fit. An epic that fits no milestone stays under `## Unassigned` with the reason (blocked, or over capacity). When the last epic ends after `Deadline:`, name the overflow in working days. Revise until the PM confirms; write nothing before that.
   - `## Write`: in step 6, after the sync, and after the roadmap PR merges when `team.approvals.roadmap` lists roles: for each milestone of the plan that Beads lacks run `gin milestone create "<title>" --start <date> --end <date>`; then per milestone `gin milestone move <epic>... --to <id>` and `gin milestone estimate <epic> <days>`. Failures follow `--milestone` step 5. The team permission check of `--milestone` step 1 applies before the first write.
   - `## Re-run`: Beads wins for membership and estimates; report each difference without writing Beads; propose an allocation only for the epics without a milestone. `/roadmap --milestone <id>` changes one milestone later.

6. Edit `skills/roadmap/SKILL.md`, then check `wc -c` is at most 12,000:
   - `--milestone` step 2: replace the sentences moved to `## Estimates` by "from the measured pace and the AI capacity, per the Estimates block of [milestone plan](references/milestone-plan.md)". Keep "Never ask the PM for estimates" only inside the reference. Add: "Ask the demo of the milestone, or propose one from the capabilities of the epics, and propose for adoption the epics that demo needs; name each one left out and why."
   - `--milestone` step 4: add `Outcome:` and `Demo:` to what the milestone block opens with, "per [manager view](references/manager-view.md)".
   - Step 2: add "On a plain run, ask the milestone plan per [milestone plan](references/milestone-plan.md)."
   - Step 4: add `Features:` and `Legacy:` to the epic fields; change the capability source to "from `docs/specs/README.md`, else the Capability Catalog of `13-CAPABILITIES.md`, else the Feature Catalog of `02-FEATURES.md`, else the brief", and "omitted with the legacy layout" to "omitted with the legacy layout unless `13-CAPABILITIES.md` exists"; add "Present the summary, the legacy coverage, and, with a milestone plan, the allocation table, per [manager view](references/manager-view.md) and [milestone plan](references/milestone-plan.md)."
   - Step 5: "A plain `/roadmap` without a milestone plan omits the milestone heading ..." (the existing sentence gains "without a milestone plan").
   - Step 6, description bullet: add `Features:` and `Legacy:` to the lines copied from the file; add one bullet "with a milestone plan, create the milestones and set membership per the Write block of [milestone plan](references/milestone-plan.md)".
   - Step 7: add "the capability counts of [manager view](references/manager-view.md)".
   - Keep verbatim the sentences asserted by `tests/install_smoke_test.sh:186-190`, `tests/workflow_core/test_epic_comments.py:69-81`, `tests/workflow_core/test_skill_routing.py:60-65`, and `tests/workflow_core/test_agents_block.py:188`.

7. Run `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_specs.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_roadmap_file.py tests/workflow_core/test_epic_comments.py tests/workflow_core/test_agents_block.py tests/workflow_core/test_milestone_cli.py tests/gin_orchestrator/test_harness_packaging.py`; expected: all pass. Commit: `feat(roadmap): manager view, legacy coverage, and milestone plan allocation (gin-workflow-legacy-inventory)`.

### Track 3: User documentation
- **Dependencies**: Track 1, Track 2
- **Files**:
  - Modify `docs/starters/brownfield.md:204-206`, `docs/starters/brownfield.vi.md` (the same passage)
  - Modify `docs/reference/skills.md`, `docs/reference/skills.vi.md` (the tech-doc and roadmap entries)
  - Modify `docs/guides/customizing-templates.md:131` (the roadmap template paragraph)
  - Test `tests/workflow_core/test_walkthrough_docs.py`
- **Provider role**: `docs`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** documentation edits that restate rules already written in the skills and templates.
- **Acceptance criteria**: the documentation requirement of the spec; each page names `12-DATABASE.md` and `13-CAPABILITIES.md` or the new roadmap sections where it describes the tech-doc set or the roadmap file; the Vietnamese pages say the same as the English ones; the docs tests pass.
- **Estimated complexity**: low

Steps:

1. Run `gin rules --files docs/starters/brownfield.md docs/reference/skills.md docs/guides/customizing-templates.md` and follow the `docs` pack.
2. `brownfield.md` and `.vi.md`, the "You get" passage: add that the set holds `12-DATABASE.md` (datastores, tables, which service reads or writes each) when the scope has a datastore, and `13-CAPABILITIES.md` (the capabilities of the old system with their features, screens, endpoints, tables, and counts, each `proposed` until the user confirms it). In the roadmap step of the same starter, say that a plain `/gin:roadmap` asks for the milestone plan and proposes the allocation, and that the file shows the outcome and demo of each milestone and the legacy coverage.
3. `skills.md` and `.vi.md`: in the tech-doc entry add the two documents to the output; in the roadmap entry add the summary table, `Outcome:` and `Demo:` per milestone, `Features:` and `Legacy:` per epic, the legacy coverage table, and the milestone plan of a plain run.
4. `customizing-templates.md`: after the way-of-working paragraph, one paragraph: which lines and sections of `roadmap.md` `/gin:roadmap` fills (`## Summary`, `Outcome:`, `Demo:`, `Features:`, `Legacy:`, `## Legacy coverage`), that `epic.md` carries `Features:` and `Legacy:`, and that a project override without them keeps working without the new lines.
5. Run `python3 -m pytest tests/workflow_core/test_walkthrough_docs.py tests/workflow_core/test_docs*.py`; expected: all pass. Commit: `docs: tech-doc database and capability documents, roadmap manager view (gin-workflow-legacy-inventory)`.

## Integration
- **Branch**: feat/legacy-inventory
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes on `feat/legacy-inventory` after Track 3
- [ ] `wc -c plugins/gin-workflow/src/skills/roadmap/SKILL.md` is at most 12,000
- [ ] `gin specs template codebase/12-DATABASE.md`, `gin specs template codebase/13-CAPABILITIES.md`, `gin specs template roadmap.md`, and `gin specs template epic.md` print the new content
- [ ] After `./install.sh`, a `/tech-doc` run on a legacy JVM workspace writes both documents and a `/roadmap` run shows the allocation table (manual, by the user)

## Notes
- Parent Bead: `gin-workflow-legacy-inventory` stays open until the human-confirmed merge. Track beads close after tests and review pass.
- `gin-workflow-87kq` is already a child of the epic and its work is step 6 of Track 1: close it together with the Track 1 bead, or the epic never reaches `implementation_complete`.
- Solo work: no push before the epic is complete; ship merges locally and pushes once.

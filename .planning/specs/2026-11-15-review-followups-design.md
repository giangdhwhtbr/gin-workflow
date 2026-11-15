# Follow-ups from the legacy-inventory, sprint-retro, and milestone-close reviews

Epic: gin-workflow-4p75
Kind: technical
Status: draft for user review.

## Goal and scope

Apply the minor review notes left by `gin-workflow-legacy-inventory` (Tracks 1 to 3), `gin-workflow-sprint-retro.1`, and `gin-workflow-milestone-close.1`. Each note makes a skill rule or a documentation sentence exact; none adds a command or changes a format.

In scope, by module:

- A. Roadmap: `plugins/gin-workflow/src/skills/roadmap/references/manager-view.md`, `plugins/gin-workflow/src/skills/roadmap/references/milestone-plan.md`, `docs/starters/brownfield.md` and `.vi.md`, `docs/guides/customizing-templates.md` and `.vi.md`, the `roadmap` row of `docs/reference/skills.md` and `.vi.md`.
- B. Tech-doc: `plugins/gin-workflow/src/skills/tech-doc/SKILL.md`, `plugins/gin-workflow/src/skills/tech-doc/references/jvm-data.md`.
- C. Retro: `plugins/gin-workflow/src/skills/retro/SKILL.md`, its test, the `retro` row of the skills reference.
- D. Milestone close: `plugins/gin-workflow/src/skills/milestone-close/SKILL.md`, the `milestone-close` row of the skills reference.

Out of scope:

- `plugins/gin-workflow/src/skills/roadmap/SKILL.md` (17 characters below its 12,000 limit): every roadmap change goes into the references.
- The `[gin retro]` and `[gin close]` formats, the CLI, and gin-console.
- `gin-workflow-ghcf`, closed by the user without a fix.

## Approach

### A. Roadmap

- `manager-view.md`, Outcome and Demo block: add that `/roadmap --milestone <id>` asks for, or proposes, both the `Outcome:` and the `Demo:` of the milestone (US-4 of the legacy-inventory spec needs both; `--milestone` step 2 of `SKILL.md` names only the demo).
- `manager-view.md`, Legacy coverage block: rows use the capability names of the Capability Catalog of `13-CAPABILITIES.md`. With `project.layout: sdd`, a name in `docs/specs/README.md` that matches no catalog name is shown to the PM to map to a catalog name, in the same question as the `unplanned` capabilities; a name left unmapped is listed in the report. An epic covers a row when its `Capabilities:` names the catalog name or a name mapped to it.
- `manager-view.md`, Report block: with a milestone plan, the report also names each milestone the run created and the epics it set into each milestone.
- `milestone-plan.md`: split the first sentence of the Write block and the adopted-epic sentence into sentences of at most 35 words (`docs#lead-with-conclusion`), and shorten elsewhere so the file stays at or under 4,000 characters (3,984 today).
- `docs/starters/brownfield.md` and `.vi.md`: the sentence about the outcome and demo of each milestone gets the condition "when you give a milestone plan" (a plain run without one writes only the `Unassigned` row).
- `docs/guides/customizing-templates.md` and `.vi.md`: the same condition for `Outcome:` and `Demo:`.
- `docs/reference/skills.md` and `.vi.md`, `roadmap` row: rewrite the semicolon list as short sentences with the same facts.

### B. Tech-doc

- `tech-doc/SKILL.md`, roles table: "`13-CAPABILITIES.md` starts after `02-FEATURES.md`, `05-API.md`, and `12-DATABASE.md` when written". The test phrase in `tests/workflow_core/test_tech_doc_skill.py` (`test_capabilities_start_after_features_api_and_database`) is updated to the new text.
- `jvm-data.md`, Schema files block: name Flyway repeatable migrations `R__*.sql`, which run again when their checksum changes and hold views, procedures, and functions; the latest version of each wins.

### C. Retro

- `retro/SKILL.md` step 2: "When its `status` is `closed`, write nothing and say its close already read the retros." (`gin milestone show` exits 0 on a closed milestone.)
- `test_retro_records_one_comment_on_an_open_milestone` adds the needle "When its `status` is `closed`".
- `retro` row of the skills reference (English and Vietnamese): a milestone is `active` only after `gin milestone kickstart`; without it, the skill asks which milestone.

### D. Milestone close

- `milestone-close/SKILL.md`, Write step 4: one `Action:` line per confirmed action only, so a `remember` fact the PM did not choose gets none.
- `milestone-close/SKILL.md`, Write intro: a resumed run lists in `Spillover:` only the epics it moved itself, and its report says the earlier run's moves are not in the comment.
- `milestone-close` row of the skills reference: the same kickstart note as the `retro` row.

## Risks and rollback

- Existing tests assert exact sentences of these files (`test_tech_doc_skill.py`, `test_skill_routing.py`, `test_specs.py`, `tests/install_smoke_test.sh`). A changed sentence needs its test changed in the same commit; every other asserted sentence stays verbatim.
- `milestone-plan.md` and `manager-view.md` are capped at 4,000 characters by `tests/workflow_core/test_token_budget.py`.
- Rollback: revert the merge commit; no data, format, or command changes.

## Testing

- New needles: `test_retro_records_one_comment_on_an_open_milestone` ("When its `status` is `closed`"); `test_roadmap_manager_view_and_milestone_plan` (the Legacy coverage mapping rule and the created-milestones report rule in `manager-view.md`; "`Outcome:` and the `Demo:`" for `--milestone`); `test_milestone_close_moves_spillover_and_records_the_result` ("per confirmed action" and the resumed-run sentence); `test_scouting_references_are_linked_and_name_their_apis` (`R__` in `jvm-data.md`).
- Changed needle: `test_capabilities_start_after_features_api_and_database` for "when written".
- Unchanged and passing: `tests/workflow_core/test_token_budget.py`, `test_docs_coverage.py`, `test_docs_check.py`, `test_walkthrough_docs.py`, `test_specs.py`, `tests/gin_orchestrator/test_harness_packaging.py`, and `python3 -m pytest -n auto` at ship.

## Open Technical Questions

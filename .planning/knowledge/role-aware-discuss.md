# Role-aware discuss: business questions for a business member, technical questions settled at plan

**Context**
Epic `gin-workflow-746z` (2026-11-07). In team mode a BA running `/gin:discuss` was asked to pick technical approaches and confirm architecture, error handling, and testing, which they cannot answer; after the spec was confirmed, no stage let a technical member settle open technical questions before the plan.

**Decision/Solution**
- A member is technical when one of their roles is an area `lead` or is listed in an area's `roles` (`TeamConfig.technical`, `workflow_core/team.py`). No config key; an area without `roles` counts only its lead, because `TeamConfig.eligible` makes everyone eligible for such an area. Exposed as `project.team.me.technical` in `gin state --format json` and in `gin team whoami`.
- The `team` skill's `## discuss` tells discuss, when `me.technical` is false, to ask business questions only and write each technical point as `- TQ-<n>: <question>` under `## Open Technical Questions` in the design doc (legacy: the spec; SDD: the change's `03-design.md`). The discuss skill reads the `team` skill at step 2 (Clarify), before any question.
- `plan` step 1 settles each open question (2-3 options, a recommendation), writes an indented `Decision: <answer>` under it, carries the decisions into Approach Options and the Recommended Approach, and with the SDD layout fills only the empty Architecture, Error Handling, and Testing sections of `03-design.md`. The rule also applies outside team mode.
- `gin record plan-approved` refuses (exit 1, nothing recorded) while the workflow's design doc has a question without a decision; the check runs before the team pull request checks. `specs.design_doc` finds the doc from the workflow id (legacy: the one `.planning/specs/*.md` with `Epic: <id>` or `Workflow: <id>`; SDD: `find_change` then `change_file(change, "design")`). Two legacy specs naming the id, an ambiguous change, or an undecodable design doc exit 2. `specs lint --spec` and `--change` report format errors; an open question is not a lint error.

**Consequences**
- Only the record refusal and the lint checks are enforced by the CLI; asking business questions only is skill behavior.
- The check reads the working tree; in team mode the lead pulls the merged plan pull request before recording.
- Legacy lookup reads every spec file with `errors="replace"`, so one non-UTF-8 unrelated spec no longer blocks every plan approval (review finding on `gin-workflow-746z.2`).
- `.planning/specs/` already has two specs with `Epic: gin-workflow-f7g`; recording `plan-approved` for that id now exits 2 instead of guessing.
- `skills/team/SKILL.md` is at 5,809 of its 6,000-character budget and the plan chain about 11,320 of 12,000: the next addition there has to trim text.
- Known limit: `TQ-0` and zero-padded ids are accepted.
- Not run: an interactive team-mode discuss with a real BA.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/team.py`, `team_cli.py`, `specs.py`, `lifecycle_cli.py`; `plugins/gin-workflow/src/skills/{team,discuss,plan}/SKILL.md`; `plugins/gin-workflow/src/templates/design-spec.md`, `design.md`
- Tests: `tests/workflow_core/test_schema_2_7.py`, `test_specs_technical_questions.py`, `test_role_aware_skills.py`
- Docs: `docs/guides/team.md`, `docs/roles.md`, `docs/concepts/lifecycle.md`, `docs/reference/cli.md`
- `.planning/specs/2026-11-07-role-aware-discuss-design.md`, `.planning/plans/2026-11-07-role-aware-discuss.md`
- Commits `439eb8a`, `f4e7d42`, `74ad9a5`, `514d875`, `d1ba11d`
- Beads: `gin-workflow-746z`, `gin-workflow-746z.1`, `gin-workflow-746z.2`, `gin-workflow-746z.3`
- Related: [ba-plugin](ba-plugin.md)

**Scope**
Team-mode discuss and plan, the design doc's `## Open Technical Questions` section, and `gin record plan-approved`.

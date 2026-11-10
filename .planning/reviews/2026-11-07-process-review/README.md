# Process review: five role personas walk through gin-workflow

Spec: `.planning/specs/2026-11-07-process-review-design.md`. Epic: `gin-workflow-process-review`.

In this file, `$D` means `.planning/reviews/2026-11-07-process-review`. Run every command from the repository root.

## Goal

Find out how the gin-workflow lifecycle reads to the people who would run it on a real legacy modernization, before more features are added. Five AI personas, one per role, walk through the whole process on the `shop-portal` scenario in `brief.md`. Each reports what is unclear, missing, or wrong from its seat, with a suggested change per finding. The main session merges the reports into `synthesis.md`, a prioritized list of proposed epics for a later `/gin:roadmap`.

## Scope

In scope:
- The core lifecycle, from setup to progress and report, including worktrees and rules.
- The gin-qa plugin as the QA persona sees it.
- The gin-ba plugin as the BA persona sees it.
- The documentation under `docs/` and the skill files under `plugins/*/src/skills/`.

Out of scope:
- Any change to plugins, CLI, docs, or tests. Changes found by the review become separate epics.
- gin-console.
- Running gin-workflow on a fixture repository. Personas read and reason; they do not execute stages.
- Human reviewers.

## Roles and runs

| Role | Prompt | Inputs | Agent type | Model | Effort | Report |
|---|---|---|---|---|---|---|
| PM | `$D/prompts/pm.md` | `$D/brief.md`, `$D/report-template.md` | `general-purpose` | `opus` | `high` | `$D/reports/pm.md` |
| BA | `$D/prompts/ba.md` | `$D/brief.md`, `$D/report-template.md` | `general-purpose` | `opus` | `high` | `$D/reports/ba.md` |
| QA | `$D/prompts/qa.md` | `$D/brief.md`, `$D/report-template.md` | `general-purpose` | `opus` | `high` | `$D/reports/qa.md` |
| Backend lead | `$D/prompts/be-lead.md` | `$D/brief.md`, `$D/report-template.md` | `general-purpose` | `opus` | `high` | `$D/reports/be-lead.md` |
| Frontend lead | `$D/prompts/fe-lead.md` | `$D/brief.md`, `$D/report-template.md` | `general-purpose` | `opus` | `high` | `$D/reports/fe-lead.md` |

## Launch recipe

1. In one message, make five calls of the native Agent tool, one per role, with the agent type, model, and effort from the table.
2. The prompt of each call is the content of the role's prompt file, followed by this line: `Inputs: brief.md and report-template.md under $D; write $D/reports/<role>.md`.
3. The runs are independent and may run in parallel. No persona reads another persona's report.
4. Each persona writes its own report. Do not edit report content by hand.

## Re-run one role

Make the same Agent call for that role only. It overwrites only that role's report. Re-run a role when its report fails `check.py reports` or does not follow `report-template.md`.

## Definition of done

- Five reports exist under `$D/reports/` and pass `python3 $D/check.py reports`.
- `$D/synthesis.md` exists and passes `python3 $D/check.py synthesis`.
- `.planning/roadmap.md` is unchanged and no bead was created by the synthesis.

## Manual verification

- The five prompt files share the section order and the core reading list: `python3 $D/check.py kit` prints `ok`.
- Each report has the sections of the template, one `### ` sub-section per stage, and a findings table: `python3 $D/check.py reports` prints `ok`.
- Every evidence path in the reports is tracked on the branch. `check.py reports` prints a `note:` line for each path that is not.
- `synthesis.md` accounts for every finding ID once: `python3 $D/check.py synthesis` prints `ok`.
- Read one report end to end and confirm it reads from the role's seat.

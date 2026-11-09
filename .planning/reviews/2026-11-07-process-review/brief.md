# Process review brief: shop-portal modernization

This is the shared scenario for all five personas. Read it fully, then walk the stages in `## Stages` in order. Facts about gin-workflow below were checked against the repository; where a line number is given, read that line yourself. The scenario does not say what is right or wrong. Judge it from your role.

## Legacy system

- `shop-portal` is a Java JSP monolith with one database and server-rendered screens.
- It is frozen: nobody changes it. It stays readable as the source of truth for current behaviour.
- It lives in the repository `legacy/shop-portal/`, marked `frozen: true` in the workspace manifest (`docs/guides/workspace.md:14`, `docs/guides/workspace.md:25`).

## Target

- Two Spring Boot services: `services/order-api/` and `services/catalog-api/`.
- Two React apps: `apps/web-shop/` for customers and `apps/web-admin/` for administrators.
- Playwright tests in the automation repository `qa/automation/`.

## Repository layout

The team works from a workspace: a parent repository that lists child repositories in its configuration (`docs/guides/workspace.md:3`).

- The parent holds `docs/`, `.planning/`, and `.agent-workflow/config.yaml` with its `workspace.repos` manifest.
- Each service, each app, the automation repository, and the frozen `legacy/shop-portal/` is a separate git repository, cloned at its manifest path and listed in the parent `.gitignore` (`docs/guides/workspace.md:9`).
- The parent tracks no child. Each child keeps its own code, hooks, branches, and worktrees (`docs/guides/workspace.md:3`).
- The workspace guide says what each role opens at each stage (`docs/guides/workspace.md:65-114`). The brownfield starter shows a similar scenario (`docs/starters/brownfield.md:9-19`).

## Team

Six members, one per role. The role names are those of the brownfield starter (`docs/starters/brownfield.md:23-31`).

| Member | Role |
|---|---|
| Product manager | `pm` |
| Business analyst | `ba` |
| Backend lead, who is also the tech lead | `be_lead` |
| Backend developer | `be_dev` |
| Frontend developer | `fe_dev` |
| Quality engineer | `qe` |

The frontend lead persona reads the process as the owner of the React apps, next to the backend lead.

## Milestone

One two-week milestone with three epics. Each epic carries the label `area:<name>` for the one area (one child repository) it changes.

| Epic | Kind | Depends on |
|---|---|---|
| `catalog-api contract` | contract epic (API schema) | none |
| `catalog-api browse endpoints` | service epic | `catalog-api contract` |
| `web-shop catalog pages` | app epic | `catalog-api contract` |

## Operating model to validate

- The tech lead owns the roadmap and the milestone reviews.
- Every roadmap epic stays in one area, which is one child repository.
- Contract epics close before the service and UI epics that depend on them.
- Each member picks a ready epic of their area and runs the lifecycle from `/discuss` to `/ship` on their own machine.
- The area lead, the BA, and QA approve through pull requests (`docs/guides/git-flow.md`).

Say where this model breaks. Consider at least epic size, coherence across areas, review load, and who writes the spec of a technical epic.

## Questions

All personas answer these in the report, at the stage where they arise.

1. Which directory does your role open, and from which directory does it run `gin`?
2. Is the per-track worktree of one child repository enough for a backend engineer?
3. How is a feature that spans one service and one app planned, executed, reviewed, and shipped?
4. Is the frozen legacy repository reachable where tech-doc and discuss need it?

Question for the PM. The roadmap can hold a `Deadline:` line and an `AI capacity:` line (`plugins/gin-workflow/src/skills/roadmap/SKILL.md:25`). `gin milestone create` takes `--lanes`. `gin milestone list` ends with a forecast line, and `gin milestone show` can warn `overflow`, `late`, and `spec_not_ready` (`docs/reference/cli.md:200-213`). Milestones are sprints and an epic belongs to one milestone. Does this let the team see a hard project deadline next to the sprint milestones?

Question for the PM and the BA. The BA confirms the specs of milestone N+1 while developers build milestone N, and `Spec ready by:` marks the date (`plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:9`). Each milestone ends with an `Integration point:` (`plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:25-26`). Does this sequencing work for this team?

## Stages

Walk these 14 stages in order. In the report, use the same numbers and names as `### <n>. <name>` headings.

1. Setup and workspace: `/gin:setup`, `gin workspace clone`, `gin workspace status`.
2. Team setup: `/gin:team-setup`.
3. Tech-doc: `/gin:tech-doc`.
4. Legacy capture and mockups: `/gin-ba:capture`, `/gin-ba:mockup`.
5. Roadmap and milestones: `/gin:roadmap`, `gin milestone`.
6. Discuss: `/gin:discuss`.
7. Plan: `/gin:plan`.
8. Orchestrate and worktrees: `/gin:orchestrate`, `/gin:worktrees`.
9. Execute and rules: `/gin:execute`, `gin rules`.
10. Review: `/gin:review`.
11. Test: `/gin-qa:cases`, `/gin-qa:run`, `/gin-qa:e2e`, `/gin-qa:tests`, `/gin-qa:report`.
12. Ship: `/gin:ship`.
13. Quick: `/gin:quick`.
14. Progress and report: `/gin:progress`, `/gin:report`.

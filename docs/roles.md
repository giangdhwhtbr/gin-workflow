# Team roles

In [team mode](guides/team.md) each member holds roles, each area of the repository has a lead role, and a gate can require approval from listed roles. This page suggests how a PM, a BA, developers and testers split the work, and what each of them reads. gin-workflow enforces only what `team.areas` and `team.approvals` configure.

## Who owns what

| Role | Skills | Files | Branch | Approves |
|---|---|---|---|---|
| PM | `/gin-workflow:roadmap`, `/gin-workflow:progress`, `/gin-workflow:report`; `/gin-workflow:roadmap --milestone` writes milestones, limited by `team.permissions.milestone` | `.planning/roadmap.md` (`docs/roadmap.md` with the SDD layout) | `roadmap/<topic>` | `roadmap` |
| BA | `/gin-workflow:discuss`, `/gin-workflow:tech-doc`, `/gin-workflow:progress` | `.planning/specs/` (`docs/specs/` and `docs/changes/` with the SDD layout) | `spec/<topic>` (`spec/<epic>-<slug>` with the SDD layout) | `requirement_confirmed` |
| Developer and tech lead | `/gin-workflow:plan`, `/gin-workflow:orchestrate`, `/gin-workflow:execute`, `/gin-workflow:review`, `/gin-workflow:ship` | source and test paths, `.planning/plans/` | `plan/<topic>`, then `feat/<topic>-t<N>` per track | `plan_approved` |
| Tester | `/gin-qa:cases`, `/gin-qa:e2e`, `/gin-workflow:progress` | `qa/cases/`, `qa/e2e/`, `qa/evidence/` | reviews the developer's pull request | `ship` |

## What each role reads

### PM

1. The Roadmap, Sprint planning, and Ship and sprint review sections of the [brownfield walkthrough](starters/brownfield-walkthrough.md)
2. [AI usage report](guides/usage-report.md)
3. [Skills reference](reference/skills.md)

### BA

1. [Getting started](getting-started.md)
2. [SDD living specs](guides/sdd.md)
3. [Customizing templates](guides/customizing-templates.md)
4. The Discuss an epic section of the [brownfield walkthrough](starters/brownfield-walkthrough.md)

### Developer and tech lead

1. [Getting started](getting-started.md)
2. [Lifecycle and gates](concepts/lifecycle.md)
3. [Team mode](guides/team.md)
4. [Rule packs](guides/rules.md)

### Tester

1. [QA add-on](guides/qa.md)
2. The Requirements section of [SDD living specs](guides/sdd.md#requirements)
3. The Test cases and E2E sections of the [brownfield walkthrough](starters/brownfield-walkthrough.md)

## Keeping work apart

- Requirement changes after plan approval (a team convention): do not edit the in-flight spec. With the SDD layout, the change goes in a new change folder whose `MODIFIED` block carries the base hash of the requirement it replaces, and `gin-qa cases plan` shows which test cases went stale.
- Tests (a team convention): developers own unit and integration tests next to the code; testers own acceptance cases and end-to-end specs under `qa/`. Give each its own area in `team.areas`, so plans keep them apart.
- Worktrees: each track runs in its own worktree created by `/gin-workflow:orchestrate`.
- Claims, hand-overs and approvals ([team mode](guides/team.md) has the details):
  - a claim fails while someone else holds the bead;
  - `gin-workflow team reassign` hands a track over;
  - a gate with roles is recorded only with an approved pull request, never approved by its author.

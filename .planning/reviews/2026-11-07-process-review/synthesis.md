# Process review synthesis

- Date: 2026-11-10
- Reports read: `reports/pm.md` (PM-1 to PM-19), `reports/ba.md` (BA-1 to BA-19), `reports/qa.md` (QA-1 to QA-20), `reports/be-lead.md` (BE-LEAD-1 to BE-LEAD-26), `reports/fe-lead.md` (FE-LEAD-1 to FE-LEAD-22).
- Total: 106 findings in 26 clusters; none dropped.
- Corrected citations: the fe-lead report cites `docs/roles.md:120-126`, `:124`, `:125`, `:175` and `team_cli.py:184`; this synthesis uses `docs/roles.md:18-24`, `:22`, `:23`, `:73` and `team_cli.py:185` instead.

Each cluster below is one proposed epic. Priority follows the most severe finding in it: `P1` holds a blocker, `P2` a major, `P3` only minor findings.

## Clusters

### Ship gate accepts pull requests of workspace children
Goal: `gin team check --gate ship`, `record shipped`, and `team deps` work on pull requests opened in a workspace child repository.
Raised by: QA, BE lead, FE lead
Priority: P1
Findings: QA-3, BE-LEAD-1, FE-LEAD-3, BE-LEAD-13, BE-LEAD-16
Evidence: `plugins/gin-workflow/src/scripts/workflow_core/team.py:424-426` compares the pull request with the parent's `origin`; `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py:185` resolves `--repository` to the workspace root.

### gin-qa runs from the qa child and its track worktrees
Goal: gin-qa resolves the workspace root, reads config from the parent, and writes its files and `git log` lookups into the `qa` child.
Raised by: QA
Priority: P1
Findings: QA-1, QA-2
Evidence: `plugins/gin-qa/src/scripts/gin_qa/reqs.py:39-41` requires `.agent-workflow/config.yaml` in the current repository.

### Approval roles without a single-holder deadlock
Goal: the starter and `team.approvals` give each gate a second approver, an `fe_lead` for app areas, and an enforceable QA sign-off on `ship`.
Raised by: BE lead, FE lead, QA
Priority: P1
Findings: BE-LEAD-2, FE-LEAD-1, FE-LEAD-13, BE-LEAD-11, QA-4
Evidence: `docs/starters/brownfield.md:47-54` makes `be_lead` the lead of every area; `docs/roles.md:18-24` has no frontend lead row; `docs/roles.md:22` names the tech lead backup approver; `docs/roles.md:23` limits developers to peer reviews; `plugins/gin-workflow/src/scripts/workflow_core/team.py:457-458` accepts any one listed role.

### Branch and pull request model for workspace children
Goal: one documented flow for child `feat/<topic>`, track worktree creation on claim, track pull request bases, review ledgers, and closing a multi-member epic.
Raised by: BE lead, FE lead, PM
Priority: P2
Findings: BE-LEAD-4, BE-LEAD-14, BE-LEAD-15, FE-LEAD-14, BE-LEAD-10, FE-LEAD-16, PM-13

### One epic rule for features that span repositories
Goal: the workspace guide and brownfield starter state one rule for how an epic maps to repositories, QA work, and shared packages.
Raised by: BA, BE lead, FE lead, QA
Priority: P2
Findings: BA-3, BE-LEAD-8, FE-LEAD-12, QA-5, FE-LEAD-11

### Owner roles for technical epics and milestone writes
Goal: docs name who runs discuss for a contract or other technical epic, who approves it, and who owns roadmap order and `gin milestone` writes.
Raised by: BA, BE lead, PM, FE lead
Priority: P2
Findings: BA-4, BE-LEAD-20, PM-8, FE-LEAD-5, PM-3, BE-LEAD-19

### Contract-first and integration scheduling
Goal: a workspace documents where the API contract lives and how apps consume it, and the roadmap schedules contract and integration work as tracked epics.
Raised by: BE lead, FE lead, PM
Priority: P2
Findings: BE-LEAD-7, FE-LEAD-6, PM-7, FE-LEAD-4, PM-9

### Shared gate state for milestone and lifecycle routing
Goal: `gin milestone` readiness and `orchestration_ready` read gate state from the epic bead, so every member's machine shows the same answer.
Raised by: PM, BA, BE lead
Priority: P2
Findings: PM-5, BA-5, BE-LEAD-5

### Milestone capacity, forecast, and exit criteria
Goal: one capacity model per role group, a forecast for in-progress and unestimated epics, member availability, and warnings for integration date and exit criteria.
Raised by: PM, QA
Priority: P2
Findings: PM-4, PM-6, PM-12, PM-17, PM-18, QA-15

### Workspace onboarding and frozen legacy access
Goal: each role knows what to clone, frozen legacy entries are reachable from tech-doc and discuss, and setup collects the repository entries.
Raised by: PM, BA, BE lead
Priority: P2
Findings: PM-1, PM-2, BA-2, BE-LEAD-12, BE-LEAD-25

### Team init for every workspace child
Goal: `gin team init` writes CODEOWNERS, the pull request template, the commit-msg hook, and the CI job into each non-frozen child.
Raised by: BE lead, FE lead
Priority: P2
Findings: BE-LEAD-3, FE-LEAD-2

### Per-entry checks, rule packs, and shape in a workspace
Goal: doctor, worktrees, and execute use the current entry's `verify.checks`, rule packs, and shape appendix instead of the parent's.
Raised by: FE lead, BE lead
Priority: P2
Findings: FE-LEAD-7, FE-LEAD-8, BE-LEAD-23, FE-LEAD-17, BE-LEAD-22, FE-LEAD-9, FE-LEAD-20

### Track environment with read-only siblings and running services
Goal: a track declares read-only sibling repositories and documents how to run the service and app combination it is tested against.
Raised by: BE lead, FE lead, QA
Priority: P2
Findings: BE-LEAD-26, FE-LEAD-10, QA-12

### QA tracks and acceptance cases in the lifecycle
Goal: execute runs QA tracks through gin-qa, review and ship check acceptance cases, and spec and ship checklists cover testability per pull request kind.
Raised by: QA
Priority: P2
Findings: QA-6, QA-7, QA-13, QA-14, QA-20

### Test evidence and defect tracking
Goal: run evidence is published beyond the tester's machine and automated failures file bug beads on the right epic.
Raised by: QA
Priority: P2
Findings: QA-8, QA-9, QA-17

### Legacy parity testing
Goal: parity tests have one owner, a case field for the legacy reference, and a stated build to run against.
Raised by: QA, BE lead
Priority: P2
Findings: QA-10, BE-LEAD-24

### SDD layout in the brownfield starter
Goal: the brownfield starter sets `artifacts.layout: sdd`, adds a capture step before discuss, and states how living specs relate to legacy behaviour.
Raised by: BA, QA
Priority: P2
Findings: BA-1, QA-11, BA-17

### SDD change flow for a team workspace
Goal: asset folders, in-flight requirement changes, `Source:` lines, spec checklists, cross-child `specs trace`, and the archive pull request follow one team flow.
Raised by: BA
Priority: P2
Findings: BA-6, BA-8, BA-9, BA-11, BA-12, BA-19

### Capture and mockups in a workspace
Goal: mockup reads the target app's design tokens, capture records who confirmed it, and the area lead reviews mockups before confirm.
Raised by: BA, FE lead
Priority: P2
Findings: BA-14, BA-15, FE-LEAD-15

### BA during build
Goal: business questions raised in execute reach the BA as epic comments, and each epic gets one BA acceptance point.
Raised by: BA
Priority: P2
Findings: BA-7, BA-10

### Tech-doc and rules for a Java and JSP legacy
Goal: tech-doc scouts Spring, JAX-RS, Struts, and JSP routes per workspace entry, and `java` and `spring` rule packs exist.
Raised by: BE lead, BA, FE lead
Priority: P2
Findings: BE-LEAD-9, BA-13, FE-LEAD-22

### Area field on roadmap epics
Goal: a roadmap epic carries `Area:`, written as an `area:<name>` label that `check-plan` can enforce.
Raised by: BE lead, PM
Priority: P2
Findings: BE-LEAD-6, PM-10

### Progress views for a team
Goal: `/gin:progress` shows milestone forecast, pending approvals, spec status, QA state, and grouping by area or repository.
Raised by: PM, BA, QA, BE lead, FE lead
Priority: P2
Findings: PM-11, PM-14, BA-16, QA-19, BE-LEAD-18, FE-LEAD-19

### Team usage totals
Goal: an epic's usage report merges children's stored `ai_usage` and usage recorded on other machines, or states that totals are partial.
Raised by: PM
Priority: P2
Findings: PM-15

### Quick in team mode
Goal: `/gin:quick` in team mode ends with a pull request and ship approval, lists covering cases, and can attach to an epic.
Raised by: PM, QA, BE lead, FE lead
Priority: P3
Findings: PM-16, QA-18, BE-LEAD-17, FE-LEAD-18

### Prompt templates match the workspace starter
Goal: the skills reference prompts use the workspace layout and put Track 5 in `services/order-api`, never in the frozen `legacy/`.
Raised by: PM, BA, QA, BE lead, FE lead
Priority: P3
Findings: PM-19, BA-18, QA-16, BE-LEAD-21, FE-LEAD-21

## Conflicts

- Epic shape: BA-3, BE-LEAD-8, and FE-LEAD-12 ask for one epic with one track per repository. QA-5 offers a separate QA epic per capability, and PM-9 asks for a feature grouping above epics instead.
- Epic area bound: BE-LEAD-6 asks `check-plan` to refuse tracks outside the epic's area. BE-LEAD-8 asks one epic to hold tracks in several repositories.
- Contract epic: PM-7 and FE-LEAD-4 ask for contract and integration epics scheduled in the roadmap. BE-LEAD-7 offers the confirmed spec as the contract, with no contract epic.
- Tech lead load: PM-3 and BE-LEAD-19 offer the tech lead roadmap order and milestone writes, and BA-4 and BE-LEAD-20 add technical discuss. BE-LEAD-2 and BE-LEAD-11 ask to take approvals off the tech lead.
- Contract spec approval: BA-4 keeps the BA as approver of a technical epic's business part. FE-LEAD-5 asks that the leads of consuming areas approve `requirement_confirmed` for it.
- Mockups for a 1-1 copy: BA-14 makes a mockup optional when the target copies the legacy UI. FE-LEAD-15 adds token reading and an area lead review before confirm.

## Dropped

None. `check.py reports` found every evidence path tracked, so no finding is dropped with `no evidence`.

## Carry into /gin:roadmap

1. Ship gate accepts pull requests of workspace children
2. gin-qa runs from the qa child and its track worktrees
3. Approval roles without a single-holder deadlock
4. One epic rule for features that span repositories
5. Branch and pull request model for workspace children
6. Owner roles for technical epics and milestone writes
7. Contract-first and integration scheduling
8. Shared gate state for milestone and lifecycle routing
9. Workspace onboarding and frozen legacy access
10. Team init for every workspace child
11. Per-entry checks, rule packs, and shape in a workspace
12. Track environment with read-only siblings and running services
13. QA tracks and acceptance cases in the lifecycle
14. Milestone capacity, forecast, and exit criteria
15. SDD layout in the brownfield starter
16. SDD change flow for a team workspace
17. BA during build
18. Test evidence and defect tracking
19. Legacy parity testing
20. Capture and mockups in a workspace
21. Tech-doc and rules for a Java and JSP legacy
22. Area field on roadmap epics
23. Progress views for a team
24. Team usage totals
25. Quick in team mode
26. Prompt templates match the workspace starter

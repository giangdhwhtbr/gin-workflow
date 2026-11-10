# Process review: five role personas walk through gin-workflow on a JSP to Spring Boot + React monorepo

Epic: gin-workflow-process-review
Workflow: process-review
Status: updated 2026-11-09 after the dependencies shipped; awaiting user review.

## Goal and scope

Find out how the gin-workflow lifecycle reads to the people who would run it on a real legacy modernization, before more features are added to it. Five AI personas, one per role, walk through the whole process on a shared scenario and report what is unclear, missing, or wrong from their seat, with a suggested change for each finding. The findings are synthesized into a list of proposed epics for a later `/gin:roadmap`.

The scenario is a legacy Java JSP monolith modernized to several Spring Boot services plus several React apps, each in its own git repository, developed from a parent workspace repository that holds the project documentation, `.planning/`, the gin-workflow config, and a `workspace.repos` manifest (the layout defined by `.planning/specs/2026-11-07-workspace-design.md`, epic `gin-workflow-workspace`). That epic shipped (merge 4ca905b), so the personas judge `docs/guides/workspace.md`, the rewritten brownfield starter, and the `gin workspace` commands, not the earlier subtree advice.

In scope:
- The core lifecycle: setup, team setup, tech-doc, roadmap and milestones, discuss, plan, orchestrate, execute, review, ship, quick, progress and report, worktrees, rules.
- The gin-qa plugin (cases, run, e2e, tests, report) as the QA persona sees it.
- The gin-ba plugin (capture, mockup) as the BA persona sees it.
- The documentation set under `docs/` and the skill files under `plugins/*/src/skills/`.

Out of scope:
- Any change to plugins, CLI, docs, or tests. Changes found by the review become separate epics.
- gin-console.
- Running gin-workflow on a fixture repository. Personas read and reason; they do not execute stages.
- Human reviewers. The prompts are written for AI personas; they may be reused for people later, but that is not a requirement here.

Confirmed summary (user, 2026-11-09): goal and scope are unchanged. Since the draft, four epics shipped and the review judges their shipped behaviour: `gin-workflow-workspace` (workspace guide and commands), `gin-workflow-docs-refresh` (task-ordered `docs/guides/ba.md`, new `docs/guides/git-flow.md` and `docs/guides/use-cases.md`), `gin-workflow-57fw` (roadmap `Deadline:` line, milestone `--lanes`, forecast line of `gin milestone list`), and `gin-workflow-roadmap-pipeline` (spec-ahead sequencing, `Spec ready by:` and an `Integration point:` per milestone). The reading lists and the brief questions in R2 and R3 follow from this.

Comments considered: 2, latest 2026-11-08T23:15:51Z

## Requirements

Everything lives under `.planning/reviews/2026-11-07-process-review/`. All files are in English.

R1. `README.md` is the review plan: goal, scope, the five roles, how one persona run is launched (agent type, model, effort, inputs, where the report goes), how to re-run a single role, and the definition of done (five reports present, synthesis written).

R2. `brief.md` is the shared scenario every persona receives. It states the legacy system (JSP monolith `shop-portal`, one database, server-rendered screens), the target (Spring Boot services under `services/order-api/` and `services/catalog-api/`, React apps under `apps/web-shop/` and `apps/web-admin/`, Playwright tests under `qa/automation/`), the repository layout (a parent workspace repository with `docs/`, `.planning/`, `.agent-workflow/config.yaml` and its `workspace.repos` manifest; each service, app, the automation repository and the frozen `legacy/shop-portal/` cloned at its manifest path and gitignored), the team (six members holding the roles `pm`, `ba`, `be_lead`, `be_dev`, `fe_dev`, `qe`, the same names as docs/starters/brownfield.md:22-28), and one two-week milestone with three epics. The brief lists the questions the personas must answer about the workspace: whether each role knows which directory to open and run `gin` from; whether the per-track worktree of one child repository is enough for a backend engineer; how a feature that spans one service and one app is planned, executed, reviewed and shipped; and whether the frozen legacy repository is reachable where tech-doc and discuss need it. The brief also states the operating model to validate: the tech lead owns the roadmap and the milestone reviews, every roadmap epic stays inside one area (one child repository), epics carry `area:<name>` and their dependencies in Beads, contract epics (API and event schemas) close before the service and UI epics that depend on them, and each member picks a ready epic of their area and runs its whole lifecycle (`/discuss` to `/ship`) on their own machine, with the area lead, the BA and QA approving through pull requests; the personas say where this model breaks (epic size, cross-area coherence, review load, who writes the spec for a technical epic). For the PM persona the brief adds the planning question: milestones are sprints and an epic belongs to one milestone, so does the shipped deadline tracking (the roadmap `Deadline:` and `AI capacity:` lines, `gin milestone create --lanes`, the forecast line of `gin milestone list`, the `overflow`, `late` and `spec_not_ready` warnings of `gin milestone show`) let the team see a hard project deadline next to sprint milestones. For the PM and BA personas the brief also asks whether the shipped spec-ahead sequencing works for this team: the BA confirms the specs of milestone N+1 while developers build milestone N (`Spec ready by:`), and each milestone ends with an `Integration point:` where its epics run end to end behind their feature flags.

R3. `prompts/<role>.md`, one file per role: `pm.md`, `ba.md`, `qa.md`, `be-lead.md`, `fe-lead.md`. Each is a complete system prompt with the same section order: identity and concerns of the role; the task (walk through every stage of the brief in order, say what you would do at that stage, what is unclear, what is missing, what you would change); the mandatory reading list as repository paths; evidence rules; output rules pointing to `report-template.md`. The mandatory core reading list is the same for all roles: `docs/starters/brownfield.md`, `docs/concepts/lifecycle.md`, `docs/roles.md`, `docs/guides/team.md`, `docs/guides/workspace.md`, `docs/guides/git-flow.md`, `docs/reference/skills.md`. The role-specific list adds at least:
- `pm`: `plugins/gin-workflow/src/skills/roadmap/SKILL.md`, `progress/SKILL.md`, `report/SKILL.md`, `docs/guides/usage-report.md`, the `gin milestone` section of `docs/reference/cli.md`.
- `ba`: `plugins/gin-workflow/src/skills/discuss/SKILL.md`, `tech-doc/SKILL.md`, `sdd/SKILL.md`, `docs/guides/ba.md`, `docs/guides/sdd.md`, `docs/guides/use-cases.md`, `plugins/gin-ba/src/skills/capture/SKILL.md`, `mockup/SKILL.md`.
- `qa`: `docs/guides/qa.md`, every `plugins/gin-qa/src/skills/*/SKILL.md`, `plugins/gin-workflow/src/skills/review/SKILL.md`, `ship/SKILL.md`.
- `be-lead`: `plugins/gin-workflow/src/skills/setup/SKILL.md`, `team-setup/SKILL.md`, `plan/SKILL.md`, `orchestrate/SKILL.md`, `execute/SKILL.md`, `review/SKILL.md`, `ship/SKILL.md`, `worktrees/SKILL.md`, `quick/SKILL.md`, `docs/reference/config.md`, `docs/guides/rules.md`, `docs/concepts/state-model.md`.
- `fe-lead`: the same stage skills as `be-lead` plus `docs/guides/rules.md` for the frontend packs and the `monorepo` and `packages` keys of `docs/reference/config.md`.
Each prompt tells the persona to stay in role, to read the listed files before writing, to cite `file:line` for every finding, to say "not found" rather than assume a feature exists, and not to modify the repository.

R4. `report-template.md` fixes the report structure: a header (role, date, model, files read); a Walkthrough section with one sub-section per stage in brief order, each with "What I would do", "Unclear", "Missing"; a Findings table with the columns ID (`<ROLE>-<n>`), stage, severity (`blocker`, `major`, `minor`), evidence (`file:line`), suggested change; a Top 3 changes list; and Questions for other roles. A report that skips a stage says why.

R5. `reports/<role>.md`, one per role, written by the persona run, following R4. A run uses the native Agent tool with the `general-purpose` agent type, the strongest model in the catalog (`opus`), effort `high`, the prompt file as its instructions, and `brief.md` plus `report-template.md` as inputs. The five runs are independent and may run in parallel; no persona reads another persona's report.

R6. `synthesis.md`, written by the main session after all five reports exist: findings merged across roles with duplicates collapsed and the originating IDs kept; clusters named as proposed epics with a one-line goal, the roles that raised them, and a priority (`P1` blocker-driven, `P2` major, `P3` minor); conflicts where two roles want opposite things, stated without resolving them; and a final list of items to carry into `/gin:roadmap`. The synthesis does not create beads.

R7. The epic `gin-workflow-process-review` sits in milestone `gin-workflow-96sx`, estimated at one day, and closes when R1 to R6 are present on the feature branch. `.planning/roadmap.md` is not edited by this epic.

## User Stories

### US-1: Run the review
As the maintainer, I want one command-free recipe per role in the review plan, so that I can launch all five personas in one session and re-run one role when its report is weak.

Acceptance criteria:
- `README.md` names, for each role, the prompt file, the inputs, the agent type, the model, the effort, and the report path.
- Launching the five runs as described produces five reports that follow `report-template.md`.
- Re-running one role overwrites only that role's report.

### US-2: Persona feedback per role
As a lead of one area, I want the walkthrough to be read from my seat, so that the findings reflect what I would actually hit at each stage rather than a generic review.

Acceptance criteria:
- Every finding has a stage, a severity, a `file:line` evidence, and a suggested change.
- Every report covers every stage of the brief, or states why a stage was skipped.
- The be-lead and fe-lead reports each answer the workspace questions listed in `brief.md`.

### US-3: Proposed epics
As the PM of gin-workflow, I want one synthesized list of proposed changes, so that the next `/gin:roadmap` run starts from prioritized, de-duplicated items instead of five raw reports.

Acceptance criteria:
- Every finding ID from the five reports appears in exactly one cluster of `synthesis.md` or in an explicit "dropped" list with a reason.
- Each cluster has a goal, the roles that raised it, and a priority.
- Conflicts between roles are listed separately from the clusters.

## Errors and compatibility

- A persona that cannot find a listed file reports it as a finding (`minor`, evidence: the missing path) and continues; the run is not aborted.
- A persona that invents a feature not present in the files is caught in synthesis: any finding whose evidence path does not exist is moved to the dropped list with the reason "no evidence".
- A report that does not follow `report-template.md` is re-run for that role, not patched by hand.
- Nothing here changes installed plugins, `.agent-workflow/`, or gin-console input; the deliverables are markdown under `.planning/reviews/` only.

## Testing

No automated tests: the deliverables are markdown. Verification is manual and listed in `README.md`:
- The five prompt files share the section order of R3 and the core reading list.
- Each report has the sections of R4; a quick check is one `## Findings` table per report and one `### ` sub-section per stage of the brief.
- Every evidence path in the reports exists on the branch (`git ls-files` check).
- `synthesis.md` accounts for every finding ID.

## Open Technical Questions

## Assumptions

- The epic belongs to the open milestone `gin-workflow-96sx`; a separate milestone is not created.
- Artifacts are in English, following the repository convention for tracked files.
- The run uses the Claude harness and its native Agent tool; a non-Claude harness would use `gin-orchestrator dispatch` with the same prompt files, but this is not verified here.
- Changes to gin-workflow found by the review are planned later through `/gin:roadmap`; none is implemented in this epic.

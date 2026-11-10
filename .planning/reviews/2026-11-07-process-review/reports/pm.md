# Process review report: pm

- Role: pm
- Date: 2026-11-10
- Model: Opus 5.5 (claude-opus-5-5), effort per the launch recipe
- Files read: .planning/reviews/2026-11-07-process-review/prompts/pm.md, .planning/reviews/2026-11-07-process-review/brief.md, .planning/reviews/2026-11-07-process-review/report-template.md, .planning/reviews/2026-11-07-process-review/README.md, .planning/reviews/2026-11-07-process-review/check.py, docs/starters/brownfield.md, docs/concepts/lifecycle.md, docs/roles.md, docs/guides/team.md, docs/guides/workspace.md, docs/guides/git-flow.md, docs/reference/skills.md, plugins/gin-workflow/src/skills/roadmap/SKILL.md, plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md, plugins/gin-workflow/src/skills/progress/SKILL.md, plugins/gin-workflow/src/skills/report/SKILL.md, docs/guides/usage-report.md, docs/reference/cli.md (the `gin milestone` and `gin usage` sections), docs/concepts/state-model.md (line 34, to check where gate events live), plugins/gin-workflow/src/scripts/workflow_core/milestone.py (lines 150-260), plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py (lines 120-148), plugins/gin-workflow/src/scripts/workflow_core/usage.py (lines 292-390)

## Walkthrough

### 1. Setup and workspace
- What I would do: Nothing hands-on; the tech lead runs `/gin:setup`, `gin workspace clone --all`, and `gin hooks install --all-repos` (`docs/guides/workspace.md:42-50`). I would clone the parent, install gin, and check with `gin workspace status` that I can see the repositories. Question 1 for my role: I open the parent and run `gin` from the parent (`docs/guides/workspace.md:65-67`), and "A PM or a BA clones the parent only" (`docs/guides/workspace.md:63`).
- Unclear: "Everything happens there, from a parent session worktree" (`docs/guides/workspace.md:67`). Is that the main checkout of the parent, or a git worktree I must create? A PM cannot be expected to know. Also, if I clone the parent only, I do not have `.beads`, which is its own child entry with `shape: beads` (`docs/guides/workspace.md:22`, `docs/starters/brownfield.md:19`). Every roadmap sync and every `gin milestone` command needs Beads (`docs/reference/cli.md:213`). So "parent only" cannot be right for me.
- Missing: One plain onboarding list for the PM: which repositories to clone (the parent and `.beads`), which logins, and one command that confirms "you can see the roadmap epics and milestones".

### 2. Team setup
- What I would do: Give the tech lead my email and role `pm`, check that `permissions: {milestone: [pm]}` and `approvals.roadmap: [pm, be_lead]` are set (`docs/starters/brownfield.md:52-57`), then run `/gin:team-setup` as a member (`docs/guides/team.md:43-47`).
- Unclear: The brief's operating model says the tech lead owns the roadmap and the milestone reviews. The docs give both to the PM (`docs/roles.md:20`, `docs/starters/brownfield.md:25`), and with `permissions.milestone: [pm]` the tech lead's `gin milestone move|close` exits 2 (`docs/reference/cli.md:226`). The two cannot both hold. Someone has to choose before setup, and the config has to say who that is.
- Missing: Team setup records no availability: no part-time members, no leave, no holidays. The roadmap is told never to ask about team composition (`plugins/gin-workflow/src/skills/roadmap/SKILL.md:25`, `plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:21`), so I have nowhere to say "the BA is away in week 2".

### 3. Tech-doc
- What I would do: I do not run it. The tech lead runs `/gin:tech-doc` (`docs/starters/brownfield.md:181-185`). I read the output under `.planning/codebase/` because the roadmap is built from it (`plugins/gin-workflow/src/skills/roadmap/SKILL.md:13`, `plugins/gin-workflow/src/skills/roadmap/SKILL.md:24`).
- Unclear: Question 4: tech-doc reads `legacy/shop-portal` only "when it is present" (`docs/guides/workspace.md:73`). The PM and BA clone the parent only (`docs/guides/workspace.md:63`), so if either of us runs `/gin:tech-doc`, as `docs/roles.md:21` allows the BA to, the legacy code is missing. On the tech lead's machine it is reachable once cloned (`docs/guides/workspace.md:59`).
- Missing: A one-page plain-language summary for me. The set is eleven technical files (`docs/starters/brownfield.md:197`), and the only advice is "Review it with the team" (`docs/starters/brownfield.md:201`).

### 4. Legacy capture and mockups
- What I would do: I would use the BA's confirmed mockups in stakeholder demos before any code exists. Capture and mockup are BA skills that work only with the SDD layout and record no gate (`docs/concepts/lifecycle.md:25`, `docs/reference/skills.md:74-83`).
- Unclear: The brief does not say which layout we use. If it is the legacy `.planning` layout, the BA add-on does not apply.
- Missing: The milestone view does not show the mockup or capture `Confirmed:` state, so I cannot tell from `gin milestone show` whether a milestone N+1 epic has its inputs ready. Only `spec_confirmed` is shown (`docs/reference/cli.md:213`).

### 5. Roadmap and milestones
- What I would do: Run `/gin:roadmap` with the goal, the deadline, the constraints, and the non-goals (`docs/starters/brownfield.md:211-219`). Confirm the split and the way of working, then get the roadmap PR approved by the tech lead (`docs/starters/brownfield.md:231`). Then `gin milestone create "M1 Catalog browse" --start … --end … --lanes N`, `/gin:roadmap --milestone <id>`, `gin milestone kickstart`, and read `gin milestone list` and `show` (`docs/starters/brownfield.md:241-265`).
- PM question (deadline next to sprints): Partly. `Deadline:` sits under `## Constraints` in the roadmap file, and `gin milestone list` ends with one forecast line: finish date, deadline, and spare or overflow working days (`docs/reference/cli.md:213`, `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:212-255`). So the deadline sits next to the sprints, on one line. What it does not give me:
  - `gin milestone show`, the per-sprint view, does not show the deadline at all.
  - An epic in progress is placed from today with its full original estimate, because there is no remaining-work estimate (`plugins/gin-workflow/src/scripts/workflow_core/milestone.py:241-243`). Mid-sprint, the forecast is too pessimistic.
  - Unestimated epics are left out of the finish date silently. They appear only as a count (`plugins/gin-workflow/src/scripts/workflow_core/milestone.py:244-246`).
  - `late` appears in the docs without a definition (`docs/reference/cli.md:213`). The code fires it only in an active milestone when an epic's planned end is before today (`plugins/gin-workflow/src/scripts/workflow_core/milestone.py:171-172`).
- Capacity: Two capacity models give different answers. The roadmap bounds a milestone by the headcount of the scarcest role group times working days (`plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:21`, `plugins/gin-workflow/src/skills/roadmap/SKILL.md:18`). For our team, FE, QA, and BA each have one member, so the bound is 1 × 10 = 10 epic-days for all three epics together. Meanwhile `show` schedules on lanes, and without `--lanes` or `AI capacity:` it defaults to the member count, which is 6 and includes the PM and the BA (`plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:141-148`, `docs/starters/brownfield.md:253`). I would see one figure from the roadmap proposal and a different one from `show`.
- Spec readiness: `spec_not_ready` is computed from my machine's local `.agent-workflow/runtime/events.jsonl` only (`plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:128-138`). The BA records `requirement_confirmed` on the BA's machine. `gin state` also reads the epic's `gates` metadata (`docs/concepts/state-model.md:34`), but `gin milestone` does not. On my machine, every confirmed spec would still show `spec_not_ready`. The measured pace in `--milestone` step 2 reads the same local log (`plugins/gin-workflow/src/skills/roadmap/SKILL.md:17`).
- Unclear: How a measured span per closed epic becomes an estimate for a new epic of a different size (`plugins/gin-workflow/src/skills/roadmap/SKILL.md:17`). I am also asked for every member's AI quota, but only the lane number is ever used (`plugins/gin-workflow/src/skills/roadmap/SKILL.md:25`, `docs/reference/cli.md:213`).
- Missing:
  - The roadmap creates epics with only the `roadmap` label (`plugins/gin-workflow/src/skills/roadmap/SKILL.md:30`). The brief's `area:<name>` per epic has to be added by hand. Area labels are set only on tracks, at orchestrate (`docs/guides/team.md:58`). The brownfield areas also span several repositories (`api: services/**`, `docs/starters/brownfield.md:49-50`), while the workspace guide says one area per repository (`docs/guides/workspace.md:49`).
  - Nothing warns when an epic estimate exceeds the milestone's working days. Spill-over moves the whole epic to the next milestone and keeps no record of partial progress (`docs/reference/cli.md:222`).

### 6. Discuss
- What I would do: Nothing hands-on. I would watch `spec_not_ready` (PM-5 breaks this today) and answer business questions the BA escalates.
- PM and BA question (spec cadence and integration point): Not for this team as briefed.
  - For M1 there is no milestone N-1, so the BA must confirm all three specs before kickoff, with no runway. The pattern expects a Foundation milestone first (`plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:6`), and the brief has none.
  - The integration point is working day floor(0.75 × 10) = 7 (`plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:15`). Before day 7, the contract epic must go through a spec PR, a plan PR, track PRs, and ship, and only then can the service and UI epics integrate. At the one-working-day review convention (`docs/guides/git-flow.md:113`), the contract epic alone waits about three days for reviews.
  - `Spec ready by:` covers only the BA's spec (`plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:9`), not the API contract the other two epics need.
  - The cadence works only if contract epics of N+1 ship during N, next to the specs.
- Unclear: Who writes the spec of the contract epic. A member with no technical role gets business questions only, and every technical point becomes a `TQ-<n>` that `/gin:plan` settles (`docs/roles.md:75`, `docs/guides/team.md:56`). Yet the brownfield prompt has the BA write the REST contract in discuss (`docs/starters/brownfield.md:284`). For a contract epic, `requirement_confirmed` (what `spec_not_ready` tracks) does not mean the contract is ready. The contract is ready when the plan is approved.
- Missing: An epic kind, or an owner role per epic, in the roadmap, so a technical epic can be discussed by the tech lead and its readiness date tracked on the right gate.

### 7. Plan
- What I would do: Nothing. The tech lead plans, and the area lead approves (`docs/starters/brownfield.md:307-332`).
- Unclear: Question 3. A feature that spans one service and one app is "two epics, or two tracks of one epic"; a track never spans two repositories (`docs/guides/workspace.md:132`). The brief's model takes the two-epic option, so "customers browse the catalog" becomes three epics, three specs, three plans, and three ships. The brownfield example puts the integration track ("replace the mocks with real API calls") inside the same epic as the API (`docs/starters/brownfield.md:342-349`). With one area per epic, that work belongs to `web-shop catalog pages`, but it depends on `catalog-api browse endpoints`, which the brief does not list as a dependency.
- Missing: A roll-up above the epic. I report to stakeholders by feature ("catalog browse is live"), not by three epics. Only the milestone and the free-text `Integrates:` line group them (`plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:23-31`).

### 8. Orchestrate and worktrees
- What I would do: Nothing. I see the epic move to `in_progress` when orchestrate records `orchestration_ready` (`docs/concepts/lifecycle.md:13`).
- Unclear: Without shared Beads, "each member creates beads only for the tracks they own" (`docs/guides/team.md:58`), so my view of track progress depends on which members have pushed. Question 2 (is one track worktree enough) is for the engineers. From my seat, I only need the cross-repository dependency, contract to mocks, to be visible as a Beads dependency.
- Missing: Nothing more for my role.

### 9. Execute and rules
- What I would do: Nothing. I would watch tracks close and use `gin team reassign` / `handoff` only through the tech lead when someone is away (`docs/starters/brownfield.md:416-422`, `docs/guides/team.md:64`).
- Unclear: Whether an expired lease or a released bead shows anywhere I look. `released` is a label (`docs/guides/team.md:64`), and `/gin:progress` does not mention it.
- Missing: Elapsed time per track. Estimates are per epic only, so I cannot see where a slipping epic loses its days.

### 10. Review
- What I would do: Approve nothing but the roadmap. The tech lead approves my roadmap PR (`docs/starters/brownfield.md:60`).
- Unclear: Review load. The tech lead is the backup approver for the roadmap, for every spec (the BA has no peer), for every plan (lead of all four areas), and for QA's own ship PRs (`docs/starters/brownfield.md:52-60`, `docs/roles.md:22`). In one milestone with three epics that is at least one roadmap, three specs, three plans, and QA's track PRs, all on one person who also builds. The model "area lead, BA and QA approve through pull requests" therefore funnels everything through `be_lead`.
- Missing: Any view of pending approvals per approver. `/gin:progress` shows the agent review ledger, not open PRs waiting on a role (`plugins/gin-workflow/src/skills/progress/SKILL.md:16`). I cannot see the bottleneck until a date slips.

### 11. Test
- What I would do: Read the `/gin-qa:report` HTML for stakeholders (`docs/starters/brownfield.md:448-458`) and use the milestone's `Exit criteria:` to decide whether the sprint is done (`plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:18`).
- Unclear: Whether bug beads filed by `/gin-qa:run` with `discovered-from` the epic (`docs/starters/brownfield.md:457`) count against the milestone. They are not epics, so `milestone show` ignores them.
- Missing: The integration point and the exit criteria are only text in the roadmap file; Beads stores no integration date (`docs/starters/brownfield.md:263`). `milestone close` checks only for open epics (`docs/reference/cli.md:224`). Nothing checks "E2E green, watermark gone, no open bug bead".

### 12. Ship
- What I would do: After ship closes the epic, watch it count as done in `gin milestone list` and read the `[gin ship]` comments on dependent epics (`docs/concepts/lifecycle.md:27`).
- Unclear: Who closes a multi-member epic. "A member's ship covers only their own tracks. The lead declares the feature complete once every track pull request has merged" (`docs/guides/team.md:68`, `docs/starters/brownfield.md:483`). Is "declares" a command, or a chat message? Until the epic bead closes, `milestone close` is refused (`docs/reference/cli.md:224`) and my forecast keeps the epic open.
- Missing: A named step, with an owner, that closes the epic once the last track PR has merged.

### 13. Quick
- What I would do: Nothing.
- Unclear: Where `/quick` work shows up. It creates no bead and no gate (`docs/concepts/lifecycle.md:74`). Progress shows `recent_quick` from the local `gin state` only (`plugins/gin-workflow/src/skills/progress/SKILL.md:16`).
- Missing: Quick changes consume team days invisibly. Neither the capacity bound nor the forecast knows about them.

### 14. Progress and report
- What I would do: At the milestone end, run `gin milestone show`, `move`, and `close`, then `/gin:report --milestone <id>` and `/gin:progress milestone <id>` (`docs/starters/brownfield.md:485-512`).
- Unclear: Usage cost per milestone in a six-person team. `gin usage collect` reads only the logs of the machine it runs on (`docs/guides/usage-report.md:3`). An epic's collect recomputes the whole epic from that machine's logs and overwrites `ai_usage` (`plugins/gin-workflow/src/scripts/workflow_core/usage.py:292-341`), and ship runs it on the tech lead's machine (`docs/concepts/lifecycle.md:68`). The report then shows only the epic's summary and hides the children's (`plugins/gin-workflow/src/scripts/workflow_core/usage.py:386`). The BA's discuss and the developers' execute costs are lost from the milestone total. I also cannot tell whether collect run from a child-repository worktree finds the parent's Beads.
- Missing: `/gin:progress` for a milestone lists epics and tracks only (`plugins/gin-workflow/src/skills/progress/SKILL.md:14`). It does not include the schedule, the warnings, the forecast against the deadline, or a stakeholder summary in plain language. I also see no estimate-versus-actual comparison per epic to calibrate the next sprint.

## Findings

| ID | Stage | Severity | Evidence | Suggested change |
|---|---|---|---|---|
| PM-1 | 1. Setup and workspace | major | `docs/guides/workspace.md:63`, `docs/guides/workspace.md:22`, `docs/reference/cli.md:213` | Say that a PM and a BA clone the parent and the `.beads` entry (or set `team.beads_sync.remote`), and add a PM onboarding check that lists the roadmap epics and milestones |
| PM-2 | 1. Setup and workspace | minor | `docs/guides/workspace.md:67` | Replace "from a parent session worktree" with the exact directory and branch the PM opens, and say that the skill creates `roadmap/<topic>` itself |
| PM-3 | 2. Team setup | major | `docs/roles.md:20`, `docs/starters/brownfield.md:57`, `docs/reference/cli.md:226` | State one roadmap owner. If the tech lead owns sequencing and milestone reviews, document `permissions.milestone: [pm, be_lead]` and split the duties: PM owns deadline and scope, tech lead owns order and technical epics |
| PM-4 | 5. Roadmap and milestones | major | `plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:21`, `plugins/gin-workflow/src/skills/roadmap/SKILL.md:18`, `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:141-148` | Use one capacity model: bound each role group by its own headcount (BE 2, FE 1, QA 1, BA 1) per epic need, and stop defaulting lanes to the full member count that includes the PM and the BA |
| PM-5 | 5. Roadmap and milestones | major | `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:128-138`, `docs/concepts/state-model.md:34`, `plugins/gin-workflow/src/skills/roadmap/SKILL.md:17` | Make `gin milestone` (spec_confirmed, spec_not_ready) and the roadmap pace read the epic's `gates` metadata as `gin state` does, so readiness is the same on every member's machine |
| PM-6 | 5. Roadmap and milestones | major | `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:241-246`, `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:171-172`, `docs/reference/cli.md:213` | Add a remaining-days estimate for in-progress epics, show the project deadline and forecast in `milestone show`, include unestimated epics in the finish with a flagged default, and define `late` in the docs |
| PM-7 | 6. Discuss | major | `plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:9`, `plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:15`, `docs/guides/git-flow.md:113` | Extend the spec cadence to contract epics: a contract epic of milestone N+1 ships during N, and `/gin:roadmap --milestone` warns when an epic and its contract blocker are adopted into the same milestone |
| PM-8 | 6. Discuss | major | `docs/roles.md:75`, `docs/guides/team.md:56`, `docs/starters/brownfield.md:284` | Add an epic kind (contract, service, app) or owner role to roadmap entries, let the tech lead run discuss for technical epics, and track a contract epic's readiness on `plan_approved` |
| PM-9 | 7. Plan | major | `docs/guides/workspace.md:132`, `docs/starters/brownfield.md:342-349`, `plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:23-31` | Add a feature grouping above epics in the roadmap with a roll-up status, and require the roadmap to name which epic owns the integration work (mocks to real API) and its dependency on the service epic |
| PM-10 | 5. Roadmap and milestones | minor | `plugins/gin-workflow/src/skills/roadmap/SKILL.md:30`, `docs/guides/team.md:58`, `docs/starters/brownfield.md:49-50`, `docs/guides/workspace.md:49` | Let roadmap entries carry `Area:` and write the `area:<name>` label on the epic, and align the brownfield areas with one area per repository |
| PM-11 | 10. Review | major | `docs/starters/brownfield.md:52-60`, `docs/roles.md:22`, `plugins/gin-workflow/src/skills/progress/SKILL.md:16` | Add a pending-approvals view (open gate PRs per approving role and member, with age) to `/gin:progress`, and recommend a second holder for `ba` and per-area leads in the starter |
| PM-12 | 11. Test | major | `docs/starters/brownfield.md:263`, `plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:18`, `docs/reference/cli.md:224` | Store the integration date on the milestone bead and have `milestone show` warn after it passes, and count open bug beads `discovered-from` the milestone's epics against its exit criteria |
| PM-13 | 12. Ship | minor | `docs/guides/team.md:68`, `docs/starters/brownfield.md:483`, `docs/reference/cli.md:224` | Name the step and command that closes a multi-member epic after its last track PR merges, and its owner |
| PM-14 | 14. Progress and report | major | `plugins/gin-workflow/src/skills/progress/SKILL.md:14-19`, `docs/reference/skills.md:24` | In milestone mode, have `/gin:progress` include `gin milestone show` (schedule, warnings) and the `list` forecast against the deadline, with a plain-language stakeholder summary |
| PM-15 | 14. Progress and report | major | `plugins/gin-workflow/src/scripts/workflow_core/usage.py:292-341`, `plugins/gin-workflow/src/scripts/workflow_core/usage.py:386`, `docs/guides/usage-report.md:3`, `docs/concepts/lifecycle.md:68` | Make an epic's summary merge its children's stored `ai_usage` and the discuss and plan usage collected on other machines, instead of recomputing from the shipping machine's logs only; until then, say in the report that team totals are partial |
| PM-16 | 13. Quick | minor | `docs/concepts/lifecycle.md:74`, `plugins/gin-workflow/src/skills/progress/SKILL.md:16` | Let `/quick` optionally attach to an epic or milestone, or report quick runs from shared state so they show in capacity and progress |
| PM-17 | 2. Team setup | minor | `plugins/gin-workflow/src/skills/roadmap/SKILL.md:25`, `plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:21` | Allow member availability (days off per milestone) in team config or in `milestone create`, and either use the per-member AI quota the skill asks for or stop asking for it |
| PM-18 | 5. Roadmap and milestones | minor | `docs/reference/cli.md:222`, `plugins/gin-workflow/src/skills/roadmap/SKILL.md:18` | Warn at roadmap time when an epic's estimate exceeds its milestone's working days, and propose a split |
| PM-19 | 7. Plan | minor | `docs/reference/skills.md:120`, `docs/reference/skills.md:190`, `docs/starters/brownfield.md:338` | Align the prompt templates with the workspace starter: no monorepo `services/api`, and no track in the frozen `legacy` area |

## Top 3 changes

1. PM-5: Spec readiness and pace read only the local event log, so on the PM's machine every confirmed spec shows `spec_not_ready`. The milestone view gives wrong answers until this is fixed.
2. PM-4: The two capacity models disagree, and the lane default counts the PM and the BA as builders. Every overflow and forecast number I give stakeholders depends on capacity, so it has to be one consistent figure.
3. PM-7: In a two-week sprint, a contract epic in the same milestone as its dependents eats the build window before the day-7 integration point. Moving contract epics one milestone ahead fixes the brief's milestone shape without new tools.

## Questions for other roles

- be-lead: Will you accept owning the roadmap order and the milestone reviews while you are also the approver for every spec, every plan, and QA's PRs? If not, which approvals move to someone else?
- ba: For the `catalog-api contract` epic, do you write the spec, or does the tech lead? Can you confirm three specs before the M1 kickoff with no previous milestone?
- fe-lead: Which epic owns the switch from contract mocks to the real `catalog-api`, and does `web-shop catalog pages` need a dependency on `catalog-api browse endpoints` for it?
- qa: Can the E2E suite run against the real API by working day 7, and should open bug beads block `gin milestone close`?

# Lean lifecycle: the host owns CI and approvals, tests run once, the ledger is optional

**Context**
Epic `gin-workflow-ws-ship-records` (2026-11-15), renamed from "several pull requests in record shipped and team deps". A gate inventory in `/discuss` (36 items) showed that the cost of the lifecycle was not the five gates but three repeated in-session steps: `gin-workflow-ws-branch-model` (4 tracks) ran the full suite 14 times (about 94 minutes), every track of two epics needed two review cycles, and the skills ran the review ledger although the project had `review_ledger: false`. The user's rule: prefer the tools a project already has (host CI, branch protection) and never demand in-session work they already do.

**Decision/Solution**
- `team.approvals.<gate>: host` (`workflow_core/team.py` `HOST`): a fourth policy form. The gate still needs pull request proof (`needs_pr` is true), but `check_approval` checks only the repository, the merged state (`ship` accepts an open pull request, `shipped` needs the merge), the artifact, and `check_plan`; no approver, author, or head commit. `/gin:team-setup` proposes it; role policies are unchanged.
- `gin record shipped --evidence <url>` is repeatable: one pull request per repository, each verified, and the proof gains `pull_requests` next to `pr_url` and `merge_commit` of the first.
- `gin team deps` reads the blocking track's `Repo:` from the plan file and searches that repository's checkout; it records `repo` (`.` for the parent in a workspace). `deps --bead` checks HEAD for the same repository or a placeholder without `repo`, else `origin/<default_branch>` of the other repository.
- `verify.run_at` (`track`, `push`, `host`; `project.run_at` in `gin state`): defaults `push` for `easy` and `standard`, `track` for `strict`. `push`: tracks run only the tests of what they changed, and ship runs `gin evidence run` once on the feature branch before `git checkout <base>`; the pre-push hook reuses that record. `host`: the pre-push hook and `gin evidence run` run nothing, and `gin hooks status` is ok without commands.
- Skills follow four settings from `gin state`: `run_at`, `review_ledger`, `review`, `worktree`. With the ledger off there is no `review-ledger.py` command; the reviewer reports a verdict and findings, and the close reason names the reviewer, cycles, and findings. The ledger procedure lives in `skills/review/ledger.md`, named in backticks so it loads on demand. `project.worktree: parallel` gives tracks worktrees only for a parallel strategy; otherwise tracks commit on `feat/<topic>`.
- Only team mode pushes a track branch. Outside team mode and a workspace, ship merges track branches into `feat/<topic>` after its checks, then runs the suite. In team mode without the ledger, another member reviewed on the track's pull request, opened before the review request; since `gin-workflow-ifbt` an agent reviews each track and a person reviews the lane's pull request ([team-lanes](team-lanes.md)).
- This epic ran that way: 5 tracks on one branch, no ledger, 10 reviewer runs, and the full suite once at ship.

**Consequences**
- The default changes for `easy` and `standard` projects: a regression outside a track's own tests shows at ship. `verify.run_at: track` restores the old flow.
- `gin state` never applies `policy.approval.ttl_seconds` (it never sets `guarded_actions`); the TTL applies only to protected-action checks through the extension API. User docs name `routing.review.max_cycles`; `project.max_cycles` is only the resolved field.
- `gin unblock` waives only lifecycle gates; `ship` and `roadmap` are never waived. `gin team check` needs a merged pull request for every gate except `ship`; only `gin team pending` accepts an open one.
- When new metadata would make an absent key ambiguous, write an explicit marker for the new case (`repo=.`), so an absent key keeps the legacy rule.
- When a policy value is added in code, grep every skill for the old condition wording ("lists roles"); `host` needed "has a policy" in the team and roadmap skills.
- `workflow_core/budget.py` counts a file in a stage chain when the skill links it or mentions `references/<name>.md`; a subagent without the Skill tool needs the absolute path of an on-demand file in its brief.
- Budgets are nearly spent: execute 11,977 and ship 11,978 of 12,000; the team skill about 5,984 of 6,000; the roadmap skill 11,985 of 12,000.
- Open: when ship runs from the `feat/<topic>` checkout (`IS_WORKTREE=no`), merged track worktrees and `-t<N>` branches are not cleaned up; `gin team complete` checks only that merged pull requests list each track in `Tracks:`; branch protection is configured by hand.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{team,team_beads,team_pending,team_cli,lifecycle_cli,project,hooks,schemas,setup_service}.py`
- `plugins/gin-workflow/src/skills/{review,execute,ship,worktrees,orchestrate,quick,setup,team-setup,workflow,progress,team,roadmap}/SKILL.md`, `skills/review/ledger.md`, `agents/{developer,code-reviewer}.md`, `references/stage-contract.md`
- Tests: `tests/workflow_core/{test_team_gates,test_team_pending,test_team_beads,test_lifecycle_cli,test_project_settings,test_hooks,test_setup_cli,test_skill_routing,test_token_budget}.py`
- Docs: `docs/reference/{config,cli,skills}.md`, `docs/concepts/{lifecycle,providers}.md`, `docs/guides/{team,git-flow,workspace,use-cases,ba}.md`, `docs/starters/brownfield.md` (with `.vi.md`)
- `.planning/specs/2026-11-15-lean-lifecycle-design.md`, `.planning/plans/2026-11-15-lean-lifecycle.md`
- Beads: `gin-workflow-ws-ship-records`, `.1` to `.5`
- Related: [approval-policies](approval-policies.md), [workspace](workspace.md), [test-suite-speed](test-suite-speed.md), [review-ledger-cycle-limit](review-ledger-cycle-limit.md)

**Scope**
Team approval policies, shipped records, `team deps`, where tests run, and how the stage skills review, isolate, and ship.

# Team lanes: a member's tracks on one branch, one worktree, one pull request

**Context**
Epic `gin-workflow-ifbt` (2026-11-19). In team mode each track had its own branch `feat/<topic>-t<N>` from `origin/<default>`, so a member's dependent track waited for the previous track's pull request to merge, another member reviewed every track, and the lead approved five to seven small pull requests per member.

**Decision/Solution**
- A lane is the tracks of one plan that one member does in one repository. Plans in team mode carry `Lane: <name>` per track (`team.Track.lane`, last field; `valid_lane`: `[a-z0-9][a-z0-9-]*`, never `t<digits>`). `check_plan` adds `Track N: missing Lane:`, `Track N: invalid lane X`, and per lane `tracks A and B have different owners` / `are in different repositories`.
- A track bead's lane is the `Lane:` line of its description (`team_pending.track_lane`); without it the bead is its own implicit lane `t<N>` and keeps `feat/<topic>-t<N>` and `.planning/worktrees/<bead>`. A named lane uses `feat/<topic>-<lane>` and `.planning/worktrees/<epic>-<lane>` (`team_beads._lane_key`). The `lane:<name>` label is written by orchestrate; no code reads it.
- `gin team claim` checks eligibility and foreign unexpired leases on every open track of the lane before any write, writes one lease to each, and marks only the named bead `in_progress` so `team ready` still lists the next. `handoff`, `takeover`, and `reassign` move every open track of the lane (`_lane_targets`); closed tracks keep their assignee.
- After the lane's pull request merged and tracks remain, the next claim restarts the branch from `origin/<default>` in the existing worktree when HEAD is the merged head (`_restart_delivered`), returns a `note` when commits were made after it, and says nothing when the host's merge commit is already in HEAD.
- `team pending` lists one lane branch per lane with an open track (gate null; `gin team check --gate ship` still applies `team.approvals.ship`). `team complete` treats a track as delivered when a merged pull request's `Plan:` and `Tracks:` lines list it (`team_beads._delivers`, the proof `team deps` uses), not by branch name.
- `gin goal` in team mode covers the caller's tracks (`--lane` narrows to one lane and adds its unassigned tracks), holds back tracks behind an open `external:` bead with `Do not start ...: they wait for another lane to merge.`, and replaces the `implementation_complete` clause with "each lane's branch is not ahead of origin".
- Agents review each track (`gin reviewer`); a person reviews the lane's pull request under `team.approvals.ship`. Contracts between lanes are fixed in the plan's `## Contracts` and change only through a new plan pull request (`skills/team/references/lanes.md`).

**Consequences**
- With a `--no-ff` merge the merged pull request's head stays an ancestor of `origin/<default>`, so "merged head is an ancestor of HEAD" cannot tell a branch restarted after the merge from new work on top of it; the merge commit's ancestry can.
- `team_beads.claim_expired` is true for an assigned bead with no claim metadata; a use on a bead that is not `in_progress` must first check that `claim_of(issue)` is non-empty. `bd ready` excludes `in_progress` beads, so tests of `ready` rows use open beads.
- `bd list --parent <epic> --all --limit 0 --json` rows carry `description`, `assignee`, `labels`, and `metadata`, so lane checks need no `bd show` per bead.
- `gin record` in team mode requires `--actor` to equal the git `user.email`; tests that record gates first and then switch a repository to team config must record before the switch.
- A test that builds a plan with `PLAN.replace(<multi-line block>, ...)` silently matches nothing when the `PLAN` fixture gains a line inside that block; check such replaces when the fixture changes.
- Exact key-set tests of `claim` JSON must change with any added field.
- Ship step 1 still says to require `implementation_complete`; the team skill states that lane ship needs only the delivered tracks closed (the ship skill had 3 characters of budget left: ship 11,997, team 5,884 of 6,000).
- Open: the restart runs only when the lane worktree exists (`gin-workflow-vfj5`); the per-track `bd update` writes of claim, handoff, and reassign are not atomic, and running the command again completes the lane.
- `gin-workflow-g9az` (2026-11-20): a team plan may declare lanes in `## Lanes` that their owners plan in `<lead plan stem>.lane-<lane>.md`; see [team-lane-plans](team-lane-plans.md).

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{team,team_beads,team_cli,team_pending,team_complete,goal}.py`
- Tests: `tests/workflow_core/test_team_{gates,beads,pending,complete}.py`, `tests/workflow_core/test_goal.py`, `tests/workflow_core/test_skill_routing.py`
- `plugins/gin-workflow/src/skills/team/references/lanes.md`, `skills/team/SKILL.md`, `templates/team/pull_request_template.md`; docs `docs/reference/cli.md`, `docs/guides/team.md`
- `.planning/specs/2026-11-19-team-lanes-design.md`, `.planning/plans/2026-11-19-team-lanes.md`
- Commits `8b508139` to `23b1cf08`
- Beads: `gin-workflow-ifbt`, `.1` to `.8`; follow-ups `gin-workflow-vfj5`, `gin-workflow-uz2z`; next epic `gin-workflow-g9az` (plan in two levels)
- Related: [team-lane-plans](team-lane-plans.md), [team-handoff](team-handoff.md), [team-progress](team-progress.md), [workspace](workspace.md), [lean-lifecycle](lean-lifecycle.md)

**Scope**
Team mode delivery: plan lanes, claim, handoff, ready, pending, complete, goal, and the team skill.

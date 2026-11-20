# Team lane plans: the lead declares lanes, each member plans their own

**Context**
Epic `gin-workflow-g9az` (2026-11-19 to 2026-11-20), on top of [team-lanes](team-lanes.md). In team mode the lead's `/plan` wrote every track's steps and answered every technical question, also for areas the lead does not own.

**Decision/Solution**
- A team plan may carry `## Lanes` before `## Tasks`, one `### Lane <name>` per lane with `Owner:`, `Area:` lines, optional `Repo:`, `Scope:`, `Acceptance criteria:`, `Contracts:`, and optional `Depends on lanes:` (`team.Lane`, `team.plan_lanes`; only Owner, Area, Repo, and Depends on lanes are read). A lane with no `### Track N` in the lead plan is planned by its owner; one with tracks is planned by the lead. Plans without `## Lanes` are checked as before.
- `check_plan` accepts a plan with lanes and no track and adds the declaration findings (`_lane_findings`, `_declaration_findings`, `_track_in_lane`); the area findings (`missing Area:`, `unknown area`, `holds no role allowed`) need `team.areas`.
- Questions `- TQ-<n> (lane <name>):` (`specs.Question.lane`) do not block `record plan-approved` when the plan file (`--plan`, else `--evidence` when it is a file) declares the lane; an undeclared lane, or marked questions without a plan file, refuse. `area_lead` approval covers declared lanes' areas.
- The lead's orchestrate creates a lane bead per unplanned lane: `Plan: <lead plan>, Lane <name>` and `Lane: <name>` (`team_pending.lane_bead`, needs `valid_lane`, so `Lane t<N>` is none). It closes when the lane plan is committed and the lane's track beads exist.
- A lane plan is `<lead plan stem>.lane-<lane>.md` (`team.plan_lane`, `team.lead_plan`); `topic_of` drops the suffix, so branch and worktree stay `feat/<topic>-<lane>` and `.planning/worktrees/<epic>-<lane>`. Beads of a lane are matched on (lead plan, lane); a lane-plan bead without `Lane:` takes the lane from its file name.
- `gin team check-plan <lane plan>` (`team.check_lane_plan`) checks the tracks against the lane's declaration, needs a `Spec:` line resolved inside the git top, and reports open or malformed questions marked for the lane. Ship runs it by instruction (`skills/team/references/lanes.md`); no gate enforces it.
- `external: <lead plan>#lane-<name>` closes in `gin team deps` when every bead of the lane, lane bead included, is closed, the lane has a track, and merged pull requests list every track (`_lane_delivered`); `merge_commit` then holds several commits separated by spaces and `deps --bead` needs all of them.
- `gin goal` leaves lane beads out of the tracks and prints `No goal: lane <name> has no tracks yet; run /plan for it.` when the member covers no open track and has lane beads to plan.

**Consequences**
- `skills/team/references/lanes.md` (about 8,100 characters) is in no stage chain: `plan` and `orchestrate` name it as backticked `references/lanes.md`, which `budget._linked` resolves to no file there. A Markdown link would add the whole file to the chain. Budgets after this epic: team 5,991 of 6,000; plan 11,981, ship 11,997 of 12,000.
- In a workspace, a lane in a child repository commits its lane plan and decisions on the parent's `feat/<topic>`, so the child's lane pull request does not show the lane plan.
- `check_plan` already has a local `lanes` dict (tracks grouped by lane); the declared lanes are `declared_lanes`.
- `tests/workflow_core/test_team_beads.py` has an `if __name__ == "__main__"` block in the middle of the file; new classes go before it.
- Open: no cycle check on `Depends on lanes:`; no test of a lane bead with a workspace `Repo:` or of takeover and reassign on a lane bead.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{team,team_cli,team_pending,team_beads,specs,lifecycle_cli,goal}.py`
- Tests: `tests/workflow_core/test_team_{gates,beads,pending,complete}.py`, `test_specs_technical_questions.py`, `test_goal.py`, `test_skill_routing.py`, `test_token_budget.py`
- `plugins/gin-workflow/src/skills/team/references/lanes.md`; docs `docs/reference/cli.md`, `docs/guides/team.md`, `docs/guides/team.vi.md`
- `.planning/specs/2026-11-19-team-lane-plans-design.md`, `.planning/plans/2026-11-19-team-lane-plans.md`
- Commits `82ca8161` to `6cef88a6`; beads `gin-workflow-g9az`, `.1` to `.7`

**Scope**
Team mode planning: lane declarations, lane-marked questions, lane beads, lane plans, lane placeholders, and goal over lane beads.

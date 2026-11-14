# Team progress: pending approvals, partial usage totals, progress sections

**Context**
Epic `gin-workflow-team-progress` (2026-11-14). A team lead could not see from `/gin:progress` which gate pull requests wait for approval, how a milestone stands, or whether usage totals are complete when members collect on different machines.

**Decision/Solution**
- `gin team pending [--workflow-id <epic> | --milestone <id>] [--format json]` (`workflow_core/team_pending.py`) lists open gate pull requests and what they still need. It works only in team mode.
  - Candidates come from one `bd list --all --limit 0`: `spec/<topic>` and `plan/<topic>` branches for epics, track branches for open tracks, and `feat/<topic>` for an epic whose tracks are all closed (`/ship` needs `implementation_complete`, so the ship pull request is never open while a track is).
  - Hosts look a pull request up only by exact branch name (`pr_for_branch`, newest of any state). `PrInfo` has no creation date, and gin stores a gate's pull request only after the gate is proven, so pending rows come from the host, not from Beads.
  - The spec or plan text of an unmerged pull request is read with `git fetch origin refs/heads/<branch>` and `git show FETCH_HEAD:<file>`; a remote-tracking ref does not exist without that fetch.
  - `missing` reuses `team.verify_gate`, which gained keyword-only `before_merge` and `artifact_text`; their defaults keep `gin team check` unchanged.
  - `HostUnavailable` before the first successful lookup exits 2; after that, a failure stays in the row's `error`.
- `gin usage report` adds `partial` and `partial_reasons` (`children_not_merged`, `not_collected`, `unattributed`, `log_sources`, `stale`, `unpriced`). It marks totals as incomplete instead of merging summaries, see [usage-collect](usage-collect.md).
- The `progress` skill adds sub-steps under step 1, in this order: Milestone, Grouping (`--area`, `--repo`, "waiting on another area"), Approvals (`gin team pending`), Spec (its spec pull request is the pending row with gate `requirement_confirmed`), and QA state. QA state lives in the `qa-track` skill (`## QA state`), so progress names no `gin-qa`.

**Consequences**
- Known limits: a spec `Kind:` that exists only on the pull request branch is not read (the bead's `kind:` label, default `capability`, decides); each open gate row costs up to three host calls; `check_plan` errors stay in `missing`; a transient error on the first host call makes the whole command exit 2.
- In a skill, sub-steps numbered `1a.` to `1e.` are not CommonMark list markers and join step 1 as one paragraph. Use indented sub-items, and order them so no step reads data a later step produces (review F-1 and F-2 on `.3`).

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/team_pending.py`, `team.py` (`verify_gate`, `check_approval`), `team_cli.py`, `usage.py` (`report`), `usage_cli.py`
- `plugins/gin-workflow/src/skills/progress/SKILL.md`, `skills/qa-track/SKILL.md`, `skills/report/SKILL.md`
- Tests: `tests/workflow_core/test_team_pending.py`, `test_team_gates.py` (`TestBeforeMerge`), `test_usage.py`, `test_usage_cli.py`, `test_skill_routing.py`
- `.planning/specs/2026-11-14-team-progress-design.md`, `.planning/plans/2026-11-14-team-progress.md`
- Beads: `gin-workflow-team-progress`, `.1` to `.3`
- Related: [team-hosts](team-hosts.md), [milestone-lanes-and-forecast](milestone-lanes-and-forecast.md)

**Scope**
`gin team pending`, `gin usage report` totals, and the `progress` and `qa-track` skills.

# Prep tasks: pre-discuss work under an epic

**Context**
Epic `gin-workflow-y4o8` (workflow `prep-tasks`, 2026-11-13). After `/gin:roadmap`, members did not know their work until `/gin:discuss` ran, and the BA blocked every epic. gin treated every child of an epic as an implementation track (close guard, `implementation_complete`, `gin goal`, milestone forecast, usage tracks, `/execute`, `/ship`), so pre-discuss work could not live under the epic.

**Decision/Solution**
- A prep task is a child bead labelled `prep` and `prep:<type>` (`capture`, `mockup`, `spike`, `question`, `other`), created with `--no-inherit-labels`. `workflow_core/prep.py` owns `is_prep` (label `prep` and no `track:` or `req:` label) and `tracks_of(children)`; every child enumeration uses them (`lifecycle_cli._delivery_state` and `_record_refusal`, `goal.main`, `milestone.remaining_days`, `usage_attribution` via `BeadSpan.prep`).
- `close_guard.check` skips review only for a prep task with no review ledger in the root, the main checkout, or any worktree (file existence; an unreadable path counts as a ledger). It now reads `project.review_ledger` from the main checkout's configuration for every bead; before, a close from a subdirectory read no config and the guard was off.
- `gin record orchestration-ready --epic <prep>` is refused, so `/execute <prep-id>` cannot turn prep work into a standalone track.
- bd 1.0.5 blocks every child of a blocked epic and has no flag to change it. `gin team ready` therefore also lists a prep task whose only blocker is its parent (`bd blocked` `blocked_by == [parent]` joined with `bd list --label prep --status open --limit 0`), and sorts each group by priority, then id.
- `/gin:allocate <epic>|--milestone <id>` (tech lead, outside the lifecycle) proposes from `skills/allocate/references/prep-catalog.md`, assigns by role and load, sets priority by dependency layer (1, 2, 3), and needs `team.beads_sync` in team mode. Skills pass `--exclude-label prep` wherever they pick implementation work; ship closes open prep tasks with `not needed: <epic> shipped` because bd refuses to close an epic with an open child.

**Consequences**
- `prep` is a reserved label. A track mislabelled `prep` without `track:`/`req:` leaves `implementation_complete`; its ledger, if any, still guards the close, and ship lists closed prep tasks as closed without review.
- An older gin treats a prep task as a track; every member updates gin before `/allocate`.
- `bd list` returns 50 rows unless `--limit 0`.
- Execution: antigravity timed out on Track 2 (its two test files take about 190 s) and the route fallback, claude sonnet, finished the uncommitted work. Track 1's close-guard exemption needed a second review cycle (ledger lookup from the main checkout and worktrees).
- Open: a gin-console follow-up shows prep tasks apart from tracks (progress bar, Gantt, report child counts, ready list).

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{prep,close_guard,lifecycle_cli,goal,milestone,usage,usage_attribution,team_beads,team_cli,task_markdown}.py`; `plugins/gin-workflow/src/skills/allocate/`
- Tests: `tests/workflow_core/test_prep.py`, `test_close_guard.py`, `test_lifecycle_cli.py`, `test_goal.py`, `test_milestone.py`, `test_usage.py`, `test_usage_attribution.py`, `test_task_markdown.py`, `test_team_beads.py`, `test_skill_routing.py`
- Docs: `docs/concepts/lifecycle.md` (Prep tasks), `docs/guides/team.md`, `docs/guides/ba.md`, `docs/reference/cli.md`, `docs/roles.md`
- `.planning/specs/2026-11-13-prep-tasks-design.md`, `.planning/plans/2026-11-13-prep-tasks.md`
- Beads: `gin-workflow-y4o8`, `.1` to `.4`
- Related: [epic-kinds](epic-kinds.md), [usage-collect](usage-collect.md), [milestone-lanes-and-forecast](milestone-lanes-and-forecast.md), [non-claude-dispatch](non-claude-dispatch.md)

**Scope**
How pre-discuss work is created, assigned, and kept out of gin's implementation checks.

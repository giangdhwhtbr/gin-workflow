# Milestones: model, scheduler, CLI, roadmap adoption

Epic: gin-workflow-6cji
Status: draft for user review.

## Goal and scope

A PM creates a dated milestone, attaches roadmap epics with estimates, and reads the computed schedule and warnings from `gin-workflow milestone list|show --json`, which gin-console consumes.

The input contract is the cross-repo change `gin-harness-6s4` in `gin-harness/docs/changes/gin-harness-6s4-milestones/` (commit b4ce341): `spec-delta.md` defines REQ-MILESTONE-001..017 and `design.md` defines the Beads model, the JSON contract (`schema: 1`), the error table, and the tests. This spec does not restate those requirements. It records the decisions this repository adds on top of them and how they land in the code. Where the two disagree, this spec wins for gin-workflow internals and the input contract wins for anything gin-console reads.

In scope: REQ-MILESTONE-001..017.

Out of scope:
- gin-console pages and REQ-MILESTONE-UI-* (the gin-console child epic of `gin-harness-6s4`).
- Migrating existing projects; none is needed.
- Moving `team claim` and `team reassign` onto the push helper without reset (R6); team hardening (`gin-workflow-rm-team-hardening`) does that.
- A `setup doctor` check for the milestone type (see R1).

## Requirements

### R1. Milestone type

bd 1.0.5 ships `milestone` as a built-in type (`bd types` lists it under "Core work types (built-in)"; `bd create --type milestone` works with `types.custom` unset, checked on a scratch database on 2026-10-30). gin-workflow does not register a custom type, and `setup doctor` gets no check for it. The epic note and the roadmap risk that said otherwise were wrong.

Milestones never carry labels.

### R2. Modules

- `plugins/gin-workflow/src/scripts/workflow_core/milestone.py`: pure functions with no `bd` or clock access.
  - `status(bead, today)`: `closed`, `planned`, `scheduled`, `active` (REQ-MILESTONE-004).
  - `estimate_days(estimated_minutes)`: `ceil(minutes / 480)`; `None`, `0`, or a negative value gives `None` (unestimated). A value set by hand that is not a multiple of 480 rounds up.
  - `schedule(milestone, epics, outside, start, today)`: planned dates, `finish`, `overflow_days`, and per-epic warnings (REQ-MILESTONE-007, 008). It raises a `CycleError` naming the cycle.
- `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py`: argparse, Beads reads and writes, the backend gate, the role check, and sync.
- `cli.py`: `"milestone"` is added to `TOP_COMMANDS` with a branch importing `milestone_cli.main`, like `team` and `specs`.

### R3. Command surface

`gin-workflow milestone create|update|kickstart|move|estimate|close|list|show` with the arguments of REQ-MILESTONE-001..011. `list` and `show` take `--json`, as the input contract fixes it, even though `team` uses `--format json`. Without `--json` they print a short text table. Write commands print the bead id and the changed fields.

Exit codes:
- 0: success, including schedules with warnings.
- 1: every domain error, every `bd` error, the non-Beads backend, and sync failures.
- 2: the team role check (REQ-MILESTONE-012) and argparse usage errors (consistent with the other command groups).

### R4. Reads

`list` and `show` gate on the backend first and then run one `bd list --all --limit 0 --json`. bd's default limit is 50, so `--limit 0` is required. From that one result they build:
- the milestones (`issue_type == "milestone"`);
- each milestone's epics (`parent` equal to the milestone id);
- `blocks` edges from each bead's `dependencies` (`type == "blocks"`);
- the status and parent of every bead outside the milestone, for `external_depends_on`.

`list` drops closed milestones unless `--all` is given. A `CycleError` makes `show` exit 1 naming the cycle and sets the `error` field of that `list` entry. `today` is the local date from one `_today()` function, so tests patch one place. `--start` never writes.

`unassigned_epics` counts beads that have `issue_type == "epic"`, the label `roadmap`, a status other than `closed`, and no parent. The type filter matters because bd 1.0.5 copies a parent's labels to children created with `--parent`, so tracks under a roadmap epic also carry `roadmap` (checked on a scratch database on 2026-10-30). Re-parenting an epic does not change its labels.

### R5. Writes

Every write runs these steps in order and stops at the first failure:

1. **Backend gate:** `tasks.backend(root)` must be `beads`. Otherwise exit 1 naming `providers.task_tracking: beads` (REQ-MILESTONE-014).
2. **Role check (team mode with a non-empty `team.permissions.milestone` only):** `team.require_member`, then a check that the member holds one of the listed roles. Either failure exits 2 naming the roles. In team mode without the key, and in individual mode, there is no check (REQ-MILESTONE-012).
3. **Pull (team mode with `beads_remote` only):** `team_beads.sync`. A failure exits 1 and says nothing was written.
4. **Validation:** read the involved beads and validate every rule of the input contract's error table before any write. For `move` with several epics, every epic is validated first.
5. **Write:** with `bd create`, `bd update` (`--metadata`, `--set-metadata`, `--parent`, `--estimate`, `--title`), or `bd close`, passing `BD_ACTOR` in team mode. If `bd` fails partway through a multi-epic `move`, the message lists the epics already moved and the one that failed.
6. **Push (team mode with `beads_remote` only):** `team_beads.push` (R6). A failure exits 1 and says the change was written locally but not pushed, naming the change (for example "kickoff written locally but not pushed").

A `move` whose source epic is a child of a closed milestone is refused, including `--to none`.

### R6. Push without reset

`team_beads._push` runs `reset_to_remote` (`dolt reset --hard origin/main`) when a push is rejected (`team_beads.py:108-114`), which would discard the milestone write that REQ-MILESTONE-016 says stays local. A new public helper is added:
- Name: `team_beads.push(root, team)`.
- Behavior: it runs `bd dolt push` when `team.beads_remote` is set and raises `SyncConflict` with bd's message on failure.
- It never resets.

`claim` and `reassign` keep `_push` unchanged.

### R7. Team permissions

- `schemas._TEAM` gains `permissions: {milestone: [role, ...]}`, with `additionalProperties: False` on `permissions`.
- `team.py` adds every role in `team.permissions.*` to the "role held by no member" check, so the error reads `team.permissions.milestone: role pm is held by no member`.
- `TeamConfig` exposes the list.
- `/team-setup` asks for the key.
- `docs/reference/config.md` states that every member must update gin-workflow before the lead adds the key, because an older gin-workflow rejects it.

### R8. Ready work excludes milestones

With the Beads backend, `gin-workflow task ready` passes `--exclude-type milestone` to `bd ready` (REQ-MILESTONE-015). The same applies to `tasks.query` for `ready` and to `team_beads.ready`. The markdown backend is unchanged. The `held_by_external` call (`bd ready --explain`) does not need the flag, because it only subtracts beads.

### R9. Roadmap skill and template

`plugins/gin-workflow/src/skills/roadmap/SKILL.md` gains `--milestone <id>` as REQ-MILESTONE-013 and 017 describe:
- Order:
  1. Check the backend and the milestone first, by running `gin-workflow milestone show <id> --json`. A non-zero exit or `status: closed` stops the skill. Then check the write permission: compare `team.me.roles` with `team.permissions` in `gin-workflow state --format json`, and stop when the rule of R5 step 2 would refuse. `team.summary` gains `permissions` (additive) for this.
  2. Propose an estimate in working days for every epic, without counting against `project.max_questions`.
  3. Revise the estimates on request.
  4. After confirmation (and after the roadmap PR merges when `team.approvals.roadmap` is set), create or update the epics as today, then set membership and estimates only through `gin-workflow milestone move` and `gin-workflow milestone estimate`.
- Adoption proposes open and `in_progress` epics labelled `roadmap` that have no parent. For an `in_progress` epic the estimate is the remaining days. Closed epics are never proposed. Title, description, and dependencies are not touched.
- On a re-run, Beads wins for membership and estimates, and the skill reports the differences from the file.
- Every roadmap query in the skill (`task list --label roadmap`) adds `--type epic` (see R4).
- The skill names only `gin-workflow` commands, never `bd` (`tests/test_no_direct_bd.py`).

`plugins/gin-workflow/src/templates/roadmap.md` gains:
- a `## Milestone: <title>` heading per milestone and an `## Unassigned` heading;
- per epic, the lines `Milestone: <id>` and `Estimate: <days>`.

A roadmap file without these lines stays valid. No Python parser reads the roadmap file, so no parser changes.

### R10. Documentation

- `docs/reference/cli.md`: the `milestone` group, its flags, exit codes, and the JSON contract (pointing to the input contract's `design.md` for field meanings).
- `docs/reference/config.md`: `team.permissions.milestone`.
- `docs/concepts/lifecycle.md` or the roadmap section of the README: one paragraph on `/roadmap --milestone`.

## User Stories

### US-1: Plan a dated milestone
As a PM, I want to create a milestone with a start and end date and adjust it later, so that each round of work has a target period.

Acceptance criteria:
- `gin-workflow milestone create "M1" --start 2026-11-02 --end 2026-12-18` prints a new bead id of type `milestone`, and `show --json` reports `status: planned`.
- `create` or `update` with `start` after `end` exits 1 naming both dates, and nothing is written.
- `update` on a closed milestone exits 1, and nothing is written.

### US-2: Kick-start a milestone
As a PM, I want to set or move a milestone's kick-off date, so that the schedule starts when the team starts.

Acceptance criteria:
- `kickstart M1 --date <future>` gives `status: scheduled`.
- `kickstart M1` without `--date` gives `status: active`.
- A second `kickstart` replaces `kickoff` and leaves `start` and `end` unchanged.

### US-3: Attach epics with estimates
As a PM, I want to move epics into a milestone and give each an estimate in working days, so that the milestone has a schedule.

Acceptance criteria:
- `move E1 --to M1` makes E1 a child of M1. `move E1 --to none` removes the parent.
- `move` exits 1 without writing when a source is not an epic, has a non-milestone parent, or is in a closed milestone, or when the target is closed or not a milestone.
- `estimate E1 5` stores `estimated_minutes=2400`, and `show` reports `estimate_days: 5`.
- `estimate E1 0` exits 1, and the estimate is unchanged.

### US-4: Read the schedule
As a PM or tech lead, I want `show` and `list` to report planned dates and warnings in a stable JSON shape, so that I and gin-console can see what overruns.

Acceptance criteria:
- `show --json` matches the input contract's `show` example field for field, with `schema: 1`.
- `list --json` matches the input contract's `list` example, with `schema: 1`.
- The chain, weekend, and unestimated-dependency scenarios of REQ-MILESTONE-007 produce the stated dates.
- `overflow`, `late`, `unestimated`, and `external_blocker` appear as REQ-MILESTONE-008 states, and the command exits 0.
- `show --start D --json` reports `preview: true` and `schedule_start: D`, and leaves Beads unchanged.
- A dependency cycle makes `show` exit 1 naming the cycle. In that case `list` exits 0 and the entry carries `error`.
- `unassigned_epics` counts open roadmap epics without a parent, not their tracks.

### US-5: Close a milestone and carry work over
As a PM, I want to move unfinished epics to the next milestone and then close the old one, so that a milestone can end early.

Acceptance criteria:
- `close M1` with an open child epic exits 1 naming it, and M1 stays open.
- After the open epics move to M2, `close M1` closes it.

### US-6: Restrict and share milestone writes in a team
As a team lead, I want only the configured roles to change milestones, and every change shared through the team's Beads remote, so that the plan stays consistent across members.

Acceptance criteria:
- With `team.permissions.milestone: [pm]`, a member without `pm` gets exit 2 naming `pm`, and nothing is written.
- Without a `team:` section, writes run without a role check.
- Config validation fails for a permission role that no member holds.
- With `beads_sync` and a rejected push, the command exits 1, says the change was written locally but not pushed, and the local Beads keeps the change.

### US-7: Plan or adopt a milestone's roadmap
As a PM, I want `/roadmap --milestone <id>` to propose the milestone's epics with estimates, including epics that already exist, so that I get a schedule without estimating each epic by hand.

Acceptance criteria:
- After confirmation, every epic of the roadmap is a child of the milestone with an estimate in Beads, and the roadmap file lists them under the milestone heading with `Milestone:` and `Estimate:` lines.
- Existing open and in-progress roadmap epics without a parent are proposed. Closed ones are not. Dropped epics stay unassigned under `Unassigned`. Title, description, and dependencies are unchanged.
- On a re-run, a differing estimate is reported (file vs Beads), and Beads keeps its value.

### US-8: Milestones are not ready work
As a developer, I want `task ready` to list only workable beads, so that a milestone never shows up as something to pick up.

Acceptance criteria:
- With the Beads backend, `gin-workflow task ready --json` lists an unblocked epic under M1 and does not list M1.

## Errors and compatibility

- Errors follow the input contract's Error Handling table, plus R3 (exit codes) and R5 (partial `move`, a source in a closed milestone).
- The JSON contract is additive-only under `schema: 1`. A removed field or a changed meaning raises `schema`, and gin-console refuses an unknown schema (REQ-MILESTONE-UI-005).
- `task ready` output loses milestone beads. Milestone beads exist only once this epic ships, so no existing output changes. gin-console filters them separately (REQ-MILESTONE-UI-007), and the two epics ship together under `gin-harness-6s4`.
- The `team.permissions` key makes the config unreadable to an older gin-workflow. This is documented in R7, and no migration is needed.
- `estimated_minutes` is unused elsewhere in gin-workflow, so adopting it changes no current behavior.
- Assumptions: dates use the machine's local timezone. Closed epics keep their planned dates. Track beads under an epic are not part of the schedule.

## Testing

Every test names its REQ-ID.

- `tests/workflow_core/test_milestone.py`, for the pure functions with an injected `today`:
  - chain, parallel epics, and weekend skipping;
  - an unestimated dependency;
  - `overflow`, including `end` on a weekend;
  - `late` only when `active`;
  - `unestimated` and `external_blocker`;
  - a cycle;
  - the start precedence `--start` > `kickoff` > `start`;
  - `estimate_days` rounding up and treating `0`/`None` as unestimated;
  - status derivation.
- `tests/workflow_core/test_milestone_cli.py`, against real `bd`, skipped without it, following `test_team_beads.py`; it runs in-process with `_today` patched:
  - every scenario of REQ-MILESTONE-001..011 and 014;
  - `--start` preview leaves Beads unchanged;
  - `unassigned_epics` ignores tracks that inherited `roadmap`;
  - one golden JSON file each for `list` and `show`.
- `tests/workflow_core/test_tasks.py`: `task ready` passes `--exclude-type milestone` with the Beads backend and not with markdown.
- Team tests:
  - a write allowed and a write refused by role;
  - individual mode skips the check;
  - validation of an unheld permission role;
  - a rejected push (fake `bd` via `fake_cli`) exits 1, says "written locally but not pushed", and runs no reset.
- Roadmap skill (REQ-MILESTONE-013, 017): checked by hand on a fixture project with open, in-progress, and closed roadmap epics, against Beads state (parent and estimate per epic; title, description, and dependencies unchanged), the regrouped roadmap file, an old roadmap file without milestones, and the drift report on a re-run.
- `python -m unittest` and `tests/test_no_direct_bd.py` pass.

Suggested plan tracks:
1. Scheduler and JSON (R2 pure part, R4).
2. CLI writes and `task ready` (R3, R5, R8).
3. Permissions and sync (R6, R7).
4. Roadmap skill, template, and docs (R9, R10).

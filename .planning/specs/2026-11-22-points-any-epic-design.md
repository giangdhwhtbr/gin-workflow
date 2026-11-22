# Story points for every epic through `gin points`

Epic: gin-workflow-05e5
Kind: capability
Status: draft for user review.

## Goal and scope

Only epics labelled `roadmap` can carry story points today. `gin milestone points` refuses any other epic with `<id> is not a roadmap epic` (`plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:397-398`), so `/discuss <epic>` step 8 cannot record the score it proposes for an epic outside the roadmap (seen on gin-workflow-6yoq, 2026-11-22). In this repository 39 of 129 epics carry the `roadmap` label.

This epic adds a dedicated command, `gin points`, that sets the points of any open epic. `gin milestone points` stays as an alias that forwards to it. `/discuss` scores every workflow, in every layout and in team mode, as a `Points:` line of the spec that is reviewed with the spec; the score reaches the epic in Beads as soon as the gate is recorded and the epic exists. The measured pace counts every closed epic with points.

In scope:

- `gin points` in its own module, the alias `gin milestone points`, and the `gin milestone estimate` message that names it.
- The `Points:` line in the templates `design-spec.md`, `technical-design.md`, and `proposal.md`.
- The skills `discuss`, `orchestrate`, `roadmap` (`SKILL.md`, `references/story-points.md`, `references/milestone-plan.md`), and `milestone-close`.
- `days_per_point` and the malformed-points warning over every epic.
- `docs/reference/cli.md`, `docs/reference/config.md`, `docs/guides/team.md`, `docs/concepts/lifecycle.md`, `docs/starters/brownfield.md` and `.vi.md`, the changelog, and the tests.

Out of scope:

- Points on tracks or tasks.
- The forecast and the `unassigned roadmap epics` count of `gin milestone list`: they stay over `roadmap` epics, because they forecast the roadmap.
- `velocity`: it already counts every epic under the milestone, whatever its labels (`plugins/gin-workflow/src/scripts/workflow_core/milestone.py:492-511`).
- gin-console: the JSON schema does not change (see Errors and compatibility).
- The `/discuss` paragraph headed **Roadmap epic**: only step 8 changes.

Assumptions:

- The `--stage` values stay `roadmap|discuss|close` and the default stays `roadmap`, so `gin milestone points` without `--stage` writes the same history as today.
- `story-points.md` stays under `skills/roadmap/references/`; `/orchestrate` links it the way `/discuss` does (`../roadmap/references/story-points.md`).
- The `Points:` line is read by the agent, as the roadmap's `Points:` lines are; no code parses it and `gin specs lint` does not check it.
- In team mode `gin points` follows `team.permissions.milestone`, as `gin milestone points` does today; no new permission key.
- The knowledge record `.planning/knowledge/story-points.md` is updated at ship through `learn`.

## Requirements

### R1: `gin points`

- `gin points EPIC N --reason TEXT [--stage roadmap|discuss|close]` (default stage `roadmap`) sets `points` and `points_reason` on the epic, appends `{from, to, stage, at, actor}` to its `points_history`, and prints `points of <epic> set to <n>`.
- It lives in its own module, `workflow_core/points_cli.py`, with its own parser (`prog="gin points"`). `points` joins `TOP_COMMANDS` in `workflow_core/cli.py` and dispatches to that module. `_points` and `_trace_points` move there from `milestone_cli.py`; the module reuses the configuration, bd, guard, and push helpers of `milestone_cli.py`.
- It accepts any bead with `issue_type: epic` that is not closed; the `roadmap` label is no longer checked.
- It refuses with exit 1 and writes nothing when:
  - `N` is not on the scale 1, 2, 3, 5, 8, 13, 21; the message lists the scale;
  - `--reason` is empty;
  - the bead is missing (`<id> not found`);
  - the bead is not an epic (`<id> is not an epic`);
  - the epic is closed (`<id> is closed`);
  - the epic's parent is a milestone with `kickoff` and the stage is not `close`; the message says the points are locked since that kick-start and names `/milestone-close`;
  - the task backend is not Beads; the message names `providers.task_tracking: beads`.
- In team mode it checks the roles of `team.permissions.milestone` (unset means any member) and exits 2 naming them when the member holds none. With shared Beads it pulls before the write and pushes after it, with the same messages as the milestone writes (`pull failed, nothing written`, `points written locally but not pushed`).
- Errors print on stderr with the prefix `points error:`.

### R2: The alias and the callers

- `gin milestone points EPIC N --reason TEXT [--stage ...]` forwards its arguments to `gin points`. Stdout, exit code, and the metadata written are the same as `gin points`. Errors take the prefix `points error:`.
- `gin milestone estimate` refuses an epic that has points with a message that names `gin points`.
- The skills call `gin points`:
  - `roadmap/SKILL.md` (the `--milestone` step 5 and the Write step) and `roadmap/references/milestone-plan.md` (the Write block);
  - `roadmap/references/story-points.md` (Write, Score in `/discuss`, Lock);
  - `milestone-close/SKILL.md` (the `estimate` action, with `--stage close`).

### R3: Scoring in the lifecycle

The score is decided once, in `/discuss`, for every layout and mode, and written to the epic as soon as both the gate and the epic exist.

- Score: `/discuss` scores every workflow per `story-points.md` before the spec goes to review, and writes the confirmed score as `Points: <n> (<reason>)` under `Kind:` in the header of the design spec (`design-spec.md` or `technical-design.md`), or of `01-proposal.md` with the SDD layout. The three templates carry the line. An epic with points in Beads shows the old and the new score with the reason. Scores do not count against `project.max_questions`.
- Review: the `Points:` line is reviewed with the spec, in chat or in the spec pull request (spec review `pr`, team mode). In team mode the approvers of `team.approvals.requirement_confirmed` approve it with the requirements. A member without a technical role keeps it: the AI proposes the score from the user stories, and it is not written as a `TQ-<n>` question.
- Write: `gin points <epic> <n> --stage discuss --reason "<reason>"` with the values of the `Points:` line, run only when the epic has no points or different points in Beads:
  - `/discuss` step 8, right after `requirement-confirmed` is recorded, when the epic exists: an epic given as `/discuss <epic-id>`, or the epic the SDD discuss created (`sdd` skill, discuss step 2). With spec review `pr` this is the later run that records the gate once the pull request merged;
  - `/orchestrate`, right after it creates the epic because the spec has no `Epic:` line (legacy layout). It copies the `Points:` line without scoring again or asking. A spec without a `Points:` line, written before this epic, leaves the epic without points and says so. With the markdown task backend it skips the step;
  - when the spec names `Epic: <id>` or the layout is SDD, `/orchestrate` writes no points.
- When `gin points` refuses because the epic is locked, or with exit 2 because the member lacks a `team.permissions.milestone` role, the skill shows the score with its reason and the exact `gin points` command, names who can run it (`/milestone-close` for a lock, a member holding one of the roles for a role), and the stage continues. The `Points:` line stays in the spec; Beads wins when they differ.
- `story-points.md`:
  - its "Read on" line names `/roadmap`, `/discuss`, and `/orchestrate`;
  - the anchors come from `gin task list --type epic --status closed --json`: closed epics with `points`, whatever their labels;
  - the section "Re-score in /discuss" becomes "Score in /discuss" with the rules above; `/orchestrate` follows its Write rule. A `technical` epic, which has no user stories, takes its drivers from the design: components, risks, and outside dependencies.

### R4: Pace and warnings over every epic

- `measure_pace` (`milestone.py:117`) counts the 10 most recently closed epics with points and actual days, whatever their labels. The roadmap's `- Days per point:` line and the default 1 still apply when none exists.
- `gin milestone list` and `show` warn `<id>: malformed points metadata ignored` for every open epic whose `points` is present but off the scale, not only `roadmap` epics (`milestone_cli.py:170-179`).

### R5: Documentation

- `docs/reference/cli.md`: a new section `## gin points` with the syntax, the refusals, the team rule, and the stages; the `gin milestone` usage block marks `points` as an alias of `gin points`; the `days_per_point` paragraph says "closed epics" instead of "closed `roadmap` epics"; the `estimate` row names `gin points`.
- `docs/reference/config.md` and `docs/guides/team.md`: `permissions.milestone` also governs `gin points`.
- `docs/concepts/lifecycle.md`: `/discuss` scores every workflow in a `Points:` line of the spec; the score reaches the epic once the spec is confirmed, or at `/orchestrate` for an epic it creates.
- `docs/starters/brownfield.md` and `docs/starters/brownfield.vi.md`: `gin points` instead of `gin milestone points`.
- `docs/changelog.md`: `gin points` for any epic, the alias, and `days_per_point` over every closed epic with points.

## User Stories

### US-1: Score any epic from the command line
As a PM, I want `gin points` to set the points of any open epic, so that epics outside the roadmap carry a size too.

Acceptance criteria:
- `gin points <epic> 5 --reason x` on an open epic without the `roadmap` label exits 0 and prints `points of <epic> set to 5`.
- After it, `gin task show <epic> --json` has `points` 5, `points_reason` `x`, and one `points_history` entry with stage `roadmap`.
- `gin points <epic> 3 --reason x --stage discuss` exits 0 and appends an entry with stage `discuss`.
- `gin points <task> 5 --reason x` on a bead that is not an epic exits 1 with `<task> is not an epic`, and the bead has no `points`.
- An off-scale `N`, an empty reason, a missing bead, a closed epic, and an epic of a kicked-off milestone without `--stage close` each exit 1 and write nothing.
- `gin milestone points <epic> 5 --reason x` prints the same line, exits with the same code, and writes the same `points`, `points_reason`, and history entry as `gin points`.
- `gin milestone estimate <epic> 5` on an epic with points exits 1 and names `gin points`.
- In team mode with `team.permissions.milestone: [pm]`, a member without `pm` gets exit 2 naming `pm`, and nothing is written.

### US-2: Every epic is scored once, in /discuss
As a PM, I want `/discuss` to score every workflow in its spec, so that every epic carries points, reviewed with its requirements, whatever the layout or mode.

Acceptance criteria:
- A spec written by `/discuss` (legacy design spec, technical design, or SDD `01-proposal.md`) has a `Points: <n> (<reason>)` line under `Kind:`.
- `/discuss <epic>` on an epic without points, once `requirement-confirmed` is recorded, adds a `points_history` entry with stage `discuss` and the values of the `Points:` line.
- `/discuss <epic>` on an epic with points shows the old and the new score with the reason; when they are equal, no entry is added.
- An SDD `/discuss` without an epic id writes the score to the epic it created, once the gate is recorded.
- With spec review `pr`, no points are written before the pull request merges; the run that records the gate writes them.
- `/orchestrate` on a legacy spec without an `Epic:` line writes the `Points:` line to the epic it creates, with stage `discuss`, and asks no scoring question.
- `/orchestrate` on a spec with an `Epic:` line, or with the SDD layout, adds no `points_history` entry.
- When `gin points` refuses because the epic is locked, or with exit 2 for a missing role, the skill prints the score and the exact `gin points` command, and the stage still ends with its gate.
- The scoring guide picks its anchors from closed epics with points, whatever their labels.

### US-3: The pace counts every finished epic
As a manager, I want `days_per_point` measured over every closed epic with points, so that the forecast uses all finished work.

Acceptance criteria:
- With a closed epic without the `roadmap` label of 5 points over 10 actual days and a closed `roadmap` epic of 5 points over 5 actual days, `gin milestone list --json` reports `days_per_point` `{value: 1.5, measured_epics: 2, assumed: false}`.
- An open epic without the `roadmap` label whose `points` is `4` makes `gin milestone list` print `<id>: malformed points metadata ignored` on stderr.
- An open epic without the `roadmap` label and outside any milestone is not counted in the forecast's `open_epics` or in `unassigned roadmap epics`.

## Errors and compatibility

- The JSON of `gin milestone list` and `show` keeps its keys and `schema: 1`, so gin-console needs no change. Its `days_per_point` value can change once epics without the `roadmap` label close with points.
- Points already written by `gin milestone points` stay valid; nothing is migrated.
- `gin milestone points` keeps working for every caller, now also for epics without the `roadmap` label. Its error prefix changes from `milestone error:` to `points error:`.
- The skills and the CLI ship in the same plugin and are installed together by `install.sh`.
- A refusal by `gin points` inside `/discuss` or `/orchestrate` never blocks the stage (R3).

## Testing

- `tests/workflow_core/test_points_cli.py` (new; the points tests of `test_milestone_cli.py` move there): US-1 against a real `bd` in a scratch repository, as `test_milestone_cli.py` does now. It covers an epic without the `roadmap` label, `--stage discuss`, a non-epic, every refusal leaving the metadata unchanged, the alias giving the same output and metadata, and the team role refusal.
- `test_milestone_cli.py`: `estimate` names `gin points`; the malformed-points warning on an epic without the `roadmap` label.
- `test_milestone.py`: `measure_pace` counts a closed epic without the `roadmap` label (US-3); the forecast still leaves out an open non-roadmap epic outside a milestone.
- `test_skill_routing.py`: the needles `gin milestone points` become `gin points`; `story-points.md` holds `Points:`, `--stage discuss`, and the anchor command without `--label roadmap`; `discuss/SKILL.md` step 8 no longer limits scoring to a roadmap epic; `orchestrate/SKILL.md` names the `Points:` line and `story-points.md`.
- Template tests: `gin specs template design-spec.md`, `technical-design.md`, and `proposal.md` each print a `Points:` line under `Kind:`.
- Manual (US-2): one `/discuss` run per path (legacy with an epic, legacy topic then `/orchestrate`, SDD) in a scratch repository with Beads, checking `points_history` after each.
- `test_rename_sweep.py` and the docs coverage tests pass with `points` in `TOP_COMMANDS` and its section in `docs/reference/cli.md`.

## Open Technical Questions

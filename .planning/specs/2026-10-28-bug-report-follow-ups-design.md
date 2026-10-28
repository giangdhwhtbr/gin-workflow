# gin-workflow 2.8 bug report follow-ups

Epic: gin-workflow-5c4y
Status: draft for user review.

## Goal and scope

Fix items 5–7 of the gin-workflow 2.8 bug report (`gin-workflow-eq77`), which the Windows support spec (`.planning/specs/2026-10-28-windows-support-design.md`) left out of scope. Each requirement maps to one existing child bead of epic `gin-workflow-5c4y`:

- R1 → `gin-workflow-4nj0`: in team mode, `task close` rejects the assignee that `team claim` set.
- R2 → `gin-workflow-83nh`: `team check-plan` reads natural-language bullets as file lists, and misses the files of plans written in the plan-schema format.
- R3 → `gin-workflow-1zos`: `record` does not say that a failed write recorded nothing; the `orchestrate` skill writes the routes file before the bead ids exist.

Out of scope:
- The two `stage` keys of `gin-workflow state --format json` (item 7): they sit at different levels, and gin-console reads the top-level `stage`.
- The bd error text "reclaim or use --force to override": it comes from bd, not gin-workflow. With R1 the mismatch that triggers it no longer happens.
- The markdown task backend (`providers.task_tracking: markdown`): it has no assignee check, so R1 applies to the Beads backend only.

## Requirements

### R1. `gin-workflow task` runs bd as the team member

Cause: `workflow_core/tasks.py::main` passes every `gin-workflow task …` command straight to `bd`, which takes the actor from git `user.name`. `team claim` sets the assignee by running bd with `BD_ACTOR=<member email>` (`team_beads._bd`), so the two identities differ.

Change, in `tasks.main` on the Beads path: when team mode is on (`team.team_for_repo(root)` returns a team), `--actor` is not in the arguments, and `BD_ACTOR` is not set in the environment, run bd with `BD_ACTOR` set to the email of `team.current_member(root, team)`.
- Applies to every `task` subcommand, so all writes use the same identity as `team claim`.
- When git `user.email` is not a team member, or team mode is off, bd runs with the environment unchanged.
- `task ready` (handled by `_ready`) is read-only and unchanged.

### R2. `team check-plan` reads files only from a track's Files block

`workflow_core/team.py::plan_tracks` changes how it collects a track's files; Area, Owner, track headings and fenced-code skipping stay as they are.

- A Files block starts at a line whose stripped text is `**Files:**`, `**Files**:`, `- **Files**:`, `- **Files:**`, or the same without bold.
- Block entries are the list lines (`- …`) that follow it. When the label line is itself a list item, entries must be indented deeper than it. The block ends at the first line that is not such an entry (a blank line, a non-list line, a list line at the label's level or shallower, a heading).
- From the label line's remaining text and from each entry, after an optional leading verb `Create`, `Modify`, `Test`, or `Delete` (with or without `:`), the files are the leading run of backticked tokens separated by commas. A token with whitespace is not a file. A trailing `:<line range>` is stripped, as today. Text after the run (for example `(imports lines 3–16; \`_file_lock\` lines 166–206)`) is ignored.
- Lines outside a Files block never contribute files. A bullet such as `- **Modify:** the row's button opens "..." filled from \`GET /:id\`` is ignored.

`plugins/gin-workflow/src/skills/plan/plan-schema.md` replaces `- **Files**: list of files to modify` with the block format above (one entry per file: `  - Create|Modify|Test \`path\``) and states that `team check-plan` reads files only from this block.

### R3. `record` reports an unwritten gate; `orchestrate` creates beads before routes

- `lifecycle_cli._record_command` catches `EventPersistenceError`, `RuntimeError`, and `OSError` from `store.append(event)` and returns `{"status": "error", "message": "<gate> not recorded for <workflow-id>: <error>"}` with exit code 1. The text output prints it as `error: …` on stderr, the JSON output as the payload, like the other record errors.
- `plugins/gin-workflow/src/skills/orchestrate/SKILL.md`: step 3 (write the routes file and run `routes resolve`) and step 4 (create the track beads) swap places, and the routes step says to key the routes file by the real track bead ids created in the step before.

## User Stories

### US-1: Close the bead I claimed
As a team member, I want `gin-workflow task close` to accept the bead I claimed with `team claim`, so that I do not need `--actor` or `--force`.

Acceptance criteria:
- In team mode, `team claim <bead>` followed by `gin-workflow task close <bead> --reason …` runs bd with `BD_ACTOR` equal to my team email.
- An explicit `--actor` or an existing `BD_ACTOR` is passed through unchanged.
- Outside team mode, or when my git email is not a member, bd's environment is unchanged.

### US-2: Plan checks that see the real file lists
As a team lead, I want `team check-plan` to check exactly the files a track lists, so that behavior bullets do not fail the check and listed files are not skipped.

Acceptance criteria:
- A track containing `- **Modify:** the row's button opens "..." filled from \`GET /:id\`` outside its Files block reports no `GET /:id` file.
- A plan in the plan-schema format (`- **Files**:` followed by `  - Modify \`path\` (notes)` entries) yields every listed path, without the backticked names in the notes.
- The existing team plan fixtures (`**Files:**` followed by `- Create: \`path\``) yield the same files as before.
- `plan-schema.md` documents the Files block and that `team check-plan` reads only it.

### US-3: Know when a gate was not recorded
As a user recording a gate, I want a failed write to say that nothing was recorded, so that I do not guess from a traceback whether the gate exists.

Acceptance criteria:
- When appending the event fails, `gin-workflow record` exits 1 and prints `error: <gate> not recorded for <workflow-id>: <cause>`, and the event log holds no event for it.
- The `orchestrate` skill creates the track beads before it writes the routes file, keyed by their real ids.

## Errors and compatibility

- R1 only adds an environment variable for bd; an explicit `--actor` wins in bd, and an existing `BD_ACTOR` is kept.
- R2 can make `team check-plan` report area violations that the old parser missed in plan-schema-format plans. That is the intended fix; existing fixture-format plans parse the same.
- R3 changes a traceback into exit 1 with a message; successful records are unchanged.

## Testing

- R1: `tests/workflow_core/test_tasks.py`, with a fake `bd` that prints `BD_ACTOR`: team mode sets the member email; `--actor` and a preset `BD_ACTOR` are kept; no team mode leaves it unset.
- R2: `tests/workflow_core/test_team_gates.py`: the `GET /:id` regression line, a plan-schema-format plan with notes after the paths, and the existing fixture tests unchanged.
- R3: `tests/workflow_core/test_lifecycle_cli.py`: `store.append` raising each caught error gives exit 1, the "not recorded" message, and no event.
- Full suite: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all`.

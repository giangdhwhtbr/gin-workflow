# Prep tasks: allocate pre-discuss work under an epic

Workflow: prep-tasks
Kind: capability
Status: draft for user review.

## Goal and scope

After `/gin:roadmap`, members do not know what to do until `/gin:discuss` runs, and discuss itself waits for inputs that only the BA (a legacy capture, a mockup) or a lead (a technical spike) can produce. A tech lead runs a new skill, `/gin:allocate`, that creates these pre-discuss tasks ("prep tasks") as children of each epic and assigns them, so the BA works across epics in order without waiting for anyone, and gin never treats a prep task as implementation work.

Problem (user, 2026-11-12 and 2026-11-13): roadmap epics assign no work to anyone, so members are unclear what to do; the BA should move across epics without blocking. Checked on master `c93fe7cc`:
- gin treats every child of an epic as an implementation track. `implementation_complete` needs every child closed (`workflow_core/lifecycle_cli.py:128-143`); `record shipped` refuses an epic with children (`lifecycle_cli.py:174-181`); `gin goal` lists every open child as a track (`workflow_core/goal.py:61-67`); `milestone.remaining_days` divides by every non-epic child (`workflow_core/milestone.py:187-190`); the ship-stage usage window waits for every child to close (`workflow_core/usage_attribution.py:134-141`).
- With `project.review_ledger` on, closing any bead that has a parent needs an approved review ledger or `--waive-review`, and the waiver then shows at ship as a track closed without review (`workflow_core/close_guard.py:90-101`, `skills/ship/SKILL.md` step 1).
- `/gin:execute`, the ship and orchestrate handoffs, `/gin:progress`, and the `parallel-agents` skill pick or list work from `gin task ready`, which includes every child (`skills/execute/SKILL.md` section 1 step 2, `skills/ship/SKILL.md` step 9, `skills/orchestrate/SKILL.md` step 5, `skills/progress/SKILL.md` step 1, `skills/parallel-agents/SKILL.md` step 1).
- bd copies a parent's labels to a child unless `--no-inherit-labels` is passed, so a child of a roadmap epic carries `roadmap` and `kind:<kind>` (`bd create --help`, bd 1.0.5; the labels come from `skills/roadmap/SKILL.md` step 6).
- bd blocks every child of a blocked epic: with epic A depending on an open epic B, a child of A is listed by `bd blocked` (`blocked_by: [A]`) and never by `bd ready`, and `bd ready` has no option to change that. `gin team ready` starts from `bd ready` (`workflow_core/team_beads.py:87-111`), so a BA would not see prep work of later epics.
- bd refuses to close an epic that has an open child (`cannot close epic <id>: 1 open child issue(s)`).
- In team mode without `team.beads_sync`, each member has a separate Beads database, so beads one member creates are invisible to the others (`skills/team/SKILL.md` section orchestrate).
- The capture and mockup skills write confirmed asset folders and never touch beads; the core plugin may not name them (`tests/gin_ba/test_ba_packaging.py`, `test_core_never_refers_to_gin_ba`).
- Budgets left (`tests/workflow_core/test_token_budget.py`): roadmap `SKILL.md` 17 characters, `team` 7, `sdd` 34, the execute chain 555, the review chain 424, the plan chain 433, the discuss chain 1,532, all skill descriptions together 351.

The bd facts were probed on bd 1.0.5 on 2026-11-13.

In scope:
- Prep tasks: the label, one predicate and one helper, and their use wherever gin enumerates an epic's children.
- CLI filters on both task backends, and `gin team ready` for prep tasks held only by their epic.
- The `/gin:allocate` skill and its catalog of prep types.
- Small edits to `discuss`, `execute`, `ship`, `orchestrate`, `progress`, `parallel-agents`, the roadmap way-of-working reference, and the stage contract.
- Docs and translations.

Out of scope:
- gin-console views (R12). Nothing breaks there: it reads only `stage`, `project.layout`, and `gates` from `gin state` and the unchanged shape of `gin milestone list|show --json`. Until the follow-up, its child counts, progress bars, Gantt rows, and ready list include prep tasks.
- Checking, when a capture or mockup prep task closes, that the folder it names is confirmed.
- Assigning implementation tracks: the plan's `Owner:` already does that in team mode.
- A permission for `/gin:allocate`: the docs name it as the tech lead's skill, and anyone can already create beads with `gin task create`.

Confirmed decisions (user, 2026-11-13): prep tasks are children of the epic marked by a label; `/gin:allocate` takes one epic or a whole milestone; discuss warns about open prep tasks and continues; the catalog has `capture`, `mockup`, `spike`, `question`, plus free `other` tasks; gin-console gets a follow-up bead; no new permission key.

Rejected alternatives: a custom bd issue type `prep` needs `types.custom` in every clone and type support in the markdown backend; prep beads outside the epic (a separate parent, or a `prep-for:<epic>` label) avoid the exclusions and the parent blocking, but the work no longer sits under its epic, which the user wants.

## Requirements

R1. Prep task. A prep task is a child bead of an epic that carries the labels `prep` and `prep:<type>`, where `<type>` is `capture`, `mockup`, `spike`, `question`, or `other`. It is created with `--no-inherit-labels`, so it carries neither `roadmap` nor `kind:<kind>`. `workflow_core` gains two functions that every rule below uses:
- `is_prep(record)`: true when the bead's labels include `prep` and include no `track:<N>` or `req:<id>` label (the labels team mode and the SDD layout put on implementation tracks).
- `tracks_of(children)`: the children for which `is_prep` is false.

R2. Closing a prep task. `close_guard` does not require a review ledger for a prep task that has none, and writes no `review.waived` event for it. A prep task that has a review ledger, found in the main checkout or any worktree as `usage._ledger` looks for one, follows today's rule, so labelling a reviewed track `prep` does not skip its review. The other checks are unchanged, including the refusal when the tracker cannot be read.

R3. Delivery state. `_delivery_state` and the `record shipped` refusal apply `tracks_of` before any other decision. `implementation_complete` is then true when every track is closed. An epic whose only children are prep tasks behaves as an epic without children. `references/stage-contract.md` and the state docs say "every child not labelled `prep`".

R4. No implementation from a prep task. `gin record orchestration-ready --epic <id>` refuses when `is_prep` is true for bead `<id>`, with `orchestration-ready refused: <id> is a prep task, not implementation work`. When the tracker cannot read the bead, the record behaves as today.

R5. Goal. `gin goal` builds its track list with `tracks_of`. An epic whose only children are prep tasks is handled as one without children.

R6. Milestone forecast. `milestone.remaining_days` counts only `tracks_of` the epic's children.

R7. Usage.
- A prep task stays a member of its epic in `gin usage collect`, so its cost counts toward the epic.
- `BeadSpan` gains a `prep` flag. A prep span is never a track for the ship-stage window in `usage_attribution.attribute`, so an open prep task does not stop ship attribution.
- A prep span is never a holder in `usage_attribution._key`, so a claimed prep task that overlaps a track does not hide the track's review usage.
- `usage.quality` adds no reopens from prep tasks to the epic.

R8. CLI filters.
- `gin task list` and `gin task ready` accept `--exclude-label <label>` (repeatable) on the markdown backend, as bd already does.
- The markdown backend's `gin task create` accepts `--no-inherit-labels` and ignores it, because that backend never copies labels.
- `gin team ready` accepts `--exclude-label <label>` (repeatable) and drops beads with any of those labels.
- `gin team ready` also lists a prep task held only by its epic: an `open` bead for which `bd blocked --json` gives `blocked_by` equal to `[P]` and `bd list --label prep --status open --limit 0 --json` gives `parent` equal to `P`. A prep task whose own `dependencies` in that `bd list` row include any `blocks` entry, external ones included, stays out. The assignee and area rules are the same as for other beads. A failure of either query raises the same `TeamError` as a failed `bd ready --explain`.
- `gin team ready` keeps its two groups in order, ready rows first and expired-claim rows after, and sorts each group by priority, then id. Each row carries `priority`.

R9. `/gin:allocate`. A new skill outside the lifecycle, like `/gin:roadmap`: it records no gate.
- Invocation: `/gin:allocate <epic>` or `/gin:allocate --milestone <id>`.
  - With `--milestone`, the epics, their `status`, `spec_confirmed`, and `depends_on` come from `gin milestone show <id> --json`. The skill skips a closed epic and one with `spec_confirmed` set, and names them; `spec_confirmed: null` counts as not confirmed and is said so.
  - With one epic, it uses `gin task show <epic> --json` and `gin state --workflow-id <epic> --format json`, and stops when the epic is closed or `requirement_confirmed` is satisfied: prep work comes before discuss.
- Team mode: it reads `team.members` (email, roles), `team.areas` (name, lead role), and `team.beads_sync` from `.agent-workflow/config.yaml` of the main checkout. It stops when `team.beads_sync` is not set, because prep tasks would exist only in the runner's database. It runs `gin team sync` before and after writing.
- Inputs per epic: its `kind:` label; the `Capabilities:`, `Scope:`, `Evidence:`, `Risks:`, `Complexity:`, and `Tracks:` lines of its roadmap entry, else of its description, skipping any line that is missing; its prep tasks (`gin task list --parent <epic> --label prep --all --json`); and, with `project.layout: sdd`, the confirmed asset folders of its capabilities. A confirmed asset folder is `<specs>/<cap>/assets/<YYYY-MM-DD>/` whose `description.md` has a `Confirmed: <date>` line. It is a legacy capture when that file also has `Kind: legacy`, and a mockup when the folder holds `mockup/index.html`.
- The catalog, in `skills/allocate/references/prep-catalog.md`:

  | Type | Default role | Proposed when | Done when |
  |---|---|---|---|
  | `capture` | `ba` | SDD layout only. A `parity` epic, or a `capability` epic whose `Scope:` or `Evidence:` names existing behaviour, and the capability has no confirmed legacy capture. | A confirmed legacy capture exists; the close reason names its folder. |
  | `mockup` | `ba` | SDD layout only. A `capability` epic whose scope includes new screens, and the capability has no confirmed mockup. | A confirmed mockup exists; the close reason names its folder. |
  | `spike` | a member holding the lead role `team.areas.<area>.lead` of the area named in `Tracks:`; else a member whose role ends in `_lead` | A `technical` epic, an epic with `Complexity: high`, or a technical risk in `Risks:`. | With Beads, the epic has the comment `[gin answer] <prep-id>: <finding>`; with the markdown backend, the close reason holds the finding. |
  | `question` | `pm`, or `ba` for a business-rule question | Each open business question in `Risks:` or the description. | With Beads, the epic has the comment `[gin answer] <prep-id>: <answer>`; with the markdown backend, the close reason holds the answer. |
  | `other` | chosen by the lead | The lead adds it. | As the lead writes it. |

- Assignment in team mode: a member who holds the type's role; among several, the one with the fewest open or in-progress prep tasks (`gin task list --label prep --status open,in_progress --assignee <email> --json`). With no holder, the skill asks the lead to name a member or drop the task. In solo mode it sets no assignee.
- Order and priority: with `--milestone`, epics are ranked by dependency layer among the run's epics (layer 0 has no open blocker in the run), and each prep task gets priority 1 for layer 0, 2 for layer 1, and 3 for deeper layers. With one epic, a prep task gets the epic's priority.
- Identity: a `capture` or `mockup` task is identified by its epic, type, and capability. Its title is `Capture: <capability>` or `Mockup: <capability>`, and at most one open task exists per identity. `spike`, `question`, and `other` tasks are matched by the lead: the table shows the epic's existing prep tasks next to each proposal, and a new one is created only when the lead says it differs.
- Confirmation: the skill presents one table (epic, type, title, assignee, priority, done when, existing match) and revises it until the lead confirms. Then, per new task: `gin task create --parent <epic> --no-inherit-labels --labels prep,prep:<type> [--assignee <email>] -p <priority> --acceptance "<done when>" -d "<work, inputs, output>" "<title>"`.
- Re-run: it proposes only differences (new tasks, `gin task update <id> --assignee <email>`, `gin task update <id> -p <priority>`). It never deletes a task and closes one as `not needed` only when the lead confirms.
- Report: each member's prep tasks in priority order. Where members find them: `gin team ready` in team mode, `gin task list --label prep --status open,in_progress` in solo mode. How to finish one: for `spike` and `question`, first `gin task comment <epic> "[gin answer] <prep-id>: <text>"` (Beads); then `gin task close <id> --reason "<output>"`; then `gin team sync` in team mode.
- Limits: the skill names capture and mockup work by their outputs, never by another plugin's skill names. Its `SKILL.md` stays within 6,000 characters, enforced by the budget test, and its description within 160 characters.

R10. Edits to existing skills. New lines contain neither `project.team` nor `sdd`, because `test_team_guidance_loads_on_demand` and `test_sdd_guidance_loads_on_demand` count those lines in stage skills.
- `discuss`: after reading the epic, it runs `gin task list --parent <epic> --label prep --all --json`. It warns about each open prep task (title, assignee) and continues. It uses the outputs that closed prep tasks name in their close reasons. Spike and question answers arrive as epic comments, which discuss already reads.
- `execute`: the existing resume and pick lines pass `--exclude-label prep` to `gin task list`, `gin task ready`, and `gin team ready`. A bead labelled `prep` named on the command line is refused as not implementation work.
- `ship`:
  - Step 1 skips prep tasks in the review-ledger `validate` and `render` loop. It lists each closed prep task of the epic (id, title, close reason) to the user as closed without review, next to `review_waivers`.
  - The merge `cleanup` loop skips prep tasks.
  - Close-out lists each open prep task to the user, then closes it with the reason `not needed: <epic> shipped` before closing the epic, because bd refuses to close an epic with an open child.
  - Step 9 lists `gin task ready --exclude-label prep`.
- `orchestrate` step 5 and the `parallel-agents` skill step 1 use `gin task ready --exclude-label prep`.
- `progress`: its ready work comes from `gin task ready --exclude-label prep`. For each epic it lists prep tasks apart from tracks, with assignee and status.
- `roadmap/references/way-of-working.md`: the spec cadence text tells the lead to run `/allocate --milestone <id>` for the BA work due before kickoff. `roadmap/SKILL.md`, `team`, and `sdd` do not change.
- `references/stage-contract.md`: the `implementation_complete` sentence of R3.

R11. Docs, with their `.vi.md` translations:
- `docs/concepts/lifecycle.md`: a prep tasks section, and `implementation_complete`.
- `docs/concepts/state-model.md`: `implementation_complete`.
- `docs/roles.md`: the tech lead runs `/allocate`; the assignee closes prep tasks.
- `docs/reference/skills.md`: the `allocate` row.
- `docs/reference/cli.md`: `--exclude-label`, the markdown `--no-inherit-labels`, `team ready` (`--exclude-label`, prep tasks held by their epic, priority order), and the R4 refusal.
- `docs/guides/team.md`: prep tasks need `team.beads_sync`.
- `docs/guides/ba.md`: how the BA finds and closes prep tasks.
- The docs name `prep` as a reserved label.

R12. Follow-up. A bead in gin-console: show prep tasks apart from tracks in the epic progress bar, the Gantt view, the report child counts (`reports/service.py`), and the ready list (`projects/source.py`).

## User Stories

### US-1: The lead hands out pre-discuss work for a sprint
As a tech lead, I want one command to create and assign the prep work of every epic in a milestone, so that each member knows their work right after the roadmap.

Acceptance criteria:
- `/gin:allocate --milestone <id>` presents one table of proposed prep tasks for the milestone's epics that are open and not yet confirmed, ordered by dependency layer.
- After the lead confirms, each created bead is a child of its epic with the labels `prep` and `prep:<type>`, an assignee in team mode, a priority from its epic's layer, and neither `roadmap` nor `kind:` labels.
- Running it again on the same milestone creates no second `capture` or `mockup` task for the same epic and capability.
- In team mode without `team.beads_sync`, it stops and names the reason.

### US-2: The BA works across epics without waiting
As a BA, I want my prep tasks from every epic in one ordered list that I can close as I finish them, so that I never wait on another member and nobody waits on a review I cannot give.

Acceptance criteria:
- `gin team ready` run by the BA lists the BA's prep tasks from several epics sorted by priority, including the prep task of an epic that depends on another open epic.
- `gin team ready` does not list a prep task that has an open blocker of its own.
- With `project.review_ledger` on, `gin task close <prep-id> --reason "<folder>"` succeeds without `--waive-review`, and `gin state --format json` lists no review waiver for it.
- `/gin:discuss <epic>` with an open prep task names it and its assignee and goes on with the discussion.

### US-3: Prep tasks never count as implementation
As a tech lead, I want gin to keep prep tasks out of every implementation step, so that delivery state, goals, and forecasts stay correct.

Acceptance criteria:
- An epic whose tracks are all closed reads `implementation_complete: satisfied` while one of its prep tasks is open or reopened.
- `gin goal --workflow-id <workflow>` lists no prep task.
- `gin record orchestration-ready --epic <prep-id>` is refused with a message naming the prep task.
- `gin task ready --exclude-label prep` lists no prep task on either backend.
- Closing a bead labelled `prep` that has a review ledger still needs the approved ledger or `--waive-review`.
- `/gin:ship` runs no review-ledger check on a prep task, lists the closed ones as closed without review, and closes each open one before closing the epic.
- `gin milestone show` computes an in-progress epic's remaining days from its tracks only.

### US-4: Projects without prep tasks behave as before
As a member of an existing project, I want nothing to change until someone creates a prep task, so that adopting the feature is a choice.

Acceptance criteria:
- An epic with no `prep` child gives the same `gin state`, `gin goal`, close-guard, milestone, and usage results as before; only the order of `gin team ready` rows changes (Errors and compatibility).
- On the markdown backend, `gin task create --no-inherit-labels` succeeds, and `gin task list --exclude-label prep` drops labelled tasks.

## Errors and compatibility

- No `prep` label anywhere: no behaviour changes. A project that already uses a `prep` label for something else sees those children leave the track checks; the docs name the label as reserved.
- An older gin treats a prep task as a track (it needs a review ledger to close and blocks `implementation_complete`), so every member updates gin before the lead runs `/allocate`. Docs say so.
- Removing the `prep` label turns the bead into a track. Adding `prep` to a track that has a `track:` or `req:` label changes nothing; adding it to another track removes it from `implementation_complete`, but its review ledger, if any, still guards the close, and ship lists it as closed without review.
- A bead labelled `prep` that also has a `track:` or `req:` label is a track for gin, so it blocks `implementation_complete`, but the skills' `--exclude-label prep` hides it from `/gin:execute`; remove the `prep` label. The docs state the exception to "every child not labelled `prep`".
- `gin team ready` now sorts by priority within each group, so its order changes for every team project, with or without prep tasks. Docs say so.
- Closing an epic outside `/gin:ship` fails while a prep task is open: close or reopen-and-close the prep task first.
- A tracker failure keeps today's behaviour at each site: close guard refuses, delivery state reports `unknown`, the R4 check is skipped, and `gin team ready` raises `TeamError`.
- bd needs `--no-inherit-labels` to keep `roadmap` and `kind:` off prep tasks; the markdown backend accepts the flag and ignores it.

## Testing

- `is_prep` and `tracks_of`: a prep task, a prep-labelled bead with `track:<N>` or `req:<id>`, and a plain track.
- Each code site of R2 to R8 gets tests with two fixtures: a closed prep task without a review ledger, and an open prep task assigned to a BA. The sites are `close_guard.check` (also a prep task with a review ledger), `_delivery_state`, the `record shipped` refusal, the R4 refusal, `goal_text` and `gin goal`, `remaining_days`, `usage_attribution.attribute` and `_key`, `usage.quality`, `team ready` (`--exclude-label`, a prep task held only by its epic, one with a blocker of its own, priority order), and the markdown backend flags.
- Delivery state cases: team mode with Beads, an epic not yet orchestrated whose prep tasks are all closed, does not read `implementation_complete: satisfied`; an orchestrated epic whose tracks are all closed stays satisfied after a prep task is reopened.
- A regression test for each site with no prep child keeps today's result.
- A test that `lifecycle_cli`, `goal`, and `milestone` take their track lists from `tracks_of`, and that `usage.collect` sets `BeadSpan.prep` from `is_prep`.
- `tests/workflow_core/test_skill_routing.py` checks the new lines in `discuss`, `execute`, `ship`, `orchestrate`, `progress`, `parallel-agents`, and the way-of-working reference.
- `tests/workflow_core/test_token_budget.py` adds the 6,000-character limit for `allocate`; `test_docs_coverage.py` covers the new skill row.
- `gin docs check` on changed pages; full suite `python3 -m pytest -n auto`.

## Open Technical Questions

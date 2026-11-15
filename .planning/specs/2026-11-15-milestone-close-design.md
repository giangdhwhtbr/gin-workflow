# Guided milestone close

Epic: gin-workflow-milestone-close
Kind: capability
Status: draft for user review.

## Goal and scope

A PM or tech lead closes a milestone in one guided run. Today `gin milestone close ID --reason TEXT` refuses while the milestone has open epics (`plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:347-352`), no skill guides the close, the open epics are moved by hand, and nothing records what the milestone delivered against its plan or what the team learned.

In scope:

- A new skill `/gin:milestone-close [<milestone-id>]` that summarises the milestone and rates it with team-level metrics compared with the previous closed milestone, moves every open epic to the next milestone with a reason and a decision, records the result as a `[gin close]` comment on the milestone bead, closes the milestone, writes a `Result:` block and Way of working changes into the roadmap file, saves lessons as knowledge records, and applies corrected estimates.
- `Result:` in the roadmap template, and the rule that `/roadmap` keeps it.
- The skill description budget raised from 4,000 to 4,500 characters.
- A row in `docs/reference/skills.md` and `docs/reference/skills.vi.md`.

Out of scope:

- Any change to the `gin milestone` CLI or to the `schema: 1` JSON of `gin milestone list` and `show`.
- Splitting an epic: the skill proposes it; `/roadmap` or `/discuss` does it.
- Showing `[gin close]` and `[gin retro]` in gin-console (recorded on `gin-console-workflow-catchup`; the console already reads bead comments through `GET /beads/{project}/{bead_id}/comments`).
- Making retros mandatory.
- Metrics per member.

Assumptions:

- Retros are optional. A milestone without `[gin retro]` comments closes the same way; the skill then asks for every reason.
- Every open epic moves to the next milestone; there is no Unassigned option at close.
- The next milestone is the open milestone with the earliest `start` after the closing milestone's `start`.

Summary confirmed with the user on 2026-11-15: the description and the 2026-11-14 notes stand, with these changes: spillover always moves to the next milestone found by start date; the reason of each open epic comes from the retros, else the person running the close is asked, and the skill then proposes what to do; retros are optional; the result is a `[gin close]` comment (console reads comments), not milestone metadata; confirmed actions are applied; lessons go to knowledge records through the `learn` skill.

Comments considered: 2, latest 2026-11-15T02:12:48Z

## Requirements

### Start

- `/gin:milestone-close [<milestone-id>]`. Without an id, the skill uses the only milestone whose `status` is `active` in `gin milestone list --json`; with none or several, it lists the open milestones and asks which one.
- `gin milestone show <id> --json` must succeed and its `status` must not be `closed`; a closed milestone is refused.
- Before `end`, the skill says the close is early and asks to continue.
- With the Beads task backend only; otherwise it stops with one sentence.
- In team mode, when `project.team.permissions.milestone` lists roles and none is in `project.team.me.roles` (or `project.team.me` is null), the skill stops and names the roles, as `/roadmap --milestone` step 1 does. The CLI enforces the same rule on each write.

### Summary (read only)

- From `gin milestone show <id> --json`: the closed epics; the open epics with `remaining_days`; the `open_bugs` count per epic; `estimate_days` against the working days from `started_at` to `closed_at` (`gin task show <epic> --json`).
- From `gin usage report --milestone <id> --format json`: total cost and the rework signals (reopens, bugs found later, review cycles). A non-zero exit is reported and the summary continues without them.
- From the roadmap file (`.planning/roadmap.md`, or `docs/roadmap.md` with `project.layout: sdd`): the milestone's `Outcome:` and `Demo:`. The skill proposes `reached`, `partial`, or `missed` for each with a one-line note. Without a roadmap file or without these lines, both are `not planned`.
- From `gin task comments <milestone-id> --json`: the newest `[gin retro]` comment per member. With none, the summary says `no retros`.

### Metrics

Added on 2026-11-15 after the first review, at the user's request. Team level only, never per member, computed during the summary:

- `completion`: closed epics over all epics of the milestone at the start of the run, as `<closed>/<total>`.
- `estimate_accuracy`: the sum of `estimate_days` over the sum of actual working days, over closed epics that have both; two decimals; 1.00 means on estimate, below 1 means the work took longer. `n/a` without such an epic.
- `capacity_used`: the sum of `estimate_days` of the closed epics over the milestone's capacity, `lanes` (from `gin milestone show --json`) times its working days, Monday to Friday, from `start` to `end` with both ends included and no `away` days subtracted; two decimals; `n/a` without `lanes` or estimates.
- `cost_per_epic`: `totals.cost` of `gin usage report --milestone <id> --format json` over the closed epics, in USD with two decimals, followed by ` partial` when the report's `partial` is true; `totals.cost` covers every epic of the milestone, open ones included; `n/a` when the report failed, `totals.cost` is null, or no epic closed.
- `rework`: the sum of `quality.reopens` and `quality.bugs` over the report's `beads` entries whose `parent` is not the `bead` of another entry (an epic's `quality` already includes its children, as `totals` in `usage.py` does); `n/a` when the report failed.
- Comparison: the skill reads the `Metrics:` line of the `[gin close]` comment of the most recently closed milestone (`gin milestone list --all --json`, status `closed`, the latest `end` before this milestone's `start`) and shows the change of each metric. Without such a milestone, comment, or line, it says `no earlier metrics`.

### Next milestone

- The open milestone (from `gin milestone list --json`) whose `start` is the earliest after the closing milestone's `start`.
- When there is none, the skill proposes a new one: start on the first working day after the closing milestone's `end`, the same number of working days, a title from the PM. It is created with `gin milestone create "<title>" --start <date> --end <date>` only after the confirmation below.

### Spillover

- Every open epic of the milestone moves to the next milestone.
- For each one the skill looks for its reason in the retros (a `Slowed us:` or `Went well:` line that names the epic id or title) and quotes it. Without one, it asks the person running the close, one epic per message.
- With the reason, it proposes one decision: keep as is, re-estimate (with the new remaining days), split (done later with `/roadmap` or `/discuss <epic>`), or remove a named blocker.
- When the moved epics push the next milestone over its capacity (the bound of the Load block of way of working), the skill still moves them and reports the overflow in working days with a proposal.

### Confirmation

- One table: delivered epics; each spillover epic with target milestone, reason and its source (`retro` or `asked`), and decision; `Outcome:` and `Demo:` results; the actions (`way_of_working` changes as the exact new text, `estimate` changes as epic and days, `lesson` records as topic and summary, and `remember` facts the PM chose). The person running the close revises it until confirmed; nothing is written before.

### Write, in this order

1. Create the next milestone when proposed.
2. `gin milestone move <epic>... --to <next-id>` for the spillover epics.
3. `gin milestone estimate <epic> <days>` for each confirmed estimate action.
4. `gin task comment <milestone-id> "<text>"` with the `[gin close]` comment.
5. `gin milestone close <milestone-id> --reason "Delivered <n> of <m> epics; <k> moved to <next-id>"`.
6. On branch `milestone-close/<milestone-id>`: write the `Result:` block into the milestone's block of the roadmap file, apply the confirmed `## Way of working` changes, and write or update each lesson as `.planning/knowledge/<topic>.md` following the Reconcile steps of the `learn` skill (search first, update instead of duplicating); commit. When `team.approvals.roadmap` lists roles, push and open a pull request as `/roadmap` step 5 does. Without a roadmap file, the `Result:` and Way of working parts are skipped and the report says so; lessons are still written.
7. `gin task remember "<fact>"` for each `remember` fact the PM chose.
8. In team mode with `team.beads_sync` set, `gin team sync`.

- A failing step stops the run and the report names what was written. A re-run continues: the moved epics are no longer in the milestone, and a closed milestone is refused, so a run that stopped after step 5 is finished by hand from the report.

### The `[gin close]` comment

```
[gin close] <milestone-id>
Delivered: <epic-id>, <epic-id>
Spillover: <epic-id> -> <milestone-id>; reason (retro|asked): <text>; decision: <text>
Outcome: reached|partial|missed|not planned; <note>
Demo: reached|partial|missed|not planned; <note>
Retros: <count>
Metrics: completion <closed>/<total>; estimate_accuracy <n.nn|n/a>; capacity_used <n.nn|n/a>; cost_per_epic <n.nn[ partial]|n/a>; rework <n|n/a>
Action: way_of_working|estimate|lesson|remember; <text>
```

- `Delivered:` is `none` when no epic closed. One `Spillover:` line per moved epic, none when nothing moved. One `Action:` line per confirmed action, none without actions. Line breaks inside a value become `; `.
- The labels are never translated: gin-console and later runs parse them.

### Roadmap file

- `templates/roadmap.md` gains an empty `Result:` line in the milestone block, after `Demo:`.
- `/milestone-close` writes it as:

  ```
  Result: closed <YYYY-MM-DD>; delivered <n> of <m> epics; <k> moved to <next milestone title>
  - Outcome: <reached|partial|missed|not planned>; <note>
  - Demo: <reached|partial|missed|not planned>; <note>
  - Metrics: <closed> of <total> epics done (<percent>%); estimates <accuracy as percent> accurate; <capacity_used as percent> of capacity used; <cost> USD per epic; <rework> reworks
  - Spillover: <epic title>: <reason>; <decision>
  - Actions: <one line per action>
  ```

  in business words for a manager, no file paths.
- `skills/roadmap/references/manager-view.md` says that `Result:` is written by `/milestone-close` and that a `/roadmap` run keeps it unchanged.

### Description budget

- `tests/workflow_core/test_token_budget.py` raises the limit of `description_chars` from 4,000 to 4,500.

## User Stories

### US-1: Close a milestone with open epics in one run
As a PM, I want one guided run to close a milestone that still has open epics, so that I do not move each epic by hand.

Acceptance criteria:
- After the run, every epic that was open in the milestone belongs to the next milestone, and the milestone is closed.
- The next milestone is the open one with the earliest start after the closed milestone's start.
- Nothing is written before the person running the close confirms the table.

### US-2: Know why an epic spilled over and what to do
As a tech lead, I want the reason and a proposed decision for each unfinished epic, taken from the retros or asked from me, so that the next milestone starts with a plan for it.

Acceptance criteria:
- A spillover epic named in a retro shows the quoted retro line as its reason, marked `retro`.
- A spillover epic without a retro reason is asked about, one per message, and marked `asked`.
- Each spillover epic has one decision: keep, re-estimate, split, or remove a named blocker.
- A milestone without any retro closes and says `no retros`.

### US-3: Record what the milestone delivered
As a manager, I want the result of the milestone on the milestone bead and in the roadmap file, so that I and gin-console can see what was delivered against the plan.

Acceptance criteria:
- The milestone bead has one `[gin close]` comment in the format above.
- The milestone's block in the roadmap file has a `Result:` block with delivered and moved counts, the Outcome and Demo results, the spillover lines, and the actions, without file paths.
- Without a roadmap file, the comment is still written and the report says the file was skipped.

### US-4: Turn the results into changes
As a PM, I want the confirmed actions applied, so that the next milestone runs with corrected estimates, an updated way of working, and the lessons kept.

Acceptance criteria:
- Each confirmed estimate action is set with `gin milestone estimate`.
- Each confirmed way-of-working change is in the roadmap file's `## Way of working` section in the same commit as `Result:`.
- Each lesson is a new or updated record under `.planning/knowledge/` in that commit.
- Each `remember` fact the PM chose is stored with `gin task remember`.

### US-7: Rate the milestone
As a PM, I want team-level metrics for the milestone compared with the previous one, so that I can see whether the process improves.

Acceptance criteria:
- The summary shows completion, estimate accuracy, capacity used, cost per epic, and rework, each computed as the Metrics section says, with `n/a` where data is missing.
- The summary shows the change of each metric against the most recently closed milestone's `Metrics:` line, or `no earlier metrics`.
- The `[gin close]` comment has one `Metrics:` line with the five keys in that order, and the `Result:` block has a `- Metrics:` line in business words.
- No metric is computed or shown per member.

### US-5: No next milestone yet
As a PM, I want the close to propose the next milestone when none exists, so that spillover always has a place.

Acceptance criteria:
- Without a later open milestone, the table proposes one starting the first working day after `end`, with the same number of working days.
- It is created only after confirmation, before any epic moves.

### US-6: Capacity of the next milestone
As a PM, I want to know when spillover overloads the next milestone, so that I can act before it starts.

Acceptance criteria:
- When the moved epics take the next milestone over its capacity, the report names the overflow in working days and a proposal, and the epics are still moved.

## Errors and compatibility

- The `gin milestone` CLI and its JSON do not change. `close` keeps refusing a milestone with open epics; the skill moves them first.
- Permission failures (exit 2 from `gin milestone` writes) and other non-zero exits stop the run with the message and what was already written.
- A roadmap file without `Result:` lines stays valid; `roadmap_file.py` reads only `Deadline:` and `AI capacity:`.
- With the markdown task backend there are no milestones; the skill stops with one sentence.
- Raising the description budget adds about 125 tokens to the descriptions loaded in each session.

## Testing

- A skill test reads `plugins/gin-workflow/src/skills/milestone-close/SKILL.md` and asserts: the `[gin close] <milestone-id>` first line and the `Delivered:`, `Spillover:`, `Outcome:`, `Demo:`, `Retros:`, `Action:` labels; the next-milestone rule by `start`; the closed-milestone refusal; the confirmation before any write; the write order create, move, estimate, comment, close; the `learn` Reconcile for lessons; the `Metrics:` line with its five keys in order, team level only, and the comparison with the previous `[gin close]`; `team.permissions.milestone`; and no concrete model names.
- The template test asserts `Result:` in the milestone block of `templates/roadmap.md`; a roadmap skill test asserts the keep-`Result:` rule in `manager-view.md`.
- `tests/workflow_core/test_roadmap_file.py`: a file with a `Result:` block gives the same `Deadline` and lanes.
- The token budget test passes at 4,500, and the packaging test lists `skills/milestone-close/SKILL.md`.
- The docs tests pass with the new rows.

## Open Technical Questions

---
name: allocate
description: Propose, assign, and create pre-discuss prep tasks (capture, mockup, spike, question) under roadmap epics, for one epic or a milestone.
---

# Allocate

On `/allocate` only. Outside the lifecycle: it records no gate. Never create or change a bead before the lead confirms the table.

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`), stop: tell the user to run `/setup` once and do nothing else.
2. `gin state --format json` gives `project.layout` and `project.team`.

## Steps
1. Epics. `/allocate --milestone <id>`: `gin milestone show <id> --json` gives each epic with `status`, `spec_confirmed`, and `depends_on`. Skip and name a closed epic and one with `spec_confirmed` set; `null` counts as not confirmed, so say so. `/allocate <epic>`: `gin task show <epic> --json` and `gin state --workflow-id <epic> --format json`; stop when the epic is closed or its requirement is confirmed, because prep work comes before discuss.
2. Team mode. Read `team.members` (email, roles), `team.areas` (name, lead role), and `team.beads_sync` from `.agent-workflow/config.yaml` of the main checkout. Stop when `team.beads_sync` is not set: prep tasks would exist only in this runner's database. Run `gin team sync` before and after writing.
3. Inputs per epic: its `kind:` label; the `Capabilities:`, `Scope:`, `Evidence:`, `Risks:`, `Complexity:`, and `Tracks:` lines of its roadmap entry, else of its description (skip a missing line); its prep tasks from `gin task list --parent <epic> --label prep --all --json`; with `project.layout: sdd`, the confirmed asset folders of its capabilities.
4. Propose tasks from the [prep catalog](references/prep-catalog.md): type, default role, when proposed, and what finishes each. Name capture and mockup work by its output, a confirmed asset folder.
5. Assign in team mode a member who holds the type's role; among several, the one with the fewest tasks from `gin task list --label prep --status open,in_progress --assignee <email> --json`. When nobody holds the role, ask the lead to name a member or drop the task. In solo mode set no assignee.
6. Priority. With `--milestone`, rank the run's epics by dependency layer (layer 0 has no open blocker in the run): layer 0 gets priority 1, layer 1 priority 2, deeper layers 3. For one epic, use the epic's priority.
7. Identity. A `capture` or `mockup` task is identified by epic, type, and capability; its title is `Capture: <capability>` or `Mockup: <capability>`, and one open task exists per identity. The lead matches `spike`, `question`, and `other`: show the epic's existing prep tasks next to each proposal, and create a new one only when the lead says it differs.
8. Present one table: epic, type, title, assignee, priority, done when, existing match. Revise it until the lead confirms.
9. Create each new task: `gin task create --parent <epic> --no-inherit-labels --labels prep,prep:<type> [--assignee <email>] -p <priority> --acceptance "<done when>" -d "<work, inputs, output>" "<title>"`.
10. On a re-run propose only differences: new tasks, `gin task update <id> --assignee <email>`, `gin task update <id> -p <priority>`. Never delete a task. Close one with reason `not needed` only when the lead confirms.
11. Report each member's prep tasks in priority order. Members find them with `gin team ready` in team mode, else `gin task list --label prep --status open,in_progress`. To finish one: for `spike` and `question`, first `gin task comment <epic> "[gin answer] <prep-id>: <text>"` (Beads); then `gin task close <id> --reason "<output>"`; then `gin team sync` in team mode.

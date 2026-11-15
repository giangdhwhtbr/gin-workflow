---
name: retro
description: Record one member's retro on an open milestone (went well, slowed the work, change next) as a comment for the milestone close.
---

# Retro

On `/retro` only. Outside the lifecycle: it records no gate. One question per message. Write nothing until the member confirms the comment.

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`), stop: tell the user to run `/setup` once and do nothing else.
2. Milestones and comments need the Beads task backend. With another backend, say so in one sentence and stop.

## Steps
1. Member. Read `gin state --format json`. With `project.team.enabled`, the member is the email of `project.team.me`; when it is null, stop and name the git email (`git config user.email`) that is not a member. Without team mode, the member is `git config user.name`. In team mode with `team.beads_sync` set in `.agent-workflow/config.yaml` of the main checkout, run `gin team sync` first.
2. Milestone. With `--milestone <id>`, use it. Otherwise use the only milestone whose `status` is `active` in `gin milestone list --json`; with none or several, list the open milestones (id, title, period, status) and ask which one. Run `gin milestone show <id> --json`; on a non-zero exit, report its message and stop. A closed milestone: write nothing and say its close already read the retros.
3. The member's part. From the epic rows of `gin milestone show <id> --json`, list each epic with `title`, `status`, `estimate_days`, and the `count` of its `open_bugs` warning (0 without one). Add the working days, Monday to Friday, from `started_at` to `closed_at` of `gin task show <epic> --json`, or to today when the epic is open; `not started` without `started_at`. In team mode keep only the epics with a track whose `assignee` is the member (`gin task list --parent <epic> --all --json`) and say how many other epics the milestone has. This list helps the member remember; it never goes into the comment.
4. Questions, one per message, in this order: what went well; what slowed the work; what to change in the next milestone. Ask nothing else and suggest no answer. The member may skip a question; write `-` for it.
5. Comment. Show the exact text and ask the member to confirm or edit it:
   ```
   [gin retro] <milestone-id> <member>
   Went well: <answer>
   Slowed us: <answer>
   Change next: <answer>
   ```
   Replace line breaks inside an answer with `; `. Never translate the labels, whatever language the answers use: the milestone close parses them.
6. Write. After the member confirms, run `gin task comment <milestone-id> "<text>"`. On a non-zero exit, report the error, show the text again so the member can retry, and write nothing else. In team mode with `team.beads_sync` set, run `gin team sync`; without it, say that other members see the comment only on this runner's database.
7. Report the milestone, the member, and that the comment was written. A member who runs `/retro` again adds a new comment, and the newest one counts.

# Story points: how the AI scores an epic

Read on `/roadmap` (step 4 and `--milestone` step 2), on `/discuss`, and on `/orchestrate` when it creates the epic.

## Scale
Points measure size relative to other epics, never time: 1, 2, 3, 5, 8, 13, 21. Days come from `gin milestone show` or `list`: points times `days_per_point`, rounded up. The command refuses any other value.

## Score
1. Drivers, read from the epic: volume (screens, endpoints, and tables of `Legacy:` in `/roadmap`; the user stories and their acceptance criteria of the confirmed spec in `/discuss`, or the components of the design for a `technical` epic), `Complexity:`, the unknowns of `Risks:`, and the outside dependencies (`Depends on:` and external services).
2. Anchors: from `gin task list --type epic --status closed --json`, pick one or two closed epics with `points` of similar drivers and compare (`same size as <epic> = 5`). Without them, score from the drivers only.
3. Take the nearest scale value. Above 21, propose a split into epics of 21 or less instead of a score.
4. Reason: one line, business words plus the counts, for example `12 screens, 31 endpoints, high: payment gateway`.

Show `Points: <n> (<reason>)` with the derived `Estimate: <days>` per epic. The PM confirms or corrects each; a corrected score gets the reason `PM: <the PM's reason, else corrected>`. Scores and corrections do not count against `project.max_questions`.

## Write
Run `gin points <epic> <n> --reason "<reason>"` for each epic whose points are missing in Beads or changed in this run. On a re-run Beads wins: a differing `Points:` line is reported, not written. An epic that keeps only a day estimate is valid input; propose a score for it.

## Score in /discuss
In every layout and in team mode, `/discuss` scores the workflow before the spec goes to review and writes `Points: <n> (<reason>)` under `Kind:` of the design spec, or of `01-proposal.md` with the SDD layout. When the epic has points in Beads, show the old and new points with the reason. The line is reviewed with the spec, in chat or in its pull request; a member without a technical role keeps it and never turns it into a `TQ-<n>` question.

Once `requirement-confirmed` is recorded (with spec review `pr`, by the run that records it after the merge) and the workflow has an epic, run `gin points <epic> <n> --stage discuss --reason "<reason>"` with the values of the `Points:` line, unless Beads already holds them. `/orchestrate` does the same right after it creates the epic for a spec without an `Epic:` line: it copies the line, scores nothing, and asks nothing; a spec without the line leaves the epic without points, and it says so. With the markdown task backend, `/discuss` and `/orchestrate` skip `gin points`, which needs Beads; the `Points:` line stays in the spec.

When `gin points` refuses because the milestone has kicked off, or exits 2 for a missing role, show the score, its reason, and the exact command, name who can run it (`/milestone-close` for a lock, a member holding a `team.permissions.milestone` role), and continue the stage. Beads wins over the `Points:` line.

## Lock
Points lock when the epic's milestone kicks off: `gin milestone kickstart` stores the committed points and the pace for the velocity KPIs. After that only a `/milestone-close` `estimate` action changes them, with `--stage close`.

# Story points: how the AI scores an epic

Read on `/roadmap` (step 4 and `--milestone` step 2) and on `/discuss <epic>` for a roadmap epic.

## Scale
Points measure size relative to other epics, never time: 1, 2, 3, 5, 8, 13, 21. Days come from `gin milestone show` or `list`: points times `days_per_point`, rounded up. The command refuses any other value.

## Score
1. Drivers, read from the epic: volume (screens, endpoints, and tables of `Legacy:` in `/roadmap`; the user stories and their acceptance criteria of the confirmed spec in `/discuss`), `Complexity:`, the unknowns of `Risks:`, and the outside dependencies (`Depends on:` and external services).
2. Anchors: from `gin task list --label roadmap --type epic --status closed --json`, pick one or two closed epics with `points` of similar drivers and compare (`same size as <epic> = 5`). Without them, score from the drivers only.
3. Take the nearest scale value. Above 21, propose a split into epics of 21 or less instead of a score.
4. Reason: one line, business words plus the counts, for example `12 screens, 31 endpoints, high: payment gateway`.

Show `Points: <n> (<reason>)` with the derived `Estimate: <days>` per epic. The PM confirms or corrects each; a corrected score gets the reason `PM: <the PM's reason, else corrected>`. Scores and corrections do not count against `project.max_questions`.

## Write
Run `gin milestone points <epic> <n> --reason "<reason>"` for each epic whose points are missing in Beads or changed in this run. On a re-run Beads wins: a differing `Points:` line is reported, not written. An epic that keeps only a day estimate is valid input; propose a score for it.

## Re-score in /discuss
After `requirement-confirmed` is recorded for a roadmap epic, score it again from its user stories. Show the old and new points with the reason. When they differ and the PM confirms, run `gin milestone points <epic> <n> --stage discuss --reason "<reason>"`. When the command refuses because the milestone has kicked off, show the score and say the change goes through `/milestone-close`.

## Lock
Points lock when the epic's milestone kicks off: `gin milestone kickstart` stores the committed points and the pace for the velocity KPIs. After that only a `/milestone-close` `estimate` action changes them, with `--stage close`.

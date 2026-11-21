---
name: run
description: Walk the manual test cases of a capability with a tester, record each result, and file a bug bead linked to the case's epic for each failure.
---

# Manual Run

`/gin-qa:run <capability> [--change <epic>] [--all]`. Results are written by `gin-qa cases result`, bugs by `gin-qa cases bug`; never edit a case file yourself.

1. Preconditions: `gin` and `gin-qa` are on `PATH`. Otherwise stop and name what to install: `install.sh --plugin gin-qa` (or `--plugin all`) from a gin-workflow clone or through `remote-install.sh`.
2. Run `gin-qa cases due <capability> [--change <epic>] [--all] --format json` and keep its `cases` in order. None: say nothing is due, offer `--all`, and stop.
3. Ask the tester once for a run reference. The default is the `Run reference:` under `## Manual runs` in the guidelines (`gin-qa cases plan <capability> --format json` names the file under `guidelines`), filled in with today's UTC date; without one, `manual <YYYY-MM-DD>`.
4. Show one case at a time: ID and title, preconditions, test data, numbered steps, expected, its `reason` and `effective_result`, and its current `result` and `bug`. Ask for `passed`, `failed`, `blocked`, or `skip`.
   - `passed` or `blocked`: run `gin-qa cases result <TC-ID> <status> --run "<ref>"`.
   - `skip`: write nothing.
   - `failed`: ask what happened instead, the evidence references (screenshots, logs, links; none is fine), and an external tracker reference. The reference is optional unless `## Bugs` in the guidelines says `External reference: required`; then ask again until one is given and, when the line names a pattern, until the reference matches it. `cases bug` attaches image evidence and the failed-step screenshots of an e2e run. Then run `gin-qa cases bug <TC-ID> --actual "<text>" [--evidence "<ref>"]... [--external-ref "<ref>"] --run "<ref>" --format json`.
   - `cases bug` exits 2 with `no epic for <TC-ID>`, `several epics for <TC-ID>: ...`, or `no such bead`: offer the epics it lists (id and title from `gin task show`), or else those of `gin task list --type epic --json`, plus another bead id. Run `cases bug` again with `--discovered-from <bead>`. Any other exit 2 (no Beads, no `gin task`): show stderr and ask whether to go on with the next case.
   Each value is one line; ask again for an empty answer. Quote every value for the shell.
5. End with the number of passed, failed, blocked, and skipped cases, and each bug as `<TC-ID> <bug>`, marked filed (`created: true`) or kept open (`created: false`). A kept bug got the new actual result and evidence in its notes.
6. Never choose a result or file a bug on your own judgement: the tester gives every answer.
7. After the tester reviews, ask whether to save the work. Only on a yes, run `gin commit <case files> -m "<capability>: <what was written>"`, with the case files whose results changed, then report the branch and that it is not pushed; on exit 2, show the message and change nothing.

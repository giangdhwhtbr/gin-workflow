---
name: e2e
description: Write or update Playwright specs for `Type: e2e` test cases by exploring the running application step by step, run them, and check the per-step evidence — one spec per case under qa/e2e/<capability>/, traced to the case by the gin-qa CLI.
---

# E2E Specs

`/gin-qa:e2e <capability>` or `/gin-qa:e2e <TC-ID>...`, optionally `--parallel N` (default 3). All commands are `gin-qa e2e <command>`; exit 1 means findings to fix, exit 2 means wrong usage or a missing tool.

1. Preconditions: `gin-workflow` and `gin-qa` are on `PATH` and `.agent-workflow/generated/effective-config.yaml` exists; otherwise stop and name what to install or run (`install.sh --plugin gin-qa`, `/setup`). If `<e2e>/evidence.ts` is missing, run `init` and show its output; it names the Playwright install command when needed. If it exists but does not contain `ariaSnapshot`, it predates step snapshots: stop and ask the user to merge the snapshot block quoted in [explore-case.md](references/explore-case.md). The project's Playwright config must find specs under the e2e folder and set `baseURL`; ask the user for the application URL and how to start it if neither is clear.
2. `plan <capability> --format json` gives `e2e` (the folder), `guidelines` (a file), and the work: `missing`, `stale`, `orphan`. With TC-IDs, run `plan` and keep only those cases.
3. Read the guidelines file (`/gin-qa:cases` creates it). Its rules (locators, sign-in, test data) override everything below.
4. Note `git status --porcelain`. `missing` and `stale`: each case is built and checked against the running application by the procedure in [explore-case.md](references/explore-case.md), which ends with `done`, `app_defect`, or `blocked`.
   - When the platform has subagents, give each case to one subagent, at most N at a time. Send it the `plan` row, the guidelines path, and the path of `explore-case.md`; nothing else from this conversation. Otherwise work through the cases one by one yourself.
   - A failed or blocked case does not stop the others.
5. When every case has ended, compare `git status --porcelain` with step 4: only these cases' spec files may have changed. Report any other change and ask the user before reverting it.
6. `orphan`: list the specs and ask the user whether to delete or keep each one. Never delete on your own.
7. Rerun step 2 with the same scope: every case that ended `done` or `app_defect` must be out of `missing` and `stale`; fix and repeat until it is. A `blocked` case keeps its draft spec and is reported, not retried. Then `run` the specs of the `done` and `app_defect` cases in one run: that folder is the official evidence. Report the specs added and changed, the run folder, each case's outcome (an `app_defect` names the step, its error, and the screenshot and snapshot paths; a `blocked` case its reason), and any `check` findings outside the scope without fixing them. Exploration runs stay in the git-ignored evidence root.
8. Do not commit; the user reviews and commits.

Reports and other formats: `export --run <folder> --format json` joins every e2e case with its `results` (one per Playwright project) and their screenshot and snapshot paths; build them from that.

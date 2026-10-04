---
name: e2e
description: Write or update Playwright specs for `Type: e2e` test cases, run them, and check the per-step evidence — one spec per case under qa/e2e/<capability>/, traced to the case by the gin-qa CLI.
---

# E2E Specs

`/gin-qa:e2e <capability>` or `/gin-qa:e2e <TC-ID>...`. All commands are `gin-qa e2e <command>`; exit 1 means findings to fix, exit 2 means wrong usage or a missing tool.

1. Preconditions: `gin-workflow` and `gin-qa` are on `PATH` and `.agent-workflow/generated/effective-config.yaml` exists; otherwise stop and name what to install or run (`install.sh --plugin gin-qa`, `/setup`). If `<e2e>/evidence.ts` is missing, run `init` and show its output; it names the Playwright install command when needed. The project's Playwright config must find specs under the e2e folder and set `baseURL`; ask the user for the application URL and how to start it if neither is clear.
2. `plan <capability> --format json` gives `e2e` (the folder), `guidelines` (a file), and the work: `missing`, `stale`, `orphan`. With TC-IDs, run `plan` and keep only those cases.
3. Read the guidelines file (`/gin-qa:cases` creates it). Its rules (locators, sign-in, test data) override everything below.
4. `missing` and `stale`: each row has the case and its `spec` path. Write one spec per case:
   - First line `// TC: <TC-ID>@00000000`, then `import { test, expect } from '../evidence';` and one `test('<TC-ID>: <title>', async ({ page, ev }) => { … })`.
   - One `await ev.step('<n>. <step text>', async () => { … })` per case step, in order. `Preconditions` go before the first step; `Expected` items are assertions in the step that produces them.
   - Pick locators from the UI source: `getByRole` with the accessible name, then `getByLabel`/`getByPlaceholder`, then `getByText`, then `getByTestId`.
   - Assert with auto-waiting `expect(...)`; never `waitForTimeout` to wait for a state.
   - Then `pin <TC-ID>` writes the real hash. Never type a hash by hand.
5. `run <TC-ID>...` for the specs you wrote. It prints the evidence folder (`run`) and any `findings`.
   - A spec defect (locator, timing, navigation): fix and rerun, at most 3 rounds per case.
   - The application does not do what `Expected` says: do not bend the spec to pass. Report it as a suspected application defect with the step, its error, and its screenshot from `<run>/<tc-id>/`.
6. `orphan`: list the specs and ask the user whether to delete or keep each one. Never delete on your own.
7. Repeat `check` until it exits 0. Report the specs added and changed, the run folder, and each case's result.
8. Do not commit; the user reviews and commits. The evidence folder is git-ignored.

Reports and other formats: `export --run <folder> --format json` joins every e2e case with its result and screenshot paths; build them from that.

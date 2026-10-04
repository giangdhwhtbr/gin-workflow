# QA E2E Exploration (Sub-project G3) — Design

Date: 2026-10-04
Status: confirmed 2026-10-04
Depends on:
- G1 (`.planning/specs/2026-10-03-qa-cases-design.md`): the TC format.
- G2 (`.planning/specs/2026-10-04-qa-e2e-design.md`): `evidence.ts`, `gin-qa e2e`, `/gin-qa:e2e`.

## Goal

`/gin-qa:e2e` writes and repairs specs from what the running application actually shows, not only from the UI source. The evidence fixture records an ARIA snapshot and the URL after every step; the agent builds a spec step by step, reading the snapshot of the last (or failing) step to choose the next locator, and reviews the screenshots before it reports a case as done. Cases are handled in parallel by subagents where the platform has them. The output is still a G2 spec and a G2 evidence run.

## Decisions

| Topic | Decision |
|---|---|
| Purpose | Exploration serves spec writing and repair. No free exploratory testing, no proposing new TCs. |
| Browser access | Through the repository's own fixture and `gin-qa e2e run`: no MCP server, no third-party browser CLI, no new dependency. Works on every platform that can run Bash. |
| Entry point | The existing `/gin-qa:e2e` skill. No new skill, no new CLI command. |
| Parallelism | One subagent per case, at most 3 at a time (`--parallel N` changes it), when the platform supports subagents; sequential otherwise. |
| Generic | Snapshots are Playwright's ARIA YAML. No overlays, video, report formats, or language-specific rules. |

## Design

### 1. Fixture (`templates/evidence.ts`)

After each `ev.step`, whether it passed or failed, next to the screenshot:

- `NN.aria.yml`: `await page.locator('body').ariaSnapshot()`.
- The page URL (`page.url()`).

Each step in `result.json` gains two optional fields:

```json
{"n": 2, "title": "...", "status": "passed", "screenshot": "02.png",
 "snapshot": "02.aria.yml", "url": "http://127.0.0.1:4173/login", "error": null}
```

A snapshot that cannot be taken is recorded as `null` and never fails the test, as with screenshots. `locator.ariaSnapshot()` needs `@playwright/test` 1.49 or later; the guidelines template says so. A `result.json` without `snapshot`/`url` (a G2 fixture) stays valid.

Repositories that ran `init` under G2 keep their fixture (`init` never overwrites). The skill detects a fixture without `ariaSnapshot` and asks the QA engineer to merge the snapshot block, which `references/explore-case.md` quotes.

### 2. CLI (`gin-qa e2e`)

No new command.

- `run` passes `--output <run>/playwright` to `npx playwright test`, so concurrent runs never clean each other's `test-results`.
- `run` creates its folder with `mkdir` without `exist_ok` and on `FileExistsError` moves to the next `-<n>` suffix, so two runs started in the same second get different folders.
- `check --run`: a step whose `snapshot` is not null needs that file to exist and be non-empty (same finding as a screenshot).
- `export`: `snapshot` becomes a repository-relative path, as `screenshot` does.

### 3. Skill (`/gin-qa:e2e`)

`SKILL.md` keeps steps 1–3 and 6–8 of G2. Step 4 and 5 change:

- Before writing, check that `<e2e>/evidence.ts` contains `ariaSnapshot`; otherwise stop and ask for the merge (section 1).
- Each `missing` or `stale` case goes through `references/explore-case.md`:
  1. Write a draft spec with the header `// TC: <TC-ID>@00000000` and step 1 only.
  2. `gin-qa e2e run <TC-ID>`; read the last step's (or the failing step's) `NN.aria.yml` and `url` in `<run>/<tc-id>/`.
  3. Add the next step, choosing the locator from the snapshot and cross-checking it in the UI source (same locator order as G2). Repeat until every TC step is in the spec, with each `Expected` item asserted.
  4. `pin <TC-ID>`, run once more, and review the evidence: read each screenshot and confirm it shows what the step title says. A test that passes but shows the wrong screen is a spec defect.
  5. Spec defects: at most 3 repair rounds after the spec is complete. The application not doing what `Expected` says is reported as a suspected application defect with the step, error, screenshot, and snapshot; the spec is not bent to pass.
- A subagent receives one case (the `plan` row), the guidelines path, and `explore-case.md`; it writes only that case's spec file and returns `done`, `app_defect`, or `blocked` with a one-line reason and its last run folder. It never commits and never edits the fixture, guidelines, or another spec.
- After all cases: `git status` shows only the expected spec files changed; `check` until exit 0; one `run` of all specs written or changed; report that run folder (the official evidence) and each case's result. Draft run folders from exploration are left in the git-ignored evidence root.

### 4. Errors

- Fixture without `ariaSnapshot`: stop before exploring (section 3).
- Every snapshot `null`: tell the QA engineer to upgrade `@playwright/test` to 1.49 or later.
- Step 1 fails to navigate: report the `baseURL` and ask how to start the application (as G2).
- A failed or blocked subagent does not stop the other cases; it is listed as not done with its reason.
- CLI exit codes are unchanged (0 / 1 findings / 2 usage or missing tool).

## Testing

- CLI (stdlib, fixture repositories as in G2): `run` passes `--output <run>/playwright` (fake `npx` records argv); a pre-existing folder for the same second yields a `-2` folder; `check --run` reports a missing or empty recorded snapshot and accepts steps without `snapshot`; `export` makes `snapshot` repository-relative.
- Real Playwright (when `GIN_QA_PLAYWRIGHT_NODE_MODULES` is set): every step has a non-empty `NN.aria.yml` containing the `Sign in` button and the right `url`; the failing step's snapshot is recorded too.
- Packaging: `skills/e2e/references/explore-case.md` is installed with the skill on every platform; `gin-qa` reports 0.3 and manifests 0.3.0.
- Core: no change.

## Success criteria

1. On a static application with one `Type: e2e` TC, `/gin-qa:e2e` produces a spec for which `gin-qa e2e run` and `gin-qa e2e check --run` exit 0, with a snapshot and URL for every step.
2. Two `gin-qa e2e run` processes started together both leave complete evidence in separate folders.
3. A repository with a G2 fixture and G2 runs still passes `check --run` and `export`.

## Non-goals

- MCP servers or third-party browser tools.
- Free exploratory testing or proposing new TCs.
- Cleaning up draft or old evidence runs.
- Managing authentication state or test data (the project's Playwright config and guidelines own them).
- Video, overlays, report formats other than JSON.

# QA E2E Evidence (Sub-project G2) — Design

Date: 2026-10-04
Status: confirmed 2026-10-04
Depends on:
- G1 (`.planning/specs/2026-10-03-qa-cases-design.md`): the `gin-qa` plugin, the TC format, `gin-qa cases export`.
Followed by: G3 (agents that explore the application in a browser).

## Goal

A QA engineer turns the `Type: e2e` test cases of G1 into Playwright specs, runs them, and gets per-step evidence (a screenshot and a status per step, a `result.json` per TC) that a deterministic command checks and that their own skills can turn into a report. Each spec traces to the TC it implements and is flagged when that TC changes or disappears. A user who does not run `gin-qa e2e init` sees no difference.

## Decisions

| Topic | Decision |
|---|---|
| Scope | Spec generation (skill), an evidence fixture, and a CLI that plans, pins, runs, checks, and exports. |
| Fixture | One TypeScript file `evidence.ts`, copied into the repository by `gin-qa e2e init`. Depends only on `@playwright/test`. The QA engineer owns and may edit it; `gin-qa` only checks the `result.json` it writes. No npm package. |
| Spec generation | The skill reads the TC and the UI source to choose locators, writes the spec, and runs it against the running application until it passes or fails for a reason it reports. No browser exploration (G3). |
| Traceability | Each spec starts with `// TC: <TC-ID>@<hash8>`, written by the CLI (`pin`), never by the AI. |
| Generic | No overlays, banners, video handling, spreadsheet or HTML reports, or language-specific rules. JSON is the only output format. |

## Design

### 1. Layout and configuration

```
qa/
  cases/auth.md                     # G1
  e2e/
    evidence.ts                     # fixture, from `gin-qa e2e init`
    auth/tc-auth-001.spec.ts        # one spec per `Type: e2e` TC
  evidence/                         # gitignored, one folder per run
    2026-10-04T10-00-00/tc-auth-001/{result.json, 01.png, 02.png}
    2026-10-04T10-00-00/tc-auth-001/<project folder>/{...}  # per named Playwright project
```

Core accepts one more optional key, `qa.e2e` (non-empty string, default `qa/e2e`), next to `qa.cases` and `qa.guidelines`; unknown keys are still rejected. Paths are normalized (`./qa/e2e/` is `qa/e2e`) and must stay inside the repository. The evidence root is the `evidence` folder next to the `qa.e2e` folder (`qa/evidence` by default; `tests/evidence` for `qa.e2e: tests/e2e`).

A spec's path is `<qa.e2e>/<capability>/<lower-case TC-ID>.spec.ts`.

### 2. TC hash

`hash8` is the first 8 hex characters of a sha256 over the TC's title, free fields, `Preconditions`, `Steps`, and `Expected`, normalized (trailing whitespace stripped, blank lines dropped). The `REQ:`/`Source:` line, `Type`, and `Priority` are excluded, so re-pinning a REQ with `gin-qa cases pin` does not make the spec stale. `gin-qa cases export` gains a `hash8` field per TC.

### 3. Fixture `evidence.ts`

- Exports `test` (Playwright `test` extended with an `ev` fixture) and `expect`.
- `ev.step(title, fn)` wraps `test.step`; after `fn` settles (pass or throw) it saves a full-page screenshot `NN.png` (NN = step number, two digits) and records `{n, title, status, screenshot, error}`; a throw is re-raised after recording.
- On teardown it writes `result.json` into `$GIN_QA_RUN_DIR/<lower-case TC-ID>/`, or `$GIN_QA_RUN_DIR/<lower-case TC-ID>/<project folder>/` for a named Playwright project, where the project folder is the lower-case name with other characters as `-`, then `-` and the first 6 hex of sha256 of the exact name (`Desktop Chrome` → `desktop-chrome-<hex6>`), so projects never share a folder. Each attempt first removes the files (not the subfolders) of its own folder. `check --run` requires a valid `result.json` in every subfolder of a case folder and rejects case or project folders that are symlinks or resolve outside the run; a project whose test never started leaves no folder, and Playwright's exit code reports it:
  ```json
  {"tc": "TC-AUTH-001", "tc_hash8": "1a2b3c4d", "project": null, "status": "passed",
   "started": "<ISO-8601>", "finished": "<ISO-8601>",
   "steps": [{"n": 1, "title": "1. Open /login", "status": "passed", "screenshot": "01.png", "error": null}]}
  ```
  `status` is `failed` if any step failed or the test failed outside a step (the first error line is kept in a step-less `error` field). The TC-ID and hash come from the spec's `// TC:` header, which the fixture reads from the spec file (`testInfo.file`, LF or CRLF); the header is the only place they live.
- Without `GIN_QA_RUN_DIR` the fixture writes nothing, so specs also run under plain `npx playwright test`.
- Video, trace, base URL, and browsers stay in the project's own Playwright config.

### 4. CLI `gin-qa e2e`

Same conventions as `gin-qa cases`: Python stdlib, `--repository` (default cwd), `--format text|json`, exit 0 clean, 1 findings, 2 usage or environment error.

| Command | Behavior |
|---|---|
| `init` | Copies `evidence.ts` into `<qa.e2e>/` and adds the evidence root to `.gitignore`. Never overwrites an existing file. Does not install Playwright; prints the install command when `@playwright/test` is not resolvable from the repository. |
| `plan [<capability>]` | JSON work list: `missing` (e2e TC without a spec, with the TC), `stale` (spec whose `@hash8` differs from the TC's, with the TC), `orphan` (spec whose TC no longer exists or is no longer `Type: e2e`). Exit 0 even when non-empty. |
| `pin <TC-ID>...` | Rewrites the header line of each TC's spec to the current hash. Touches nothing else. Exit 1 if a TC or its spec does not exist. |
| `run [<TC-ID>... \| <capability>]` | Creates `<evidence root>/<timestamp>/`, sets `GIN_QA_RUN_DIR`, runs `npx playwright test <spec files>` (all specs when no argument), then runs `check --run` on that folder and prints the run path. Exit: Playwright's exit code if non-zero, else 1 if the check has findings, else 0. |
| `check [--run <dir>]` | Without `--run`, specs: missing or malformed header, header TC-ID not matching the file name, stale, orphan, missing. With `--run`, evidence: every spec selected in the run has a valid `result.json` (each project's, when there are several); every recorded screenshot exists inside its case folder and is non-empty; `passed` with zero steps; `tc_hash8` differs from the current TC. Findings carry `file:line` (spec) or the evidence path. |
| `export --run <dir>` | `{"run": "<dir>", "cases": [<cases export entry> + {"results": [<result.json per project, screenshot paths made repository-relative>]}]}` for every e2e TC; `results` is empty when the TC did not run. |

`run` records which specs it selected in `<run>/run.json` (`{"started", "specs": [...], "playwright_exit"}`) so `check --run` and `export` know what was expected.

Errors (exit 2, naming the command to run): `npx` or `@playwright/test` missing for `run`; `evidence.ts` missing (`gin-qa e2e init`); the run folder missing or outside the evidence root.

### 5. Skill `/gin-qa:e2e <capability | TC-ID...>`

1. Preconditions: `gin-qa` and `gin-workflow` on `PATH`, `gin-qa e2e init` done. Otherwise stop and name the command.
2. Read `qa/guidelines.md`; its e2e rules (locator conventions, sign-in, test data) override the skill's defaults.
3. `gin-qa e2e plan …`. For each `missing` or `stale` TC: read the UI source to pick locators (role, then label/placeholder, then text, then test id); write one spec with one `ev.step` per TC step and the `Expected` bullets as auto-waiting assertions (never `waitForTimeout` to await state); then `gin-qa e2e pin`.
4. `gin-qa e2e run` for those TCs. A spec defect (locator, timing) is fixed, up to 3 rounds per TC. When the application does not do what `Expected` says, the spec is not bent to pass: report it as a suspected application defect with the evidence path.
5. Rerun `plan` with the same scope until the cases handled are out of `missing` and `stale` (G3 adds `blocked` cases, which are reported instead). `orphan`: list and ask whether to delete or keep; never delete on its own.
6. Report the specs written or changed and the run path. Never commit.

### 6. Packaging

- `plugins/gin-qa/src/skills/e2e/SKILL.md`, `src/templates/evidence.ts`, `gin_qa/e2e.py` (plus CLI wiring). Plugin version 0.2, launcher version 0.2 in `install.sh`/`install.ps1`.
- Core: `qa.e2e` in the schema and `examples/config.full.yaml`. Core skills, agents, and references still contain no mention of `gin-qa`.

## Testing

- Unit (stdlib, fixture repositories as in G1): TC `hash8` ignores `REQ:`/`Type`/`Priority` and changes with steps; `plan` finds missing, stale, orphan; `pin` changes only the header line; every `check` finding type, with and without `--run`; `export` joins results and leaves `results: []` for TCs not run; `init` copies once and never overwrites; `.gitignore` updated once.
- `run` with a fake `npx` on `PATH` that writes `result.json`: environment variable, TC-ID → file mapping, `run.json`, exit-code rules; missing `npx` exits 2.
- Real Playwright smoke, skipped when `npx playwright` is unavailable: a static page served by `python3 -m http.server`, one two-step e2e TC, `run` then `check --run` exit 0, two non-empty PNGs.
- Core: `qa.e2e` accepted, unknown `qa` sub-keys still rejected.
- Packaging: the `e2e` skill and `evidence.ts` template are installed; token budget for the skill.

## Success criteria

1. On a repository with `Type: e2e` TCs and a running application, `/gin-qa:e2e <capability>` produces specs for which `gin-qa e2e run` and `gin-qa e2e check --run` exit 0.
2. Editing a TC's steps makes `plan` and `check` report exactly its spec as stale; re-pinning its REQ does not.
3. `gin-qa e2e export --run` gives JSON, screenshot paths included, from which a QA engineer's own skill can build a report.
4. A user who installs only `gin-workflow`, or uses `gin-qa` without `gin-qa e2e init`, sees no change.

## Non-goals

- Agents exploring the application in a browser (G3).
- Overlays, banners, video stitching, visual comparison.
- HTML, spreadsheet, or any report format other than JSON.
- Managing authentication state or test data.
- Cleaning up old evidence runs.

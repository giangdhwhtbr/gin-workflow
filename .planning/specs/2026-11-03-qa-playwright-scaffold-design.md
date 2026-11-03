# Playwright scaffold in e2e init

Epic: gin-workflow-qa-playwright-scaffold
Status: draft for user review.

## Goal and scope

Today `gin-qa e2e init` copies the evidence fixture (`qa/e2e/evidence.ts`) and git-ignores the evidence root, and nothing else (`plugins/gin-qa/src/scripts/gin_qa/e2e.py:125-142`). Every project then writes its own `playwright.config.ts` by hand, as gin-console did, before `gin-qa e2e run` can find a spec or reach the application. After this change `init` also leaves a runnable `playwright.config.ts` that follows Playwright practice, finds specs under the configured e2e folder, and knows the application URL, so `/gin-qa:e2e` asks for that URL at most once per repository.

In scope:
- A config template `plugins/gin-qa/src/templates/playwright.config.ts`.
- `gin-qa e2e init --base-url URL`: writes the config when the repository root has none, and hints the `e2e` npm script.
- `/gin-qa:e2e` step 1: runs `init` when the config is missing, asks the URL only then, and skips the question when the config sets `baseURL`.
- Docs, packaging, and version bump.

Out of scope: page objects, auth setup projects, API stub helpers (gin-console's `qa/e2e/support/api.ts` stays project code), writing to `package.json`, and Playwright configs outside the repository root.

Decided with the user on 2026-11-03: the config reads `E2E_BASE_URL` first and falls back to a literal URL that `init --base-url` writes (default `http://localhost:3000`); a static template with two tokens replaced by `init`, rather than a config that reads gin-workflow's effective config at run time.

## Requirements

### R1. Config template

`plugins/gin-qa/src/templates/playwright.config.ts` holds two tokens, `__E2E_DIR__` and `__BASE_URL__`, and nothing else that `init` rewrites. It sets:

- `testDir: '__E2E_DIR__'` and `fullyParallel: true`.
- `forbidOnly: !!process.env.CI` and `retries: process.env.CI ? 2 : 0`.
- `reporter`: `list`, and `junit` with `outputFile` `path.join(process.env.GIN_QA_RUN_DIR, 'junit.xml')` when `GIN_QA_RUN_DIR` is set, else `test-results/junit.xml`. `gin-qa e2e run` sets `GIN_QA_RUN_DIR` to the run folder (`e2e.py:195-197`), so a run's JUnit report lands next to its evidence; `check_run` reads only the case folders and ignores the file.
- `use`: `baseURL: process.env.E2E_BASE_URL ?? '__BASE_URL__'`, `trace: 'on-first-retry'`, `testIdAttribute: 'data-testid'`.
- `projects`: one project named `chromium` using `devices['Desktop Chrome']`. The evidence fixture already stores a named project's evidence in `<run>/<tc-id>/chromium-<hex6>/`, which `check` and `export` read.
- A commented-out `webServer` block (`command`, `url: '__BASE_URL__'`, `reuseExistingServer: !process.env.CI`) with a one-line comment on when to enable it.
- A header comment: written by `gin-qa e2e init`, the file belongs to the repository, `E2E_BASE_URL` overrides the URL.

### R2. `init` writes the config

`gin-qa e2e init [--base-url URL]`:

1. Writes `playwright.config.ts` at the repository root when no `playwright.config.{ts,js,mjs,cjs,mts,cts}` exists there, replacing `__E2E_DIR__` with `qa.e2e` (the effective e2e folder, `eff.e2e_dir`) and `__BASE_URL__` with the URL. It never overwrites or edits an existing config. Output line: `wrote playwright.config.ts (baseURL <url>)`.
2. `--base-url` defaults to `http://localhost:3000`. The value is written into a TypeScript string literal, so `init` accepts it only when `urllib.parse.urlsplit` gives scheme `http` or `https` and a non-empty host, and it contains none of `'`, `\`, `` ` ``, or a control character; otherwise `init` exits 2 with `--base-url: expected an http(s) URL, got <value>` and writes nothing.
3. When a config already exists and `--base-url` was given, the output says `playwright.config.<ext> exists; --base-url not applied`.
4. When the root `package.json` is missing or has no `scripts.e2e`, the output adds `add "e2e": "playwright test" to the package.json scripts`. An unreadable `package.json` (invalid JSON) gets the same hint.
5. The fixture copy, the `.gitignore` entry, and the Playwright install hint keep their current behaviour and order; the config step comes after the fixture copy.

`init` stays idempotent: a second run on an initialized repository prints `already initialized`, apart from the npm hint while the script is still missing.

The template is found next to `evidence.ts` by the existing `_template()` search, generalized to take a file name; a missing template exits 2 with the existing reinstall message.

### R3. `/gin-qa:e2e` asks the URL at most once

`plugins/gin-qa/src/skills/e2e/SKILL.md` step 1 becomes:

- Run `init` when `<e2e>/evidence.ts` is missing or the repository root has no Playwright config.
- When the config is missing, ask the user once for the application URL (and how to start it, for the `webServer` comment) and pass it as `--base-url`.
- When a config exists and sets `baseURL`, do not ask. Ask only when an existing config sets no `baseURL`.

The `blocked` rule in `references/explore-case.md` (step 1 cannot reach the page: name the `baseURL` and ask how to start the application) is unchanged.

### R4. Docs, packaging, version

- `docs/guides/qa.md`: the `init` bullet names the config, `--base-url`, and `E2E_BASE_URL`; the "your project provides … its Playwright config" sentence says `init` writes a starting config.
- `docs/reference/cli.md` (`## gin-qa`, line 385): one sentence that `e2e init` takes `--base-url URL` and writes `playwright.config.ts` when the root has none.
- `docs/guides/customizing-templates.md`: one sentence that the config template is copied once and then belongs to the repository.
- `tests/install_smoke_test.sh` and `tests/install_smoke_test.ps1` assert the template in `dist/claude-code/templates/` and in the installed launcher's `templates/`.
- Version bump per `docs/contributing.md` "Release" step 1: gin-qa plugin version (`plugin.meta.json`, `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`), the QA launcher version (`QA_LAUNCHER_VERSION` in `install.sh`, `$QaLauncherVersion` in `install.ps1`), `VERSION` in `gin_qa/cli.py`, and the smoke-test assertions.

## User Stories

### US-1: A runnable config from init
As a developer adding e2e specs to a project, I want `gin-qa e2e init` to write a Playwright config that already finds the specs and the application, so that I do not write one by hand before the first run.

Acceptance criteria:
- In a repository without a Playwright config, `gin-qa e2e init --base-url http://127.0.0.1:8080` writes `playwright.config.ts` whose `testDir` is the configured e2e folder and whose fallback `baseURL` is `http://127.0.0.1:8080`.
- With that config and no other, `gin-qa e2e run` on a pinned spec exits 0, `gin-qa e2e check --run <folder>` prints `ok`, and `<folder>/junit.xml` exists.
- Running `init` again leaves the config byte-for-byte unchanged.
- In a repository that has `playwright.config.js`, `init` writes no `playwright.config.ts`.

### US-2: Bad URLs are refused
As a developer, I want `init` to refuse a URL that is not a plain http(s) URL, so that a typo or a quote never produces a broken TypeScript file.

Acceptance criteria:
- `init --base-url localhost:3000`, `init --base-url "http://x/'"`, and `init --base-url ftp://x` each exit 2 with the `--base-url` message, and no config file is written.

### US-3: The npm script hint
As a developer, I want `init` to tell me the `e2e` npm script is missing, so that `npm run e2e` works the same way in every gin-qa project.

Acceptance criteria:
- With no `package.json`, or one without `scripts.e2e`, `init` prints the `add "e2e": "playwright test"` hint.
- With `scripts.e2e` present, `init` does not print it.

### US-4: The URL question is asked once
As a user of `/gin-qa:e2e`, I want the skill to ask for the application URL only when no Playwright config exists, so that later runs start without a question.

Acceptance criteria:
- `SKILL.md` step 1 runs `init` when the config is missing, asks the URL only in that case or when an existing config sets no `baseURL`, and passes it as `--base-url`.

## Errors and compatibility

- Existing repositories keep their config: `init` only writes when no `playwright.config.*` exists at the root, so gin-console and any hand-written config are untouched. Those repositories do not get `junit.xml` in their run folders unless they add the reporter themselves.
- An invalid `--base-url` exits 2 before anything is written, including the fixture and `.gitignore` (validation runs first).
- A repository that already ran `init` with an older gin-qa gets the config on the next `init`; `/gin-qa:e2e` now runs `init` when the config is missing, so this happens on its next use and asks for the URL once.
- `E2E_BASE_URL` set in the environment overrides the written URL for both `gin-qa e2e run` and plain `npx playwright test`.
- `retries` is 0 outside CI, so local exploration in `/gin-qa:e2e` sees each failure once, as today.

## Testing

- `tests/gin_qa/test_e2e_cli.py`:
  - `init --base-url` writes the config with both tokens replaced (no `__E2E_DIR__` or `__BASE_URL__` left), using a non-default `qa.e2e` folder.
  - Default URL `http://localhost:3000` when the flag is absent.
  - A second `init` leaves the config unchanged; an existing `playwright.config.js` prevents writing and, with `--base-url`, prints the "not applied" line.
  - Each US-2 URL exits 2 and writes nothing.
  - The npm hint appears without `package.json`, with `package.json` lacking `scripts.e2e`, and with invalid JSON; it is absent when `scripts.e2e` exists.
- `tests/gin_qa/test_e2e_playwright.py` (runs only with `GIN_QA_PLAYWRIGHT_NODE_MODULES`): a new test runs `init --base-url <local server>` with no hand-written config, writes and pins a passing spec, and asserts US-1's run, check, and `junit.xml` criteria. The existing tests keep their own configs.
- Install smoke tests per R4.

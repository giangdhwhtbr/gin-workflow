# Plan: Playwright scaffold in e2e init

Epic: gin-workflow-qa-playwright-scaffold
Spec: .planning/specs/2026-11-03-qa-playwright-scaffold-design.md

## Objective

`gin-qa e2e init [--base-url URL]` leaves a runnable `playwright.config.ts` at the repository root (testDir from `qa.e2e`, `baseURL` from `E2E_BASE_URL` with a written fallback, CI retries and `forbidOnly`, trace on first retry, `list` and `junit` reporters, one `chromium` project, a commented `webServer`, `testIdAttribute`), hints the `e2e` npm script, and `/gin-qa:e2e` asks for the application URL only when no config exists.

Goal (from the spec): after this change `init` also leaves a runnable `playwright.config.ts` that follows Playwright practice, finds specs under the configured e2e folder, and knows the application URL, so `/gin-qa:e2e` asks for that URL at most once per repository.

Architecture: one static template `plugins/gin-qa/src/templates/playwright.config.ts` with two tokens (`__E2E_DIR__`, `__BASE_URL__`); `gin_qa/e2e.py:init` validates the URL, replaces the tokens, and writes the file only when the root has no `playwright.config.*`. The installer already copies every file under `templates/` into each `dist/` and the launcher's `templates/` (`install.sh:388-392,573-575`), so no packaging code changes.

Tech Stack: Python 3 stdlib (`urllib.parse`, `json`) in the gin-qa CLI; TypeScript Playwright config; `unittest` tests run by `python3 -m pytest -n auto`.

### Global Constraints (verbatim from the spec)

- Out of scope: page objects, auth setup projects, API stub helpers (gin-console's `qa/e2e/support/api.ts` stays project code), writing to `package.json`, and Playwright configs outside the repository root.
- Decided with the user on 2026-11-03: the config reads `E2E_BASE_URL` first and falls back to a literal URL that `init --base-url` writes (default `http://localhost:3000`); a static template with two tokens replaced by `init`, rather than a config that reads gin-workflow's effective config at run time.
- It never overwrites or edits an existing config.
- An invalid `--base-url` exits 2 before anything is written, including the fixture and `.gitignore` (validation runs first).

## Route Rubric
- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis
- Problem statement: `init` writes only the fixture and the `.gitignore` entry (`e2e.py:125-142`); every project hand-writes its Playwright config, and `/gin-qa:e2e` step 1 asks for the URL whenever the config is unclear.
- Success criteria: the spec's US-1 to US-4 acceptance criteria; `python3 -m pytest -n auto` green; the real-Playwright test passes with `GIN_QA_PLAYWRIGHT_NODE_MODULES` set; `bash tests/install_smoke_test.sh` passes.
- Constraints: Global Constraints above; the evidence fixture's `result.json` shape and `check_run` are unchanged.
- Non-goals: page objects, auth setup projects, API stubs, editing `package.json`, nested configs.

## Approach Options
### Option 1: Static template with two tokens
- Summary: `templates/playwright.config.ts` holds `__E2E_DIR__` and `__BASE_URL__`; `init` replaces them with `str.replace`.
- Pros: the written file is plain, readable TypeScript the user owns; the template is reviewed as a file; packaging already copies `templates/`.
- Cons: the e2e folder is frozen at init time; a later `qa.e2e` change needs a manual edit.

### Option 2: Config reads gin-workflow's effective config at run time
- Summary: the config shells out to `gin-workflow state` or parses `effective-config.yaml` to find `qa.e2e`.
- Pros: follows `qa.e2e` changes automatically.
- Cons: couples a user-owned TypeScript file to gin-workflow internals; slower and harder to read; breaks when gin-workflow is not on `PATH`.

### Recommended Approach
- Selected option: Option 1.
- Rationale: decided with the user in the spec; the config belongs to the repository.

## Scope
- In scope: spec R1 (template), R2 (`init`), R3 (skill step 1), R4 (docs, smoke tests, version bump).
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 asserts the template and the CLI behaviour that Track 1 creates, so the two tracks run one after the other.
```

## Tasks

### Track 1: Config template and `init --base-url`
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-qa/src/templates/playwright.config.ts`
  - Modify `plugins/gin-qa/src/scripts/gin_qa/e2e.py:3-20` (imports `urlsplit`; constants `CONFIG`, `CONFIG_NAMES`, `DEFAULT_BASE_URL`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/e2e.py:117-142` (`_template(name)`, new `check_base_url`, `_has_e2e_script`, `init(root, eff, base_url)`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:41` (`--base-url` on `init`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:179-182` (pass `args.base_url`)
  - Test `tests/gin_qa/test_e2e_cli.py:82-92` (existing init test writes `package.json` before the idempotence check)
  - Test `tests/gin_qa/test_e2e_cli.py` (new class `TestInitConfig` after `TestInitPlanPin`, before line 124)
  - Test `tests/gin_qa/test_e2e_playwright.py` (new method in `TestPlaywrightRun` after line 142)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change to one module and its CLI with a clear spec; the URL validation at a code-generation boundary has several listed edge cases.
- **Acceptance criteria**: spec US-1, US-2, US-3; R1 and R2 as written; every test in Steps passes.
- **Estimated complexity**: medium

Interfaces produced:
- `e2e.CONFIG: str = "playwright.config.ts"`
- `e2e.CONFIG_NAMES: tuple[str, ...]` — `playwright.config.{ts,js,mjs,cjs,mts,cts}`
- `e2e.DEFAULT_BASE_URL: str = "http://localhost:3000"`
- `e2e.check_base_url(value: str) -> str` — returns `value` or raises `QaError("--base-url: expected an http(s) URL, got <value>")`
- `e2e.init(root: Path, eff: Effective, base_url: str | None = None) -> list[str]`
- CLI: `gin-qa e2e init [--base-url URL] [--repository PATH] [--format text|json]`; output lines `wrote playwright.config.ts (baseURL <url>)`, `<name> exists; --base-url not applied`, `add "e2e": "playwright test" to the package.json scripts`.

Interfaces consumed: `Effective.e2e_dir` (`reqs.py:29`), `evidence_root`, `_playwright` (`e2e.py`), `qa`, `write`, `make_repo` (`tests/gin_qa/qa_fixtures.py`).

#### Step 1.1: Failing CLI tests

In `tests/gin_qa/test_e2e_cli.py`, in `test_init_copies_the_fixture_once_and_ignores_evidence`, replace the line

```python
        write(self.root, "node_modules/@playwright/test/package.json", "{}")
```

with

```python
        write(self.root, "node_modules/@playwright/test/package.json", "{}")
        write(self.root, "package.json", '{"scripts": {"e2e": "playwright test"}}')
```

Insert this class between `TestInitPlanPin` and `TestE2eFolderConfig`:

```python
class TestInitConfig(E2eCase):
    HINT = 'add "e2e": "playwright test" to the package.json scripts'

    def test_writes_the_config_with_the_e2e_folder_and_base_url(self):
        config = self.root / ".agent-workflow/config.yaml"
        config.write_text(config.read_text() + "qa:\n  e2e: tests/e2e\n")
        result = self.e2e("init", "--base-url", "http://127.0.0.1:8080")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("wrote playwright.config.ts (baseURL http://127.0.0.1:8080)", result.stdout)
        text = (self.root / "playwright.config.ts").read_text()
        self.assertIn("testDir: 'tests/e2e'", text)
        self.assertIn("baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8080'", text)
        self.assertIn("url: 'http://127.0.0.1:8080'", text)
        self.assertNotIn("__E2E_DIR__", text)
        self.assertNotIn("__BASE_URL__", text)
        self.assertTrue((self.root / "tests/e2e/evidence.ts").is_file())

    def test_default_url_and_the_config_is_never_overwritten(self):
        self.assertEqual(0, self.e2e("init").returncode)
        config = self.root / "playwright.config.ts"
        self.assertIn("process.env.E2E_BASE_URL ?? 'http://localhost:3000'", config.read_text())
        before = config.read_bytes()
        result = self.e2e("init", "--base-url", "http://example.test")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("playwright.config.ts exists; --base-url not applied", result.stdout)
        self.assertEqual(before, config.read_bytes())
        self.assertNotIn("not applied", self.e2e("init").stdout)

    def test_an_existing_js_config_is_kept(self):
        write(self.root, "playwright.config.js", "module.exports = {};\n")
        result = self.e2e("init", "--base-url", "http://example.test")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse((self.root / "playwright.config.ts").exists())
        self.assertIn("playwright.config.js exists; --base-url not applied", result.stdout)
        self.assertEqual("module.exports = {};\n", (self.root / "playwright.config.js").read_text())

    def test_bad_base_urls_exit_2_and_write_nothing(self):
        ignore = self.root / ".gitignore"
        for value in ("localhost:3000", "http://x/'", "ftp://x", "http://", "http://x/\\", "http://x/`",
                      "http://x/\n", "http://[::1"):
            with self.subTest(value=value):
                result = self.e2e("init", "--base-url", value)
                self.assertEqual(2, result.returncode)
                self.assertIn("--base-url: expected an http(s) URL, got", result.stderr)
                self.assertFalse((self.root / "playwright.config.ts").exists())
                self.assertFalse((self.root / "qa/e2e/evidence.ts").exists())
                self.assertNotIn("/qa/evidence/", ignore.read_text() if ignore.exists() else "")

    def test_npm_script_hint(self):
        package = self.root / "package.json"
        for body, shown in ((None, True), ('{"scripts": {"test": "x"}}', True), ("{not json", True),
                            ("[]", True), ('{"scripts": {"e2e": "playwright test"}}', False)):
            with self.subTest(body=body):
                if body is None:
                    package.unlink(missing_ok=True)
                else:
                    package.write_text(body)
                result = self.e2e("init")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(shown, self.HINT in result.stdout)
```

Run: `python3 -m pytest tests/gin_qa/test_e2e_cli.py -q -k "Init"`
Expected: `TestInitConfig` tests fail (no `playwright.config.ts`, `--base-url` unrecognized → exit 2); `test_init_copies_the_fixture_once_and_ignores_evidence` passes.

#### Step 1.2: Template

Create `plugins/gin-qa/src/templates/playwright.config.ts`:

```ts
// Playwright config written by `gin-qa e2e init`. It belongs to this repository: edit it freely.
// E2E_BASE_URL overrides baseURL. Under `gin-qa e2e run` (GIN_QA_RUN_DIR set) the JUnit report goes
// to the run folder, next to the evidence.
import { defineConfig, devices } from '@playwright/test';
import * as path from 'node:path';

const runDir = process.env.GIN_QA_RUN_DIR;

export default defineConfig({
  testDir: '__E2E_DIR__',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: [
    ['list'],
    ['junit', { outputFile: runDir ? path.join(runDir, 'junit.xml') : 'test-results/junit.xml' }],
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? '__BASE_URL__',
    trace: 'on-first-retry',
    testIdAttribute: 'data-testid',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  // Uncomment to let Playwright start the application before the tests and stop it after them.
  // webServer: {
  //   command: 'npm run start',
  //   url: '__BASE_URL__',
  //   reuseExistingServer: !process.env.CI,
  // },
});
```

#### Step 1.3: `init` and the CLI flag

In `plugins/gin-qa/src/scripts/gin_qa/e2e.py`, add `from urllib.parse import urlsplit` after `from typing import Any`, and after `FIXTURE = "evidence.ts"` add:

```python
CONFIG = "playwright.config.ts"
CONFIG_NAMES = tuple(f"playwright.config.{ext}" for ext in ("ts", "js", "mjs", "cjs", "mts", "cts"))
DEFAULT_BASE_URL = "http://localhost:3000"
```

Replace `_template` and `init` (lines 117-142) with:

```python
def _template(name: str) -> Path:
    here = Path(__file__).resolve().parent
    for base in (here.parent, here.parent.parent):  # installed launcher, then plugin source
        if (base / "templates" / name).is_file():
            return base / "templates" / name
    raise QaError(f"the {name} template is missing from this gin-qa install; reinstall gin-qa")


def check_base_url(value: str) -> str:
    """The URL goes into a TypeScript string literal: only a plain http(s) URL with a host is accepted."""
    try:
        parts = urlsplit(value)
        plain = parts.scheme in ("http", "https") and bool(parts.hostname)
    except ValueError:  # e.g. an unclosed IPv6 bracket
        plain = False
    if not plain or any(char in "'\\`" or ord(char) < 32 or ord(char) == 127 for char in value):
        raise QaError(f"--base-url: expected an http(s) URL, got {value!r}")
    return value


def _has_e2e_script(root: Path) -> bool:
    try:
        scripts = json.loads((root / "package.json").read_text(encoding="utf-8")).get("scripts")
    except (OSError, ValueError, AttributeError):
        return False
    return isinstance(scripts, dict) and "e2e" in scripts


def init(root: Path, eff: Effective, base_url: str | None = None) -> list[str]:
    """Copies the fixture, ignores the evidence folder, and writes the Playwright config; never overwrites.
    Returns what it did."""
    url = check_base_url(DEFAULT_BASE_URL if base_url is None else base_url)
    done: list[str] = []
    target = root / eff.e2e_dir / FIXTURE
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_template(FIXTURE), target)
        done.append(f"wrote {eff.e2e_dir}/{FIXTURE}")
    ignore = root / ".gitignore"
    entry = f"/{evidence_root(eff)}/"
    lines = ignore.read_text(encoding="utf-8").splitlines() if ignore.is_file() else []
    if entry not in lines:
        ignore.write_text("\n".join([*lines, entry]) + "\n", encoding="utf-8")
        done.append(f"added {entry} to .gitignore")
    existing = next((name for name in CONFIG_NAMES if (root / name).exists()), None)
    if existing is None:
        text = _template(CONFIG).read_text(encoding="utf-8")
        (root / CONFIG).write_text(text.replace("__E2E_DIR__", eff.e2e_dir).replace("__BASE_URL__", url),
                                   encoding="utf-8")
        done.append(f"wrote {CONFIG} (baseURL {url})")
    elif base_url is not None:
        done.append(f"{existing} exists; --base-url not applied")
    if _playwright(root) is None:
        done.append("@playwright/test is not installed here: npm install -D @playwright/test && "
                    "npx playwright install chromium")
    if not _has_e2e_script(root):
        done.append('add "e2e": "playwright test" to the package.json scripts')
    return done
```

Note: the error message uses `{value!r}` (the spec's `got <value>`, quoted) so a newline in a bad value prints as `\n` and stays on one line; the test checks only the prefix `--base-url: expected an http(s) URL, got`. `check_base_url` runs before any write, which is what keeps the fixture and `.gitignore` untouched on a bad URL.

In `plugins/gin-qa/src/scripts/gin_qa/cli.py` line 41, replace

```python
    sub.add_parser("init", parents=[common])
```

with

```python
    sub.add_parser("init", parents=[common]).add_argument("--base-url")
```

and in `_run_e2e` replace `done = e2e.init(root, eff)` with `done = e2e.init(root, eff, args.base_url)`.

Run: `python3 -m pytest tests/gin_qa -q`
Expected: all pass (the Playwright tests skip without `GIN_QA_PLAYWRIGHT_NODE_MODULES`).

#### Step 1.4: Real-Playwright test of the generated config

In `tests/gin_qa/test_e2e_playwright.py`, add to `TestPlaywrightRun` after `test_named_projects_and_crlf_spec_keep_separate_evidence`:

```python
    def test_config_written_by_init_runs_and_leaves_a_junit_report(self):
        (self.root / "playwright.config.ts").unlink()
        result = self.e2e("init", "--base-url", self.url(""))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(f"wrote playwright.config.ts (baseURL {self.url('')})", result.stdout)
        self.write_spec("Dashboard")
        code, payload = self.run_once()
        self.assertEqual((0, []), (code, payload["findings"]))
        self.assertTrue((self.root / payload["run"] / "junit.xml").is_file())
        results = list((self.root / payload["run"] / "tc-auth-001").glob("chromium-*/result.json"))
        self.assertEqual(1, len(results))
        self.assertEqual("passed", json.loads(results[0].read_text())["status"])
```

Run: `GIN_QA_PLAYWRIGHT_NODE_MODULES=$HOME/gin-fam/gin-console/node_modules python3 -m pytest tests/gin_qa/test_e2e_playwright.py -q`
Expected: 4 passed.

#### Step 1.5: Commit

`git add plugins/gin-qa/src tests/gin_qa && git commit -m "feat(gin-qa): e2e init writes a Playwright config (gin-workflow-qa-playwright-scaffold)"`

### Track 2: Skill, docs, smoke tests, and version bump
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-qa/src/skills/e2e/SKILL.md:10` (step 1)
  - Modify `docs/guides/qa.md:44` (the `init` bullet)
  - Modify `docs/guides/qa.md:50` (the "Your project provides" sentence)
  - Modify `docs/guides/customizing-templates.md:166` (one sentence after the fixture paragraph)
  - Modify `docs/reference/cli.md:385` (one sentence on `e2e init --base-url`)
  - Modify `plugins/gin-qa/plugin.meta.json:3`, `plugins/gin-qa/src/.claude-plugin/plugin.json:3`, `plugins/gin-qa/src/.codex-plugin/plugin.json:3` (`0.5.0` → `0.6.0`)
  - Modify `install.sh:13` (`QA_LAUNCHER_VERSION="0.5"`)
  - Modify `install.ps1:19` (`$QaLauncherVersion = '0.5'`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:15` (`VERSION = "0.5"`)
  - Test `tests/install_smoke_test.sh:190,198,389,392,466,474`
  - Test `tests/install_smoke_test.ps1:72,133-134,189`
- **Provider role**: `docs`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** mechanical text and version edits with exact replacements given; no logic.
- **Acceptance criteria**: spec US-4 and R4; `bash tests/install_smoke_test.sh` passes; no `0.4` gin-qa launcher reference remains outside `old_version`/`Old`.
- **Estimated complexity**: low

Interfaces consumed: Track 1's `gin-qa e2e init --base-url` and its output line `wrote playwright.config.ts (baseURL <url>)`; the template path `templates/playwright.config.ts`.

#### Step 2.1: Smoke tests first

`tests/install_smoke_test.sh`:
- line 190: `launcher version 0.4 to` → `launcher version 0.5 to`
- after line 198 (`.../templates/evidence.ts`) add `assert_exists "plugins/gin-qa/dist/claude-code/templates/playwright.config.ts"`
- line 389: `gin-qa/0.4/templates/evidence.ts` → `gin-qa/0.5/templates/evidence.ts`, and add after it `assert_exists "$MOCK_HOME/.local/lib/gin-qa/0.5/templates/playwright.config.ts"`
- line 392: `"gin-qa 0.4"` → `"gin-qa 0.5"`
- after line 466 (`assert_exists "$QA_REPO/qa/e2e/evidence.ts"`) add `assert_contains "$QA_REPO/playwright.config.ts" "testDir: 'qa/e2e'"`
- line 474: `old_version=0.3; current_version=0.4` → `old_version=0.4; current_version=0.5`

`tests/install_smoke_test.ps1`:
- line 72: `version 0.4` → `version 0.5`
- lines 133-134: `gin-qa/0.4/` → `gin-qa/0.5/`; add after 134 `Assert-Exists (Join-Path $TestHome '.local/lib/gin-qa/0.5/templates/playwright.config.ts')`
- line 189: `Old = '0.3'; Current = '0.4'` → `Old = '0.4'; Current = '0.5'`

Run: `bash tests/install_smoke_test.sh`
Expected: fails at the `launcher version 0.5` assertion.

#### Step 2.2: Version bump

- `plugins/gin-qa/plugin.meta.json`, `plugins/gin-qa/src/.claude-plugin/plugin.json`, `plugins/gin-qa/src/.codex-plugin/plugin.json`: `"version": "0.5.0"` → `"version": "0.6.0"`.
- `install.sh:13`: `QA_LAUNCHER_VERSION="0.5"`.
- `install.ps1:19`: `$QaLauncherVersion = '0.5'`.
- `plugins/gin-qa/src/scripts/gin_qa/cli.py:15`: `VERSION = "0.5"`.

Run: `bash tests/install_smoke_test.sh`
Expected: exits 0.

#### Step 2.3: Skill step 1

In `plugins/gin-qa/src/skills/e2e/SKILL.md` line 10, replace the two sentences

> If `<e2e>/evidence.ts` is missing, run `init` and show its output; it names the Playwright install command when needed.

and

> The project's Playwright config must find specs under the e2e folder and set `baseURL`; ask the user for the application URL and how to start it if neither is clear.

with, respectively,

> If `<e2e>/evidence.ts` is missing or the repository root has no `playwright.config.*`, run `init` and show its output; it names the Playwright install command and the `e2e` npm script when needed. When the config is missing, first ask the user once for the application URL and pass it as `init --base-url <url>`; `init` writes a config that finds specs under the e2e folder and falls back to that URL when `E2E_BASE_URL` is unset.

and

> When a Playwright config exists and sets `baseURL`, do not ask for the URL. Ask for it, and for how to start the application, only when an existing config sets no `baseURL`.

Keep the `ariaSnapshot` sentence between them unchanged.

#### Step 2.4: Docs

- `docs/guides/qa.md:44` becomes: ``- `gin-qa e2e init` copies the evidence fixture `qa/e2e/evidence.ts` (yours to edit), git-ignores `qa/evidence/`, and writes `playwright.config.ts` at the repository root when there is none: specs under `qa/e2e`, `baseURL` from `E2E_BASE_URL` or the `--base-url` value (default `http://localhost:3000`), CI retries, trace on first retry, `list` and `junit` reporters (the JUnit report lands in the run folder), and one `chromium` project.``
- `docs/guides/qa.md:50` becomes: `Your project provides `@playwright/test` 1.49 or later. `init` writes a starting Playwright config once; after that the config is yours (`baseURL`, browsers, video, trace, `webServer`), and `init` never overwrites it.`
- `docs/guides/customizing-templates.md`, after line 166, add a paragraph: ``The Playwright config template is copied the same way: `gin-qa e2e init` writes `playwright.config.ts` only when the repository root has no `playwright.config.*`, and the written file is yours to edit.``
- `docs/reference/cli.md:385`, append to the paragraph: `` `gin-qa e2e init [--base-url URL]` also writes `playwright.config.ts` when the repository root has none; an invalid URL exits 2 and writes nothing.``

Run: `python3 -m pytest -n auto -q`
Expected: all pass (docs coverage tests included).

#### Step 2.5: Commit

`git add -A plugins/gin-qa install.sh install.ps1 tests docs && git commit -m "docs(gin-qa): Playwright config in e2e init; gin-qa 0.6.0 (gin-workflow-qa-playwright-scaffold)"`

## Integration
- **Branch**: `feat/qa-playwright-scaffold`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes
- [ ] `GIN_QA_PLAYWRIGHT_NODE_MODULES=$HOME/gin-fam/gin-console/node_modules python3 -m pytest tests/gin_qa/test_e2e_playwright.py` passes (4 tests, none skipped)
- [ ] `bash tests/install_smoke_test.sh` passes
- [ ] Manual: in a scratch repository, `gin-qa e2e init --base-url http://127.0.0.1:5173` then `cat playwright.config.ts` shows `testDir: 'qa/e2e'` and the URL; a second `init` prints only the npm hint.

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog (`haiku`, `sonnet`, `opus`; `low` … `max`) using the route rubric.
- The user may override `Model:` and `Effort:` before plan approval.
- Deliverable merge-holds apply only to the Parent Bead (`gin-workflow-qa-playwright-scaffold`); track beads close after tests and review pass.
- `tests/install_smoke_test.ps1` runs only on Windows; Track 2 edits it but cannot run it here.

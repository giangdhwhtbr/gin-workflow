# Plan: QA E2E Exploration (Sub-project G3)

**Goal:** `/gin-qa:e2e` writes and repairs specs from what the running application actually shows, not only from the UI source. The evidence fixture records an ARIA snapshot and the URL after every step; the agent builds a spec step by step, reading the snapshot of the last (or failing) step to choose the next locator, and reviews the screenshots before it reports a case as done. Cases are handled in parallel by subagents where the platform has them. The output is still a G2 spec and a G2 evidence run.

**Architecture:** All in the `gin-qa` plugin; core is untouched. The CLI (`gin_qa/e2e.py`) gets two run-isolation fixes (a Playwright `--output` per run, race-safe run folders) and learns the optional `snapshot` step field in `check --run` and `export`. The fixture template records `NN.aria.yml` and the URL per step. The `/gin-qa:e2e` skill moves its per-case procedure into `references/explore-case.md` (build the spec one step at a time from the snapshots, review the screenshots, return an outcome line) and dispatches it to subagents in parallel where the platform has them.

**Tech Stack:** Python 3.12 stdlib for `gin-qa`; TypeScript with `@playwright/test` ≥ 1.49 (in the user's project); `unittest`; Markdown skill and reference; bash/PowerShell installers.

**Spec:** `.planning/specs/2026-10-04-qa-explore-design.md` @ `2b4976a` (workflow id `qa-explore`, `requirement_confirmed` recorded).

## Global Constraints

Copied verbatim from the spec decisions:

| Topic | Decision |
|---|---|
| Purpose | Exploration serves spec writing and repair. No free exploratory testing, no proposing new TCs. |
| Browser access | Through the repository's own fixture and `gin-qa e2e run`: no MCP server, no third-party browser CLI, no new dependency. Works on every platform that can run Bash. |
| Entry point | The existing `/gin-qa:e2e` skill. No new skill, no new CLI command. |
| Parallelism | One subagent per case, at most 3 at a time (`--parallel N` changes it), when the platform supports subagents; sequential otherwise. |
| Generic | Snapshots are Playwright's ARIA YAML. No overlays, video, report formats, or language-specific rules. |

Repository constraints:
- Test command (repo root): `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py`. Baseline on `docs/qa-explore-spec` (`2b4976a`): `Ran 769 tests … OK`. The validated prototype, rebuilt track by track from this plan's files, ends at `Ran 771 tests … OK` with the real-Playwright tests enabled, and the install smoke test passing after every track.
- Real-Playwright tests (`tests/gin_qa/test_e2e_playwright.py`) run only with `GIN_QA_PLAYWRIGHT_NODE_MODULES=<dir>/node_modules` (`npm install @playwright/test` and `npx playwright install chromium` done there); otherwise they skip (2 skips). Track 2 and verification run them.
- Install smoke test: `bash tests/install_smoke_test.sh`. The PowerShell smoke test cannot run here (no `pwsh`); keep it consistent by reading.
- Core (`plugins/gin-workflow/src`) unchanged; it never names `gin-qa`. `gin-qa` skills ≤ 6,000 chars each, descriptions ≤ 1,000.
- Generic only: no overlays, video, report formats, language rules, or anything naming a particular project.
- Git: commit/push on `feat/qa-explore` (worktree); never commit to `master`.

## Deviations from the spec (decided while planning; each keeps the spec's intent)

1. **`screenshot` check reuses the new `_non_empty` helper**, so both file checks read the same way; the screenshot finding text is unchanged.
2. **The spec's success criterion 2 (concurrent runs)** is a unit test that starts three `gin-qa e2e run` processes at once with the fake `npx`, plus a deterministic test with the current and next second's folders already taken.
3. **The snapshot call has a 5 s timeout** so a page that never settles cannot stall a step for the default action timeout.
4. **`explore-case.md` tells the agent to ignore the unpinned-header finding** that `run` reports before `pin` (the draft header is `@00000000`).

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`: brainstorm `high_reasoning`; design `high_reasoning`; plan `standard_impl`; implement `standard_impl`; verify `standard_impl`; review `high_reasoning`; docs `cheap_simple`
- `override_rule`: Track 1 (concurrency of run folders and Playwright output) uses `high_reasoning`.

## Requirement Analysis
- Problem: `/gin-qa:e2e` picks locators from the UI source only, so specs need several blind repair rounds, and cases are handled one by one in one context.
- Success: spec §Success criteria and the Validation list below.
- Constraints: no new dependency, no MCP, no new command or skill; the fixture stays repository-owned (old fixtures keep working); output is still a G2 spec and run.
- Non-goals (spec): MCP or third-party browser tools, free exploratory testing or new TCs, cleaning runs, auth/test data management, video and report formats.

## Approach Options
### Option 1: ARIA snapshots from the repository's fixture (selected in discuss)
- Pros: no dependency; every platform with Bash; parallel-safe; snapshots double as text evidence.
- Cons: each exploration round reruns the spec from the start.
### Option 2: Playwright MCP
- Cons: per-platform MCP setup; parallel subagents share one browser; an external dependency.
### Recommended Approach
- Option 1, as confirmed.

## Scope
- In: `plugins/gin-qa/**`, `install.sh`, `install.ps1`, `README.md`, `tests/gin_qa/`, `tests/install_smoke_test.*`.
- Out: `plugins/gin-workflow/**`, schema, gates.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Three small dependent tracks (CLI, fixture, skill and packaging) over one package; sequential direct execution keeps the shared test files conflict-free.
```

## File Structure

| Path | Responsibility |
|---|---|
| `plugins/gin-qa/src/scripts/gin_qa/e2e.py` | Run isolation; snapshot checks and export |
| `plugins/gin-qa/src/templates/evidence.ts`, `plugins/gin-qa/src/templates/guidelines.md` | Per-step ARIA snapshot and URL; Playwright version note |
| `plugins/gin-qa/src/skills/e2e/SKILL.md`, `plugins/gin-qa/src/skills/e2e/references/explore-case.md` (new) | Orchestration and parallelism; per-case exploration procedure |
| `plugins/gin-qa/src/scripts/gin_qa/cli.py`, manifests, `install.sh`, `install.ps1`, `README.md` | 0.3 packaging |
| `tests/gin_qa/test_e2e_cli.py`, `tests/gin_qa/test_e2e_playwright.py`, `tests/gin_qa/test_packaging.py`, smoke tests | Tests |

## Tasks

Diff blocks are exact `git diff` output against the previous track; apply each with `git apply --recount <file>` after saving it, or edit by hand.

### Track 1: `gin-qa e2e run` output folder and race-safe run folders; snapshots in `check --run` and `export`

**Metadata:**
- Dependencies: none
- Provider role: backend
- Reasoning: high
- Model guidance: high_reasoning
- Estimated complexity: low

**Files:**
- Modify: `plugins/gin-qa/src/scripts/gin_qa/e2e.py`
- Test: `tests/gin_qa/test_e2e_cli.py`

**Interfaces:**
- Consumes: G2 `e2e.run`, `e2e.check_run`, `e2e.export`, `result.json` shape.
- Produces: `e2e.run` creates `<evidence root>/<UTC %Y-%m-%dT%H-%M-%S>` with `mkdir()` (no `exist_ok`) and on `FileExistsError` tries `-2`, `-3`, …; runs `npx playwright test <specs> --output <run>/playwright`. `e2e._non_empty(folder, name) -> bool`. `check_run`: a step whose `snapshot` is not null needs that file non-empty (`<where>: step <n> has no snapshot on disk`); steps without `snapshot`, or with `null`, are valid. `export`: `screenshot` and `snapshot` both become repository-relative paths. Fake `npx` in tests writes `01.aria.yml` and `snapshot`/`url` and ignores non-spec arguments.

- [ ] **Step 1: Failing tests.**

Apply to `tests/gin_qa/test_e2e_cli.py`:

```diff
diff --git a/tests/gin_qa/test_e2e_cli.py b/tests/gin_qa/test_e2e_cli.py
index aea892a..7231f92 100644
--- a/tests/gin_qa/test_e2e_cli.py
+++ b/tests/gin_qa/test_e2e_cli.py
@@ -2,8 +2,11 @@
 
 from __future__ import annotations
 
+from datetime import datetime, timedelta, timezone
 import json
+import os
 from pathlib import Path
+import subprocess
 import sys
 import tempfile
 import textwrap
@@ -12,7 +15,7 @@ import unittest
 sys.path.insert(0, str(Path(__file__).resolve().parent))
 sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-qa/src/scripts"))
 
-from qa_fixtures import AUTH_SPEC, case, cases_file, gin_workflow_bin, make_repo, qa, write  # noqa: E402
+from qa_fixtures import AUTH_SPEC, QA_LAUNCHER, case, cases_file, gin_workflow_bin, make_repo, qa, write  # noqa: E402
 from gin_qa.cases import hash8 as case_hash8, parse_file  # noqa: E402
 
 FAKE_NPX = textwrap.dedent('''\
@@ -22,16 +25,17 @@ FAKE_NPX = textwrap.dedent('''\
     root, run = pathlib.Path.cwd(), pathlib.Path(os.environ["GIN_QA_RUN_DIR"])
     (root / ".npx-args").write_text(json.dumps(sys.argv[1:]))
     skip = (root / ".fake-skip").read_text().split() if (root / ".fake-skip").exists() else []
-    for spec in sys.argv[3:]:
+    for spec in [arg for arg in sys.argv[3:] if arg.endswith(".spec.ts")]:
         tc, pinned = re.match(r"// TC: (\\S+)@(\\w+)", (root / spec).read_text()).groups()
         if tc in skip:
             continue
         folder = run / tc.lower()
         folder.mkdir(parents=True)
         (folder / "01.png").write_bytes(b"png")
+        (folder / "01.aria.yml").write_text("- heading Login")
         (folder / "result.json").write_text(json.dumps({{"tc": tc, "tc_hash8": pinned, "status": "passed",
             "steps": [{{"n": 1, "title": "1. Open /login", "status": "passed", "screenshot": "01.png",
-                        "error": None}}]}}))
+                        "snapshot": "01.aria.yml", "url": "http://127.0.0.1/login", "error": None}}]}}))
     exit_file = root / ".fake-exit"
     sys.exit(int(exit_file.read_text()) if exit_file.exists() else 0)
 ''').format(python=sys.executable)
@@ -166,13 +170,32 @@ class TestRunAndEvidence(E2eCase):
         payload = json.loads(result.stdout)
         self.assertEqual((0, []), (payload["playwright_exit"], payload["findings"]))
         self.assertRegex(payload["run"], r"^qa/evidence/\d{4}-\d\d-\d\dT\d\d-\d\d-\d\d$")
-        self.assertEqual(["playwright", "test", "qa/e2e/auth/tc-auth-001.spec.ts"],
+        self.assertEqual(["playwright", "test", "qa/e2e/auth/tc-auth-001.spec.ts",
+                          "--output", f"{payload['run']}/playwright"],
                          json.loads((self.root / ".npx-args").read_text()))
         record = json.loads((self.root / payload["run"] / "run.json").read_text())
         self.assertEqual((["qa/e2e/auth/tc-auth-001.spec.ts"], 0), (record["specs"], record["playwright_exit"]))
         self.assertNotEqual(payload["run"], json.loads(self.run_e2e("auth").stdout)["run"])
         self.assertEqual(0, self.e2e("check", "--run", payload["run"]).returncode)
 
+    def test_a_taken_folder_moves_to_the_next_suffix(self):
+        now = datetime.now(timezone.utc)
+        for moment in (now, now + timedelta(seconds=1)):
+            (self.root / "qa/evidence" / moment.strftime("%Y-%m-%dT%H-%M-%S")).mkdir(parents=True)
+        self.assertRegex(json.loads(self.run_e2e().stdout)["run"], r"^qa/evidence/[0-9T-]+-2$")
+
+    def test_concurrent_runs_keep_separate_complete_evidence(self):
+        env = {**os.environ, "PATH": f"{self.bin}:{self.npx}:/usr/bin:/bin"}
+        command = [sys.executable, str(QA_LAUNCHER), "e2e", "run", "--format", "json", "--repository", str(self.root)]
+        procs = [subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
+                 for _ in range(3)]
+        outputs = [proc.communicate() for proc in procs]
+        self.assertEqual([0, 0, 0], [proc.returncode for proc in procs], outputs)
+        runs = [json.loads(out)["run"] for out, _ in outputs]
+        self.assertEqual(3, len(set(runs)))
+        for folder in runs:
+            self.assertEqual(0, self.e2e("check", "--run", folder).returncode)
+
     def test_run_exit_codes(self):
         (self.root / ".fake-exit").write_text("1")
         self.assertEqual(1, self.run_e2e().returncode)
@@ -216,8 +239,15 @@ class TestRunAndEvidence(E2eCase):
                 self.assertEqual([finding], self.run_json("check", "--run", folder)["findings"])
         result_file.write_text(json.dumps(data))
         (self.root / folder / "tc-auth-001/01.png").write_bytes(b"")
-        self.assertEqual([f"{where}: step 1 has no screenshot on disk"],
+        (self.root / folder / "tc-auth-001/01.aria.yml").unlink()
+        self.assertEqual([f"{where}: step 1 has no screenshot on disk", f"{where}: step 1 has no snapshot on disk"],
                          self.run_json("check", "--run", folder)["findings"])
+        (self.root / folder / "tc-auth-001/01.png").write_bytes(b"png")
+        for step in ({"snapshot": None, "url": None}, {}):
+            with self.subTest(step=step):
+                g2_step = {key: value for key, value in data["steps"][0].items() if key not in ("snapshot", "url")}
+                result_file.write_text(json.dumps({**data, "steps": [{**g2_step, **step}]}))
+                self.assertEqual([], self.run_json("check", "--run", folder)["findings"])
         result_file.write_text("{")
         self.assertIn("result.json is not valid JSON", self.run_json("check", "--run", folder)["findings"][0])
         for bad in ("qa/cases", "qa/evidence/none"):
@@ -230,9 +260,9 @@ class TestRunAndEvidence(E2eCase):
         self.assertEqual((folder, 0), (payload["run"], payload["playwright_exit"]))
         [row] = payload["cases"]
         self.assertEqual(("TC-AUTH-001", self.tc_hash(), "qa/e2e/auth/tc-auth-001.spec.ts", "passed",
-                          f"{folder}/tc-auth-001/01.png"),
+                          f"{folder}/tc-auth-001/01.png", f"{folder}/tc-auth-001/01.aria.yml"),
                          (row["id"], row["hash8"], row["spec"], row["result"]["status"],
-                          row["result"]["steps"][0]["screenshot"]))
+                          row["result"]["steps"][0]["screenshot"], row["result"]["steps"][0]["snapshot"]))
         (self.root / folder / "tc-auth-001/result.json").unlink()
         self.assertIsNone(self.run_json("export", "--run", folder)["cases"][0]["result"])
 
```

- [ ] **Step 2:** Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/gin_qa/test_e2e_cli.py` → `FAILED (failures=3)` (no `--output` argument; no snapshot finding; `snapshot` not repository-relative). The suffix and concurrent-run tests already pass sequentially; they guard the race-safe folder creation.

- [ ] **Step 3: Implement.**

Apply to `plugins/gin-qa/src/scripts/gin_qa/e2e.py`:

```diff
diff --git a/plugins/gin-qa/src/scripts/gin_qa/e2e.py b/plugins/gin-qa/src/scripts/gin_qa/e2e.py
index c509839..94e9619 100644
--- a/plugins/gin-qa/src/scripts/gin_qa/e2e.py
+++ b/plugins/gin-qa/src/scripts/gin_qa/e2e.py
@@ -181,14 +181,19 @@ def run(root: Path, eff: Effective, targets: list[str]) -> tuple[str, int, list[
     if not specs:
         raise QaError(f"no e2e specs under {eff.e2e_dir}; write them with /gin-qa:e2e")
     stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
-    folder = f"{evidence_root(eff)}/{stamp}"
-    suffix = 2
-    while (root / folder).exists():
-        folder, suffix = f"{evidence_root(eff)}/{stamp}-{suffix}", suffix + 1
-    (root / folder).mkdir(parents=True)
+    folder, suffix = f"{evidence_root(eff)}/{stamp}", 2
+    (root / evidence_root(eff)).mkdir(parents=True, exist_ok=True)
+    while True:
+        try:
+            (root / folder).mkdir()
+            break
+        except FileExistsError:  # another run started in the same second
+            folder, suffix = f"{evidence_root(eff)}/{stamp}-{suffix}", suffix + 1
     record = {"started": datetime.now(timezone.utc).isoformat(), "specs": specs, "playwright_exit": None}
     (root / folder / "run.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
-    result = subprocess.run([npx, "playwright", "test", *specs], cwd=root, stdout=sys.stderr,
+    # Each run gets its own Playwright output folder: the shared default is wiped when a run starts.
+    result = subprocess.run([npx, "playwright", "test", *specs, "--output", f"{folder}/playwright"],
+                            cwd=root, stdout=sys.stderr,
                             env={**os.environ, "GIN_QA_RUN_DIR": str(root / folder)})
     record["playwright_exit"] = result.returncode
     (root / folder / "run.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
@@ -218,6 +223,10 @@ def _result(path: Path) -> tuple[dict[str, Any] | None, str | None]:
     return data, None
 
 
+def _non_empty(folder: Path, name: object) -> bool:
+    return isinstance(name, str) and bool(name) and (folder / name).is_file() and (folder / name).stat().st_size > 0
+
+
 def check_run(root: Path, eff: Effective, folder: str) -> list[str]:
     path, record = _run_folder(root, eff, folder)
     shown = path.relative_to(root.resolve()).as_posix()
@@ -240,11 +249,11 @@ def check_run(root: Path, eff: Effective, folder: str) -> list[str]:
         if data["status"] == "passed" and not data["steps"]:
             errors.append(f"{where}: passed without any ev.step; nothing was checked")
         for step in data["steps"]:
-            name = step.get("screenshot") if isinstance(step, dict) else None
-            shot = path / case_id.lower() / name if isinstance(name, str) and name else None
-            if shot is None or not shot.is_file() or shot.stat().st_size == 0:
-                errors.append(f"{where}: step {step.get('n') if isinstance(step, dict) else '?'} "
-                              f"has no screenshot on disk")
+            step = step if isinstance(step, dict) else {"n": "?"}
+            if not _non_empty(path / case_id.lower(), step.get("screenshot")):
+                errors.append(f"{where}: step {step.get('n')} has no screenshot on disk")
+            if step.get("snapshot") is not None and not _non_empty(path / case_id.lower(), step["snapshot"]):
+                errors.append(f"{where}: step {step.get('n')} has no snapshot on disk")
         if case_id not in cases:
             errors.append(f"{where}: {case_id} is not an e2e test case any more")
         elif data.get("tc_hash8") != tc.hash8(cases[case_id]):
@@ -261,8 +270,9 @@ def export(root: Path, eff: Effective, folder: str) -> dict[str, Any]:
         data, _ = _result(path / case.id.lower() / "result.json")
         if data is not None:
             for step in data["steps"]:
-                if isinstance(step, dict) and step.get("screenshot"):
-                    step["screenshot"] = f"{shown}/{case.id.lower()}/{step['screenshot']}"
+                for key in ("screenshot", "snapshot"):
+                    if isinstance(step, dict) and step.get(key):
+                        step[key] = f"{shown}/{case.id.lower()}/{step[key]}"
         spec = spec_path(eff, case)
         rows.append({**tc.as_dict(case), "spec": spec if (root / spec).is_file() else None, "result": data})
     return {"run": shown, "started": record.get("started"), "playwright_exit": record.get("playwright_exit"),
```

- [ ] **Step 4:** Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py` → `Ran 771 tests … OK` (2 skips without `GIN_QA_PLAYWRIGHT_NODE_MODULES`).

- [ ] **Step 5: Commit** on `feat/qa-explore`: `git add -A && git commit -m "feat(gin-qa): separate Playwright output per run, race-safe run folders, step snapshots in check and export"` (message ends with the `Co-Authored-By` line).

### Track 2: Evidence fixture records an ARIA snapshot and the URL per step

**Metadata:**
- Dependencies: Track 1
- Provider role: backend
- Reasoning: medium
- Model guidance: standard_impl
- Estimated complexity: low

**Files:**
- Modify: `plugins/gin-qa/src/templates/evidence.ts`, `plugins/gin-qa/src/templates/guidelines.md`
- Test: `tests/gin_qa/test_e2e_playwright.py`

**Interfaces:**
- Consumes: Track 1 `check_run`/`export` handling of `snapshot`.
- Produces: `plugins/gin-qa/src/templates/evidence.ts`: `StepResult` gains `snapshot: string | null` and `url: string`; after each `ev.step` (passed or failed), under `GIN_QA_RUN_DIR`, writes `NN.aria.yml` from `page.locator('body').ariaSnapshot({ timeout: 5000 })` (`null` on any error) and records `page.url()`. Guidelines template states `@playwright/test` 1.49 or later.

- [ ] **Step 1: Failing tests.**

Apply to `tests/gin_qa/test_e2e_playwright.py`:

```diff
diff --git a/tests/gin_qa/test_e2e_playwright.py b/tests/gin_qa/test_e2e_playwright.py
index 5560847..79d8a18 100644
--- a/tests/gin_qa/test_e2e_playwright.py
+++ b/tests/gin_qa/test_e2e_playwright.py
@@ -78,6 +78,9 @@ class TestPlaywrightRun(unittest.TestCase):
     def e2e(self, *args: str):
         return qa(self.root, self.bin, *args, group="e2e", path=os.environ.get("PATH", "/usr/bin:/bin"))
 
+    def url(self, page: str) -> str:
+        return f"http://127.0.0.1:{self.server.server_address[1]}{page}"
+
     def write_spec(self, heading: str) -> None:
         write(self.root, "qa/e2e/auth/tc-auth-001.spec.ts", SPEC.format(pinned="00000000", heading=heading))
         self.assertEqual(0, self.e2e("pin", "TC-AUTH-001").returncode)
@@ -96,6 +99,10 @@ class TestPlaywrightRun(unittest.TestCase):
                          (result["status"], result["error"], [s["status"] for s in result["steps"]],
                           [s["screenshot"] for s in result["steps"]]))
         self.assertTrue(all((evidence / name).stat().st_size > 1000 for name in ("01.png", "02.png")))
+        self.assertEqual((["01.aria.yml", "02.aria.yml"], [self.url("/login.html")] * 2),
+                         ([s["snapshot"] for s in result["steps"]], [s["url"] for s in result["steps"]]))
+        self.assertIn('button "Sign in"', (evidence / "01.aria.yml").read_text())
+        self.assertIn('heading "Dashboard"', (evidence / "02.aria.yml").read_text())
         self.assertEqual(0, self.e2e("check", "--run", payload["run"]).returncode)
 
     def test_failing_step_is_recorded_with_its_screenshot(self):
@@ -106,6 +113,8 @@ class TestPlaywrightRun(unittest.TestCase):
         self.assertEqual(("failed", ["passed", "failed"], "02.png"),
                          (result["status"], [s["status"] for s in result["steps"]], result["steps"][1]["screenshot"]))
         self.assertIn("expect(locator).toBeVisible()", result["steps"][1]["error"])
+        self.assertEqual("02.aria.yml", result["steps"][1]["snapshot"])
+        self.assertIn('button "Sign in"', (self.root / payload["run"] / "tc-auth-001/02.aria.yml").read_text())
         self.assertNotIn("\x1b", result["steps"][1]["error"])
 
 
```

- [ ] **Step 2:** Run `GIN_QA_PLAYWRIGHT_NODE_MODULES=<node_modules> PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/gin_qa/test_e2e_playwright.py` → `FAILED (errors=2)` (`KeyError: 'snapshot'`).

- [ ] **Step 3: Implement.**

Apply to `plugins/gin-qa/src/templates/evidence.ts`:

```diff
diff --git a/plugins/gin-qa/src/templates/evidence.ts b/plugins/gin-qa/src/templates/evidence.ts
index faef9bb..35256c5 100644
--- a/plugins/gin-qa/src/templates/evidence.ts
+++ b/plugins/gin-qa/src/templates/evidence.ts
@@ -3,7 +3,9 @@
 //
 // A spec starts with `// TC: <TC-ID>@<hash8>` (written by `gin-qa e2e pin`) and wraps each test
 // case step in `ev.step`. Under `gin-qa e2e run` (GIN_QA_RUN_DIR set) every step leaves a
-// screenshot, and the test leaves <run>/<tc-id>/result.json. Without it the fixture records nothing.
+// screenshot, an ARIA snapshot (NN.aria.yml), and the page URL, and the test leaves
+// <run>/<tc-id>/result.json. Without it the fixture records nothing. ARIA snapshots need
+// @playwright/test 1.49 or later; on older versions `snapshot` is null.
 import { test as base, expect } from '@playwright/test';
 import * as fs from 'node:fs';
 import * as path from 'node:path';
@@ -13,6 +15,8 @@ type StepResult = {
   title: string;
   status: 'passed' | 'failed';
   screenshot: string | null;
+  snapshot: string | null;
+  url: string;
   error: string | null;
 };
 
@@ -49,20 +53,30 @@ export const test = base.extend<{ ev: Evidence }>({
             failure = error;
           }
           let screenshot: string | null = null;
+          let snapshot: string | null = null;
           if (tcDir) {
-            const name = `${String(n).padStart(2, '0')}.png`;
+            const prefix = String(n).padStart(2, '0');
             try {
-              await page.screenshot({ path: path.join(tcDir, name), fullPage: true });
-              screenshot = name;
+              await page.screenshot({ path: path.join(tcDir, `${prefix}.png`), fullPage: true });
+              screenshot = `${prefix}.png`;
             } catch {
               screenshot = null;
             }
+            try {
+              const aria = await page.locator('body').ariaSnapshot({ timeout: 5000 });
+              fs.writeFileSync(path.join(tcDir, `${prefix}.aria.yml`), aria + '\n');
+              snapshot = `${prefix}.aria.yml`;
+            } catch {
+              snapshot = null;
+            }
           }
           steps.push({
             n,
             title,
             status: failure ? 'failed' : 'passed',
             screenshot,
+            snapshot,
+            url: page.url(),
             error: failure ? firstLine(failure) : null,
           });
           if (failure) throw failure;
```

Apply to `plugins/gin-qa/src/templates/guidelines.md`:

```diff
diff --git a/plugins/gin-qa/src/templates/guidelines.md b/plugins/gin-qa/src/templates/guidelines.md
index d3fcb03..b1b5b9b 100644
--- a/plugins/gin-qa/src/templates/guidelines.md
+++ b/plugins/gin-qa/src/templates/guidelines.md
@@ -10,6 +10,7 @@ Rules for writing test cases in this repository. `/gin-qa:cases` reads this file
 
 ## E2E specs (`/gin-qa:e2e`)
 
+- Playwright: `@playwright/test` 1.49 or later (the evidence fixture records ARIA snapshots).
 - Locators: prefer `getByRole` with the accessible name; use `getByTestId` only when no stable name exists.
 - Sign-in: none yet (describe how specs sign in, e.g. a `storageState` file or a sign-in step).
 - Test data: none yet (describe the users and records specs may rely on).
```

- [ ] **Step 4:** Run `GIN_QA_PLAYWRIGHT_NODE_MODULES=<node_modules> PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py` → `Ran 771 tests … OK`, no skips.

- [ ] **Step 5: Commit** on `feat/qa-explore`: `git add -A && git commit -m "feat(gin-qa): evidence fixture records an ARIA snapshot and URL per step"` (message ends with the `Co-Authored-By` line).

### Track 3: `/gin-qa:e2e` explores step by step, in parallel; gin-qa 0.3 packaging

**Metadata:**
- Dependencies: Track 2
- Provider role: backend
- Reasoning: medium
- Model guidance: standard_impl
- Estimated complexity: low

**Files:**
- Create: `plugins/gin-qa/src/skills/e2e/references/explore-case.md`
- Modify: `plugins/gin-qa/src/skills/e2e/SKILL.md`, `plugins/gin-qa/src/scripts/gin_qa/cli.py`, `plugins/gin-qa/plugin.meta.json`, `plugins/gin-qa/src/.claude-plugin/plugin.json`, `plugins/gin-qa/src/.codex-plugin/plugin.json`, `install.sh`, `install.ps1`, `README.md`
- Test: `tests/gin_qa/test_packaging.py`, `tests/install_smoke_test.sh`, `tests/install_smoke_test.ps1`

**Interfaces:**
- Consumes: Track 1–2 CLI and fixture behavior.
- Produces: `plugins/gin-qa/src/skills/e2e/SKILL.md` (`--parallel N`, default 3; fixture check for `ariaSnapshot`; per-case procedure delegated to subagents when available; `git status` scope check; one official run; links only to `references/explore-case.md`, twice). New `plugins/gin-qa/src/skills/e2e/references/explore-case.md` (spec shape, the snapshot loop, evidence review, outcome line `<TC-ID> done|app_defect|blocked <run folder> <reason>`, the snapshot block for older fixtures). `gin-qa` 0.3: `VERSION = "0.3"`, manifests `0.3.0`, `install.sh` `QA_LAUNCHER_VERSION="0.3"`, `install.ps1` `$QaLauncherVersion = '0.3'`. README paragraph. Smoke tests assert `explore-case.md` is installed and the launcher reports `gin-qa 0.3`.

- [ ] **Step 1: Failing tests.**

Apply to `tests/gin_qa/test_packaging.py`:

```diff
diff --git a/tests/gin_qa/test_packaging.py b/tests/gin_qa/test_packaging.py
index 84d62c0..deac8b2 100644
--- a/tests/gin_qa/test_packaging.py
+++ b/tests/gin_qa/test_packaging.py
@@ -30,7 +30,7 @@ class TestPackaging(unittest.TestCase):
                          {p["name"]: p["source"]["path"] for p in marketplace["plugins"]})
 
     def test_skill_budget_and_links(self):
-        expected = {"cases": ["../../templates/guidelines.md", "../../templates/cases.md"], "e2e": []}
+        expected = {"cases": ["../../templates/guidelines.md", "../../templates/cases.md"], "e2e": ["references/explore-case.md"] * 2}
         self.assertEqual(sorted(expected), sorted(p.name for p in (QA / "src/skills").iterdir()))
         self.assertLessEqual(description_chars(QA / "src"), 1_000)
         for name, want in expected.items():
```

Apply to `tests/install_smoke_test.sh`:

```diff
diff --git a/tests/install_smoke_test.sh b/tests/install_smoke_test.sh
index 737a20a..262ab0f 100755
--- a/tests/install_smoke_test.sh
+++ b/tests/install_smoke_test.sh
@@ -186,10 +186,11 @@ assert_contains "plugins/gin-workflow/dist/claude-code/skills/tech-doc/SKILL.md"
 
 assert_contains "$output_file" "Processing plugin: gin-qa"
 assert_not_contains "$output_file" "Processing plugin: gin-workflow"
-assert_contains "$output_file" "would install gin-qa launcher version 0.2 to"
+assert_contains "$output_file" "would install gin-qa launcher version 0.3 to"
 assert_exists "plugins/gin-qa/dist/claude-code/.claude-plugin/plugin.json"
 assert_exists "plugins/gin-qa/dist/claude-code/skills/cases/SKILL.md"
 assert_exists "plugins/gin-qa/dist/claude-code/skills/e2e/SKILL.md"
+assert_exists "plugins/gin-qa/dist/claude-code/skills/e2e/references/explore-case.md"
 assert_exists "plugins/gin-qa/dist/claude-code/templates/evidence.ts"
 assert_exists "plugins/gin-qa/dist/claude-code/templates/guidelines.md"
 assert_exists "plugins/gin-qa/dist/claude-code/scripts/gin_qa/cli.py"
@@ -267,10 +268,11 @@ HOME="$MOCK_HOME" ./install.sh --platform claude --plugin gin-qa >"$output_file"
 assert_not_contains "$output_file" "gin-workflow is not installed"
 assert_exists "$MOCK_HOME/.claude/skills/gin-qa/skills/cases/SKILL.md"
 assert_exists "$MOCK_HOME/.claude/skills/gin-qa/skills/e2e/SKILL.md"
-assert_exists "$MOCK_HOME/.local/lib/gin-qa/0.2/templates/evidence.ts"
+assert_exists "$MOCK_HOME/.claude/skills/gin-qa/skills/e2e/references/explore-case.md"
+assert_exists "$MOCK_HOME/.local/lib/gin-qa/0.3/templates/evidence.ts"
 assert_contains "$MOCK_HOME/.claude/settings.json" '"gin-qa@skills-dir": true'
 qa_version="$(HOME="$MOCK_HOME" "$MOCK_HOME/.local/bin/gin-qa" --version)"
-if [ "$qa_version" != "gin-qa 0.2" ]; then
+if [ "$qa_version" != "gin-qa 0.3" ]; then
   echo "Unexpected gin-qa launcher version: $qa_version" >&2
   exit 1
 fi
```

Apply to `tests/install_smoke_test.ps1`:

```diff
diff --git a/tests/install_smoke_test.ps1 b/tests/install_smoke_test.ps1
index e8175a1..20e0122 100644
--- a/tests/install_smoke_test.ps1
+++ b/tests/install_smoke_test.ps1
@@ -68,10 +68,11 @@ try {
     Assert-True (-not $dryRunOutput.Contains('gin-qa', [StringComparison]::Ordinal)) 'Default install processed gin-qa'
 
     $qaDryRun = Invoke-Installer @{ Platform = 'codex'; Plugin = 'gin-qa'; DryRun = $true }
-    Assert-Contains $qaDryRun 'would install gin-qa launcher version 0.2'
+    Assert-Contains $qaDryRun 'would install gin-qa launcher version 0.3'
     Assert-True (-not $qaDryRun.Contains('Processing plugin: gin-workflow', [StringComparison]::Ordinal)) 'gin-qa install processed gin-workflow'
     Assert-Exists (Join-Path $Root 'plugins/gin-qa/dist/codex/skills/cases/SKILL.md')
     Assert-Exists (Join-Path $Root 'plugins/gin-qa/dist/codex/skills/e2e/SKILL.md')
+    Assert-Exists (Join-Path $Root 'plugins/gin-qa/dist/codex/skills/e2e/references/explore-case.md')
 
     $project = Join-Path $TestRoot 'project'
     New-Item -ItemType Directory -Path $project | Out-Null
@@ -91,8 +92,8 @@ try {
     Invoke-Installer @{ Platform = 'claude'; Plugin = 'all'; Project = $qaProject } | Out-Null
     Assert-Exists (Join-Path $qaProject '.claude/skills/setup/SKILL.md')
     Assert-Exists (Join-Path $qaProject '.claude/skills/cases/SKILL.md')
-    Assert-Exists (Join-Path $TestHome '.local/lib/gin-qa/0.2/gin_qa/cli.py')
-    Assert-Exists (Join-Path $TestHome '.local/lib/gin-qa/0.2/templates/evidence.ts')
+    Assert-Exists (Join-Path $TestHome '.local/lib/gin-qa/0.3/gin_qa/cli.py')
+    Assert-Exists (Join-Path $TestHome '.local/lib/gin-qa/0.3/templates/evidence.ts')
     Assert-Exists (Join-Path $TestHome '.local/bin/gin-qa.cmd')
 
     $linkProject = Join-Path $TestRoot 'link-project'
```

- [ ] **Step 2:** Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/gin_qa/test_packaging.py` → `FAILED (failures=1)` (`skills/e2e/SKILL.md` has no link to `references/explore-case.md`); `bash tests/install_smoke_test.sh` fails on the missing `explore-case.md`.

- [ ] **Step 3: Implement.**

Apply to `plugins/gin-qa/src/skills/e2e/SKILL.md`:

```diff
diff --git a/plugins/gin-qa/src/skills/e2e/SKILL.md b/plugins/gin-qa/src/skills/e2e/SKILL.md
index 148eb2a..c06a8eb 100644
--- a/plugins/gin-qa/src/skills/e2e/SKILL.md
+++ b/plugins/gin-qa/src/skills/e2e/SKILL.md
@@ -1,26 +1,21 @@
 ---
 name: e2e
-description: Write or update Playwright specs for `Type: e2e` test cases, run them, and check the per-step evidence — one spec per case under qa/e2e/<capability>/, traced to the case by the gin-qa CLI.
+description: Write or update Playwright specs for `Type: e2e` test cases by exploring the running application step by step, run them, and check the per-step evidence — one spec per case under qa/e2e/<capability>/, traced to the case by the gin-qa CLI.
 ---
 
 # E2E Specs
 
-`/gin-qa:e2e <capability>` or `/gin-qa:e2e <TC-ID>...`. All commands are `gin-qa e2e <command>`; exit 1 means findings to fix, exit 2 means wrong usage or a missing tool.
+`/gin-qa:e2e <capability>` or `/gin-qa:e2e <TC-ID>...`, optionally `--parallel N` (default 3). All commands are `gin-qa e2e <command>`; exit 1 means findings to fix, exit 2 means wrong usage or a missing tool.
 
-1. Preconditions: `gin-workflow` and `gin-qa` are on `PATH` and `.agent-workflow/generated/effective-config.yaml` exists; otherwise stop and name what to install or run (`install.sh --plugin gin-qa`, `/setup`). If `<e2e>/evidence.ts` is missing, run `init` and show its output; it names the Playwright install command when needed. The project's Playwright config must find specs under the e2e folder and set `baseURL`; ask the user for the application URL and how to start it if neither is clear.
+1. Preconditions: `gin-workflow` and `gin-qa` are on `PATH` and `.agent-workflow/generated/effective-config.yaml` exists; otherwise stop and name what to install or run (`install.sh --plugin gin-qa`, `/setup`). If `<e2e>/evidence.ts` is missing, run `init` and show its output; it names the Playwright install command when needed. If it exists but does not contain `ariaSnapshot`, it predates step snapshots: stop and ask the user to merge the snapshot block quoted in [explore-case.md](references/explore-case.md). The project's Playwright config must find specs under the e2e folder and set `baseURL`; ask the user for the application URL and how to start it if neither is clear.
 2. `plan <capability> --format json` gives `e2e` (the folder), `guidelines` (a file), and the work: `missing`, `stale`, `orphan`. With TC-IDs, run `plan` and keep only those cases.
 3. Read the guidelines file (`/gin-qa:cases` creates it). Its rules (locators, sign-in, test data) override everything below.
-4. `missing` and `stale`: each row has the case and its `spec` path. Write one spec per case:
-   - First line `// TC: <TC-ID>@00000000`, then `import { test, expect } from '../evidence';` and one `test('<TC-ID>: <title>', async ({ page, ev }) => { … })`.
-   - One `await ev.step('<n>. <step text>', async () => { … })` per case step, in order. `Preconditions` go before the first step; `Expected` items are assertions in the step that produces them.
-   - Pick locators from the UI source: `getByRole` with the accessible name, then `getByLabel`/`getByPlaceholder`, then `getByText`, then `getByTestId`.
-   - Assert with auto-waiting `expect(...)`; never `waitForTimeout` to wait for a state.
-   - Then `pin <TC-ID>` writes the real hash. Never type a hash by hand.
-5. `run <TC-ID>...` for the specs you wrote. It prints the evidence folder (`run`) and any `findings`.
-   - A spec defect (locator, timing, navigation): fix and rerun, at most 3 rounds per case.
-   - The application does not do what `Expected` says: do not bend the spec to pass. Report it as a suspected application defect with the step, its error, and its screenshot from `<run>/<tc-id>/`.
+4. `missing` and `stale`: each case is built and checked against the running application by the procedure in [explore-case.md](references/explore-case.md), which ends with `done`, `app_defect`, or `blocked`.
+   - When the platform has subagents, give each case to one subagent, at most N at a time. Send it the `plan` row, the guidelines path, and the path of `explore-case.md`; nothing else from this conversation. Otherwise work through the cases one by one yourself.
+   - A failed or blocked case does not stop the others.
+5. When every case has ended: `git status` must show changes only to the spec files of these cases; undo anything else a subagent touched and report it.
 6. `orphan`: list the specs and ask the user whether to delete or keep each one. Never delete on your own.
-7. Repeat `check` until it exits 0. Report the specs added and changed, the run folder, and each case's result.
-8. Do not commit; the user reviews and commits. The evidence folder is git-ignored.
+7. Repeat `check` until it exits 0. Then `run` the specs written or changed in one run: that folder is the official evidence. Report the specs added and changed, the run folder, and each case's outcome; an `app_defect` names the step, its error, and the screenshot and snapshot paths. Exploration runs stay in the git-ignored evidence root.
+8. Do not commit; the user reviews and commits.
 
-Reports and other formats: `export --run <folder> --format json` joins every e2e case with its result and screenshot paths; build them from that.
+Reports and other formats: `export --run <folder> --format json` joins every e2e case with its result, screenshot, and snapshot paths; build them from that.
```

Create `plugins/gin-qa/src/skills/e2e/references/explore-case.md`:

````markdown
# Explore one case

Build the Playwright spec for one `Type: e2e` test case from what the running application shows. Input: the case's `plan` row (TC-ID, title, steps, expected, `spec` path) and the guidelines file. Write only the case's spec file. Never commit, and never edit the fixture, the guidelines, the test cases, or another spec. Commands are `gin-qa e2e <command>`.

## Spec shape

- First line `// TC: <TC-ID>@00000000`, then `import { test, expect } from '../evidence';` and one `test('<TC-ID>: <title>', async ({ page, ev }) => { … })`.
- One `await ev.step('<n>. <step text>', async () => { … })` per case step, in order. `Preconditions` go before the first step; `Expected` items are assertions in the step that produces them.
- Locators, in order of preference: `getByRole` with the accessible name, `getByLabel`/`getByPlaceholder`, `getByText`, `getByTestId`. The guidelines win over this list.
- Assert with auto-waiting `expect(...)`; never `waitForTimeout` to wait for a state.

## Loop

1. Write the spec with step 1 only. `run <TC-ID> --format json` prints the run folder (`run`); the case's evidence is in `<run>/<tc-id>/`. Until step 4 the run also reports the unpinned header as a finding; ignore that one.
2. Read `result.json` there. For the last step (or the failing one) read its `NN.aria.yml` (the page's ARIA tree after the step) and `url`. If step 1 cannot reach the page, stop with `blocked`: name the `baseURL` and ask how to start the application.
3. Add the next step. Take its locator from the snapshot (role and accessible name as shown there) and confirm it in the UI source. Add the assertions for the `Expected` items it produces. Run again and go back to 2 until every case step is in the spec.
4. `pin <TC-ID>` writes the real hash; never type a hash by hand. Run once more.
5. Review the evidence: read every `NN.png` and confirm it shows what its step title says. A passing test that shows the wrong screen or skips the step's action is a spec defect.
6. Spec defects (locator, timing, navigation, wrong screen): fix and rerun, at most 3 rounds after the spec is complete.

## Outcome

Return one line: `<TC-ID> done|app_defect|blocked <run folder> <reason>`.

- `done`: the last run passed and the evidence review found nothing.
- `app_defect`: the application does not do what `Expected` says. Do not bend the spec to pass; name the step, its error, and its screenshot and snapshot.
- `blocked`: anything else that stops the case (no access, 3 rounds used up, a step the UI cannot perform), with the reason.

## Fixture without snapshots

A repository whose `evidence.ts` has no `ariaSnapshot` predates step snapshots. Its owner merges this into `ev.step`, after the screenshot, and adds `snapshot: string | null; url: string;` to `StepResult` and `snapshot, url: page.url(),` to the pushed step:

```ts
let snapshot: string | null = null;
if (tcDir) {
  try {
    const aria = await page.locator('body').ariaSnapshot({ timeout: 5000 });
    fs.writeFileSync(path.join(tcDir, `${String(n).padStart(2, '0')}.aria.yml`), aria + '\n');
    snapshot = `${String(n).padStart(2, '0')}.aria.yml`;
  } catch {
    snapshot = null;
  }
}
```

`ariaSnapshot` needs `@playwright/test` 1.49 or later. If every step's `snapshot` is null, ask the user to upgrade it.
````

Apply to `plugins/gin-qa/src/scripts/gin_qa/cli.py`:

```diff
diff --git a/plugins/gin-qa/src/scripts/gin_qa/cli.py b/plugins/gin-qa/src/scripts/gin_qa/cli.py
index 61c0f93..ada0858 100644
--- a/plugins/gin-qa/src/scripts/gin_qa/cli.py
+++ b/plugins/gin-qa/src/scripts/gin_qa/cli.py
@@ -12,7 +12,7 @@ from . import cases as tc
 from . import e2e
 from .reqs import Effective, QaError, resolve, specs_reqs
 
-VERSION = "0.2"
+VERSION = "0.3"
 
 
 def _parser() -> argparse.ArgumentParser:
```

Apply to `plugins/gin-qa/plugin.meta.json`:

```diff
diff --git a/plugins/gin-qa/plugin.meta.json b/plugins/gin-qa/plugin.meta.json
index 36cacd1..81f81b0 100644
--- a/plugins/gin-qa/plugin.meta.json
+++ b/plugins/gin-qa/plugin.meta.json
@@ -1,6 +1,6 @@
 {
   "name": "gin-qa",
-  "version": "0.2.0",
+  "version": "0.3.0",
   "description": "QA add-on for gin-workflow: test cases derived from specs and Playwright specs with per-step evidence, traced and exported as JSON.",
   "author": { "name": "gin" },
   "repository": "https://github.com/giangdhwhtbr/gin-workflow"
```

Apply to `plugins/gin-qa/src/.claude-plugin/plugin.json`:

```diff
diff --git a/plugins/gin-qa/src/.claude-plugin/plugin.json b/plugins/gin-qa/src/.claude-plugin/plugin.json
index 3c54bbb..bcb62ce 100644
--- a/plugins/gin-qa/src/.claude-plugin/plugin.json
+++ b/plugins/gin-qa/src/.claude-plugin/plugin.json
@@ -1,6 +1,6 @@
 {
   "name": "gin-qa",
-  "version": "0.2.0",
+  "version": "0.3.0",
   "description": "QA add-on for gin-workflow: test cases derived from specs and Playwright specs with per-step evidence, traced and exported as JSON.",
   "author": {
     "name": "gin"
```

Apply to `plugins/gin-qa/src/.codex-plugin/plugin.json`:

```diff
diff --git a/plugins/gin-qa/src/.codex-plugin/plugin.json b/plugins/gin-qa/src/.codex-plugin/plugin.json
index 4349950..954a439 100644
--- a/plugins/gin-qa/src/.codex-plugin/plugin.json
+++ b/plugins/gin-qa/src/.codex-plugin/plugin.json
@@ -1,6 +1,6 @@
 {
   "name": "gin-qa",
-  "version": "0.2.0",
+  "version": "0.3.0",
   "description": "QA add-on for gin-workflow: test cases derived from specs and Playwright specs with per-step evidence, traced and exported as JSON.",
   "author": {
     "name": "gin"
```

Apply to `install.sh`:

```diff
diff --git a/install.sh b/install.sh
index 57326ce..2bb59d4 100755
--- a/install.sh
+++ b/install.sh
@@ -10,7 +10,7 @@ UNINSTALL=false
 DRY_RUN=false
 TARGET_PLUGIN="gin-workflow"
 LAUNCHER_VERSION="2.7"
-QA_LAUNCHER_VERSION="0.2"
+QA_LAUNCHER_VERSION="0.3"
 
 while [[ "$#" -gt 0 ]]; do
   case $1 in
```

Apply to `install.ps1`:

```diff
diff --git a/install.ps1 b/install.ps1
index 3d5a3cf..9879325 100644
--- a/install.ps1
+++ b/install.ps1
@@ -15,7 +15,7 @@ Set-StrictMode -Version Latest
 $ErrorActionPreference = 'Stop'
 
 $LauncherVersion = '2.7'
-$QaLauncherVersion = '0.2'
+$QaLauncherVersion = '0.3'
 $ScriptRoot = $PSScriptRoot
 $UserHome = $env:HOME
 if ([string]::IsNullOrWhiteSpace($UserHome)) {
```

Apply to `README.md`:

````diff
diff --git a/README.md b/README.md
index d2773d6..c4dbeb0 100644
--- a/README.md
+++ b/README.md
@@ -152,7 +152,7 @@ curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/rem
 ```
 Test cases live in `qa/cases/<capability>.md` (configurable with `qa.cases` in `.agent-workflow/config.yaml`); team rules for writing them go in `qa/guidelines.md` (`qa.guidelines`). `gin-qa cases export --format json` feeds your own report tooling.
 
-`/gin-qa:e2e <capability>` turns `Type: e2e` cases into Playwright specs under `qa/e2e/<capability>/` (`qa.e2e`) and runs them with `gin-qa e2e run`. `gin-qa e2e init` copies the evidence fixture `qa/e2e/evidence.ts` (yours to edit) and git-ignores `qa/evidence/`; each run leaves a screenshot per step and a `result.json` per case there, checked by `gin-qa e2e check --run <folder>` and exported with `gin-qa e2e export --run <folder> --format json`. The project provides `@playwright/test` and its Playwright config (`baseURL`, browsers, video, trace).
+`/gin-qa:e2e <capability>` turns `Type: e2e` cases into Playwright specs under `qa/e2e/<capability>/` (`qa.e2e`) and runs them with `gin-qa e2e run`. `gin-qa e2e init` copies the evidence fixture `qa/e2e/evidence.ts` (yours to edit) and git-ignores `qa/evidence/`; each run leaves a screenshot per step and a `result.json` per case there, checked by `gin-qa e2e check --run <folder>` and exported with `gin-qa e2e export --run <folder> --format json`. The skill builds each spec step by step against the running application, reading the ARIA snapshot (`NN.aria.yml`) and URL the fixture records after every step, and reviews the screenshots before it reports a case; on platforms with subagents it works on several cases in parallel (`--parallel N`, default 3). The project provides `@playwright/test` (1.49 or later) and its Playwright config (`baseURL`, browsers, video, trace).
 
 ---
 
````

- [ ] **Step 4:** Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py` → `Ran 771 tests … OK`; `bash tests/install_smoke_test.sh` → exit 0. The PowerShell smoke test cannot run here; keep it consistent by reading.

- [ ] **Step 5: Commit** on `feat/qa-explore`: `git add -A && git commit -m "feat(gin-qa): /gin-qa:e2e explores the running application, gin-qa 0.3"` (message ends with the `Co-Authored-By` line).

## Integration
- **Branch**: `feat/qa-explore` in worktree `.planning/worktrees/<epic>`, based on `docs/qa-explore-spec` (`2b4976a`).
- **Merge strategy**: sequential; each track is reviewed and closed before the next starts.

## Validation
- [ ] `GIN_QA_PLAYWRIGHT_NODE_MODULES=<node_modules> PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py` → `Ran 771 tests … OK` (no skips).
- [ ] `bash tests/install_smoke_test.sh` → exit 0.
- [ ] Manual, in a scratch SDD repository with a small web page, `@playwright/test` installed, a Playwright config with `baseURL`, and the worktree launchers on `PATH`: run the `explore-case.md` loop for one case (draft step 1, read `01.aria.yml`, add steps, `pin`, run) → `run` and `check --run` exit 0, every step has `NN.aria.yml` and `url`; `export --run` lists snapshot paths; a G2-shaped `result.json` (no `snapshot`) still passes `check --run`.
- [ ] Two `gin-qa e2e run` started together against the real page → two folders, both `check --run` exit 0.

## Notes
- Model guidance is planning metadata, not Beads state.
- Concrete providers and models resolve from machine-local configuration during orchestration.
- Track beads close when their tests and review pass; the parent epic stays open until the human-confirmed merge.
- After shipping, refresh installed snapshots (`install.sh --plugin all` per platform) so `gin-qa --version` reports `gin-qa 0.3`.

# Plan: Retire AI usage tracking

Epic: gin-workflow-wkwb
Spec: `.planning/specs/2026-11-21-retire-ai-usage-design.md`

## Objective

gin 3.4.0 ships without AI usage tracking: no `gin usage` command, no usage modules or price catalog, no budget check in `gin routes dispatch`, no usage steps in `execute`, `ship` and `milestone-close`, and no `report` skill. A config that still holds `usage:` validates, and `gin state` and `gin setup doctor` say it is ignored. Nothing shipped or documented describes usage tracking except the changelog. The full suite passes.

## Global Constraints

From the spec:

- The next release is 3.4.0; the ignored-key line reads `usage is ignored since gin 3.4.0; delete it from .agent-workflow/config.yaml`.
- Config schema stays 2.11: `schemas.py` keeps `usage: {budget_usd}`; no migration, no schema bump.
- `ai_usage` metadata already on beads stays; nothing writes it any more.
- gin-console is out of scope (`gin-console-5c4`); ship this epic with or after it (`gin-harness-1u3`).
- No replacement for the quality signals in gin-workflow.
- gin-qa's own `report` skill and its `gin-qa report` command are unchanged.

Added by this plan:

- Tracks run in order. Each leaves the tests it names green.
- Every stage chain stays at or under 12,000 characters (`tests/workflow_core/test_token_budget.py`); Track 1 only removes text.
- No track runs `./install.sh` against the real `HOME`, `gin setup update`, or `gin setup refresh`: the installed gin 3.3.0 and the main checkout's generated config serve other sessions. `tests/install_smoke_test.sh` uses its own temporary `HOME`.
- `install.ps1` and `tests/install_smoke_test.ps1` cannot run on this machine (no `pwsh`). They are edited to mirror the bash changes; the Windows job of `.github/workflows/test.yml` runs them before the release tag.
- Read a pytest summary line before calling a run green: `N passed`, no `failed`, no `error`.
- Line numbers are from `master` at `103dcbbe`; a later step sees them shifted by earlier ones and locates text by the quoted words.

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
- Problem statement: `gin usage collect` takes about 36 s per bead and 57 s per epic, so `execute` and `ship` wait about 10 minutes per 6-track epic, and the numbers miss the `execute` and `ship` work (`gin-workflow-u5mt`) and every `/quick` bead recorded under `default-workflow`.
- Success criteria: the spec's Testing section: `gin usage` is an unknown command, a config with `usage:` validates and warns once in `gin state` and once in `gin setup doctor`, dispatch ignores the budget, `close_guard` still finds a review ledger in a linked worktree, the sweep test passes, the install smoke test passes, and the full suite passes.
- Constraints: Global Constraints above.
- Non-goals: gin-console, existing `ai_usage` metadata, quality signals, a schema bump.

## Approach Options
### Option 1: Remove in one epic (confirmed at discuss)
- Summary: delete the code, the skill steps, the `report` skill, the docs and the tests together; keep `usage:` valid and ignored.
- Pros: skills and CLI ship together, so no release runs a skill against a removed command; one release.
- Cons: a project that set `usage.budget_usd` loses the budget stop at upgrade.

### Option 2: Deprecate in 3.4.0, remove in a later release
- Summary: `gin usage` prints a deprecation warning for one release.
- Pros: a transition for other users.
- Cons: the 10-minute cost stays one more release. Rejected at discuss.

### Recommended Approach
- Selected option: Option 1.
- Rationale: confirmed by the user on 2026-11-21; it follows the 3.3.0 removal of gin-orchestrator.

## Scope
- In scope: sections A to E of the spec.
- Out of scope: the Global Constraints' non-goals.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks 1 and 2 both edit tests/workflow_core/test_harness_packaging.py, and Track 3 sweeps what Tracks 1 and 2 leave, so each track needs the state the previous one leaves.
```

## Tasks

### Track 1: Skills stop collecting usage; the report skill and its install paths go
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/execute/SKILL.md:33-39` (delete step 3 of "Worker dispatch", renumber), `:42` (step 2 of "Complete")
  - Modify `plugins/gin-workflow/src/skills/ship/SKILL.md:34` (merge step), `:39` (close-out step)
  - Modify `plugins/gin-workflow/src/skills/milestone-close/SKILL.md:23,33,35,37,72,82` (cost and rework)
  - Delete `plugins/gin-workflow/src/skills/report/SKILL.md` (and its folder)
  - Modify `install.sh:612-620` (OpenCode rename list), `:836-853` (`remove_legacy_project_install`)
  - Modify `install.ps1:339-346` (OpenCode rename list), `:877-899` (`Remove-LegacyProjectInstall`)
  - Test `tests/workflow_core/test_token_budget.py:130-135`
  - Test `tests/workflow_core/test_skill_routing.py:253-270`
  - Test `tests/workflow_core/test_harness_packaging.py:95,140,191,243,257`
  - Test `tests/install_smoke_test.sh:150,263,283,291-298,316,414,422-452`
  - Test `tests/install_smoke_test.ps1:113,130-156,394-404`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded edits with exact text, but they span skill prose, two installers and two smoke tests that must stay mirrored.
- **Steps**:
  1. Update the pins first (they fail until step 3):
     - `test_token_budget.py:133`: delete the line `self.assertLess(text.index("usage collect"), text.index("review-ledger.py cleanup"))` and add, in the same test, `self.assertNotIn("usage collect", text)`.
     - `test_skill_routing.py:253-270`: remove the needles `"cost_per_epic"`, `"rework"` and ``"whose `parent` is not the `bead` of another entry"``; remove `"cost_per_epic", "rework",` from the `keys` tuple; add `self.assertNotIn("gin usage", text)`. Add a test to the same class:
       ```python
       def test_no_skill_collects_or_reports_ai_usage(self):
           self.assertFalse((SRC / "skills/report").exists())
           for path in sorted((SRC / "skills").rglob("*.md")):
               with self.subTest(path=path.relative_to(SRC).as_posix()):
                   text = path.read_text(encoding="utf-8")
                   self.assertNotIn("gin usage", text)
                   self.assertNotIn("over_budget", text)
       ```
     - `test_harness_packaging.py`: delete `"skills/report/SKILL.md",` (`:95`); `prefixed = {"sdd", "team"}` (`:140`); replace the `skills/report` assertion (`:191`) with `self.assertFalse((root / "skills/report").exists())`; replace the `gin-report` assertions (`:243`, `:257`) with `self.assertFalse((root / "skills/gin-report").exists())` and `self.assertIn("name: gin-learn", (root / "skills/gin-learn/SKILL.md").read_text(encoding="utf-8"))`.
  2. Run `timeout 600 python3 -m pytest tests/workflow_core/test_token_budget.py tests/workflow_core/test_skill_routing.py -q`: the new assertions fail.
  3. Skills:
     - `execute/SKILL.md`: delete step 3 of `## 3. Worker dispatch` (`After each worker result, run gin usage collect ... ask the user to raise usage.budget_usd or stop.`) and renumber steps 4–7 to 3–6. Step 2 of `## 4. Complete` becomes: ``2. Once tests and review pass, close the track bead with `gin task close <id> --reason "<evidence>"` naming the reviewer (or `self_check`), cycle count, and finding count; this unblocks dependents and needs no PR or merge.``
     - `ship/SKILL.md:34`: delete ``run `gin usage collect --bead <epic> --best-effort` and, `` so the sentence reads ``First, on the feature branch (in the worktree, or in `MAIN_ROOT` when `IS_WORKTREE=no`), with `project.review_ledger` on, run `python3 review-ledger.py cleanup --bead-id <id>` for each closed track bead ...``. `:39`: delete ``run `gin usage collect --bead <epic> --best-effort` before closing the parent bead, unless the merge already ran it; `` so step 7 starts ``7. Close out: close the remaining beads with evidence (`gin task close`); ...``.
     - `milestone-close/SKILL.md`: delete the `Cost and rework ...` bullet (`:23`), the `cost_per_epic` bullet (`:33`) and the `rework` bullet (`:35`); in the `Metrics:` template (`:72`) delete `cost_per_epic <n.nn[ partial]|n/a>; rework <n|n/a>; `; in the summary sentence (`:82`) delete `<cost> USD per epic; <rework> reworks; `; append to the comparison paragraph (`:37`): ``Compare only the metrics both lines hold; a line written before gin 3.4.0 also holds `cost_per_epic` and `rework`, which are no longer computed.``
     - `git rm -r plugins/gin-workflow/src/skills/report`.
  4. Installers:
     - `install.sh:616`: drop `report` from `for skill in learn sdd team worktrees debugging review-response parallel-agents report; do`.
     - `install.sh` `remove_legacy_project_install`: in the `opencode)` branch change `rm -rf "$root/skills/gin-workflow-report"` to `rm -rf "$root/skills/gin-workflow-report" "$root/skills/gin-report"`; after `esac` add:
       ```bash
           # gin's report skill was retired in 3.4.0; gin-qa's report skill shares the folder name and stays.
           if [ -f "$root/skills/report/SKILL.md" ] && grep -q "Report AI usage" "$root/skills/report/SKILL.md"; then
             rm -rf "$root/skills/report"
           fi
       ```
     - `install.ps1:342`: drop `'report'` from the rename list. In `Remove-LegacyProjectInstall` make the opencode list `$skills += 'gin-workflow-report', 'gin-report'` and, after the `foreach ($skill in $skills)` loop, add:
       ```powershell
               # gin's report skill was retired in 3.4.0; gin-qa's report skill shares the folder name and stays.
               $report = Join-Path $root 'skills/report/SKILL.md'
               if ((Test-Path -LiteralPath $report -PathType Leaf) -and [IO.File]::ReadAllText($report).Contains('Report AI usage')) {
                   Remove-Item -LiteralPath (Join-Path $root 'skills/report') -Recurse -Force
               }
       ```
  5. Smoke tests:
     - `install_smoke_test.sh`: `:150`, `:263`, `:283`, `:316` become `assert_not_exists` of the same `skills/report` path; `:291` becomes `assert_not_exists ".../dist/opencode/skills/gin-report"`; `:298` checks `gin-learn/SKILL.md` for `name: gin-learn`; `:414` and `:431` check `gin-learn/SKILL.md` instead of `gin-report`; `:438` checks `gin-learn` for `name: gin-learn`; before the install at `:425`, add `"$opencode_project/.opencode/skills/gin-report"` to the `mkdir -p` of stale folders and after it `assert_not_exists "$opencode_project/.opencode/skills/gin-report"`; in the reinstall block (`:447-452`) keep the two `skills/report` assertions (gin-qa's) and replace the two `gin-report` assertions with `assert_not_exists "$opencode_project/.opencode/skills/gin-report"`. Add after that block:
       ```bash
       # gin's report skill was retired in 3.4.0: a project install removes gin's stale copy and keeps gin-qa's.
       report_project="$MOCK_HOME/report-project"
       mkdir -p "$report_project/.claude/skills/report" "$report_project/.codex/skills/report"
       printf '%s\n' '---' 'name: report' 'description: Report AI usage per bead or epic' '---' > "$report_project/.claude/skills/report/SKILL.md"
       printf '%s\n' '---' 'name: report' 'description: Write an offline HTML report of the test cases' '---' > "$report_project/.codex/skills/report/SKILL.md"
       HOME="$MOCK_HOME" ./install.sh --platform claude --project "$report_project" >/dev/null
       HOME="$MOCK_HOME" ./install.sh --platform codex --project "$report_project" >/dev/null
       assert_not_exists "$report_project/.claude/skills/report"
       assert_contains "$report_project/.codex/skills/report/SKILL.md" "offline HTML report"
       ```
     - `install_smoke_test.ps1`: mirror it. `:113` and `:136` assert the `gin-report` paths do not exist; `:139` checks `gin-learn` for `name: gin-learn`; before the install at `:131` write `.claude/skills/report/SKILL.md` with `description: Report AI usage per bead or epic` and `.codex/skills/report/SKILL.md` with `description: Write an offline HTML report of the test cases`; `:149-150` become a not-exists assertion of `.opencode/skills/gin-report`; `:154` asserts `.claude/skills/report` does not exist; `:155` asserts `.codex/skills/report/SKILL.md` contains `offline HTML report`; `:394` uses `plugins/gin-workflow/src/skills/learn/SKILL.md`, `:401` checks `.opencode/skills/gin-learn/SKILL.md`, and the message reads `Linked OpenCode install renamed the source learn skill`.
  6. Run `timeout 900 python3 -m pytest tests/workflow_core/test_token_budget.py tests/workflow_core/test_skill_routing.py tests/workflow_core/test_harness_packaging.py -q`: passes. Run `timeout 900 bash tests/install_smoke_test.sh`: exits 0.
  7. Commit: `feat(skills)!: no usage steps in execute, ship and milestone-close; retire the report skill (gin-workflow-wkwb)`.
- **Acceptance criteria**: no skill under `plugins/gin-workflow/src/skills` mentions `gin usage` or `over_budget`; no harness layout ships gin's `report` or `gin-report`; a project install removes gin's stale `report` and `gin-report` and keeps gin-qa's `report`; the `Metrics:` line has no `cost_per_epic` or `rework`; the named tests and the bash smoke test pass.
- **Estimated complexity**: medium

### Track 2: Remove gin usage, the budget check and the usage modules; warn about `usage:`
- **Dependencies**: Track 1
- **Files**:
  - Delete `plugins/gin-workflow/src/scripts/workflow_core/usage.py`, `usage_cli.py`, `usage_logs.py`, `usage_attribution.py`, `usage_prices_default.yaml`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/checkout.py` (add `Worktree`, `worktrees`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/close_guard.py:72-74` (import)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/cli.py:13,194-196` (command)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/routes.py:28,134-140` (budget check)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/configuration.py:185-188` (notice)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:16,589` (state warning)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py:16-23,493-494` (doctor action)
  - Delete `tests/workflow_core/test_usage.py`, `test_usage_attribution.py`, `test_usage_cli.py`, `test_usage_logs.py`, `test_routes_budget.py`
  - Create `tests/workflow_core/test_usage_retired.py`
  - Test `tests/workflow_core/test_lifecycle_cli.py:145-156`, `tests/workflow_core/test_migrations.py:517-523`
  - Modify `tests/workflow_core/test_tasks.py:144-160`, `tests/workflow_core/test_no_verify_stage.py:21`, `tests/workflow_core/test_harness_packaging.py:96-99`
  - Test `tests/workflow_core/test_close_guard.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** deletions plus one moved function and one config notice following the `RETIRED_KEYS_NOTICE` pattern; the tests are given in full.
- **Steps**:
  1. Create `tests/workflow_core/test_usage_retired.py`:
     ```python
     """AI usage tracking was retired in gin 3.4.0: no command, no modules, and dispatch ignores `usage.budget_usd`."""

     from __future__ import annotations

     import contextlib
     import importlib.util
     import io
     import json
     import os
     from pathlib import Path
     import sys
     import tempfile
     import unittest
     from unittest import mock

     sys.path.insert(0, str(Path(__file__).resolve().parent))
     sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"))

     from team_fixtures import fake_cli, path_with, write  # noqa: E402
     from workflow_core import cli, routes  # noqa: E402
     from workflow_core.setup_service import refresh  # noqa: E402

     CONFIG = "schema_version: '2.8'\nproviders:\n  task_tracking: beads\nusage:\n  budget_usd: 1\n"
     ROUTE = {"provider": "claude", "selection_mode": "explicit", "model": "sonnet", "effort": "medium"}
     MANIFEST = json.dumps({"workflow_id": "ep1", "tracks": {"t1": {"resolved": ROUTE}}})


     class UsageRetiredTests(unittest.TestCase):
         def test_gin_usage_is_an_unknown_command(self):
             err = io.StringIO()
             with contextlib.redirect_stderr(err):
                 self.assertEqual(2, cli.main(["usage", "collect", "--bead", "x"]))
             self.assertIn("usage: gin {", err.getvalue())
             self.assertNotIn("usage", cli.TOP_COMMANDS)

         def test_the_usage_modules_are_gone(self):
             for name in ("usage", "usage_cli", "usage_logs", "usage_attribution"):
                 with self.subTest(module=name):
                     self.assertIsNone(importlib.util.find_spec(f"workflow_core.{name}"))

         def test_dispatch_ignores_the_budget_and_never_calls_bd(self):
             with tempfile.TemporaryDirectory() as tmp:
                 base = Path(os.path.realpath(tmp))
                 root, bin_dir = base / "repo", base / "bin"
                 write(root, ".agent-workflow/runtime/assignments/ep1.yaml", MANIFEST)
                 with mock.patch.dict(os.environ, path_with(bin_dir)):
                     write(root, ".agent-workflow/config.yaml", CONFIG)
                     refresh(root)
                     (root / ".agent-workflow/executables.local.yaml").unlink()
                     fake_cli(bin_dir, "bd", [{"argv": ["show", "ep1"], "stdout": [
                         {"id": "ep1", "issue_type": "epic",
                          "metadata": {"ai_usage": json.dumps({"cost": 5, "unpriced": []})}}]}])
                     out = io.StringIO()
                     with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                         code = routes.main(["dispatch", "--workflow-id", "ep1", "--task-id", "t1",
                                             "--repository", str(root), "--json"])
                 self.assertEqual((0, "sonnet"), (code, json.loads(out.getvalue())["model"]))
                 self.assertFalse((bin_dir / "calls.log").exists())
     ```
     In `test_lifecycle_cli.py`, next to `test_state_warns_about_retired_keys_on_an_older_schema`, add:
     ```python
     def test_state_says_usage_is_ignored(self):
         import io
         from unittest.mock import patch

         from workflow_core.configuration import USAGE_IGNORED_NOTICE

         config = self.workflow_dir / "config.yaml"
         config.write_text(config.read_text(encoding="utf-8") + "usage:\n  budget_usd: 5\n", encoding="utf-8")
         self.assertEqual(1, self._state_json()["warnings"].count(USAGE_IGNORED_NOTICE))
         config.write_text(config.read_text(encoding="utf-8").replace("usage:\n  budget_usd: 5\n", ""), encoding="utf-8")
         self.assertNotIn(USAGE_IGNORED_NOTICE, self._state_json()["warnings"])
     ```
     (`setUp` writes `config.yaml` as `schema_version: '2.3'`.) In `test_migrations.py`, next to `test_doctor_reports_retired_keys_on_an_older_schema`, add:
     ```python
     def test_doctor_says_usage_is_ignored(self):
         from workflow_core.configuration import USAGE_IGNORED_NOTICE

         current = migrate_config(V210, "2.11")
         with tempfile.TemporaryDirectory() as directory:
             repository, _ = _write_repository(directory, {**current, "usage": {"budget_usd": 5}})
             self.assertEqual(1, setup_service.doctor(repository)["actions"].count(USAGE_IGNORED_NOTICE))
         with tempfile.TemporaryDirectory() as directory:
             repository, _ = _write_repository(directory, current)
             self.assertNotIn(USAGE_IGNORED_NOTICE, setup_service.doctor(repository)["actions"])
     ```
  2. Run `timeout 600 python3 -m pytest tests/workflow_core/test_usage_retired.py tests/workflow_core/test_lifecycle_cli.py tests/workflow_core/test_migrations.py -q`: the new tests fail.
  3. Code:
     - `checkout.py`: add `from dataclasses import dataclass` and `import os`; move `Worktree` and `worktrees()` from `usage_attribution.py` unchanged, except that `inside(path, base)` becomes a private helper in `checkout.py`:
       ```python
       def _inside(path: Path, base: Path) -> bool:
           try:
               path.relative_to(base)
           except ValueError:
               return False
           return True
       ```
       (`worktrees()` already passes two `os.path.realpath` paths.)
     - `close_guard.py:72-74`: `from .checkout import main_checkout, worktrees`; drop the `usage_attribution` import.
     - `cli.py:13`: remove `"usage", ` from `TOP_COMMANDS`; delete the `if argv[0] == "usage":` branch (`:194-196`).
     - `routes.py:28`: `from . import workspace`; delete the `try: stop = usage.over_budget(...)` block and the `if stop is not None: return stop, 3` lines (`:134-140`). Keep `import sys` (other uses remain).
     - `configuration.py`, after `RETIRED_KEYS_NOTICE`: `USAGE_IGNORED_NOTICE = "usage is ignored since gin 3.4.0; delete it from .agent-workflow/config.yaml"`.
     - `lifecycle_cli.py:16`: import `USAGE_IGNORED_NOTICE`; in `warnings` (`:589`) add `(USAGE_IGNORED_NOTICE if "usage" in config.to_dict() else None),` right after the `RETIRED_KEYS_NOTICE` entry.
     - `setup_service.py`: import `USAGE_IGNORED_NOTICE`; after `if retired_keys(effective_cfg): backend_actions.append(RETIRED_KEYS_NOTICE)` add `if "usage" in effective_cfg: backend_actions.append(USAGE_IGNORED_NOTICE)`.
     - `git rm` the five source files and the five test files listed above.
     - `test_tasks.py:144-160`: drop `usage` from both `from workflow_core import specs, usage` imports and delete the two `usage._bd` assertions; rename `test_specs_and_usage_follow_the_markdown_backend` to `test_specs_follow_the_markdown_backend`.
     - `test_no_verify_stage.py:21`: delete the `usage_attribution.py` entry.
     - `test_harness_packaging.py:96-99`: delete the four `scripts/workflow_core/usage*.py` entries.
  4. Run `grep -rnE 'usage_attribution|usage_logs|usage_cli|workflow_core import .*\busage\b|from \.usage|import usage' plugins/gin-workflow/src tests`: no output.
  5. Run `timeout 600 python3 -m pytest tests/workflow_core/test_usage_retired.py tests/workflow_core/test_lifecycle_cli.py tests/workflow_core/test_migrations.py tests/workflow_core/test_close_guard.py tests/workflow_core/test_tasks.py tests/workflow_core/test_no_verify_stage.py tests/workflow_core/test_harness_packaging.py tests/workflow_core/test_routes_cli.py -q`: passes. Then `timeout 900 python3 -m pytest -n auto -q`: passes.
  6. Commit: `feat(cli)!: remove gin usage, the price catalog and the dispatch budget; usage: is ignored (gin-workflow-wkwb)`.
- **Acceptance criteria**: `gin usage` exits 2 as an unknown command; the four modules and the price catalog are gone; dispatch never reads `bd` for a budget; a config with `usage:` validates and gets the ignored-key line once in `gin state` and once in `gin setup doctor`; `close_guard` finds a ledger in a linked worktree; the full suite passes.
- **Estimated complexity**: medium

### Track 3: Docs, changelog, sweep test and version 3.4.0
- **Dependencies**: Track 2
- **Files**:
  - Delete `docs/guides/usage-report.md`, `docs/guides/usage-report.vi.md`
  - Modify `mkdocs.yml:83,126` (nav)
  - Modify `docs/roles.md:20,47`, `docs/roles.vi.md:20,47` (PM row and reading list)
  - Modify `docs/reference/cli.md:5,321-323,427-436`
  - Modify `docs/reference/config.md:15,113-115,205-` (`usage` and `usage-prices.yaml`)
  - Modify `docs/reference/skills.md:3,25,53,256-262`, `docs/reference/skills.vi.md:3,25,53,256-262`
  - Modify `docs/guides/workspace.md:84`, `docs/guides/workspace.vi.md:84`
  - Modify `docs/starters/brownfield.md:523-526`, `docs/starters/brownfield.vi.md:523-526`
  - Modify `docs/contributing.md:38`
  - Modify `docs/concepts/lifecycle.md:14,61,78-79`
  - Modify `docs/concepts/state-model.md:13,82`
  - Modify `docs/concepts/architecture.md:51,75,101,115,160-171`
  - Modify `docs/guides/ai-strategy.md:57`, `docs/guides/ai-strategy.vi.md:57`
  - Modify `docs/guides/qa.md:107`, `docs/guides/qa.vi.md:107`
  - Modify `README.md:16,64,88,99`
  - Modify `docs/changelog.md` (new 3.4.0 section)
  - Create `tests/workflow_core/test_retired_usage_sweep.py`
  - Modify the version locations `scripts/bump_version.py` writes
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** documentation removal across 18 pages and one Mermaid diagram; the surrounding text must still read as one piece, which needs more judgement than the weakest model gives.
- **Steps**:
  1. Create `tests/workflow_core/test_retired_usage_sweep.py`:
     ```python
     """AI usage tracking was retired in gin 3.4.0: nothing shipped or documented describes it."""

     from pathlib import Path
     import re
     import unittest

     ROOT = Path(__file__).resolve().parents[2]
     ROOTS = ("plugins", "scripts", ".claude-plugin", "docs", "README.md", "AGENTS.md", "mkdocs.yml",
              "install.sh", "install.ps1")
     # The changelog keeps the history; schemas.py keeps `usage: {budget_usd}` valid and ignored.
     ALLOWED = {"docs/changelog.md", "plugins/gin-workflow/src/scripts/workflow_core/schemas.py"}
     PATTERN = re.compile(r"(?<![\w-])gin usage|ai_usage|budget_usd|over_budget|usage-prices|usage_prices|usage-report"
                          r"|usage_cli|usage_logs|usage_attribution|/gin:report|@gin-report")
     SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".toml", ".sh", ".ps1", ".txt", ".html", ""}


     def scanned():
         for name in ROOTS:
             root = ROOT / name
             for path in ([root] if root.is_file() else sorted(root.rglob("*"))):
                 rel = path.relative_to(ROOT).as_posix()
                 if (path.is_file() and path.suffix in SUFFIXES and rel not in ALLOWED
                         and not {"dist", "__pycache__", "fixtures"} & set(path.parts)):
                     yield rel, path.read_text(encoding="utf-8", errors="replace")


     class RetiredUsageSweepTests(unittest.TestCase):
         def test_nothing_describes_ai_usage_tracking(self):
             for rel, text in scanned():
                 with self.subTest(file=rel):
                     for number, line in enumerate(text.splitlines(), 1):
                         self.assertIsNone(PATTERN.search(line), f"{rel}:{number}: {line.strip()}")
     ```
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_retired_usage_sweep.py -q`: fails and lists the doc lines below.
  3. Docs, removing usage tracking so each page still reads as one piece:
     - `git rm docs/guides/usage-report.md docs/guides/usage-report.vi.md`; delete the `AI usage report` nav entry (`mkdocs.yml:126`) and its translation (`:83`).
     - `roles.md` and `roles.vi.md`: `:20` drops `` `/gin:report`, `` from the PM row; `:47` deletes item 3 of the PM list and renumbers item 4 to 3.
     - `workspace.md:84` and `workspace.vi.md:84`: the row keeps only `` `/gin:progress` ``.
     - `starters/brownfield.md` and `.vi.md` (`:523-526`): delete the `text` block that starts with `/gin:report --milestone <id>`.
     - `contributing.md:38`: drop `, and `report`` from the renamed-skill list (it ends `` `review-response`, and `parallel-agents` ``) and change the example to `` (for example `gin-learn`) ``.
     - `cli.md`: `:5` ends `... rules, specs, and team mode.`; in `routes dispatch` (`:321-323`) delete any budget sentence and `; 3 the epic is over budget (`dispatch`)` from the exit codes; delete the whole `## gin usage` section (`:427-436`).
     - `config.md`: delete the `usage-prices.yaml` row (`:15`) and the `## usage-prices.yaml` section (`:205` to the next `##`); the `### usage` section (`:113-115`) becomes: ```usage:` is ignored since gin 3.4.0; delete it. gin no longer tracks AI usage.``
     - `skills.md` and `skills.vi.md`: in the OpenCode note (`:3`) drop `` and `report` is `@gin-report` `` (vi: `` và `report` là `@gin-report` ``), keeping "the other six generic skills"; delete the gin `report` row (`:25`, not gin-qa's at `:71`) and the gin `report` example (`:256-262`, from `` `report`: `` to the end of its code block); in the `milestone-close` row (`:53`) delete the cost item and the `cost per epic, rework` metrics.
     - `lifecycle.md`: `:14` drops `collects usage, `; `:61` drops the usage-tracking clause and the sentence about cost; `:78-79` drop the two `gin usage collect` sentences and the budget sentence, keeping the close step.
     - `state-model.md`: delete the `ai_usage` row (`:13`) and the paragraph at `:82`.
     - `architecture.md`: `:51` drops `, and usage` (the list ends `... specs, and team mode`); `:75` drops `usage collect, `; delete participant `U as gin usage` (`:101`) and the arrow `A->>U` (`:115`); delete the usage flow diagram and its paragraph (`:160-171`, from the heading or sentence that introduces `usage_logs` to the `execute and ship run usage collect` paragraph).
     - `ai-strategy.md:57` and `ai-strategy.vi.md:57`: delete the `usage.budget_usd` bullet.
     - `qa.md:107` and `qa.vi.md:107`: delete the sentence that starts with `gin usage collect` (vi: the matching sentence).
     - `README.md`: `:16` drops the `usage report` link; `:64` says "Seven generic skills", drops `` `@gin-report` ``, and ends the sentence `so generic names do not shadow OpenCode's built-ins.`; `:88` drops ``/gin:report` shows AI cost and rework; ``; `:99` deletes the `report` row.
  4. `docs/changelog.md`: add above `## [3.3.0]`:
     ```markdown
     ## [3.4.0] - <today, YYYY-MM-DD>

     gin no longer tracks AI usage. Collecting it took about a minute per epic at every track and at ship, and the figures missed most of the work, so the `gin usage` command, the price catalog, the per-epic budget, and the `report` skill are removed.

     ### Upgrade notes

     - `gin usage collect` and `gin usage report` are gone; `execute`, `ship`, and `milestone-close` no longer run them. `ai_usage` already stored on beads stays, and nothing writes it any more.
     - `usage.budget_usd` is ignored, and `gin routes dispatch` no longer exits 3. `gin state` and `gin setup doctor` say so until you delete `usage:` from `.agent-workflow/config.yaml`; no `gin setup update` is needed.
     - `.agent-workflow/usage-prices.yaml` is no longer read; delete it.
     - The `report` skill (`/gin:report`, OpenCode `gin-report`) is removed; a project install removes gin's copy and keeps gin-qa's `report` skill.
     - `milestone-close` no longer computes `cost_per_epic` and `rework`.
     ```
  5. Run `timeout 300 python3 -m pytest tests/workflow_core/test_retired_usage_sweep.py -q`: passes; if it names a line, remove the mention there. Run `gin docs check` on the changed pages: `ok`.
  6. Run `python3 scripts/bump_version.py 3.4.0`; it prints the files it changed. Run `timeout 300 python3 -m pytest tests/test_bump_version.py tests/test_version_pins.py tests/test_release_notes.py tests/workflow_core/test_version_pin.py -q`: passes.
  7. Commit: `docs: AI usage tracking is retired; 3.4.0 changelog; sweep test (gin-workflow-wkwb)` and `chore(release): 3.4.0 (gin-workflow-wkwb)`.
- **Acceptance criteria**: the sweep passes; `gin docs check` prints `ok`; every version location reads 3.4.0; the 3.4.0 changelog section satisfies `tests/test_release_notes.py`.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/retire-ai-usage`
- **Merge strategy**: sequential
- Ship after `gin-console-5c4`, or together with it (`gin-harness-1u3`). After the merge into `master`: push once, then `./install.sh` once the push has finished.
- Not in this epic: tagging `v3.4.0`; deleting `ai_usage` from beads.

## Validation
- [ ] `timeout 900 python3 -m pytest -n auto -q` passes on `feat/retire-ai-usage` after Track 3
- [ ] `timeout 900 bash tests/install_smoke_test.sh` exits 0
- [ ] `gin docs check` prints `ok` for the changed pages
- [ ] `mkdocs build --strict` and the Windows smoke test pass on a manual run of `.github/workflows/test.yml` before the release tag
- [ ] After `./install.sh`, `gin usage` prints the usage line and exits 2, and `gin state --format json` in this repository shows no usage warning (manual)

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- The Parent Bead stays open until the human-confirmed merge; track beads close when their tests and review pass.

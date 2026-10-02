# Plan: Best-Practice Rules (Sub-project D)

**Goal:** Agents consistently follow language/framework best practices without raising per-task token cost beyond a fixed budget.

**Architecture:** Rule packs are Markdown files with YAML frontmatter in `plugins/gin-workflow/src/rules/`. A deterministic module `workflow_core/rules.py` parses packs and project rules, selects them by task file scope, orders them by precedence, and trims them by impact to a 4,000-char budget. `gin-workflow rules` exposes this. A second module `workflow_core/rules_checks.py` proposes packs for setup and runs read-only tool checks and conflict warnings for `setup preset` and `doctor`. Skills (`execute`, `quick`, `review`) and agents (`developer`, `code-reviewer`) inject the CLI output. Config schema moves to 2.5 with a defaults-only migration.

**Tech Stack:** Python 3.12 stdlib (`tomllib`, `re`, `json`) + PyYAML/jsonschema (already required); `unittest`; Markdown skills/agents/packs; bash/PowerShell installers.

**Spec:** `.planning/specs/2026-10-01-best-practice-rules-design.md` @ `f2360e2` (workflow id `best-practice-rules`, `requirement_confirmed` recorded).

## Global Constraints

Copied from the spec decisions:

| Topic | Decision |
|---|---|
| Enforcement | Two layers: tooling (linters/typecheck, verified by `verify.checks`) first; short imperative text only for what tooling cannot check. Review uses the same packs as checklist. |
| First packs | 7: `core`, `typescript`, `python`, `react`, `nextjs`, `fastapi`, `node-api`. |
| Precedence | Project rules > framework > language > core. Packs selectable/disable-able in config. `CLAUDE.md`/`AGENTS.md` are not copied (harness loads them); conflicts only warned. |
| Impact | Every bullet has an impact level `critical`, `high`, or `medium`. Over budget, `medium` then `high` bullets are trimmed; `critical` is never trimmed. |
| Rationale | Each pack keeps a `## Why` section for maintainers. It is never injected and does not count toward the budget. |
| Loading | Deterministic CLI selects packs by task file scope; injected only into `developer` (execute, `/quick`) and reviewer prompts; ≤ 4,000 chars per task. |
| Tooling layer | Report and suggest only (`doctor`, setup dry-run). Setup never edits lint/tsconfig; changes go through `/quick` or a task. |
| Schema | 2.5, with a defaults-only migration from 2.4. |

Repository constraints:
- Test command (repo root): `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py`. Baseline 2026-10-02 on `spec/d-best-practice-rules`: `Ran 600 tests … OK`.
- Install smoke test: `bash tests/install_smoke_test.sh`. The PowerShell smoke test cannot run here (no `pwsh`); keep it consistent by reading.
- Token budgets (`tests/workflow_core/test_token_budget.py`): each stage chain ≤ 12,000 chars (execute is 10,129 today); `quick` ≤ 8,000 (3,876 today); `agents/*.md` ≤ 4,000; descriptions ≤ 4,000.
- Review ledger severities are `CRITICAL|IMPORTANT|MINOR|SUGGESTION`. The spec's "finding severity `high`" for a `critical` rule violation maps to **at least `IMPORTANT`**.
- Portable config forbids keys named `commands`/`*_commands`; the new `rules` block uses `packs` and `disabled` only.
- Worker-result/evidence schema `"2.3"` constants in `workflow_providers/{contracts,evidence,worker_dispatch,routed_worker}.py` and `manifests.py`/`models.py` are a separate contract: do not change them.
- The launcher (`~/.local/lib/gin-workflow/<ver>/`) ships only `workflow_core/`; it must also ship `rules/` so `gin-workflow rules` works outside the plugin tree.
- Git: commit/push on `feat/best-practice-rules` (worktree); never commit to `master`.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`: brainstorm `high_reasoning`; design `high_reasoning`; plan `standard_impl`; implement `standard_impl`; verify `standard_impl`; review `high_reasoning`; docs `cheap_simple`
- `override_rule`: Track 1 (schema/migration compatibility) and Track 2 (selection/trimming semantics) use `high_reasoning`.

## Requirement Analysis
- Problem: agents have no packaged best-practice guidance; the only conventions they see are whatever `CLAUDE.md`/`AGENTS.md` say, so quality varies by stack and reviewers have no shared checklist.
- Success: spec acceptance criteria 1–6 (see Validation).
- Constraints: deterministic selection (no LLM); ≤ 4,000 chars per task; `critical` never trimmed; 2.3/2.4 configs keep working; setup/doctor are read-only toward lint/type configs.
- Non-goals: packs beyond the initial 7; suggesting rules from recurring findings; editing project lint configs; LLM conflict detection.

## Approach Options
### Option 1: Deterministic CLI selects and trims; skills inject its output (selected)
- Pros: testable, fixed token cost, same rule set for implementer and reviewer.
- Cons: more CLI surface (`gin-workflow rules`) and pack lint rules.
### Option 2: Skills tell the agent to read relevant rule files (portalkaitori style)
- Cons: nondeterministic loading, unbounded tokens, no trimming, no stable anchors for findings.
### Recommended Approach
- Option 1, as the spec decides.

## Scope
- In: `plugins/gin-workflow/src/{rules,scripts/workflow_core,scripts/workflow_providers/registry.py,skills/{execute,quick,review,setup},agents/{developer,code-reviewer}.md,examples/config.full.yaml}`, `install.sh`, `install.ps1`, `tests/`.
- Out: `docs/*` canonical reference pairs (no change planned), SDD specs (F), team mode (E).

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks build on one another (schema, then rules engine, then packs, then setup/doctor and skill integration) and share cli.py, setup_service.py and the installers; sequential direct execution avoids conflicts.
```

## File Structure

| Path | Responsibility |
|---|---|
| `src/scripts/workflow_core/schemas.py` | 2.5; accept 2.3/2.4/2.5; `rules` block schema |
| `src/scripts/workflow_core/configuration.py` | Workflow/setup-CLI version 2.5 |
| `src/scripts/workflow_core/migrations.py` | `CURRENT_VERSION = "2.5"`, 2.4→2.5 (versions only) |
| `src/scripts/workflow_core/cli.py` | Version 2.5; route `rules` |
| `src/scripts/workflow_providers/registry.py:178,184` | Treat 2.3/2.4/2.5 alike |
| `src/scripts/workflow_core/rules.py` (new) | Parse packs, select by files, precedence order, trim, `--list`, `main()` |
| `src/scripts/workflow_core/rules_checks.py` (new) | `propose_packs`, `check_tool`, `tool_check_report`, `conflict_warnings`, `rules_doctor` |
| `src/scripts/workflow_core/project.py` | `preset_assignments(..., rule_packs=())` |
| `src/scripts/workflow_core/setup_service.py` | `preset` proposes packs + missing tool checks; `doctor` reports rules |
| `src/rules/{README,core,typescript,python,react,nextjs,fastapi,node-api}.md` (new) | Policy + 7 packs |
| `src/skills/{execute,quick,review,setup}/SKILL.md`, `src/agents/{developer,code-reviewer}.md` | Injection and checklist |
| `src/examples/config.full.yaml` | 2.5 + `rules` example |
| `install.sh`, `install.ps1`, `tests/install_smoke_test.{sh,ps1}` | Launcher 2.5; ship `rules/` in dists and launcher |

## Tasks

### Track 1: Config schema 2.5 with the `rules` block

**Metadata:**
- Dependencies: none
- Provider role: backend
- Reasoning: high
- Model guidance: high_reasoning
- Estimated complexity: medium

**Files:**
- Modify: `workflow_core/schemas.py:10-11,~133` (add `rules` after `quick`), `workflow_core/configuration.py:26-27`, `workflow_core/migrations.py:15,60-74`, `workflow_core/cli.py:19`, `workflow_providers/registry.py:178,184`, `install.sh:12`, `install.ps1:17`, `tests/install_smoke_test.sh:139,229-245`, `tests/install_smoke_test.ps1:65,76,112,126`, `src/examples/config.full.yaml:1-3` (+ `rules` block)
- Test: `tests/workflow_core/test_schema_2_5.py` (new); update `2.4` → `2.5` only where tests assert the *current* config/setup-CLI/launcher version (`tests/workflow_core/test_setup_cli.py:29,254-256,397,409`). Tests that write `schema_version: '2.4'` configs stay as they are (2.4 must keep loading).

**Interfaces:**
- Produces: `SUPPORTED_SCHEMA_VERSION = "2.5"`, `SUPPORTED_CONFIG_VERSIONS = ("2.3", "2.4", "2.5")`, `migrations.CURRENT_VERSION = "2.5"`, config key `rules: {packs: [str], disabled: [str]}`.

- [ ] **Step 1: Failing tests** (`tests/workflow_core/test_schema_2_5.py`)

```python
"""Schema 2.5: rules block, read-compatibility, and the 2.4 -> 2.5 migration."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.configuration import (  # noqa: E402
    ConfigValidationError, resolve_effective_config, validate_portable_config)
from workflow_core.migrations import CURRENT_VERSION, migrate_config  # noqa: E402
from workflow_core.schemas import SUPPORTED_CONFIG_VERSIONS  # noqa: E402


class TestSchema25(unittest.TestCase):
    def test_current_version_is_2_5_and_older_versions_load(self):
        self.assertEqual("2.5", CURRENT_VERSION)
        self.assertEqual(("2.3", "2.4", "2.5"), SUPPORTED_CONFIG_VERSIONS)
        for version in SUPPORTED_CONFIG_VERSIONS:
            with self.subTest(version=version):
                validate_portable_config({"schema_version": version})

    def test_rules_block_validates(self):
        validate_portable_config({"schema_version": "2.5",
                                  "rules": {"packs": ["core", "react"], "disabled": ["nextjs"]}})
        for bad in ({"packs": "core"}, {"packs": [""]}, {"unknown": []}):
            with self.subTest(bad=bad), self.assertRaises(ConfigValidationError):
                validate_portable_config({"schema_version": "2.5", "rules": bad})

    def test_migration_2_4_to_2_5_only_bumps_versions(self):
        source = {"schema_version": "2.4", "workflow_version": "2.4", "setup_cli_version": "2.4",
                  "project": {"shape": "frontend"}}
        migrated = migrate_config(source, "2.5")
        self.assertEqual({**source, "schema_version": "2.5", "workflow_version": "2.5",
                          "setup_cli_version": "2.5"}, migrated)
        self.assertNotIn("rules", migrated)

    def test_migration_2_3_chains_through_2_4(self):
        source = {"schema_version": "2.3", "workflow_version": "2.3", "setup_cli_version": "2.3"}
        self.assertEqual("2.5", migrate_config(source, "2.5")["schema_version"])

    def test_effective_config_keeps_rules_block(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".agent-workflow").mkdir()
            (root / ".agent-workflow/config.yaml").write_text(
                "schema_version: '2.5'\nrules: {packs: [core, python]}\n", encoding="utf-8")
            config = resolve_effective_config(root, write=False).config.to_dict()
            self.assertEqual(["core", "python"], config["rules"]["packs"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2:** Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/workflow_core/test_schema_2_5.py -v` → FAIL (`'2.4' != '2.5'`, rules block accepted without validation).

- [ ] **Step 3: Implement**
  - `schemas.py`: `SUPPORTED_SCHEMA_VERSION = "2.5"`, `SUPPORTED_CONFIG_VERSIONS = ("2.3", "2.4", "2.5")`. Add to `CONFIG_SCHEMA["properties"]` after `"quick"`:
    ```python
            "rules": {
                "type": "object",
                "properties": {
                    "packs": {"type": "array", "uniqueItems": True, "items": {"type": "string", "minLength": 1}},
                    "disabled": {"type": "array", "uniqueItems": True, "items": {"type": "string", "minLength": 1}},
                },
                "additionalProperties": False,
            },
    ```
  - `configuration.py`: `SUPPORTED_WORKFLOW_VERSION = "2.5"`, `SUPPORTED_SETUP_CLI_VERSION = "2.5"`.
  - `migrations.py`: `CURRENT_VERSION = "2.5"`; add
    ```python
    def _migrate_2_4_to_2_5(config: dict[str, Any]) -> dict[str, Any]:
        migrated = dict(config)
        migrated["schema_version"] = "2.5"
        migrated["workflow_version"] = "2.5"
        migrated["setup_cli_version"] = "2.5"
        return migrated
    ```
    and `("2.4", "2.5"): _migrate_2_4_to_2_5,` in `_MIGRATIONS`.
  - `cli.py`: `CLI_VERSION = "2.5"`.
  - `registry.py:178,184`: `in ("2.3", "2.4", "2.5")`.
  - `install.sh:12` `LAUNCHER_VERSION="2.5"`; `install.ps1:17` `$LauncherVersion = '2.5'`; smoke tests: every `2.4` launcher path/version string → `2.5` (the `2.1` upgrade fixture stays).
  - `examples/config.full.yaml`: versions `"2.5"` and append
    ```yaml
    rules:
      packs: [core, typescript, react]
      disabled: []
    ```
  - `test_setup_cli.py:29,254-256,397,409`: expected current version `2.5`.

- [ ] **Step 4:** Run the Step 2 command → PASS. Run the full suite → `OK`; run `bash tests/install_smoke_test.sh` → passes.

- [ ] **Step 5:** Commit `feat(config): schema 2.5 with rules block and 2.4 read-compatibility`.

### Track 2: Rules engine and `gin-workflow rules` CLI

**Metadata:**
- Dependencies: Track 1
- Provider role: backend
- Reasoning: high
- Model guidance: high_reasoning
- Estimated complexity: high

**Files:**
- Create: `plugins/gin-workflow/src/scripts/workflow_core/rules.py`
- Modify: `workflow_core/cli.py:63-70` (route `rules`, usage string)
- Test: `tests/workflow_core/test_rules.py` (new)

**Interfaces:**
- Produces:
  - `RulesError(ValueError)`
  - `Bullet(anchor: str, impact: str, line: str)`; `Pack(id, tier, source, applies_to, requires, bullets, why, meta, path)` with `body_chars: int`, `body_limit: int`
  - `parse_pack(path: Path, *, source: str) -> Pack`
  - `plugin_rules_dir() -> Path`; `load_plugin_packs(directory: Path) -> dict[str, Pack]`; `load_project_rules(repository: Path) -> list[Pack]`
  - `rules_config(config: Mapping) -> tuple[list[str], set[str]]`
  - `select_packs(plugin, project, config, files) -> tuple[list[Pack], list[str]]`
  - `build_rules(packs, budget: int = TASK_BUDGET) -> dict` (keys `text, chars, budget, trimmed, warnings, packs`)
  - `list_packs(plugin, project, config) -> list[dict]`
  - `main(arguments: Sequence[str]) -> int`
  - Constants `TIERS`, `IMPACTS`, `TASK_BUDGET = 4_000`, `DEFAULT_BODY_LIMIT = 1_500`, `BODY_LIMITS = {"core": 1_000}`

- [ ] **Step 1: Failing tests** (`tests/workflow_core/test_rules.py`)

```python
"""Rule pack parsing, selection by file scope, precedence, and budget trimming."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.rules import (  # noqa: E402
    RulesError, build_rules, load_plugin_packs, load_project_rules, parse_pack, select_packs)


def _pack(directory: Path, name: str, front: str, body: str) -> Path:
    path = directory / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{front}\n---\n{body}", encoding="utf-8")
    return path


def _plugin_dir(root: Path) -> Path:
    packs = root / "rules"
    _pack(packs, "core", "id: core\ntier: core\napplies_to: ['**/*']",
          "- [critical] `scope`: Stay in scope.\n- `naming`: Name by domain.\n")
    _pack(packs, "typescript", "id: typescript\ntier: language\napplies_to: ['**/*.ts', '**/*.tsx']",
          "- [high] `no-any`: Avoid any.\n")
    _pack(packs, "python", "id: python\ntier: language\napplies_to: ['**/*.py']",
          "- [high] `typed`: Type public functions.\n")
    _pack(packs, "react", "id: react\ntier: framework\nrequires: [typescript]\napplies_to: ['**/*.tsx']",
          "- [critical] `state-location`: Server state in the data layer.\n\n## Why\n- `state-location`: WHY-TEXT.\n")
    _pack(packs, "nextjs", "id: nextjs\ntier: framework\nrequires: [react]\napplies_to: ['app/**']",
          "- [high] `server-default`: Prefer server components.\n")
    _pack(packs, "fastapi", "id: fastapi\ntier: framework\nrequires: [python]\napplies_to: ['**/*.py']",
          "- [high] `thin-routes`: Keep routes thin.\n")
    (packs / "README.md").write_text("policy, not a pack\n", encoding="utf-8")
    return packs


class TestParse(unittest.TestCase):
    def test_bullets_impacts_and_why_are_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = load_plugin_packs(_plugin_dir(Path(tmp)))["react"]
            self.assertEqual([("state-location", "critical")], [(b.anchor, b.impact) for b in pack.bullets])
            self.assertEqual({"state-location": "WHY-TEXT."}, dict(pack.why))
            self.assertNotIn("WHY", "\n".join(b.line for b in pack.bullets))

    def test_missing_impact_defaults_to_medium_and_readme_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs = load_plugin_packs(_plugin_dir(Path(tmp)))
            self.assertNotIn("README", packs)
            self.assertEqual("medium", packs["core"].bullets[1].impact)

    def test_malformed_packs_are_rejected(self):
        cases = {
            "prose": ("id: x\ntier: core\napplies_to: ['**/*']", "Some prose line.\n"),
            "dup": ("id: x\ntier: core\napplies_to: ['**/*']", "- `a`: one.\n- `a`: two.\n"),
            "impact": ("id: x\ntier: core\napplies_to: ['**/*']", "- [low] `a`: one.\n"),
            "tier": ("id: x\ntier: lib\napplies_to: ['**/*']", "- `a`: one.\n"),
            "applies": ("id: x\ntier: core", "- `a`: one.\n"),
            "why-unknown": ("id: x\ntier: core\napplies_to: ['**/*']", "- `a`: one.\n\n## Why\n- `b`: no.\n"),
            "why-twice": ("id: x\ntier: core\napplies_to: ['**/*']", "- `a`: one.\n\n## Why\n- `a`: 1.\n- `a`: 2.\n"),
        }
        for name, (front, body) in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(RulesError):
                    parse_pack(_pack(Path(tmp), "x", front, body), source="plugin")

    def test_project_rule_needs_only_applies_to(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _pack(repo / ".agent-workflow/rules", "api-style", "applies_to: ['src/**']", "- `codes`: Use codes.\n")
            [rule] = load_project_rules(repo)
            self.assertEqual(("api-style", "project", "project"), (rule.id, rule.tier, rule.source))


class TestSelect(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plugin = load_plugin_packs(_plugin_dir(self.root))

    def tearDown(self):
        self.tmp.cleanup()

    def _ids(self, config, files, project=()):
        packs, _ = select_packs(self.plugin, list(project), config, files)
        return [p.id for p in packs]

    def test_missing_rules_block_means_core_only(self):
        self.assertEqual(["core"], self._ids({}, ["app/page.tsx"]))

    def test_python_scope_never_gets_react(self):
        config = {"rules": {"packs": ["core", "python", "fastapi", "typescript", "react"]}}
        self.assertEqual(["fastapi", "python", "core"], self._ids(config, ["api/main.py"]))

    def test_requires_are_co_loaded_and_ordered_after_dependents(self):
        config = {"rules": {"packs": ["nextjs"]}}
        self.assertEqual(["nextjs", "react", "typescript", "core"], self._ids(config, ["app/page.tsx"]))

    def test_disabled_wins_over_packs_and_requires(self):
        config = {"rules": {"packs": ["react"], "disabled": ["typescript", "core"]}}
        self.assertEqual(["react"], self._ids(config, ["src/a.tsx"]))

    def test_project_rules_come_first(self):
        repo = self.root / "repo"
        _pack(repo / ".agent-workflow/rules", "ui", "applies_to: ['**/*.tsx']", "- `x`: Project rule.\n")
        ids = self._ids({"rules": {"packs": ["react"]}}, ["src/a.tsx"], load_project_rules(repo))
        self.assertEqual(["ui", "react", "typescript", "core"], ids)

    def test_unknown_pack_is_warned_not_fatal(self):
        _, warnings = select_packs(self.plugin, [], {"rules": {"packs": ["vue"]}}, ["a.vue"])
        self.assertEqual(["unknown rule pack 'vue' ignored"], warnings)


class TestBudget(unittest.TestCase):
    def _packs(self, root: Path):
        line = "x" * 120
        _pack(root / "rules", "core", "id: core\ntier: core\napplies_to: ['**/*']",
              "".join(f"- `c-med-{i}`: {line}\n" for i in range(4)) + f"- [critical] `c-crit`: {line}\n")
        _pack(root / "rules", "python", "id: python\ntier: language\napplies_to: ['**/*.py']",
              "".join(f"- [high] `p-high-{i}`: {line}\n" for i in range(4)) + f"- `p-med`: {line}\n")
        plugin = load_plugin_packs(root / "rules")
        _pack(root / "repo/.agent-workflow/rules", "proj", "applies_to: ['**/*.py']", f"- `proj-med`: {line}\n")
        packs, _ = select_packs(plugin, load_project_rules(root / "repo"), {"rules": {"packs": ["python"]}}, ["a.py"])
        return packs

    def test_within_budget_returns_everything(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_rules(self._packs(Path(tmp)))
            self.assertEqual([], result["trimmed"])
            self.assertEqual(result["chars"], len(result["text"]))
            self.assertIn("## proj (project)", result["text"])

    def test_medium_trimmed_first_from_lowest_precedence_project_last(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_rules(self._packs(Path(tmp)), budget=1_000)
            self.assertEqual(["core#c-med-3", "core#c-med-2", "core#c-med-1", "core#c-med-0", "python#p-med"],
                             result["trimmed"][:5])
            self.assertLessEqual(result["chars"], 1_000)
            self.assertIn("c-crit", result["text"])

    def test_high_trimmed_after_all_medium_and_critical_never(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_rules(self._packs(Path(tmp)), budget=100)
            self.assertIn("proj#proj-med", result["trimmed"])
            self.assertIn("python#p-high-0", result["trimmed"])
            self.assertIn("c-crit", result["text"])
            self.assertTrue(any("critical rules exceed budget" in w for w in result["warnings"]))
            self.assertGreater(result["chars"], 100)

    def test_why_never_rendered(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs, _ = select_packs(load_plugin_packs(_plugin_dir(Path(tmp))), [],
                                    {"rules": {"packs": ["react"]}}, ["a.tsx"])
            result = build_rules(packs)
            self.assertNotIn("WHY-TEXT", result["text"])
            self.assertNotIn("WHY-TEXT", json.dumps(result))


class TestCli(unittest.TestCase):
    def _run(self, repo: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPTS / "gin-workflow"), "rules", "--repository", str(repo), *args],
                              cwd=ROOT, env={"PYTHONPATH": str(SCRIPTS), "PATH": "/usr/bin:/bin"},
                              capture_output=True, text=True, check=False)

    def test_files_uses_packaged_packs_and_core_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(Path(tmp), "--files", "src/a.py", "--format", "json")
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(["core"], [p["id"] for p in payload["packs"]])

    def test_list_reports_sizes_and_impact_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(Path(tmp), "--list", "--format", "json")
            self.assertEqual(0, result.returncode, result.stderr)
            [core] = json.loads(result.stdout)["packs"]
            self.assertEqual(("core", "plugin"), (core["id"], core["source"]))
            self.assertEqual({"critical", "high", "medium"}, set(core["impacts"]))

    def test_malformed_project_rule_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _pack(repo / ".agent-workflow/rules", "bad", "applies_to: ['**/*']", "prose\n")
            result = self._run(repo, "--files", "a.py")
            self.assertEqual(2, result.returncode)
            self.assertIn("rules error", result.stderr)


if __name__ == "__main__":
    unittest.main()
```

Note: `TestCli` needs `src/rules/core.md` to exist. Track 2 creates a minimal `src/rules/core.md` stub with one valid bullet (`- [critical] \`scope\`: Change only files in the task scope.`); Track 3 replaces it with the full pack.

- [ ] **Step 2:** Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/workflow_core/test_rules.py -v` → FAIL (`No module named 'workflow_core.rules'`).

- [ ] **Step 3: Implement** `workflow_core/rules.py`:

```python
"""Best-practice rule packs: parse, select by file scope, order by precedence, trim to budget."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

from .configuration import require_yaml, resolve_effective_config

TIERS = ("core", "language", "framework")
IMPACTS = ("critical", "high", "medium")
TASK_BUDGET = 4_000
DEFAULT_BODY_LIMIT = 1_500
BODY_LIMITS = {"core": 1_000}
_TIER_RANK = {"project": 0, "framework": 1, "language": 2, "core": 3}
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)
_BULLET = re.compile(r"^- (?:\[([a-z]+)\] )?`([a-z0-9][a-z0-9-]*)`: (\S.*)$")
_WHY_LINE = re.compile(r"^- `([a-z0-9][a-z0-9-]*)`: (\S.*)$")
_WHY_HEADING = "## Why"


class RulesError(ValueError):
    """Raised when a rule pack or project rule file is malformed."""


@dataclass(frozen=True)
class Bullet:
    anchor: str
    impact: str
    line: str


@dataclass(frozen=True)
class Pack:
    id: str
    tier: str
    source: str
    applies_to: tuple[str, ...]
    requires: tuple[str, ...]
    bullets: tuple[Bullet, ...]
    why: Mapping[str, str]
    meta: Mapping[str, Any]
    path: Path

    @property
    def body_chars(self) -> int:
        return len("\n".join(bullet.line for bullet in self.bullets))

    @property
    def body_limit(self) -> int:
        return BODY_LIMITS.get(self.id, DEFAULT_BODY_LIMIT) if self.source == "plugin" else DEFAULT_BODY_LIMIT


def _string_list(value: Any, *, path: Path, key: str, required: bool) -> tuple[str, ...]:
    if value is None and not required:
        return ()
    if not isinstance(value, list) or (required and not value) or not all(isinstance(v, str) and v for v in value):
        raise RulesError(f"{path}: {key} must be a {'non-empty ' if required else ''}list of strings")
    return tuple(value)


def parse_pack(path: Path, *, source: str) -> Pack:
    text = Path(path).read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if not match:
        raise RulesError(f"{path}: missing YAML frontmatter")
    meta = require_yaml().safe_load(match.group(1)) or {}
    if not isinstance(meta, Mapping):
        raise RulesError(f"{path}: frontmatter must be a mapping")
    lines = text[match.end():].splitlines()
    split = lines.index(_WHY_HEADING) if _WHY_HEADING in lines else len(lines)
    bullets: list[Bullet] = []
    for line in lines[:split]:
        if not line.strip():
            continue
        found = _BULLET.match(line)
        if not found or (found.group(1) or "medium") not in IMPACTS:
            raise RulesError(f"{path}: not a rule bullet: {line!r}")
        bullets.append(Bullet(anchor=found.group(2), impact=found.group(1) or "medium", line=line))
    anchors = [bullet.anchor for bullet in bullets]
    duplicates = sorted({anchor for anchor in anchors if anchors.count(anchor) > 1})
    if duplicates:
        raise RulesError(f"{path}: duplicate anchors {duplicates}")
    why: dict[str, str] = {}
    for line in lines[split + 1:]:
        if not line.strip():
            continue
        found = _WHY_LINE.match(line)
        if not found or found.group(1) not in anchors or found.group(1) in why:
            raise RulesError(f"{path}: invalid ## Why line {line!r}")
        why[found.group(1)] = found.group(2)
    if source == "plugin":
        if meta.get("id") != path.stem:
            raise RulesError(f"{path}: id must equal the file stem {path.stem!r}")
        if meta.get("tier") not in TIERS:
            raise RulesError(f"{path}: tier must be one of {TIERS}")
    return Pack(
        id=str(meta.get("id") or path.stem),
        tier="project" if source == "project" else str(meta["tier"]),
        source=source,
        applies_to=_string_list(meta.get("applies_to"), path=path, key="applies_to", required=True),
        requires=_string_list(meta.get("requires"), path=path, key="requires", required=False),
        bullets=tuple(bullets),
        why=why,
        meta=dict(meta),
        path=Path(path),
    )


def plugin_rules_dir() -> Path:
    """Launcher layout ships `rules/` beside `workflow_core/`; plugin trees have it two levels up."""
    here = Path(__file__).resolve().parent
    for candidate in (here.parent / "rules", here.parent.parent / "rules"):
        if candidate.is_dir():
            return candidate
    raise RulesError("plugin rules directory not found next to workflow_core")


def load_plugin_packs(directory: Path) -> dict[str, Pack]:
    return {path.stem: parse_pack(path, source="plugin")
            for path in sorted(Path(directory).glob("*.md")) if path.name != "README.md"}


def load_project_rules(repository: Path) -> list[Pack]:
    return [parse_pack(path, source="project")
            for path in sorted((Path(repository) / ".agent-workflow/rules").glob("*.md"))]


def rules_config(config: Mapping[str, Any]) -> tuple[list[str], set[str]]:
    section = config.get("rules") if isinstance(config.get("rules"), Mapping) else {}
    packs = [str(item) for item in (section.get("packs") or ["core"])]
    return packs, {str(item) for item in (section.get("disabled") or ())}


def _glob_regex(pattern: str) -> re.Pattern[str]:
    parts, index = [], 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            parts.append("(?:.*/)?")
            index += 3
        elif pattern.startswith("**", index):
            parts.append(".*")
            index += 2
        elif pattern[index] == "*":
            parts.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            parts.append("[^/]")
            index += 1
        else:
            parts.append(re.escape(pattern[index]))
            index += 1
    return re.compile("".join(parts) + r"\Z")


def _matches(pack: Pack, files: Sequence[str]) -> bool:
    return any(_glob_regex(pattern).match(path) for pattern in pack.applies_to for path in files)


def _depth(pack: Pack, plugin: Mapping[str, Pack], seen: tuple[str, ...] = ()) -> int:
    required = [plugin[name] for name in pack.requires if name in plugin and name not in seen]
    return 1 + max((_depth(item, plugin, (*seen, pack.id)) for item in required), default=0)


def select_packs(plugin: Mapping[str, Pack], project: Sequence[Pack], config: Mapping[str, Any],
                 files: Sequence[str]) -> tuple[list[Pack], list[str]]:
    """Enabled packs matching `files` (+ core, + requires), highest precedence first."""
    packs, disabled = rules_config(config)
    warnings = [f"unknown rule pack {name!r} ignored" for name in packs if name not in plugin]
    enabled = {name for name in ("core", *packs) if name in plugin and name not in disabled}
    chosen = {name for name in enabled if name == "core" or _matches(plugin[name], files)}
    pending = list(chosen)
    while pending:
        for name in plugin[pending.pop()].requires:
            if name in plugin and name not in disabled and name not in chosen:
                chosen.add(name)
                pending.append(name)
    selected = [plugin[name] for name in chosen]
    selected += [rule for rule in project if rule.id not in disabled and _matches(rule, files)]
    selected.sort(key=lambda pack: (_TIER_RANK[pack.tier], -_depth(pack, plugin), pack.id))
    return selected, warnings


def _render(packs: Sequence[Pack], kept: Sequence[list[Bullet]]) -> str:
    blocks = [f"## {pack.id} ({pack.source})\n" + "\n".join(bullet.line for bullet in bullets)
              for pack, bullets in zip(packs, kept) if bullets]
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def build_rules(packs: Sequence[Pack], budget: int = TASK_BUDGET) -> dict[str, Any]:
    """Render packs; over budget, drop medium then high bullets, lowest precedence first; never critical."""
    kept = [list(pack.bullets) for pack in packs]
    text = _render(packs, kept)
    trimmed: list[str] = []
    warnings: list[str] = []
    for impact in ("medium", "high"):
        step: list[str] = []
        for index in reversed(range(len(packs))):
            for bullet in reversed(list(kept[index])):
                if len(text) <= budget:
                    break
                if bullet.impact == impact:
                    kept[index].remove(bullet)
                    step.append(f"{packs[index].id}#{bullet.anchor}")
                    text = _render(packs, kept)
        if step:
            trimmed += step
            warnings.append(f"rules over {budget} chars: trimmed {impact} " + ", ".join(step))
    if len(text) > budget:
        warnings.append(f"critical rules exceed budget: {len(text)} > {budget} chars")
    return {
        "text": text,
        "chars": len(text),
        "budget": budget,
        "trimmed": trimmed,
        "warnings": warnings,
        "packs": [{"id": pack.id, "source": pack.source, "tier": pack.tier,
                   "bullets": [{"anchor": b.anchor, "impact": b.impact, "text": b.line} for b in bullets],
                   "trimmed": [b.anchor for b in pack.bullets if b not in bullets]}
                  for pack, bullets in zip(packs, kept)],
    }


def list_packs(plugin: Mapping[str, Pack], project: Sequence[Pack], config: Mapping[str, Any]) -> list[dict[str, Any]]:
    packs, disabled = rules_config(config)
    enabled = [plugin[name] for name in dict.fromkeys(("core", *packs)) if name in plugin and name not in disabled]
    rows = [rule for rule in project if rule.id not in disabled] + enabled
    return [{"id": pack.id, "source": pack.source, "tier": pack.tier, "chars": pack.body_chars,
             "limit": pack.body_limit, "over_limit": pack.body_chars > pack.body_limit,
             "impacts": {impact: sum(b.impact == impact for b in pack.bullets) for impact in IMPACTS}}
            for pack in rows]


def _load_config(repository: Path) -> Mapping[str, Any]:
    if not (repository / ".agent-workflow/config.yaml").is_file():
        return {}
    return resolve_effective_config(repository, write=False).config.to_dict()


def _relative(repository: Path, raw: str) -> str:
    path = Path(raw)
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(repository)
        except ValueError:
            pass
    return path.as_posix().removeprefix("./")


def main(arguments: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="gin-workflow rules")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--format", choices=("text", "json"), default="text")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--files", nargs="+")
    mode.add_argument("--list", action="store_true")
    try:
        args = parser.parse_args(list(arguments))
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    repository = args.repository.resolve()
    try:
        config = _load_config(repository)
        plugin = load_plugin_packs(plugin_rules_dir())
        project = load_project_rules(repository)
    except (RulesError, ValueError) as error:
        print(f"rules error: {error}", file=sys.stderr)
        return 2
    if args.list:
        rows = list_packs(plugin, project, config)
        if args.format == "json":
            print(json.dumps({"packs": rows}, indent=2, sort_keys=True))
        else:
            for row in rows:
                counts = " ".join(f"{k}={v}" for k, v in row["impacts"].items())
                flag = " OVER LIMIT" if row["over_limit"] else ""
                print(f"{row['id']} ({row['source']}, {row['tier']}): {row['chars']}/{row['limit']} chars; {counts}{flag}")
        return 0
    packs, warnings = select_packs(plugin, project, config, [_relative(repository, f) for f in args.files])
    result = build_rules(packs)
    for warning in [*warnings, *result["warnings"]]:
        print(f"warning: {warning}", file=sys.stderr)
    if args.format == "json":
        print(json.dumps({**result, "warnings": [*warnings, *result["warnings"]]}, indent=2, sort_keys=True))
    else:
        sys.stdout.write(result["text"])
    return 0
```

  `cli.py`: accept `rules` and route it before the setup parser:

```python
    if not argv or argv[0] not in ("setup", "state", "unblock", "record", "quick-check", "rules"):
        print("usage: gin-workflow {setup,state,unblock,record,quick-check,rules} <command>", file=sys.stderr)
        return 2
    if argv[0] == "rules":
        from .rules import main as rules_main
        return rules_main(argv[1:])
```

  Create stub `plugins/gin-workflow/src/rules/core.md`:

```markdown
---
id: core
tier: core
applies_to: ["**/*"]
---
- [critical] `scope`: Change only files in the task scope; report needed changes elsewhere instead of making them.
```

- [ ] **Step 4:** Run the Step 2 command → PASS. Full suite → `OK`.

- [ ] **Step 5:** Commit `feat(rules): rule pack engine and gin-workflow rules CLI`.

### Track 3: The seven packs, maintenance policy, budget lint, and packaging

**Metadata:**
- Dependencies: Track 2
- Provider role: backend
- Reasoning: medium
- Model guidance: standard_impl
- Estimated complexity: medium

**Files:**
- Create: `plugins/gin-workflow/src/rules/{README,typescript,python,react,nextjs,fastapi,node-api}.md`; replace the stub `rules/core.md`
- Modify: `install.sh` (`copy_src` mkdir + a `rules` block like `references`; `install_launcher` copies `src/rules/.` to `$install_dir/rules/`), `install.ps1` (`Copy-PluginSource` directory list adds `'rules'`; launcher copies `src/rules` to `$installDirectory/rules`), `tests/install_smoke_test.sh` / `.ps1` (assert launcher `rules/core.md`, run `gin-workflow rules --list` from the installed launcher)
- Test: `tests/workflow_core/test_token_budget.py` (new test), `tests/workflow_core/test_rule_packs.py` (new), `tests/workflow_providers/test_harness_packaging.py:36-92` (REQUIRED_ARTIFACTS += `rules/README.md` and the 7 packs)

**Interfaces:**
- Consumes: `load_plugin_packs`, `Pack.body_chars`, `Pack.body_limit` (Track 2).
- Produces: packs whose frontmatter `detect`, `tool_checks`, `conflict_keywords` Track 4 reads.

- [ ] **Step 1: Failing tests**

`tests/workflow_core/test_token_budget.py`, add to `TestBudgetLimits`:

```python
    def test_rule_pack_bodies_within_budget(self):
        from workflow_core.rules import load_plugin_packs

        packs = load_plugin_packs(SRC / "rules")
        self.assertEqual({"core", "typescript", "python", "react", "nextjs", "fastapi", "node-api"}, set(packs))
        for pack in packs.values():
            with self.subTest(pack=pack.id):
                self.assertLessEqual(pack.body_chars, pack.body_limit)
```

`tests/workflow_core/test_rule_packs.py`:

```python
"""Lint for the packaged rule packs: frontmatter, anchors, impacts, Why lines, tool checks."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins/gin-workflow/src/scripts"))

from workflow_core.rules import IMPACTS, TIERS, load_plugin_packs  # noqa: E402

PACKS = load_plugin_packs(ROOT / "plugins/gin-workflow/src/rules")
CHECK_KINDS = {"tsconfig_option", "eslint_rule", "pyproject_tool", "file_exists"}
DETECT_KEYS = {"package_json_deps", "pyproject_deps", "files_exist"}


class TestRulePacks(unittest.TestCase):
    def test_frontmatter_and_bullets(self):
        for pack in PACKS.values():
            with self.subTest(pack=pack.id):
                self.assertIn(pack.tier, TIERS)
                self.assertTrue(pack.applies_to)
                self.assertTrue(pack.bullets)
                self.assertTrue(all(b.impact in IMPACTS for b in pack.bullets))
                self.assertTrue(all(name in PACKS for name in pack.requires))
                self.assertLessEqual(set(pack.meta.get("detect") or {}), DETECT_KEYS)

    def test_tool_checks_and_conflicts_are_well_formed(self):
        for pack in PACKS.values():
            for check in pack.meta.get("tool_checks") or []:
                with self.subTest(pack=pack.id, check=check.get("id")):
                    self.assertTrue(check["id"] and check["suggest"].strip())
                    self.assertEqual(1, len(check["check"]))
                    self.assertIn(next(iter(check["check"])), CHECK_KINDS)
            for item in pack.meta.get("conflict_keywords") or []:
                self.assertEqual({"pack_says", "project_conflict"}, set(item))

    def test_every_pack_explains_its_critical_rules(self):
        for pack in PACKS.values():
            for bullet in pack.bullets:
                if bullet.impact == "critical":
                    with self.subTest(pack=pack.id, anchor=bullet.anchor):
                        self.assertIn(bullet.anchor, pack.why)

    def test_core_applies_everywhere_and_others_are_scoped(self):
        self.assertEqual(("**/*",), PACKS["core"].applies_to)
        self.assertNotIn("**/*", [p for pack in PACKS.values() if pack.id != "core" for p in pack.applies_to])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2:** Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/workflow_core/test_rule_packs.py tests/workflow_core/test_token_budget.py -v` → FAIL (only `core` exists; no `## Why` for `scope`).

- [ ] **Step 3: Write the packs.** Exact content:

`rules/README.md`:

```markdown
# Rule packs

Best-practice packs injected by `gin-workflow rules --files <paths>` into the `developer` agent and the reviewer. Only the bullets before `## Why` are injected.

## Format
- Frontmatter: `id` (= file stem), `tier` (`core` | `language` | `framework`), `applies_to` (globs), optional `requires`, `detect`, `conflict_keywords`, `tool_checks`.
- Body: one bullet per rule, `- [critical|high|medium] \`anchor\`: Imperative text.` Impact defaults to `medium`. Anchors are stable; findings cite `<pack>#<anchor>`.
- Body ≤ 1,500 chars (`core` ≤ 1,000). `## Why` holds at most one line per anchor and is never injected; every `critical` rule has one.
- Only rules that linters and type checkers cannot enforce. Enforceable rules belong in `tool_checks`.

## Precedence
Project rules (`.agent-workflow/rules/*.md`) > framework > language > core. Over the 4,000-char task budget, `medium` then `high` bullets are trimmed from the lowest precedence first; `critical` is never trimmed.

## Maintenance
- Add a rule when the same correction was needed more than twice.
- Remove a rule once tooling enforces it or it is obsolete; name the replacement in the commit message.
```

`rules/core.md`:

```markdown
---
id: core
tier: core
applies_to: ["**/*"]
---
- [critical] `scope`: Change only files in the task scope; report needed changes elsewhere instead of making them.
- [critical] `no-secrets`: Never commit secrets, tokens, or credentials; read them from the environment or a secret store.
- [high] `errors-explicit`: Handle or propagate every error; never swallow one or log-and-continue without a stated reason.
- [high] `validate-boundaries`: Validate input where it enters the system (HTTP, CLI, files, queues); trust it inside.
- [high] `test-behavior`: Test observable behavior through public interfaces, not private helpers.
- `reuse-first`: Reuse existing helpers and patterns before adding an abstraction or dependency.
- `domain-names`: Name things for what they mean in the domain; no new abbreviations.
- `one-job`: Give each function one responsibility; split it when describing it needs "and".

## Why
- `scope`: Out-of-scope edits bypass the plan and the review that approved it.
- `no-secrets`: Committed secrets leak through history even after deletion.
- `errors-explicit`: Swallowed errors turn failures into silent data corruption.
```

`rules/typescript.md`:

```markdown
---
id: typescript
tier: language
applies_to: ["**/*.ts", "**/*.tsx", "**/*.mts", "**/*.cts"]
detect: {package_json_deps: [typescript], files_exist: [tsconfig.json]}
tool_checks:
  - id: tsconfig-strict
    check: {tsconfig_option: {strict: true}}
    suggest: |
      // tsconfig.json
      { "compilerOptions": { "strict": true } }
  - id: typescript-eslint
    check: {eslint_rule: "@typescript-eslint/no-floating-promises"}
    suggest: |
      // eslint.config.js
      import tseslint from "typescript-eslint";
      export default tseslint.config(...tseslint.configs.recommendedTypeChecked);
---
- [critical] `no-type-escape`: Do not silence the type checker with `any`, `as` casts, or `!`; narrow with guards or fix the type.
- [high] `model-states`: Model variants as discriminated unions so invalid states cannot be represented.
- [high] `parse-at-boundary`: Parse untrusted data (JSON, env, API responses) with a schema before giving it a type.
- `readonly-inputs`: Mark data a function does not mutate as `readonly`.
- `types-with-owner`: Export a type from the module that owns it; avoid catch-all `types.ts` files.

## Why
- `no-type-escape`: Escapes hide exactly the bugs the type checker exists to catch.
- `parse-at-boundary`: A type annotation on unvalidated data is a false guarantee.
```

`rules/python.md`:

```markdown
---
id: python
tier: language
applies_to: ["**/*.py"]
detect: {files_exist: [pyproject.toml, requirements.txt]}
tool_checks:
  - id: ruff
    check: {pyproject_tool: tool.ruff}
    suggest: |
      [tool.ruff.lint]
      select = ["E", "F", "I", "B", "UP", "BLE"]
  - id: mypy
    check: {pyproject_tool: tool.mypy}
    suggest: |
      [tool.mypy]
      strict = true
---
- [critical] `typed-public`: Annotate every public function signature; keep `Any` inside boundary adapters.
- [high] `structured-data`: Pass structured data as dataclasses or Pydantic models, not loose dicts between modules.
- [high] `io-at-edges`: Keep network, disk, and env access at the edges; core functions take and return values.
- `no-module-state`: Do not keep mutable state at module level; pass dependencies explicitly.
- `local-fixtures`: Keep pytest fixtures beside their tests; move one to `conftest.py` only when shared.

## Why
- `typed-public`: Signatures are the contract callers and type checkers rely on.
- `io-at-edges`: Pure cores are testable without mocks.
```

`rules/react.md`:

```markdown
---
id: react
tier: framework
requires: [typescript]
applies_to: ["**/*.tsx", "**/*.jsx"]
detect: {package_json_deps: [react]}
conflict_keywords:
  - {pack_says: "named export", project_conflict: "default export"}
tool_checks:
  - id: react-hooks-lint
    check: {eslint_rule: "react-hooks/rules-of-hooks"}
    suggest: |
      // eslint.config.js
      import reactHooks from "eslint-plugin-react-hooks";
      export default [reactHooks.configs["recommended-latest"]];
---
- [critical] `state-location`: Keep server state in the data-fetching layer (query cache or loader), not in component state.
- [high] `derive-not-sync`: Derive values during render instead of copying them into state with an effect.
- [high] `effects-external-only`: Use effects only to sync with external systems; handle user actions in event handlers.
- [high] `stable-keys`: Key list items by stable domain ids, never by array index in lists that reorder.
- `one-component-per-file`: Export one component per file; split a component that renders unrelated concerns.
- `named-exports`: Use named exports for components.
- `semantic-first`: Use semantic elements (`button`, `label`, headings) before ARIA attributes.

## Why
- `state-location`: Server state copied into components goes stale and duplicates caching logic.
- `derive-not-sync`: Synced state renders twice and drifts from its source.
```

`rules/nextjs.md`:

```markdown
---
id: nextjs
tier: framework
requires: [react]
applies_to: ["app/**", "src/app/**", "pages/**", "src/pages/**", "middleware.ts", "src/middleware.ts"]
detect: {package_json_deps: [next]}
tool_checks:
  - id: next-lint
    check: {eslint_rule: "@next/next/no-html-link-for-pages"}
    suggest: |
      // eslint.config.js
      import next from "@next/eslint-plugin-next";
      export default [{ plugins: { "@next/next": next }, rules: next.configs.recommended.rules }];
---
- [critical] `server-secrets`: Read secrets only in server code; never import server-only modules or private env into Client Components.
- [high] `server-default`: Keep components on the server; add `"use client"` only at the smallest interactive leaf.
- [high] `fetch-on-server`: Fetch data in Server Components or route handlers, not in client effects.
- [high] `cache-explicit`: State the caching and revalidation intent of every fetch and route.
- `mutations-revalidate`: Mutate through Server Actions or route handlers that revalidate the affected paths.
- `route-colocation`: Keep route-only components inside the route segment; move them to `components/` when reused.

## Why
- `server-secrets`: Anything a Client Component imports ships to the browser.
- `cache-explicit`: Implicit caching defaults change between Next.js versions.
```

`rules/fastapi.md`:

```markdown
---
id: fastapi
tier: framework
requires: [python]
applies_to: ["**/*.py"]
detect: {pyproject_deps: [fastapi]}
---
- [critical] `models-at-edge`: Declare request and response models; never return ORM objects or raw dicts from routes.
- [high] `depends-for-resources`: Get sessions, settings, and the current user through `Depends`, not module globals.
- [high] `thin-routes`: Keep route functions thin; business logic lives in services that do not import FastAPI.
- [high] `no-blocking-async`: Never block inside `async def`; use `def` routes or async clients.
- `stable-errors`: Raise `HTTPException` or a mapped domain error with a stable code; never leak stack traces.
- `router-per-domain`: Use one `APIRouter` per domain module, included by the app factory.

## Why
- `models-at-edge`: Response models are the API contract and stop accidental field leaks.
```

`rules/node-api.md`:

```markdown
---
id: node-api
tier: framework
applies_to: ["**/*.ts", "**/*.js", "**/*.mts", "**/*.mjs", "**/*.cts", "**/*.cjs"]
detect: {package_json_deps: [express, fastify, koa, hono, "@nestjs/core"]}
---
- [critical] `validate-input`: Validate every request body, query, and params with a schema before use.
- [critical] `async-errors`: Route every async error to the framework error handler; leave no promise unhandled.
- [high] `thin-handlers`: Handlers parse, call a service, and map the result; services never see `req` or `res`.
- [high] `config-once`: Read and validate environment config once at startup into a typed object.
- `error-shape`: Return one error body shape with a stable code.
- `graceful-shutdown`: Close servers, pools, and queues on SIGTERM.

## Why
- `validate-input`: Unvalidated input is the main source of injection and crash bugs.
- `async-errors`: An unhandled rejection can crash the process or hang the request.
```

- [ ] **Step 4: Packaging.**
  - `install.sh` `copy_src`: add `"$target/rules"` to the `mkdir -p` list and a block identical to the `references` block with `rules`. In `install_launcher`, after copying `workflow_core`: `mkdir -p "$install_dir/rules"` and `cp -rf "$SCRIPT_DIR/plugins/gin-workflow/src/rules/." "$install_dir/rules/"`.
  - `install.ps1`: `Copy-PluginSource` list becomes `@('commands', 'skills', 'agents', 'scripts', 'references', 'examples', 'rules')`; in the launcher section add `New-Directory (Join-Path $installDirectory 'rules')` and `Copy-DirectoryContent -Source (Join-Path $PluginSourceRoot 'rules') -Destination (Join-Path $installDirectory 'rules')`, using the variable that already points at `plugins/gin-workflow/src` in that function (derive it from `$sourceDirectory` as `Split-Path -Parent $sourceDirectory` if none exists).
  - `test_harness_packaging.py` REQUIRED_ARTIFACTS: add `"rules/README.md"`, `"rules/core.md"`, `"rules/typescript.md"`, `"rules/python.md"`, `"rules/react.md"`, `"rules/nextjs.md"`, `"rules/fastapi.md"`, `"rules/node-api.md"`.
  - `tests/install_smoke_test.sh`: after the launcher asserts, `assert_exists "$MOCK_HOME/.local/lib/gin-workflow/2.5/rules/core.md"` and run `"$MOCK_HOME/.local/lib/gin-workflow/2.5/gin-workflow" rules --list --repository "$MOCK_HOME"` asserting the output contains `core (plugin, core)`. Mirror both in `install_smoke_test.ps1`.

- [ ] **Step 5:** Run the Step 2 command → PASS. Full suite → `OK`. `bash tests/install_smoke_test.sh` → passes. `gin-workflow`-from-source check: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 plugins/gin-workflow/src/scripts/gin-workflow rules --list` prints 1 line (`core`, since this repo has no `rules:` block).

- [ ] **Step 6:** Commit `feat(rules): seven best-practice packs with budget lint and packaging`.

### Track 4: Pack proposals, tool checks, and conflicts in setup and doctor

**Metadata:**
- Dependencies: Track 3
- Provider role: backend
- Reasoning: medium
- Model guidance: standard_impl
- Estimated complexity: medium

**Files:**
- Create: `plugins/gin-workflow/src/scripts/workflow_core/rules_checks.py`
- Modify: `workflow_core/project.py:83-107` (`preset_assignments` gains `rule_packs`), `workflow_core/setup_service.py:695-709` (`preset`), `workflow_core/setup_service.py:~470-488` (`doctor`, after the review-ledger block and before `healthy = ...`), `skills/setup/SKILL.md` (Quick setup "Then" step 2)
- Test: `tests/workflow_core/test_rules_checks.py` (new), `tests/workflow_core/test_setup_cli.py` (preset and doctor assertions)

**Interfaces:**
- Consumes: `load_plugin_packs`, `plugin_rules_dir`, `rules_config`, `Pack.meta` (Tracks 2–3); `project_detect._read_json`, `_mentions`, `_workspace_globs`, `_workspace_dirs`.
- Produces:
  - `propose_packs(root: Path, plugin: Mapping[str, Pack], *, stack_intent: str = "") -> list[str]` (ordered core, language, framework; ids sorted within tier)
  - `check_tool(root: Path, check: Mapping[str, Any]) -> str` (`present` | `missing` | `unknown`)
  - `tool_check_report(root: Path, packs: Sequence[Pack]) -> list[dict]` (`pack, id, status, suggest`)
  - `conflict_warnings(root: Path, packs: Sequence[Pack]) -> list[dict]` (`pack, pack_says, project_conflict, file`)
  - `rules_doctor(root: Path, config: Mapping) -> dict` (`packs, tool_checks, conflicts` or `error`)
  - `preset` payload keys `rule_packs`, `rule_tool_checks`; doctor `checks_details["rules"]`.

- [ ] **Step 1: Failing tests** (`tests/workflow_core/test_rules_checks.py`)

```python
"""Pack proposals for setup, read-only tool checks, and CLAUDE.md/AGENTS.md conflict warnings."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins/gin-workflow/src/scripts"))

from workflow_core.rules import load_plugin_packs  # noqa: E402
from workflow_core.rules_checks import (  # noqa: E402
    check_tool, conflict_warnings, propose_packs, rules_doctor, tool_check_report)

PLUGIN = load_plugin_packs(ROOT / "plugins/gin-workflow/src/rules")


def _repo(files: dict[str, str]) -> Path:
    root = Path(tempfile.mkdtemp())
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _pkg(*deps: str) -> str:
    return json.dumps({"dependencies": {d: "1" for d in deps}})


class TestPropose(unittest.TestCase):
    def test_react_vite(self):
        root = _repo({"package.json": json.dumps({"dependencies": {"react": "1"},
                                                  "devDependencies": {"vite": "1", "typescript": "1"}}),
                      "tsconfig.json": "{}"})
        self.assertEqual(["core", "typescript", "react"], propose_packs(root, PLUGIN))

    def test_fastapi(self):
        root = _repo({"pyproject.toml": '[project]\ndependencies=["fastapi"]\n'})
        self.assertEqual(["core", "python", "fastapi"], propose_packs(root, PLUGIN))

    def test_nextjs(self):
        root = _repo({"package.json": _pkg("next", "react")})
        self.assertEqual(["core", "typescript", "nextjs", "react"], propose_packs(root, PLUGIN))

    def test_workspace_packages_count(self):
        root = _repo({"package.json": json.dumps({"workspaces": ["apps/*"]}),
                      "apps/api/package.json": _pkg("express")})
        self.assertIn("node-api", propose_packs(root, PLUGIN))

    def test_greenfield_uses_stack_intent(self):
        root = _repo({"README.md": "# new"})
        self.assertEqual(["core", "python", "fastapi"], propose_packs(root, PLUGIN, stack_intent="FastAPI service"))
        self.assertEqual(["core", "typescript", "nextjs", "react"],
                         propose_packs(root, PLUGIN, stack_intent="Next.js app"))
        self.assertEqual(["core"], propose_packs(root, PLUGIN))


class TestToolChecks(unittest.TestCase):
    def test_tsconfig_strict(self):
        self.assertEqual("missing", check_tool(_repo({}), {"tsconfig_option": {"strict": True}}))
        self.assertEqual("missing", check_tool(_repo({"tsconfig.json": '{"compilerOptions": {}}'}),
                                               {"tsconfig_option": {"strict": True}}))
        jsonc = '{\n  // comment\n  "$schema": "https://x/y",\n  "compilerOptions": {"strict": true,},\n}\n'
        self.assertEqual("present", check_tool(_repo({"tsconfig.json": jsonc}), {"tsconfig_option": {"strict": True}}))
        self.assertEqual("unknown", check_tool(_repo({"tsconfig.json": "{oops"}), {"tsconfig_option": {"strict": True}}))
        self.assertEqual("unknown", check_tool(_repo({"tsconfig.json": '{"extends": "./base.json"}'}),
                                               {"tsconfig_option": {"strict": True}}))

    def test_pyproject_tool(self):
        self.assertEqual("missing", check_tool(_repo({"pyproject.toml": "[project]\n"}), {"pyproject_tool": "tool.ruff"}))
        self.assertEqual("present", check_tool(_repo({"pyproject.toml": "[tool.ruff]\n"}), {"pyproject_tool": "tool.ruff"}))
        self.assertEqual("unknown", check_tool(_repo({"pyproject.toml": "[tool.ruff\n"}), {"pyproject_tool": "tool.ruff"}))

    def test_eslint_rule(self):
        check = {"eslint_rule": "react-hooks/rules-of-hooks"}
        self.assertEqual("missing", check_tool(_repo({}), check))
        self.assertEqual("missing", check_tool(_repo({"eslint.config.js": "export default [];"}), check))
        self.assertEqual("present", check_tool(
            _repo({"eslint.config.js": 'import reactHooks from "eslint-plugin-react-hooks";'}), check))

    def test_file_exists_and_report_shape(self):
        self.assertEqual("present", check_tool(_repo({"a.txt": ""}), {"file_exists": "a.txt"}))
        report = tool_check_report(_repo({}), [PLUGIN["python"]])
        self.assertEqual([("python", "ruff", "missing"), ("python", "mypy", "missing")],
                         [(r["pack"], r["id"], r["status"]) for r in report])
        self.assertTrue(all(r["suggest"] for r in report))


class TestConflictsAndDoctor(unittest.TestCase):
    def test_conflict_keyword_in_claude_md(self):
        root = _repo({"CLAUDE.md": "Components use a Default Export.\n"})
        [warning] = conflict_warnings(root, [PLUGIN["react"]])
        self.assertEqual(("react", "default export", "CLAUDE.md"),
                         (warning["pack"], warning["project_conflict"], warning["file"]))

    def test_rules_doctor_uses_config(self):
        root = _repo({})
        result = rules_doctor(root, {"rules": {"packs": ["python"], "disabled": []}})
        self.assertEqual(["core", "python"], result["packs"])
        self.assertEqual({"ruff", "mypy"}, {r["id"] for r in result["tool_checks"]})
        self.assertEqual([], result["conflicts"])


if __name__ == "__main__":
    unittest.main()
```

`tests/workflow_core/test_setup_cli.py`, extend `test_preset_proposes_explicit_assignments` (temp repo is empty → greenfield → core only):

```python
            self.assertEqual(["core"], payload["rule_packs"])
            self.assertIn('rules.packs=["core"]', payload["assignments"])
            self.assertEqual([], payload["rule_tool_checks"])
```

and add:

```python
    def test_doctor_reports_rules_without_changing_health(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            self.assertEqual(0, self.run_cli(repository, "init", "--approve", "--non-interactive").returncode)
            (repository / "CLAUDE.md").write_text("Use default export for pages.\n", encoding="utf-8")
            self.assertEqual(0, self.run_cli(repository, "configure", "--approve",
                                             "--set", 'rules.packs=["core", "react"]').returncode)
            payload = json.loads(self.run_cli(repository, "doctor", "--format", "json").stdout)
            rules = payload["checks_details"]["rules"]
            self.assertEqual(["core", "react", "typescript"], sorted(rules["packs"]))
            self.assertEqual("react", rules["conflicts"][0]["pack"])
            self.assertNotIn("rules", payload["checks"])
```

- [ ] **Step 2:** Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/workflow_core/test_rules_checks.py tests/workflow_core/test_setup_cli.py -v` → FAIL (`No module named 'workflow_core.rules_checks'`, missing `rule_packs`).

- [ ] **Step 3: Implement** `workflow_core/rules_checks.py`:

```python
"""Read-only rule-pack support for setup and doctor: proposals, tool checks, conflict warnings."""

from __future__ import annotations

import json
from pathlib import Path
import re
import tomllib
from typing import Any, Mapping, Sequence

from .project_detect import _mentions, _read_json, _workspace_dirs, _workspace_globs
from .rules import Pack, RulesError, load_plugin_packs, plugin_rules_dir, rules_config

_TIER_ORDER = ("core", "language", "framework")
_ESLINT_FILES = ("eslint.config.js", "eslint.config.mjs", "eslint.config.cjs", "eslint.config.ts",
                 ".eslintrc", ".eslintrc.json", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.yml", ".eslintrc.yaml")
_JSONC_TOKENS = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.DOTALL)
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")
_CONFLICT_FILES = ("CLAUDE.md", "AGENTS.md")


def _js_deps(root: Path) -> set[str]:
    deps: set[str] = set()
    for directory in [root, *_workspace_dirs(root, _workspace_globs(root))]:
        manifest = _read_json(directory / "package.json")
        for key in ("dependencies", "devDependencies"):
            if isinstance(manifest.get(key), dict):
                deps |= set(manifest[key])
    return deps


def _py_text(root: Path) -> str:
    return "".join((root / name).read_text(encoding="utf-8", errors="replace").lower()
                   for name in ("pyproject.toml", "requirements.txt") if (root / name).is_file())


def _with_requires(chosen: set[str], plugin: Mapping[str, Pack]) -> set[str]:
    pending = list(chosen)
    while pending:
        for name in plugin[pending.pop()].requires:
            if name in plugin and name not in chosen:
                chosen.add(name)
                pending.append(name)
    return chosen


def propose_packs(root: Path, plugin: Mapping[str, Pack], *, stack_intent: str = "") -> list[str]:
    root = Path(root).resolve()
    deps, py_text, intent = _js_deps(root), _py_text(root), stack_intent.lower()
    chosen = {"core"} & set(plugin)
    for pack in plugin.values():
        detect = pack.meta.get("detect") or {}
        js_names = [str(n) for n in detect.get("package_json_deps", [])]
        py_names = [str(n) for n in detect.get("pyproject_deps", [])]
        if (any(name in deps for name in js_names)
                or any(_mentions(py_text, name) for name in py_names)
                or any((root / str(name)).exists() for name in detect.get("files_exist", []))
                or (intent and any(_mentions(intent, name.lower()) for name in (pack.id, *js_names, *py_names)))):
            chosen.add(pack.id)
    return sorted(_with_requires(chosen, plugin), key=lambda name: (_TIER_ORDER.index(plugin[name].tier), name))


def _jsonc(text: str) -> Any:
    stripped = _JSONC_TOKENS.sub(lambda m: m.group(0) if m.group(0).startswith('"') else "", text)
    return json.loads(_TRAILING_COMMA.sub(r"\1", stripped))


def check_tool(root: Path, check: Mapping[str, Any]) -> str:
    """`present` | `missing` | `unknown`; never raises on unreadable or unparseable config."""
    root = Path(root)
    kind, value = next(iter(check.items()))
    if kind == "file_exists":
        return "present" if (root / str(value)).exists() else "missing"
    if kind == "tsconfig_option":
        path = root / "tsconfig.json"
        if not path.is_file():
            return "missing"
        try:
            data = _jsonc(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            return "unknown"
        options = data.get("compilerOptions", {}) if isinstance(data, dict) else None
        if not isinstance(options, dict):
            return "unknown"
        for key, expected in dict(value).items():
            if key not in options:
                return "unknown" if "extends" in data else "missing"
            if options[key] != expected:
                return "missing"
        return "present"
    if kind == "eslint_rule":
        texts = []
        for name in _ESLINT_FILES:
            if (root / name).is_file():
                try:
                    texts.append((root / name).read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError):
                    return "unknown"
        package_config = _read_json(root / "package.json").get("eslintConfig")
        if package_config:
            texts.append(json.dumps(package_config))
        if not texts:
            return "missing"
        plugin_name = str(value).split("/")[0]
        return "present" if any(str(value) in text or plugin_name in text for text in texts) else "missing"
    if kind == "pyproject_tool":
        path = root / "pyproject.toml"
        if not path.is_file():
            return "missing"
        try:
            node: Any = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
            return "unknown"
        for part in str(value).split("."):
            if not isinstance(node, dict) or part not in node:
                return "missing"
            node = node[part]
        return "present"
    return "unknown"


def tool_check_report(root: Path, packs: Sequence[Pack]) -> list[dict[str, str]]:
    return [{"pack": pack.id, "id": str(item["id"]), "status": check_tool(root, item["check"]),
             "suggest": str(item.get("suggest", ""))}
            for pack in packs for item in (pack.meta.get("tool_checks") or [])]


def conflict_warnings(root: Path, packs: Sequence[Pack]) -> list[dict[str, str]]:
    warnings = []
    for name in _CONFLICT_FILES:
        path = Path(root) / name
        text = path.read_text(encoding="utf-8", errors="replace").lower() if path.is_file() else ""
        for pack in packs:
            for item in pack.meta.get("conflict_keywords") or []:
                if text and str(item["project_conflict"]).lower() in text:
                    warnings.append({"pack": pack.id, "pack_says": str(item["pack_says"]),
                                     "project_conflict": str(item["project_conflict"]), "file": name})
    return warnings


def rules_doctor(root: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    try:
        plugin = load_plugin_packs(plugin_rules_dir())
    except RulesError as error:
        return {"error": str(error)}
    names, disabled = rules_config(config)
    chosen = _with_requires({n for n in ("core", *names) if n in plugin and n not in disabled}, plugin) - disabled
    packs = [plugin[name] for name in sorted(chosen, key=lambda n: (_TIER_ORDER.index(plugin[n].tier), n))]
    return {"packs": [pack.id for pack in packs], "tool_checks": tool_check_report(root, packs),
            "conflicts": conflict_warnings(root, packs)}
```

  `project.py` `preset_assignments`: add keyword `rule_packs: Sequence[str] = ()` (import `Sequence` from `typing`) and, before the `verify.checks` loop, `if rule_packs: values["rules.packs"] = list(rule_packs)`.

  `setup_service.py` `preset`:

```python
    from .rules import load_plugin_packs, plugin_rules_dir
    from .rules_checks import propose_packs, tool_check_report

    root = Path(repository).resolve()
    detected = detect_project(root)
    plugin = load_plugin_packs(plugin_rules_dir())
    rule_packs = propose_packs(root, plugin, stack_intent=stack_intent)
    try:
        assignments = preset_assignments(
            stage=project_stage or detected["stage"], shape=project_shape or detected["shape"],
            rigor=rigor or detected["suggested_rigor"], provider_mode=provider_mode or "single",
            monorepo=monorepo or detected["monorepo"], stack_intent=stack_intent,
            verify_commands=detected["verify_commands"], packages=tuple(detected["packages"]),
            rule_packs=rule_packs)
    except ValueError as error:
        raise SetupError(str(error)) from error
    missing = [key for key, value in detected["verify_commands"].items() if not value and key != "e2e"]
    tool_checks = [item for item in tool_check_report(root, [plugin[name] for name in rule_packs])
                   if item["status"] != "present"]
    return {"status": "proposed", "assignments": assignments, "detected": detected,
            "rule_packs": rule_packs, "rule_tool_checks": tool_checks,
            "warnings": [f"no {key} command detected" for key in missing], "actions": []}
```

  `setup_service.py` `doctor`, after the review-ledger block and before `healthy = all(checks.values())`:

```python
    if checks["configuration"]:
        from .rules_checks import rules_doctor

        rules_detail = rules_doctor(root, resolve_effective_config(root, write=False).config.to_dict())
        checks_details["rules"] = rules_detail
        for item in rules_detail.get("tool_checks", []):
            if item["status"] == "missing":
                actions.append(f"rules: add {item['id']} for pack {item['pack']} (suggestion in checks_details.rules)")
        for item in rules_detail.get("conflicts", []):
            actions.append(f"rules: {item['file']} says '{item['project_conflict']}', pack {item['pack']} says "
                           f"'{item['pack_says']}'; the project wins, record the divergence")
```

  `skills/setup/SKILL.md`, Quick setup "Then" step 2 becomes:
  `2. Run \`init --dry-run\` with the harness and every assignment. Present both \`configuration\` and \`provider_configuration\`, the proposed \`rule_packs\` (the user may add or remove packs as an extra \`--set rules.packs=[...]\`), each \`rule_tool_checks\` item with its \`suggest\` snippet (suggestions only; setup never edits lint or type configs), the exact files/actions, and any validation error. Do not write on dry-run.`

- [ ] **Step 4:** Run the Step 2 command → PASS. Full suite → `OK`.

- [ ] **Step 5:** Commit `feat(rules): pack proposals, tool checks, and conflict warnings in setup and doctor`.

### Track 5: Inject rules into execute, quick, review, and the agents

**Metadata:**
- Dependencies: Track 2
- Provider role: docs
- Reasoning: low
- Model guidance: cheap_simple
- Estimated complexity: low

**Files:**
- Modify: `skills/execute/SKILL.md` (§2 Implement), `skills/quick/SKILL.md` (step 3), `skills/review/SKILL.md` (Requesting step 2, Reviewing step 3), `agents/developer.md` (Inputs), `agents/code-reviewer.md` (Phase 1)
- Test: `tests/workflow_core/test_token_budget.py` (new test)

**Interfaces:**
- Consumes: `gin-workflow rules --files <paths...>` (Track 2).

- [ ] **Step 1: Failing test**, add to `TestBudgetLimits` in `tests/workflow_core/test_token_budget.py`:

```python
    def test_rules_injected_only_into_implement_and_review_paths(self):
        injected = ("skills/execute/SKILL.md", "skills/quick/SKILL.md", "skills/review/SKILL.md",
                    "agents/developer.md", "agents/code-reviewer.md")
        for relative in injected:
            with self.subTest(path=relative):
                self.assertIn("gin-workflow rules --files", (SRC / relative).read_text(encoding="utf-8"))
        for stage in ("discuss", "plan", "orchestrate", "verify", "ship"):
            with self.subTest(stage=stage):
                self.assertNotIn("gin-workflow rules", (SRC / "skills" / stage / "SKILL.md").read_text(encoding="utf-8"))
```

- [ ] **Step 2:** Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/workflow_core/test_token_budget.py -v` → FAIL on the five injected paths.

- [ ] **Step 3: Edit text** (exact lines):
  - `skills/execute/SKILL.md` §2, insert after the shape-appendix bullet:
    `- Run \`gin-workflow rules --files <scope files>\` and give its output to the \`developer\` agent (or follow it when executing directly). Rules never widen the scope.`
  - `skills/quick/SKILL.md` step 3 becomes:
    `3. Run \`gin-workflow rules --files <files to change>\` and follow its output. Implement the change. Write a failing test first when behavior changes.`
  - `skills/review/SKILL.md` Requesting step 2, append:
    ` Include the output of \`gin-workflow rules --files <reviewed files>\` as the rules checklist.`
  - `skills/review/SKILL.md` Reviewing step 3, append:
    ` Check the rules checklist, \`critical\` and \`high\` first; cite a violation as \`<pack>#<anchor>\`, and record a \`critical\` violation at severity \`IMPORTANT\` or higher.`
  - `agents/developer.md` Inputs, add item 5:
    `5. Follow the rules block the orchestrator passed (\`gin-workflow rules --files <scope>\`); run that command yourself when none was passed.`
  - `agents/code-reviewer.md` Phase 1, add item 5:
    `5. **Rules checklist**: Use the rules block from the request, or run \`gin-workflow rules --files <changed files>\`. Check \`critical\` and \`high\` rules first and cite violations as \`<pack>#<anchor>\`.`

- [ ] **Step 4:** Run the Step 2 command → PASS (stage chains stay ≤ 12,000; quick ≤ 8,000; agents ≤ 4,000). Full suite → `OK`.

- [ ] **Step 5:** Commit `feat(rules): inject rules into execute, quick, review, developer, and code-reviewer`.

## Integration
- **Branch**: `feat/best-practice-rules` (worktree under `.planning/worktrees/`), based on `spec/d-best-practice-rules`.
- **Merge strategy**: sequential (Tracks 1 → 2 → 3 → 4, Track 5 after Track 2).

## Validation
Spec acceptance criteria:
- [ ] 1. Seven packs within budget, bodies only non-tooling rules, valid impact and anchor per bullet — `test_rule_packs.py`, `test_token_budget.py::test_rule_pack_bodies_within_budget`.
- [ ] 2. `rules --files` returns only relevant packs in precedence order, project rules first, no `## Why`, impact trimming, `critical` kept — `test_rules.py`.
- [ ] 3. Injection only in `execute`, `/quick`, `review` (+ agents); reviewer prioritizes `critical`/`high` — `test_token_budget.py::test_rules_injected_only_into_implement_and_review_paths`.
- [ ] 4. Setup proposes packs; doctor reports missing tooling with snippets and conflicts, read-only — `test_rules_checks.py`, `test_setup_cli.py`.
- [ ] 5. Schema 2.5 with a defaults-only migration from 2.4 — `test_schema_2_5.py`.
- [ ] 6. Full suite `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py` → `OK`; token budget test passes; `bash tests/install_smoke_test.sh` passes (dists for claude-code, codex, antigravity include `rules/`).

## Risks
- `eslint_rule` is a static substring scan; a config that enables the plugin under an alias reports `missing`. Acceptable: doctor only suggests.
- `node-api` applies to every `.ts`/`.js` file, so a Next.js + Express repo loads it for frontend `.ts` files too; trimming keeps the cost bounded. Narrow `applies_to` in a later pack revision if reviews show noise.
- Installed launcher must be refreshed after merge (ship step 8) or `gin-workflow rules` will be missing on this host.

## Notes
- Parent Bead (deliverable) remains open until a human-confirmed merge; track beads close after tests and review pass.
- Provider roles and reasoning are portable; concrete models are resolved at orchestration.

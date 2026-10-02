# Project Profile Bootstrap, Frontend Support, Quick Path (Sub-project B+C) Implementation Plan

> **For agentic workers:** Use the `execute` stage per track. Authoritative task state is tracked in Beads; checkboxes give the visual step breakdown. Commit and push freely on the feature branch; never commit to `master`; PR/merge needs explicit approval.

**Goal:** Setup classifies the project (stage × shape, monorepo), asks ≤ 5 questions in single-provider mode, writes explicit presets and detected verify commands, lists real models from provider CLIs, supports single-provider independent review, adds a `/quick` fast path, replaces `full-stack-developer`/`codebase-mapper` with a `developer` agent plus shape appendices, and ships a benchmark protocol.

**Architecture:** Deterministic Python does detection (`project_detect.py`), presets (`project.py`), model listing (`native_cli.list_models`), quick-path gating (`gin-workflow quick-check`), and exposes the resolved project block through `gin-workflow state --format json`; skills only ask questions and pass `--set` assignments. Config schema 2.4 is read-compatible with 2.3; a missing `project:` section resolves to today's behavior.

**Tech Stack:** Python 3 stdlib + PyYAML/jsonschema (already required); `unittest`; Markdown skills/agents; bash/PowerShell installers.

**Spec:** `.planning/specs/2026-10-01-project-profile-bootstrap-design.md` (workflow id `project-profile-bootstrap`, `requirement_confirmed` recorded).

## Global Constraints

- Test command (repo root): `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py` — baseline 2026-10-02: `Ran 553 tests … OK`.
- Install smoke test: `bash tests/install_smoke_test.sh` (PowerShell smoke cannot run here: no `pwsh`; keep it consistent by reading).
- Budgets (from A, `tests/workflow_core/test_token_budget.py`): each stage chain ≤ 12,000 chars; `quick` chain ≤ 8,000; `agents/*.md` ≤ 4,000; `skills/gin-*/SKILL.md` ≤ 6,000; descriptions ≤ 4,000; no `ContextManifest|ArtifactRegistry|ApprovalDecision|load_effective_config` in skills; no `commands/<name>.md` shadowing a skill; every lifecycle stage skill keeps its `## Before you start` block.
- `docs/<name>.md` ↔ `plugins/gin-workflow/src/references/<name>.md` canonical pairs stay byte-identical.
- Antigravity's executable is `agy`; resolve it only through `executable_resolver.PROVIDER_EXE_ALIASES`.
- Worker-result / evidence schema `"2.3"` constants in `workflow_providers/{contracts,evidence,worker_dispatch,routed_worker}.py` and `manifests.py`/`models.py` are a separate contract: do **not** change them.
- Portable config forbids keys named `commands`/`*_commands` (`configuration._validate_portable`, provider-command guard). The spec's `verify.commands` is therefore stored as **`verify.checks`** (`project.packages[].verify.checks`); JSON outputs keep the field name `verify_commands`. The guard itself is not relaxed.
- `legacy` stage is never auto-assigned. Detection writes nothing; only the approved `init`/`configure` writes.
- Git: commit/push on `feat/project-profile-bootstrap`; never commit to `master`.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`: brainstorm `high_reasoning`; design `high_reasoning`; plan `standard_impl`; implement `standard_impl`; verify `standard_impl`; review `high_reasoning`; docs `cheap_simple`
- `override_rule`: Track 1 (schema/migration compatibility) and Track 5 (review independence) use `high_reasoning`.

## Requirement Analysis
- Problem: setup detects only harness markers; 9 routing questions for every user; model ids typed from memory; single-provider review fails without self-review; no frontend specialization; every change takes the full lifecycle; codebase-mapper duplicates codegraph.
- Success: spec acceptance criteria 1–8 (see Validation).
- Constraints: existing 2.3 repos keep working unchanged; skills never infer presets at runtime; detection is deterministic.
- Non-goals: rules packs (D), scaffolding, automated benchmark runs, lifecycle-gate changes beyond `quick.completed`.

## Approach Options
### Option 1: Code does detection/presets/gating; skills pass `--set` (selected)
- Pros: deterministic, testable, small skills. Cons: more CLI surface (`setup preset`, `setup models`, `quick-check`).
### Option 2: Skills infer presets and detection by reading files
- Cons: nondeterministic, untestable, larger token load per setup.
### Recommended Approach
- Option 1.

## Scope
- In: `plugins/gin-workflow/src/{scripts/workflow_core,scripts/workflow_providers/native_cli.py,skills,agents,references}`, `install.sh`, `install.ps1`, `tests/`, `docs/benchmarks/`, `scripts/benchmark/` (repo root, not packaged), `README.md`.
- Out: `docs/*` canonical pair content (except as needed to keep pairs identical — none planned), rules (D), team mode (E).

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks share setup_service.py, cli.py, schemas, skills and the budget test; sequential direct execution avoids conflicts.
```

## File Structure

| Path | Responsibility |
|---|---|
| `scripts/workflow_core/project.py` (new) | Enums, `ProjectSettings`, `project_settings(config)`, `preset_assignments(...)`, `quick_verify_commands(...)` |
| `scripts/workflow_core/project_detect.py` (new) | `detect_project(root)`: stage, shape, monorepo, packages, package manager, verify commands, providers, codegraph |
| `scripts/workflow_core/schemas.py` | Accept 2.3/2.4; schema for `project`, `provider_mode`, `verify`, `quick`, `routing.review.independence` |
| `scripts/workflow_core/configuration.py` | Read-compatible versions; built-ins at 2.4 |
| `scripts/workflow_core/migrations.py` | `CURRENT_VERSION = "2.4"`, 2.3→2.4 (versions only) |
| `scripts/workflow_core/setup_service.py` | `detect` adds `project`; new `preset`, `models`; doctor checks |
| `scripts/workflow_core/cli.py` | Version 2.4; args for `preset`/`models`; route `quick-check` |
| `scripts/workflow_core/lifecycle_cli.py` | `state` adds `project`, `recent_quick`; `record quick-completed`; `quick-check` |
| `scripts/workflow_core/review_coordinator.py` | `independence` = `provider` \| `session` |
| `scripts/workflow_providers/native_cli.py` | `list_models(provider, runner=None)` |
| `scripts/workflow_providers/registry.py:178,184` | Treat config schema 2.3 and 2.4 alike |
| `scripts/workflow_core/budget.py` | `STAGES` gains `quick` |
| `skills/{setup,quick,review,verify,execute,progress,tech-doc}/SKILL.md` | Quick setup, `/quick`, independence, verify per rigor, developer agent, quick in progress, slim tech-doc |
| `agents/developer.md` (new), `agents/{full-stack-developer,codebase-mapper}.md` (delete), `agents/{docs-writer,agent-researcher}.md` | Implementer + reference cleanup |
| `references/shape-frontend.md`, `references/shape-backend.md` (new) | Shape appendices ≤ 1,500 chars |
| `docs/benchmarks/README.md`, `scripts/benchmark/summarize_usage.py` (new) | Benchmark protocol + summarizer |
| `install.sh`, `install.ps1`, `tests/install_smoke_test.{sh,ps1}` | Launcher 2.4; agent list |

## Tasks

### Track 1: Config schema 2.4 with 2.3 read-compatibility and project settings

**Metadata:**
- Dependencies: none
- Provider role: backend
- Reasoning: high
- Model guidance: high_reasoning
- Estimated complexity: medium

**Files:**
- Create: `plugins/gin-workflow/src/scripts/workflow_core/project.py`
- Modify: `workflow_core/schemas.py:10-120`, `workflow_core/configuration.py:26-36,179-197`, `workflow_core/migrations.py:15,53-66`, `workflow_core/cli.py:18`, `workflow_providers/registry.py:178,184`, `install.sh:12`, `install.ps1` (launcher version), `tests/install_smoke_test.sh` / `.ps1` (`2.3` launcher paths → `2.4`)
- Test: `tests/workflow_core/test_project_settings.py` (new); update version assertions in `tests/workflow_core/{test_configuration,test_migrations,test_setup_cli,test_bundles,test_end_to_end,test_lifecycle_cli,test_provider_config}.py` only where they assert the *config/setup-CLI* version.

**Interfaces:**
- Produces: `SUPPORTED_CONFIG_VERSIONS = ("2.3", "2.4")`; `project.ProjectSettings(stage, shape, monorepo, rigor, stack_intent, packages, provider_mode, verify_commands, independence, worktree, review, review_ledger, max_cycles, quick_max_files)`; `project.project_settings(config: Mapping) -> ProjectSettings`.

- [ ] **Step 1: Failing tests** (`tests/workflow_core/test_project_settings.py`)

```python
"""Project settings resolution and schema 2.4 compatibility."""

from __future__ import annotations

import unittest

from workflow_core.configuration import ConfigValidationError, validate_portable_config
from workflow_core.migrations import migrate_config
from workflow_core.project import project_settings


class TestProjectSettings(unittest.TestCase):
    def test_missing_project_section_keeps_legacy_behavior(self):
        settings = project_settings({"schema_version": "2.3"})
        self.assertEqual(("fullstack", "standard", "multi", "provider"),
                         (settings.shape, settings.rigor, settings.provider_mode, settings.independence))
        self.assertEqual({}, settings.verify_commands)

    def test_explicit_project_values_are_read(self):
        settings = project_settings({
            "schema_version": "2.4",
            "project": {"stage": "brownfield", "shape": "frontend", "rigor": "easy", "worktree": "never"},
            "provider_mode": "single",
            "verify": {"checks": {"lint": "pnpm run lint", "e2e": ""}},
            "routing": {"review": {"independence": "session", "max_cycles": 2}},
            "quick": {"max_files": 7},
        })
        self.assertEqual("frontend", settings.shape)
        self.assertEqual("session", settings.independence)
        self.assertEqual({"lint": "pnpm run lint"}, settings.verify_commands)
        self.assertEqual(7, settings.quick_max_files)

    def test_both_versions_validate_and_bad_enum_fails(self):
        validate_portable_config({"schema_version": "2.3"})
        validate_portable_config({"schema_version": "2.4", "project": {"shape": "frontend"}})
        with self.assertRaises(ConfigValidationError):
            validate_portable_config({"schema_version": "2.4", "project": {"shape": "mobile"}})
        with self.assertRaises(ConfigValidationError):
            validate_portable_config({"schema_version": "2.4", "routing": {"review": {"independence": "team"}}})

    def test_migration_2_3_to_2_4_only_bumps_versions(self):
        source = {"schema_version": "2.3", "workflow_version": "2.3", "setup_cli_version": "2.3",
                  "routing": {"review": {"max_cycles": 3}}}
        migrated = migrate_config(source, "2.4")
        self.assertEqual("2.4", migrated["schema_version"])
        self.assertEqual({"review": {"max_cycles": 3}}, migrated["routing"])
        self.assertNotIn("project", migrated)
```

- [ ] **Step 2:** Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/workflow_core/test_project_settings.py -v` → FAIL (`No module named 'workflow_core.project'`).

- [ ] **Step 3: Schema.** In `schemas.py`: `SUPPORTED_SCHEMA_VERSION = "2.4"`, `SUPPORTED_CONFIG_VERSIONS = ("2.3", "2.4")`; config `schema_version` becomes `{"enum": list(SUPPORTED_CONFIG_VERSIONS)}`; provenance keeps `{"enum": [...]}` too. Add top-level properties:

```python
_CHECKS = {"type": "object", "propertyNames": {"enum": ["lint", "typecheck", "test", "build", "e2e"]},
             "additionalProperties": {"type": "string"}}
...
        "project": {
            "type": "object",
            "properties": {
                "stage": {"enum": ["greenfield", "brownfield", "legacy"]},
                "shape": {"enum": ["frontend", "backend", "fullstack", "library"]},
                "monorepo": {"type": "boolean"},
                "rigor": {"enum": ["easy", "standard", "strict"]},
                "stack_intent": {"type": "string"},
                "worktree": {"enum": ["never", "parallel", "always"]},
                "review": {"enum": ["self_check", "independent"]},
                "review_ledger": {"type": "boolean"},
                "packages": {"type": "array", "items": {"type": "object", "required": ["path", "shape"],
                    "properties": {"path": {"type": "string", "minLength": 1},
                                   "shape": {"enum": ["frontend", "backend", "fullstack", "library"]},
                                   "verify": {"type": "object", "properties": {"checks": _CHECKS},
                                              "additionalProperties": False}},
                    "additionalProperties": False}},
            },
            "additionalProperties": False,
        },
        "provider_mode": {"enum": ["single", "multi"]},
        "verify": {"type": "object", "properties": {"checks": _CHECKS}, "additionalProperties": False},
        "quick": {"type": "object", "properties": {"max_files": {"type": "integer", "minimum": 1}},
                  "additionalProperties": False},
```

and in `routing.review.properties` add `"independence": {"enum": ["provider", "session"]}`.

- [ ] **Step 4: Configuration.** `SUPPORTED_WORKFLOW_VERSION = SUPPORTED_SETUP_CLI_VERSION = "2.4"`; in `validate_portable_config` replace the three equality checks with membership in `SUPPORTED_CONFIG_VERSIONS` (imported from `schemas`) and keep the error text `unsupported schema_version …; expected one of ('2.3', '2.4')`.

- [ ] **Step 5: Migration.** `migrations.CURRENT_VERSION = "2.4"`; add

```python
def _migrate_2_3_to_2_4(config: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(config)
    migrated["schema_version"] = "2.4"
    migrated["workflow_version"] = "2.4"
    migrated["setup_cli_version"] = "2.4"
    return migrated
```

registered as `("2.3", "2.4")`; `migrate_config` also accepts `("2.2","2.4")` by chaining: replace the single lookup with a loop that applies successive registered steps until `target_version`.

- [ ] **Step 6: Project settings module** `workflow_core/project.py`:

```python
"""Resolved project profile: stage x shape, rigor presets, verify commands (schema 2.4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

STAGES = ("greenfield", "brownfield", "legacy")
SHAPES = ("frontend", "backend", "fullstack", "library")
RIGORS = ("easy", "standard", "strict")
VERIFY_KEYS = ("lint", "typecheck", "test", "build", "e2e")
RIGOR_PRESETS: dict[str, dict[str, Any]] = {
    "easy": {"worktree": "never", "review": "self_check", "review_ledger": False, "max_cycles": 2},
    "standard": {"worktree": "parallel", "review": "independent", "review_ledger": False, "max_cycles": 2},
    "strict": {"worktree": "always", "review": "independent", "review_ledger": True, "max_cycles": 2},
}


@dataclass(frozen=True)
class ProjectSettings:
    stage: str = "brownfield"
    shape: str = "fullstack"
    monorepo: bool = False
    rigor: str = "standard"
    stack_intent: str = ""
    packages: tuple[Mapping[str, Any], ...] = ()
    provider_mode: str = "multi"
    verify_commands: Mapping[str, str] = field(default_factory=dict)
    independence: str = "provider"
    worktree: str = "parallel"
    review: str = "independent"
    review_ledger: bool = False
    max_cycles: int = 2
    quick_max_files: int = 5

    def to_dict(self) -> dict[str, Any]:
        return {name: (list(value) if isinstance(value, tuple) else dict(value) if isinstance(value, Mapping) else value)
                for name, value in self.__dict__.items()}


def _section(config: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    current: Any = config
    for key in keys:
        current = current.get(key, {}) if isinstance(current, Mapping) else {}
    return current if isinstance(current, Mapping) else {}


def project_settings(config: Mapping[str, Any]) -> ProjectSettings:
    """Resolve the project block; a config without `project:` keeps pre-2.4 behavior."""
    project = _section(config, "project")
    review = _section(config, "routing", "review")
    rigor = str(project.get("rigor", "standard"))
    preset = RIGOR_PRESETS.get(rigor, RIGOR_PRESETS["standard"])
    commands = {k: str(v) for k, v in _section(config, "verify", "checks").items() if k in VERIFY_KEYS and str(v).strip()}
    return ProjectSettings(
        stage=str(project.get("stage", "brownfield")),
        shape=str(project.get("shape", "fullstack")),
        monorepo=bool(project.get("monorepo", False)),
        rigor=rigor,
        stack_intent=str(project.get("stack_intent", "")),
        packages=tuple(project.get("packages", ()) or ()),
        provider_mode=str(config.get("provider_mode", "multi")),
        verify_commands=commands,
        independence=str(review.get("independence", "provider")),
        worktree=str(project.get("worktree", preset["worktree"])),
        review=str(project.get("review", preset["review"])),
        review_ledger=bool(project.get("review_ledger", preset["review_ledger"])),
        max_cycles=int(review.get("max_cycles", preset["max_cycles"])),
        quick_max_files=int(_section(config, "quick").get("max_files", 5)),
    )
```

- [ ] **Step 7: Versions elsewhere.** `cli.CLI_VERSION = "2.4"`; `install.sh` `LAUNCHER_VERSION="2.4"` and the matching PowerShell constant; smoke tests' `2.3` launcher paths/version strings → `2.4`; `registry.py:178,184` `== "2.3"` → `in ("2.3", "2.4")`. Run `grep -rn '"2\.3"' plugins/gin-workflow/src/scripts/workflow_core` and confirm the only remaining hits are `SUPPORTED_CONFIG_VERSIONS`, `manifests.py`, `models.py` (worker contracts).

- [ ] **Step 8:** Run Track test → PASS; full suite: fix only assertions that check the *config/setup CLI* version (e.g. `test_reports_current_setup_cli_version`, migration targets, init writes `2.4`); worker/evidence `2.3` assertions stay. Smoke test OK.

### Track 2: Deterministic project detection

**Metadata:**
- Dependencies: Track 1
- Provider role: backend
- Reasoning: medium
- Model guidance: standard_impl
- Estimated complexity: medium

**Files:**
- Create: `workflow_core/project_detect.py`, `tests/workflow_core/test_project_detect.py`
- Modify: `workflow_core/setup_service.py:76-90` (`detect` adds `"project": detect_project(root)`)

**Interfaces:**
- Produces: `detect_project(root: Path, *, which=shutil.which) -> dict` with keys `stage, shape, monorepo, package_manager, stack, packages, verify_commands, suggested_rigor, providers, codegraph`.

- [ ] **Step 1: Failing tests** — build fixtures in temp dirs:

```python
"""Deterministic project detection fixtures."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from workflow_core.project_detect import detect_project


def _repo(files: dict[str, str]) -> Path:
    root = Path(tempfile.mkdtemp())
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _pkg(deps=(), dev=(), scripts=None, **extra) -> str:
    return json.dumps({"dependencies": {d: "1" for d in deps}, "devDependencies": {d: "1" for d in dev},
                       "scripts": scripts or {}, **extra})


NO_TOOLS = lambda name: None  # noqa: E731


class TestDetectProject(unittest.TestCase):
    def test_empty_repo_is_greenfield(self):
        result = detect_project(_repo({"README.md": "# x"}), which=NO_TOOLS)
        self.assertEqual(("greenfield", "easy"), (result["stage"], result["suggested_rigor"]))

    def test_react_vite_is_frontend_with_pnpm_scripts(self):
        root = _repo({"package.json": _pkg(["react", "react-dom"], ["vite", "typescript"],
                                           {"lint": "eslint .", "test": "vitest", "build": "vite build"}),
                      "pnpm-lock.yaml": "", "tsconfig.json": "{}", "src/main.tsx": ""})
        result = detect_project(root, which=NO_TOOLS)
        self.assertEqual(("brownfield", "frontend", "pnpm"), (result["stage"], result["shape"], result["package_manager"]))
        self.assertEqual({"lint": "pnpm run lint", "typecheck": "pnpm exec tsc --noEmit", "test": "pnpm run test",
                          "build": "pnpm run build", "e2e": ""}, result["verify_commands"])

    def test_fastapi_is_backend_with_uv_tools(self):
        root = _repo({"pyproject.toml": '[project]\ndependencies=["fastapi"]\n[tool.ruff]\n[tool.mypy]\n[tool.pytest.ini_options]\n',
                      "uv.lock": "", "app/main.py": ""})
        result = detect_project(root, which=NO_TOOLS)
        self.assertEqual(("backend", "uv"), (result["shape"], result["package_manager"]))
        self.assertEqual("uv run ruff check .", result["verify_commands"]["lint"])
        self.assertEqual("uv run mypy .", result["verify_commands"]["typecheck"])
        self.assertEqual("uv run pytest", result["verify_commands"]["test"])

    def test_next_plus_express_is_fullstack(self):
        root = _repo({"package.json": _pkg(["next", "react", "express"]), "package-lock.json": "{}"})
        self.assertEqual("fullstack", detect_project(root, which=NO_TOOLS)["shape"])

    def test_pnpm_workspace_is_monorepo_with_per_package_shapes(self):
        root = _repo({"package.json": _pkg(), "pnpm-workspace.yaml": "packages:\n  - 'apps/*'\n",
                      "pnpm-lock.yaml": "",
                      "apps/web/package.json": _pkg(["react"], scripts={"test": "vitest"}),
                      "apps/api/package.json": _pkg(["fastify"])})
        result = detect_project(root, which=NO_TOOLS)
        self.assertTrue(result["monorepo"])
        self.assertEqual("fullstack", result["shape"])
        shapes = {p["path"]: p["shape"] for p in result["packages"]}
        self.assertEqual({"apps/api": "backend", "apps/web": "frontend"}, shapes)

    def test_library_and_default_npm_test_script_ignored(self):
        root = _repo({"package.json": _pkg(main="index.js", scripts={"test": 'echo "Error: no test specified" && exit 1'}),
                      "package-lock.json": "{}", "index.js": ""})
        result = detect_project(root, which=NO_TOOLS)
        self.assertEqual("library", result["shape"])
        self.assertEqual("", result["verify_commands"]["test"])

    def test_legacy_is_never_auto_assigned_and_providers_use_agy(self):
        found = {"claude": "/bin/claude", "agy": "/usr/local/bin/agy", "codegraph": "/bin/codegraph"}
        result = detect_project(_repo({"package.json": _pkg(["express"]), "package-lock.json": "{}"}),
                                which=lambda name: found.get(name))
        self.assertNotEqual("legacy", result["stage"])
        self.assertEqual({"claude": True, "codex": False, "antigravity": True},
                         {k: bool(v) for k, v in result["providers"].items()})
        self.assertEqual({"installed": True, "indexed": False, "stale": False}, result["codegraph"])
```

- [ ] **Step 2:** Run → FAIL (module missing).

- [ ] **Step 3: Implement** `workflow_core/project_detect.py`:

```python
"""Deterministic, read-only project detection for setup (no LLM, no writes)."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Callable

from .executable_resolver import PROVIDER_EXE_ALIASES

FRONTEND_JS = {"react", "vue", "svelte", "next", "nuxt", "@angular/core", "solid-js", "preact", "astro"}
BACKEND_JS = {"express", "@nestjs/core", "fastify", "koa", "hono"}
BACKEND_PY = {"fastapi", "django", "flask"}
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".go", ".rs", ".java", ".rb"}
SKIP_DIRS = {".git", "node_modules", ".agent-workflow", ".planning", ".venv", "dist", "build"}
NPM_DEFAULT_TEST = "no test specified"
EXEC_PREFIX = {"npm": "npx", "pnpm": "pnpm exec", "yarn": "yarn", "bun": "bunx"}
RUN_PREFIX = {"uv": "uv run ", "poetry": "poetry run ", "pip": ""}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _js_pm(root: Path) -> str:
    for lock, pm in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"), ("bun.lock", "bun")):
        if (root / lock).exists():
            return pm
    return "npm"


def _py_pm(root: Path) -> str:
    return "uv" if (root / "uv.lock").exists() else "poetry" if (root / "poetry.lock").exists() else "pip"


def _empty_commands() -> dict[str, str]:
    return {"lint": "", "typecheck": "", "test": "", "build": "", "e2e": ""}


def _js_package(directory: Path, pm: str) -> tuple[str | None, dict[str, str], list[str]]:
    manifest = _read_json(directory / "package.json")
    deps = {**manifest.get("dependencies", {}), **manifest.get("devDependencies", {})}
    front, back = bool(FRONTEND_JS & set(deps)), bool(BACKEND_JS & set(deps))
    shape = "fullstack" if front and back else "frontend" if front else "backend" if back else (
        "library" if ("main" in manifest or "exports" in manifest or "bin" in manifest) and not manifest.get("private") else None)
    scripts = manifest.get("scripts", {}) if isinstance(manifest.get("scripts"), dict) else {}
    commands = _empty_commands()
    run = lambda name: f"{pm} run {name}"  # noqa: E731
    if "lint" in scripts:
        commands["lint"] = run("lint")
    typecheck = next((s for s in ("typecheck", "type-check") if s in scripts), None)
    if typecheck:
        commands["typecheck"] = run(typecheck)
    elif (directory / "tsconfig.json").exists() and "typescript" in deps:
        commands["typecheck"] = f"{EXEC_PREFIX[pm]} tsc --noEmit"
    if "test" in scripts and NPM_DEFAULT_TEST not in str(scripts["test"]):
        commands["test"] = run("test")
    if "build" in scripts:
        commands["build"] = run("build")
    e2e = next((s for s in ("test:e2e", "e2e") if s in scripts), None)
    if e2e:
        commands["e2e"] = run(e2e)
    stack = sorted(name for name in deps if name in FRONTEND_JS | BACKEND_JS | {"typescript", "vite"})
    return shape, commands, stack


def _py_package(root: Path, pm: str) -> tuple[str | None, dict[str, str], list[str]]:
    text = ""
    for name in ("pyproject.toml", "requirements.txt"):
        if (root / name).is_file():
            text += (root / name).read_text(encoding="utf-8", errors="replace").lower()
    if not text:
        return None, _empty_commands(), []
    found = sorted(dep for dep in BACKEND_PY if re.search(rf"\b{dep}\b", text))
    shape = "backend" if found else ("library" if "[project]" in text else None)
    prefix = RUN_PREFIX[pm]
    commands = _empty_commands()
    if "ruff" in text:
        commands["lint"] = f"{prefix}ruff check ."
    if "mypy" in text:
        commands["typecheck"] = f"{prefix}mypy ."
    if "pytest" in text:
        commands["test"] = f"{prefix}pytest"
    return shape, commands, found


def _workspace_globs(root: Path) -> list[str]:
    globs: list[str] = []
    workspace = root / "pnpm-workspace.yaml"
    if workspace.is_file():
        globs += re.findall(r"-\s*['\"]?([^'\"\n]+)['\"]?", workspace.read_text(encoding="utf-8"))
    workspaces = _read_json(root / "package.json").get("workspaces")
    if isinstance(workspaces, dict):
        workspaces = workspaces.get("packages")
    if isinstance(workspaces, list):
        globs += [str(item) for item in workspaces]
    return globs


def _combine(shapes: list[str]) -> str:
    kinds = set(shapes)
    if {"frontend", "backend"} <= kinds or "fullstack" in kinds:
        return "fullstack"
    return next(iter(kinds)) if len(kinds) == 1 else "fullstack"


def _source_count(root: Path, limit: int = 5) -> int:
    count = 0
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file() and path.suffix in SOURCE_SUFFIXES:
            count += 1
            if count >= limit:
                break
    return count


def _codegraph(root: Path, which: Callable[[str], str | None]) -> dict[str, bool]:
    index = root / ".codegraph"
    indexed = index.is_dir()
    stale = False
    if indexed:
        newest = max((p.stat().st_mtime for p in index.rglob("*") if p.is_file()), default=0.0)
        head = subprocess.run(["git", "log", "-1", "--format=%ct"], cwd=root, capture_output=True, text=True, check=False)
        stale = head.returncode == 0 and head.stdout.strip().isdigit() and newest < int(head.stdout.strip())
    return {"installed": which("codegraph") is not None, "indexed": indexed, "stale": stale}


def detect_project(root: Path, *, which: Callable[[str], str | None] = shutil.which) -> dict[str, Any]:
    root = Path(root).resolve()
    manifests = [n for n in ("package.json", "pyproject.toml", "requirements.txt", "go.mod", "Cargo.toml") if (root / n).is_file()]
    shape: str | None = None
    commands, stack, pm, packages = _empty_commands(), [], "", []
    if (root / "package.json").is_file():
        pm = _js_pm(root)
        shape, commands, stack = _js_package(root, pm)
    elif (root / "pyproject.toml").is_file() or (root / "requirements.txt").is_file():
        pm = _py_pm(root)
        shape, commands, stack = _py_package(root, pm)
    elif (root / "go.mod").is_file():
        pm, shape, commands = "go", "backend", {**_empty_commands(), "test": "go test ./...", "build": "go build ./..."}
    elif (root / "Cargo.toml").is_file():
        cargo = (root / "Cargo.toml").read_text(encoding="utf-8")
        pm = "cargo"
        shape = "library" if "[lib]" in cargo and not (root / "src/main.rs").exists() else "backend"
        commands = {**_empty_commands(), "lint": "cargo clippy", "test": "cargo test", "build": "cargo build"}
    globs = _workspace_globs(root)
    monorepo = bool(globs) or (root / "turbo.json").is_file() or (root / "nx.json").is_file()
    if monorepo and pm in EXEC_PREFIX:
        for pattern in globs:
            for directory in sorted(p for p in root.glob(pattern) if (p / "package.json").is_file()):
                package_shape, package_commands, _ = _js_package(directory, pm)
                packages.append({"path": directory.relative_to(root).as_posix(),
                                 "shape": package_shape or "library",
                                 "verify": {"checks": package_commands}})
        if packages:
            shape = _combine([p["shape"] for p in packages])
    stage = "greenfield" if not manifests and _source_count(root) < 5 else "brownfield"
    providers = {provider: which(PROVIDER_EXE_ALIASES.get(provider, (provider,))[0])
                 for provider in ("claude", "codex", "antigravity")}
    return {
        "stage": stage,
        "shape": shape or "fullstack",
        "monorepo": monorepo,
        "package_manager": pm,
        "stack": stack,
        "packages": packages,
        "verify_commands": commands,
        "suggested_rigor": "easy" if stage == "greenfield" else "standard",
        "providers": providers,
        "codegraph": _codegraph(root, which),
    }
```

- [ ] **Step 4:** `setup_service.detect` adds `"project": detect_project(root)` (import at top). Run tests → PASS; `test_setup_cli.py` detect tests still pass (only an added key).

### Track 3: Presets, `setup preset`, and the `project` block in `gin-workflow state`

**Metadata:**
- Dependencies: Track 2
- Provider role: backend
- Reasoning: medium
- Model guidance: standard_impl
- Estimated complexity: medium

**Files:**
- Modify: `workflow_core/project.py` (add `preset_assignments`), `workflow_core/setup_service.py` (`preset` command + `COMMANDS`), `workflow_core/cli.py` (args), `workflow_core/lifecycle_cli.py` (`_state_command` adds `project`)
- Test: `tests/workflow_core/test_project_settings.py` (preset tests), `tests/workflow_core/test_setup_cli.py` (CLI `preset`), `tests/workflow_core/test_lifecycle_cli.py` (state `project`)

**Interfaces:**
- Consumes: `detect_project`, `project_settings`, `RIGOR_PRESETS`.
- Produces: `preset_assignments(*, stage, shape, rigor, provider_mode, monorepo=False, stack_intent="", verify_commands=None, packages=()) -> list[str]`; CLI `gin-workflow setup preset --project-stage S --project-shape X --rigor R --provider-mode M [--monorepo] [--stack-intent TEXT] --format json` → `{"status": "proposed", "assignments": [...]}` (verify commands and packages come from `detect_project(repository)`); `gin-workflow state --format json` gains `"project": ProjectSettings.to_dict()`.

- [ ] **Step 1: Failing tests**

```python
from workflow_core.project import preset_assignments  # add to imports of test_project_settings.py
from workflow_core.setup_service import _parse_assignment, _set_nested


def _apply(assignments):
    config = {"schema_version": "2.4"}
    for assignment in assignments:
        path, value = _parse_assignment(assignment)
        _set_nested(config, path, value)
    return config


class TestPresets(unittest.TestCase):
    def test_single_provider_frontend_standard(self):
        config = _apply(preset_assignments(stage="brownfield", shape="frontend", rigor="standard",
                                           provider_mode="single",
                                           verify_commands={"lint": "pnpm run lint", "test": "pnpm run test: unit"}))
        validate_portable_config(config)
        self.assertEqual(["docs", "frontend", "general", "review"],
                         sorted(config["routing"]["roles"]))
        self.assertEqual({"preferred": ["main_harness"]}, config["routing"]["roles"]["frontend"])
        self.assertEqual("session", config["routing"]["review"]["independence"])
        self.assertEqual("pnpm run test: unit", config["verify"]["checks"]["test"])
        self.assertEqual("parallel", config["project"]["worktree"])
        settings = project_settings(config)
        self.assertEqual(("frontend", "standard", "single"), (settings.shape, settings.rigor, settings.provider_mode))

    def test_multi_provider_writes_no_roles_and_provider_independence(self):
        config = _apply(preset_assignments(stage="brownfield", shape="backend", rigor="strict", provider_mode="multi"))
        validate_portable_config(config)
        self.assertNotIn("roles", config.get("routing", {}))
        self.assertEqual("provider", config["routing"]["review"]["independence"])
        self.assertEqual(("always", True), (config["project"]["worktree"], config["project"]["review_ledger"]))

    def test_rejects_unknown_values(self):
        with self.assertRaises(ValueError):
            preset_assignments(stage="legacy", shape="mobile", rigor="standard", provider_mode="single")
```

Add to `test_lifecycle_cli.py`: after writing a config with `project: {shape: frontend}`, `state --format json` has `project.shape == "frontend"`; without `project:` it reports `shape == "fullstack"`. Add to `test_setup_cli.py`: `cli_main(["setup","preset","--repository",tmp,"--project-stage","brownfield","--project-shape","frontend","--rigor","easy","--provider-mode","single","--format","json"])` returns 0 and prints assignments including `project.rigor="easy"`.

- [ ] **Step 2:** Run → FAIL.

- [ ] **Step 3: Implement** in `project.py`:

```python
import json

ROLES_BY_SHAPE = {
    "frontend": ("frontend", "review", "docs", "general"),
    "backend": ("backend", "review", "docs", "general"),
    "fullstack": ("frontend", "backend", "review", "docs", "general"),
    "library": ("frontend", "backend", "review", "docs", "general"),
}


def preset_assignments(*, stage: str, shape: str, rigor: str, provider_mode: str, monorepo: bool = False,
                       stack_intent: str = "", verify_commands: Mapping[str, str] | None = None,
                       packages: tuple[Mapping[str, Any], ...] | list = ()) -> list[str]:
    """Explicit `--set` assignments for setup; skills never infer presets at runtime."""
    if stage not in STAGES or shape not in SHAPES or rigor not in RIGORS or provider_mode not in ("single", "multi"):
        raise ValueError(f"invalid project preset: {stage=} {shape=} {rigor=} {provider_mode=}")
    preset = RIGOR_PRESETS[rigor]
    values: dict[str, Any] = {
        "project.stage": stage, "project.shape": shape, "project.monorepo": monorepo, "project.rigor": rigor,
        "project.worktree": preset["worktree"], "project.review": preset["review"],
        "project.review_ledger": preset["review_ledger"], "provider_mode": provider_mode,
        "routing.review.max_cycles": preset["max_cycles"],
        "routing.review.independence": "session" if provider_mode == "single" else "provider",
        "quick.max_files": 5,
    }
    if stack_intent:
        values["project.stack_intent"] = stack_intent
    if packages:
        values["project.packages"] = [dict(package) for package in packages]
    for key in VERIFY_KEYS:
        values[f"verify.checks.{key}"] = str((verify_commands or {}).get(key, ""))
    if provider_mode == "single":
        for role in ROLES_BY_SHAPE[shape]:
            values[f"routing.roles.{role}"] = {"preferred": ["main_harness"]}
        values["routing.review.role"] = "review"
        values["routing.review.require_independent"] = True
        values["routing.review.allow_self_review_fallback"] = False
    return [f"{key}={json.dumps(value)}" for key, value in values.items()]
```

`setup_service.py`:

```python
def preset(repository: Path, *, project_stage: str | None = None, project_shape: str | None = None,
           rigor: str | None = None, provider_mode: str | None = None, monorepo: bool = False,
           stack_intent: str = "", **_: Any) -> dict[str, Any]:
    detected = detect_project(Path(repository))
    try:
        assignments = preset_assignments(
            stage=project_stage or detected["stage"], shape=project_shape or detected["shape"],
            rigor=rigor or detected["suggested_rigor"], provider_mode=provider_mode or "single",
            monorepo=monorepo or detected["monorepo"], stack_intent=stack_intent,
            verify_commands=detected["verify_commands"], packages=tuple(detected["packages"]))
    except ValueError as error:
        raise SetupError(str(error)) from error
    missing = [key for key, value in detected["verify_commands"].items() if not value and key != "e2e"]
    return {"status": "proposed", "assignments": assignments, "detected": detected,
            "warnings": [f"no {key} command detected" for key in missing], "actions": []}
```

register `"preset": preset`; `cli._parser` adds `--project-stage`, `--project-shape`, `--rigor`, `--provider-mode` (choices from `project` enums), `--monorepo` (store_true), `--stack-intent` (default `""`). In `lifecycle_cli._state_command` add `"project": project_settings(config.to_dict() if hasattr(config, "to_dict") else config).to_dict()` to the payload (use the same `config` object passed to `route_next_stage`).

- [ ] **Step 4:** Run tests → PASS; full suite OK.

### Track 4: Model discovery (`list_models`, `gin-workflow setup models`)

**Metadata:**
- Dependencies: Track 1
- Provider role: backend
- Reasoning: medium
- Model guidance: standard_impl
- Estimated complexity: low

**Files:**
- Modify: `workflow_providers/native_cli.py` (append `list_models`), `workflow_core/setup_service.py` (`models` command), `workflow_core/cli.py` (`--provider`)
- Test: `tests/workflow_providers/test_list_models.py` (new)

**Interfaces:**
- Produces: `list_models(provider: str, *, runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None, which=shutil.which) -> list[dict]` each `{"id","label","description","reasoning_levels"}`; CLI `gin-workflow setup models --provider {claude,codex,antigravity} --format json` → `{"status":"listed","provider":p,"models":[...],"manual_entry":True}`.

- [ ] **Step 1: Failing tests** (recorded fixtures):

```python
"""Provider model listing from native CLIs with safe fallback."""

from __future__ import annotations

import json
import subprocess
import unittest

from workflow_providers.native_cli import list_models

CODEX_JSON = json.dumps({"models": [
    {"slug": "gpt-6-sol", "display_name": "GPT-6 Sol", "description": "frontier", "visibility": "list",
     "supported_reasoning_levels": [{"effort": "low"}, {"effort": "high"}]},
    {"slug": "internal", "display_name": "x", "visibility": "hide"}]})
AGY_TEXT = "Fetching available models...\ngemini-3.8-flash-high\tGemini 3.8 Flash (High)\nclaude-opus-4-6-thinking\tClaude Opus 4.6 (Thinking)\n"


def runner_for(stdout, code=0):
    return lambda argv: subprocess.CompletedProcess(argv, code, stdout, "")


FOUND = lambda name: f"/bin/{name}"  # noqa: E731


class TestListModels(unittest.TestCase):
    def test_codex_json_keeps_listed_models(self):
        models = list_models("codex", runner=runner_for(CODEX_JSON), which=FOUND)
        self.assertEqual([{"id": "gpt-6-sol", "label": "GPT-6 Sol", "description": "frontier",
                           "reasoning_levels": ["low", "high"]}], models)

    def test_agy_text_parses_ids_and_suffix_levels(self):
        models = list_models("antigravity", runner=runner_for(AGY_TEXT), which=FOUND)
        self.assertEqual(["gemini-3.8-flash-high", "claude-opus-4-6-thinking"], [m["id"] for m in models])
        self.assertEqual(["high"], models[0]["reasoning_levels"])
        self.assertEqual([], models[1]["reasoning_levels"])

    def test_claude_returns_aliases_without_running_cli(self):
        def fail(argv):
            raise AssertionError("claude has no list command")
        self.assertEqual(["opus", "sonnet", "haiku"], [m["id"] for m in list_models("claude", runner=fail, which=FOUND)])

    def test_failures_and_unknown_providers_return_empty(self):
        self.assertEqual([], list_models("codex", runner=runner_for("not json"), which=FOUND))
        self.assertEqual([], list_models("codex", runner=runner_for(CODEX_JSON, code=1), which=FOUND))
        self.assertEqual([], list_models("antigravity", runner=runner_for(AGY_TEXT), which=lambda name: None))
        self.assertEqual([], list_models("other", runner=runner_for(""), which=FOUND))
```

- [ ] **Step 2:** Run → FAIL.

- [ ] **Step 3: Implement** (append to `native_cli.py`; import `shutil`, `json`, `subprocess`, `PROVIDER_EXE_ALIASES` from `workflow_core.executable_resolver` if not already):

```python
_CLAUDE_ALIASES = (("opus", "Claude Opus (latest)"), ("sonnet", "Claude Sonnet (latest)"), ("haiku", "Claude Haiku (latest)"))
_LIST_COMMANDS = {"codex": ("debug", "models"), "antigravity": ("models",)}
_LEVEL_SUFFIX = re.compile(r"-(low|medium|high)$")


def list_models(provider, *, runner=None, which=shutil.which):
    """Models a provider CLI offers; [] on any failure so setup falls back to manual entry."""
    if provider == "claude":
        return [{"id": i, "label": label, "description": "alias tracks the latest model", "reasoning_levels": []}
                for i, label in _CLAUDE_ALIASES]
    if provider not in _LIST_COMMANDS:
        return []
    executable = which(PROVIDER_EXE_ALIASES.get(provider, (provider,))[0])
    if executable is None:
        return []
    run = runner or (lambda argv: subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False,
                                                  env=sanitized_environment()))
    try:
        completed = run([executable, *_LIST_COMMANDS[provider]])
    except (OSError, subprocess.SubprocessError):
        return []
    if completed.returncode != 0:
        return []
    if provider == "codex":
        try:
            data = json.loads(completed.stdout)
        except ValueError:
            return []
        entries = data.get("models", data) if isinstance(data, dict) else data
        return [{"id": str(m.get("slug") or m.get("id")), "label": str(m.get("display_name", m.get("slug", ""))),
                 "description": str(m.get("description", "")),
                 "reasoning_levels": [str(l.get("effort", l)) if isinstance(l, dict) else str(l)
                                      for l in m.get("supported_reasoning_levels", [])]}
                for m in entries if isinstance(m, dict) and m.get("visibility", "list") == "list" and (m.get("slug") or m.get("id"))]
    models = []
    for line in completed.stdout.splitlines():
        if "\t" not in line:
            continue
        model_id, label = (part.strip() for part in line.split("\t", 1))
        match = _LEVEL_SUFFIX.search(model_id)
        models.append({"id": model_id, "label": label, "description": "",
                       "reasoning_levels": [match.group(1)] if match else []})
    return models
```

`setup_service.models(repository, *, provider=None, **_)` raises `SetupError("--provider is required")` when missing, else returns `{"status": "listed", "provider": provider, "models": list_models(provider), "manual_entry": True, "actions": []}`; register `"models"`; parser `--provider` with choices `("claude","codex","antigravity")`.

- [ ] **Step 4:** Tests PASS; manual: `gin-workflow setup models --provider antigravity --format json` lists `gemini-3.8-flash-*`; `--provider codex` lists `gpt-6-sol`; full suite OK.

### Track 5: Single-provider review independence (`session`)

**Metadata:**
- Dependencies: Track 1
- Provider role: backend
- Reasoning: high
- Model guidance: high_reasoning
- Estimated complexity: medium

**Files:**
- Modify: `workflow_core/review_coordinator.py:53-172`, `skills/review/SKILL.md` (Reviewing step 1)
- Test: `tests/workflow_core/test_review_coordinator.py`

**Interfaces:**
- Produces: `ReviewCoordinator(..., independence: str = "provider")`; `request_review(..., implementation_session: str = "", reviewer_session: str = "")`; `ReviewCycle` gains `implementation_session: str = ""`, `reviewer_session: str = ""` (appended with defaults).

- [ ] **Step 1: Failing tests**

```python
    def test_session_independence_accepts_same_provider_with_distinct_session(self):
        coordinator = ReviewCoordinator(FakeReviewProvider(), independence="session")
        cycle = coordinator.request_review(
            task_id="ui", cycle_number=1, provider_role="review", reasoning="high",
            implementation_route=("claude", "opus"),
            reviewer_candidates=(RouteCandidate("claude", "opus", False),),
            context=self.context(), implementation_session="impl-1", reviewer_session="rev-1")
        self.assertEqual(("claude", "rev-1"), (cycle.reviewer_provider, cycle.reviewer_session))

    def test_session_independence_rejects_same_or_missing_session(self):
        coordinator = ReviewCoordinator(FakeReviewProvider(), independence="session")
        for reviewer_session in ("impl-1", ""):
            with self.subTest(reviewer_session=reviewer_session):
                with self.assertRaises(ReviewCoordinationError):
                    coordinator.request_review(
                        task_id="ui", cycle_number=1, provider_role="review", reasoning="high",
                        implementation_route=("claude", "opus"),
                        reviewer_candidates=(RouteCandidate("claude", "opus", False),),
                        context=self.context(), implementation_session="impl-1",
                        reviewer_session=reviewer_session)

    def test_unknown_independence_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            ReviewCoordinator(FakeReviewProvider(), independence="team")
```

- [ ] **Step 2:** Run → FAIL.

- [ ] **Step 3: Implement.** Constructor validates `independence in ("provider", "session")` (`ValueError("independence must be provider or session")`). In `request_review`, candidate filter becomes:

```python
        def independent(candidate: RouteCandidate) -> bool:
            if not self.require_independent:
                return True
            if self.independence == "session":
                return bool(reviewer_session) and reviewer_session != implementation_session
            return candidate.provider != implementation_route[0]
        selected = next((c for c in reviewer_candidates if independent(c)), None)
```

error messages: provider mode keeps `"independent reviewer route is unavailable"`; session mode raises `"independent reviewer session is unavailable"` when no fallback applies. Pass both sessions into `ReviewCycle(...)`; include `reviewer_session` in the request idempotency key when set.

- [ ] **Step 4:** Review skill, Reviewing step 1 becomes: "Independence follows `project.independence` from `gin-workflow state --format json`: `provider` — the reviewer provider must differ from the implementation provider; `session` — a fresh session/subagent of the same provider with a clean context and a different actor id (`reviewer:<provider>:session-<id>`), never the implementer's session. Self-review only under the explicit `allow_self_review_fallback` policy." Keep the phrases `must differ from the implementation provider`, `maximum review cycles`, `original provider/model route` (asserted by tests).

- [ ] **Step 5:** Tests PASS (existing provider-mode tests unchanged); full suite OK.

### Track 6: `/quick` fast path

**Metadata:**
- Dependencies: Track 3
- Provider role: backend
- Reasoning: medium
- Model guidance: standard_impl
- Estimated complexity: medium

**Files:**
- Create: `skills/quick/SKILL.md`
- Modify: `workflow_core/lifecycle_cli.py` (`record quick-completed`, `quick-check`, `state.recent_quick`), `workflow_core/cli.py` (route `quick-check`), `workflow_core/budget.py` (`STAGES` + `quick`), `skills/progress/SKILL.md` (report `recent_quick`), `README.md` (skill list)
- Test: `tests/workflow_core/test_lifecycle_cli.py`, `tests/workflow_core/test_token_budget.py`

**Interfaces:**
- Produces: `gin-workflow quick-check --changed-files N --modules M [--workflow-id ID] [--repository P] [--format json]` → payload `{"decision": "allowed"|"escalate"|"refused", "reason", "rigor", "verify_commands": {...}, "review": "self_check"|"independent"}` with exit 0/3/4; `gin-workflow record quick-completed --evidence TEXT --actor ID` writes `quick.completed`; `state` payload `"recent_quick": [{"timestamp","evidence"}]` (last 5).

- [ ] **Step 1: Failing tests** (append to `TestLifecycleCLI`; write `project:` config via a helper that rewrites `.agent-workflow/config.yaml`):

```python
    def _write_config(self, text):
        (self.workflow_dir / "config.yaml").write_text(text)

    def _quick(self, *extra):
        import io
        from unittest.mock import patch
        with patch("sys.stdout", new=io.StringIO()) as out:
            code = cli_main(["quick-check", "--repository", str(self.repo_path), "--format", "json", *extra])
        return code, json.loads(out.getvalue())

    def test_quick_check_allows_small_change_with_rigor_commands(self):
        self._write_config("schema_version: '2.4'\nproject: {rigor: easy}\n"
                           "verify: {checks: {lint: l, typecheck: t, test: u, build: b, e2e: e}}\n")
        code, payload = self._quick("--changed-files", "2", "--modules", "1")
        self.assertEqual((0, "allowed", "self_check"), (code, payload["decision"], payload["review"]))
        self.assertEqual({"lint": "l", "typecheck": "t", "test": "u"}, payload["verify_commands"])

    def test_quick_check_escalates_over_threshold_or_multiple_modules(self):
        self._write_config("schema_version: '2.4'\nproject: {rigor: standard}\nquick: {max_files: 3}\n")
        self.assertEqual(3, self._quick("--changed-files", "4", "--modules", "1")[0])
        self.assertEqual(3, self._quick("--changed-files", "1", "--modules", "2")[0])

    def test_quick_check_refuses_strict_without_waiver(self):
        self._write_config("schema_version: '2.4'\nproject: {rigor: strict}\n")
        code, payload = self._quick("--changed-files", "1", "--modules", "1")
        self.assertEqual((4, "refused"), (code, payload["decision"]))
        cli_main(["unblock", "--repository", str(self.repo_path), "--gate", "requirement_confirmed",
                  "--reason", "hotfix", "--actor", "user"])
        self.assertEqual(0, self._quick("--changed-files", "1", "--modules", "1")[0])

    def test_record_quick_completed_shows_in_state(self):
        self.assertEqual(0, cli_main(["record", "quick-completed", "--repository", str(self.repo_path),
                                      "--evidence", "lint ok; 3 tests ok", "--actor", "user"]))
        self.assertEqual("lint ok; 3 tests ok", self._state()["recent_quick"][-1]["evidence"])
```

(`self._state()` = the full JSON payload variant of `_state_gates`.) In `test_token_budget.py`, `TestBudgetLimits.test_each_stage_chain_within_budget` keeps 12,000 for all, plus `test_quick_chain_within_8000`: `self.assertLessEqual(stage_chars(SRC, "quick"), 8_000)`. `test_stage_skills_inline_setup_guard_and_contract_read` iterates `STAGES`, so `quick` must carry the guard too.

- [ ] **Step 2:** Run → FAIL.

- [ ] **Step 3: Implement.** In `lifecycle_cli.py`: add `"quick-completed": ("quick.completed", {})` to `_RECORDABLE_GATES`; in `_state_command` add `"recent_quick"` from `event_store.read_all()` filtered by workflow and type (last 5, `{"timestamp": e.timestamp, "evidence": e.payload.get("evidence", "")}`); add:

```python
_QUICK_COMMANDS = {"easy": ("lint", "typecheck", "test"), "standard": ("lint", "typecheck", "test", "build"),
                   "strict": ("lint", "typecheck", "test", "build", "e2e")}


def _quick_check_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    repo_path = Path(args.repository).resolve()
    config = resolve_effective_config(repo_path, write=False).config
    settings = project_settings(config.to_dict())
    commands = {k: v for k, v in settings.verify_commands.items() if k in _QUICK_COMMANDS[settings.rigor]}
    base = {"rigor": settings.rigor, "verify_commands": commands,
            "review": "self_check" if settings.rigor == "easy" else "independent"}
    if settings.rigor == "strict":
        store = _get_event_store(repo_path)
        waivers = collect_waivers(store, workflow_id=args.workflow_id,
                                  scope_hash=getattr(args, "scope_hash", None) or _resolve_scope_hash(repo_path))
        if "requirement_confirmed" not in waivers:
            return {**base, "decision": "refused",
                    "reason": "strict rigor requires /discuss; waive requirement_confirmed with gin-workflow unblock to use /quick"}, 4
    if args.changed_files > settings.quick_max_files or args.modules > 1:
        return {**base, "decision": "escalate",
                "reason": f"{args.changed_files} files / {args.modules} modules exceeds quick limits "
                          f"({settings.quick_max_files} files, 1 module); use the full lifecycle"}, 3
    return {**base, "decision": "allowed", "reason": "within quick limits"}, 0
```

wire `quick-check` in `main` (args `--changed-files` int required, `--modules` int default 1; JSON/text output) and allow it in `cli.py` (`("setup","state","unblock","record","quick-check")`). `budget.STAGES` appends `"quick"`.

- [ ] **Step 4: Skill** `skills/quick/SKILL.md` (≤ 3,500 chars) — frontmatter `name: quick`, `description: Small, low-risk change without plan or beads: confirm, implement, verify per rigor, report.`; body: `## Before you start` block (same two steps as other stages); then: 1) restate the requirement in 1–3 lines, get confirmation; 2) estimate changed files and top-level modules, run `gin-workflow quick-check --changed-files N --modules M --format json` — `refused` ⇒ stop, point to `/gin-workflow:discuss`; `escalate` ⇒ stop, recommend the full lifecycle; 3) implement (test first when behavior changes); 4) run every returned `verify_commands` entry fresh and keep output (easy: scope tests to changed files when the runner supports it); 5) `review: independent` ⇒ one review per the `review` skill with a fresh session/subagent, else run the self-check: diff re-read, no debug leftovers, no secrets, tests cover the change; 6) re-run quick-check if the change grew; 7) `gin-workflow record quick-completed --evidence "<files>; <verify results>" --actor <id>`; 8) report summary + verify output. Never create plans, beads, or gates; never commit or push (the user commits).

- [ ] **Step 5:** Progress skill step 3 adds "and recent `/quick` runs (`recent_quick` in `gin-workflow state`)". README support-skill list adds `quick`. Tests PASS; budget: `quick` ≤ 8,000; full suite OK.

### Track 7: Quick setup flow, advanced setup, and doctor checks

**Metadata:**
- Dependencies: Track 4, Track 6
- Provider role: docs
- Reasoning: medium
- Model guidance: standard_impl
- Estimated complexity: medium

**Files:**
- Modify: `skills/setup/SKILL.md`, `workflow_core/setup_service.py` (`doctor`), `tests/workflow_core/test_config_examples.py` (questionnaire assertions), `tests/workflow_core/test_setup_cli.py` (doctor), `plugins/gin-workflow/src/examples/config.full.yaml` (add `project`, `provider_mode`, `verify.checks`, `quick`, `routing.review.independence` examples)

**Interfaces:**
- Consumes: `setup detect` (`project`), `setup preset`, `setup models`.
- Produces: doctor `checks_details` keys `verify_commands` (`{"missing": [...]}`), `codegraph` (`{"installed","indexed","stale","suggestion"}`), `project_stage` (`{"suggestion": "..."}` when `stage: greenfield` and a manifest now exists).

- [ ] **Step 1: Failing tests.** `test_config_examples.py`: replace the nine-group assertion with: setup skill contains, in order, `1. **Project type**`, `2. **Rigor**`, `3. **Provider mode**`, `4. **Verify commands**`, `5. **Code index**`; contains `Ask exactly one question`, `gin-workflow setup preset`, `gin-workflow setup models`, `--advanced`, `provider_configuration`, `same assignments`, and the nine advanced group names still appear under `## Advanced setup` (`Main harness` … `Independent review`). `test_setup_cli.py`: doctor on a repo whose config has `verify.checks.test: ""` reports `checks_details["verify_commands"]["missing"]` containing `test`; with `project.stage: greenfield` and a `package.json` present, reports a `project_stage.suggestion`; with `.codegraph/` older than HEAD, `codegraph.stale` is true (use `which` injection or `os.utime`). Doctor must not write (assert repository bytes unchanged).

- [ ] **Step 2:** Run → FAIL.

- [ ] **Step 3: Setup skill** (≤ 6,000 chars). Quick setup (default), one question at a time:
  1. **Project type** — show `gin-workflow setup detect --format json` `project` (stage, shape, monorepo, stack, packages); confirm or edit. Never propose `legacy` unless the user says so.
  2. **Rigor** — suggest `suggested_rigor`; explain easy/standard/strict in one line each.
  3. **Provider mode** — `single` (current harness, default) or `multi` (continues into Advanced setup groups 2–9).
  4. **Verify commands** — confirm detected commands (edit any); greenfield: ask `stack_intent` instead.
  5. **Code index** — only when `codegraph.installed` and not `indexed` on brownfield/legacy: offer `codegraph init` (run only on approval).
  Optional: model per tier for the current harness from `gin-workflow setup models --provider <harness> --format json` (suggest fast/cheap ⇒ low, frontier ⇒ high, `agy` id suffix matches tier; always allow manual entry; empty list ⇒ manual entry).
  Then: `gin-workflow setup preset ... --format json` → assignments (+ any user edits as extra `--set`), `init --dry-run` showing `configuration` and `provider_configuration`, explicit approval, one `init --approve` with the same assignments. `## Advanced setup` (`/setup --advanced` or multi mode) keeps the nine existing groups verbatim plus the five project questions. Keep `--provider-set`, `same assignments`, `provider_configuration`, `configuration` phrases.

- [ ] **Step 4: Doctor** additions (read-only) in `setup_service.doctor` after configuration checks:

```python
    if checks["configuration"]:
        settings = project_settings(resolve_effective_config(root, write=False).config.to_dict())
        missing = [k for k in ("lint", "typecheck", "test", "build") if not settings.verify_commands.get(k)]
        checks_details["verify_commands"] = {"missing": missing}
        detected = detect_project(root)
        if settings.stage == "greenfield" and detected["stage"] == "brownfield":
            checks_details["project_stage"] = {"suggestion": "project now has a manifest/sources; run /setup configure to set project.stage=brownfield"}
        graph = dict(detected["codegraph"])
        if graph["stale"]:
            graph["suggestion"] = "codegraph index is older than HEAD; run `codegraph sync`"
        checks_details["codegraph"] = graph
```

- [ ] **Step 5:** Tests PASS; `config.full.yaml` validates (existing `test_config_examples` example-validation test); full suite OK.

### Track 8: Developer agent, shape appendices, codegraph-backed tech-doc

**Metadata:**
- Dependencies: Track 5, Track 6
- Provider role: docs
- Reasoning: medium
- Model guidance: standard_impl
- Estimated complexity: medium

**Files:**
- Create: `agents/developer.md` (≤ 4,000), `references/shape-frontend.md` (≤ 1,500), `references/shape-backend.md` (≤ 1,500)
- Delete: `agents/full-stack-developer.md`, `agents/codebase-mapper.md`
- Modify: `agents/{docs-writer,agent-researcher,code-reviewer}.md` (remove `codebase-mapper` and `.planning/codebase/` mapper tables; use codegraph-then-grep lookup), `skills/tech-doc/SKILL.md` (slim, ≤ 5,000, codegraph-backed, on demand), `skills/execute/SKILL.md` (implementer = `developer` agent; shape appendix by `project.shape`), `skills/verify/SKILL.md` (verify commands per rigor from `gin-workflow state`), `tests/install_smoke_test.sh` + `.ps1` (agent list), `tests/workflow_providers/test_harness_packaging.py` (required artifacts), `README.md`
- Test: `tests/workflow_core/test_token_budget.py` (shape appendix ≤ 1,500)

**Interfaces:**
- Produces: `agents/developer.md` frontmatter `name: developer`, `tools: ["view_file", "grep_search", "list_dir", "run_command"]`, `model: standard_impl`.

- [ ] **Step 1: Failing tests.** Packaging: `REQUIRED_ARTIFACTS` adds `agents/developer.md`, `references/shape-frontend.md`, `references/shape-backend.md`; new test asserts `agents/full-stack-developer.md` and `agents/codebase-mapper.md` do not exist and no file under `src/` mentions `codebase-mapper` or `full-stack-developer`. Budget: `("references/shape-*.md", 1_500)` added to the per-file limits. Smoke: replace `full-stack-developer.md` asserts with `developer.md`, add `assert_not_exists` for both removed agents (claude-code and codex dist).

- [ ] **Step 2:** Run → FAIL.

- [ ] **Step 3: Write files.**
  - `developer.md`: role (implement one assigned bead/track or `/quick` change within its file scope); inputs (`bd show`, plan track, `gin-workflow state --format json` → `project.shape`, `verify_commands`); load **one** appendix: `references/shape-frontend.md` for frontend, `references/shape-backend.md` for backend, for fullstack the one matching the task's files (both only when the task spans both); follow the `execute` skill; test first; never mask failures; escalate out-of-scope changes; output contract (Changed, Verification with command output, Risks, Beads status).
  - `shape-frontend.md`: component boundaries and single responsibility; state ownership (local first, lift only when shared; server state via the project's data layer); accessibility basics (semantic elements, labels, keyboard focus, alt text); no hardcoded user-facing strings when i18n exists; no secrets in client code; at `strict`, visual check (Playwright screenshot) when configured.
  - `shape-backend.md`: explicit API contracts (types/schemas at boundaries); validate input at the edge; consistent error handling without leaking internals; migrations reversible and separate from code changes; data access through the existing layer, no N+1; idempotency for retries.
  - `tech-doc`: one paragraph purpose; run only on `/tech-doc`; lookup order `codegraph files`/`codegraph explore` when `.codegraph/` exists, else grep/read; keep `.planning/codebase/` default, `single combined document` rule, `ARCHITECTURE.md` canonical file name, `codegraph` mention (smoke asserts these three).
  - `execute` §3: "When dispatching an implementer, use the `developer` agent." §2: "Read the shape appendix for `project.shape` (plugin `references/shape-<shape>.md`) before editing." (plain text, no link — keeps the chain ≤ 12,000).
  - `verify` step 3: "Quality gates: run `project.verify_commands` from `gin-workflow state --format json` per rigor (easy: lint, typecheck, tests; standard: + build; strict: + e2e/a11y when configured) …".

- [ ] **Step 4:** `grep -rn "codebase-mapper\|full-stack-developer" plugins/gin-workflow/src tests README.md install.sh install.ps1` → no hits (except smoke `assert_not_exists`). Budget report: all stages ≤ 12,000, `quick` ≤ 8,000. Full suite + smoke OK.

### Track 9: Benchmark protocol and usage summarizer

**Metadata:**
- Dependencies: none
- Provider role: general
- Reasoning: low
- Model guidance: cheap_simple
- Estimated complexity: low

**Files:**
- Create: `docs/benchmarks/README.md`, `scripts/benchmark/summarize_usage.py`, `tests/workflow_core/test_benchmark_summary.py`, `tests/fixtures/benchmark/session-a.jsonl`

**Interfaces:**
- Produces: `summarize(path: Path) -> dict` with `input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens, tool_calls, wall_seconds`; CLI `python3 scripts/benchmark/summarize_usage.py LABEL=PATH [LABEL=PATH ...]` prints a Markdown table.

- [ ] **Step 1: Fixture + failing test.** Fixture (3 lines):

```
{"type":"user","timestamp":"2026-10-02T00:00:00Z","message":{"role":"user","content":"fix bug"}}
{"type":"assistant","timestamp":"2026-10-02T00:00:10Z","message":{"role":"assistant","usage":{"input_tokens":100,"output_tokens":20,"cache_creation_input_tokens":50,"cache_read_input_tokens":0},"content":[{"type":"tool_use","name":"Read","input":{}}]}}
{"type":"assistant","timestamp":"2026-10-02T00:01:40Z","message":{"role":"assistant","usage":{"input_tokens":30,"output_tokens":5,"cache_creation_input_tokens":0,"cache_read_input_tokens":40},"content":[{"type":"text","text":"done"}]}}
```

```python
"""Benchmark usage summarizer over a recorded Claude Code transcript."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("summarize_usage", ROOT / "scripts/benchmark/summarize_usage.py")
summarize_usage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summarize_usage)


class TestSummarizeUsage(unittest.TestCase):
    def test_sums_usage_tool_calls_and_wall_time(self):
        result = summarize_usage.summarize(ROOT / "tests/fixtures/benchmark/session-a.jsonl")
        self.assertEqual({"input_tokens": 130, "output_tokens": 25, "cache_creation_input_tokens": 50,
                          "cache_read_input_tokens": 40, "tool_calls": 1, "wall_seconds": 100.0}, result)

    def test_table_has_one_row_per_label(self):
        table = summarize_usage.table({"gin-easy": ROOT / "tests/fixtures/benchmark/session-a.jsonl"})
        self.assertIn("| gin-easy | 130 | 25 | 50 | 40 | 1 | 100 |", table)
```

- [ ] **Step 2:** Run → FAIL.

- [ ] **Step 3: Implement** `scripts/benchmark/summarize_usage.py`:

```python
"""Summarize token usage, tool calls, and wall time from Claude Code transcript JSONL files."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys

FIELDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def summarize(path: Path) -> dict[str, float]:
    totals = {field: 0 for field in FIELDS}
    tool_calls, stamps = 0, []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("timestamp"):
            stamps.append(datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")))
        message = entry.get("message") or {}
        if entry.get("type") != "assistant":
            continue
        for field in FIELDS:
            totals[field] += int((message.get("usage") or {}).get(field, 0))
        content = message.get("content") or []
        tool_calls += sum(1 for block in content if isinstance(block, dict) and block.get("type") == "tool_use")
    wall = (max(stamps) - min(stamps)).total_seconds() if stamps else 0.0
    return {**totals, "tool_calls": tool_calls, "wall_seconds": wall}


def table(runs: dict[str, Path]) -> str:
    lines = ["| Run | Input | Output | Cache write | Cache read | Tool calls | Wall s |", "|---|---|---|---|---|---|---|"]
    for label, path in runs.items():
        s = summarize(path)
        lines.append(f"| {label} | {s['input_tokens']} | {s['output_tokens']} | {s['cache_creation_input_tokens']} | "
                     f"{s['cache_read_input_tokens']} | {s['tool_calls']} | {int(s['wall_seconds'])} |")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    runs = dict(arg.split("=", 1) for arg in argv)
    print(table({label: Path(path) for label, path in runs.items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Protocol** `docs/benchmarks/README.md`: pinned sample (React + TypeScript + Vite repo at a recorded commit); tasks (a) small bug fix, (b) medium feature (component + state + tests); configurations: gin `easy` (`/quick`), gin `standard`, superpowers, spec-kit — same harness (Claude Code) and model; metrics: input/output/cache tokens, tool calls, wall time, tests pass; a run whose tests fail is reported as failed, not cheaper; transcripts under `~/.claude/projects/<project>/<session>.jsonl`; command `python3 scripts/benchmark/summarize_usage.py gin-easy=<path> superpowers=<path>`; record results as `docs/benchmarks/YYYY-MM-DD-<sample>.md` with framework versions. Not in CI. (`docs/benchmarks/README.md` has no canonical `references/` pair.)

- [ ] **Step 5:** Tests PASS; `test_scoped_markdown_links_are_repo_relative_and_resolve` OK for the new doc; full suite OK.

## Integration
- **Branch**: `feat/project-profile-bootstrap` (worktree `.planning/worktrees/project-profile-bootstrap`)
- **Merge strategy**: sequential

## Validation
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py` — OK
- [ ] `bash tests/install_smoke_test.sh` — OK; `install.sh --dry-run` for claude/codex/antigravity — OK
- [ ] Budget report: every stage ≤ 12,000, `quick` ≤ 8,000, descriptions ≤ 4,000
- [ ] Acceptance 1 (harness, plain prompt): `/gin-workflow:setup` on a React+TS+pnpm scratch repo with one provider finishes in ≤ 5 questions and writes `project.shape: frontend`, detected `verify.checks`, frontend-only roles, `routing.review.independence: session`
- [ ] Acceptance 2: a 2.3 config loads unchanged (state routes as before), `setup update` migrates to 2.4 with only version fields changed
- [ ] Acceptance 3: `gin-workflow setup models --provider codex|antigravity|claude --format json` lists real models / aliases; a failing CLI yields `[]` + manual entry
- [ ] Acceptance 4: coordinator `session` mode passes without `allow_self_review_fallback`
- [ ] Acceptance 5: `/quick` (harness, plain prompt) runs quick-check, verify commands per rigor, records `quick.completed`, escalates over threshold, refuses at strict without waiver, never commits
- [ ] Acceptance 6–8: agents replaced, appendices present, benchmark summarizer tested, `record quick-completed` exists

## Risks
- Version bump touches many assertions → Track 1 limits edits to config/setup-CLI version checks; worker/evidence `2.3` contract untouched (Global Constraints).
- Detection heuristics misclassify → output is only a proposal; user confirms in setup question 1; fixtures lock the rules.
- `setup preset` single-mode roles conflict with existing roles in `configure` flows → presets are used only at `init`; `configure` keeps explicit `--set`.
- Skill behavior not exercised by unit tests → plain-prompt harness checks for setup and `/quick` (as in A's verify).
- `agy`/`codex` model listing formats change → fixtures plus empty-list fallback; never blocks setup.

## Notes
- Model guidance is planning metadata, not Beads state.
- Parent bead "Sub-project B+C" stays open until human-confirmed merge; track beads close after tests and review pass.

# Plan: SDD Living Specs (Sub-project F)

**Goal:** A repository can keep its product requirements as a living, ID-addressable spec in git, change it through reviewable deltas, and trace every changed requirement to tests, while repositories that do not opt in keep today's behavior unchanged.

**Architecture:** Opt-in through `artifacts.layout: sdd` (schema 2.6; default `legacy`). A deterministic CLI `gin-workflow specs` (modules `workflow_core/specs.py` core, `specs_archive.py`, `specs_trace.py`, `specs_migrate.py`, `specs_cli.py`) parses requirement blocks, lints specs and deltas, allocates REQ-IDs across worktrees and remotes, renumbers, traces REQs to tests, reads the spec-review PR state, archives deltas into the living spec, and migrates `.planning`. Templates ship in `src/templates/` with project overrides in `.agent-workflow/templates/`. Stage skills gain at most two lines that hand off to an on-demand `gin-sdd` skill, so legacy stage chains barely grow. `setup preset` proposes `sdd` for greenfield; `setup doctor` suggests migration and flags path conflicts. A thin `migrate-specs` skill drives the migration and optional living-spec seeding.

**Tech Stack:** Python 3.12 stdlib (`re`, `hashlib`, `subprocess`, `argparse`) + PyYAML/jsonschema (already required); `git`, optional `bd` and `gh` executables; `unittest`; Markdown skills and templates; bash/PowerShell installers.

**Spec:** `.planning/specs/2026-10-03-sdd-living-specs-design.md` @ `c26ae48` (workflow id `sdd-living-specs`, `requirement_confirmed` recorded).

## Global Constraints

Copied verbatim from the spec decisions:

| Topic | Decision |
|---|---|
| Opt-in | `artifacts.layout: legacy \| sdd`, default `legacy`. Setup proposes `sdd` for greenfield; repos with `.planning/specs` or `.planning/plans` stay `legacy` until migrated. |
| Location | One `docs/` root: `docs/specs`, `docs/changes`, `docs/adr`, `docs/codebase`; every path configurable under `artifacts`. |
| Change folder | `docs/changes/<epic-id>-<slug>/`. `discuss` creates the epic bead right after the user confirms the design, so the folder name is final from the start. |
| Bead ↔ REQ | Bead ids keep the `bd` prefix and `<epic>.N` hierarchy. Track beads link requirements with `--spec-id <epic-id>-<slug>` (the change id, stable across archive; `bd list --spec <epic-id>` finds them) and one label `req:<REQ-ID>` per requirement. |
| Requirement format | `### REQ-<CAP>-<NNN>: <title>`, one SHALL/MUST statement, ≥1 `#### Scenario:` with GIVEN/WHEN/THEN bullets. EARS recommended in templates, not enforced. |
| ID allocation | Sequential per capability via `specs next-id`, scanning living specs and deltas in every local worktree and `refs/remotes`. `specs lint --against <base>` blocks duplicates; `specs renumber` repairs them. |
| Traceability | Automated tests carry the REQ-ID in the test name or a comment; manual/QE cases live in `tests.md`. Missing evidence warns under `easy`, blocks `verification-passed` under `standard`/`strict`. |
| Merge into living spec | `specs archive` runs at the start of `ship`, on the feature branch, before merge or PR. Deterministic and atomic; stops on base-hash conflict. |
| Spec approval | `artifacts.spec_review: chat \| pr`, default `chat`. `pr` pushes the change folder on `spec/<epic>-<slug>`, waits for the spec PR to merge, then records `requirement_confirmed`. Role checks belong to E. |
| Conventions | F ships templates (project override in `.agent-workflow/templates/`) and `specs lint`. Commit convention, commit-msg hook, PR template, and CODEOWNERS belong to E. |
| tech-doc | Kept. Under `sdd` it writes to `artifacts.codebase` using overridable templates; it also seeds living specs during migration. |
| Migration | Two phases: deterministic `specs migrate [--dry-run] [--force]`, then an optional AI-assisted, user-reviewed living-spec seeding in `/gin-workflow:migrate-specs`. |
| Schema | 2.6, with a defaults-only migration from 2.5. |

Repository constraints:
- Test command (repo root): `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py`. Baseline 2026-10-03 on `master` (`16381fc`): `Ran 647 tests … OK`. The validated prototype of this plan ends at `Ran 686 tests … OK`.
- Install smoke test: `bash tests/install_smoke_test.sh`. The PowerShell smoke test cannot run here (no `pwsh`); keep it consistent by reading.
- Token budgets (`tests/workflow_core/test_token_budget.py`): each stage chain ≤ 12,000 chars (execute 10,507 today), `quick` ≤ 8,000 (3,950), `skills/gin-*/SKILL.md` ≤ 6,000, `agents/*.md` ≤ 4,000, descriptions ≤ 4,000 (2,729). Any `references/*.md` named in a stage skill is counted in its chain, so the SDD procedure lives in a skill (`gin-sdd`) that stage skills name only conditionally, exactly like `gin-debugging`.
- "Existing tests pass unmodified" excludes tests that assert the *current* version: `test_schema_2_5.py::test_current_version_is_2_5_and_older_versions_load` (becomes a 2.5-still-loads test) and four `2.5` assertions in `test_setup_cli.py` (lines 29, 270–272, 413, 425) move to `2.6`. Tests that write `schema_version: '2.5'` (or older) configs stay as they are.
- SDD defaults are applied at read time (`specs.sdd_config`), not added to `BUILT_IN_DEFAULTS`, so the generated effective config of every existing repository is byte-for-byte unchanged.
- Portable config forbids keys named `commands`/`*_commands`; new keys are `layout`, `specs`, `changes`, `adr`, `codebase`, `spec_review`, `test_globs` under `artifacts`.
- Worker-result/evidence schema `"2.3"` constants in `workflow_providers/{contracts,evidence,worker_dispatch,routed_worker}.py` and `manifests.py`/`models.py` are a separate contract: do not change them.
- The launcher (`~/.local/lib/gin-workflow/<ver>/`) ships `workflow_core/` and `rules/`; it must also ship `templates/`.
- Git: commit/push on `feat/sdd-living-specs` (worktree); never commit to `master`.

## Deviations from the spec (decided while planning; each keeps the spec's intent)

1. `references/sdd-layout.md` becomes the skill `skills/gin-sdd/SKILL.md`: a reference named in a stage skill is always counted in that stage's chain (`budget._REFERENCE`), a conditionally named skill is not.
2. Two extra subcommands: `specs hash <REQ-ID>` prints the `<!-- base: <hash> -->` line an agent puts under a `MODIFIED`/`REMOVED` heading; `specs template <name>` prints a template with project overrides applied (works under either layout; tech-doc and discuss use it).
3. Five modules instead of two: `specs.py` (config, templates, parse, hash, lint, ids, new, renumber), `specs_cli.py`, `specs_archive.py`, `specs_trace.py` (trace, status), `specs_migrate.py` (migrate, setup/doctor report). Each track adds whole modules instead of editing the previous one.
4. No `plan.md` template: `skills/plan/plan-schema.md` already is the plan template. `specs new` creates `proposal.md`, `spec-delta.md`, `design.md`, `tests.md`.
5. Conflict rule: a specs folder conflicts when it holds files other than `README.md` and `<cap>/spec.md` (the spec's "no `spec.md` with `### REQ-`" would flag a freshly migrated, still-empty folder).
6. `proposal.md` carries `Epic: <id>`; `specs.change_epic()` reads it because the epic id itself contains hyphens and cannot be split off the folder name.
7. `layout` and `spec_review` are surfaced as `project.layout` and `project.spec_review` in `gin-workflow state --format json` (fields on `ProjectSettings`), which is what stage skills already read.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`: brainstorm `high_reasoning`; design `high_reasoning`; plan `standard_impl`; implement `standard_impl`; verify `standard_impl`; review `high_reasoning`; docs `cheap_simple`
- `override_rule`: Track 1 (schema/migration compatibility), Track 2 (parsing, ID allocation), and Track 3 (atomic archive) use `high_reasoning`.

## Requirement Analysis
- Problem: `.planning/specs/` holds dated per-change design docs, so there is no current truth of what the product must do, no stable requirement IDs, and no check that changed requirements are tested. A team also needs shared document formats and a way to approve a spec before work starts.
- Success: spec §Testing items and the Validation list below.
- Constraints: opt-in only; legacy repos unchanged; deterministic CLI (no LLM in lint, ids, trace, archive, migrate); archive and migrate all-or-nothing; no network dependency for `next-id`; stage chains within budget.
- Non-goals (spec): role-gated approvals, identity, commit-msg hook, PR template, CODEOWNERS (E); test-case generation (G); rewriting historical gate evidence; enforcing EARS; migrating this repository.

## Approach Options
### Option 1: Deterministic `gin-workflow specs` CLI + on-demand `gin-sdd` skill (selected)
- Pros: testable, same behavior on every harness, fixed token cost for legacy repos, agents call commands instead of re-deriving rules.
- Cons: larger CLI surface; Markdown format must stay strict.
### Option 2: Skills describe the format and agents edit specs by hand
- Cons: no reliable ID allocation, no atomic merge, traceability depends on the model reading every test file.
### Recommended Approach
- Option 1, as the spec decides.

## Scope
- In: `plugins/gin-workflow/src/{scripts/workflow_core,scripts/workflow_providers/registry.py,templates,skills/{gin-sdd,migrate-specs,discuss,plan,orchestrate,execute,review,verify,ship,quick,tech-doc},agents/developer.md,examples/config.full.yaml}`, `install.sh`, `install.ps1`, `tests/`.
- Out: `docs/*` canonical reference pairs, README (no change planned), team mode (E), `gin-qa` (G), migrating this repository's own `.planning`.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks build on one another (schema and templates, then the specs core, then archive/trace, then migrate and setup, then skill wiring) and share cli.py, specs_cli.py, the installers, and the packaging test; sequential direct execution avoids conflicts.
```

## File Structure

| Path | Responsibility |
|---|---|
| `plugins/gin-workflow/src/scripts/workflow_core/schemas.py` | 2.6; accept 2.3–2.6; SDD keys under `artifacts` |
| `plugins/gin-workflow/src/scripts/workflow_core/configuration.py`, `migrations.py`, `cli.py`, `../workflow_providers/registry.py` | Version 2.6; 2.5→2.6 migration (versions only); `cli.py` routes `specs` |
| `plugins/gin-workflow/src/scripts/workflow_core/project.py` | `ProjectSettings.layout`/`spec_review`; `preset_assignments(..., layout="")` |
| `plugins/gin-workflow/src/templates/**` (new) | 7 change/spec templates + 8 tech-doc templates |
| `plugins/gin-workflow/src/scripts/workflow_core/specs.py` (new) | `sdd_config`, templates, `parse_blocks`, `block_hash`, lint, `scan_ids`/`next_id`, `new_change`, `requirement_hash`, `renumber` |
| `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py` (new) | `gin-workflow specs` argparse front end and exit codes |
| `plugins/gin-workflow/src/scripts/workflow_core/specs_archive.py` (new) | `archive` (atomic delta merge, README update, `git mv`), shared `move` |
| `plugins/gin-workflow/src/scripts/workflow_core/specs_trace.py` (new) | `trace` (REQ → tests), `status` (spec PR via `gh`) |
| `plugins/gin-workflow/src/scripts/workflow_core/specs_migrate.py` (new) | `plan_moves`, refusals, `migrate`, `sdd_report` for setup/doctor |
| `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py` | `preset` proposes `sdd` for greenfield; `doctor` reports `checks_details.sdd` |
| `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md`, `skills/migrate-specs/SKILL.md` (new) | SDD procedure per stage; migration skill |
| `plugins/gin-workflow/src/skills/{discuss,plan,orchestrate,execute,review,verify,ship,quick,tech-doc}/SKILL.md`, `agents/developer.md` | One conditional line each |
| `plugins/gin-workflow/src/examples/config.full.yaml` | 2.6 + SDD keys |
| `install.sh`, `install.ps1`, `tests/install_smoke_test.{sh,ps1}` | Launcher 2.6; ship `templates/` |
| `tests/workflow_core/specs_fixtures.py` (new) | Shared temp-repo helpers for SDD tests |

## Tasks

### Track 1: Schema 2.6, project settings, templates, and packaging

**Metadata:**
- Dependencies: none
- Provider role: backend
- Reasoning: high
- Model guidance: high_reasoning
- Estimated complexity: medium

**Files:**
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/schemas.py:10-11,25-31`, `plugins/gin-workflow/src/scripts/workflow_core/configuration.py:26-27`, `plugins/gin-workflow/src/scripts/workflow_core/migrations.py:15,68-82`, `plugins/gin-workflow/src/scripts/workflow_core/cli.py:19`, `plugins/gin-workflow/src/scripts/workflow_providers/registry.py:178,184`, `plugins/gin-workflow/src/scripts/workflow_core/project.py:21-36,49-72,84-104`, `install.sh:12,254,304-311,384-387`, `install.ps1:17,80,286-290`, `tests/install_smoke_test.sh`, `tests/install_smoke_test.ps1`, `plugins/gin-workflow/src/examples/config.full.yaml:1-3,27-33`
- Create: `plugins/gin-workflow/src/templates/` (15 files)
- Test: `tests/workflow_core/test_schema_2_6.py` (new); `tests/workflow_core/test_schema_2_5.py` (current-version test only); `tests/workflow_core/test_setup_cli.py` (four current-version assertions); `tests/workflow_providers/test_harness_packaging.py` (template artifacts)

**Interfaces:**
- Produces: `SUPPORTED_SCHEMA_VERSION = "2.6"`, `SUPPORTED_CONFIG_VERSIONS = ("2.3", "2.4", "2.5", "2.6")`, `migrations.CURRENT_VERSION = "2.6"`; config keys `artifacts.{layout: legacy|sdd, specs, changes, adr, codebase: str, spec_review: chat|pr, test_globs: [str]}`; `ProjectSettings.layout: str = "legacy"`, `ProjectSettings.spec_review: str = "chat"`; `preset_assignments(..., layout: str = "")`; template names `proposal.md`, `spec-delta.md`, `spec.md`, `design.md`, `tests.md`, `adr.md`, `specs-README.md`, `codebase/<FILE>.md` with placeholders `{{epic}}`, `{{slug}}`, `{{title}}`, `{{date}}`, `{{capability}}`, `{{scope}}`.

- [ ] **Step 1: Failing tests.** Create `tests/workflow_core/test_schema_2_6.py`:

```python
"""Schema 2.6: SDD artifact keys, project layout settings, and the 2.5 -> 2.6 migration."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.configuration import ConfigValidationError, validate_portable_config  # noqa: E402
from workflow_core.migrations import CURRENT_VERSION, migrate_config  # noqa: E402
from workflow_core.project import preset_assignments, project_settings  # noqa: E402
from workflow_core.schemas import SUPPORTED_CONFIG_VERSIONS  # noqa: E402


class TestSchema26(unittest.TestCase):
    def test_current_version_is_2_6_and_older_versions_load(self):
        self.assertEqual("2.6", CURRENT_VERSION)
        self.assertEqual(("2.3", "2.4", "2.5", "2.6"), SUPPORTED_CONFIG_VERSIONS)
        for version in SUPPORTED_CONFIG_VERSIONS:
            with self.subTest(version=version):
                validate_portable_config({"schema_version": version})

    def test_sdd_artifact_keys_validate(self):
        validate_portable_config({"schema_version": "2.6", "artifacts": {
            "layout": "sdd", "specs": "docs/specs", "changes": "docs/changes", "adr": "docs/adr",
            "codebase": "docs/codebase", "spec_review": "pr", "test_globs": ["tests/**"]}})
        for bad in ({"layout": "openspec"}, {"spec_review": "email"}, {"test_globs": "tests/**"},
                    {"test_globs": [""]}, {"specs": ""}, {"unknown": "x"}):
            with self.subTest(bad=bad), self.assertRaises(ConfigValidationError):
                validate_portable_config({"schema_version": "2.6", "artifacts": bad})

    def test_migration_2_5_to_2_6_only_bumps_versions(self):
        source = {"schema_version": "2.5", "workflow_version": "2.5", "setup_cli_version": "2.5",
                  "rules": {"packs": ["core"]}}
        self.assertEqual({**source, "schema_version": "2.6", "workflow_version": "2.6", "setup_cli_version": "2.6"},
                         migrate_config(source, "2.6"))

    def test_project_settings_default_to_legacy_chat(self):
        settings = project_settings({"schema_version": "2.5"})
        self.assertEqual(("legacy", "chat"), (settings.layout, settings.spec_review))
        settings = project_settings({"schema_version": "2.6", "artifacts": {"layout": "sdd", "spec_review": "pr"}})
        self.assertEqual(("sdd", "pr"), (settings.layout, settings.spec_review))

    def test_preset_assignment_sets_layout_only_when_given(self):
        common = {"stage": "greenfield", "shape": "backend", "rigor": "easy", "provider_mode": "single"}
        self.assertIn('artifacts.layout="sdd"', preset_assignments(**common, layout="sdd"))
        self.assertFalse(any(a.startswith("artifacts.layout") for a in preset_assignments(**common)))


if __name__ == "__main__":
    unittest.main()
```

Update the tests that assert the current version:

```diff
diff --git a/tests/workflow_core/test_schema_2_5.py b/tests/workflow_core/test_schema_2_5.py
index dd8bf38..8ba941c 100644
--- a/tests/workflow_core/test_schema_2_5.py
+++ b/tests/workflow_core/test_schema_2_5.py
@@ -13,12 +13,11 @@ sys.path.insert(0, str(SCRIPTS))
 from workflow_core.configuration import (  # noqa: E402
     ConfigValidationError, resolve_effective_config, validate_portable_config)
-from workflow_core.migrations import CURRENT_VERSION, migrate_config  # noqa: E402
+from workflow_core.migrations import migrate_config  # noqa: E402
 from workflow_core.schemas import SUPPORTED_CONFIG_VERSIONS  # noqa: E402
 
 
 class TestSchema25(unittest.TestCase):
-    def test_current_version_is_2_5_and_older_versions_load(self):
-        self.assertEqual("2.5", CURRENT_VERSION)
-        self.assertEqual(("2.3", "2.4", "2.5"), SUPPORTED_CONFIG_VERSIONS)
+    def test_2_5_and_older_versions_load(self):
+        self.assertIn("2.5", SUPPORTED_CONFIG_VERSIONS)
         for version in SUPPORTED_CONFIG_VERSIONS:
             with self.subTest(version=version):
```

```diff
diff --git a/tests/workflow_core/test_setup_cli.py b/tests/workflow_core/test_setup_cli.py
index 6c37e14..2f5dd66 100644
--- a/tests/workflow_core/test_setup_cli.py
+++ b/tests/workflow_core/test_setup_cli.py
@@ -27,5 +27,5 @@ class SetupCliTests(unittest.TestCase):
 
         self.assertEqual(0, result.returncode, result.stderr)
-        self.assertEqual("gin-workflow 2.5", result.stdout.strip())
+        self.assertEqual("gin-workflow 2.6", result.stdout.strip())
 
     def run_cli(self, repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
@@ -268,7 +268,7 @@ class SetupCliTests(unittest.TestCase):
                     "harness": "codex",
                     "policy": {"mode": "guarded"},
-                    "schema_version": "2.5",
-                    "setup_cli_version": "2.5",
-                    "workflow_version": "2.5",
+                    "schema_version": "2.6",
+                    "setup_cli_version": "2.6",
+                    "workflow_version": "2.6",
                 },
                 payload["configuration"],
@@ -411,5 +411,5 @@ class SetupCliTests(unittest.TestCase):
             self.assertIn("configuration", payload)
             self.assertIn("provider_configuration", payload)
-            self.assertEqual("2.5", payload["configuration"]["schema_version"])
+            self.assertEqual("2.6", payload["configuration"]["schema_version"])
             self.assertEqual("opus", payload["provider_configuration"]["providers"]["claude"]["models"]["high"])
             self.assertFalse((workflow / "providers.local.yaml").exists())
@@ -423,5 +423,5 @@ class SetupCliTests(unittest.TestCase):
             effective = (workflow / "generated/effective-config.yaml").read_text(encoding="utf-8")
             provenance = (workflow / "generated/config-provenance.yaml").read_text(encoding="utf-8")
-            self.assertIn("schema_version: '2.5'", effective)
+            self.assertIn("schema_version: '2.6'", effective)
             self.assertIn("routing:", effective)
             self.assertIn("schema_version: '2.3'", provenance)
```

Add the template artifacts to `REQUIRED_ARTIFACTS` in `tests/workflow_providers/test_harness_packaging.py` (after `"rules/node-api.md",`):

```python
    "templates/proposal.md",
    "templates/spec-delta.md",
    "templates/spec.md",
    "templates/specs-README.md",
    "templates/codebase/OVERVIEW.md",
```

- [ ] **Step 2:** Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/workflow_core/test_schema_2_6.py tests/workflow_core/test_schema_2_5.py -v` → FAIL (`'2.5' != '2.6'`, unknown `artifacts.layout`, missing `ProjectSettings.layout`).

- [ ] **Step 3: Implement** the version bump, schema, migration, and settings:

```diff
diff --git a/plugins/gin-workflow/src/scripts/workflow_core/schemas.py b/plugins/gin-workflow/src/scripts/workflow_core/schemas.py
index 7d66e3a..9622b99 100644
--- a/plugins/gin-workflow/src/scripts/workflow_core/schemas.py
+++ b/plugins/gin-workflow/src/scripts/workflow_core/schemas.py
@@ -8,6 +8,6 @@ from .models import DependencyUnavailableError
 
 
-SUPPORTED_SCHEMA_VERSION = "2.5"
-SUPPORTED_CONFIG_VERSIONS = ("2.3", "2.4", "2.5")
+SUPPORTED_SCHEMA_VERSION = "2.6"
+SUPPORTED_CONFIG_VERSIONS = ("2.3", "2.4", "2.5", "2.6")
 
 _SHAPES = ["frontend", "backend", "fullstack", "library"]
@@ -25,6 +25,12 @@ CONFIG_SCHEMA: dict[str, Any] = {
         "artifacts": {
             "type": "object",
+            "properties": {
+                "layout": {"enum": ["legacy", "sdd"]},
+                "spec_review": {"enum": ["chat", "pr"]},
+                "test_globs": {"type": "array", "uniqueItems": True, "items": {"type": "string", "minLength": 1}},
+            },
             "propertyNames": {
-                "enum": ["plans", "beads", "worktrees", "knowledge", "evidence", "runtime"]
+                "enum": ["plans", "beads", "worktrees", "knowledge", "evidence", "runtime",
+                         "layout", "specs", "changes", "adr", "codebase", "spec_review", "test_globs"]
             },
             "additionalProperties": {"type": "string", "minLength": 1},
```

```diff
diff --git a/plugins/gin-workflow/src/scripts/workflow_core/configuration.py b/plugins/gin-workflow/src/scripts/workflow_core/configuration.py
index 7b35a32..c9d8e62 100644
--- a/plugins/gin-workflow/src/scripts/workflow_core/configuration.py
+++ b/plugins/gin-workflow/src/scripts/workflow_core/configuration.py
@@ -24,6 +24,6 @@ class ConfigValidationError(ValueError):
 
 
-SUPPORTED_WORKFLOW_VERSION = "2.5"
-SUPPORTED_SETUP_CLI_VERSION = "2.5"
+SUPPORTED_WORKFLOW_VERSION = "2.6"
+SUPPORTED_SETUP_CLI_VERSION = "2.6"
```

```diff
diff --git a/plugins/gin-workflow/src/scripts/workflow_core/migrations.py b/plugins/gin-workflow/src/scripts/workflow_core/migrations.py
index b583704..0dabccb 100644
--- a/plugins/gin-workflow/src/scripts/workflow_core/migrations.py
+++ b/plugins/gin-workflow/src/scripts/workflow_core/migrations.py
@@ -13,5 +13,5 @@ from .configuration import require_yaml, validate_portable_config
 
 
-CURRENT_VERSION = "2.5"
+CURRENT_VERSION = "2.6"
 BACKUP_SCHEMA_VERSION = "1"
 
@@ -75,4 +75,12 @@ def _migrate_2_4_to_2_5(config: dict[str, Any]) -> dict[str, Any]:
 
 
+def _migrate_2_5_to_2_6(config: dict[str, Any]) -> dict[str, Any]:
+    migrated = dict(config)
+    migrated["schema_version"] = "2.6"
+    migrated["workflow_version"] = "2.6"
+    migrated["setup_cli_version"] = "2.6"
+    return migrated
+
+
 _MIGRATIONS = {
     ("2.0", "2.1"): _migrate_2_0_to_2_1,
@@ -81,4 +89,5 @@ _MIGRATIONS = {
     ("2.3", "2.4"): _migrate_2_3_to_2_4,
     ("2.4", "2.5"): _migrate_2_4_to_2_5,
+    ("2.5", "2.6"): _migrate_2_5_to_2_6,
 }
 _NEXT_STEP = {source: target for source, target in _MIGRATIONS}
```

`plugins/gin-workflow/src/scripts/workflow_core/cli.py:19`: `CLI_VERSION = "2.5"` → `CLI_VERSION = "2.6"`.

```diff
diff --git a/plugins/gin-workflow/src/scripts/workflow_providers/registry.py b/plugins/gin-workflow/src/scripts/workflow_providers/registry.py
index fc861bf..b6f5030 100644
--- a/plugins/gin-workflow/src/scripts/workflow_providers/registry.py
+++ b/plugins/gin-workflow/src/scripts/workflow_providers/registry.py
@@ -176,5 +176,5 @@ class ProviderRegistry:
             ".agent-workflow/runtime/evidence",
         )
-        if evidence_authority is None and str(config.get("schema_version", "")) in ("2.3", "2.4", "2.5"):
+        if evidence_authority is None and str(config.get("schema_version", "")) in ("2.3", "2.4", "2.5", "2.6"):
             evidence_runtime_root = _path(root, artifacts.get("runtime"), ".agent-workflow/runtime")
             evidence_event_store = event_store or WorkflowEventStore(
@@ -182,5 +182,5 @@ class ProviderRegistry:
             )
             evidence_authority = build_composite_evidence_authority(root, evidence_event_store)
-        if str(config.get("schema_version", "")) in ("2.3", "2.4", "2.5") and not isinstance(
+        if str(config.get("schema_version", "")) in ("2.3", "2.4", "2.5", "2.6") and not isinstance(
             evidence_authority,
             CompositeEvidenceAuthority,
```

```diff
diff --git a/plugins/gin-workflow/src/scripts/workflow_core/project.py b/plugins/gin-workflow/src/scripts/workflow_core/project.py
index bc4dab1..8f43ebc 100644
--- a/plugins/gin-workflow/src/scripts/workflow_core/project.py
+++ b/plugins/gin-workflow/src/scripts/workflow_core/project.py
@@ -34,4 +34,6 @@ class ProjectSettings:
     max_cycles: int = 2
     quick_max_files: int = 5
+    layout: str = "legacy"
+    spec_review: str = "chat"
 
     def to_dict(self) -> dict[str, Any]:
@@ -69,4 +71,6 @@ def project_settings(config: Mapping[str, Any]) -> ProjectSettings:
         max_cycles=int(review.get("max_cycles", preset["max_cycles"])),
         quick_max_files=int(_section(config, "quick").get("max_files", 5)),
+        layout=str(_section(config, "artifacts").get("layout", "legacy")),
+        spec_review=str(_section(config, "artifacts").get("spec_review", "chat")),
     )
 
@@ -83,5 +87,5 @@ def preset_assignments(*, stage: str, shape: str, rigor: str, provider_mode: str
                        stack_intent: str = "", verify_commands: Mapping[str, str] | None = None,
                        packages: tuple[Mapping[str, Any], ...] | list = (),
-                       rule_packs: Sequence[str] = ()) -> list[str]:
+                       rule_packs: Sequence[str] = (), layout: str = "") -> list[str]:
     """Explicit `--set` assignments for setup; skills never infer presets at runtime."""
     if stage not in STAGES or shape not in SHAPES or rigor not in RIGORS or provider_mode not in ("single", "multi"):
@@ -102,4 +106,6 @@ def preset_assignments(*, stage: str, shape: str, rigor: str, provider_mode: str
     if rule_packs:
         values["rules.packs"] = list(rule_packs)
+    if layout:
+        values["artifacts.layout"] = layout
     for key in VERIFY_KEYS:
         values[f"verify.checks.{key}"] = str((verify_commands or {}).get(key, ""))
```

```diff
diff --git a/plugins/gin-workflow/src/examples/config.full.yaml b/plugins/gin-workflow/src/examples/config.full.yaml
index b88843e..cd8b69e 100644
--- a/plugins/gin-workflow/src/examples/config.full.yaml
+++ b/plugins/gin-workflow/src/examples/config.full.yaml
@@ -1,5 +1,5 @@
-schema_version: "2.5"
-workflow_version: "2.5"
-setup_cli_version: "2.5"
+schema_version: "2.6"
+workflow_version: "2.6"
+setup_cli_version: "2.6"
 harness: codex
 provider_mode: multi
@@ -32,4 +32,10 @@ artifacts:
   evidence: .agent-workflow/runtime/evidence
   runtime: .agent-workflow/runtime
+  layout: sdd
+  specs: docs/specs
+  changes: docs/changes
+  adr: docs/adr
+  codebase: docs/codebase
+  spec_review: chat
 
 routing:
```

- [ ] **Step 4: Templates.** Create exactly these files:

`plugins/gin-workflow/src/templates/adr.md`:

```markdown
# {{title}}

Date: {{date}}
Status: proposed

## Context

## Decision

## Consequences
```

`plugins/gin-workflow/src/templates/codebase/ARCHITECTURE.md`:

```markdown
# ARCHITECTURE

Analysis Date: {{date}}
Scope: {{scope}}
Evidence:
Index Use:

## Components and Responsibilities

## Request and Data Flows

## Key Abstractions

## Error Handling and Cross-cutting Concerns

## Inference And Uncertainty

## Follow-up
```

`plugins/gin-workflow/src/templates/codebase/CONCERNS.md`:

```markdown
# CONCERNS

Analysis Date: {{date}}
Scope: {{scope}}
Evidence:
Index Use:

## Top Risks

| Risk | Evidence | Impact | Remediation | Suggested Bead | Confidence |
|---|---|---|---|---|---|

## Inference And Uncertainty

## Follow-up
```

`plugins/gin-workflow/src/templates/codebase/CONVENTIONS.md`:

```markdown
# CONVENTIONS

Analysis Date: {{date}}
Scope: {{scope}}
Evidence:
Index Use:

## Formatting and Linting

## Naming and Imports

## Error Handling and Logging

## Comments

## Inference And Uncertainty

## Follow-up
```

`plugins/gin-workflow/src/templates/codebase/INTEGRATIONS.md`:

```markdown
# INTEGRATIONS

Analysis Date: {{date}}
Scope: {{scope}}
Evidence:
Index Use:

## External Services and APIs

## Auth and Webhooks

## CI/CD and Deployment

## Observability

## Environment Variables (names only)

## Inference And Uncertainty

## Follow-up
```

`plugins/gin-workflow/src/templates/codebase/OVERVIEW.md`:

```markdown
# OVERVIEW

Analysis Date: {{date}}
Scope: {{scope}}
Evidence:
Index Use:

## Purpose

## Capabilities

## Primary Workflows

## Entry Points

## Non-goals

## Inference And Uncertainty

## Follow-up
```

`plugins/gin-workflow/src/templates/codebase/STACK.md`:

```markdown
# STACK

Analysis Date: {{date}}
Scope: {{scope}}
Evidence:
Index Use:

## Languages and Runtimes

## Frameworks and Versions

## Build and Test Tools

## Platform Requirements

## Inference And Uncertainty

## Follow-up
```

`plugins/gin-workflow/src/templates/codebase/STRUCTURE.md`:

```markdown
# STRUCTURE

Analysis Date: {{date}}
Scope: {{scope}}
Evidence:
Index Use:

## Directory Layout

## Module Responsibilities

## Key Files and Generated Assets

## Where to Add New Code

## Inference And Uncertainty

## Follow-up
```

`plugins/gin-workflow/src/templates/codebase/TESTING.md`:

```markdown
# TESTING

Analysis Date: {{date}}
Scope: {{scope}}
Evidence:
Index Use:

## Runners and Commands

## Organization

## Fixtures and Mocking

## Coverage and Test Types

## Inference And Uncertainty

## Follow-up
```

`plugins/gin-workflow/src/templates/design.md`:

```markdown
# Design: {{title}}

Epic: {{epic}}

## Architecture

## Data Flow

## Error Handling

## Testing
```

`plugins/gin-workflow/src/templates/proposal.md`:

```markdown
# {{title}}

Epic: {{epic}}
Date: {{date}}

## Why

## What Changes

## Capabilities Affected

## Non-goals

## Success Criteria
```

`plugins/gin-workflow/src/templates/spec-delta.md`:

```markdown
# Spec Delta: {{title}}

<!-- One block per requirement: "### REQ-<CAP>-<NNN>: <title>", one SHALL/MUST statement,
     and at least one "#### Scenario:" with "- GIVEN", "- WHEN", "- THEN" bullets.
     Get new IDs from `gin-workflow specs next-id <cap>`.
     MODIFIED and REMOVED blocks put an HTML comment "base: <hash>" on the line after the heading,
     the living block hash from `gin-workflow specs hash <REQ-ID>`; REMOVED blocks add "Reason: <why>".
     Preferred sentence patterns (EARS): "WHEN <trigger>, the <system> SHALL <response>",
     "WHILE <state>, ...", "IF <unwanted condition>, THEN ...", "WHERE <feature>, ...". -->

## ADDED

## MODIFIED

## REMOVED
```

`plugins/gin-workflow/src/templates/spec.md`:

```markdown
# {{capability}}

## Purpose

## Requirements
```

`plugins/gin-workflow/src/templates/specs-README.md`:

```markdown
# Specs

Living requirements, one folder per capability: `<capability>/spec.md`.
Changes are proposed in `../changes/<epic-id>-<slug>/spec-delta.md` and merged here at ship.

## Capabilities
```

`plugins/gin-workflow/src/templates/tests.md`:

```markdown
# Tests: {{title}}

Automated tests carry the REQ-ID in the test name or a comment. List here only manual or QE cases.

| TC | REQ | type | evidence |
|---|---|---|---|
```

- [ ] **Step 5: Packaging.** Ship `templates/` in every dist and in the launcher:

```diff
diff --git a/install.sh b/install.sh
index 7a0f217..3eb7eb2 100755
--- a/install.sh
+++ b/install.sh
@@ -10,5 +10,5 @@ UNINSTALL=false
 DRY_RUN=false
 TARGET_PLUGIN="gin-workflow"
-LAUNCHER_VERSION="2.5"
+LAUNCHER_VERSION="2.6"
 
 while [[ "$#" -gt 0 ]]; do
@@ -252,5 +252,5 @@ copy_src() {
   local target="$2"
 
-  mkdir -p "$target/commands" "$target/skills" "$target/agents" "$target/scripts" "$target/references" "$target/examples" "$target/rules"
+  mkdir -p "$target/commands" "$target/skills" "$target/agents" "$target/scripts" "$target/references" "$target/examples" "$target/rules" "$target/templates"
 
   if [ -d "$plugin_src_dir/commands" ] && [ "$(ls -A "$plugin_src_dir/commands" 2>/dev/null)" ]; then
@@ -309,4 +309,12 @@ copy_src() {
     fi
   fi
+
+  if [ -d "$plugin_src_dir/templates" ] && [ "$(ls -A "$plugin_src_dir/templates" 2>/dev/null)" ]; then
+    if [ "$LINK" = true ]; then
+      cp -rsf "$plugin_src_dir/templates/." "$target/templates/"
+    else
+      cp -rf "$plugin_src_dir/templates/." "$target/templates/"
+    fi
+  fi
 }
 
@@ -382,8 +390,9 @@ install_launcher() {
   fi
 
-  mkdir -p "$install_dir/workflow_core" "$install_dir/rules" "$(dirname "$launcher_link")"
+  mkdir -p "$install_dir/workflow_core" "$install_dir/rules" "$install_dir/templates" "$(dirname "$launcher_link")"
   cp -f "$source_dir/gin-workflow" "$launcher_target"
   cp -rf "$source_dir/workflow_core/." "$install_dir/workflow_core/"
   cp -rf "$source_dir/../rules/." "$install_dir/rules/"
+  cp -rf "$source_dir/../templates/." "$install_dir/templates/"
   chmod 755 "$launcher_target"
   ln -sfn "$launcher_target" "$launcher_link"
```

```diff
diff --git a/install.ps1 b/install.ps1
index 4469f16..cb6d4f6 100644
--- a/install.ps1
+++ b/install.ps1
@@ -15,5 +15,5 @@ Set-StrictMode -Version Latest
 $ErrorActionPreference = 'Stop'
 
-$LauncherVersion = '2.5'
+$LauncherVersion = '2.6'
 $ScriptRoot = $PSScriptRoot
 $UserHome = $env:HOME
@@ -78,5 +78,5 @@ function Copy-PluginSource {
         [Parameter(Mandatory)][string]$Destination
     )
-    foreach ($directory in @('commands', 'skills', 'agents', 'scripts', 'references', 'examples', 'rules')) {
+    foreach ($directory in @('commands', 'skills', 'agents', 'scripts', 'references', 'examples', 'rules', 'templates')) {
         Copy-DirectoryContent `
             -Source (Join-Path $PluginSource $directory) `
@@ -289,4 +289,7 @@ function Install-Launcher {
         -Source (Join-Path (Split-Path -Parent $sourceDirectory) 'rules') `
         -Destination (Join-Path $installDirectory 'rules')
+    Copy-DirectoryContent `
+        -Source (Join-Path (Split-Path -Parent $sourceDirectory) 'templates') `
+        -Destination (Join-Path $installDirectory 'templates')
 
     $shimContent = "@echo off`r`npython `"$launcherTarget`" %*`r`n"
```

`tests/install_smoke_test.sh`: replace every `2.5` with `2.6` (lines 139, 229, 230, 233, 237, 251) and add after the `rules_list` `esac` (line 242):

```bash
assert_exists "$MOCK_HOME/.local/lib/gin-workflow/2.6/templates/spec-delta.md"
assert_exists "$MOCK_HOME/.claude/skills/gin-workflow/templates/proposal.md"
```

```diff
diff --git a/tests/install_smoke_test.ps1 b/tests/install_smoke_test.ps1
index 69b05ab..02e6c99 100644
--- a/tests/install_smoke_test.ps1
+++ b/tests/install_smoke_test.ps1
@@ -63,5 +63,5 @@ try {
 
     $dryRunOutput = Invoke-Installer @{ Platform = 'codex'; DryRun = $true }
-    Assert-Contains $dryRunOutput 'would install gin-workflow launcher version 2.5'
+    Assert-Contains $dryRunOutput 'would install gin-workflow launcher version 2.6'
     Assert-Exists (Join-Path $Root 'plugins/gin-workflow/dist/codex/.codex-plugin/plugin.json')
     Assert-True (-not (Test-Path -LiteralPath (Join-Path $TestHome '.local/bin/gin-workflow.cmd'))) 'Dry-run wrote the launcher shim'
@@ -74,6 +74,7 @@ try {
     Assert-Exists (Join-Path $project '.codex/skills/setup/SKILL.md')
     Assert-Exists (Join-Path $project '.codex/.codex-plugin/plugin.json')
-    Assert-Exists (Join-Path $TestHome '.local/lib/gin-workflow/2.5/workflow_core/cli.py')
-    Assert-Exists (Join-Path $TestHome '.local/lib/gin-workflow/2.5/rules/core.md')
+    Assert-Exists (Join-Path $TestHome '.local/lib/gin-workflow/2.6/workflow_core/cli.py')
+    Assert-Exists (Join-Path $TestHome '.local/lib/gin-workflow/2.6/rules/core.md')
+    Assert-Exists (Join-Path $TestHome '.local/lib/gin-workflow/2.6/templates/spec-delta.md')
     Assert-Exists (Join-Path $TestHome '.local/bin/gin-workflow.cmd')
 
@@ -111,5 +112,5 @@ try {
     if ($IsWindows) {
         $version = & cmd.exe /d /c (Join-Path $TestHome '.local/bin/gin-workflow.cmd') --version
-        Assert-True (($version | Out-String).Trim() -eq 'gin-workflow 2.5') "Unexpected launcher version: $version"
+        Assert-True (($version | Out-String).Trim() -eq 'gin-workflow 2.6') "Unexpected launcher version: $version"
         $rulesList = & cmd.exe /d /c (Join-Path $TestHome '.local/bin/gin-workflow.cmd') rules --list --repository $TestHome
         Assert-True (($rulesList | Out-String).Contains('core (plugin, core)')) "Launcher did not list the core rule pack: $rulesList"
@@ -127,5 +128,5 @@ try {
     Invoke-Installer @{ Platform = 'codex'; Project = $project } | Out-Null
     $upgradedShim = [IO.File]::ReadAllText($shim)
-    Assert-Contains $upgradedShim (Join-Path $managedRoot '2.5/gin-workflow')
+    Assert-Contains $upgradedShim (Join-Path $managedRoot '2.6/gin-workflow')
     Assert-Exists $oldLauncher
```

- [ ] **Step 6:** Run the Step 2 command → PASS. Full suite `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py` → `OK`; `bash tests/install_smoke_test.sh` → exit 0.

- [ ] **Step 7:** Commit `feat(config): schema 2.6 with SDD artifact keys, templates, and packaging`.

### Track 2: Specs core (parse, lint, next-id, new, hash, template, renumber) and `gin-workflow specs`

**Metadata:**
- Dependencies: Track 1
- Provider role: backend
- Reasoning: high
- Model guidance: high_reasoning
- Estimated complexity: high

**Files:**
- Create: `plugins/gin-workflow/src/scripts/workflow_core/specs.py`, `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py`
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/cli.py:69-74` (route `specs`), `tests/install_smoke_test.sh` (one line), `tests/workflow_providers/test_harness_packaging.py` (two artifacts)
- Test: `tests/workflow_core/specs_fixtures.py` (new helper), `tests/workflow_core/test_specs.py` (new)

**Interfaces:**
- Consumes: Track 1 templates and config keys; `atomic.atomic_write_many(files, mode=)`, `configuration.resolve_effective_config`, `rules._glob_regex`.
- Produces: `SpecsError`; `Block(id, title, section, start, end, text)` with `.cap`, `.base`; `cap_of(req_id) -> str`; `sdd_config(config) -> dict`; `load_config(root)`; `require_layout(cfg, layout)`; `plugin_templates_dir()`; `template_text(root, name) -> str`; `render(text, values)`; `parse_blocks(text) -> (list[Block], list[(line, message)])`; `block_hash(text) -> str`; `lint_block(block) -> list[str]`; `shown(root, path) -> str`; `living_files`, `living_blocks(root, cfg) -> dict[id, (Path, Block)]`; `find_change(root, cfg, change_id) -> Path`; `change_epic(change) -> str`; `delta_blocks(root, change) -> (list[Block], list[str])`; `lint_living(root, cfg)`, `lint_change(root, cfg, change, *, against=None) -> list[str]`; `ids_at_ref(root, cfg, ref, *, exclude=None) -> set[str]`; `scan_ids(root, cfg) -> (set[str], list[str])`; `next_id(root, cfg, cap) -> (str, list[str])`; `new_change(root, cfg, slug, epic, title="", today=None) -> Path`; `requirement_hash(root, cfg, req_id) -> (Block, str)`; `default_base(root) -> str`; `test_files(root, cfg, candidates) -> list[str]`; `renumber(root, cfg, change, old, new, *, against=None) -> dict`; constants `SDD_DEFAULTS`, `DELTA_SECTIONS`, `CHANGE_TEMPLATES`, `REQ_ID`, `_BASE`. CLI: `gin-workflow specs {new,next-id,lint,hash,template,renumber}` with `--repository`, `--format text|json`; exit 0/1/2.

- [ ] **Step 1: Failing tests.** Create `tests/workflow_core/specs_fixtures.py`:

```python
"""Shared helpers for SDD spec tests: a temporary git repository with an sdd config."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

LAUNCHER = SCRIPTS / "gin-workflow"

AUTH_SPEC = """# Auth

## Purpose

Sign-in.

## Requirements

### REQ-AUTH-001: Sign in with password
The system SHALL sign a user in with a valid password.

#### Scenario: valid password
- GIVEN a registered user
- WHEN they submit the right password
- THEN they are signed in

### REQ-AUTH-002: Reject wrong password
The system SHALL reject a wrong password.

#### Scenario: wrong password
- GIVEN a registered user
- WHEN they submit a wrong password
- THEN they see "Invalid credentials"
"""

ADDED_BLOCK = """### REQ-AUTH-003: Lock account after failed logins
The system SHALL lock an account for 15 minutes after 5 failed logins.

#### Scenario: fifth failure locks
- GIVEN a user with 4 failed logins
- WHEN the next login fails
- THEN the account is locked
"""


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout


def make_repo(root: Path, *, layout: str = "sdd", extra: str = "") -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")
    (root / ".agent-workflow").mkdir()
    (root / ".agent-workflow/config.yaml").write_text(
        f"schema_version: '2.6'\nartifacts:\n  layout: {layout}\n{extra}", encoding="utf-8")
    return root


def write(root: Path, relative: str, text: str) -> Path:
    path = Path(root) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def commit_all(root: Path, message: str = "c") -> None:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)


def delta(*, added: str = "", modified: str = "", removed: str = "") -> str:
    return f"# Spec Delta\n\n## ADDED\n\n{added}\n## MODIFIED\n\n{modified}\n## REMOVED\n\n{removed}"


def make_change(root: Path, name: str = "ep-1-lockout", *, epic: str = "ep-1", spec_delta: str = "") -> Path:
    change = Path(root) / "docs/changes" / name
    write(root, f"docs/changes/{name}/proposal.md", f"# Lockout\n\nEpic: {epic}\n")
    write(root, f"docs/changes/{name}/spec-delta.md", spec_delta or delta(added=ADDED_BLOCK))
    write(root, f"docs/changes/{name}/tests.md", "| TC | REQ | type | evidence |\n|---|---|---|---|\n")
    return change
```

Create `tests/workflow_core/test_specs.py`:

```python
"""SDD specs core: blocks, hash, lint, next-id, new, hash/template commands, renumber."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specs_fixtures import (ADDED_BLOCK, AUTH_SPEC, LAUNCHER, commit_all, delta, git,  # noqa: E402
                            make_change, make_repo, write)
from workflow_core import specs  # noqa: E402
from workflow_core.specs import SpecsError  # noqa: E402


def run_specs(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(LAUNCHER), "specs", *args, "--repository", str(root)],
                          text=True, capture_output=True, check=False)


class TestBlocks(unittest.TestCase):
    def test_parse_blocks_sections_and_ranges(self):
        blocks, errors = specs.parse_blocks(AUTH_SPEC)
        self.assertEqual([], errors)
        self.assertEqual(["REQ-AUTH-001", "REQ-AUTH-002"], [b.id for b in blocks])
        self.assertEqual({"Requirements"}, {b.section for b in blocks})
        self.assertTrue(blocks[0].text.startswith("### REQ-AUTH-001: Sign in with password"))
        self.assertTrue(blocks[0].text.endswith("- THEN they are signed in"))
        self.assertEqual("auth", blocks[0].cap)

    def test_malformed_heading_is_reported(self):
        _, errors = specs.parse_blocks("## Requirements\n\n### Lockout\nThe system SHALL lock.\n")
        self.assertEqual(3, errors[0][0])

    def test_multi_word_capability(self):
        self.assertEqual("user-profile", specs.cap_of("REQ-USER-PROFILE-012"))
        with self.assertRaises(SpecsError):
            specs.cap_of("REQ-auth-1")

    def test_hash_ignores_base_line_and_trailing_space(self):
        plain = "### REQ-AUTH-001: X\nThe system SHALL x.\n"
        noisy = "\n### REQ-AUTH-001: X   \n<!-- base: " + "a" * 64 + " -->\nThe system SHALL x.\n\n"
        self.assertEqual(specs.block_hash(plain), specs.block_hash(noisy))
        self.assertNotEqual(specs.block_hash(plain), specs.block_hash(plain.replace("x.", "y.")))

    def test_lint_block_rules(self):
        block = specs.parse_blocks(ADDED_BLOCK)[0][0]
        self.assertEqual([], specs.lint_block(block))
        bare = specs.parse_blocks("### REQ-AUTH-009: X\nThe system locks.\n\n#### Scenario: s\n- GIVEN a\n- THEN b\n")[0][0]
        self.assertEqual(["REQ-AUTH-009: needs a SHALL or MUST statement", "REQ-AUTH-009: scenario 1 lacks WHEN"],
                         specs.lint_block(bare))
        none = specs.parse_blocks("### REQ-AUTH-009: X\nThe system MUST lock.\n")[0][0]
        self.assertEqual(["REQ-AUTH-009: needs at least one '#### Scenario:'"], specs.lint_block(none))


class TestRepositoryCommands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(Path(self.tmp.name) / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        self.cfg = specs.sdd_config(specs.load_config(self.root))

    def tearDown(self):
        self.tmp.cleanup()

    def test_sdd_config_defaults(self):
        self.assertEqual("docs/specs", self.cfg["specs"])
        self.assertEqual("chat", self.cfg["spec_review"])
        self.assertIn("**/test_*.py", self.cfg["test_globs"])

    def test_lint_living_ok_then_wrong_folder_and_duplicate(self):
        self.assertEqual([], specs.lint_living(self.root, self.cfg))
        write(self.root, "docs/specs/billing/spec.md", "# Billing\n\n## Requirements\n\n" + ADDED_BLOCK.replace("003", "001"))
        errors = specs.lint_living(self.root, self.cfg)
        self.assertTrue(any("REQ-AUTH-001 belongs in auth/spec.md" in e for e in errors), errors)
        self.assertTrue(any("REQ-AUTH-001 duplicates" in e for e in errors), errors)

    def test_lint_change_rules(self):
        change = make_change(self.root)
        self.assertEqual([], specs.lint_change(self.root, self.cfg, change))
        base = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-002")[1]
        bad = delta(added=ADDED_BLOCK.replace("003", "001"),
                    modified="### REQ-AUTH-002: Reject wrong password\nThe system SHALL reject.\n\n"
                             "#### Scenario: s\n- GIVEN a\n- WHEN b\n- THEN c\n",
                    removed=f"### REQ-AUTH-001: Sign in with password\n<!-- base: {base} -->\n")
        write(self.root, "docs/changes/ep-1-lockout/spec-delta.md", bad)
        errors = specs.lint_change(self.root, self.cfg, change)
        self.assertTrue(any("REQ-AUTH-001 already exists" in e for e in errors), errors)
        self.assertTrue(any("REQ-AUTH-002 needs '<!-- base: <hash> -->'" in e for e in errors), errors)
        self.assertTrue(any("REQ-AUTH-001 needs a 'Reason: <why>' line" in e for e in errors), errors)
        self.assertTrue(any("REQ-AUTH-001 appears twice" in e for e in errors), errors)

    def test_block_outside_delta_sections(self):
        change = make_change(self.root, spec_delta="# Delta\n\n## Other\n\n" + ADDED_BLOCK)
        self.assertTrue(any("outside ## ADDED/MODIFIED/REMOVED" in e for e in specs.lint_change(self.root, self.cfg, change)))

    def test_lint_against_base_flags_id_taken_on_base_but_not_own_change(self):
        make_change(self.root)
        commit_all(self.root)
        git(self.root, "checkout", "-q", "-b", "feature")
        other = make_change(self.root, "ep-2-other", epic="ep-2")
        self.assertEqual(["docs/changes/ep-2-other/spec-delta.md:5: REQ-AUTH-003 is already used on main"],
                         [e for e in specs.lint_change(self.root, self.cfg, other, against="main") if "already used" in e])
        own = self.root / "docs/changes/ep-1-lockout"
        self.assertEqual([], specs.lint_change(self.root, self.cfg, own, against="main"))

    def test_find_change_by_full_name_or_epic_prefix(self):
        change = make_change(self.root)
        self.assertEqual(change, specs.find_change(self.root, self.cfg, "ep-1-lockout"))
        self.assertEqual(change, specs.find_change(self.root, self.cfg, "ep-1"))
        with self.assertRaises(SpecsError):
            specs.find_change(self.root, self.cfg, "ep-9")

    def test_next_id_scans_tree_worktrees_and_remote(self):
        self.assertEqual("REQ-AUTH-003", specs.next_id(self.root, self.cfg, "auth")[0])
        self.assertEqual("REQ-BILLING-001", specs.next_id(self.root, self.cfg, "billing")[0])
        commit_all(self.root)
        worktree = Path(self.tmp.name) / "wt"
        git(self.root, "worktree", "add", "-q", "-b", "wt", str(worktree))
        make_change(worktree)
        self.assertEqual("REQ-AUTH-004", specs.next_id(self.root, self.cfg, "auth")[0])
        remote = Path(self.tmp.name) / "remote.git"
        git(Path(self.tmp.name), "init", "-q", "--bare", str(remote))
        git(self.root, "remote", "add", "origin", str(remote))
        git(self.root, "checkout", "-q", "-b", "pushed")
        write(self.root, "docs/changes/ep-5-x/spec-delta.md", delta(added=ADDED_BLOCK.replace("003", "007")))
        commit_all(self.root)
        git(self.root, "push", "-q", "origin", "pushed")
        git(self.root, "checkout", "-q", "main")
        self.assertEqual(("REQ-AUTH-008", []), specs.next_id(self.root, self.cfg, "auth"))

    def test_next_id_warns_without_remote(self):
        self.assertEqual(["no git remote; scanned local worktrees only"], specs.next_id(self.root, self.cfg, "auth")[1])

    def test_new_change_renders_templates_and_refuses_existing(self):
        change = specs.new_change(self.root, self.cfg, "lockout", "ep-1", "Account lockout")
        self.assertEqual(sorted(specs.CHANGE_TEMPLATES), sorted(p.name for p in change.iterdir()))
        proposal = (change / "proposal.md").read_text(encoding="utf-8")
        self.assertIn("# Account lockout", proposal)
        self.assertEqual("ep-1", specs.change_epic(change))
        with self.assertRaises(SpecsError):
            specs.new_change(self.root, self.cfg, "lockout", "ep-1")
        with self.assertRaises(SpecsError):
            specs.new_change(self.root, self.cfg, "Bad Slug", "ep-1")

    def test_project_template_overrides_plugin(self):
        write(self.root, ".agent-workflow/templates/proposal.md", "# {{title}} (team)\n\nEpic: {{epic}}\n")
        change = specs.new_change(self.root, self.cfg, "lockout", "ep-1", "Lockout")
        self.assertEqual("# Lockout (team)\n\nEpic: ep-1\n", (change / "proposal.md").read_text(encoding="utf-8"))

    def test_renumber_rewrites_change_tests_and_bead_labels(self):
        make_change(self.root)
        commit_all(self.root)
        git(self.root, "checkout", "-q", "-b", "feature")
        write(self.root, "tests/test_lockout.py", "def test_lock():  # REQ-AUTH-003\n    pass\n# REQ-AUTH-0030\n")
        write(self.root, "src/app.py", "# REQ-AUTH-003\n")
        commit_all(self.root)
        change = self.root / "docs/changes/ep-1-lockout"
        calls = []

        def fake_bd(_root, argv):
            calls.append(argv)
            return [{"id": "ep-1.1"}] if argv[0] == "list" else ""

        with mock.patch("workflow_core.specs._bd", fake_bd):
            result = specs.renumber(self.root, self.cfg, change, "REQ-AUTH-003", "REQ-AUTH-004", against="main")
        self.assertEqual(["docs/changes/ep-1-lockout/spec-delta.md", "tests/test_lockout.py"], result["files"])
        self.assertIn("# REQ-AUTH-0030", (self.root / "tests/test_lockout.py").read_text(encoding="utf-8"))
        self.assertIn("REQ-AUTH-004", (self.root / "tests/test_lockout.py").read_text(encoding="utf-8"))
        self.assertEqual("# REQ-AUTH-003\n", (self.root / "src/app.py").read_text(encoding="utf-8"))
        self.assertEqual(["list", "--parent", "ep-1", "--label", "req:REQ-AUTH-003", "--all", "--limit", "0", "--json"],
                         calls[0])
        self.assertEqual(["update", "ep-1.1", "--remove-label", "req:REQ-AUTH-003", "--add-label", "req:REQ-AUTH-004"],
                         calls[1])

    def test_renumber_refuses_taken_id(self):
        change = make_change(self.root)
        with self.assertRaises(SpecsError):
            specs.renumber(self.root, self.cfg, change, "REQ-AUTH-003", "REQ-AUTH-002", against="HEAD")


class TestSpecsCli(unittest.TestCase):
    def test_exit_codes_and_layout_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_repo(Path(directory), layout="legacy")
            result = run_specs(root, "lint")
            self.assertEqual(2, result.returncode)
            self.assertIn("artifacts.layout is 'legacy'", result.stderr)
            self.assertEqual(0, run_specs(root, "template", "proposal.md").returncode)
        with tempfile.TemporaryDirectory() as directory:
            root = make_repo(Path(directory))
            write(root, "docs/specs/auth/spec.md", AUTH_SPEC)
            self.assertEqual(0, run_specs(root, "lint").returncode)
            self.assertEqual("REQ-AUTH-003", run_specs(root, "next-id", "auth").stdout.strip())
            hashed = run_specs(root, "hash", "REQ-AUTH-001", "--format", "json")
            self.assertEqual(64, len(json.loads(hashed.stdout)["hash"]))
            created = run_specs(root, "new", "lockout", "--epic", "ep-1")
            self.assertEqual("docs/changes/ep-1-lockout", created.stdout.strip())
            write(root, "docs/changes/ep-1-lockout/spec-delta.md", delta(added="### REQ-AUTH-003: X\nNo statement.\n"))
            linted = run_specs(root, "lint", "--change", "ep-1", "--format", "json")
            self.assertEqual(1, linted.returncode)
            self.assertEqual("findings", json.loads(linted.stdout)["status"])
            self.assertEqual(2, run_specs(root, "lint", "--change", "nope").returncode)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2:** Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/workflow_core/test_specs.py -v` → FAIL (`ModuleNotFoundError: workflow_core.specs`).

- [ ] **Step 3: Implement** `plugins/gin-workflow/src/scripts/workflow_core/specs.py`:

```python
"""SDD living specs: requirement blocks, lint, ID allocation, change folders, renumbering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Mapping, Sequence

from .atomic import atomic_write_many
from .configuration import resolve_effective_config

DEFAULT_TEST_GLOBS = ("**/test_*.py", "**/*_test.py", "**/*.test.*", "**/*.spec.*", "tests/**", "__tests__/**")
SDD_DEFAULTS: dict[str, Any] = {
    "layout": "legacy", "specs": "docs/specs", "changes": "docs/changes", "adr": "docs/adr",
    "codebase": "docs/codebase", "spec_review": "chat", "test_globs": list(DEFAULT_TEST_GLOBS),
}
DELTA_SECTIONS = ("ADDED", "MODIFIED", "REMOVED")
CHANGE_TEMPLATES = ("proposal.md", "spec-delta.md", "design.md", "tests.md")
REQ_ID = re.compile(r"\bREQ-([A-Z][A-Z0-9-]*)-(\d{3,})\b")
_FULL_ID = re.compile(r"^REQ-([A-Z][A-Z0-9-]*)-(\d{3,})$")
_HEADING = re.compile(r"^### (REQ-[A-Z][A-Z0-9-]*-\d{3,}): (\S.*)$")
_HEADING_LINE = re.compile(r"^### (REQ-[A-Z][A-Z0-9-]*-\d{3,}):", re.MULTILINE)
_BASE = re.compile(r"^<!-- base: ([0-9a-f]{64}) -->$")
_STATEMENT = re.compile(r"\b(SHALL|MUST)\b")
_CAP = re.compile(r"^[a-z][a-z0-9-]*$")
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_EPIC_LINE = re.compile(r"^Epic: (\S+)$", re.MULTILINE)


class SpecsError(ValueError):
    """Usage or configuration error (exit 2)."""


@dataclass(frozen=True)
class Block:
    id: str
    title: str
    section: str
    start: int
    end: int
    text: str

    @property
    def cap(self) -> str:
        return cap_of(self.id)

    @property
    def base(self) -> str | None:
        for line in self.text.splitlines()[1:]:
            found = _BASE.match(line.strip())
            if found:
                return found.group(1)
        return None


def cap_of(req_id: str) -> str:
    found = _FULL_ID.match(req_id)
    if not found:
        raise SpecsError(f"not a requirement id: {req_id!r}")
    return found.group(1).lower()


def sdd_config(config: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = config.get("artifacts") if isinstance(config.get("artifacts"), Mapping) else {}
    return {key: artifacts.get(key, default) for key, default in SDD_DEFAULTS.items()}


def load_config(repository: Path) -> Mapping[str, Any]:
    if not (Path(repository) / ".agent-workflow/config.yaml").is_file():
        raise SpecsError("gin-workflow setup is required; run /setup once")
    return resolve_effective_config(Path(repository), write=False).config.to_dict()


def require_layout(cfg: Mapping[str, Any], layout: str) -> None:
    if cfg["layout"] != layout:
        raise SpecsError(f"artifacts.layout is {cfg['layout']!r}; this command needs {layout!r}")


def plugin_templates_dir() -> Path:
    """Launcher layout ships `templates/` beside `workflow_core/`; plugin trees have it two levels up."""
    here = Path(__file__).resolve().parent
    for candidate in (here.parent / "templates", here.parent.parent / "templates"):
        if candidate.is_dir():
            return candidate
    raise SpecsError("plugin templates directory not found next to workflow_core")


def template_text(repository: Path, name: str) -> str:
    """Project override `.agent-workflow/templates/<name>` wins over the plugin template."""
    for base in (Path(repository) / ".agent-workflow/templates", plugin_templates_dir()):
        path = base / name
        if path.is_file():
            return path.read_text(encoding="utf-8")
    raise SpecsError(f"unknown template: {name}")


def render(text: str, values: Mapping[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def parse_blocks(text: str) -> tuple[list[Block], list[tuple[int, str]]]:
    """Requirement blocks (`### REQ-…` up to the next `##`/`###` heading) and malformed headings."""
    lines = text.splitlines()
    blocks: list[Block] = []
    errors: list[tuple[int, str]] = []
    section = ""
    current: tuple[str, str, int] | None = None

    def close(end: int) -> None:
        if current is not None:
            req_id, title, start = current
            body = "\n".join(lines[start:end]).rstrip()
            blocks.append(Block(req_id, title, section, start, end, body))

    for index, line in enumerate(lines):
        if line.startswith("## ") or line.startswith("### "):
            close(index)
            current = None
        if line.startswith("## "):
            section = line[3:].strip()
        elif line.startswith("### "):
            found = _HEADING.match(line)
            if found:
                current = (found.group(1), found.group(2), index)
            else:
                errors.append((index + 1, f"heading is not a requirement '### REQ-<CAP>-<NNN>: <title>': {line!r}"))
    close(len(lines))
    return blocks, errors


def block_hash(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines() if not _BASE.match(line.strip())]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def lint_block(block: Block) -> list[str]:
    """Statement and scenario rules for an ADDED, MODIFIED, or living block."""
    errors: list[str] = []
    body = block.text.splitlines()[1:]
    prose = [line for line in body if line.strip() and not line.startswith("#") and not line.startswith("- ")]
    if not any(_STATEMENT.search(line) for line in prose):
        errors.append(f"{block.id}: needs a SHALL or MUST statement")
    scenarios: list[list[str]] = []
    for line in body:
        if line.startswith("#### Scenario:"):
            scenarios.append([])
        elif line.startswith("#### "):
            errors.append(f"{block.id}: only '#### Scenario:' sub-headings are allowed")
        elif scenarios and line.startswith("- "):
            scenarios[-1].append(line[2:].split(" ", 1)[0])
    if not scenarios:
        errors.append(f"{block.id}: needs at least one '#### Scenario:'")
    for number, steps in enumerate(scenarios, start=1):
        missing = [step for step in ("GIVEN", "WHEN", "THEN") if step not in steps]
        if missing:
            errors.append(f"{block.id}: scenario {number} lacks {', '.join(missing)}")
    return errors


def specs_dir(root: Path, cfg: Mapping[str, Any]) -> Path:
    return Path(root) / cfg["specs"]


def changes_dir(root: Path, cfg: Mapping[str, Any]) -> Path:
    return Path(root) / cfg["changes"]


def living_files(root: Path, cfg: Mapping[str, Any]) -> dict[str, Path]:
    base = specs_dir(root, cfg)
    return {path.parent.name: path for path in sorted(base.glob("*/spec.md"))} if base.is_dir() else {}


def living_blocks(root: Path, cfg: Mapping[str, Any]) -> dict[str, tuple[Path, Block]]:
    found: dict[str, tuple[Path, Block]] = {}
    for path in living_files(root, cfg).values():
        for block in parse_blocks(path.read_text(encoding="utf-8"))[0]:
            found.setdefault(block.id, (path, block))
    return found


def find_change(root: Path, cfg: Mapping[str, Any], change_id: str) -> Path:
    base = changes_dir(root, cfg)
    exact = base / change_id
    if exact.is_dir() and change_id != "archive":
        return exact
    matches = [p for p in sorted(base.glob(f"{change_id}-*")) if p.is_dir()] if base.is_dir() else []
    if len(matches) == 1:
        return matches[0]
    raise SpecsError(f"unknown change {change_id!r} under {cfg['changes']}" if not matches
                     else f"change {change_id!r} is ambiguous: {', '.join(p.name for p in matches)}")


def change_epic(change: Path) -> str:
    proposal = change / "proposal.md"
    found = _EPIC_LINE.search(proposal.read_text(encoding="utf-8")) if proposal.is_file() else None
    if not found:
        raise SpecsError(f"{proposal}: missing 'Epic: <id>' line")
    return found.group(1)


def shown(root: Path, path: Path) -> str:
    """Repository-relative path for findings."""
    try:
        return Path(path).relative_to(root).as_posix()
    except ValueError:
        return str(path)


def delta_blocks(root: Path, change: Path) -> tuple[list[Block], list[str]]:
    path = change / "spec-delta.md"
    if not path.is_file():
        return [], [f"{shown(root, path)}: missing spec-delta.md"]
    blocks, malformed = parse_blocks(path.read_text(encoding="utf-8"))
    errors = [f"{shown(root, path)}:{line}: {message}" for line, message in malformed]
    for block in blocks:
        if block.section not in DELTA_SECTIONS:
            errors.append(f"{shown(root, path)}:{block.start + 1}: {block.id} is outside ## ADDED/MODIFIED/REMOVED")
    return blocks, errors


def lint_living(root: Path, cfg: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}
    for cap, path in living_files(root, cfg).items():
        name = shown(root, path)
        if not _CAP.match(cap):
            errors.append(f"{name}: capability folder must match [a-z][a-z0-9-]*")
        blocks, malformed = parse_blocks(path.read_text(encoding="utf-8"))
        errors += [f"{name}:{line}: {message}" for line, message in malformed]
        for block in blocks:
            where = f"{name}:{block.start + 1}"
            if block.cap != cap:
                errors.append(f"{where}: {block.id} belongs in {block.cap}/spec.md")
            if block.id in seen:
                errors.append(f"{where}: {block.id} duplicates {seen[block.id]}")
            seen.setdefault(block.id, name)
            errors += [f"{where}: {message}" for message in lint_block(block)]
    return errors


def lint_change(root: Path, cfg: Mapping[str, Any], change: Path, *, against: str | None = None) -> list[str]:
    blocks, errors = delta_blocks(root, change)
    path = shown(root, change / "spec-delta.md")
    living = living_blocks(root, cfg)
    seen: set[str] = set()
    for block in blocks:
        where = f"{path}:{block.start + 1}"
        if block.id in seen:
            errors.append(f"{where}: {block.id} appears twice in the delta")
        seen.add(block.id)
        if not _CAP.match(block.cap):
            errors.append(f"{where}: capability {block.cap!r} must match [a-z][a-z0-9-]*")
        if block.section == "ADDED":
            if block.id in living:
                errors.append(f"{where}: {block.id} already exists in {shown(root, living[block.id][0])}")
            errors += [f"{where}: {message}" for message in lint_block(block)]
        elif block.section in ("MODIFIED", "REMOVED"):
            if block.id not in living:
                errors.append(f"{where}: {block.id} is not in the living spec")
            if block.base is None:
                errors.append(f"{where}: {block.id} needs '<!-- base: <hash> -->' (gin-workflow specs hash {block.id})")
            if block.section == "MODIFIED":
                errors += [f"{where}: {message}" for message in lint_block(block)]
            elif not re.search(r"^Reason: \S", block.text, re.MULTILINE):
                errors.append(f"{where}: {block.id} needs a 'Reason: <why>' line")
    if against:
        own = Path(cfg["changes"]) / change.name
        taken = ids_at_ref(root, cfg, against, exclude=own)
        for block in blocks:
            if block.section == "ADDED" and block.id in taken:
                errors.append(f"{path}:{block.start + 1}: {block.id} is already used on {against}")
    return errors


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)


def _ids_in(text: str) -> set[str]:
    return set(_HEADING_LINE.findall(text))


def _local_ids(tree: Path, cfg: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    for pattern, base in (("*/spec.md", cfg["specs"]), ("**/spec-delta.md", cfg["changes"])):
        directory = Path(tree) / base
        if directory.is_dir():
            for path in directory.glob(pattern):
                ids |= _ids_in(path.read_text(encoding="utf-8"))
    return ids


def ids_at_ref(root: Path, cfg: Mapping[str, Any], ref: str, *, exclude: Path | None = None) -> set[str]:
    """Requirement ids in living specs and deltas at a git ref, optionally skipping one change folder."""
    result = _git(root, "grep", "-I", "-E", "^### REQ-", ref, "--", cfg["specs"], cfg["changes"])
    ids: set[str] = set()
    skip = f"{exclude.as_posix()}/" if exclude else None
    for line in result.stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) == 3 and not (skip and parts[1].startswith(skip)):
            ids |= _ids_in(parts[2])
    return ids


def scan_ids(root: Path, cfg: Mapping[str, Any]) -> tuple[set[str], list[str]]:
    """Ids in this tree, every local worktree, and every remote-tracking branch."""
    ids = _local_ids(root, cfg)
    warnings: list[str] = []
    listed = _git(root, "worktree", "list", "--porcelain")
    if listed.returncode != 0:
        return ids, ["not a git repository; scanned this tree only"]
    for line in listed.stdout.splitlines():
        if line.startswith("worktree "):
            ids |= _local_ids(Path(line[len("worktree "):]), cfg)
    if not _git(root, "remote").stdout.strip():
        warnings.append("no git remote; scanned local worktrees only")
        return ids, warnings
    if _git(root, "fetch", "--quiet").returncode != 0:
        warnings.append("git fetch failed; remote branches may be stale")
    refs = _git(root, "for-each-ref", "--format=%(refname)", "refs/remotes").stdout.split()
    for ref in refs:
        if not ref.endswith("/HEAD"):
            ids |= ids_at_ref(root, cfg, ref)
    return ids, warnings


def next_id(root: Path, cfg: Mapping[str, Any], cap: str) -> tuple[str, list[str]]:
    if not _CAP.match(cap):
        raise SpecsError(f"capability {cap!r} must match [a-z][a-z0-9-]*")
    ids, warnings = scan_ids(root, cfg)
    numbers = [int(_FULL_ID.match(item).group(2)) for item in ids if cap_of(item) == cap]
    return f"REQ-{cap.upper()}-{max(numbers, default=0) + 1:03d}", warnings


def new_change(root: Path, cfg: Mapping[str, Any], slug: str, epic: str, title: str = "",
               today: date | None = None) -> Path:
    if not _SLUG.match(slug):
        raise SpecsError(f"slug {slug!r} must match [a-z0-9][a-z0-9-]*")
    change = changes_dir(root, cfg) / f"{epic}-{slug}"
    if change.exists():
        raise SpecsError(f"change folder already exists: {change}")
    values = {"epic": epic, "slug": slug, "title": title or slug.replace("-", " ").capitalize(),
              "date": (today or date.today()).isoformat()}
    atomic_write_many({change / name: render(template_text(root, name), values).encode("utf-8")
                       for name in CHANGE_TEMPLATES}, mode=0o644)
    return change


def requirement_hash(root: Path, cfg: Mapping[str, Any], req_id: str) -> tuple[Block, str]:
    living = living_blocks(root, cfg)
    if req_id not in living:
        raise SpecsError(f"{req_id} is not in the living spec")
    block = living[req_id][1]
    return block, block_hash(block.text)


def _bd(root: Path, argv: Sequence[str]) -> Any:
    executable = shutil.which("bd")
    if executable is None:
        raise SpecsError("bd is not installed")
    completed = subprocess.run([executable, *argv], cwd=root, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise SpecsError(f"bd {' '.join(argv)} failed: {completed.stderr.strip()}")
    return json.loads(completed.stdout) if "--json" in argv else completed.stdout


def default_base(root: Path) -> str:
    for branch in ("main", "master"):
        found = _git(root, "merge-base", "HEAD", branch)
        if found.returncode == 0:
            return found.stdout.strip()
    raise SpecsError("cannot find a merge-base with main or master; pass --against")


def test_files(root: Path, cfg: Mapping[str, Any], candidates: Sequence[str]) -> list[str]:
    from .rules import _glob_regex

    patterns = [_glob_regex(pattern) for pattern in cfg["test_globs"]]
    return [path for path in candidates if any(pattern.match(path) for pattern in patterns)]


def renumber(root: Path, cfg: Mapping[str, Any], change: Path, old: str, new: str,
             *, against: str | None = None) -> dict[str, Any]:
    cap_of(old)
    cap_of(new)
    taken, _ = scan_ids(root, cfg)
    if new in taken:
        raise SpecsError(f"{new} is already used")
    base = against or default_base(root)
    changed = _git(root, "diff", "--name-only", f"{base}...HEAD").stdout.split()
    targets = sorted(change.rglob("*.md")) + [Path(root) / path for path in test_files(root, cfg, changed)]
    pattern = re.compile(rf"\b{re.escape(old)}\b")
    writes: dict[Path, bytes] = {}
    for path in targets:
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if pattern.search(text):
                writes[path] = pattern.sub(new, text).encode("utf-8")
    beads = _bd(root, ["list", "--parent", change_epic(change), "--label", f"req:{old}",
                       "--all", "--limit", "0", "--json"])
    atomic_write_many(writes, mode=0o644)
    relabeled = []
    for bead in beads:
        _bd(root, ["update", bead["id"], "--remove-label", f"req:{old}", "--add-label", f"req:{new}"])
        relabeled.append(bead["id"])
    return {"old": old, "new": new, "files": sorted(str(p.relative_to(root)) for p in writes), "beads": relabeled}
```

Create `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py`:

```python
"""`gin-workflow specs` command line: exit 0 ok, 1 content findings, 2 usage or configuration error."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from . import specs


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repository", type=Path, default=Path.cwd())
    common.add_argument("--format", choices=("text", "json"), default="text")
    parser = argparse.ArgumentParser(prog="gin-workflow specs")
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("new", parents=[common])
    item.add_argument("slug")
    item.add_argument("--epic", required=True)
    item.add_argument("--title", default="")
    sub.add_parser("next-id", parents=[common]).add_argument("cap")
    item = sub.add_parser("lint", parents=[common])
    item.add_argument("--change")
    item.add_argument("--against")
    sub.add_parser("hash", parents=[common]).add_argument("req_id")
    sub.add_parser("template", parents=[common]).add_argument("name")
    item = sub.add_parser("renumber", parents=[common])
    item.add_argument("old")
    item.add_argument("new")
    item.add_argument("--change", required=True)
    item.add_argument("--against")
    return parser


def _emit(payload: dict[str, Any], output_format: str, text: str) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True) if output_format == "json" else text)


def _findings(errors: list[str], output_format: str, ok: str) -> int:
    _emit({"status": "findings" if errors else "ok", "findings": errors}, output_format,
          "\n".join(errors) if errors else ok)
    return 1 if errors else 0


def _run(args: argparse.Namespace) -> int:
    root = args.repository.resolve()
    if args.command == "template":
        text = specs.template_text(root, args.name)
        _emit({"name": args.name, "text": text}, args.format, text.rstrip("\n"))
        return 0
    config = specs.load_config(root)
    cfg = specs.sdd_config(config)
    specs.require_layout(cfg, "sdd")
    if args.command == "new":
        change = specs.new_change(root, cfg, args.slug, args.epic, args.title)
        relative = change.relative_to(root).as_posix()
        _emit({"change": change.name, "path": relative}, args.format, relative)
        return 0
    if args.command == "next-id":
        req_id, warnings = specs.next_id(root, cfg, args.cap)
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        _emit({"id": req_id, "warnings": warnings}, args.format, req_id)
        return 0
    if args.command == "lint":
        if args.change:
            errors = specs.lint_change(root, cfg, specs.find_change(root, cfg, args.change), against=args.against)
        else:
            errors = specs.lint_living(root, cfg)
        return _findings(errors, args.format, "ok")
    if args.command == "hash":
        block, digest = specs.requirement_hash(root, cfg, args.req_id)
        _emit({"id": block.id, "hash": digest}, args.format, f"<!-- base: {digest} -->")
        return 0
    change = specs.find_change(root, cfg, args.change)
    result = specs.renumber(root, cfg, change, args.old, args.new, against=args.against)
    _emit(result, args.format, "\n".join([f"{args.old} -> {args.new}", *result["files"], *result["beads"]]))
    return 0

def main(arguments: Sequence[str]) -> int:
    try:
        args = _parser().parse_args(list(arguments))
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    try:
        return _run(args)
    except (specs.SpecsError, ValueError) as error:
        print(f"specs error: {error}", file=sys.stderr)
        return 2
```

Route it in `plugins/gin-workflow/src/scripts/workflow_core/cli.py` `main()` — replace:

```python
    if not argv or argv[0] not in ("setup", "state", "unblock", "record", "quick-check", "rules"):
        print("usage: gin-workflow {setup,state,unblock,record,quick-check,rules} <command>", file=sys.stderr)
        return 2
    if argv[0] == "rules":
        from .rules import main as rules_main
        return rules_main(argv[1:])
```

with:

```python
    if not argv or argv[0] not in ("setup", "state", "unblock", "record", "quick-check", "rules", "specs"):
        print("usage: gin-workflow {setup,state,unblock,record,quick-check,rules,specs} <command>", file=sys.stderr)
        return 2
    if argv[0] == "rules":
        from .rules import main as rules_main
        return rules_main(argv[1:])
    if argv[0] == "specs":
        from .specs_cli import main as specs_main
        return specs_main(argv[1:])
```

Add to `REQUIRED_ARTIFACTS` in `tests/workflow_providers/test_harness_packaging.py`:

```python
    "scripts/workflow_core/specs.py",
    "scripts/workflow_core/specs_cli.py",
```

Add after the two template asserts in `tests/install_smoke_test.sh`:

```bash
HOME="$MOCK_HOME" "$MOCK_HOME/.local/bin/gin-workflow" specs --help >/dev/null
```

- [ ] **Step 4:** Run the Step 2 command → PASS (18 tests). Full suite → `OK`; smoke → exit 0.

- [ ] **Step 5:** Commit `feat(specs): requirement blocks, lint, REQ-ID allocation, and gin-workflow specs`.

### Track 3: Archive, trace, and spec-review status

**Metadata:**
- Dependencies: Track 2
- Provider role: backend
- Reasoning: high
- Model guidance: high_reasoning
- Estimated complexity: medium

**Files:**
- Create: `plugins/gin-workflow/src/scripts/workflow_core/specs_archive.py`, `plugins/gin-workflow/src/scripts/workflow_core/specs_trace.py`
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py` (three subcommands), `tests/workflow_providers/test_harness_packaging.py` (two artifacts)
- Test: `tests/workflow_core/test_specs_archive_trace.py` (new)

**Interfaces:**
- Consumes: Track 2 `specs.*`.
- Produces: `ArchiveConflict(errors)`; `move(root, source, target)` (`git mv`, fallback plain move); `archive(root, cfg, change, *, today=None) -> {change, archived_to, specs, added, modified, removed}`; `trace(root, cfg, change) -> {change, requirements: [{id, status: covered|missing, sources}], missing}`; `status(root, change) -> {change, branch, status: none|open|merged|closed|gh_unavailable, url?, merge_commit?, message?}`. CLI: `specs archive|trace|status --change ID`; `archive` exit 1 on conflict, `trace` exit 1 when a REQ is missing.

- [ ] **Step 1: Failing tests.** Create `tests/workflow_core/test_specs_archive_trace.py`:

```python
"""SDD archive (delta -> living spec), traceability, spec-review status, and an end-to-end cycle."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specs_fixtures import (ADDED_BLOCK, AUTH_SPEC, LAUNCHER, commit_all, delta, git,  # noqa: E402
                            make_change, make_repo, write)
from workflow_core import specs, specs_trace  # noqa: E402
from workflow_core.specs_archive import ArchiveConflict, archive  # noqa: E402

TODAY = __import__("datetime").date(2026, 10, 3)
MODIFIED = """### REQ-AUTH-002: Reject wrong password
<!-- base: {base} -->
The system SHALL reject a wrong password and count the failure.

#### Scenario: wrong password
- GIVEN a registered user
- WHEN they submit a wrong password
- THEN they see "Invalid credentials" and the failure count grows
"""


class TestArchive(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(Path(self.tmp.name) / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        write(self.root, "docs/specs/README.md", "# Specs\n\n## Capabilities\n- [auth](auth/spec.md)\n")
        self.cfg = specs.sdd_config(specs.load_config(self.root))
        self.base2 = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-002")[1]
        self.base1 = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-001")[1]

    def tearDown(self):
        self.tmp.cleanup()

    def test_applies_added_modified_removed_and_new_capability(self):
        billing = ADDED_BLOCK.replace("REQ-AUTH-003", "REQ-BILLING-001")
        change = make_change(self.root, spec_delta=delta(
            added=ADDED_BLOCK + "\n" + billing, modified=MODIFIED.format(base=self.base2),
            removed=f"### REQ-AUTH-001: Sign in with password\n<!-- base: {self.base1} -->\nReason: replaced by SSO\n"))
        commit_all(self.root)
        result = archive(self.root, self.cfg, change, today=TODAY)
        auth = (self.root / "docs/specs/auth/spec.md").read_text(encoding="utf-8")
        self.assertNotIn("REQ-AUTH-001", auth)
        self.assertIn("and count the failure.", auth)
        self.assertNotIn("<!-- base:", auth)
        self.assertTrue(auth.rstrip().endswith("- THEN the account is locked"))
        self.assertEqual(["REQ-AUTH-002", "REQ-AUTH-003"], [b.id for b in specs.parse_blocks(auth)[0]])
        billing_spec = (self.root / "docs/specs/billing/spec.md").read_text(encoding="utf-8")
        self.assertTrue(billing_spec.startswith("# Billing\n"))
        self.assertIn("### REQ-BILLING-001", billing_spec)
        self.assertIn("- [billing](billing/spec.md)", (self.root / "docs/specs/README.md").read_text(encoding="utf-8"))
        self.assertEqual("docs/changes/archive/2026-10-03-ep-1-lockout", result["archived_to"])
        self.assertFalse(change.exists())
        self.assertTrue((self.root / result["archived_to"] / "spec-delta.md").is_file())
        self.assertTrue(any(line.startswith("R") for line in git(self.root, "status", "--porcelain").splitlines()))
        self.assertEqual([], specs.lint_living(self.root, self.cfg))

    def test_base_hash_conflict_writes_nothing(self):
        change = make_change(self.root, spec_delta=delta(modified=MODIFIED.format(base=self.base2)))
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC.replace("reject a wrong password.", "reject it."))
        before = (self.root / "docs/specs/auth/spec.md").read_text(encoding="utf-8")
        with self.assertRaises(ArchiveConflict) as caught:
            archive(self.root, self.cfg, change, today=TODAY)
        self.assertIn("REQ-AUTH-002: living block changed since the delta was written", caught.exception.errors[0])
        self.assertEqual(before, (self.root / "docs/specs/auth/spec.md").read_text(encoding="utf-8"))
        self.assertTrue(change.is_dir())

    def test_lint_errors_block_archive(self):
        change = make_change(self.root, spec_delta=delta(added="### REQ-AUTH-003: X\nNo statement.\n"))
        with self.assertRaises(ArchiveConflict):
            archive(self.root, self.cfg, change, today=TODAY)
        self.assertTrue(change.is_dir())


class TestTraceAndStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(Path(self.tmp.name) / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        self.cfg = specs.sdd_config(specs.load_config(self.root))
        base = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-002")[1]
        self.change = make_change(self.root, spec_delta=delta(added=ADDED_BLOCK, modified=MODIFIED.format(base=base)))

    def tearDown(self):
        self.tmp.cleanup()

    def test_trace_finds_code_tags_and_tests_md_rows(self):
        write(self.root, "tests/test_lockout.py", "def test_lock():  # REQ-AUTH-003\n    pass\n")
        write(self.root, "src/notes.py", "# REQ-AUTH-002 is not a test file\n")
        commit_all(self.root)
        result = specs_trace.trace(self.root, self.cfg, self.change)
        self.assertEqual(["REQ-AUTH-002"], result["missing"])
        self.assertEqual(["tests/test_lockout.py"], result["requirements"][0]["sources"])
        write(self.root, "docs/changes/ep-1-lockout/tests.md",
              "| TC | REQ | type | evidence |\n|---|---|---|---|\n| TC-1 | REQ-AUTH-002 | manual | screenshot.png |\n"
              "| TC-2 | REQ-AUTH-002 | manual | - |\n")
        result = specs_trace.trace(self.root, self.cfg, self.change)
        self.assertEqual([], result["missing"])
        self.assertEqual(["docs/changes/ep-1-lockout/tests.md#TC-1"], result["requirements"][1]["sources"])

    def _gh(self, stdout: str, returncode: int = 0):
        return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="boom")

    def test_status_states(self):
        with mock.patch("workflow_core.specs_trace.shutil.which", return_value=None):
            self.assertEqual("gh_unavailable", specs_trace.status(self.root, self.change)["status"])
        cases = [("[]", {"status": "none"}),
                 ('[{"url": "u", "state": "OPEN", "mergeCommit": null}]', {"status": "open", "url": "u"}),
                 ('[{"url": "u", "state": "MERGED", "mergeCommit": {"oid": "abc"}}]',
                  {"status": "merged", "url": "u", "merge_commit": "abc"}),
                 ('[{"url": "u", "state": "CLOSED", "mergeCommit": null}]', {"status": "closed", "url": "u"})]
        for stdout, expected in cases:
            with self.subTest(stdout=stdout), \
                    mock.patch("workflow_core.specs_trace.shutil.which", return_value="/usr/bin/gh"), \
                    mock.patch("workflow_core.specs_trace.subprocess.run", return_value=self._gh(stdout)) as run:
                result = specs_trace.status(self.root, self.change)
                self.assertEqual({"change": "ep-1-lockout", "branch": "spec/ep-1-lockout", **expected}, result)
                self.assertIn("spec/ep-1-lockout", run.call_args.args[0])
        with mock.patch("workflow_core.specs_trace.shutil.which", return_value="/usr/bin/gh"), \
                mock.patch("workflow_core.specs_trace.subprocess.run", return_value=self._gh("", 1)):
            with self.assertRaises(specs.SpecsError):
                specs_trace.status(self.root, self.change)


class TestEndToEnd(unittest.TestCase):
    def run_specs(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(LAUNCHER), "specs", *args, "--repository", str(root)],
                              text=True, capture_output=True, check=False)

    def test_new_delta_lint_trace_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_repo(Path(directory) / "repo")
            write(root, "docs/specs/auth/spec.md", AUTH_SPEC)
            commit_all(root)
            self.assertEqual(0, self.run_specs(root, "new", "lockout", "--epic", "ep-1").returncode)
            req = self.run_specs(root, "next-id", "auth").stdout.strip()
            write(root, "docs/changes/ep-1-lockout/spec-delta.md", delta(added=ADDED_BLOCK.replace("REQ-AUTH-003", req)))
            self.assertEqual(0, self.run_specs(root, "lint", "--change", "ep-1", "--against", "main").returncode)
            self.assertEqual(1, self.run_specs(root, "trace", "--change", "ep-1").returncode)
            write(root, "tests/test_lockout.py", f"def test_lock():  # {req}\n    pass\n")
            commit_all(root)
            traced = json.loads(self.run_specs(root, "trace", "--change", "ep-1", "--format", "json").stdout)
            self.assertEqual([], traced["missing"])
            archived = self.run_specs(root, "archive", "--change", "ep-1", "--format", "json")
            self.assertEqual(0, archived.returncode, archived.stderr)
            self.assertIn(req, (root / "docs/specs/auth/spec.md").read_text(encoding="utf-8"))
            self.assertEqual(0, self.run_specs(root, "lint").returncode)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2:** Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/workflow_core/test_specs_archive_trace.py -v` → FAIL (`ModuleNotFoundError: workflow_core.specs_archive`).

- [ ] **Step 3: Implement** `plugins/gin-workflow/src/scripts/workflow_core/specs_archive.py`:

```python
"""Merge a change's spec delta into the living spec, then archive the change folder."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import shutil
import subprocess
from typing import Any, Mapping

from .atomic import atomic_write_many
from .specs import (Block, SpecsError, block_hash, delta_blocks, lint_change, living_blocks, parse_blocks,
                    render, specs_dir, template_text, _BASE)


class ArchiveConflict(ValueError):
    """The delta cannot be applied; nothing was written (exit 1)."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _clean(block: Block) -> list[str]:
    return [line for line in block.text.splitlines() if not _BASE.match(line.strip())]


def _apply(lines: list[str], edits: Mapping[str, Block | None]) -> list[str]:
    """Replace (Block) or drop (None) living blocks by id, bottom-up so indexes stay valid."""
    blocks = sorted(parse_blocks("\n".join(lines))[0], key=lambda block: block.start, reverse=True)
    for block in blocks:
        if block.id in edits:
            replacement = edits[block.id]
            lines[block.start:block.end] = [] if replacement is None else [*_clean(replacement), ""]
    return lines


def _append(lines: list[str], added: list[Block]) -> list[str]:
    while lines and not lines[-1].strip():
        lines.pop()
    for block in added:
        lines += ["", *_clean(block)]
    return lines


def move(root: Path, source: Path, target: Path) -> None:
    """`git mv` keeps history; untracked sources fall back to a plain move."""
    target.parent.mkdir(parents=True, exist_ok=True)
    moved = subprocess.run(["git", "mv", str(source), str(target)], cwd=root, capture_output=True, check=False)
    if moved.returncode != 0:
        shutil.move(str(source), str(target))


def archive(root: Path, cfg: Mapping[str, Any], change: Path, *, today: date | None = None) -> dict[str, Any]:
    errors = lint_change(root, cfg, change)
    blocks, _ = delta_blocks(root, change)
    living = living_blocks(root, cfg)
    for block in blocks:
        if block.section in ("MODIFIED", "REMOVED") and block.id in living:
            current = block_hash(living[block.id][1].text)
            if block.base != current:
                errors.append(f"{block.id}: living block changed since the delta was written "
                              f"(base {str(block.base)[:12]}, now {current[:12]}); update the delta")
    if errors:
        raise ArchiveConflict(errors)
    target = Path(cfg["changes"]) / "archive" / f"{(today or date.today()).isoformat()}-{change.name}"
    if (Path(root) / target).exists():
        raise SpecsError(f"archive folder already exists: {target}")

    base = specs_dir(root, cfg)
    texts: dict[str, list[str]] = {}
    new_caps: list[str] = []
    for block in blocks:
        path = base / block.cap / "spec.md"
        if block.cap not in texts:
            if path.is_file():
                texts[block.cap] = path.read_text(encoding="utf-8").splitlines()
            else:
                title = block.cap.replace("-", " ").capitalize()
                texts[block.cap] = render(template_text(root, "spec.md"), {"capability": title}).splitlines()
                new_caps.append(block.cap)
    for cap, lines in texts.items():
        mine = [block for block in blocks if block.cap == cap]
        edits = {b.id: (b if b.section == "MODIFIED" else None) for b in mine if b.section != "ADDED"}
        texts[cap] = _append(_apply(lines, edits), [b for b in mine if b.section == "ADDED"])
    writes = {base / cap / "spec.md": ("\n".join(lines).rstrip() + "\n").encode("utf-8") for cap, lines in texts.items()}
    if new_caps:
        readme = base / "README.md"
        text = readme.read_text(encoding="utf-8") if readme.is_file() else template_text(root, "specs-README.md")
        lines = text.rstrip().splitlines() + [f"- [{cap}]({cap}/spec.md)" for cap in new_caps]
        writes[readme] = ("\n".join(lines) + "\n").encode("utf-8")
    atomic_write_many(writes, mode=0o644)
    move(root, change, Path(root) / target)
    return {"change": change.name, "archived_to": target.as_posix(),
            "specs": sorted(str(path.relative_to(root)) for path in writes),
            "added": [b.id for b in blocks if b.section == "ADDED"],
            "modified": [b.id for b in blocks if b.section == "MODIFIED"],
            "removed": [b.id for b in blocks if b.section == "REMOVED"]}
```

Create `plugins/gin-workflow/src/scripts/workflow_core/specs_trace.py`:

```python
"""Requirement traceability (REQ -> tests) and spec-review PR status."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Mapping

from .specs import REQ_ID, SpecsError, delta_blocks, test_files


def _tracked(root: Path) -> list[str]:
    listed = subprocess.run(["git", "ls-files"], cwd=root, text=True, capture_output=True, check=False)
    if listed.returncode == 0:
        return listed.stdout.splitlines()
    return [path.relative_to(root).as_posix() for path in Path(root).rglob("*") if path.is_file()]


def _tests_md_rows(path: Path) -> list[tuple[str, set[str], str]]:
    rows = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and line.lstrip().startswith("|"):
            ids = {match.group(0) for match in REQ_ID.finditer(cells[1])}
            if ids:
                rows.append((cells[0], ids, cells[3]))
    return rows


def trace(root: Path, cfg: Mapping[str, Any], change: Path) -> dict[str, Any]:
    blocks, errors = delta_blocks(root, change)
    if errors:
        raise SpecsError("; ".join(errors))
    wanted = [block.id for block in blocks if block.section in ("ADDED", "MODIFIED")]
    sources: dict[str, list[str]] = {req: [] for req in wanted}
    for relative in test_files(root, cfg, _tracked(root)):
        try:
            text = (Path(root) / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for req in {match.group(0) for match in REQ_ID.finditer(text)} & set(wanted):
            sources[req].append(relative)
    tests_md = change / "tests.md"
    for case, ids, evidence in _tests_md_rows(tests_md):
        if evidence and evidence != "-":
            for req in ids & set(wanted):
                sources[req].append(f"{tests_md.relative_to(root).as_posix()}#{case}")
    requirements = [{"id": req, "status": "covered" if sources[req] else "missing", "sources": sorted(sources[req])}
                    for req in wanted]
    return {"change": change.name, "requirements": requirements,
            "missing": [row["id"] for row in requirements if row["status"] == "missing"]}


def status(root: Path, change: Path) -> dict[str, Any]:
    branch = f"spec/{change.name}"
    record = "gin-workflow record requirement-confirmed --workflow-id <epic> --evidence <pr-url> --actor <id>"
    executable = shutil.which("gh")
    if executable is None:
        return {"change": change.name, "branch": branch, "status": "gh_unavailable",
                "message": f"gh unavailable; check the PR for {branch} by hand, then: {record}"}
    listed = subprocess.run([executable, "pr", "list", "--head", branch, "--state", "all",
                             "--json", "url,state,mergeCommit"], cwd=root, text=True, capture_output=True, check=False)
    if listed.returncode != 0:
        raise SpecsError(f"gh pr list failed: {listed.stderr.strip()}")
    prs = json.loads(listed.stdout or "[]")
    if not prs:
        return {"change": change.name, "branch": branch, "status": "none"}
    pr = prs[0]
    state = str(pr.get("state", "")).lower()
    payload = {"change": change.name, "branch": branch, "status": state, "url": pr.get("url", "")}
    if state == "merged":
        payload["merge_commit"] = (pr.get("mergeCommit") or {}).get("oid", "")
    return payload
```

Extend `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py`:

```diff
--- plangen/specs_cli_t2.py	2026-10-03 05:16:24.524320496 +0000
+++ plangen/specs_cli_t3.py	2026-10-03 05:16:13.693770968 +0000
@@ -32,6 +32,9 @@
     item.add_argument("new")
     item.add_argument("--change", required=True)
     item.add_argument("--against")
+    sub.add_parser("archive", parents=[common]).add_argument("--change", required=True)
+    sub.add_parser("trace", parents=[common]).add_argument("--change", required=True)
+    sub.add_parser("status", parents=[common]).add_argument("--change", required=True)
     return parser
 
 
@@ -76,10 +79,31 @@
         _emit({"id": block.id, "hash": digest}, args.format, f"<!-- base: {digest} -->")
         return 0
     change = specs.find_change(root, cfg, args.change)
-    result = specs.renumber(root, cfg, change, args.old, args.new, against=args.against)
-    _emit(result, args.format, "\n".join([f"{args.old} -> {args.new}", *result["files"], *result["beads"]]))
+    if args.command == "renumber":
+        result = specs.renumber(root, cfg, change, args.old, args.new, against=args.against)
+        _emit(result, args.format, "\n".join([f"{args.old} -> {args.new}", *result["files"], *result["beads"]]))
+        return 0
+    if args.command == "archive":
+        from .specs_archive import ArchiveConflict, archive
+
+        try:
+            result = archive(root, cfg, change)
+        except ArchiveConflict as conflict:
+            return _findings(conflict.errors, args.format, "ok")
+        _emit(result, args.format, f"archived to {result['archived_to']}; updated {', '.join(result['specs'])}")
+        return 0
+    from .specs_trace import status, trace
+
+    if args.command == "trace":
+        result = trace(root, cfg, change)
+        lines = [f"{row['id']}: {row['status']} {' '.join(row['sources'])}".rstrip() for row in result["requirements"]]
+        _emit(result, args.format, "\n".join(lines))
+        return 1 if result["missing"] else 0
+    result = status(root, change)
+    _emit(result, args.format, " ".join(str(result.get(key, "")) for key in ("status", "url", "merge_commit")).strip())
     return 0
 
+
 def main(arguments: Sequence[str]) -> int:
     try:
         args = _parser().parse_args(list(arguments))
```

Add to `REQUIRED_ARTIFACTS`: `"scripts/workflow_core/specs_archive.py",` and `"scripts/workflow_core/specs_trace.py",`.

- [ ] **Step 4:** Run the Step 2 command → PASS (6 tests). Full suite → `OK`.

- [ ] **Step 5:** Commit `feat(specs): archive deltas into living specs, trace REQs to tests, spec PR status`.

### Track 4: Migration, setup preset and doctor, and the migrate-specs skill

**Metadata:**
- Dependencies: Track 3
- Provider role: backend
- Reasoning: medium
- Model guidance: standard_impl
- Estimated complexity: medium

**Files:**
- Create: `plugins/gin-workflow/src/scripts/workflow_core/specs_migrate.py`, `plugins/gin-workflow/src/skills/migrate-specs/SKILL.md`
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py` (`migrate`), `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py:489-500,707-730`, `tests/workflow_providers/test_harness_packaging.py` (two artifacts)
- Test: `tests/workflow_core/test_specs_migrate.py` (new)

**Interfaces:**
- Consumes: `specs_archive.move`, `specs.template_text`, `setup_service.configure`, `lifecycle_cli._process_gate_state`/`_delivery_gate_state`, `events.WorkflowEventStore`.
- Produces: `plan_moves(root, config, cfg) -> {moves: [{from, to}], skipped}`; `in_flight_workflows(root) -> list[str]`; `open_worktrees(root, config) -> list[str]`; `refusals(root, config, *, force) -> list[str]`; `migrate(root, config, cfg, *, dry_run, force) -> {moves, skipped, refusals, readme, status: planned|refused|migrated}`; `sdd_report(root, config, cfg, *, proposed=False) -> {layout, conflict?, suggestion?}`; `setup preset` payload key `sdd`; `setup doctor` `checks_details.sdd` and `sdd:` actions. CLI: `specs migrate [--dry-run] [--force]` (needs `layout: legacy`; exit 1 when refused).

- [ ] **Step 1: Failing tests.** Create `tests/workflow_core/test_specs_migrate.py`:

```python
"""Legacy .planning -> SDD docs/ migration, and the setup preset/doctor SDD report."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specs_fixtures import LAUNCHER, commit_all, git, make_repo, write  # noqa: E402
from workflow_core import specs  # noqa: E402
from workflow_core.specs_migrate import migrate, plan_moves, sdd_report  # noqa: E402


def run_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(LAUNCHER), *args, "--repository", str(root)],
                          text=True, capture_output=True, check=False)


class TestMigrate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(Path(self.tmp.name) / "repo", layout="legacy")
        self.assertEqual(0, run_cli(self.root, "setup", "refresh").returncode)
        write(self.root, ".planning/specs/2026-10-01-rules-design.md", "# Rules design\n")
        write(self.root, ".planning/plans/2026-10-02-rules.md", "# Rules plan\n")
        write(self.root, ".planning/specs/2026-09-01-lonely-design.md", "# Lonely\n")
        write(self.root, ".planning/plans/notes.md", "# Notes\n")
        write(self.root, ".planning/codebase/OVERVIEW.md", "# Overview\n")
        write(self.root, ".planning/reviews/x/review.json", "{}\n")
        commit_all(self.root)
        self.config = specs.load_config(self.root)
        self.cfg = specs.sdd_config(self.config)

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_pairs_by_slug_and_lists_skipped(self):
        plan = plan_moves(self.root, self.config, self.cfg)
        self.assertEqual([
            {"from": ".planning/specs/2026-09-01-lonely-design.md", "to": "docs/changes/archive/2026-09-01-lonely/design.md"},
            {"from": ".planning/specs/2026-10-01-rules-design.md", "to": "docs/changes/archive/2026-10-01-rules/design.md"},
            {"from": ".planning/plans/2026-10-02-rules.md", "to": "docs/changes/archive/2026-10-01-rules/plan.md"},
            {"from": ".planning/codebase", "to": "docs/codebase"},
        ], plan["moves"])
        self.assertEqual([".planning/plans/notes.md"], plan["skipped"])

    def test_dry_run_changes_nothing(self):
        result = run_cli(self.root, "specs", "migrate", "--dry-run", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("planned", json.loads(result.stdout)["status"])
        self.assertEqual("", git(self.root, "status", "--porcelain"))

    def test_migrate_moves_with_git_and_switches_layout(self):
        result = run_cli(self.root, "specs", "migrate", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.root / "docs/changes/archive/2026-10-01-rules/plan.md").is_file())
        self.assertTrue((self.root / "docs/codebase/OVERVIEW.md").is_file())
        self.assertTrue((self.root / ".planning/reviews/x/review.json").is_file())
        self.assertTrue((self.root / ".planning/plans/notes.md").is_file())
        self.assertTrue((self.root / "docs/specs/README.md").is_file())
        status = git(self.root, "status", "--porcelain").splitlines()
        self.assertIn("R  .planning/plans/2026-10-02-rules.md -> docs/changes/archive/2026-10-01-rules/plan.md", status)
        self.assertEqual("sdd", specs.sdd_config(specs.load_config(self.root))["layout"])
        again = run_cli(self.root, "specs", "migrate")
        self.assertEqual(2, again.returncode)

    def test_refusals(self):
        write(self.root, "dirty.txt", "x\n")
        result = migrate(self.root, self.config, self.cfg, dry_run=False, force=True)
        self.assertEqual("refused", result["status"])
        self.assertIn("uncommitted changes; commit or set them aside first", result["refusals"])
        (self.root / "dirty.txt").unlink()
        with mock.patch("workflow_core.specs_migrate.in_flight_workflows", return_value=["wf-1"]):
            blocked = migrate(self.root, self.config, self.cfg, dry_run=False, force=False)
            self.assertEqual(["workflow wf-1 is approved but not shipped (use --force to migrate anyway)"],
                             blocked["refusals"])
            self.assertTrue((self.root / ".planning/plans/2026-10-02-rules.md").is_file())
            forced = migrate(self.root, self.config, self.cfg, dry_run=False, force=True)
        self.assertEqual("migrated", forced["status"])

    def test_in_flight_reads_recorded_gates(self):
        from workflow_core.specs_migrate import in_flight_workflows

        self.assertEqual([], in_flight_workflows(self.root))
        recorded = run_cli(self.root, "record", "plan-approved", "--workflow-id", "wf-1", "--evidence", "p.md",
                           "--actor", "u")
        self.assertEqual(0, recorded.returncode, recorded.stderr)
        with mock.patch("workflow_core.lifecycle_cli._beads_json", return_value=None):
            self.assertEqual(["wf-1"], in_flight_workflows(self.root))

    def test_open_worktree_refuses(self):
        git(self.root, "worktree", "add", "-q", "-b", "t1", str(self.root / ".planning/worktrees/t1"))
        result = migrate(self.root, self.config, self.cfg, dry_run=True, force=False)
        self.assertTrue(any(r.startswith("worktree open at") for r in result["refusals"]), result["refusals"])


class TestSddReport(unittest.TestCase):
    def test_legacy_suggests_migration_and_sdd_flags_foreign_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            defaults = dict(specs.SDD_DEFAULTS)
            self.assertEqual({"layout": "legacy"}, sdd_report(root, {}, defaults))
            write(root, ".planning/specs/2026-10-01-x-design.md", "# x\n")
            self.assertIn("migrate-specs", sdd_report(root, {}, defaults)["suggestion"])
            write(root, "docs/specs/login.spec.ts", "test()\n")
            write(root, "docs/specs/auth/spec.md", "# Auth\n")
            report = sdd_report(root, {}, defaults, proposed=True)
            self.assertEqual(["login.spec.ts"], report["conflict"]["files"])

    def test_setup_preset_proposes_sdd_only_for_greenfield(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            green = json.loads(run_cli(root, "setup", "preset", "--project-stage", "greenfield", "--format", "json").stdout)
            self.assertIn('artifacts.layout="sdd"', green["assignments"])
            self.assertEqual({"layout": "sdd"}, green["sdd"])
            brown = json.loads(run_cli(root, "setup", "preset", "--project-stage", "brownfield", "--format", "json").stdout)
            self.assertFalse(any(a.startswith("artifacts.layout") for a in brown["assignments"]))
            self.assertEqual({"layout": "legacy"}, brown["sdd"])

    def test_doctor_reports_sdd_without_changing_health(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(0, run_cli(root, "setup", "init", "--approve", "--non-interactive").returncode)
            write(root, ".planning/plans/2026-10-01-x.md", "# x\n")
            payload = json.loads(run_cli(root, "setup", "doctor", "--format", "json").stdout)
            self.assertEqual("legacy", payload["checks_details"]["sdd"]["layout"])
            self.assertTrue(any(a.startswith("sdd: run /gin-workflow:migrate-specs") for a in payload["actions"]))
            self.assertNotIn("sdd", payload["checks"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2:** Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/workflow_core/test_specs_migrate.py -v` → FAIL (`ModuleNotFoundError: workflow_core.specs_migrate`).

- [ ] **Step 3: Implement** `plugins/gin-workflow/src/scripts/workflow_core/specs_migrate.py`:

```python
"""Move a legacy `.planning` layout into the SDD `docs/` layout; setup and doctor SDD checks."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping

from .atomic import atomic_write_many
from .specs import specs_dir, template_text
from .specs_archive import move

_DESIGN = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)-design\.md$")
_PLAN = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$")
LEGACY_SPECS = ".planning/specs"
LEGACY_CODEBASE = ".planning/codebase"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)


def plan_moves(root: Path, config: Mapping[str, Any], cfg: Mapping[str, Any]) -> dict[str, Any]:
    """Pair `<date>-<slug>-design.md` with `<date>-<slug>.md` by slug; everything else moves alone or is skipped."""
    plans_dir = str((config.get("artifacts") or {}).get("plans", ".planning/plans"))
    archive = Path(cfg["changes"]) / "archive"
    designs: dict[str, list[tuple[str, Path]]] = defaultdict(list)
    plans: dict[str, list[tuple[str, Path]]] = defaultdict(list)
    skipped: list[str] = []
    for kind, directory in (("design", LEGACY_SPECS), ("plan", plans_dir)):
        for path in sorted((Path(root) / directory).glob("*.md")):
            relative = path.relative_to(root)
            design = _DESIGN.match(path.name)
            plan = _PLAN.match(path.name)
            if kind == "design" and design:
                designs[design.group(2)].append((design.group(1), relative))
            elif kind == "plan" and plan and not design:
                plans[plan.group(2)].append((plan.group(1), relative))
            else:
                skipped.append(relative.as_posix())
    moves: list[dict[str, str]] = []
    for slug in sorted(set(designs) | set(plans)):
        if len(designs[slug]) == 1 and len(plans[slug]) == 1:
            day = designs[slug][0][0]
            pairs = [(designs[slug][0][1], "design.md", day), (plans[slug][0][1], "plan.md", day)]
        else:
            pairs = [(path, "design.md", day) for day, path in designs[slug]]
            pairs += [(path, "plan.md", day) for day, path in plans[slug]]
        for source, name, day in pairs:
            moves.append({"from": source.as_posix(), "to": (archive / f"{day}-{slug}" / name).as_posix()})
    if (Path(root) / LEGACY_CODEBASE).is_dir():
        moves.append({"from": LEGACY_CODEBASE, "to": str(cfg["codebase"])})
    return {"moves": moves, "skipped": skipped}


def in_flight_workflows(root: Path) -> list[str]:
    from .events import WorkflowEventStore
    from .lifecycle_cli import _delivery_gate_state, _process_gate_state

    path = Path(root) / ".agent-workflow/runtime/events.jsonl"
    if not path.is_file():
        return []
    store = WorkflowEventStore(path)
    ids = sorted({event.workflow_id for event in store.read_all()})
    return [workflow for workflow in ids
            if _process_gate_state(store, workflow)["plan_approved"]
            and not _delivery_gate_state(Path(root), store, workflow)["shipped"]]


def open_worktrees(root: Path, config: Mapping[str, Any]) -> list[str]:
    base = (Path(root) / str((config.get("artifacts") or {}).get("worktrees", ".planning/worktrees"))).resolve()
    listed = _git(root, "worktree", "list", "--porcelain").stdout.splitlines()
    paths = [Path(line[len("worktree "):]).resolve() for line in listed if line.startswith("worktree ")]
    return [path.as_posix() for path in paths if path.is_relative_to(base)]


def refusals(root: Path, config: Mapping[str, Any], *, force: bool) -> list[str]:
    found: list[str] = []
    if _git(root, "status", "--porcelain").stdout.strip():
        found.append("uncommitted changes; commit or set them aside first")
    if not force:
        found += [f"workflow {item} is approved but not shipped (use --force to migrate anyway)"
                  for item in in_flight_workflows(root)]
        found += [f"worktree open at {item} (use --force to migrate anyway)" for item in open_worktrees(root, config)]
    return found


def migrate(root: Path, config: Mapping[str, Any], cfg: Mapping[str, Any], *, dry_run: bool,
            force: bool) -> dict[str, Any]:
    plan = plan_moves(root, config, cfg)
    blocked = refusals(root, config, force=force)
    readme = specs_dir(root, cfg) / "README.md"
    result = {**plan, "refusals": blocked, "readme": readme.relative_to(root).as_posix(),
              "status": "planned" if dry_run else ("refused" if blocked else "migrated")}
    if dry_run or blocked:
        return result
    for item in plan["moves"]:
        move(root, Path(root) / item["from"], Path(root) / item["to"])
    if not readme.is_file():
        atomic_write_many({readme: template_text(root, "specs-README.md").encode("utf-8")}, mode=0o644)
    from .setup_service import configure

    configure(root, assignments=['artifacts.layout="sdd"'], approve=True)
    return result


def _foreign(directory: Path) -> list[str]:
    """Files that do not belong to an SDD specs folder (README.md and <cap>/spec.md)."""
    if not directory.is_dir():
        return []
    return sorted(path.relative_to(directory).as_posix() for path in directory.rglob("*")
                  if path.is_file() and path.name != "README.md"
                  and not (path.name == "spec.md" and path.parent.parent == directory))


def sdd_report(root: Path, config: Mapping[str, Any], cfg: Mapping[str, Any], *, proposed: bool = False) -> dict[str, Any]:
    """Read-only SDD checks for `setup preset` (proposed layout) and `setup doctor`."""
    report: dict[str, Any] = {"layout": "sdd" if proposed else cfg["layout"]}
    foreign = _foreign(specs_dir(root, cfg))
    if report["layout"] == "sdd" and foreign:
        report["conflict"] = {"path": str(cfg["specs"]), "files": foreign[:10],
                              "suggestion": "set artifacts.specs to another folder, e.g. docs/requirements"}
    plans_dir = str((config.get("artifacts") or {}).get("plans", ".planning/plans"))
    if report["layout"] == "legacy" and any(any((Path(root) / d).glob("*.md")) for d in (LEGACY_SPECS, plans_dir)):
        report["suggestion"] = "run /gin-workflow:migrate-specs to move .planning specs and plans into the SDD layout"
    return report
```

Extend `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py`:

```diff
--- plangen/specs_cli_t3.py	2026-10-03 05:16:13.693770968 +0000
+++ plangen/specs_cli_final.py	2026-10-03 05:16:24.532198953 +0000
@@ -35,6 +35,9 @@
     sub.add_parser("archive", parents=[common]).add_argument("--change", required=True)
     sub.add_parser("trace", parents=[common]).add_argument("--change", required=True)
     sub.add_parser("status", parents=[common]).add_argument("--change", required=True)
+    item = sub.add_parser("migrate", parents=[common])
+    item.add_argument("--dry-run", action="store_true")
+    item.add_argument("--force", action="store_true")
     return parser
 
 
@@ -56,6 +59,15 @@
         return 0
     config = specs.load_config(root)
     cfg = specs.sdd_config(config)
+    if args.command == "migrate":
+        from .specs_migrate import migrate
+
+        specs.require_layout(cfg, "legacy")
+        result = migrate(root, config, cfg, dry_run=args.dry_run, force=args.force)
+        lines = [f"{m['from']} -> {m['to']}" for m in result["moves"]]
+        lines += [f"skipped: {item}" for item in result["skipped"]] + [f"refused: {r}" for r in result["refusals"]]
+        _emit(result, args.format, "\n".join([f"status: {result['status']}", *lines]))
+        return 1 if result["status"] == "refused" else 0
     specs.require_layout(cfg, "sdd")
     if args.command == "new":
         change = specs.new_change(root, cfg, args.slug, args.epic, args.title)
```

Wire setup and doctor in `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py`:

```diff
diff --git a/plugins/gin-workflow/src/scripts/workflow_core/setup_service.py b/plugins/gin-workflow/src/scripts/workflow_core/setup_service.py
index 112add3..0487e67 100644
--- a/plugins/gin-workflow/src/scripts/workflow_core/setup_service.py
+++ b/plugins/gin-workflow/src/scripts/workflow_core/setup_service.py
@@ -490,5 +490,6 @@ def doctor(repository: Path, *, probe: bool = False, **_: Any) -> dict[str, Any]
         from .rules_checks import rules_doctor
 
-        rules_detail = rules_doctor(root, resolve_effective_config(root, write=False).config.to_dict())
+        effective = resolve_effective_config(root, write=False).config.to_dict()
+        rules_detail = rules_doctor(root, effective)
         checks_details["rules"] = rules_detail
         for item in rules_detail.get("tool_checks", []):
@@ -499,4 +500,15 @@ def doctor(repository: Path, *, probe: bool = False, **_: Any) -> dict[str, Any]
                            f"'{item['pack_says']}'; the project wins, record the divergence")
 
+        from .specs import sdd_config
+        from .specs_migrate import sdd_report
+
+        sdd_detail = sdd_report(root, effective, sdd_config(effective))
+        checks_details["sdd"] = sdd_detail
+        if "suggestion" in sdd_detail:
+            actions.append(f"sdd: {sdd_detail['suggestion']}")
+        if "conflict" in sdd_detail:
+            actions.append(f"sdd: {sdd_detail['conflict']['path']} holds non-SDD files; "
+                           f"{sdd_detail['conflict']['suggestion']}")
+
     healthy = all(checks.values())
     payload: dict[str, Any] = {
@@ -710,4 +722,6 @@ def preset(repository: Path, *, project_stage: str | None = None, project_shape:
     from .rules import load_plugin_packs, plugin_rules_dir
     from .rules_checks import propose_packs, tool_check_report
+    from .specs import SDD_DEFAULTS
+    from .specs_migrate import sdd_report
 
     root = Path(repository).resolve()
@@ -715,11 +729,13 @@ def preset(repository: Path, *, project_stage: str | None = None, project_shape:
     plugin = load_plugin_packs(plugin_rules_dir())
     rule_packs = propose_packs(root, plugin, stack_intent=stack_intent)
+    stage = project_stage or detected["stage"]
+    layout = "sdd" if stage == "greenfield" else ""
     try:
         assignments = preset_assignments(
-            stage=project_stage or detected["stage"], shape=project_shape or detected["shape"],
+            stage=stage, shape=project_shape or detected["shape"],
             rigor=rigor or detected["suggested_rigor"], provider_mode=provider_mode or "single",
             monorepo=monorepo or detected["monorepo"], stack_intent=stack_intent,
             verify_commands=detected["verify_commands"], packages=tuple(detected["packages"]),
-            rule_packs=rule_packs)
+            rule_packs=rule_packs, layout=layout)
     except ValueError as error:
         raise SetupError(str(error)) from error
@@ -727,6 +743,7 @@ def preset(repository: Path, *, project_stage: str | None = None, project_shape:
     tool_checks = [item for item in tool_check_report(root, [plugin[name] for name in rule_packs])
                    if item["status"] != "present"]
+    sdd = sdd_report(root, {}, dict(SDD_DEFAULTS), proposed=bool(layout)) if layout else {"layout": "legacy"}
     return {"status": "proposed", "assignments": assignments, "detected": detected,
-            "rule_packs": rule_packs, "rule_tool_checks": tool_checks,
+            "rule_packs": rule_packs, "rule_tool_checks": tool_checks, "sdd": sdd,
             "warnings": [f"no {key} command detected" for key in missing], "actions": []}
```

- [ ] **Step 4: Skill.** Create `plugins/gin-workflow/src/skills/migrate-specs/SKILL.md`:

```markdown
---
name: migrate-specs
description: Move a legacy .planning specs/plans layout into the SDD docs/ layout, then optionally seed living specs.
---

# Migrate Specs

Load only when the user invokes it.

1. Run `gin-workflow specs migrate --dry-run`. Show the moves, skipped files, and refusals.
2. Refusals: uncommitted changes always stop; ask the user to commit first. An approved-but-unshipped workflow or an open worktree stops unless the user explicitly accepts `--force`.
3. On approval: `git switch -c chore/migrate-specs`, run `gin-workflow specs migrate [--force]`, then commit (`chore(specs): migrate .planning to SDD layout`). Never commit on `main`/`master`.
4. Ask whether to seed living specs now. If yes:
   - If `artifacts.codebase` is empty, run the `tech-doc` skill first.
   - Propose a capability list from `docs/codebase` and `docs/changes/archive/*/design.md`; the user edits it.
   - For each capability, one at a time: draft `docs/specs/<cap>/spec.md` from `gin-workflow specs template spec.md`, describing current behavior only, with IDs `REQ-<CAP>-001…` and at least one GIVEN/WHEN/THEN scenario each; add it to `docs/specs/README.md`; run `gin-workflow specs lint`; show the draft and wait for approval; commit.
   - Stopping midway keeps the committed capabilities.
5. Report the branch, commits, and remaining capabilities. Merging needs the user's approval.
```

Add to `REQUIRED_ARTIFACTS`: `"scripts/workflow_core/specs_migrate.py",` and `"skills/migrate-specs/SKILL.md",`.

- [ ] **Step 5:** Run the Step 2 command → PASS (9 tests). Full suite → `OK`; smoke → exit 0.

- [ ] **Step 6:** Commit `feat(specs): migrate .planning to the SDD layout; setup and doctor SDD checks`.

### Track 5: Stage wiring through the on-demand `gin-sdd` skill

**Metadata:**
- Dependencies: Track 4
- Provider role: docs
- Reasoning: medium
- Model guidance: standard_impl
- Estimated complexity: low

**Files:**
- Create: `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md`
- Modify: `plugins/gin-workflow/src/skills/{discuss,plan,orchestrate,execute,review,verify,ship,quick,tech-doc}/SKILL.md`, `plugins/gin-workflow/src/agents/developer.md`, `tests/workflow_providers/test_harness_packaging.py` (one artifact)
- Test: `tests/workflow_core/test_token_budget.py` (new test)

**Interfaces:**
- Consumes: every `gin-workflow specs` subcommand (Tracks 2–4); `project.layout`/`project.spec_review` from `gin-workflow state` (Track 1).

- [ ] **Step 1: Failing test.** Add to `TestBudgetLimits` in `tests/workflow_core/test_token_budget.py`:

```diff
diff --git a/tests/workflow_core/test_token_budget.py b/tests/workflow_core/test_token_budget.py
index 65bc21e..b7e3548 100644
--- a/tests/workflow_core/test_token_budget.py
+++ b/tests/workflow_core/test_token_budget.py
@@ -112,4 +112,17 @@ class TestBudgetLimits(unittest.TestCase):
         self.assertIn("validate --bead-id <bead-id> --in-history", text)
 
+    def test_sdd_guidance_loads_on_demand(self):
+        sdd_skill = (SRC / "skills/gin-sdd/SKILL.md").resolve()
+        for stage in ("discuss", "plan", "orchestrate", "execute", "review", "verify", "ship", "quick"):
+            text = (SRC / "skills" / stage / "SKILL.md").read_text(encoding="utf-8")
+            with self.subTest(stage=stage):
+                self.assertIn("`gin-sdd` skill", text)
+                self.assertLessEqual(sum("sdd" in line for line in text.splitlines()), 2)
+                self.assertNotIn(sdd_skill, stage_chain(SRC, stage))
+        guide = sdd_skill.read_text(encoding="utf-8")
+        for heading in ("## discuss", "## plan", "## orchestrate", "## execute and review", "## verify", "## ship", "## quick"):
+            with self.subTest(heading=heading):
+                self.assertIn(heading, guide)
+
     def test_commands_agents_and_shared_skills_within_budget(self):
         limits = [("agents/*.md", 4_000), ("skills/gin-*/SKILL.md", 6_000), ("references/shape-*.md", 1_500)]
```

- [ ] **Step 2:** Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/workflow_core/test_token_budget.py -v` → FAIL (`gin-sdd/SKILL.md` missing; stage skills lack the `gin-sdd` line).

- [ ] **Step 3: Implement.** Create `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md`:

```markdown
---
name: gin-sdd
description: Use in a lifecycle stage when `project.layout` is `sdd` — change folders, REQ-IDs, trace, spec review, archive.
---

# SDD Layout

Applies only when `gin-workflow state --format json` reports `project.layout: sdd`. Paths come from `artifacts.specs` (default `docs/specs`) and `artifacts.changes` (default `docs/changes`). Every `state`/`record` call for a change passes `--workflow-id <epic>`. All commands are `gin-workflow specs <command>`; exit 1 means findings to fix, exit 2 means wrong usage or layout.

## discuss
1. After the user confirms the design: `bd create --type epic --title "<title>"` → `specs new <slug> --epic <epic>` creates `<changes>/<epic>-<slug>/`.
2. Write `proposal.md`, `spec-delta.md`, and `design.md` in that folder. Each new requirement gets its ID from `specs next-id <cap>`; a `MODIFIED` or `REMOVED` block puts the output of `specs hash <REQ-ID>` on the line after its heading, and a `REMOVED` block adds `Reason: <why>`. An architecture decision also gets `docs/adr/NNNN-<slug>.md` from `specs template adr.md`.
3. `specs lint --change <epic>` must exit 0.
4. `project.spec_review`:
   - `chat`: the user confirms → `gin-workflow record requirement-confirmed --workflow-id <epic> --evidence <change folder> --actor <id>`.
   - `pr`: commit only the change folder on branch `spec/<epic>-<slug>` and push; ask approval, then `gh pr create --fill`; return `awaiting_spec_review` without recording. On a later run, `specs status --change <epic>`: `merged` → record `requirement-confirmed` with evidence `<pr url> <merge commit>`; `open` → report and stop; `closed` or `none` → ask the user. Implementation branches from the updated base.

## plan
Write `<change>/plan.md`. Each track's Metadata adds `Requirements: REQ-…`; every `ADDED`/`MODIFIED` REQ in the delta belongs to at least one track. Record `plan-approved --workflow-id <epic>`.

## orchestrate
Reuse the epic as parent. Each track bead: `bd create --parent <epic> --spec-id <epic>-<slug> --labels req:<REQ-ID>,…` from its `Requirements:`.

## execute and review
New or changed tests carry the REQ-ID in the test name or a comment (`# REQ-AUTH-003`). The reviewer checks that each scenario of the track's REQs has a test.

## verify
Run `specs lint --change <epic> --against <base>` and `specs trace --change <epic>`. A `missing` REQ is a warning under `easy` rigor and blocks `verification-passed` under `standard` and `strict`. A duplicate ID on the base: `specs renumber <old> <new> --change <epic>`, then rerun both.

## ship
Before presenting options, on the feature branch: `specs archive --change <epic>`, then commit (`docs(specs): archive <epic>`). Exit 1 (living block changed since the delta was written, or lint findings) stops ship: show the findings and ask the user.

## quick
Never creates a change folder. If the change alters behavior a living-spec REQ describes, stop and recommend the full lifecycle.
```

Add one conditional line to each stage skill and the developer agent:

```diff
diff --git a/plugins/gin-workflow/src/skills/discuss/SKILL.md b/plugins/gin-workflow/src/skills/discuss/SKILL.md
index 3eb150f..01554d7 100644
--- a/plugins/gin-workflow/src/skills/discuss/SKILL.md
+++ b/plugins/gin-workflow/src/skills/discuss/SKILL.md
@@ -21,4 +21,5 @@ Turn a requirement into a confirmed design. The user starts with an idea, not a
 4. **Present the design** in sections scaled to complexity (a few sentences up to ~300 words); confirm each section before moving on. Cover architecture, components, data flow, error handling, testing. Prefer small units with one purpose and clear interfaces; in existing code follow existing patterns and include only targeted improvements that serve the goal.
 5. **Write the spec** to `.planning/specs/YYYY-MM-DD-<topic>-design.md`. Commit it on a feature branch, never on `main`/`master`.
+   With `project.layout: sdd` (`gin-workflow state --format json`), steps 5–8 follow the `gin-sdd` skill instead: change folder, REQ-IDs, and `chat` or `pr` spec review.
 6. **Self-review the spec** and fix inline: placeholders (TBD/TODO), contradictions, scope too large for one plan, requirements readable two ways.
 7. **User review** — "Spec written to `<path>`. Please review it and tell me about any changes before we write the implementation plan." Apply changes and repeat step 6 until the user explicitly confirms.
```

```diff
diff --git a/plugins/gin-workflow/src/skills/plan/SKILL.md b/plugins/gin-workflow/src/skills/plan/SKILL.md
index e6f7169..fc865d7 100644
--- a/plugins/gin-workflow/src/skills/plan/SKILL.md
+++ b/plugins/gin-workflow/src/skills/plan/SKILL.md
@@ -15,5 +15,5 @@ Write a plan an engineer with zero context could execute: exact files, code, com
 
 1. Require `requirement_confirmed` (`gin-workflow state`). If objectives, constraints, non-goals, or success criteria are unclear, stop and return to `discuss`. If the spec spans independent subsystems, propose one plan per subsystem.
-2. Save to `.planning/plans/YYYY-MM-DD-<feature>.md` (user preference overrides) using the format in [plan-schema.md](plan-schema.md). Start with Goal, Architecture, Tech Stack, and **Global Constraints** copied verbatim from the spec.
+2. Save to `.planning/plans/YYYY-MM-DD-<feature>.md` (with `project.layout: sdd`: `<change>/plan.md` plus per-track `Requirements:`, per the `gin-sdd` skill; user preference overrides) using the format in [plan-schema.md](plan-schema.md). Start with Goal, Architecture, Tech Stack, and **Global Constraints** copied verbatim from the spec.
 3. Map files first: each file one responsibility; files that change together live together; follow existing patterns.
 4. Size tracks: the smallest unit with its own test cycle that a reviewer could reject independently. Fold setup, config, and docs into the track that needs them. Steps are 2–5 minutes each: failing test → run (fail) → minimal code → run (pass) → commit only if authorized.
```

```diff
diff --git a/plugins/gin-workflow/src/skills/orchestrate/SKILL.md b/plugins/gin-workflow/src/skills/orchestrate/SKILL.md
index 3fb15a8..5f9eb15 100644
--- a/plugins/gin-workflow/src/skills/orchestrate/SKILL.md
+++ b/plugins/gin-workflow/src/skills/orchestrate/SKILL.md
@@ -14,5 +14,5 @@ Turn an approved plan into durable Beads state. Beads is the only source of stat
 ## Steps
 
-1. Require `plan_approved` and read the plan from `.planning/plans/`.
+1. Require `plan_approved` and read the plan from `.planning/plans/`. With `project.layout: sdd`, read `<change>/plan.md`, reuse the epic, and label tracks per the `gin-sdd` skill.
 2. Reject any implementation or review track without a provider role and reasoning; list every one.
 3. Resolve routes for the whole batch before any durable write: build an `AssignmentRequest(task_id, provider_role, reasoning, main_harness, workflow_id)` per track and call `workflow_core.assignments.resolve_all_assignments(requests, config, local)` (`PYTHONPATH=<plugin>/scripts`; `config` is the generated effective config and `local` comes from `workflow_core.provider_config.load_provider_local_config(repo)`). If anything is unresolved, report all diagnostics and stop. Otherwise persist each preview with `write_assignment_manifest`. Concrete provider/model names never enter Beads or the plan.
```

```diff
diff --git a/plugins/gin-workflow/src/skills/execute/SKILL.md b/plugins/gin-workflow/src/skills/execute/SKILL.md
index d29c845..71f063b 100644
--- a/plugins/gin-workflow/src/skills/execute/SKILL.md
+++ b/plugins/gin-workflow/src/skills/execute/SKILL.md
@@ -21,4 +21,5 @@ Implement one ready work unit inside its approved scope and record evidence.
 - Follow the plan steps exactly, test first. Keep changes minimal and in scope.
 - Read the shape appendix for `project.shape` from `gin-workflow state --format json` (plugin `references/shape-<shape>.md`) before editing.
+- With `project.layout: sdd`, tests carry the track's REQ-IDs (the `gin-sdd` skill).
 - Run `gin-workflow rules --files <scope files>` and give its output to the `developer` agent (or follow it when executing directly). Rules never widen the scope.
 - On a `greenfield` project, a task that sets up lint, typecheck, or test starts from the `suggest` snippets of the missing checks in `checks_details.rules.tool_checks` of `gin-workflow setup doctor --format json`.
```

```diff
diff --git a/plugins/gin-workflow/src/skills/review/SKILL.md b/plugins/gin-workflow/src/skills/review/SKILL.md
index de0bf57..3178589 100644
--- a/plugins/gin-workflow/src/skills/review/SKILL.md
+++ b/plugins/gin-workflow/src/skills/review/SKILL.md
@@ -21,5 +21,5 @@ Review after every track, after a major feature, and before merge; never skip be
 1. Independence follows `project.independence` from `gin-workflow state --format json`: `provider` — the reviewer provider must differ from the implementation provider; `session` — a fresh session/subagent of the same provider with a clean context and a different actor id (`reviewer:<provider>:session-<id>`), never the implementer's session. Self-review only under the explicit `allow_self_review_fallback` policy; otherwise route exhaustion needs a human decision.
 2. `start-review --actor-id <reviewer>` acquires the lease (`--force-takeover --reason "<why>"` only when authorized; `resync-lease --lease-id <id>` after a stale revision). `validate` replays the ledger.
-3. Inspect the in-scope files for correctness, edge cases, error handling, security, performance, and plan alignment; run the tests in isolation. Never modify implementation files. Check the rules checklist, `critical` and `high` first; cite a violation as `<pack>#<anchor>`, and record a `critical` violation at severity `IMPORTANT` or higher.
+3. Inspect the in-scope files for correctness, edge cases, error handling, security, performance, and plan alignment; run the tests in isolation. Never modify implementation files. Check the rules checklist, `critical` and `high` first; cite a violation as `<pack>#<anchor>`, and record a `critical` violation at severity `IMPORTANT` or higher. With `project.layout: sdd`, each scenario of the track's REQs needs a test (the `gin-sdd` skill).
 4. Record each issue with `add-finding --finding-id <id> --severity <sev> --actor-id <reviewer> --lease-id <lease>`.
 5. For a claimed fix, check the tree. If confirmed, `verify-finding`; if absent, incomplete, or wrong, `reopen-finding --reason "<why>"`. `verified` is terminal, so never verify what you could not confirm. If sources changed, re-run `checkpoint` before approving.
```

```diff
diff --git a/plugins/gin-workflow/src/skills/verify/SKILL.md b/plugins/gin-workflow/src/skills/verify/SKILL.md
index 2d7048c..19c33ba 100644
--- a/plugins/gin-workflow/src/skills/verify/SKILL.md
+++ b/plugins/gin-workflow/src/skills/verify/SKILL.md
@@ -22,5 +22,5 @@ Gate for every claim: identify the command that proves it → run it fully and f
    - `python3 review-ledger.py render --bead-id <bead-id> --check` — no drift in `review.md`.
 3. **Quality gates**: run `project.verify_commands` from `gin-workflow state --format json` per rigor (easy: lint, typecheck, tests; standard: + build; strict: + e2e/a11y when configured), then any manual/UI checks the plan specifies.
-4. **Requirements**: re-read the confirmed spec and approved plan, make a line-by-line checklist, and verify each item against the code — not only the diff.
+4. **Requirements**: re-read the confirmed spec and approved plan, make a line-by-line checklist, and verify each item against the code — not only the diff. With `project.layout: sdd`, also run `specs lint` and `specs trace` per the `gin-sdd` skill.
 5. Record every run, failure, skipped check (say so explicitly), risk, and unavailable provider. Failures route to the `gin-debugging` skill; do not patch blindly here.
```

````diff
diff --git a/plugins/gin-workflow/src/skills/ship/SKILL.md b/plugins/gin-workflow/src/skills/ship/SKILL.md
index 4944035..7065f20 100644
--- a/plugins/gin-workflow/src/skills/ship/SKILL.md
+++ b/plugins/gin-workflow/src/skills/ship/SKILL.md
@@ -14,5 +14,5 @@ Verify → detect workspace → present options → execute the choice → clean
 ## Steps
 
-1. Require `verification_passed` and a terminal review state. Re-run the project test command; if it fails, show the failures and stop.
+1. Require `verification_passed` and a terminal review state. Re-run the project test command; if it fails, show the failures and stop. With `project.layout: sdd`, archive the change into the living spec first, per the `gin-sdd` skill.
 2. Detect the workspace before changing directory and save the results:
    ```bash
````

```diff
diff --git a/plugins/gin-workflow/src/skills/quick/SKILL.md b/plugins/gin-workflow/src/skills/quick/SKILL.md
index 5676da9..527be5f 100644
--- a/plugins/gin-workflow/src/skills/quick/SKILL.md
+++ b/plugins/gin-workflow/src/skills/quick/SKILL.md
@@ -12,5 +12,5 @@ description: Small, low-risk change without plan or beads: confirm, implement, v
 A fast path for a small, low-risk change. No plan, no beads, no lifecycle gates.
 
-1. Restate the requirement in 1–3 lines and get the user's confirmation.
+1. Restate the requirement in 1–3 lines and get the user's confirmation. With `project.layout: sdd`, a change to behavior a living-spec REQ describes escalates (the `gin-sdd` skill).
 2. Estimate the changed files and top-level modules, then run `gin-workflow quick-check --changed-files N --modules M --format json`:
    - `refused`: stop and point to `/gin-workflow:discuss` (strict rigor needs a `requirement_confirmed` waiver first).
```

```diff
diff --git a/plugins/gin-workflow/src/skills/tech-doc/SKILL.md b/plugins/gin-workflow/src/skills/tech-doc/SKILL.md
index 51c926b..09cd657 100644
--- a/plugins/gin-workflow/src/skills/tech-doc/SKILL.md
+++ b/plugins/gin-workflow/src/skills/tech-doc/SKILL.md
@@ -12,5 +12,5 @@ Write durable technical documentation for onboarding, architecture review, and p
 1. **Scope**: whole repository or one subsystem (focus there, but note key outside dependencies). Confirm the target output before writing unless the request, Beads task, or approved plan already authorizes it.
 2. **Gather evidence**: when `.codegraph/` exists, start with `codegraph files` for structure and `codegraph explore "<subsystem or question>"` for symbols and call paths; otherwise use grep and read. Treat index output as hints until verified against the files. Prefer code, lockfiles, configuration, migrations, schemas, tests, and workflow files.
-3. **Choose the shape**: default to the split set below under `.planning/codebase/` (or `.planning/codebase/<scope-slug>/` for a subsystem). Use a single combined document only when the user asks for one, the scope is very narrow, or an approved plan says so. Do not invent alternate names (`Backend.md`, `Database.md`) when a canonical file covers the topic.
+3. **Choose the shape**: default to the split set below under `.planning/codebase/` (with `project.layout: sdd`, `artifacts.codebase`, default `docs/codebase/`; a subsystem gets a `<scope-slug>/` subfolder). Start each file from `gin-workflow specs template codebase/<FILE>.md`, which honors project overrides in `.agent-workflow/templates/`. Use a single combined document only when the user asks for one, the scope is very narrow, or an approved plan says so. Do not invent alternate names (`Backend.md`, `Database.md`) when a canonical file covers the topic.
 4. **Write**: clear prose with headings and short lists; Mermaid only where it clarifies architecture, data flow, or ownership; one topic per file, linking to siblings instead of repeating them.
 5. **Mark uncertainty**: separate verified facts from inference; name what is unknown and where the answer likely lives.
```

```diff
diff --git a/plugins/gin-workflow/src/agents/developer.md b/plugins/gin-workflow/src/agents/developer.md
index be9fb84..93d335d 100644
--- a/plugins/gin-workflow/src/agents/developer.md
+++ b/plugins/gin-workflow/src/agents/developer.md
@@ -21,4 +21,5 @@ Before editing:
 5. Follow the rules block the orchestrator passed (`gin-workflow rules --files <scope>`); run that command yourself when none was passed.
 6. On a `greenfield` project, when the task sets up lint, typecheck, or test, start from the `suggest` snippets of the missing checks in `checks_details.rules.tool_checks` of `gin-workflow setup doctor --format json`.
+7. With `project.layout: sdd`, put the track's REQ-IDs in new or changed test names or comments.
 
 ## Guidelines
```

Add to `REQUIRED_ARTIFACTS`: `"skills/gin-sdd/SKILL.md",`.

- [ ] **Step 4:** Run the Step 2 command → PASS. `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.budget --report` → every stage within its limit (prototype: discuss 4,795; plan 8,228; orchestrate 4,820; execute 10,592; verify 5,058; ship 6,079; review 5,708; quick 4,060; descriptions 2,944). Full suite → `OK` (prototype: `Ran 686 tests … OK`); smoke → exit 0.

- [ ] **Step 5:** Commit `feat(skills): SDD layout procedure in gin-sdd, wired into stage skills`.

## Integration
- **Branch**: `feat/sdd-living-specs` in `.planning/worktrees/<epic>` (from `master`).
- **Merge strategy**: sequential (Tracks 1 → 2 → 3 → 4 → 5).

## Validation
Spec §Testing:
- [ ] Existing tests pass unmodified apart from the current-version assertions listed in Global Constraints; a config without `layout` and with `layout: legacy` behaves as before — `test_schema_2_6.py::test_project_settings_default_to_legacy_chat`, `test_specs.py::TestSpecsCli::test_exit_codes_and_layout_guard`, `test_specs_migrate.py::test_setup_preset_proposes_sdd_only_for_greenfield`.
- [ ] Unit tests: block parser and hash, every lint rule, `next-id` across worktrees and a fake remote, `renumber` (files, refusal, bead label calls) — `test_specs.py`; `trace` (code tag, `tests.md`, missing), `archive` (each delta kind, new capability, base-hash conflict leaves tree untouched), `status` (none/open/merged/closed/unavailable/error) — `test_specs_archive_trace.py`; `migrate` (dry-run, pairing, unpaired, skipped, each refusal, `--force`) — `test_specs_migrate.py`.
- [ ] End-to-end on a temporary git repo: `new` → delta → `lint --against` → `trace` → `archive` → `lint` — `test_specs_archive_trace.py::TestEndToEnd`.
- [ ] Schema 2.6 tests and migration from 2.5 — `test_schema_2_6.py`.
- [ ] Token budget: chains within limits; `gin-sdd` not in any stage chain; each stage skill has at most two `sdd` lines — `test_token_budget.py::test_sdd_guidance_loads_on_demand`.
- [ ] Installer smoke: `templates/` in dists and launcher; `gin-workflow specs --help` exits 0 — `tests/install_smoke_test.sh`.
- [ ] Full suite `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py` → `OK`.

## Risks
- `next-id` fetches on every call; on a slow remote that costs seconds. It only warns on failure and never blocks.
- `trace` matches REQ-IDs textually in test files: a stale comment counts as coverage. The reviewer step ("each scenario has a test") is the human check on top.
- `archive` writes spec files before `git mv`; if the move then fails, the specs are updated but the change folder stays. Rerunning `archive` reports the ADDED IDs as already existing, so this rare case is finished by hand (`git mv` the folder into `archive/`).
- `specs status` relies on `gh` auth; without it the skill falls back to a manual `record` with the PR URL.
- Installed launcher and plugin snapshots must be refreshed after merge (ship step 8) or `gin-workflow specs` is missing on this host.

## Notes
- Parent Bead (deliverable) remains open until a human-confirmed merge; track beads close after tests and review pass.
- Provider roles and reasoning are portable; concrete models are resolved at orchestration.
- Every code block in this plan was run in a scratch worktree of `master` @ `16381fc` before the plan was written: per-track suites passed at each track's version of `specs_cli.py`, and the full suite ended at `Ran 686 tests … OK` with `bash tests/install_smoke_test.sh` exit 0.

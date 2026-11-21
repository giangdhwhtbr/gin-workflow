# Plan: Retire gin-orchestrator

Workflow: retire-orchestrator
Spec: `.planning/specs/2026-11-21-retire-orchestrator-design.md`

## Objective

gin 3.3.0 ships without the gin-orchestrator extension. Every stage runs inside the session's own harness, config schema 2.11 has no `orchestrator`, `provider_mode`, or `routing.review.independence`, the installers refuse the plugin and remove a copy that 3.2.0 installed, and nothing shipped or documented names it. The full suite passes.

## Global Constraints

From the spec:

- The extension is deleted, not moved. `v3.2.0` is its archive; no extra tag.
- The five main harnesses, their model catalogs (`catalog.py`), install targets, and per-harness bundles are unchanged.
- `gin routes resolve`, `gin routes dispatch`, the assignment manifest, the `route.dispatched` event, and `provider_role`, `Model:`, `Effort:` on tracks are unchanged.
- The word "orchestrator" as a role or actor name (`agents/*.md`, `review_ledger/bead_fsm.py`) and the `orchestrate` stage are unchanged.
- `workflow_core/events.py` is unchanged: `_TERMINAL_WORKER_EVENTS` stays, because reading `events.jsonl` recomputes the id of old `worker.*` events.
- Configs at schema 2.3 to 2.10 stay supported. One that still holds the three keys keeps working: role names under `orchestrator.roles` count as known roles and resolve to the main harness, the rest is ignored.
- `LOCAL_GITIGNORE_ENTRIES` and the local-file list in `bundles.py` keep naming `orchestrator.local.yaml`.
- On codex, opencode, and copilot: `execute` implements in the session and notes `in_session`; `review` stops for the user unless `allow_self_review_fallback`; research and tech-doc work run in the session. `gin-workflow-nox6` replaces this later.
- Out of scope: native subagents (`gin-workflow-nox6`), work shared between harnesses, faster tests, tagging `v3.3.0`, this repository's own `.agent-workflow/config.yaml` (a `/quick` after 3.3.0 is installed).

Added by this plan:

- When the epic ends, no file under `plugins/`, `scripts/`, `.claude-plugin/`, `docs/` (except `docs/changelog.md` and `docs/guides/upgrading*.md`), `README.md`, `AGENTS.md`, or `mkdocs.yml` contains `gin-orchestrator` or `gin_orchestrator`; Track 6 enforces it. New messages, comments, and docstrings name the config keys or say "the worker extension".
- Tracks run in order. Each leaves the tests it names green, and Tracks 2 and 4 run the full suite.
- Every stage chain stays at or under 12,000 characters (`tests/workflow_core/test_token_budget.py`); Track 1 only removes text.
- No track runs `./install.sh` against the real `HOME`, `gin setup update`, or `gin setup refresh`: the installed gin 3.2.0 and the main checkout's generated config serve other sessions. `tests/install_smoke_test.sh` uses its own temporary `HOME`.
- `install.ps1` and `tests/install_smoke_test.ps1` cannot run on this machine (no `pwsh`). They are edited to mirror the bash changes; the Windows job of `.github/workflows/test.yml` runs them before the release tag.
- Read a pytest summary line before calling a run green: `N passed`, no `failed`, no `error`.

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
- Problem statement: the extension is 27% of the Python source and 362 tests, core keeps a facade (`workflow_core/ext.py`) stable for it, and in this repository 54 worker requests gave 20 completed workers while 252 of 281 routes already went to the main harness.
- Success criteria: the "Done when" list of the spec: the suite and the install smoke test pass, `gin docs check` is clean for the changed pages, `mkdocs build --strict` passes on CI, and gin-console still lists this repository after a reinstall.
- Constraints: Global Constraints above.
- Non-goals: the out-of-scope list above.

## Approach Options
### Option 1: One cut, released as 3.3.0 (confirmed at discuss)
- Summary: delete the extension, the client, the facade, and the config keys in one epic; unmigrated configs keep working with a warning; `gin setup update --to-version 2.11 --approve` cleans them.
- Pros: no dead branch or facade contract left in core; one release.
- Cons: a project that used the extension loses delegated execution and cross-provider review at upgrade.

### Option 2: Deprecate in 3.3.0, delete in 4.0.0
- Summary: 3.3.0 warns and drops the plugin from `--plugin all`; 4.0.0 deletes.
- Pros: a transition release for other users.
- Cons: two releases; 21k lines live one more cycle. Rejected at discuss.

### Option 3: Delete the extension, keep the seam in core
- Summary: keep `orchestrator_client.py`, `ext.py`, and `provider_mode` for a later external tool.
- Pros: smallest diff.
- Cons: dead branches and a facade contract stay in core. Rejected at discuss.

### Recommended Approach
- Selected option: Option 1.
- Rationale: confirmed by the user; removal follows the pattern already used for `notifications` in schema 2.10.

## Scope
- In scope: sections A to F of the spec.
- Out of scope: the Global Constraints' out-of-scope list.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: The tracks share test files (test_config_examples.py, test_setup_cli.py, test_lifecycle_cli.py, the install smoke tests), and each track needs the suite state the previous one leaves.
```

## Tasks

### Track 1: Skills stop naming the extension
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/discuss/SKILL.md:20` (research clause)
  - Modify `plugins/gin-workflow/src/skills/plan/SKILL.md:22` (research clause)
  - Modify `plugins/gin-workflow/src/skills/tech-doc/SKILL.md:28-31` (three spawn clauses)
  - Modify `plugins/gin-workflow/src/skills/execute/SKILL.md:32` (dispatch sentence)
  - Delete `plugins/gin-workflow/src/skills/execute/references/worker-lifecycle.md`
  - Modify `plugins/gin-workflow/src/skills/review/SKILL.md:19-24` (reviewer spawn, independence)
  - Modify `plugins/gin-workflow/src/skills/setup/SKILL.md:12-38` (worker harness sentence, action list)
  - Modify `plugins/gin-workflow/src/skills/parallel-agents/SKILL.md:27` (one clause)
  - Test `tests/workflow_core/test_skill_routing.py:178-208`
  - Modify `tests/install_smoke_test.sh:106` (required-file entry)
- **Provider role**: `general`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** every replacement text is given below, but the lines are 500 to 900 characters long and budget and phrase tests read them.
- **Steps**:
  1. In `tests/workflow_core/test_skill_routing.py`:
     - Delete `test_skills_reference_orchestrator_dispatch` (lines 196-208).
     - In `test_execute_references_use_dispatch_and_normalized_statuses` delete the two lines that read `plugins/gin-orchestrator/.../worker_dispatch.py` and assert `status must be completed, failed, or cancelled`, and replace the final loop with
       ```python
       self.assertIn("routes dispatch", policy)
       ```
     - Add
       ```python
       def test_skills_do_not_name_the_retired_extension(self):
           self.assertFalse((SRC / "skills/execute/references/worker-lifecycle.md").exists())
           for path in sorted((SRC / "skills").rglob("*.md")) + sorted((SRC / "references").glob("*.md")):
               text = path.read_text(encoding="utf-8")
               with self.subTest(file=str(path.relative_to(SRC))):
                   for gone in ("gin-orchestrator", "worker-lifecycle", "project.independence", "--probe"):
                       self.assertNotIn(gone, text)
       ```
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_skill_routing.py -q`: the new test fails.
  3. Edit the skills. Each "old" text occurs once in its file.
     - `discuss/SKILL.md:20`, old:
       ```text
       spawn natively when supported, else run `gin-orchestrator dispatch --workflow-id <topic> --task-id <topic>-scout --stage discuss --role research --model <model> --workspace . --objective "<brief>" --agent agent-researcher --json`)
       ```
       new:
       ```text
       spawn natively when supported, else do the lookup in this session)
       ```
     - `plan/SKILL.md:22`, old:
       ```text
       spawn natively when supported, else run `gin-orchestrator dispatch --workflow-id <id> --task-id <id>-scout --stage plan --role research --model <model> --workspace . --objective "<brief>" --agent agent-researcher --json`)
       ```
       new: the same text as in `discuss`.
     - `tech-doc/SKILL.md:28`, `:30`, `:31`: in each line replace the parenthetical that starts with ``(native subagent or `gin-orchestrator dispatch --workflow-id tech-doc`` and ends with ``--json`)`` by
       ```text
       (native subagent; a harness without one does this in the session, one item at a time)
       ```
     - `execute/SKILL.md:32`: replace ``When `provider` is the main harness `claude` or `antigravity`, always spawn`` by ``On `claude` or `antigravity`, always spawn``, and replace the sentence that starts with ``Otherwise (a provider other than the main harness`` and ends with ``note `in_session` on the bead.`` by
       ```text
       On `codex`, `opencode`, or `copilot`, implement the track in this session with that context and note `in_session` on the bead.
       ```
     - `git rm plugins/gin-workflow/src/skills/execute/references/worker-lifecycle.md`.
     - `review/SKILL.md:19`: replace the text that starts with ``always natively when `route.provider == main_harness` is `claude` `` and ends with ``no self-review unless `allow_self_review_fallback`.`` by
       ```text
       natively on `claude` (`Agent`) or `antigravity` (`invoke_subagent`, `Model="inherit"`). Without a native subagent, stop for the user; no self-review unless `allow_self_review_fallback`.
       ```
     - `review/SKILL.md:24`: replace the text that starts with ``Independence follows `project.independence`:`` and ends with ``never the implementer's session.`` by
       ```text
       Independence: the reviewer is a fresh session/subagent of the same harness with a clean context and a different actor id (`reviewer:<provider>:session-<id>`), never the implementer's session.
       ```
       and delete the sentence ``Provider independence needs gin-orchestrator; without it independence is `session`.``
     - `setup/SKILL.md:12`: the line becomes `Setup runs with one main harness.`
     - `setup/SKILL.md:38`: replace `` `detect`, `preset`, `models`, `configure` `` by `` `detect`, `preset`, `configure` ``, and ``(`--probe` for active model health; also reports`` by `(reports`.
     - `parallel-agents/SKILL.md:27`: delete ` (workers on other harnesses and their capacity limits need gin-orchestrator)`.
  4. In `tests/install_smoke_test.sh` delete line 106 (`"skills/execute/references/worker-lifecycle.md"`).
  5. Run `timeout 300 python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py tests/test_no_direct_bd.py -q`: passes. Run `(cd plugins/gin-workflow/src/scripts && python3 -m workflow_core.budget --report)`: discuss below 11,441, plan below 11,981, execute below 11,816, review below 10,832.
  6. Commit: `refactor(skills): stages run on the session's harness; drop worker dispatch (retire-orchestrator)`.
- **Acceptance criteria**: no skill or reference names the extension, `worker-lifecycle.md`, `project.independence`, or `--probe`; `gin:agent-researcher` and `routes dispatch` are still named where the existing tests expect them; budgets hold.
- **Estimated complexity**: low

### Track 2: Delete the extension; installers refuse and remove it
- **Dependencies**: Track 1
- **Files**:
  - Delete `plugins/gin-orchestrator/`
  - Delete `tests/gin_orchestrator/`
  - Delete `tests/workflow_core/test_import_boundary.py`
  - Modify `.claude-plugin/marketplace.json:33-42`
  - Modify `scripts/bump_version.py:13-36`
  - Modify `install.sh:14-1053` (lines 14, 43, 89-100, 719, after 807, 1006, 1015, 1022-1026, 1034, before 1049, 1053)
  - Modify `install.ps1:20-1129` (lines 20, 707, after 844, 1039-1040, 1067, 1082, 1090-1099, 1106, before 1122, 1129)
  - Modify `tests/install_smoke_test.sh:128-687`
  - Modify `tests/install_smoke_test.ps1:90-233`
  - Modify `tests/test_all.py:14`
  - Modify `tests/gin_qa/test_packaging.py:32-34`
  - Modify `tests/workflow_core/test_rename_sweep.py:13`
  - Modify `tests/workflow_core/test_config_examples.py:7-41`
  - Test `tests/workflow_core/test_assignments.py:77` (added during execute: the full suite of this track found the assertion on an execute-skill phrase that Track 1 removed; it now asserts the `in_session` sentence, in its own commit)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded edits with the code given, across two installers and their smoke tests; the PowerShell side cannot be run here, so it must mirror the bash side line for line.
- **Steps**:
  1. Tests first, in `tests/install_smoke_test.sh`:
     - Delete line 128 (`rm -rf plugins/gin-orchestrator/dist`) and line 147 (its `assert_not_exists`).
     - Replace lines 238-251 (the `--plugin gin-orchestrator --dry-run` block; keep `empty_home`, the next block uses it) by
       ```bash
       # gin-orchestrator was removed in gin 3.3.0: the installer refuses it.
       empty_home="$(mktemp -d)"
       if HOME="$empty_home" ./install.sh --platform claude --plugin gin-orchestrator --dry-run >"$output_file" 2>&1; then
         echo "Expected --plugin gin-orchestrator to be refused" >&2
         exit 1
       fi
       assert_contains "$output_file" "gin-orchestrator was removed in gin 3.3.0"
       assert_not_exists "plugins/gin-orchestrator/src"
       ```
     - In the `--plugin all --dry-run` block (lines 253-259) delete the three asserts on `Processing plugin: gin-orchestrator`, `installing it first`, and `would install gin-orchestrator launcher`, and add `assert_not_contains "$output_file" "gin-orchestrator"`.
     - Delete lines 490-511 (the two blocks that install gin-orchestrator into `MOCK_HOME` and into `orch_home`).
     - Lines 566-570: the loop becomes `for plugin in gin-workflow gin-qa; do`; delete the `gin-orchestrator)` arm.
     - Lines 672 and 681: both loops become `for addon in gin-qa; do`. Delete line 687 (the `gin-orchestrator version --json` call). After the `gin-ba` asserts of that block add
       ```bash
       # A gin-orchestrator that gin 3.2.0 installed is removed by any install run.
       retired_home="$MOCK_HOME/retired-home"
       mkdir -p "$retired_home/.local/lib/gin-orchestrator/3.2.0" "$retired_home/.local/bin" \
         "$retired_home/.claude/skills/gin-orchestrator/skills/providers"
       printf '%s\n' '# retired add-on copy' > "$retired_home/.local/lib/gin-orchestrator/3.2.0/gin-orchestrator"
       ln -s "$retired_home/.local/lib/gin-orchestrator/3.2.0/gin-orchestrator" "$retired_home/.local/bin/gin-orchestrator"
       HOME="$retired_home" ./install.sh --platform claude >"$output_file" 2>&1
       assert_contains "$output_file" "Removed the gin-orchestrator launcher at"
       if [ -L "$retired_home/.local/bin/gin-orchestrator" ]; then
         echo "Expected the gin-orchestrator launcher link to be removed" >&2
         exit 1
       fi
       assert_not_exists "$retired_home/.local/lib/gin-orchestrator"
       assert_not_exists "$retired_home/.claude/skills/gin-orchestrator"
       assert_not_contains "$output_file" "Refreshing the installed gin-orchestrator add-on."
       ```
  2. Other tests:
     - `tests/gin_qa/test_packaging.py:32-34`: remove the `"gin-orchestrator": "plugins/gin-orchestrator/src"` entry from the expected dict.
     - `tests/test_all.py:14`: the tuple becomes `("workflow_core", "review_ledger", "gin_qa", "gin_ba")`.
     - `tests/workflow_core/test_rename_sweep.py:13`: drop `"plugins/gin-orchestrator/src"` from `ROOTS`.
     - `tests/workflow_core/test_config_examples.py`: remove the `sys.path` insert of `plugins/gin-orchestrator/src/scripts` (line 10), the import of `validate_local_config` (line 13), the load of `orchestrator.local.example.yaml` (line 22), and the assertions on `local` in `test_full_examples_validate_with_production_loaders_and_show_expected_routes`. Keep its assertions on `portable`; Track 3 changes those.
     - `git rm tests/workflow_core/test_import_boundary.py`.
  3. Run `timeout 300 python3 -m pytest tests/gin_qa/test_packaging.py -q`: fails on the marketplace dict. `timeout 900 bash tests/install_smoke_test.sh` stops at the refusal case.
  4. Remove the extension: `git rm -r -q plugins/gin-orchestrator tests/gin_orchestrator && rm -rf plugins/gin-orchestrator` (the second command removes the untracked `dist/`).
  5. `.claude-plugin/marketplace.json`: delete the `gin-orchestrator` object (lines 34-42) and the comma after the `gin-ba` object.
  6. `scripts/bump_version.py`: `PLUGINS = ("gin-workflow", "gin-qa", "gin-ba")`; delete the `ORCHESTRATOR_VERSION` location (line 29), `"ORCH_LAUNCHER_VERSION"` (line 31), `"OrchLauncherVersion"` (lines 32-33), and the `docs/reference/orchestrator-contract.md` location with the comment above it (lines 35-36).
  7. `install.sh`:
     - Delete line 14 (`ORCH_LAUNCHER_VERSION="3.2.0"`).
     - Line 43: the value list becomes `(gin-workflow|gin-qa|gin-ba|all)`.
     - Lines 89-93 become
       ```bash
         gin-orchestrator)
           echo "Error: gin-orchestrator was removed in gin 3.3.0" >&2
           exit 1
           ;;
         all)
           PLUGINS=(gin-workflow gin-qa gin-ba)
           ;;
       ```
     - Line 100: the message lists `'gin-workflow', 'gin-qa', 'gin-ba', or 'all'`.
     - Delete line 719 (`gin-orchestrator) packages=gin_orchestrator ;;`).
     - After `remove_legacy_plugin` (lines 783-807) add
       ```bash
       # gin-orchestrator was removed in gin 3.3.0: its launcher and its global
       # plugin installs go, for each selected harness.
       remove_retired_orchestrator() {
         local old=gin-orchestrator
         remove_managed_launcher "$old"
         if [ "$DRY_RUN" = true ]; then
           return
         fi
         if matches_platform "claude" && [ "$HAS_CLAUDE" = true ] && [ -d "${HOME}/.claude/skills/$old" ]; then
           disable_claude_plugin "$old"
           rm -rf "${HOME}/.claude/skills/$old"
         fi
         if matches_platform "opencode"; then
           rm -rf "${HOME}/.config/opencode/skills/$old"
         fi
         if matches_platform "antigravity" && [ "$HAS_AGY" = true ]; then
           rm -rf "${HOME}/.gemini/config/plugins/$old"
         fi
         # Best effort: the plugin may not be registered, and then the harness CLI exits non-zero.
         if matches_platform "codex" && [ "$HAS_CODEX" = true ]; then
           codex plugin remove "$old@gin-workflow-marketplace" >/dev/null 2>&1 || true
         fi
         if matches_platform "copilot" && [ "$HAS_COPILOT" = true ]; then
           copilot plugin uninstall "$old" >/dev/null 2>&1 || true
         fi
       }
       ```
       `remove_managed_launcher` (line 677) honours `DRY_RUN` and prints nothing when no launcher exists, so a dry run on a clean `HOME` prints no line with the name. `disable_claude_plugin` (line 233) edits `enabledPlugins` in the user's `~/.claude/settings.json`, as `remove_legacy_plugin` already does; the directory guard keeps it from running where the plugin was never installed.
     - Line 1006: drop `plugins/gin-orchestrator/dist` from the `rm -rf` list.
     - In the `--uninstall` block, next to `remove_managed_launcher gin-workflow` (line 1015), add `remove_managed_launcher gin-orchestrator`.
     - Delete lines 1022-1026 (the `gin-orchestrator requires gin` block).
     - Line 1034: `for addon in gin-qa; do`.
     - Directly before `for p_name in "${PLUGINS[@]}"; do` (line 1049) add a line `remove_retired_orchestrator`.
     - Delete line 1053 (the `gin-orchestrator)` arm).
  8. `install.ps1`, mirroring step 7:
     - Keep `'gin-orchestrator'` in the `ValidateSet` of line 6 so the script can print its own message; before `$Plugins = switch ($Plugin) {` (line 1039) add
       ```powershell
       if ($Plugin -eq 'gin-orchestrator') {
           throw 'Error: gin-orchestrator was removed in gin 3.3.0'
       }
       ```
     - Delete line 20 (`$OrchLauncherVersion`), line 707 (`'gin-orchestrator' { @('gin_orchestrator') }`), lines 1090-1099 (the `requires gin` block), and line 1129 (the `'gin-orchestrator' { $OrchLauncherVersion }` arm).
     - Line 1040: `'all' { @('gin-workflow', 'gin-qa', 'gin-ba') }`. Line 1067: drop the `plugins/gin-orchestrator/dist` entry. Line 1106: `foreach ($addon in @('gin-qa')) {`.
     - After `Remove-LegacyPlugin` (lines 810-844) add `Remove-RetiredOrchestrator`: `$old = 'gin-orchestrator'`; `Remove-ManagedLauncher -Name $old`; `if ($DryRun) { return }`; then the body of `Remove-LegacyPlugin` without its OpenCode agents block, with the Claude branch also requiring `Test-Path -LiteralPath (Join-Path $UserHome ".claude/skills/$old")`. Read `Remove-ManagedLauncher` (line 527) first and confirm it removes nothing under `-DryRun`.
     - Call `Remove-RetiredOrchestrator` directly before the final `foreach ($name in $Plugins) {` (line 1122), and add `Remove-ManagedLauncher -Name 'gin-orchestrator'` in the uninstall block after line 1082.
  9. `tests/install_smoke_test.ps1`: apply the same changes as step 1 to lines 90-103 (the gin-orchestrator install cases become the refusal case, asserting the thrown message), 179-182, and 233 (drop the plugin from the upgrade list), and add the retired-home case with a `gin-orchestrator.cmd` shim written the way that file writes its other stale shims.
  10. Run `timeout 600 python3 -m pytest tests/test_bump_version.py tests/test_version_pins.py tests/gin_qa/test_packaging.py tests/workflow_core/test_rename_sweep.py tests/workflow_core/test_config_examples.py tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_skill_routing.py -q`: passes.
  11. Run `timeout 900 bash tests/install_smoke_test.sh`: exits 0.
  12. Run `timeout 900 python3 -m pytest -n auto -q`: no failures.
  13. Commit: `feat(install)!: remove the gin-orchestrator plugin; installers refuse it and remove a 3.2.0 copy (retire-orchestrator)`.
- **Acceptance criteria**: the plugin and its tests are gone from git; `--plugin gin-orchestrator` exits non-zero with `gin-orchestrator was removed in gin 3.3.0`; a `HOME` seeded with a 3.2.0 launcher and Claude skills folder has neither after `./install.sh --platform claude`; `--plugin all --dry-run` on a clean `HOME` prints nothing with the name; the suite passes.
- **Estimated complexity**: medium

### Track 3: Config schema 2.11
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/schemas.py:11-12`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/migrations.py:17-153`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/configuration.py:27-228`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py:483-766` (doctor action after line 486, `update` lines 707-766)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:590` (state warning)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/project.py:105-108` (preset)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/executables.py:85`
  - Modify `plugins/gin-workflow/src/examples/config.full.yaml:1-100`
  - Test `tests/workflow_core/test_migrations.py`
  - Test `tests/workflow_core/test_schema_2_8.py:127-146`
  - Test `tests/workflow_core/test_lifecycle_cli.py:161-193`
  - Test `tests/workflow_core/test_setup_cli.py:70-338`
  - Test `tests/workflow_core/test_project_settings.py:80-107`
  - Test `tests/workflow_core/test_executables.py:75`
  - Test `tests/workflow_core/test_config_examples.py:26-58`
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** a config migration with a file deletion and its rollback, where the same update function already renames and rewrites that local file for older targets.
- **Interfaces produced**:
  - `migrations.CURRENT_VERSION = "2.11"`; `migrations._migrate_2_10_to_2_11(config: dict[str, Any]) -> dict[str, Any]`.
  - `configuration.RETIRED_KEYS_NOTICE: str`; `configuration.retired_keys(config: Mapping[str, Any]) -> list[str]`.
- **Steps**:
  1. Write failing tests in `tests/workflow_core/test_migrations.py` (class `MigrationTests`; import `retired_keys` and `RETIRED_KEYS_NOTICE` from `workflow_core.configuration`). Add next to `V29`:
     ```python
     V210 = {**V28, "schema_version": "2.10", "workflow_version": "2.10", "setup_cli_version": "2.10"}
     RETIRED = {
         "provider_mode": "multi",
         "orchestrator": {"roles": {"mobile": {"preferred": ["codex"]}, "backend": {"preferred": ["codex"]}},
                          "worker": {"timeout_seconds": 900}},
         "routing": {"roles": {"backend": {"preferred": ["main_harness"]}},
                     "review": {"independence": "provider", "max_cycles": 3}},
     }
     ```
     and the tests:
     ```python
     def test_version_key_orders_2_11_after_2_10(self):
         self.assertLess(version_key("2.10"), version_key("2.11"))

     def test_migrates_2_10_to_2_11_dropping_the_retired_keys(self):
         config = {**V210, **RETIRED}

         migrated = migrate_config(config, "2.11")

         for field in ("schema_version", "workflow_version", "setup_cli_version"):
             self.assertEqual("2.11", migrated[field])
         self.assertEqual([], retired_keys(migrated))
         self.assertEqual({"backend": {"preferred": ["main_harness"]}, "mobile": {"preferred": ["main_harness"]}},
                          migrated["routing"]["roles"])
         self.assertEqual({"max_cycles": 3}, migrated["routing"]["review"])
         self.assertIn("orchestrator", config)

     def test_2_10_to_2_11_removes_an_empty_review_and_adds_no_routing(self):
         only_review = migrate_config({**V210, "routing": {"review": {"independence": "session"}}}, "2.11")
         self.assertNotIn("routing", only_review)
         self.assertNotIn("routing", migrate_config(V210, "2.11"))

     def test_2_11_config_with_a_retired_key_is_rejected(self):
         migrated = migrate_config(V210, "2.11")
         cases = (("orchestrator", {"orchestrator": {}}), ("provider_mode", {"provider_mode": "single"}),
                  ("routing.review.independence", {"routing": {"review": {"independence": "session"}}}))
         for key, extra in cases:
             with self.subTest(key=key):
                 with self.assertRaises(ConfigValidationError) as raised:
                     validate_portable_config({**migrated, **extra})
                 self.assertIn(f"{key} was removed in schema 2.11", str(raised.exception))
                 self.assertIn("gin setup update --to-version 2.11 --approve", str(raised.exception))

     def test_update_to_2_11_backs_up_and_deletes_the_local_file(self):
         with tempfile.TemporaryDirectory() as directory:
             repository, workflow = _write_repository(directory, {**V210, **RETIRED}, {"providers": {}})
             local_before = (workflow / "orchestrator.local.yaml").read_bytes()

             result = setup_service.update(repository, target_version="2.11", approve=True)

             self.assertFalse((workflow / "orchestrator.local.yaml").exists())
             self.assertEqual(local_before, (Path(result["backup"]) / "orchestrator.local.yaml").read_bytes())
             self.assertIn("remove .agent-workflow/orchestrator.local.yaml", result["actions"])

     def test_rollback_restores_the_local_file_the_2_11_update_deleted(self):
         with tempfile.TemporaryDirectory() as directory:
             repository, workflow = _write_repository(directory, {**V210, **RETIRED}, {"providers": {}})
             local_before = (workflow / "orchestrator.local.yaml").read_bytes()
             config_before = (workflow / "config.yaml").read_bytes()

             result = setup_service.update(repository, target_version="2.11", approve=True)
             setup_service.rollback(repository, backup=Path(result["backup"]))

             self.assertEqual(local_before, (workflow / "orchestrator.local.yaml").read_bytes())
             self.assertEqual(config_before, (workflow / "config.yaml").read_bytes())

     def test_update_at_2_11_still_removes_a_leftover_local_file(self):
         with tempfile.TemporaryDirectory() as directory:
             repository, workflow = _write_repository(directory, migrate_config(V210, "2.11"), {"providers": {}})

             setup_service.update(repository, target_version="2.11", approve=True)

             self.assertFalse((workflow / "orchestrator.local.yaml").exists())

     def test_this_repository_config_migrates_to_2_11(self):
         yaml = setup_service.require_yaml()
         root = Path(__file__).resolve().parents[2]
         config = yaml.safe_load((root / ".agent-workflow/config.yaml").read_text(encoding="utf-8"))

         migrated = migrate_config(config, "2.11")

         validate_portable_config(migrated)
         self.assertEqual([], retired_keys(migrated))
     ```
     Add `test_doctor_reports_retired_keys_on_an_older_schema`, written like `test_doctor_reports_notifications_on_older_schema` (line 368): with `{**V210, **RETIRED}` the doctor actions contain `RETIRED_KEYS_NOTICE`; with `migrate_config(V210, "2.11")` they do not.
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_migrations.py -q`: the new tests fail (import error on `retired_keys`).
  3. `schemas.py:11-12`: `SUPPORTED_SCHEMA_VERSION = "2.11"` and append `"2.11"` to `SUPPORTED_CONFIG_VERSIONS`. Leave the `orchestrator`, `provider_mode`, and `independence` properties: configs below 2.11 may hold them.
  4. `migrations.py`: `CURRENT_VERSION = "2.11"`; after `_migrate_2_9_to_2_10` add
     ```python
     def _migrate_2_10_to_2_11(config: dict[str, Any]) -> dict[str, Any]:
         """The worker extension is retired: `orchestrator`, `provider_mode`, and `routing.review.independence` go."""
         migrated = copy.deepcopy(dict(config))
         orchestrator = migrated.pop("orchestrator", None)
         migrated.pop("provider_mode", None)
         routing = dict(migrated.get("routing") or {})
         roles = dict(routing.get("roles") or {})
         retired = orchestrator.get("roles") if isinstance(orchestrator, Mapping) else None
         for name in (retired if isinstance(retired, Mapping) else ()):
             roles.setdefault(str(name), {"preferred": ["main_harness"]})
         if roles:
             routing["roles"] = roles
         review = dict(routing.get("review") or {})
         review.pop("independence", None)
         if review:
             routing["review"] = review
         else:
             routing.pop("review", None)
         if routing:
             migrated["routing"] = routing
         else:
             migrated.pop("routing", None)
         for field in ("schema_version", "workflow_version", "setup_cli_version"):
             migrated[field] = "2.11"
         return migrated
     ```
     and register `("2.10", "2.11"): _migrate_2_10_to_2_11,` in `_MIGRATIONS`.
  5. `configuration.py`:
     - Lines 27-28: both constants become `"2.11"`.
     - After `legacy_worker_routing` add
       ```python
       RETIRED_KEYS_NOTICE = (
           "orchestrator, provider_mode, and routing.review.independence are ignored since gin 3.3.0; "
           "run gin setup update --to-version 2.11 --approve"
       )


       def retired_keys(config: Mapping[str, Any]) -> list[str]:
           """The keys schema 2.11 removed that `config` still holds, in a fixed order."""
           routing = config.get("routing")
           review = routing.get("review") if isinstance(routing, Mapping) else None
           found = [key for key in ("orchestrator", "provider_mode") if key in config]
           if isinstance(review, Mapping) and "independence" in review:
               found.append("routing.review.independence")
           return found
       ```
     - In `validate_portable_config`, after the `notifications` check (lines 192-200), add
       ```python
       if schema_version in SUPPORTED_CONFIG_VERSIONS and version_key(schema_version) >= version_key("2.11"):
           for key in retired_keys(config):
               raise ConfigValidationError(
                   f"{key} was removed in schema 2.11; run gin setup update --to-version 2.11 --approve"
               )
       ```
     - Lines 224-227: the message becomes `"worker routing (routing.concurrency, queue, worker, circuit_breaker, or a role naming a provider other than main_harness) was removed in schema 2.11; delete it from routing:"`. The docstring of `legacy_worker_routing` becomes ``"""Whether `routing:` still holds worker routing, which schema 2.8 moved out and schema 2.11 removed."""``.
  6. `setup_service.py`:
     - Import `RETIRED_KEYS_NOTICE` and `retired_keys` from `.configuration`. In `doctor`, after the `notifications` action (lines 483-486), add
       ```python
       if retired_keys(effective_cfg):
           backend_actions.append(RETIRED_KEYS_NOTICE)
       ```
     - In `update`, after the block that starts `if version_key(target_version) >= version_key("2.9") and local_source.is_file():` (lines 714-728), add
       ```python
       retire_local = version_key(target_version) >= version_key("2.11") and local_source.is_file()
       if retire_local:
           local_writes.pop(new_local, None)
           local_backup[local_source.name] = local_source.read_bytes()
           local_actions.append(f"remove {local_source.relative_to(main).as_posix()}")
       ```
     - Line 739: `if rename_local:` becomes `if rename_local and not retire_local:`.
     - Line 759: replace `if rename_local:` by
       ```python
       if retire_local:
           local_source.unlink()
           res.setdefault("actions", []).append(f"remove {local_source.relative_to(main).as_posix()}")
       elif rename_local:
       ```
       The existing body stays under `elif`. `rollback` already restores any backed-up local file (lines 787-791).
  7. `lifecycle_cli.py:590`: in the `warnings` tuple replace `orchestrator_client.warning(config.to_dict())` by `(RETIRED_KEYS_NOTICE if retired_keys(config.to_dict()) else None)`, importing both names from `.configuration`. Leave line 588 (`extensions`) and the `orchestrator_client` import: Track 4 removes them.
  8. `project.py:105-108`: delete `"provider_mode": "single",` and `"routing.review.independence": "session",` from `preset_assignments`. `executables.py:85`: the literal becomes `'schema_version: "2.11"'`.
  9. `examples/config.full.yaml`: lines 1-3 become `2.11`; delete line 5 (`provider_mode: multi`), line 64 (`independence: provider`), and the `orchestrator:` block (lines 71-100).
  10. Update the tests that assert the old behaviour:
      - `test_schema_2_8.py:127-128` and `:145-146`: both pairs become `self.assertIn("removed in schema 2.11", str(ctx.exception))`.
      - `test_lifecycle_cli.py:161-193`: replace `test_state_warns_in_multi_mode_without_orchestrator` by `test_state_warns_about_retired_keys_on_an_older_schema`: write `"schema_version: '2.10'\nprovider_mode: multi\n"` to `self.workflow_dir / "config.yaml"`, call `lifecycle_main(["state", "--repository", str(self.repo_path), "--format", "json"])` as the old test does, and assert `RETIRED_KEYS_NOTICE in data["warnings"]`; in text format assert `f"Warning: {RETIRED_KEYS_NOTICE}"` is printed; with `"schema_version: '2.11'\n"` the notice is absent.
      - `test_setup_cli.py:336-338`: the three versions become `"2.11"`. `test_setup_cli.py:70-83` and `test_project_settings.py:80-107`: remove the `provider_mode` and `routing.review.independence` assignments from the expected preset output (lines 78 and 80; 88, 91, 94, 106, 107).
      - `test_executables.py:75`: `'schema_version: "2.11"'`.
      - `test_config_examples.py:26-36`: remove the assertions on `portable["orchestrator"]`; `:57-58`: replace the two assertions by `self.assertEqual([], retired_keys(portable))`.
  11. Run `timeout 600 python3 -m pytest tests/workflow_core/test_migrations.py tests/workflow_core/test_schema_2_5.py tests/workflow_core/test_schema_2_6.py tests/workflow_core/test_schema_2_7.py tests/workflow_core/test_schema_2_8.py tests/workflow_core/test_configuration.py tests/workflow_core/test_setup_cli.py tests/workflow_core/test_project_settings.py tests/workflow_core/test_executables.py tests/workflow_core/test_config_examples.py tests/workflow_core/test_lifecycle_cli.py tests/workflow_core/test_routes_cli.py tests/workflow_core/test_reviewer.py -q`: passes.
  12. Commit: `feat(config)!: schema 2.11 removes orchestrator, provider_mode, and review independence (retire-orchestrator)`.
- **Acceptance criteria**: the "New tests" of the spec that concern the migration, the update and rollback of `orchestrator.local.yaml`, the 2.11 refusal, the doctor action, and the state warning pass; a 2.10 config holding the keys still loads.
- **Estimated complexity**: high

### Track 4: Core without the client and the facade
- **Dependencies**: Track 3
- **Files**:
  - Delete `plugins/gin-workflow/src/scripts/workflow_core/orchestrator_client.py`
  - Delete `plugins/gin-workflow/src/scripts/workflow_core/ext.py`
  - Delete `tests/workflow_core/test_orchestrator_client.py`, `tests/workflow_core/orchestrator_fakes.py`, `tests/workflow_core/test_ext.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/routes.py:10-150`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/reviewer.py:6-119`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py:31-930` (lines 31, 448, 610-623, 632-635, 918-924, 930)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/cli.py:23-122` (lines 23, 31, 63, 71, 117, 121)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:21-588`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/project.py:31-72`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/executables.py:14`
  - Test `tests/workflow_core/test_routes_cli.py:14-426`
  - Test `tests/workflow_core/test_reviewer.py:16-230`
  - Test `tests/workflow_core/test_lifecycle_cli.py:21-159`
  - Test `tests/workflow_core/test_setup_cli.py:20-970`
  - Test `tests/workflow_core/test_version_pin.py:19-285`
  - Test `tests/workflow_core/test_project_settings.py:14-35`
  - Test `tests/workflow_core/test_usage_cli.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** deletion of guarded branches at known line ranges in eight modules; no new behaviour beyond the two state tests.
- **Steps**:
  1. Tests first.
     - `test_lifecycle_cli.py`: replace `test_state_reports_extensions_orchestrator` (lines 118-159) by
       ```python
       def test_state_has_no_extensions_and_no_retired_project_keys(self):
           data = self._state_json()
           self.assertNotIn("extensions", data)
           self.assertNotIn("provider_mode", data["project"])
           self.assertNotIn("independence", data["project"])

       def test_state_reads_a_log_with_an_old_worker_event(self):
           event = WorkflowEvent.create(
               event_type="worker.failed", workflow_id="default-workflow", task_id="t-1",
               payload={"provider": "antigravity", "reason": "worker_routes_unavailable"},
           )
           WorkflowEventStore(self.workflow_dir / "runtime/events.jsonl").append(event)
           self.assertIn("gates", self._state_json())
       ```
       importing `WorkflowEvent` and `WorkflowEventStore` from `workflow_core.events`; use the events path the class's other tests use if it differs. Remove the `orchestrator_fakes` import (line 21).
     - `test_usage_cli.py`: add `test_report_reads_a_log_with_an_old_worker_event`, built like `test_report_json_and_text` (line 75), with the same `worker.failed` event appended to the fixture's `events.jsonl` before the report runs; the report exits 0.
     - `test_routes_cli.py`: remove the `orchestrator_fakes` import (line 14) and `provider_mode: single` from the configs in `setUp` (line 25) and line 117. Delete `_set_multi_mode` (207-220) and the tests `test_multi_mode_delegates_and_writes_the_returned_routes` (222-255), `test_delegation_forwards_model_and_effort` (256-286), `test_delegation_keeps_repo_in_the_manifest` (287-315), `test_multi_mode_diagnostics_from_orchestrator_exit_2_and_write_nothing` (316-340), `test_failing_orchestrator_falls_back_with_a_warning` (341-358), `test_malformed_orchestrator_reply_falls_back_with_a_warning` (375-388), `test_missing_routes_capability_falls_back` (389-400), `test_single_mode_never_calls_the_orchestrator` (401-426). Rename `test_role_owned_by_the_absent_orchestrator_routes_to_the_main_harness` (359-374) to `test_a_role_under_an_unmigrated_orchestrator_block_routes_to_the_main_harness`, write its config without the fake on `PATH`, and replace the `orchestrator_missing` assertion (line 373) by `self.assertEqual([], data["warnings"])`. In `test_paths_prints_the_library_dir` (198-205) assert `workflow_core/cli.py` instead of `workflow_core/ext.py`.
     - `test_reviewer.py`: remove the import (line 16) and the `provider_mode` parameter of the `config()` helper (23-32). Delete `test_provider_independence_without_orchestrator_warns` (145-149), `test_multi_mode_returns_orchestrator_routes` (173-181), `test_multi_mode_passes_the_implementer_route_to_the_orchestrator` (182-196), `test_empty_orchestrator_routes_exit_2` (197-204), `test_failing_orchestrator_reviews_on_the_main_harness_with_warning` (205-216), `test_malformed_orchestrator_reply_reviews_on_the_main_harness_with_warning` (217-230).
     - `test_setup_cli.py`: remove the import (line 20). Delete `test_doctor_probe_delegates_in_multi_mode` (914-928), `test_doctor_reports_orchestrator_missing_with_the_install_command` (929-941), `test_doctor_probe_failure_reports_orchestrator_failed` (942-953), `test_models_delegates_or_returns_an_empty_list` (954-970).
     - `test_version_pin.py`: remove the import (line 19). In `test_companions_found_on_path` (225-236) drop the fake orchestrator (lines 227, 230, 232) so the expected companions hold gin-qa only. Delete `test_orchestrator_is_found_through_executables_local_yaml` (276-285).
     - `test_project_settings.py:14-35`: remove the assertions that read `settings.provider_mode` and `settings.independence` (lines 17, 19-22, 28, 30, 35). Leave line 60: the schema still rejects an unknown `independence` value in a config below 2.11.
     - `git rm tests/workflow_core/test_orchestrator_client.py tests/workflow_core/orchestrator_fakes.py tests/workflow_core/test_ext.py`.
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_lifecycle_cli.py -q`: `test_state_has_no_extensions_and_no_retired_project_keys` fails; `test_state_reads_a_log_with_an_old_worker_event` passes (it guards `events.py`).
  3. `routes.py` `resolve`: delete lines 65-125 (the `if orchestrator_client.delegates(config_dict, "routes"):` branch and its `else`). Replace lines 139-150 (`orchestrator = ...` through the `for diag in raw_diagnostics:` loop) by `diagnostics.extend(validate_plan_assignments(tracks, config, harness))`. Remove `import tempfile` (line 10) and `orchestrator_client` from the import on line 29. `assignments.py:108-112` stays: it is what keeps a role under `orchestrator.roles` known for a config below 2.11.
  4. `reviewer.py`: delete lines 75-119 (the delegation branch, its `else`, and the `independence` block), so `actor_id = (` follows the `review_route(...)` call. Line 6 becomes `from collections.abc import Sequence`; line 17 becomes `from . import workspace`.
  5. `setup_service.py`: delete the `if effective.get("provider_mode") == "multi":` block (lines 610-623); lines 632-633 become `for name, version in ((version_pin.QA, version_pin.qa_version()),):`; delete `models` (lines 918-924) and its `COMMANDS` entry (line 930); remove the `probe` parameter of `doctor` (line 448) and the module import (line 31).
  6. `cli.py`: delete `ACTIONS["models"]` (line 23), the `--probe` argument (line 63), and the `--provider` argument (line 71); in `ACTIONS["doctor"]` (line 31) delete ` (--probe asks the orchestrator for provider health)`; delete the import on line 117; line 121 becomes `probed = ((version_pin.QA, version_pin.qa_version()),)`.
  7. `lifecycle_cli.py`: delete line 588 (`"extensions": ...`) and `orchestrator_client` from the import on line 21. `project.py`: delete the fields `provider_mode` (line 31) and `independence` (line 33) and their keyword arguments in `project_settings` (lines 70 and 72). `executables.py:14`: drop `"gin-orchestrator"` from `KNOWN_TOOLS`.
  8. `git rm plugins/gin-workflow/src/scripts/workflow_core/orchestrator_client.py plugins/gin-workflow/src/scripts/workflow_core/ext.py`, then `grep -rn "orchestrator_client\|workflow_core.ext\|from . import ext" plugins/gin-workflow/src/scripts tests`: no output.
  9. Run `timeout 900 python3 -m pytest -n auto -q`: no failures.
  10. Commit: `refactor(core)!: drop the orchestrator client and the ext facade; state JSON loses extensions (retire-orchestrator)`.
- **Acceptance criteria**: `gin state --format json` has no `extensions`, `project.provider_mode`, or `project.independence`; `gin setup models`, `--probe`, and `--provider` are gone; a 2.10 config whose track names a role only under `orchestrator.roles` resolves to the main harness with no warning from `gin routes resolve`; a log with an old `worker.failed` event is read by `gin state` and `gin usage report`; the suite passes.
- **Estimated complexity**: medium

### Track 5: Docs
- **Dependencies**: Track 4
- **Files**:
  - Delete `docs/orchestrator/README.md`, `docs/orchestrator/routing.md`, `docs/reference/orchestrator-contract.md`
  - Modify `mkdocs.yml:95-97`
  - Modify `docs/concepts/providers.md` (rewrite)
  - Modify `README.md:17-77` (lines 17, 18, 33, 67, 77)
  - Modify `AGENTS.md:12-15`
  - Modify `docs/concepts/architecture.md:25-172` (lines 25-26, 57, 126, 133-143, 151, 157, 163, 172)
  - Modify `docs/concepts/lifecycle.md:73-75`
  - Modify `docs/concepts/state-model.md:34-87` (lines 34, 61, 87)
  - Modify `docs/contributing.md:25-120` (lines 25-29, 39, 50-51, 58, 84, 103, 120)
  - Modify `docs/reference/cli.md:52-474` (lines 52-56, 66, 302-304, 315, 344, 462-474)
  - Modify `docs/reference/config.md:12-222` (lines 12-22, 36-48, 74, 137-142, the `orchestrator` section from 146, 167, 198-222)
  - Modify `docs/reference/troubleshooting.md:53-174` (lines 53, 76, 141-152, 174)
  - Modify `docs/reference/skills.md:3-91`, `docs/reference/skills.vi.md:3-91`
  - Modify `docs/getting-started.md:47`, `docs/getting-started.vi.md:47`
  - Modify `docs/starters/greenfield.md:45`, `docs/starters/greenfield.vi.md:45`
  - Modify `docs/guides/recommended-tools.md:46`, `docs/guides/recommended-tools.vi.md:46`
  - Modify `docs/guides/use-cases.md:39`, `docs/guides/use-cases.vi.md:39`
  - Modify `docs/guides/windows.md:142`, `docs/guides/windows.vi.md:142`
  - Modify `docs/guides/claude-workflow.md:20-29`, `docs/guides/claude-workflow.vi.md:20-29`
  - Modify `docs/guides/upgrading.md:30-70`, `docs/guides/upgrading.vi.md:30-70`
  - Modify `docs/changelog.md:3-5`
  - Test `tests/workflow_core/test_config_examples.py:61-80`
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one concept page is rewritten and about thirty pages in two languages are edited at known lines; link, README-map, and style rules are test-enforced.
- **Steps**:
  1. `tests/workflow_core/test_config_examples.py`, `test_readme_links_the_provider_guide_and_docs_cover_routing` (lines 61-80): stop reading `docs/orchestrator/README.md`; for `docs/concepts/providers.md` require `provider role`, `main harness`, and `privacy`; keep the `rollback` requirement on `docs/reference/config.md`. Add `self.assertFalse((ROOT / "docs/orchestrator").exists())`. Run `timeout 300 python3 -m pytest tests/workflow_core/test_config_examples.py -q`: fails.
  2. `git rm -r docs/orchestrator docs/reference/orchestrator-contract.md`. In `mkdocs.yml` delete the `not_in_nav` lines `/orchestrator/**` (95) and `/reference/orchestrator-contract.md` (97).
  3. Rewrite `docs/concepts/providers.md` with these sections: `# Providers` (gin runs every stage in the session's own harness, with no other tool); `## Capabilities` (the table without the worker dispatch row); `## Roles, models, and efforts` (a provider role names responsibility; every role resolves to the main harness; `Model:` and `Effort:` come from that harness's catalog); `## Independent review` (a fresh session or subagent of the same harness with a clean context and its own actor id, plus the per-harness table of spec section D); `## Evidence and identity`; `## Privacy`. Keep the two last sections' existing content where it does not name the extension.
  4. Edit the other pages at the lines in **Files**. In each: remove the sentence, table row, diagram node, or section that describes the extension, `provider_mode`, `routing.review.independence`, `orchestrator:`, `orchestrator.local.yaml`, `gin setup models`, `--probe`, `--provider`, or `extensions.orchestrator`; point any remaining link to a deleted page at `concepts/providers.md` or remove it. Specific content:
     - `README.md`: delete the Orchestrator row (17) and the orchestrator contract link (18); line 33 keeps the optional tools that gin itself uses; delete the add-on row (77).
     - `AGENTS.md:12`: the bullet ends after "the evidence policy"; line 15 drops the parenthesis about `plugins/gin-orchestrator/src/`.
     - `docs/concepts/architecture.md`: delete the `EXT` subgraph and its edges; the routing flowchart (133-143) becomes plan role, model, and effort to the main harness catalog to the manifest; line 172 says three plugins.
     - `docs/reference/cli.md`: delete the section `## Delegation to gin-orchestrator` (462-474); the `state` section (66) lists no `extensions`; the `reviewer` section (302-304) describes one route on the main harness.
     - `docs/reference/config.md`: line 40 says the current value is `2.11`; after the 2.10 paragraph (48) add one for 2.11 (the three keys go, role names under `orchestrator.roles` move to `routing.roles`, the update backs up and deletes `orchestrator.local.yaml`); delete the `provider_mode` row (74), the `independence` row (142), the section `### orchestrator` (from 146), and the section `## orchestrator.local.yaml` (198-215); the local-file examples (203, 222) say `2.11`.
     - `docs/reference/troubleshooting.md`: delete the section on `orchestrator_missing`, `orchestrator_contract_mismatch`, and `orchestrator_failed` (141-152); reword 53, 76, and 174 without the name.
     - `docs/reference/skills.md` and `.vi.md`: delete the `/gin-orchestrator:<name>` clause (3) and the section at 89-91.
     - `docs/guides/upgrading.md` and `.vi.md`: lines 30 and 40 name gin-qa and gin-ba only; add a last section `## What changes at 3.3` with the removed parts, the command `gin setup update --to-version 2.11 --approve`, and the per-harness table of spec section D. Line 3 is history and stays.
     - `docs/changelog.md`: line 3 lists the add-ons gin-qa and gin-ba; above the 3.2.0 entry add `## [3.3.0] - <the date this track is committed>` with a one-paragraph summary, `### Upgrade notes` (the extension is removed and the installer deletes an installed copy; run the update command per project; review is a fresh session of the same harness; on codex, opencode, and copilot `execute` runs in the session and `review` stops for the user; `gin setup models`, `--probe`, and `--provider` are gone; the docs pages under `/orchestrator/` are gone), and `### Changed` (config schema 2.11; `gin state --format json` without `extensions`, `project.provider_mode`, `project.independence`).
     - The `.vi.md` pages get the same change in Vietnamese at the same lines.
  5. Run `gin docs check` on every changed page (`gin docs check $(git diff --name-only --diff-filter=AM HEAD -- '*.md' | grep -v '^\.planning/')`): `ok`.
  6. Run `timeout 600 python3 -m pytest tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_config_examples.py tests/workflow_core/test_walkthrough_docs.py tests/workflow_core/test_rename_sweep.py tests/test_release_notes.py -q`: passes.
  7. Commit: `docs: gin runs in one harness; remove the orchestrator pages; 3.3.0 changelog and upgrade notes (retire-orchestrator)`.
- **Acceptance criteria**: no page links to a deleted page; every remaining docs page is in the README map; `gin docs check` is `ok`; the changelog has a 3.3.0 entry with upgrade notes; the upgrading guide has the 3.3 section in both languages.
- **Estimated complexity**: medium

### Track 6: Sweep test and version 3.3.0
- **Dependencies**: Track 5
- **Files**:
  - Create `tests/workflow_core/test_retired_extension_sweep.py`
  - Modify `plugins/gin-workflow/plugin.meta.json`, `plugins/gin-qa/plugin.meta.json`, `plugins/gin-ba/plugin.meta.json`, `install.sh:12-13`, `install.ps1:18-19` (and the other version locations `scripts/bump_version.py` writes)
- **Provider role**: `backend`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** one test file given in full and one script run.
- **Steps**:
  1. Create `tests/workflow_core/test_retired_extension_sweep.py`:
     ```python
     """gin-orchestrator was retired in gin 3.3.0: nothing shipped or documented names it."""

     from pathlib import Path
     import unittest

     ROOT = Path(__file__).resolve().parents[2]
     ROOTS = ("plugins", "scripts", ".claude-plugin", "docs", "README.md", "AGENTS.md", "mkdocs.yml")
     # History and upgrade notes keep the name. install.sh and install.ps1 are not swept:
     # they name the plugin to refuse and remove it, and the install smoke tests cover them.
     ALLOWED = {"docs/changelog.md", "docs/guides/upgrading.md", "docs/guides/upgrading.vi.md"}
     NAMES = ("gin-orchestrator", "gin_orchestrator")
     SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".toml", ".sh", ".ps1", ".txt", ".html", ""}


     def scanned():
         for name in ROOTS:
             root = ROOT / name
             for path in ([root] if root.is_file() else sorted(root.rglob("*"))):
                 rel = path.relative_to(ROOT).as_posix()
                 if (path.is_file() and path.suffix in SUFFIXES and rel not in ALLOWED
                         and not {"dist", "__pycache__", "fixtures"} & set(path.parts)):
                     yield rel, path.read_text(encoding="utf-8", errors="replace")


     class RetiredExtensionSweepTests(unittest.TestCase):
         def test_nothing_names_the_retired_extension(self):
             for rel, text in scanned():
                 with self.subTest(file=rel):
                     for number, line in enumerate(text.splitlines(), 1):
                         self.assertFalse(any(name in line for name in NAMES), f"{rel}:{number}: {line.strip()}")

         def test_the_extension_sources_are_gone(self):
             self.assertFalse((ROOT / "plugins/gin-orchestrator/src").exists())
             self.assertFalse((ROOT / "plugins/gin-orchestrator/plugin.meta.json").exists())
             self.assertFalse((ROOT / "tests/gin_orchestrator").exists())
     ```
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_retired_extension_sweep.py -q`: passes. If it names a file, remove the mention there in the wording the Global Constraints give, and name the file in the commit message.
  3. Run `python3 scripts/bump_version.py 3.3.0`; it prints the files it changed.
  4. Run `timeout 300 python3 -m pytest tests/test_bump_version.py tests/test_version_pins.py tests/test_release_notes.py tests/workflow_core/test_version_pin.py -q`: passes.
  5. Commit: `chore(release): 3.3.0; sweep test for the retired extension (retire-orchestrator)`.
- **Acceptance criteria**: the sweep passes; every version location reads 3.3.0; the changelog section for 3.3.0 satisfies `tests/test_release_notes.py`.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/retire-orchestrator`
- **Merge strategy**: sequential
- After the merge into `master`: `rm -rf plugins/gin-orchestrator` in the main checkout (git leaves the untracked `dist/`), push, then `./install.sh` once the push has finished. That install removes the `gin-orchestrator` launcher, its Claude skills folder, and its `enabledPlugins` entry in `~/.claude/settings.json` on this machine.
- Follow-ups to file at orchestrate: re-plan `gin-workflow-nox6`; `gin-harness/AGENTS.md:11`; this repository's config to 2.11 by `/quick` after the install.

## Validation
- [ ] `timeout 900 python3 -m pytest -n auto -q` passes on `feat/retire-orchestrator` after Track 6
- [ ] `timeout 900 bash tests/install_smoke_test.sh` exits 0
- [ ] `gin docs check` prints `ok` for the changed pages
- [ ] `mkdocs build --strict` and the Windows smoke test pass on a manual run of `.github/workflows/test.yml` before the release tag
- [ ] After `./install.sh`, gin-console lists this repository with its gates (manual)

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- The Parent Bead stays open until the human-confirmed merge; track beads close when their tests and review pass.
- Line numbers are from `master` at `cb91e1c5`; a later track sees the numbers shifted by the earlier ones and locates code by the quoted names.

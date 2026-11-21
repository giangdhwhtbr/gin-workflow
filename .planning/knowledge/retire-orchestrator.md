# gin-orchestrator retired; one harness per session; schema 2.11

**Context**
Epic `gin-workflow-u5mt` (2026-11-21, spec `.planning/specs/2026-11-21-retire-orchestrator-design.md`, gin 3.3.0). The extension started worker processes on other harness CLIs. It was 8.8k of 32.3k lines of Python source with 12.2k lines of tests, core kept the facade `workflow_core/ext.py` stable for it, and in this repository 54 worker requests gave 20 completed workers while 252 of 281 routes already went to the main harness. Removing it does not make the suite faster: the slow tests are the `bd` ones (see [test-suite-speed](test-suite-speed.md)).

**Decision/Solution**
- gin-workflow runs every stage in the session's own harness. `plugins/gin-orchestrator/`, `workflow_core/orchestrator_client.py`, and `workflow_core/ext.py` are gone; `v3.2.0` is the archive. Work shared between harnesses is a later design in gin-harness and has no hook in gin-workflow.
- On `claude` and `antigravity`, tracks and reviews run in native subagents. On `codex`, `opencode`, and `copilot`, `execute` implements in the session and notes `in_session`, `review` stops for the user (self-review only with `allow_self_review_fallback`), and research and tech-doc work run in the session, until `gin-workflow-nox6` gives them native subagents.
- Config schema 2.11 follows the `notifications` precedent of 2.10 ([remove-telegram](remove-telegram.md)): `_migrate_2_10_to_2_11` drops `orchestrator`, `provider_mode`, and `routing.review.independence`, and moves role names found only under `orchestrator.roles` into `routing.roles` with `main_harness`; `validate_portable_config` refuses the keys at 2.11 or later; on an older schema they are ignored, `gin state` warns, and `gin setup doctor` lists one action (`configuration.RETIRED_KEYS_NOTICE`). `assignments.py` still counts names under `orchestrator.roles` as known roles, which keeps an unmigrated plan valid.
- `gin setup update --to-version 2.11 --approve` moves any tier models of the local file into the catalog, then backs up and deletes `.agent-workflow/orchestrator.local.yaml`, also when the config is already at 2.11 (a non-empty backup makes `apply_migration` run). `rollback` restores the file.
- `gin state --format json` has no `extensions`, `project.provider_mode`, or `project.independence`; `gin setup models`, `--probe`, and `--provider` are gone. gin-console reads none of them.
- `workflow_core/events.py` keeps `_TERMINAL_WORKER_EVENTS` although nothing emits `worker.*` events: the stored id of `worker.completed`, `worker.failed`, and `worker.cancelled` excludes the payload, and reading `events.jsonl` recomputes every id.
- The installers refuse `--plugin gin-orchestrator` and, on every install run, remove a launcher they installed and the plugin folders of the selected harnesses (`remove_retired_orchestrator`, `Remove-RetiredOrchestrator`).
- `tests/workflow_core/test_retired_extension_sweep.py` fails when a file under `plugins/`, `scripts/`, `.claude-plugin/`, `docs/`, or `README.md`, `AGENTS.md`, `mkdocs.yml` names the extension, except `docs/changelog.md` and the upgrading guides. The installers are not swept: they name the plugin to refuse and remove it.

**Consequences**
- A project that reviewed with `independence: provider` now reviews with a fresh session of the same harness.
- This repository's own config stays at 2.10 until gin 3.3.0 is installed (`gin-workflow-jqwb`): the installed CLI refuses a newer schema.
- Deleting a component's test directory can take coverage of surviving code with it. `tests/gin_orchestrator/` held `test_harness_packaging.py` (gin-workflow's own bundles for each harness, no reference to the extension) and, inside extension test files, pins of the review and dispatch skills, the assignment manifest write, and the unknown-implementer exit code. Six track reviews approved before ship found it; the files were restored under `tests/workflow_core/`. Before deleting a test directory, list the files that do not import the component and the tests that read files outside it.
- Tests outside `test_skill_routing.py` assert phrases of the skill text (`test_assignments.py` reads the execute skill), so a track that edits skill text runs the full suite, not only the targeted tests. [epic-kinds](epic-kinds.md) records the same lesson for packaged references.
- Raising `migrations.CURRENT_VERSION` changes the default target of `setup_service.update()` and the schema `setup init` writes. A test of an earlier migration step pins `target_version` or writes an older config.
- A test of old stored data uses a stored line, not the current writer: an event built with `WorkflowEvent.create` gets its id from the rule that checks it. `gin state` turns `EventPersistenceError` into the warning `event log unreadable` and still prints gates, so such a test asserts that warning is absent. A test that asserts only an exit code can be vacuous: corrupt the input once and see the test fail.
- A Bash heredoc whose text contains a recursive remove command is blocked by the gin safety hook even when the text is data; write the script to a file and run the file.
- `install.ps1` and `tests/install_smoke_test.ps1` were changed by reading only (no `pwsh` on the development machine); the Windows job of `.github/workflows/test.yml` is the check.

**References**
- Spec `.planning/specs/2026-11-21-retire-orchestrator-design.md`; plan `.planning/plans/2026-11-21-retire-orchestrator.md`
- `plugins/gin-workflow/src/scripts/workflow_core/{migrations,configuration,setup_service,routes,reviewer,events}.py`; `install.sh`, `install.ps1`; `docs/concepts/providers.md`, `docs/guides/upgrading.md`
- Tests: `tests/workflow_core/{test_migrations,test_retired_extension_sweep,test_harness_packaging,test_events}.py`, `tests/install_smoke_test.sh`
- Beads: `gin-workflow-u5mt`, `gin-workflow-u5mt.1` to `.6`; follow-ups `gin-workflow-jqwb`, `gin-workflow-bryf`, `gin-workflow-nox6`

**Scope**
gin-workflow core routing, review, config schema, installers, stage skills, and docs.

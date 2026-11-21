# Retire gin-orchestrator

Workflow: retire-orchestrator
Kind: technical
Status: confirmed by the user on 2026-11-21.

## Goal and scope

gin-workflow runs every stage inside the session's own harness. The gin-orchestrator extension, which starts worker processes on other harness CLIs, is removed from this repository and is not moved elsewhere. gin 3.3.0 ships without it.

Why (measured on `master` `cb91e1c5`, 2026-11-21):

- The extension is 8.8k of 32.3k lines of Python source (27%), with 12.2k lines of tests; 362 of 2722 tests cover it or its client in core. Core must also keep the facade `workflow_core/ext.py` stable for it; nothing else imports that facade.
- In this repository's `events.jsonl` since 2026-08-16, 54 worker requests gave 20 completed workers; 26 of 42 dispatched tasks never had a completed worker; 262 of 364 measured worker minutes ended failed or cancelled.
- 252 of 281 dispatched track routes already went to the main harness.
- It does not make the suite faster (414 s and 427 s with the extension's tests, 439 s without, same machine) and saves at most about 1.5k prompt tokens per lifecycle. Those are not goals of this change.

In scope:

- Delete the extension, its tests, and the core code that exists only to call it or to serve it.
- Config schema 2.11 without `orchestrator:`, `provider_mode`, and `routing.review.independence`, with a migration from 2.10.
- `gin state --format json` without `extensions`, `project.provider_mode`, and `project.independence`.
- Skills, installers, version tooling, and docs follow.

Out of scope:

- Native subagents on codex, opencode, and copilot (`gin-workflow-nox6`). After this change those harnesses keep the behaviour they have today without the extension; see D.
- Work shared between harnesses. A later design in gin-harness covers it and gets its own spec; this change leaves no hook for it in gin-workflow.
- The five main harnesses, their model catalogs (`catalog.py`), install targets, and per-harness bundles: unchanged.
- `gin routes resolve`, `gin routes dispatch`, the assignment manifest, the `route.dispatched` event, and `provider_role`, `Model:`, `Effort:` on tracks: unchanged.
- The word "orchestrator" as a role or actor name (`agents/*.md`, `review_ledger/bead_fsm.py`) and the `orchestrate` stage: unchanged.
- Faster tests. The slowest tests are the `bd` ones in `tests/workflow_core/test_team_beads.py`.
- Tagging `v3.3.0`. The epic ends at the merge into `master`; the release tag needs the user's go-ahead.

Follow-ups, each its own piece of work:

- Re-plan `gin-workflow-nox6`: its spec and plan on `feat/native-subagents` were written while the dispatch branch existed.
- `gin-harness/AGENTS.md:11` lists gin-orchestrator as an add-on (another repository).
- This repository's own `.agent-workflow/config.yaml` moves to 2.11 after gin 3.3.0 is installed, as a `/quick` change that runs `gin setup update --to-version 2.11 --approve`. The update needs the 3.3.0 CLI, and the installed 3.2.0 refuses a 2.11 config, so it cannot be a track of this epic. Until then this repository runs as an unmigrated project (B).

Assumptions:

- `v3.2.0` is the archive of the extension. No commit after that tag touches `plugins/gin-orchestrator/src` or `tests/gin_orchestrator`, so no extra tag is made.
- gin-console needs no change: nothing under `gin-console/backend/src` or `gin-console/frontend/src` reads `extensions`, `provider_mode`, `independence`, or `orchestrator`.

## Approach

### A. Extension and core code

Delete:

- `plugins/gin-orchestrator/` (tracked: `plugin.meta.json` and `src/`, which holds the `providers` skill; `dist/` is untracked build output) and its entry in `.claude-plugin/marketplace.json`.
- `plugins/gin-workflow/src/scripts/workflow_core/orchestrator_client.py` and `ext.py`.
- `tests/gin_orchestrator/`, `tests/workflow_core/test_orchestrator_client.py`, `tests/workflow_core/orchestrator_fakes.py`, `tests/workflow_core/test_ext.py`.

Edit in `workflow_core/`:

- `routes.py` `resolve`: remove the delegation branch and its warning. The main-harness path that follows it is the whole function.
- `reviewer.py`: remove the delegation branch and the `independence: provider` warning. The reviewer is a fresh session of the main harness, as it is today when the extension is absent.
- `setup_service.py`: remove the doctor `orchestrator` and `providers` probes and the `models` function; `gin setup models` is removed with it (only the extension's `providers` skill used it). The `--probe` and `--provider` options of `gin setup` go too: nothing else reads them.
- `cli.py`: `gin version` no longer lists gin-orchestrator among companions.
- `lifecycle_cli.py`, `project.py`: see C.
- `executables.py`: drop `gin-orchestrator` from `KNOWN_TOOLS`.
- `events.py` is unchanged. `_TERMINAL_WORKER_EVENTS` stays: reading `events.jsonl` recomputes each event's id, and the id of an old `worker.completed`, `worker.failed`, or `worker.cancelled` event was computed without its payload. Removing the set would make every log that holds such an event unreadable.
- `schemas.py`, `configuration.py`, `migrations.py`, `assignments.py`: see B.

Keep: `LOCAL_GITIGNORE_ENTRIES` and the local-file list in `bundles.py` still name `orchestrator.local.yaml`, so a file left in a project that has not run the update is never committed or bundled.

### B. Config schema 2.11

This follows the removal of `notifications` in schema 2.10.

- `SUPPORTED_CONFIG_VERSIONS` gains `"2.11"`. Versions 2.3 to 2.10 stay supported.
- `_migrate_2_10_to_2_11`:
  - removes `orchestrator` and `provider_mode`;
  - adds each role name found only under `orchestrator.roles` to `routing.roles` as `{"preferred": ["main_harness"]}`, so a plan that names the role still validates;
  - removes `routing.review.independence`, and `routing.review` when that leaves it empty.
- `gin setup update --to-version 2.11 --approve` also puts `.agent-workflow/orchestrator.local.yaml` in the update's backup and deletes it. `gin setup rollback` restores it, as it restores local files today.
- A config at 2.11 or later that holds `orchestrator`, `provider_mode`, or `routing.review.independence` is refused: `<key> was removed in schema 2.11; run gin setup update --to-version 2.11 --approve`. The JSON schema keeps accepting the three keys, because configs below 2.11 may still hold them.
- A config below 2.11 that still holds them keeps working: role names under `orchestrator.roles` still count as known roles and resolve to the main harness; everything else in the block, `provider_mode`, and `independence` are ignored. `gin setup doctor` lists one action and `gin state` one warning: `orchestrator, provider_mode, and routing.review.independence are ignored since gin 3.3.0; run gin setup update --to-version 2.11 --approve`. This takes the place of today's "install gin-orchestrator" warning.
- The `legacy_worker_routing` error (worker routing left under `routing:`) no longer says the keys belong under `orchestrator:`; it says worker routing was removed in schema 2.11.
- `examples/config.full.yaml` drops the three keys.
- `gin setup preset` no longer proposes `provider_mode` or `routing.review.independence`.
- The `schema_version` line written to `executables.local.yaml` becomes 2.11, as it became 2.10 with that schema.

### C. State JSON and CLI

- `gin state --format json`: remove the top-level `extensions` key, `project.provider_mode`, and `project.independence` (`ProjectSettings` loses both fields). `catalog`, `harness`, and the other `project` keys are unchanged.
- `gin reviewer` keeps its flags and output shape; `--implementer` stays.
- `docs/reference/cli.md` loses the delegation table and the `gin setup models` row.

### D. Skills

Every `gin-orchestrator dispatch` command and every sentence about the extension leaves the skills. `execute/references/worker-lifecycle.md` is deleted.

| Step | claude, antigravity | codex, opencode, copilot (until `gin-workflow-nox6`) |
|---|---|---|
| `execute` a track | native `gin:developer` subagent | implement in the session, note `in_session` on the bead |
| `review` | native `gin:code-reviewer` subagent | stop for the user; self-review only with `allow_self_review_fallback` |
| research in `discuss` and `plan`; scouts, writers, and reviewers in `tech-doc` | native subagent | one after another in the session |

- `review/SKILL.md`: independence is always a fresh session or subagent of the same harness with a clean context and its own actor id. The sentence about provider independence and the read of `project.independence` go.
- `setup/SKILL.md`: remove the pointer to `/gin-orchestrator:providers`.
- `parallel-agents/SKILL.md`: remove the clause about workers on other harnesses.

### E. Installers, build, version

- `install.sh` and `install.ps1`: `gin-orchestrator` leaves the `--plugin` values and `all`; `--plugin gin-orchestrator` fails with `gin-orchestrator was removed in gin 3.3.0`. The launcher install and `ORCH_LAUNCHER_VERSION` go.
- Every install run removes an installed `gin-orchestrator` launcher and its plugin or skill directories for each harness, the way old plugin names are removed at `install.sh:789-805`. A 3.2.0 extension left next to a 3.3.0 core would fail at import, because `workflow_core.ext` no longer exists.
- `scripts/bump_version.py`: drop `gin-orchestrator` from `PLUGINS` and the `ORCHESTRATOR_VERSION` and `ORCH_LAUNCHER_VERSION` locations. The release version is 3.3.0.

### F. Docs

- Delete `docs/orchestrator/README.md`, `docs/orchestrator/routing.md`, and `docs/reference/orchestrator-contract.md`. `mkdocs.yml` drops their two `not_in_nav` entries. The site has no redirect plugin and none is added, so the old URLs return 404; the pages were never in the navigation.
- Rewrite `docs/concepts/providers.md` for one harness per session.
- Remove the extension, the three config keys, and `orchestrator.local.yaml` from the other pages that mention them, and from the `.vi.md` version where a page has one: `README.md`, `AGENTS.md`, and under `docs/`: `concepts/architecture.md`, `concepts/lifecycle.md`, `concepts/state-model.md`, `contributing.md`, `getting-started.md`, `guides/claude-workflow.md`, `guides/recommended-tools.md`, `guides/use-cases.md`, `guides/windows.md`, `reference/cli.md`, `reference/config.md`, `reference/skills.md`, `reference/troubleshooting.md`, `starters/greenfield.md`.
- `docs/guides/upgrading.md` and `.vi.md` gain a 3.3 section: what was removed, the update command, and the table in D.
- `docs/changelog.md`: a 3.3.0 entry with upgrade notes, and the intro line no longer lists gin-orchestrator as an add-on.

## Risks and rollback

- A project that reviewed with `independence: provider` now reviews with a fresh session of the same harness. The doctor action, the `gin state` warning, and the upgrade notes say so; nothing restores cross-provider review.
- On codex, opencode, and copilot a project that used the extension loses delegated execution and review until `gin-workflow-nox6` ships. This is the behaviour those harnesses already have when the extension is not installed.
- A plan that names a role defined only under `orchestrator.roles` keeps validating, before and after the config update (B).
- An installed 3.2.0 extension next to a 3.3.0 core: the installer removes it (E). A copy installed outside the installer's known locations fails with an import error when started and affects nothing else, since core no longer calls it.
- Removing `extensions` from the state JSON: gin-console does not read it (assumption above); the check is in Testing.
- A link from outside to `/orchestrator/` or `/reference/orchestrator-contract/` on the docs site breaks.
- Rollback: revert the merge commit and reinstall 3.2.0 with `./install.sh --plugin all`. A project already at schema 2.11 runs `gin setup rollback --backup <dir>` first, which restores its 2.10 config and `orchestrator.local.yaml`.

## Testing

Removed with the code: `tests/gin_orchestrator/`, the three core test files in A, and `tests/workflow_core/test_import_boundary.py` (it guards the boundary to the extension's library). One file of that directory is kept: `test_harness_packaging.py` never named the extension; it tests gin-workflow's own bundles for each harness, so it moves to `tests/workflow_core/`.

Updated: `tests/install_smoke_test.sh`, `tests/install_smoke_test.ps1`, `tests/test_all.py`, `tests/gin_qa/test_packaging.py`, and in `tests/workflow_core/`: `test_skill_routing.py`, `test_rename_sweep.py`, `test_version_pin.py`, `test_routes_cli.py`, `test_reviewer.py`, `test_config_examples.py`, `test_lifecycle_cli.py`, `test_setup_cli.py`, `test_project_settings.py`, `test_schema_2_8.py`, `test_executables.py`, `test_migrations.py`.

New tests:

- Migration 2.10 to 2.11: the three keys are gone; a role only under `orchestrator.roles` is in `routing.roles` with `main_harness`; a role already in `routing.roles` is untouched; an empty `routing.review` is removed.
- `gin setup update --to-version 2.11 --approve` backs up and deletes `orchestrator.local.yaml`; `gin setup rollback` restores it.
- A 2.11 config holding each removed key is refused with the message in B.
- A 2.10 config with `provider_mode: multi` and an `orchestrator:` block: `gin routes resolve` routes every track to the main harness, including one whose role exists only under `orchestrator.roles`; `gin state` carries the one warning; `gin setup doctor` lists the one action.
- `gin state --format json` has no `extensions`, `project.provider_mode`, or `project.independence`.
- A line of a real `events.jsonl` written by gin 3.2.0, a `worker.failed` event with a payload: `WorkflowEventStore.read_all()` returns it, and `gin state` reports no unreadable event log. (`gin usage report` reads the log through the same store; a test of its exit code proved vacuous and was dropped.)
- `migrate_config` takes this repository's `.agent-workflow/config.yaml` to a 2.11 config that validates and holds none of the three keys.
- Sweep: the strings `gin-orchestrator` and `gin_orchestrator` appear nowhere under `plugins/`, `scripts/`, `.claude-plugin/`, `docs/`, or in `README.md`, `AGENTS.md`, `mkdocs.yml`, except `docs/changelog.md` and `docs/guides/upgrading*.md`. `install.sh` and `install.ps1` are not swept: they name the plugin to refuse and remove it, and the install smoke tests cover them.
- Install smoke: a prefix that holds a 3.2.0 `gin-orchestrator` launcher and plugin directory has neither after the install; `--plugin gin-orchestrator` exits non-zero with the message in E. `tests/install_smoke_test.ps1` gets the same cases; it runs on the Windows job of `test.yml` and the release workflow, not on this machine (no `pwsh`).

Done when:

1. `python3 -m pytest -n auto` passes.
2. `bash tests/install_smoke_test.sh` passes.
3. `gin docs check` prints `ok` for the changed pages, and `mkdocs build --strict` passes on CI (`mkdocs` is not installed on this machine).
4. After `./install.sh`, gin-console lists this repository with its gates (manual check; the console reads `gin-workflow state --format json`).

## Open Technical Questions

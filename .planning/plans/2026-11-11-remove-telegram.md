# Plan: Remove Telegram notifications and `gin notify`

Spec: .planning/specs/2026-11-11-remove-telegram-design.md
Workflow: remove-telegram

## Objective

No outbound notification remains: `gin notify`, `workflow_core/notify.py`, the `notifications` config section, the gin-orchestrator `notifications` provider role, and every skill and doc step that notifies are gone. Config schema 2.10 drops `notifications` through a registered migration; this repository's config is on 2.10. The full suite passes.

**Goal** (spec): gin-workflow and gin-orchestrator stop sending any outbound notification. The Telegram sender, the `gin notify` command, the `notifications` config section, and the gin-orchestrator `notifications` provider role are removed, and no skill or reference tells an agent to notify.

**Architecture**: removal plus one config schema step. gin-orchestrator's notification role goes first (it imports `workflow_core.ext.notify`); then the core removes `notify` and adds the 2.9 → 2.10 migration, following the 2.8 → 2.9 `model_tiers` precedent (migration drops the key, `configuration.py` rejects it on the new schema, `setup doctor` reports it on older ones). Version gates written as literal tuples (`("2.8", "2.9")`, `== "2.9"`) become "at least" comparisons so 2.10 keeps their behaviour.

**Tech Stack**: Python 3 standard library, PyYAML, jsonschema; unittest/pytest (`python3 -m pytest -n auto`).

**Global Constraints** (spec, verbatim):
- Out of scope: historical specs and plans under `.planning/` (left as written), gin-console (it reads no notification data), and any replacement notification channel.
- Breaking: `gin notify` disappears. Any external script calling it fails; the skills shipped here no longer call it.
- A 2.10 config with `notifications` is rejected; older configs keep loading and `doctor` points at the migration.
- The `2.10` version string must stay quoted in YAML (`"2.10"`); unquoted it parses as the float `2.1`.
- gin-console is unaffected: it parses no notification fields.

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
- Problem statement: the Telegram integration and `gin notify` are unused; they add a command, a config key, a provider role, credentials checks, and skill steps.
- Success criteria: spec requirements 1–7 and US-1 to US-3 hold as tests; `python3 -m pytest -n auto` passes.
- Constraints: Global Constraints above.
- Non-goals: a replacement channel; editing `.planning/` history.

## Approach Options
### Option 1: schema 2.10 with a migration (selected in `/discuss`)
- Summary: drop `notifications` from the schema, register 2.9 → 2.10, reject the key on 2.10, report it on older schemas.
- Pros: same pattern as `model_tiers`; no dead key in the schema.
- Cons: a version bump touches every literal version gate.

### Option 2: keep the key, ignore it
- Summary: schema still accepts `notifications`; doctor warns.
- Pros: no bump.
- Cons: a dead key stays forever; rejected in `/discuss`.

### Recommended Approach
- Selected option: Option 1, with the whole orchestrator role removed (both confirmed in `/discuss` on 2026-11-11).
- Rationale: matches the existing removal precedent and leaves no unused contract.

## Scope
- In scope: spec requirements 1–7.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 deletes the module Track 1's provider imports, and Track 3's docs test checks the result of both; one lane.
```

## Tasks

`S` is `plugins/gin-workflow/src/scripts/workflow_core`; `O` is `plugins/gin-orchestrator/src/scripts/gin_orchestrator`. Run tests from the repository root.

### Track 1: gin-orchestrator without a notifications role
- **Dependencies**: none
- **Files**:
  - Delete `plugins/gin-orchestrator/src/scripts/gin_orchestrator/notifications.py`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/contracts.py:757-766,921-925` (remove `NotificationRequest`, `NotificationReceipt`, `NotificationProvider`)
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/fakes.py:21-22,507-525` (remove `FakeNotificationProvider` and its imports)
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/worker_scheduler.py:13,99,113,220-241` (no `notifications` argument; `schedule` maps `self._run`)
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/registry.py:31,43,49,101,132,162,234-239,481,509,533` (no default, field, construction, metadata, or scheduler argument)
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/__init__.py:13-15,35,41,57,66-68,87` (drop the exports)
  - Test `tests/gin_orchestrator/test_contracts.py`, `tests/gin_orchestrator/test_registry.py`, `tests/gin_orchestrator/test_worker_scheduler.py`, `tests/gin_orchestrator/test_end_to_end.py`, `tests/gin_orchestrator/test_copilot_worker.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded removal inside one package with every touch point listed; no new logic beyond one compatibility test.
- **Interfaces**:
  - Removed: `NotificationRequest`, `NotificationReceipt`, `NotificationProvider`, `FakeNotificationProvider`, `TelegramNotificationProvider`, `ProviderRegistry.notifications`, `WorkerScheduler(..., notifications=...)`, `WorkerScheduler._run_and_notify`.
  - Unchanged: `ProviderRegistry.from_config(...)` signature; a config whose `providers` mapping still has `notifications` loads (the key is never read).
- **Steps**:
  1. Failing tests:
     - `tests/gin_orchestrator/test_registry.py`: replace the test asserting `registry.notifications` is a `FakeNotificationProvider` (around line 675) and the one asserting `TelegramNotificationProvider` (around line 719) with `test_leftover_notifications_provider_is_ignored`: build the registry from the same config as the former fake test (which sets `"notifications": "fake"`) and assert it loads, `not hasattr(registry, "notifications")`, and `"notifications" not in registry.metadata` (or the metadata mapping the old test read). Remove the `TelegramNotificationProvider` import (line 32) and `FakeNotificationProvider` (line 26); delete the `assertIs(registry.notifications, scheduler.notifications)` line (around 836).
     - Add to the package test (`tests/gin_orchestrator/test_contracts.py`): `test_no_notification_symbols_exported` asserting `not any("Notification" in name for name in gin_orchestrator.__all__)` and `not hasattr(gin_orchestrator, "TelegramNotificationProvider")`.
     Run `python3 -m pytest tests/gin_orchestrator/test_registry.py tests/gin_orchestrator/test_contracts.py -q` → the new tests fail.
  2. Production edits, in this order: delete `notifications.py`; remove the three types from `contracts.py`; remove `FakeNotificationProvider` and its two imports from `fakes.py`; in `worker_scheduler.py` remove the `NotificationRequest` import, the `notifications` parameter and attribute, and `_run_and_notify`, and change `executor.map(self._run_and_notify, selected)` to `executor.map(self._run, selected)` (`_run` keeps its single-argument signature returning `WorkerResult`); in `registry.py` remove `"notifications": "telegram"` from `_DEFAULTS`, the `notifications` field, the `_entry(config, "notifications")` line, the telegram/fake construction block, the positional `notifications` argument at construction, the `"notifications"` metadata entry, and `notifications=self.notifications`; in `__init__.py` remove the imports and `__all__` entries.
  3. Remaining tests: in `test_contracts.py` remove the `NotificationRequest`/`TelegramNotificationProvider`/`FakeNotificationProvider` imports, the notification half of `test_review_and_notification_providers_share_normalized_contract` (keep the review assertions and rename it `test_review_provider_normalized_contract`), the `FakeNotificationProvider` entry of the parametrised list (around 249-253), and the Telegram provider test (around 344-371). In `test_worker_scheduler.py` remove the two notification tests (around 170-190) and the `FakeNotificationProvider` import. In `test_registry.py`, `test_end_to_end.py`, `test_copilot_worker.py` remove every `"notifications": "fake"` entry and the `"providers.notifications=fake"` assignment (test_end_to_end.py:1039).
  4. `grep -rn "Notification\|notifications" plugins/gin-orchestrator tests/gin_orchestrator` → nothing. `python3 -m pytest tests/gin_orchestrator -q -n auto` → pass.
  5. Commit: `refactor(orchestrator): remove the notifications provider role (remove-telegram)`.
- **Acceptance criteria**: spec requirement 4; US-3; orchestrator suite passes.
- **Estimated complexity**: medium

### Track 2: core drops `gin notify`; config schema 2.10
- **Dependencies**: Track 1
- **Files**:
  - Delete `plugins/gin-workflow/src/scripts/workflow_core/notify.py`
  - Delete `tests/workflow_core/test_notify.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/cli.py:21,101-103` (no `notify`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/ext.py:30,81` (no `notify`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/schemas.py:10-11,260-264` (`"2.10"`; no `notifications`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/migrations.py:17,124-143` (`CURRENT_VERSION = "2.10"`, `version_key`, `_migrate_2_9_to_2_10`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/configuration.py:27-28,208-213` (`"2.10"`; rejection; version gates)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py:28,447-457,582-584,658,663,722` (no credentials check; `notifications` doctor action; version gates)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/executables.py:85` (`"2.10"`)
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/registry.py:211,217` (version tuples → `SUPPORTED_CONFIG_VERSIONS`)
  - Modify `plugins/gin-workflow/src/examples/config.full.yaml:1-3`, `plugins/gin-orchestrator/src/examples/orchestrator.local.example.yaml:1` (`"2.10"`)
  - Modify `.agent-workflow/config.yaml` (migrated to 2.10)
  - Test `tests/workflow_core/test_migrations.py`, `tests/workflow_core/test_schema_2_8.py:239-253`, `tests/workflow_core/test_setup_cli.py:941-963`, `tests/workflow_core/test_workspace_cli_resolution.py:93-101`, `tests/workflow_core/test_ext.py:41`, plus any test asserting the current version is `2.9`
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** a config migration and schema bump across core and orchestrator; literal version gates must keep their behaviour at 2.10 (the `models` move of the 2.9 migration must still run on a 2.8 → 2.10 update).
- **Interfaces**:
  - `migrations.version_key(version: str) -> tuple[int, ...]`: `tuple(int(part) for part in str(version).split("."))`; `version_key("2.10") > version_key("2.9")`.
  - `migrations.CURRENT_VERSION == "2.10"`; `_MIGRATIONS[("2.9", "2.10")] = _migrate_2_9_to_2_10`.
  - `schemas.SUPPORTED_SCHEMA_VERSION == "2.10"`; `SUPPORTED_CONFIG_VERSIONS` ends with `"2.10"`; `configuration.SUPPORTED_WORKFLOW_VERSION == SUPPORTED_SETUP_CLI_VERSION == "2.10"`.
  - `validate_portable_config` on schema 2.10 with `notifications` raises `ConfigValidationError("notifications was removed in schema 2.10; run gin setup update --to-version 2.10 --approve")`.
  - `gin setup doctor` on an older schema with `notifications` adds the action `"notifications is ignored since schema 2.10; run gin setup update --to-version 2.10 --approve"`.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_migrations.py` (add `V29 = {**V28, "schema_version": "2.9", "workflow_version": "2.9", "setup_cli_version": "2.9"}` next to `V28`):
     - `test_migrates_2_9_to_2_10_dropping_notifications`: `migrate_config({**V29, "notifications": {"telegram": True}, "routing": routing}, "2.10")` has all three version fields `"2.10"`, no `notifications`, the same `routing`, and the input still has `notifications`.
     - `test_2_10_config_with_notifications_is_rejected`: `validate_portable_config({**migrated_2_10, "notifications": {"telegram": True}})` raises `ConfigValidationError` whose message contains `"removed in schema 2.10"`.
     - `test_update_2_8_to_2_10_still_moves_local_tier_models`: copy the existing `test_update_to_2_9_...` approve test (around line 214) with `target_version="2.10"`; assert the `models` catalog entry is written and `schema_version == "2.10"`.
     - `test_doctor_reports_notifications_on_older_schema`: a repository with `{**V29, "notifications": {"telegram": True}}` (use `_write_repository`); `setup_service.doctor(...)` actions include `"notifications is ignored since schema 2.10"`.
     - `test_version_key_orders_2_10_after_2_9`.
     In `test_setup_cli.py` replace `test_doctor_warns_when_telegram_is_on_without_credentials` with `test_doctor_never_reports_telegram_credentials`: configure nothing, run doctor with and without `TELEGRAM_*` in the env, assert no action contains `telegram`.
     Run `python3 -m pytest tests/workflow_core/test_migrations.py tests/workflow_core/test_setup_cli.py -q -k "2_10 or notifications or telegram or version_key"` → fail.
  2. `migrations.py`: add `version_key`; set `CURRENT_VERSION = "2.10"`; add
     ```python
     def _migrate_2_9_to_2_10(config: dict[str, Any]) -> dict[str, Any]:
         """Outbound notifications are removed; `notifications` goes."""
         migrated = copy.deepcopy(dict(config))
         migrated.pop("notifications", None)
         for field in ("schema_version", "workflow_version", "setup_cli_version"):
             migrated[field] = "2.10"
         return migrated
     ```
     and register `("2.9", "2.10")`.
  3. `schemas.py`: `SUPPORTED_SCHEMA_VERSION = "2.10"`, append `"2.10"` to `SUPPORTED_CONFIG_VERSIONS`, delete the `notifications` property. `configuration.py`: both supported versions `"2.10"`; replace `== "2.9" and "model_tiers"` with `version_key(...) >= version_key("2.9") and "model_tiers"` and `in ("2.8", "2.9")` with `>= version_key("2.8")`; add after the `model_tiers` check: when `version_key(schema) >= version_key("2.10")` and `"notifications" in config`, raise the message from Interfaces (this check must run before jsonschema validation reports the unknown key, or replace that error; the test asserts the message). Import `version_key` without a cycle: define it in `schemas.py` and re-export it from `migrations.py` if `migrations` imports `configuration`.
  4. `setup_service.py`: remove the `credentials_warning` import and the `notifications`/`telegram` block (582-584); add after the `model_tiers` action (452) `if "notifications" in effective_cfg: backend_actions.append(<doctor message>)`; change `not in ("2.8", "2.9")` (447) to `version_key(...) < version_key("2.8")`, `target_version in ("2.8", "2.9")` (658) to `>= version_key("2.8")`, `target_version == "2.9"` (663) to `>= version_key("2.9")`, and `not in ("2.8", "2.9")` (722) to `< version_key("2.8")` (guard a missing `restored_version` as `"0"`).
  5. `cli.py`: remove `"notify"` from `TOP_COMMANDS` and the `notify` dispatch branch. `ext.py`: remove the import and `__all__` entry. Delete `notify.py` and `tests/workflow_core/test_notify.py`. `registry.py:211,217`: replace both literal tuples with `SUPPORTED_CONFIG_VERSIONS` (import it from `workflow_core.ext`). `executables.py:85`, `config.full.yaml`, `orchestrator.local.example.yaml`: `"2.10"`.
  6. Other tests: `test_ext.py` drop `"notify"`; `test_schema_2_8.py` delete `test_notifications_telegram_is_an_optional_boolean`; `test_workspace_cli_resolution.py` replace `test_notify_from_a_child_reads_the_parent_config` with `test_notify_is_not_a_command` (running `notify` from the child exits non-zero and stderr names an invalid choice or unknown command); in `test_configuration.py:218` swap `"notifications"` for another nested mapping the secret scan still sees (e.g. `"usage": {"api_key": "sk-literal"}` if that test only checks secret detection; keep the asserted error). Run `grep -rn '"2\.9"' tests | grep -i "current\|CURRENT\|SUPPORTED_SCHEMA"` and update any test asserting the current version.
  7. Migrate this repository's config: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.cli setup update --to-version 2.10 --approve` from the worktree root; check `.agent-workflow/config.yaml` has `schema_version: '2.10'` (quoted) and no `notifications`. Remove the backup it writes if it lands inside the worktree's tracked tree (`git status`).
  8. `python3 -m pytest -n auto` → pass (docs-only failures from Track 3 do not exist yet: `test_skill_routing.py` still finds the notify text; if it fails here, it is fixed in Track 3 and noted in the commit body).
  9. Commit: `feat(config)!: schema 2.10 removes notifications; drop gin notify (remove-telegram)`.
- **Acceptance criteria**: spec requirements 1, 2, 3, 7; US-1 (first two bullets); US-2.
- **Estimated complexity**: high

### Track 3: skills, references, and docs without notifications
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-workflow/src/references/stage-contract.md:14,17,30-31` (remove `## Notifications`; reword the two "notification" clauses)
  - Modify `plugins/gin-workflow/src/skills/execute/SKILL.md:34,36,43`
  - Modify `plugins/gin-workflow/src/skills/execute/references/worker-lifecycle.md:5`
  - Modify `plugins/gin-workflow/src/skills/review/SKILL.md:16,30`
  - Modify `plugins/gin-workflow/src/skills/workflow/SKILL.md:19`, `plugins/gin-workflow/src/skills/learn/SKILL.md:20`
  - Modify `docs/reference/cli.md:301-310` (remove `gin notify`), `docs/reference/config.md:39-45,89-97,186,205` (remove `notifications`; 2.10 paragraph; versions), `docs/concepts/providers.md:17`, `docs/contributing.md:99`
  - Test `tests/workflow_core/test_skill_routing.py:20`, `tests/workflow_core/test_docs_coverage.py:83-88`
- **Provider role**: `docs`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** mechanical text removals with exact locations, guarded by one grep test.
- **Steps**:
  1. Failing test: in `test_docs_coverage.py` replace `test_no_doc_mentions_telegram_sh` with `test_no_doc_or_skill_mentions_notifications` over the same `targets` plus `plugins/*/src/references/*.md`, flagging lines containing `telegram`, `gin notify`, `notify --event`, or `notifications.` (case-insensitive for `telegram`). In `test_skill_routing.py:20` change the assertion to `self.assertNotIn("notify --event", text)`. Run both files → fail.
  2. Edits:
     - `stage-contract.md`: delete the `## Notifications` heading and paragraph; line 14 ends "Never: self-assessment or summaries."; line 17 drops "A notification is never approval."
     - `execute/SKILL.md` 34: "If `routes dispatch` exits 3 (`over_budget`), leave the bead `in_progress` with a note and ask the user to raise `usage.budget_usd` or stop."; 36: "otherwise ask the user and leave the bead `in_progress` with a note."; 43: delete the sentence starting "If `gin state --workflow-id <id>` now shows".
     - `worker-lifecycle.md` 5: delete the sentence "On exit, `gin notify ...` (`worker_failed` on failure)."
     - `review/SKILL.md` 16: "Without a native subagent or `gin-orchestrator`, stop for the user"; 30: "Never manufacture approval."
     - `workflow/SKILL.md` 19: drop ", and never treat notifications as approval evidence"; `learn/SKILL.md` 20: drop "A notification never counts as reconciliation."
     - `cli.md`: delete the `## \`gin notify\`` section through its exit-codes line.
     - `config.md`: delete the `### \`notifications\`` section; set the current version to `2.10` at line 39 and in the two example blocks; after the 2.9 paragraphs add: "Schema 2.10 removes `notifications`: `gin setup update --to-version 2.10` drops the key and keeps every other key. A schema 2.10 configuration that sets `notifications` is rejected; on an older schema `gin setup doctor` reports it as ignored."
     - `providers.md`: delete the Notifications row. `contributing.md:99`: "no page mentions the removed worker-routing key of the old schema, `gin notify`, or Telegram."
  3. `python3 -m pytest tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_skill_routing.py -q` → pass; `gin docs check docs/reference/cli.md docs/reference/config.md docs/concepts/providers.md docs/contributing.md` → ok; `python3 -m pytest -n auto` → pass.
  4. Commit: `docs: remove notification steps and gin notify (remove-telegram)`.
- **Acceptance criteria**: spec requirements 5, 6; US-1 third bullet.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/remove-telegram`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes
- [ ] `grep -rniE "telegram|gin notify|notify --event" plugins docs` returns nothing
- [ ] `gin setup doctor` (after reinstall) reports no notification action on this repository
- [ ] `.agent-workflow/config.yaml` is on `"2.10"` without `notifications`

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- Deliverable merge-holds apply only to the Parent Bead; track beads close once tests and review pass.
- After merge, `install.sh` must run again before the main checkout's 2.10 config loads with the installed `gin`.

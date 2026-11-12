# Remove Telegram notifications and `gin notify`

Workflow: remove-telegram
Status: draft for user review.

## Goal and scope

gin-workflow and gin-orchestrator stop sending any outbound notification. The Telegram sender, the `gin notify` command, the `notifications` config section, and the gin-orchestrator `notifications` provider role are removed, and no skill or reference tells an agent to notify.

In scope: gin-workflow core (`workflow_core`), config schema and migrations, gin-orchestrator, plugin skills and references, docs under `docs/`, tests, and this repository's own `.agent-workflow/config.yaml`.

Out of scope: historical specs and plans under `.planning/` (left as written), gin-console (it reads no notification data), and any replacement notification channel.

## Requirements

1. `workflow_core/notify.py` is deleted. `gin notify` is no longer a command: it is removed from the CLI command list and dispatch in `cli.py`, and `notify` is no longer exported by `workflow_core.ext`.
2. `gin setup doctor` no longer checks `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` and never reports `telegram_credentials_missing`.
3. Config schema 2.10:
   - `SUPPORTED_CONFIG_VERSIONS` and the migrations `CURRENT_VERSION` add `"2.10"`; `schema_version`, `workflow_version`, and `setup_cli_version` move to `2.10`.
   - A registered migration `2.9 → 2.10` removes `notifications` and keeps every other key; `gin setup update --to-version 2.10 --approve` applies it with the usual validated backup.
   - The `notifications` property is removed from the config schema. A schema 2.10 configuration that sets `notifications` is rejected with a message saying it was removed in 2.10.
   - On an older schema, `gin setup doctor` reports that `notifications` is ignored and points to `gin setup update`.
4. gin-orchestrator:
   - `gin_orchestrator/notifications.py` (`TelegramNotificationProvider`) is deleted.
   - `NotificationRequest`, `NotificationReceipt`, and `NotificationProvider` are removed from `contracts.py`; `FakeNotificationProvider` is removed from `fakes.py`; none of them is exported from the package.
   - The registry no longer has a `notifications` default, field, or metadata entry. A leftover `providers.notifications` key in a config is ignored.
   - The worker scheduler takes no `notifications` argument and sends no `worker_finished` / `worker_failed` event.
5. Skills and references: the `## Notifications` section of `stage-contract.md` and every `gin notify` step in `execute/SKILL.md`, `execute/references/worker-lifecycle.md`, and `review/SKILL.md` are removed. Statements that a notification is never approval or evidence are removed or reworded where they no longer make sense.
6. Docs: the `gin notify` section of `docs/reference/cli.md`, the `notifications` section of `docs/reference/config.md`, and the Notifications row of `docs/concepts/providers.md` are removed; `config.md` gains a schema 2.10 paragraph describing the migration and rejection; current-version mentions say `2.10`.
7. This repository's `.agent-workflow/config.yaml` is migrated to 2.10 (no `notifications` key).

## User Stories

### US-1: No notification command or config
As a gin-workflow user, I want the Telegram integration gone, so that the workflow carries no unused delivery code, credentials, or settings.

Acceptance criteria:
- `gin notify --event needs_input x` fails as an unknown command.
- `gin setup doctor` output never contains `telegram_credentials_missing`, with or without `TELEGRAM_*` variables set.
- `grep -rn "gin notify\|notifications.telegram" plugins docs` returns nothing.

### US-2: Existing configs migrate cleanly
As a user whose config sets `notifications.telegram`, I want `gin setup update` to remove it, so that my config stays valid on the new schema.

Acceptance criteria:
- `gin setup update --to-version 2.10 --approve` on a 2.9 config with `notifications` writes a 2.10 config without `notifications`, keeps every other key, and writes a backup.
- Validating a 2.10 config that sets `notifications` fails with a message naming the removal in 2.10.
- `gin setup doctor` on a 2.9 config with `notifications` reports that the key is ignored.

### US-3: Orchestrator without a notification role
As a gin-orchestrator user, I want workers to run without a notification provider, so that dispatch never depends on an outbound channel.

Acceptance criteria:
- `gin_orchestrator` exports no `Notification*` or `TelegramNotificationProvider` symbol.
- A registry built from a config that still sets `providers.notifications: fake` loads without error and has no `notifications` attribute.
- The worker scheduler returns worker results with no notification call.

## Errors and compatibility

- Breaking: `gin notify` disappears. Any external script calling it fails; the skills shipped here no longer call it.
- A 2.10 config with `notifications` is rejected; older configs keep loading and `doctor` points at the migration.
- The `2.10` version string must stay quoted in YAML (`"2.10"`); unquoted it parses as the float `2.1`.
- gin-console is unaffected: it parses no notification fields.

## Testing

- Delete `tests/workflow_core/test_notify.py` and the Telegram tests in `test_setup_cli.py`, `test_workspace_cli_resolution.py`, `test_schema_2_8.py`, `test_contracts.py`, `test_registry.py`, and `test_worker_scheduler.py`; drop `"notifications": "fake"` from orchestrator test fixtures; update `test_ext.py` and `test_skill_routing.py`.
- Add tests: the 2.9 → 2.10 migration removes `notifications` and keeps other keys; a 2.10 config with `notifications` is rejected; `doctor` reports `notifications` on an older schema; a registry config with a leftover `providers.notifications` loads; a docs-coverage test asserts no doc or skill mentions `gin notify` or `notifications.telegram`.
- Full suite `python3 -m pytest -n auto` passes.

## Open Technical Questions

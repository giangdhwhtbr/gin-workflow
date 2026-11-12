# Outbound notifications removed; schema 2.10

**Context**
Epic `gin-workflow-remove-telegram` (2026-11-11, spec `.planning/specs/2026-11-11-remove-telegram-design.md`). The Telegram sender (`gin notify`, `notifications.telegram`) and the gin-orchestrator `notifications` provider role had no users.

**Decision/Solution**
- Nothing in gin-workflow or gin-orchestrator sends an outbound notification. `gin notify`, `workflow_core/notify.py`, `NotificationProvider`/`Request`/`Receipt`, `FakeNotificationProvider`, and `TelegramNotificationProvider` are gone; the worker scheduler maps `_run` directly. The registry never reads `providers.notifications`, so a leftover key loads.
- Config schema 2.10 follows the `model_tiers` precedent of 2.9: `_migrate_2_9_to_2_10` drops `notifications`; `validate_portable_config` rejects it on 2.10 or later before jsonschema runs, so its message surfaces; `setup doctor` reports it as ignored on older schemas.
- Version gates compare with `schemas.version_key` (re-exported by `migrations`), never with literal tuples such as `("2.8", "2.9")`: a literal gate silently changes behaviour at the next version (the 2.9 tier-models move would have been skipped on a 2.8 to 2.10 update). Guard `version_key` with membership in `SUPPORTED_CONFIG_VERSIONS` wherever the version comes from a file (rollback reads it from backup metadata), because it raises on a non-numeric string.

**Consequences**
- A schema bump cannot be committed together with the repository's own config migration: the pre-commit hook runs the installed `gin`, which rejects the new version. Merge, run `./install.sh`, then run `gin setup update --to-version <new> --approve` in the main checkout and commit the config.
- Skills no longer tell agents to notify before waiting for the user; `tests/workflow_core/test_docs_coverage.py` fails on any page, skill, or reference that mentions Telegram, `gin notify`, `notify --event`, or a `notifications.<key>`.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{schemas,migrations,configuration,setup_service}.py`, `plugins/gin-orchestrator/src/scripts/gin_orchestrator/{registry,worker_scheduler}.py`, `docs/reference/config.md`
- Beads: `gin-workflow-remove-telegram.1` to `.3`

**Scope**
gin-workflow core config, gin-orchestrator providers, stage skills.

from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.migrations import (  # noqa: E402
    MigrationError,
    apply_migration,
    migrate_config,
    rollback_migration,
)
from workflow_core import setup_service  # noqa: E402


V28 = {"schema_version": "2.8", "workflow_version": "2.8", "setup_cli_version": "2.8", "harness": "claude"}
LOCAL_WITH_MODELS = {
    "schema_version": "2.8",
    "providers": {
        "codex": {
            "executable": "codex",
            "models": {
                "low": {"model": "m1", "effort": "low"},
                "medium": {"model": "m1", "effort": "medium"},
                "high": {"model": "m2", "effort": "high"},
            },
        },
        "antigravity": {"executable": "agy", "models": {"low": "a", "medium": "b", "high": "b"}},
    },
}


def _write_repository(directory, config, local=None, local_name="orchestrator.local.yaml"):
    repository = Path(directory)
    workflow = repository / ".agent-workflow"
    workflow.mkdir()
    yaml = setup_service.require_yaml()
    (workflow / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    if local is not None:
        (workflow / local_name).write_text(yaml.safe_dump(local), encoding="utf-8")
    return repository, workflow


class MigrationTests(unittest.TestCase):
    def test_unknown_same_version_fails_closed_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            config = workflow / "config.yaml"
            original = "schema_version: '9.9'\nworkflow_version: '9.9'\nsetup_cli_version: '9.9'\n"
            config.write_text(original, encoding="utf-8")

            with self.assertRaisesRegex(MigrationError, "unsupported migration target"):
                apply_migration(repository, target_version="9.9")

            self.assertEqual(original, config.read_text(encoding="utf-8"))
            self.assertFalse((workflow / "backups").exists())

    def test_migrates_2_2_to_2_3_with_validated_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / '.agent-workflow'
            workflow.mkdir()
            config = workflow / 'config.yaml'
            original = b"""schema_version: '2.2'
workflow_version: '2.2'
setup_cli_version: '2.2'
harness: codex
"""
            config.write_bytes(original)

            result = apply_migration(repository, target_version='2.3')

            self.assertEqual('migrated', result['status'])
            self.assertEqual('2.2', result['from_version'])
            self.assertEqual('2.3', result['to_version'])
            backup = Path(result['backup'])
            self.assertEqual(original, (backup / 'config.yaml').read_bytes())
            migrated = config.read_text(encoding='utf-8')
            self.assertIn("schema_version: '2.3'", migrated)
            self.assertIn("workflow_version: '2.3'", migrated)
            self.assertIn("setup_cli_version: '2.3'", migrated)

    def test_2_2_to_2_3_dry_run_leaves_repository_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / '.agent-workflow'
            workflow.mkdir()
            config = workflow / 'config.yaml'
            original = b"""schema_version: '2.2'
workflow_version: '2.2'
setup_cli_version: '2.2'
"""
            config.write_bytes(original)

            result = apply_migration(repository, target_version='2.3', dry_run=True)

            self.assertEqual('migration_available', result['status'])
            self.assertEqual(original, config.read_bytes())
            self.assertFalse((workflow / 'backups').exists())

    def test_migrates_2_1_to_2_2_without_inventing_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            config = workflow / "config.yaml"
            config.write_text(
                "schema_version: '2.1'\nworkflow_version: '2.1'\nsetup_cli_version: '2.1'\nharness: codex\n",
                encoding="utf-8",
            )

            result = apply_migration(repository, target_version="2.2")

            self.assertEqual("migrated", result["status"])
            migrated = config.read_text(encoding="utf-8")
            self.assertIn("schema_version: '2.2'", migrated)
            self.assertNotIn("routing:", migrated)

    def test_update_backs_up_then_migrates_and_explicit_rollback_restores(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            config = workflow / "config.yaml"
            original = b"schema_version: '2.1'\nworkflow_version: '2.1'\nsetup_cli_version: '2.1'\nharness: codex\n"
            config.write_bytes(original)

            result = apply_migration(repository, target_version="2.2")

            self.assertEqual("migrated", result["status"])
            self.assertEqual("2.1", result["from_version"])
            self.assertEqual("2.2", result["to_version"])
            backup = Path(result["backup"])
            self.assertTrue(backup.is_relative_to(workflow / "backups"))
            self.assertEqual(original, (backup / "config.yaml").read_bytes())
            self.assertIn("schema_version: '2.2'", config.read_text(encoding="utf-8"))

            restored = rollback_migration(repository, backup)

            self.assertEqual("rolled_back", restored["status"])
            self.assertEqual(original, config.read_bytes())

    def test_rollback_rejects_target_outside_backup_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (workflow / "config.yaml").write_text("schema_version: '2.1'\n", encoding="utf-8")
            outside = repository / "untrusted-backup"
            outside.mkdir()
            (outside / "config.yaml").write_text("schema_version: '2.0'\n", encoding="utf-8")

            with self.assertRaisesRegex(MigrationError, "inside .agent-workflow/backups"):
                rollback_migration(repository, outside)

            self.assertEqual(
                "schema_version: '2.1'\n",
                (workflow / "config.yaml").read_text(encoding="utf-8"),
            )

    def test_dry_run_migration_neither_writes_config_nor_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            config = workflow / "config.yaml"
            original = b"schema_version: '2.1'\nworkflow_version: '2.1'\nsetup_cli_version: '2.1'\nharness: codex\n"
            config.write_bytes(original)

            result = apply_migration(repository, target_version="2.2", dry_run=True)

            self.assertEqual("migration_available", result["status"])
            self.assertEqual(original, config.read_bytes())
            self.assertFalse((workflow / "backups").exists())


    def test_migrates_2_8_to_2_9_dropping_model_tiers_and_keeping_routing(self):
        routing = {"roles": {"backend": {"preferred": ["main_harness"]}}, "review": {"max_cycles": 3}}
        config = {**V28, "model_tiers": {"plan": "high_reasoning"}, "routing": routing}

        migrated = migrate_config(config, "2.9")

        for field in ("schema_version", "workflow_version", "setup_cli_version"):
            self.assertEqual("2.9", migrated[field])
        self.assertNotIn("model_tiers", migrated)
        self.assertEqual(routing, migrated["routing"])
        self.assertIn("model_tiers", config)

    def test_update_to_2_9_previews_catalog_entries_from_local_tiers_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, workflow = _write_repository(directory, V28, LOCAL_WITH_MODELS)
            config_before = (workflow / "config.yaml").read_bytes()
            local_before = (workflow / "orchestrator.local.yaml").read_bytes()

            preview = setup_service.update(repository, target_version="2.9", approve=False)

            self.assertEqual(["m1", "m2"], preview["configuration"]["models"]["codex"]["models"])
            self.assertEqual(["a", "b"], preview["configuration"]["models"]["antigravity"]["models"])
            self.assertTrue(any("orchestrator.local.yaml" in action for action in preview["actions"]))
            self.assertEqual(config_before, (workflow / "config.yaml").read_bytes())
            self.assertEqual(local_before, (workflow / "orchestrator.local.yaml").read_bytes())
            self.assertFalse((workflow / "backups").exists())

    def test_update_to_2_9_moves_local_tier_models_into_the_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, workflow = _write_repository(directory, V28, LOCAL_WITH_MODELS)
            yaml = setup_service.require_yaml()

            result = setup_service.update(repository, target_version="2.9", approve=True)

            self.assertEqual("migrated", result["status"])
            self.assertTrue(Path(result["backup"]).is_dir())
            config = yaml.safe_load((workflow / "config.yaml").read_text(encoding="utf-8"))
            self.assertEqual("2.9", config["schema_version"])
            self.assertEqual({"codex": {"models": ["m1", "m2"]}, "antigravity": {"models": ["a", "b"]}}, config["models"])
            local = yaml.safe_load((workflow / "orchestrator.local.yaml").read_text(encoding="utf-8"))
            self.assertEqual({"codex": {"executable": "codex"}, "antigravity": {"executable": "agy"}}, local["providers"])

    def test_update_to_2_9_keeps_an_existing_catalog_entry_and_still_clears_local_models(self):
        with tempfile.TemporaryDirectory() as directory:
            config = {**V28, "models": {"codex": {"models": ["kept"]}}}
            repository, workflow = _write_repository(directory, config, LOCAL_WITH_MODELS)
            yaml = setup_service.require_yaml()

            setup_service.update(repository, target_version="2.9", approve=True)

            written = yaml.safe_load((workflow / "config.yaml").read_text(encoding="utf-8"))
            self.assertEqual(["kept"], written["models"]["codex"]["models"])
            self.assertEqual(["a", "b"], written["models"]["antigravity"]["models"])
            local = yaml.safe_load((workflow / "orchestrator.local.yaml").read_text(encoding="utf-8"))
            self.assertNotIn("models", local["providers"]["codex"])

    def test_doctor_reports_model_tiers_and_local_provider_models(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, _ = _write_repository(directory, {**V28, "model_tiers": {"plan": "high_reasoning"}})
            actions = setup_service.doctor(repository)["actions"]
            self.assertTrue(any("model_tiers" in action and "models:" in action for action in actions), actions)

        with tempfile.TemporaryDirectory() as directory:
            repository, _ = _write_repository(directory, V28, LOCAL_WITH_MODELS)
            actions = setup_service.doctor(repository)["actions"]
            self.assertTrue(
                any("gin-workflow setup update --to-version 2.9 --approve" in action for action in actions), actions
            )

    def test_default_update_from_2_7_renames_the_local_file_and_moves_its_tier_models(self):
        with tempfile.TemporaryDirectory() as directory:
            config = {**V28, "schema_version": "2.7", "workflow_version": "2.7", "setup_cli_version": "2.7"}
            repository, workflow = _write_repository(directory, config, LOCAL_WITH_MODELS, "providers.local.yaml")
            yaml = setup_service.require_yaml()

            setup_service.update(repository, approve=True)

            self.assertFalse((workflow / "providers.local.yaml").exists())
            local = yaml.safe_load((workflow / "orchestrator.local.yaml").read_text(encoding="utf-8"))
            self.assertEqual({"codex": {"executable": "codex"}, "antigravity": {"executable": "agy"}}, local["providers"])
            written = yaml.safe_load((workflow / "config.yaml").read_text(encoding="utf-8"))
            self.assertEqual(["m1", "m2"], written["models"]["codex"]["models"])
            self.assertEqual(["a", "b"], written["models"]["antigravity"]["models"])

    def test_update_at_2_9_still_moves_leftover_local_tier_models(self):
        with tempfile.TemporaryDirectory() as directory:
            config = {**V28, "schema_version": "2.9", "workflow_version": "2.9", "setup_cli_version": "2.9"}
            repository, workflow = _write_repository(directory, config, LOCAL_WITH_MODELS)
            yaml = setup_service.require_yaml()

            result = setup_service.update(repository, target_version="2.9", approve=True)

            self.assertNotEqual("up_to_date", result["status"])
            self.assertTrue(Path(result["backup"]).is_dir())
            written = yaml.safe_load((workflow / "config.yaml").read_text(encoding="utf-8"))
            self.assertEqual(["m1", "m2"], written["models"]["codex"]["models"])
            local = yaml.safe_load((workflow / "orchestrator.local.yaml").read_text(encoding="utf-8"))
            self.assertNotIn("models", local["providers"]["codex"])
            actions = setup_service.doctor(repository)["actions"]
            self.assertFalse(any("--to-version 2.9 --approve" in action for action in actions), actions)

    def test_rollback_restores_the_local_file_the_2_9_update_rewrote(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, workflow = _write_repository(directory, V28, LOCAL_WITH_MODELS)
            local_before = (workflow / "orchestrator.local.yaml").read_bytes()
            config_before = (workflow / "config.yaml").read_bytes()

            result = setup_service.update(repository, target_version="2.9", approve=True)
            setup_service.rollback(repository, backup=Path(result["backup"]))

            self.assertEqual(local_before, (workflow / "orchestrator.local.yaml").read_bytes())
            self.assertEqual(config_before, (workflow / "config.yaml").read_bytes())


if __name__ == "__main__":
    unittest.main()

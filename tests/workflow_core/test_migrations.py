from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.migrations import (  # noqa: E402
    MigrationError,
    apply_migration,
    rollback_migration,
)


class MigrationTests(unittest.TestCase):
    def test_update_backs_up_then_migrates_and_explicit_rollback_restores(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            config = workflow / "config.yaml"
            original = b"schema_version: '2.0'\nworkflow_version: '2.0'\npolicy:\n  safe: true\n"
            config.write_bytes(original)

            result = apply_migration(repository, target_version="2.1")

            self.assertEqual("migrated", result["status"])
            self.assertEqual("2.0", result["from_version"])
            self.assertEqual("2.1", result["to_version"])
            backup = Path(result["backup"])
            self.assertTrue(backup.is_relative_to(workflow / "backups"))
            self.assertEqual(original, (backup / "config.yaml").read_bytes())
            self.assertIn("schema_version: '2.1'", config.read_text(encoding="utf-8"))

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
            original = b"schema_version: '2.0'\n"
            config.write_bytes(original)

            result = apply_migration(repository, target_version="2.1", dry_run=True)

            self.assertEqual("migration_available", result["status"])
            self.assertEqual(original, config.read_bytes())
            self.assertFalse((workflow / "backups").exists())


if __name__ == "__main__":
    unittest.main()

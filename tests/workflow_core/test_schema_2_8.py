"""Schema 2.8: worker routing moves under orchestrator: and single-harness defaults."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.configuration import ConfigValidationError, validate_portable_config  # noqa: E402
from workflow_core.migrations import CURRENT_VERSION, migrate_config  # noqa: E402
from workflow_core.schemas import SUPPORTED_CONFIG_VERSIONS  # noqa: E402
from workflow_core import setup_service  # noqa: E402

LAUNCHER = SCRIPTS / "gin-workflow"

LEGACY = {
    "schema_version": "2.7",
    "workflow_version": "2.7",
    "setup_cli_version": "2.7",
    "harness": "claude",
    "routing": {
        "concurrency": {"claude": 2, "codex": 1},
        "queue": {"max_wait_seconds": 600},
        "worker": {"max_retries": 2},
        "circuit_breaker": {"failure_threshold": 3},
        "review": {"max_cycles": 3, "role": "review"},
        "roles": {
            "backend": {
                "preferred": ["main_harness"],
                "by_tier": {"high": ["codex"]},
                "fallback": ["main_harness"],
            },
            "review": {"preferred": ["main_harness"]},
        },
    },
}


class TestSchema28(unittest.TestCase):
    def test_migration_moves_worker_routing_under_orchestrator(self):
        migrated = migrate_config(LEGACY, "2.8")

        # orchestrator holds concurrency, queue, worker, circuit_breaker, and roles.backend equal to original
        orchestrator = migrated.get("orchestrator", {})
        self.assertEqual(LEGACY["routing"]["concurrency"], orchestrator.get("concurrency"))
        self.assertEqual(LEGACY["routing"]["queue"], orchestrator.get("queue"))
        self.assertEqual(LEGACY["routing"]["worker"], orchestrator.get("worker"))
        self.assertEqual(LEGACY["routing"]["circuit_breaker"], orchestrator.get("circuit_breaker"))
        self.assertEqual(LEGACY["routing"]["roles"]["backend"], orchestrator.get("roles", {}).get("backend"))

        # routing.roles.backend == {"preferred": ["main_harness"]}
        self.assertEqual({"preferred": ["main_harness"]}, migrated["routing"]["roles"]["backend"])
        # routing.roles.review is unchanged
        self.assertEqual({"preferred": ["main_harness"]}, migrated["routing"]["roles"]["review"])

        # routing has no worker keys
        for key in ("concurrency", "queue", "worker", "circuit_breaker"):
            self.assertNotIn(key, migrated["routing"])

        # providers.task_tracking == "beads", provider_mode == "multi", routing.review.independence == "provider"
        self.assertEqual("beads", migrated.get("providers", {}).get("task_tracking"))
        self.assertEqual("multi", migrated.get("provider_mode"))
        self.assertEqual("provider", migrated["routing"]["review"]["independence"])

        # all three version fields are 2.8
        for field in ("schema_version", "workflow_version", "setup_cli_version"):
            self.assertEqual("2.8", migrated[field])

    def test_migration_keeps_explicit_values(self):
        explicit = copy.deepcopy(LEGACY)
        explicit["providers"] = {"task_tracking": "markdown"}
        explicit["provider_mode"] = "single"
        explicit["routing"]["review"]["independence"] = "session"

        migrated = migrate_config(explicit, "2.8")
        self.assertEqual("markdown", migrated["providers"]["task_tracking"])
        self.assertEqual("single", migrated["provider_mode"])
        self.assertEqual("session", migrated["routing"]["review"]["independence"])

    def test_migration_without_workers_adds_only_the_backend(self):
        simple = {
            "schema_version": "2.7",
            "workflow_version": "2.7",
            "setup_cli_version": "2.7",
            "harness": "claude",
            "routing": {
                "roles": {
                    "backend": {"preferred": ["main_harness"]},
                    "review": {"preferred": ["main_harness"]},
                },
                "review": {"role": "review"},
            },
        }
        migrated = migrate_config(simple, "2.8")
        self.assertNotIn("orchestrator", migrated)
        self.assertNotIn("provider_mode", migrated)
        self.assertEqual("beads", migrated.get("providers", {}).get("task_tracking"))

    def test_migration_is_idempotent(self):
        first = migrate_config(LEGACY, "2.8")
        second = migrate_config(first, "2.8")
        self.assertEqual(first, second)

    def test_2_8_rejects_worker_keys_under_routing(self):
        config = {
            "schema_version": "2.8",
            "workflow_version": "2.8",
            "setup_cli_version": "2.8",
            "harness": "claude",
            "routing": {
                "concurrency": {"claude": 2},
                "roles": {"backend": {"preferred": ["main_harness"]}},
            },
        }
        with self.assertRaises(ConfigValidationError) as ctx:
            validate_portable_config(config)
        self.assertIn("orchestrator:", str(ctx.exception))
        self.assertIn("setup update --to-version 2.8", str(ctx.exception))

    def test_2_8_rejects_a_routing_role_naming_a_provider(self):
        config = {
            "schema_version": "2.8",
            "workflow_version": "2.8",
            "setup_cli_version": "2.8",
            "harness": "claude",
            "routing": {
                "roles": {
                    "backend": {"preferred": ["codex"]},
                },
            },
        }
        with self.assertRaises(ConfigValidationError) as ctx:
            validate_portable_config(config)
        self.assertIn("orchestrator:", str(ctx.exception))
        self.assertIn("setup update --to-version 2.8", str(ctx.exception))

    def test_orchestrator_section_is_not_validated(self):
        config = {
            "schema_version": "2.8",
            "workflow_version": "2.8",
            "setup_cli_version": "2.8",
            "harness": "claude",
            "orchestrator": {"anything": [1, {"x": "y"}]},
        }
        validate_portable_config(config)

    def test_migration_rejects_a_malformed_source_config(self):
        malformed = copy.deepcopy(LEGACY)
        malformed["routing"]["roles"]["backend"] = "codex"
        with self.assertRaises(ConfigValidationError):
            migrate_config(malformed, "2.8")

    def test_update_renames_the_local_file_and_rollback_restores_it(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            workflow = repo / ".agent-workflow"
            workflow.mkdir(parents=True)
            yaml = setup_service.require_yaml()

            # Write a 2.7 config
            config_content = yaml.safe_dump(LEGACY, sort_keys=True)
            (workflow / "config.yaml").write_text(config_content, encoding="utf-8")

            # Write providers.local.yaml
            local_bytes = b"schema_version: '2.7'\nproviders:\n  claude:\n    executable: claude\n"
            (workflow / "providers.local.yaml").write_bytes(local_bytes)

            preview = setup_service.update(repo, target_version="2.8", dry_run=True)
            self.assertIn("rename .agent-workflow/providers.local.yaml to orchestrator.local.yaml", preview["actions"])
            self.assertTrue((workflow / "providers.local.yaml").is_file())

            # Run setup update --to-version 2.8 --approve
            res = setup_service.update(repo, target_version="2.8", approve=True)
            self.assertEqual("migrated", res["status"])

            # orchestrator.local.yaml exists with same bytes
            new_local = workflow / "orchestrator.local.yaml"
            self.assertTrue(new_local.is_file())
            self.assertEqual(local_bytes, new_local.read_bytes())
            self.assertFalse((workflow / "providers.local.yaml").exists())

            # .agent-workflow/.gitignore lists orchestrator.local.yaml
            gitignore = workflow / ".gitignore"
            self.assertTrue(gitignore.is_file())
            gitignore_text = gitignore.read_text(encoding="utf-8")
            self.assertIn("orchestrator.local.yaml", gitignore_text)

            # setup rollback --backup <backup> restores providers.local.yaml and 2.7 config
            backup = Path(res["backup"])
            preview = setup_service.rollback(repo, backup=backup, dry_run=True)
            self.assertIn("rename .agent-workflow/orchestrator.local.yaml to providers.local.yaml", preview["actions"])
            self.assertTrue(new_local.is_file())
            roll = setup_service.rollback(repo, backup=backup)
            self.assertEqual("rolled_back", roll["status"])
            self.assertEqual("2.7", roll["restored_version"])

            restored_local = workflow / "providers.local.yaml"
            self.assertTrue(restored_local.is_file())
            self.assertEqual(local_bytes, restored_local.read_bytes())
            self.assertFalse(new_local.exists())

            # 2.7 config restored
            restored_config = yaml.safe_load((workflow / "config.yaml").read_text(encoding="utf-8"))
            self.assertEqual("2.7", restored_config["schema_version"])


if __name__ == "__main__":
    unittest.main()

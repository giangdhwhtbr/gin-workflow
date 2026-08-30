import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "plugins/gin-workflow/src/scripts/gin-workflow"
sys.path.insert(0, str(ROOT / "plugins/gin-workflow/src/scripts"))

from workflow_core import setup_service  # noqa: E402


class SetupCliTests(unittest.TestCase):
    def test_reports_current_setup_cli_version(self):
        result = subprocess.run(
            [sys.executable, str(LAUNCHER), "--version"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("gin-workflow 2.3", result.stdout.strip())

    def run_cli(self, repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(LAUNCHER), "setup", *arguments, "--repository", str(repository), "--format", "json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_init_creates_documented_layout_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)

            first = self.run_cli(repository, "init", "--approve", "--non-interactive")
            self.assertEqual(0, first.returncode, first.stderr)
            self.assertEqual("initialized", json.loads(first.stdout)["status"])

            workflow = repository / ".agent-workflow"
            expected = (
                workflow / "config.yaml",
                workflow / "generated/effective-config.yaml",
                workflow / "generated/config-provenance.yaml",
                workflow / "backups",
                workflow / "references",
                workflow / "runtime/evidence",
            )
            for path in expected:
                self.assertTrue(path.exists(), path)

            config_before = (workflow / "config.yaml").read_bytes()
            generated_before = (workflow / "generated/effective-config.yaml").read_bytes()
            second = self.run_cli(repository, "init", "--non-interactive")

            self.assertEqual(0, second.returncode, second.stderr)
            self.assertEqual("already_initialized", json.loads(second.stdout)["status"])
            self.assertEqual(config_before, (workflow / "config.yaml").read_bytes())
            self.assertEqual(generated_before, (workflow / "generated/effective-config.yaml").read_bytes())

    def test_init_dry_run_previews_machine_local_provider_assignments_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)

            result = self.run_cli(
                repository,
                "init",
                "--dry-run",
                "--provider-set",
                "providers.claude.executable=claude",
                "--provider-set",
                "providers.claude.models.low=haiku",
                "--provider-set",
                "providers.claude.models.medium=sonnet",
                "--provider-set",
                "providers.claude.models.high=opus",
                "--non-interactive",
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("opus", payload["provider_configuration"]["providers"]["claude"]["models"]["high"])
            self.assertFalse((repository / ".agent-workflow").exists())

    def test_init_applies_approved_configuration_atomically_in_one_call(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)

            result = self.run_cli(
                repository,
                "init",
                "--harness",
                "codex",
                "--set",
                "policy.mode=guarded",
                "--approve",
                "--non-interactive",
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("initialized", json.loads(result.stdout)["status"])
            config = (repository / ".agent-workflow/config.yaml").read_text(encoding="utf-8")
            generated = (
                repository / ".agent-workflow/generated/effective-config.yaml"
            ).read_text(encoding="utf-8")
            self.assertIn("harness: codex", config)
            self.assertIn("mode: guarded", config)
            self.assertIn("mode: guarded", generated)

    def test_init_stages_all_configuration_files_before_mutating_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            with mock.patch.object(
                setup_service,
                "atomic_write_many",
                side_effect=OSError("staging failed"),
                create=True,
            ):
                with self.assertRaisesRegex(OSError, "staging failed"):
                    setup_service.initialize(repository, approve=True)

            self.assertFalse((repository / ".agent-workflow").exists())

    def test_init_repairs_interrupted_setup_with_config_but_no_generated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (workflow / "config.yaml").write_text(
                "schema_version: '2.3'\n"
                "workflow_version: '2.3'\n"
                "setup_cli_version: '2.3'\n",
                encoding="utf-8",
            )

            preview = self.run_cli(
                repository, "init", "--dry-run", "--non-interactive"
            )

            self.assertEqual(0, preview.returncode, preview.stderr)
            self.assertEqual("would_repair", json.loads(preview.stdout)["status"])
            self.assertFalse(
                (workflow / "generated/effective-config.yaml").exists()
            )

            denied = self.run_cli(repository, "init", "--non-interactive")

            self.assertNotEqual(0, denied.returncode)
            self.assertEqual("approval_required", json.loads(denied.stdout)["status"])
            self.assertFalse(
                (workflow / "generated/effective-config.yaml").exists()
            )

            result = self.run_cli(
                repository, "init", "--approve", "--non-interactive"
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("repaired", json.loads(result.stdout)["status"])
            self.assertTrue(
                (workflow / "generated/effective-config.yaml").is_file()
            )
            self.assertTrue(
                (workflow / "generated/config-provenance.yaml").is_file()
            )

    def test_init_requires_approval_before_any_first_time_write(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)

            result = self.run_cli(repository, "init", "--non-interactive")

            self.assertNotEqual(0, result.returncode)
            self.assertEqual("approval_required", json.loads(result.stdout)["status"])
            self.assertFalse((repository / ".agent-workflow").exists())

    def test_init_rejects_unapproved_configuration_without_partial_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)

            result = self.run_cli(
                repository,
                "init",
                "--set",
                "policy.mode=guarded",
                "--non-interactive",
            )

            self.assertNotEqual(0, result.returncode)
            self.assertEqual("approval_required", json.loads(result.stdout)["status"])
            self.assertFalse((repository / ".agent-workflow").exists())

    def test_init_dry_run_reports_exact_actions_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)

            result = self.run_cli(repository, "init", "--dry-run", "--non-interactive")

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("would_initialize", payload["status"])
            self.assertEqual(
                [
                    "create .agent-workflow/config.yaml",
                    "create .agent-workflow/backups/",
                    "create .agent-workflow/references/",
                    "create .agent-workflow/runtime/evidence/",
                    "generate .agent-workflow/generated/effective-config.yaml",
                    "generate .agent-workflow/generated/config-provenance.yaml",
                ],
                payload["actions"],
            )
            self.assertFalse((repository / ".agent-workflow").exists())

    def test_init_dry_run_returns_complete_proposed_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)

            result = self.run_cli(
                repository,
                "init",
                "--dry-run",
                "--harness",
                "codex",
                "--set",
                "policy.mode=guarded",
                "--non-interactive",
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("configuration", payload)
            self.assertEqual(
                {
                    "harness": "codex",
                    "policy": {"mode": "guarded"},
                    "schema_version": "2.3",
                    "setup_cli_version": "2.3",
                    "workflow_version": "2.3",
                },
                payload["configuration"],
            )
            self.assertFalse((repository / ".agent-workflow").exists())

    def test_configure_requires_explicit_approval_before_user_authored_write(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            initialized = self.run_cli(
                repository, "init", "--approve", "--non-interactive"
            )
            self.assertEqual(0, initialized.returncode, initialized.stderr)
            config = repository / ".agent-workflow/config.yaml"
            before = config.read_bytes()

            denied = self.run_cli(
                repository,
                "configure",
                "--set",
                "policy.mode=guarded",
                "--non-interactive",
            )

            self.assertNotEqual(0, denied.returncode)
            self.assertEqual("approval_required", json.loads(denied.stdout)["status"])
            self.assertEqual(before, config.read_bytes())

            approved = self.run_cli(
                repository,
                "configure",
                "--set",
                "policy.mode=guarded",
                "--approve",
                "--non-interactive",
            )
            self.assertEqual(0, approved.returncode, approved.stderr)
            self.assertEqual("configured", json.loads(approved.stdout)["status"])
            self.assertIn("mode: guarded", config.read_text(encoding="utf-8"))

    def test_configure_previews_then_writes_machine_local_provider_config(self):
        assignments = (
            "--provider-set", "providers.claude.executable=claude",
            "--provider-set", "providers.claude.models.low=haiku",
            "--provider-set", "providers.claude.models.medium=sonnet",
            "--provider-set", "providers.claude.models.high=opus",
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            initialized = self.run_cli(repository, "init", "--approve", "--non-interactive")
            self.assertEqual(0, initialized.returncode, initialized.stderr)

            preview = self.run_cli(repository, "configure", "--dry-run", *assignments)

            self.assertEqual(0, preview.returncode, preview.stderr)
            payload = json.loads(preview.stdout)
            self.assertEqual("would_configure", payload["status"])
            self.assertEqual("opus", payload["provider_configuration"]["providers"]["claude"]["models"]["high"])
            self.assertFalse((repository / ".agent-workflow/providers.local.yaml").exists())

            applied = self.run_cli(repository, "configure", "--approve", *assignments)

            self.assertEqual(0, applied.returncode, applied.stderr)
            local = (repository / ".agent-workflow/providers.local.yaml").read_text(encoding="utf-8")
            self.assertIn("high: opus", local)
            self.assertEqual("providers.local.yaml\n", (repository / ".agent-workflow/.gitignore").read_text(encoding="utf-8"))

    def test_provider_configuration_preserves_existing_workflow_gitignore_entries(self):
        assignments = (
            "--provider-set", "providers.claude.executable=claude",
            "--provider-set", "providers.claude.models.low=haiku",
            "--provider-set", "providers.claude.models.medium=sonnet",
            "--provider-set", "providers.claude.models.high=opus",
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            initialized = self.run_cli(repository, "init", "--approve", "--non-interactive")
            self.assertEqual(0, initialized.returncode, initialized.stderr)
            ignored = repository / ".agent-workflow/.gitignore"
            ignored.write_text("runtime/private.log\n# user rule\n", encoding="utf-8")

            applied = self.run_cli(repository, "configure", "--approve", *assignments)

            self.assertEqual(0, applied.returncode, applied.stderr)
            self.assertEqual(
                "runtime/private.log\n# user rule\nproviders.local.yaml\n",
                ignored.read_text(encoding="utf-8"),
            )

    def test_update_previews_then_applies_v2_3_routing_and_local_provider_config(self):
        arguments = (
            "--set", "routing.concurrency.claude=1",
            "--set", "routing.roles.backend.preferred=[claude]",
            "--provider-set", "providers.claude.executable=claude",
            "--provider-set", "providers.claude.models.low=haiku",
            "--provider-set", "providers.claude.models.medium=sonnet",
            "--provider-set", "providers.claude.models.high=opus",
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (workflow / "config.yaml").write_text(
                "schema_version: '2.2'\nworkflow_version: '2.2'\nsetup_cli_version: '2.2'\nharness: codex\n",
                encoding="utf-8",
            )

            preview = self.run_cli(repository, "update", "--dry-run", *arguments)

            self.assertEqual(0, preview.returncode, preview.stderr)
            payload = json.loads(preview.stdout)
            self.assertEqual("migration_available", payload["status"])
            self.assertIn("configuration", payload)
            self.assertIn("provider_configuration", payload)
            self.assertEqual("2.3", payload["configuration"]["schema_version"])
            self.assertEqual("opus", payload["provider_configuration"]["providers"]["claude"]["models"]["high"])
            self.assertFalse((workflow / "providers.local.yaml").exists())

            applied = self.run_cli(repository, "update", "--approve", *arguments)

            self.assertEqual(0, applied.returncode, applied.stderr)
            self.assertEqual("migrated", json.loads(applied.stdout)["status"])
            self.assertIn("routing:", (workflow / "config.yaml").read_text(encoding="utf-8"))
            self.assertIn("high: opus", (workflow / "providers.local.yaml").read_text(encoding="utf-8"))
            effective = (workflow / "generated/effective-config.yaml").read_text(encoding="utf-8")
            provenance = (workflow / "generated/config-provenance.yaml").read_text(encoding="utf-8")
            self.assertIn("schema_version: '2.3'", effective)
            self.assertIn("routing:", effective)
            self.assertIn("schema_version: '2.3'", provenance)

    def test_read_only_commands_do_not_change_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            initialized = self.run_cli(
                repository, "init", "--approve", "--non-interactive"
            )
            self.assertEqual(0, initialized.returncode, initialized.stderr)
            before = {
                path.relative_to(repository): path.read_bytes()
                for path in repository.rglob("*")
                if path.is_file()
            }

            for command in ("detect", "doctor", "status", "diff"):
                with self.subTest(command=command):
                    result = self.run_cli(repository, command, "--non-interactive")
                    self.assertEqual(0, result.returncode, result.stderr)
                    json.loads(result.stdout)

            after = {
                path.relative_to(repository): path.read_bytes()
                for path in repository.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)

    def test_harness_override_command_and_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            initialized = self.run_cli(repository, "init", "--approve", "--non-interactive")
            self.assertEqual(0, initialized.returncode, initialized.stderr)

            # Set override to claude
            set_res = self.run_cli(repository, "harness-override", "--harness", "claude")
            self.assertEqual(0, set_res.returncode, set_res.stderr)
            payload = json.loads(set_res.stdout)
            self.assertEqual("success", payload["status"])
            self.assertEqual("claude", payload["harness"])

            override_file = repository / ".agent-workflow" / "runtime" / "session-harness.override"
            self.assertTrue(override_file.is_file())
            self.assertEqual("claude", override_file.read_text().strip())

            # Query current override
            get_res = self.run_cli(repository, "harness-override")
            self.assertEqual(0, get_res.returncode, get_res.stderr)
            get_payload = json.loads(get_res.stdout)
            self.assertEqual("claude", get_payload["harness"])

            # Reset override
            reset_res = self.run_cli(repository, "harness-override", "--reset")
            self.assertEqual(0, reset_res.returncode, reset_res.stderr)
            reset_payload = json.loads(reset_res.stdout)
            self.assertEqual("success", reset_payload["status"])
            self.assertFalse(override_file.exists())


if __name__ == "__main__":
    unittest.main()


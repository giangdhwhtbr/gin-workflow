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
                "schema_version: '2.1'\n"
                "workflow_version: '2.1'\n"
                "setup_cli_version: '2.1'\n",
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
                    "schema_version": "2.1",
                    "setup_cli_version": "2.1",
                    "workflow_version": "2.1",
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

    def test_configure_normalizes_malformed_repository_yaml_as_structured_json(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            config = workflow / "config.yaml"
            malformed = b"schema_version: '2.1'\npolicy: [\n"
            config.write_bytes(malformed)

            result = self.run_cli(
                repository,
                "configure",
                "--set",
                "policy.mode=guarded",
                "--approve",
                "--non-interactive",
            )

            self.assertNotEqual(0, result.returncode)
            self.assertNotIn("Traceback", result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("error", payload["status"])
            self.assertIn("invalid YAML", payload["message"])
            self.assertEqual(malformed, config.read_bytes())


if __name__ == "__main__":
    unittest.main()

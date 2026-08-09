import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "plugins/gin-workflow/src/scripts/gin-workflow"


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

            first = self.run_cli(repository, "init", "--non-interactive")
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

    def test_configure_requires_explicit_approval_before_user_authored_write(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            initialized = self.run_cli(repository, "init", "--non-interactive")
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
            initialized = self.run_cli(repository, "init", "--non-interactive")
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

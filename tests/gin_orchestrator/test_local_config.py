from pathlib import Path
import tempfile
import unittest

from tests.gin_orchestrator import paths  # noqa: F401

from workflow_core.ext import ProviderLocalConfigError  # noqa: E402
from gin_orchestrator.local_config import (  # noqa: E402
    LOCAL_FILE,
    load_local_config,
    validate_local_config,
)


class LocalConfigTests(unittest.TestCase):
    def test_loads_complete_machine_local_provider_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (repository / LOCAL_FILE).write_text(
                "schema_version: '2.9'\n"
                "providers:\n"
                "  claude:\n"
                "    executable: claude\n",
                encoding="utf-8",
            )

            providers = load_local_config(repository)

        self.assertEqual("claude", providers["claude"].executable)
        self.assertEqual("claude", providers["claude"].provider)

    def test_load_local_config_reads_from_main_checkout_when_inside_worktree(self):
        import subprocess

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve() / "repo"
            repository.mkdir()
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repository, check=True)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (repository / LOCAL_FILE).write_text(
                "schema_version: '2.9'\n"
                "providers:\n"
                "  claude:\n"
                "    executable: claude\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "."], cwd=repository, check=True)
            subprocess.run(
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"],
                cwd=repository,
                check=True,
            )
            tree = repository / ".planning/worktrees/wt1"
            subprocess.run(["git", "worktree", "add", "-q", "-b", "feat/wt1", str(tree)], cwd=repository, check=True)

            providers = load_local_config(tree)
            self.assertEqual("claude", providers["claude"].executable)

    def test_rejects_models_field_with_migration_hint(self):
        with self.assertRaisesRegex(
            ProviderLocalConfigError,
            "orchestrator.local.yaml models moved to models: in config.yaml; run gin-workflow setup update --to-version 2.9 --approve",
        ):
            validate_local_config(
                {
                    "schema_version": "2.9",
                    "providers": {
                        "claude": {
                            "executable": "claude",
                            "models": {"low": "haiku", "medium": "sonnet"},
                        }
                    },
                }
            )

    def test_rejects_unknown_or_secret_like_fields(self):
        with self.assertRaisesRegex(ProviderLocalConfigError, "unsupported provider fields"):
            validate_local_config(
                {
                    "schema_version": "2.9",
                    "providers": {
                        "claude": {
                            "executable": "claude",
                            "api_key": "sk-local-secret",
                        }
                    },
                }
            )

    def test_rejects_missing_executable(self):
        with self.assertRaisesRegex(ProviderLocalConfigError, "requires executable"):
            validate_local_config(
                {
                    "schema_version": "2.9",
                    "providers": {
                        "claude": {},
                    },
                }
            )

    def test_missing_file_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (workflow / "config.yaml").write_text(
                "schema_version: '2.9'\nharness: claude\nprovider_mode: single\n",
                encoding="utf-8",
            )
            with self.assertRaises(ProviderLocalConfigError):
                load_local_config(repository)

    def test_load_local_config_raises_on_invalid_or_corrupt_config(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (repository / LOCAL_FILE).write_text(
                "schema_version: [\nunclosed array\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ProviderLocalConfigError, "invalid provider local configuration"):
                load_local_config(repository)


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.ext import ProviderLocalConfigError  # noqa: E402
from workflow_providers.local_config import (  # noqa: E402
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
                "schema_version: '2.8'\n"
                "providers:\n"
                "  claude:\n"
                "    executable: claude\n"
                "    models:\n"
                "      low: haiku\n"
                "      medium: sonnet\n"
                "      high: opus\n",
                encoding="utf-8",
            )

            providers = load_local_config(repository)

        self.assertEqual("claude", providers["claude"].executable)
        self.assertEqual("opus", providers["claude"].models["high"])

    def test_load_local_config_reads_from_main_checkout_when_inside_worktree(self):
        import subprocess

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve() / "repo"
            repository.mkdir()
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repository, check=True)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (repository / LOCAL_FILE).write_text(
                "schema_version: '2.8'\n"
                "providers:\n"
                "  claude:\n"
                "    executable: claude\n"
                "    models:\n"
                "      low: haiku\n"
                "      medium: sonnet\n"
                "      high: opus\n",
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
            self.assertEqual("opus", providers["claude"].models["high"])

    def test_rejects_missing_reasoning_tier(self):
        with self.assertRaisesRegex(ProviderLocalConfigError, "missing model tier: high"):
            validate_local_config(
                {
                    "schema_version": "2.8",
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
                    "schema_version": "2.8",
                    "providers": {
                        "claude": {
                            "executable": "claude",
                            "models": {"low": "haiku", "medium": "sonnet", "high": "opus"},
                            "api_key": "sk-local-secret",
                        }
                    },
                }
            )

    def test_provider_default_is_an_explicit_machine_local_selection_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (repository / LOCAL_FILE).write_text(
                "schema_version: '2.8'\n"
                "providers:\n"
                "  antigravity:\n"
                "    executable: agy\n"
                "    models:\n"
                "      low: provider_default\n"
                "      medium: provider_default\n"
                "      high: gemini-pro\n",
                encoding="utf-8",
            )

            providers = load_local_config(repository)

        antigravity = providers["antigravity"]
        self.assertEqual("provider_default", antigravity.models["medium"])
        self.assertEqual("provider_default", antigravity.selection_mode("medium"))
        self.assertEqual("explicit", antigravity.selection_mode("high"))

    def test_provider_default_is_accepted_for_opencode(self):
        validate_local_config(
            {
                "schema_version": "2.8",
                "providers": {
                    "opencode": {
                        "executable": "opencode",
                        "models": {
                            "low": "provider_default",
                            "medium": "provider_default",
                            "high": "github-copilot/claude-sonnet-5.5",
                        },
                    }
                },
            }
        )

    def test_provider_default_is_rejected_for_non_antigravity_providers(self):
        with self.assertRaisesRegex(
            ProviderLocalConfigError,
            "provider_default is only supported for antigravity",
        ):
            validate_local_config(
                {
                    "schema_version": "2.8",
                    "providers": {
                        "codex": {
                            "executable": "codex",
                            "models": {
                                "low": "provider_default",
                                "medium": "provider_default",
                                "high": "provider_default",
                            },
                        }
                    },
                }
            )

    def test_loads_mapping_model_tier_with_effort(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (repository / LOCAL_FILE).write_text(
                "schema_version: '2.8'\n"
                "providers:\n"
                "  codex:\n"
                "    executable: codex\n"
                "    models:\n"
                "      low:\n"
                "        model: gpt-6-astra\n"
                "        effort: low\n"
                "      medium:\n"
                "        model: gpt-6-astra\n"
                "        effort: medium\n"
                "      high:\n"
                "        model: gpt-6-astra\n"
                "        effort: high\n",
                encoding="utf-8",
            )

            providers = load_local_config(repository)

        codex = providers["codex"]
        self.assertEqual("gpt-6-astra", codex.models["low"].model)
        self.assertEqual("low", codex.models["low"].effort)
        self.assertEqual("medium", codex.models["medium"].effort)
        self.assertEqual("high", codex.models["high"].effort)
        self.assertEqual("explicit", codex.selection_mode("low"))

    def test_rejects_effort_for_non_codex_provider(self):
        with self.assertRaisesRegex(
            ProviderLocalConfigError,
            "effort is only supported for codex",
        ):
            validate_local_config(
                {
                    "schema_version": "2.8",
                    "providers": {
                        "claude": {
                            "executable": "claude",
                            "models": {
                                "low": {"model": "haiku", "effort": "low"},
                                "medium": "sonnet",
                                "high": "opus",
                            },
                        }
                    },
                }
            )

    def test_rejects_invalid_effort_value(self):
        with self.assertRaisesRegex(
            ProviderLocalConfigError,
            "effort must be one of",
        ):
            validate_local_config(
                {
                    "schema_version": "2.8",
                    "providers": {
                        "codex": {
                            "executable": "codex",
                            "models": {
                                "low": {"model": "gpt-6-astra", "effort": "super-high"},
                                "medium": "gpt-6-astra",
                                "high": "gpt-6-astra",
                            },
                        }
                    },
                }
            )

    def test_rejects_effort_on_provider_default(self):
        with self.assertRaisesRegex(
            ProviderLocalConfigError,
            "provider_default cannot declare an effort",
        ):
            validate_local_config(
                {
                    "schema_version": "2.8",
                    "providers": {
                        "antigravity": {
                            "executable": "agy",
                            "models": {
                                "low": {"model": "provider_default", "effort": "low"},
                                "medium": "provider_default",
                                "high": "gemini-pro",
                            },
                        }
                    },
                }
            )

    def test_missing_file_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (workflow / "config.yaml").write_text(
                "schema_version: '2.8'\nharness: claude\nprovider_mode: single\n",
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

import importlib
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))


class ProviderLocalConfigTests(unittest.TestCase):
    def provider_config(self):
        try:
            return importlib.import_module("workflow_core.provider_config")
        except ModuleNotFoundError as error:
            self.fail(f"provider-local configuration module is missing: {error}")

    def test_loads_complete_machine_local_provider_mapping(self):
        module = self.provider_config()
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (workflow / "providers.local.yaml").write_text(
                "schema_version: '2.3'\n"
                "providers:\n"
                "  claude:\n"
                "    executable: claude\n"
                "    models:\n"
                "      low: haiku\n"
                "      medium: sonnet\n"
                "      high: opus\n",
                encoding="utf-8",
            )

            providers = module.load_provider_local_config(repository)

        self.assertEqual("claude", providers["claude"].executable)
        self.assertEqual("opus", providers["claude"].models["high"])

    def test_rejects_missing_reasoning_tier(self):
        module = self.provider_config()
        with self.assertRaisesRegex(module.ProviderLocalConfigError, "missing model tier: high"):
            module.validate_provider_local_config(
                {
                    "schema_version": "2.3",
                    "providers": {
                        "claude": {
                            "executable": "claude",
                            "models": {"low": "haiku", "medium": "sonnet"},
                        }
                    },
                }
            )

    def test_rejects_unknown_or_secret_like_fields(self):
        module = self.provider_config()
        with self.assertRaisesRegex(module.ProviderLocalConfigError, "unsupported provider fields"):
            module.validate_provider_local_config(
                {
                    "schema_version": "2.3",
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
        module = self.provider_config()
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (workflow / "providers.local.yaml").write_text(
                "schema_version: '2.3'\n"
                "providers:\n"
                "  antigravity:\n"
                "    executable: agy\n"
                "    models:\n"
                "      low: provider_default\n"
                "      medium: provider_default\n"
                "      high: gemini-pro\n",
                encoding="utf-8",
            )

            providers = module.load_provider_local_config(repository)

        antigravity = providers["antigravity"]
        self.assertEqual("provider_default", antigravity.models["medium"])
        self.assertEqual("provider_default", antigravity.selection_mode("medium"))
        self.assertEqual("explicit", antigravity.selection_mode("high"))

    def test_provider_default_is_accepted_for_opencode(self):
        module = self.provider_config()
        module.validate_provider_local_config(
            {
                "schema_version": "2.3",
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
        module = self.provider_config()
        with self.assertRaisesRegex(
            module.ProviderLocalConfigError,
            "provider_default is only supported for antigravity",
        ):
            module.validate_provider_local_config(
                {
                    "schema_version": "2.3",
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
        module = self.provider_config()
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            workflow = repository / ".agent-workflow"
            workflow.mkdir()
            (workflow / "providers.local.yaml").write_text(
                "schema_version: '2.3'\n"
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

            providers = module.load_provider_local_config(repository)

        codex = providers["codex"]
        self.assertEqual("gpt-6-astra", codex.models["low"].model)
        self.assertEqual("low", codex.models["low"].effort)
        self.assertEqual("medium", codex.models["medium"].effort)
        self.assertEqual("high", codex.models["high"].effort)
        self.assertEqual("explicit", codex.selection_mode("low"))

    def test_rejects_effort_for_non_codex_provider(self):
        module = self.provider_config()
        with self.assertRaisesRegex(
            module.ProviderLocalConfigError,
            "effort is only supported for codex",
        ):
            module.validate_provider_local_config(
                {
                    "schema_version": "2.3",
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
        module = self.provider_config()
        with self.assertRaisesRegex(
            module.ProviderLocalConfigError,
            "effort must be one of",
        ):
            module.validate_provider_local_config(
                {
                    "schema_version": "2.3",
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
        module = self.provider_config()
        with self.assertRaisesRegex(
            module.ProviderLocalConfigError,
            "provider_default cannot declare an effort",
        ):
            module.validate_provider_local_config(
                {
                    "schema_version": "2.3",
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

    def test_post_init_normalizes_raw_strings_and_dicts(self):
        module = self.provider_config()
        config = module.ProviderModelConfig(
            "codex",
            "codex",
            {
                "low": "gpt-4o",
                "medium": {"model": "gpt-6-astra", "effort": "medium"},
                "high": module.TierModelTarget("gpt-6-astra", "high"),
            },
        )
        self.assertEqual("gpt-4o", config.models["low"].model)
        self.assertIsNone(config.models["low"].effort)
        self.assertEqual("gpt-6-astra", config.models["medium"].model)
        self.assertEqual("medium", config.models["medium"].effort)
        self.assertEqual("high", config.models["high"].effort)

    def test_tier_model_target_equality_semantics(self):
        module = self.provider_config()
        without_effort = module.TierModelTarget("gpt-4o")
        with_effort = module.TierModelTarget("gpt-4o", "medium")

        self.assertEqual(without_effort, "gpt-4o")
        self.assertNotEqual(with_effort, "gpt-4o")
        self.assertNotEqual(without_effort, with_effort)
        self.assertEqual(with_effort, module.TierModelTarget("gpt-4o", "medium"))
        self.assertNotEqual(with_effort, module.TierModelTarget("gpt-4o", "high"))


if __name__ == "__main__":
    unittest.main()


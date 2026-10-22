import importlib
from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))


class ProviderConfigCoreTests(unittest.TestCase):
    def provider_config(self):
        try:
            return importlib.import_module("workflow_core.provider_config")
        except ModuleNotFoundError as error:
            self.fail(f"provider configuration module is missing: {error}")

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

    def test_default_provider_config_returns_valid_config_for_all_harnesses(self):
        module = self.provider_config()
        for harness in ("claude", "antigravity", "opencode", "codex"):
            with self.subTest(harness=harness):
                data = module.default_provider_config(harness)
                self.assertIn("executable", data)
                self.assertIn("models", data)
                model_cfg = module.default_provider_model_config(harness)
                self.assertEqual(harness, model_cfg.provider)
                self.assertIn("medium", model_cfg.models)

        with self.assertRaisesRegex(module.ProviderLocalConfigError, "unknown harness"):
            module.default_provider_config("unknown-harness")


if __name__ == "__main__":
    unittest.main()

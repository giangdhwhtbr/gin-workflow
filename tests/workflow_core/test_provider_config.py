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

    def test_default_executables_and_default_model_config(self):
        module = self.provider_config()
        for harness in ("claude", "antigravity", "opencode", "codex", "copilot"):
            with self.subTest(harness=harness):
                self.assertIn(harness, module.DEFAULT_EXECUTABLES)
                cfg = module.default_provider_model_config(harness)
                self.assertEqual(harness, cfg.provider)
                self.assertEqual(module.DEFAULT_EXECUTABLES[harness], cfg.executable)

        self.assertEqual(module.DEFAULT_EXECUTABLES["copilot"], "copilot")
        self.assertIn("copilot", module.PROVIDER_DEFAULT_PROVIDERS)

        with self.assertRaisesRegex(module.ProviderLocalConfigError, "unknown harness"):
            module.default_provider_model_config("unknown-harness")

    def test_copilot_provider_default_route_candidate(self):
        from workflow_core.assignments import AssignmentResolutionError, RouteCandidate
        self.assertEqual(
            RouteCandidate("copilot", "provider_default", False).selection_mode,
            "provider_default",
        )
        with self.assertRaisesRegex(
            AssignmentResolutionError,
            "provider_default is only supported for antigravity, opencode, and copilot",
        ):
            RouteCandidate("claude", "provider_default", False)

    def test_provider_model_config_dataclass(self):
        module = self.provider_config()
        cfg = module.ProviderModelConfig("claude", "claude")
        self.assertEqual("claude", cfg.provider)
        self.assertEqual("claude", cfg.executable)


if __name__ == "__main__":
    unittest.main()

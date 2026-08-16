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
                "schema_version: '2.2'\n"
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
                    "schema_version": "2.2",
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
                    "schema_version": "2.2",
                    "providers": {
                        "claude": {
                            "executable": "claude",
                            "models": {"low": "haiku", "medium": "sonnet", "high": "opus"},
                            "api_key": "sk-local-secret",
                        }
                    },
                }
            )


if __name__ == "__main__":
    unittest.main()

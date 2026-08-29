from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins/gin-workflow/src"
SCRIPTS = PLUGIN / "scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.configuration import require_yaml, validate_portable_config  # noqa: E402
from workflow_core.provider_config import validate_provider_local_config  # noqa: E402


class ConfigExampleTests(unittest.TestCase):
    def load(self, path):
        return require_yaml().safe_load(path.read_text(encoding="utf-8"))

    def test_full_examples_validate_with_production_loaders_and_show_expected_routes(self):
        portable = self.load(PLUGIN / "examples/config.full.yaml")
        local = self.load(PLUGIN / "examples/providers.local.example.yaml")

        validate_portable_config(portable)
        validate_provider_local_config(local)

        roles = portable["routing"]["roles"]
        self.assertEqual(["claude"], roles["backend"]["preferred"])
        self.assertEqual(["antigravity"], roles["frontend"]["preferred"])
        self.assertEqual(["main_harness"], roles["review"]["preferred"])
        self.assertIn("main_harness", roles["backend"]["fallback"])
        self.assertEqual("opus", local["providers"]["claude"]["models"]["high"])
        self.assertIn("circuit_breaker", portable["routing"])
        self.assertEqual(3, portable["routing"]["review"]["max_cycles"])
        self.assertEqual(3, portable["routing"]["circuit_breaker"]["failure_threshold"])
        self.assertEqual(600, portable["routing"]["queue"]["max_wait_seconds"])
        self.assertEqual(2, portable["routing"]["worker"]["max_retries"])
        self.assertEqual(86400, portable["policy"]["approval"]["ttl_seconds"])

    def test_setup_questionnaire_covers_nine_groups_one_at_a_time_and_two_layer_preview(self):
        setup = (PLUGIN / "skills/setup/SKILL.md").read_text(encoding="utf-8")
        groups = (
            "Main harness",
            "Enabled native providers",
            "Preferred provider roles",
            "Reasoning-to-model mappings",
            "Ordered fallbacks",
            "Provider concurrency",
            "Queue and worker limits",
            "Circuit breaker",
            "Independent review",
        )
        positions = [setup.index(f"{index}. **{group}**") for index, group in enumerate(groups, 1)]

        self.assertEqual(sorted(positions), positions)
        self.assertIn("Ask exactly one question group at a time", setup)
        self.assertIn("--provider-set", setup)
        self.assertIn("provider_configuration", setup)
        self.assertIn("configuration", setup)
        self.assertIn("same assignments", setup)

    def test_canonical_docs_match_plugin_references_and_link_routing_guide(self):
        for name in (
            "setup-system.md",
            "capability-provider-contracts.md",
            "context-and-evidence-policy.md",
        ):
            self.assertEqual(
                (ROOT / "docs" / name).read_bytes(),
                (PLUGIN / "references" / name).read_bytes(),
            )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        vietnamese = (ROOT / "docs/huong-dan-workflow-v2.1.md").read_text(encoding="utf-8")
        routing = (ROOT / "docs/provider-routing.md").read_text(encoding="utf-8")

        self.assertIn("docs/provider-routing.md", readme)
        self.assertIn("v2.2", vietnamese)
        for phrase in (
            "provider role",
            "reasoning tier",
            "providers.local.yaml",
            "health",
            "circuit breaker",
            "rollback",
            "privacy",
        ):
            self.assertIn(phrase, routing.lower())


if __name__ == "__main__":
    unittest.main()

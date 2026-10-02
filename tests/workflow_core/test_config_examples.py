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
        self.assertEqual(2, portable["routing"]["review"]["max_cycles"])
        self.assertEqual(3, portable["routing"]["circuit_breaker"]["failure_threshold"])
        self.assertEqual(600, portable["routing"]["queue"]["max_wait_seconds"])
        self.assertEqual(2, portable["routing"]["worker"]["max_retries"])
        self.assertEqual(86400, portable["policy"]["approval"]["ttl_seconds"])

    def test_setup_quick_flow_asks_five_questions_and_keeps_advanced_groups(self):
        setup = (PLUGIN / "skills/setup/SKILL.md").read_text(encoding="utf-8")
        quick = ("Project type", "Rigor", "Provider mode", "Verify commands", "Code index")
        positions = [setup.index(f"{index}. **{name}**") for index, name in enumerate(quick, 1)]
        self.assertEqual(sorted(positions), positions)
        for phrase in ("Ask exactly one question", "gin-workflow setup preset", "gin-workflow setup models",
                       "--advanced", "--provider-set", "provider_configuration", "configuration",
                       "same assignments"):
            self.assertIn(phrase, setup)

        advanced = setup[setup.index("## Advanced setup"):]
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
        positions = [advanced.index(f"{index}. **{group}**") for index, group in enumerate(groups, 1)]
        self.assertEqual(sorted(positions), positions)

    def test_full_example_shows_project_profile_sections(self):
        portable = self.load(PLUGIN / "examples/config.full.yaml")
        self.assertEqual("brownfield", portable["project"]["stage"])
        self.assertIn("checks", portable["verify"])
        self.assertIn("max_files", portable["quick"])
        self.assertIn(portable["provider_mode"], ("single", "multi"))
        self.assertEqual("provider", portable["routing"]["review"]["independence"])

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

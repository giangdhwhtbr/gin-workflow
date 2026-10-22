from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins/gin-workflow/src"
SCRIPTS = PLUGIN / "scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.configuration import require_yaml, validate_portable_config  # noqa: E402
from workflow_providers.local_config import validate_local_config  # noqa: E402


class ConfigExampleTests(unittest.TestCase):
    def load(self, path):
        return require_yaml().safe_load(path.read_text(encoding="utf-8"))

    def test_full_examples_validate_with_production_loaders_and_show_expected_routes(self):
        portable = self.load(PLUGIN / "examples/config.full.yaml")
        local = self.load(PLUGIN / "examples/providers.local.example.yaml")

        validate_portable_config(portable)
        validate_local_config(local)

        roles = portable["orchestrator"]["roles"]
        self.assertEqual(["claude"], roles["backend"]["preferred"])
        self.assertEqual(["antigravity"], roles["frontend"]["preferred"])
        self.assertEqual(["main_harness"], roles["review"]["preferred"])
        self.assertIn("main_harness", roles["backend"]["fallback"])
        self.assertEqual("opus", local["providers"]["claude"]["models"]["high"])
        self.assertIn("circuit_breaker", portable["orchestrator"])
        self.assertEqual(2, portable["routing"]["review"]["max_cycles"])
        self.assertEqual(3, portable["orchestrator"]["circuit_breaker"]["failure_threshold"])
        self.assertEqual(600, portable["orchestrator"]["queue"]["max_wait_seconds"])
        self.assertEqual(2, portable["orchestrator"]["worker"]["max_retries"])
        self.assertEqual(86400, portable["policy"]["approval"]["ttl_seconds"])
        self.assertEqual("beads", portable["providers"]["task_tracking"])  # the example shows team mode

    def test_setup_quick_flow_asks_five_questions_without_advanced_groups(self):
        setup = (PLUGIN / "skills/setup/SKILL.md").read_text(encoding="utf-8")
        quick = ("Project type", "Rigor", "Verify commands", "Code index", "Task tracking")
        positions = [setup.index(f"{index}. **{name}**") for index, name in enumerate(quick, 1)]
        self.assertEqual(sorted(positions), positions)
        for phrase in ("Ask exactly one question", "gin-workflow setup preset", "configuration",
                       "same assignments"):
            self.assertIn(phrase, setup)
        self.assertNotIn("## Advanced setup", setup)
        self.assertNotIn("--provider-set", setup)

    def test_full_example_shows_project_profile_sections(self):
        portable = self.load(PLUGIN / "examples/config.full.yaml")
        self.assertEqual("brownfield", portable["project"]["stage"])
        self.assertIn("checks", portable["verify"])
        self.assertIn("max_files", portable["quick"])
        self.assertIn(portable["provider_mode"], ("single", "multi"))
        self.assertEqual("provider", portable["routing"]["review"]["independence"])

    def test_readme_links_the_provider_guide_and_docs_cover_routing(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        getting_started = (ROOT / "docs/getting-started.md").read_text(encoding="utf-8")
        routing = (ROOT / "docs/concepts/providers.md").read_text(encoding="utf-8")
        config = (ROOT / "docs/reference/config.md").read_text(encoding="utf-8")

        self.assertIn("docs/concepts/providers.md", readme)
        self.assertIn("docs/starters/greenfield.md", readme)
        self.assertIn("discuss", getting_started)
        for phrase in (
            "provider role",
            "reasoning tier",
            "providers.local.yaml",
            "health",
            "circuit breaker",
            "privacy",
        ):
            self.assertIn(phrase, routing.lower())
        self.assertIn("rollback", config)


if __name__ == "__main__":
    unittest.main()

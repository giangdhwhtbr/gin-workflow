from __future__ import annotations

import unittest

from workflow_core.catalog import (
    DEFAULT_CATALOGS,
    Catalog,
    catalog_for,
    escalate,
    map_index,
    map_route,
    route_diagnostics,
    tier_of,
)


class CatalogTests(unittest.TestCase):
    def test_catalog_for_defaults_and_override(self):
        self.assertEqual(catalog_for({}, "claude"), DEFAULT_CATALOGS["claude"])
        custom = {"models": {"claude": {"models": ["sonnet", "opus"]}}}
        self.assertEqual(
            catalog_for(custom, "claude"),
            Catalog(("sonnet", "opus"), ()),
        )
        with self.assertRaises(KeyError):
            catalog_for({}, "unknown_harness")

    def test_route_diagnostics(self):
        claude = DEFAULT_CATALOGS["claude"]
        antigravity = DEFAULT_CATALOGS["antigravity"]

        self.assertEqual([], route_diagnostics(claude, "sonnet", "medium"))

        unknown_model_diags = route_diagnostics(claude, "unknown-model", "medium")
        self.assertEqual(1, len(unknown_model_diags))
        self.assertIn("model 'unknown-model' is not in the catalog; allowed: haiku, sonnet, opus", unknown_model_diags[0])

        unknown_effort_diags = route_diagnostics(claude, "sonnet", "unknown-effort")
        self.assertEqual(1, len(unknown_effort_diags))
        self.assertIn("effort 'unknown-effort' is not in the catalog; allowed: low, medium, high, xhigh, max", unknown_effort_diags[0])

        ag_effort_diags = route_diagnostics(antigravity, "provider_default", "low")
        self.assertEqual(1, len(ag_effort_diags))
        self.assertIn("effort 'low' given, but the catalog lists no efforts", ag_effort_diags[0])

    def test_tier_of(self):
        claude = DEFAULT_CATALOGS["claude"]
        antigravity = DEFAULT_CATALOGS["antigravity"]

        self.assertEqual("low", tier_of(claude, "haiku"))
        self.assertEqual("medium", tier_of(claude, "sonnet"))
        self.assertEqual("high", tier_of(claude, "opus"))
        self.assertEqual("medium", tier_of(antigravity, "provider_default"))

    def test_map_index(self):
        self.assertEqual(1, map_index(1, 3, 3))
        self.assertEqual(1, map_index(1, 3, 2))
        self.assertEqual(1, map_index(2, 3, 2))
        self.assertEqual(0, map_index(0, 3, 5))
        self.assertEqual(2, map_index(1, 3, 4))
        self.assertEqual(1, map_index(0, 1, 3))
        self.assertEqual(1, map_index(0, 1, 4))

    def test_map_route(self):
        claude = DEFAULT_CATALOGS["claude"]
        codex = DEFAULT_CATALOGS["codex"]
        antigravity3 = Catalog(("ag-small", "ag-med", "ag-large"), ())

        self.assertEqual(("ag-med", None), map_route(claude, antigravity3, "sonnet", "medium"))
        self.assertEqual(("gpt-6-astra", "xhigh"), map_route(claude, codex, "opus", "max"))
        self.assertEqual(("gpt-6-astra", "high"), map_route(claude, codex, "haiku", "high"))

    def test_escalate(self):
        claude = DEFAULT_CATALOGS["claude"]
        antigravity = DEFAULT_CATALOGS["antigravity"]

        self.assertEqual(("sonnet", "low"), escalate(claude, "haiku", "low"))
        self.assertEqual(("opus", "medium"), escalate(claude, "opus", "low"))
        self.assertIsNone(escalate(claude, "opus", "max"))
        self.assertIsNone(escalate(antigravity, "provider_default", None))


if __name__ == "__main__":
    unittest.main()

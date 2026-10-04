"""Lint for the packaged rule packs: frontmatter, anchors, impacts, Why lines, tool checks."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins/gin-workflow/src/scripts"))

from workflow_core.rules import IMPACTS, TIERS, load_plugin_packs  # noqa: E402

PACKS = load_plugin_packs(ROOT / "plugins/gin-workflow/src/rules")
CHECK_KINDS = {"tsconfig_option", "eslint_rule", "pyproject_tool", "file_exists"}
DETECT_KEYS = {"package_json_deps", "pyproject_deps", "files_exist"}


class TestRulePacks(unittest.TestCase):
    def test_frontmatter_and_bullets(self):
        for pack in PACKS.values():
            with self.subTest(pack=pack.id):
                self.assertIn(pack.tier, TIERS)
                self.assertTrue(pack.applies_to)
                self.assertTrue(pack.bullets)
                self.assertTrue(all(b.impact in IMPACTS for b in pack.bullets))
                self.assertTrue(all(name in PACKS for name in pack.requires))
                self.assertLessEqual(set(pack.meta.get("detect") or {}), DETECT_KEYS)

    def test_tool_checks_and_conflicts_are_well_formed(self):
        for pack in PACKS.values():
            for check in pack.meta.get("tool_checks") or []:
                with self.subTest(pack=pack.id, check=check.get("id")):
                    self.assertTrue(check["id"] and check["suggest"].strip())
                    self.assertEqual(1, len(check["check"]))
                    self.assertIn(next(iter(check["check"])), CHECK_KINDS)
            for item in pack.meta.get("conflict_keywords") or []:
                self.assertEqual({"pack_says", "project_conflict"}, set(item))

    def test_every_pack_explains_its_critical_rules(self):
        for pack in PACKS.values():
            for bullet in pack.bullets:
                if bullet.impact == "critical":
                    with self.subTest(pack=pack.id, anchor=bullet.anchor):
                        self.assertIn(bullet.anchor, pack.why)

    def test_core_and_lean_apply_everywhere_and_others_are_scoped(self):
        for name in ("core", "lean"):
            self.assertEqual(("**/*",), PACKS[name].applies_to)
            self.assertEqual("core", PACKS[name].tier)
        self.assertNotIn("**/*", [p for pack in PACKS.values() if pack.id not in ("core", "lean")
                                  for p in pack.applies_to])


if __name__ == "__main__":
    unittest.main()

"""Schema 2.6: SDD artifact keys, project layout settings, and the 2.5 -> 2.6 migration."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.configuration import ConfigValidationError, validate_portable_config  # noqa: E402
from workflow_core.migrations import CURRENT_VERSION, migrate_config  # noqa: E402
from workflow_core.project import preset_assignments, project_settings  # noqa: E402
from workflow_core.schemas import SUPPORTED_CONFIG_VERSIONS  # noqa: E402


class TestSchema26(unittest.TestCase):
    def test_current_version_is_2_6_and_older_versions_load(self):
        self.assertEqual("2.6", CURRENT_VERSION)
        self.assertEqual(("2.3", "2.4", "2.5", "2.6"), SUPPORTED_CONFIG_VERSIONS)
        for version in SUPPORTED_CONFIG_VERSIONS:
            with self.subTest(version=version):
                validate_portable_config({"schema_version": version})

    def test_sdd_artifact_keys_validate(self):
        validate_portable_config({"schema_version": "2.6", "artifacts": {
            "layout": "sdd", "specs": "docs/specs", "changes": "docs/changes", "adr": "docs/adr",
            "codebase": "docs/codebase", "spec_review": "pr", "test_globs": ["tests/**"]}})
        for bad in ({"layout": "openspec"}, {"spec_review": "email"}, {"test_globs": "tests/**"},
                    {"test_globs": [""]}, {"specs": ""}, {"unknown": "x"}):
            with self.subTest(bad=bad), self.assertRaises(ConfigValidationError):
                validate_portable_config({"schema_version": "2.6", "artifacts": bad})

    def test_migration_2_5_to_2_6_only_bumps_versions(self):
        source = {"schema_version": "2.5", "workflow_version": "2.5", "setup_cli_version": "2.5",
                  "rules": {"packs": ["core"]}}
        self.assertEqual({**source, "schema_version": "2.6", "workflow_version": "2.6", "setup_cli_version": "2.6"},
                         migrate_config(source, "2.6"))

    def test_project_settings_default_to_legacy_chat(self):
        settings = project_settings({"schema_version": "2.5"})
        self.assertEqual(("legacy", "chat"), (settings.layout, settings.spec_review))
        settings = project_settings({"schema_version": "2.6", "artifacts": {"layout": "sdd", "spec_review": "pr"}})
        self.assertEqual(("sdd", "pr"), (settings.layout, settings.spec_review))

    def test_preset_assignment_sets_layout_only_when_given(self):
        common = {"stage": "greenfield", "shape": "backend", "rigor": "easy", "provider_mode": "single"}
        self.assertIn('artifacts.layout="sdd"', preset_assignments(**common, layout="sdd"))
        self.assertFalse(any(a.startswith("artifacts.layout") for a in preset_assignments(**common)))


if __name__ == "__main__":
    unittest.main()

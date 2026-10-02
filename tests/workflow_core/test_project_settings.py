"""Project settings resolution and schema 2.4 compatibility."""

from __future__ import annotations

import unittest

from workflow_core.configuration import ConfigValidationError, validate_portable_config
from workflow_core.migrations import migrate_config
from workflow_core.project import project_settings


class TestProjectSettings(unittest.TestCase):
    def test_missing_project_section_keeps_legacy_behavior(self):
        settings = project_settings({"schema_version": "2.3"})
        self.assertEqual(("fullstack", "standard", "multi", "provider"),
                         (settings.shape, settings.rigor, settings.provider_mode, settings.independence))
        self.assertEqual({}, settings.verify_commands)

    def test_explicit_project_values_are_read(self):
        settings = project_settings({
            "schema_version": "2.4",
            "project": {"stage": "brownfield", "shape": "frontend", "rigor": "easy", "worktree": "never"},
            "provider_mode": "single",
            "verify": {"checks": {"lint": "pnpm run lint", "e2e": ""}},
            "routing": {"review": {"independence": "session", "max_cycles": 2}},
            "quick": {"max_files": 7},
        })
        self.assertEqual("frontend", settings.shape)
        self.assertEqual("session", settings.independence)
        self.assertEqual({"lint": "pnpm run lint"}, settings.verify_commands)
        self.assertEqual(7, settings.quick_max_files)

    def test_both_versions_validate_and_bad_enum_fails(self):
        validate_portable_config({"schema_version": "2.3"})
        validate_portable_config({"schema_version": "2.4", "project": {"shape": "frontend"}})
        with self.assertRaises(ConfigValidationError):
            validate_portable_config({"schema_version": "2.4", "project": {"shape": "mobile"}})
        with self.assertRaises(ConfigValidationError):
            validate_portable_config({"schema_version": "2.4", "routing": {"review": {"independence": "team"}}})

    def test_migration_2_3_to_2_4_only_bumps_versions(self):
        source = {"schema_version": "2.3", "workflow_version": "2.3", "setup_cli_version": "2.3",
                  "routing": {"review": {"max_cycles": 3}}}
        migrated = migrate_config(source, "2.4")
        self.assertEqual("2.4", migrated["schema_version"])
        self.assertEqual({"review": {"max_cycles": 3}}, migrated["routing"])
        self.assertNotIn("project", migrated)

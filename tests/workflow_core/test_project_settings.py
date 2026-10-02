"""Project settings resolution and schema 2.4 compatibility."""

from __future__ import annotations

import unittest

from workflow_core.configuration import ConfigValidationError, validate_portable_config
from workflow_core.migrations import migrate_config
from workflow_core.project import preset_assignments, project_settings
from workflow_core.setup_service import _parse_assignment, _set_nested


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


def _apply(assignments):
    config = {"schema_version": "2.4"}
    for assignment in assignments:
        path, value = _parse_assignment(assignment)
        _set_nested(config, path, value)
    return config


class TestPresets(unittest.TestCase):
    def test_single_provider_frontend_standard(self):
        config = _apply(preset_assignments(stage="brownfield", shape="frontend", rigor="standard",
                                           provider_mode="single",
                                           verify_commands={"lint": "pnpm run lint", "test": "pnpm run test: unit"}))
        validate_portable_config(config)
        self.assertEqual(["docs", "frontend", "general", "review"],
                         sorted(config["routing"]["roles"]))
        self.assertEqual({"preferred": ["main_harness"]}, config["routing"]["roles"]["frontend"])
        self.assertEqual("session", config["routing"]["review"]["independence"])
        self.assertEqual("pnpm run test: unit", config["verify"]["checks"]["test"])
        self.assertEqual("parallel", config["project"]["worktree"])
        settings = project_settings(config)
        self.assertEqual(("frontend", "standard", "single"), (settings.shape, settings.rigor, settings.provider_mode))

    def test_multi_provider_writes_no_roles_and_provider_independence(self):
        config = _apply(preset_assignments(stage="brownfield", shape="backend", rigor="strict", provider_mode="multi"))
        validate_portable_config(config)
        self.assertNotIn("roles", config.get("routing", {}))
        self.assertEqual("provider", config["routing"]["review"]["independence"])
        self.assertEqual(("always", True), (config["project"]["worktree"], config["project"]["review_ledger"]))

    def test_rejects_unknown_values(self):
        with self.assertRaises(ValueError):
            preset_assignments(stage="legacy", shape="mobile", rigor="standard", provider_mode="single")

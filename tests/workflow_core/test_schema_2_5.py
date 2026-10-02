"""Schema 2.5: rules block, read-compatibility, and the 2.4 -> 2.5 migration."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.configuration import (  # noqa: E402
    ConfigValidationError, resolve_effective_config, validate_portable_config)
from workflow_core.migrations import CURRENT_VERSION, migrate_config  # noqa: E402
from workflow_core.schemas import SUPPORTED_CONFIG_VERSIONS  # noqa: E402


class TestSchema25(unittest.TestCase):
    def test_current_version_is_2_5_and_older_versions_load(self):
        self.assertEqual("2.5", CURRENT_VERSION)
        self.assertEqual(("2.3", "2.4", "2.5"), SUPPORTED_CONFIG_VERSIONS)
        for version in SUPPORTED_CONFIG_VERSIONS:
            with self.subTest(version=version):
                validate_portable_config({"schema_version": version})

    def test_rules_block_validates(self):
        validate_portable_config({"schema_version": "2.5",
                                  "rules": {"packs": ["core", "react"], "disabled": ["nextjs"]}})
        for bad in ({"packs": "core"}, {"packs": [""]}, {"unknown": []}):
            with self.subTest(bad=bad), self.assertRaises(ConfigValidationError):
                validate_portable_config({"schema_version": "2.5", "rules": bad})

    def test_migration_2_4_to_2_5_only_bumps_versions(self):
        source = {"schema_version": "2.4", "workflow_version": "2.4", "setup_cli_version": "2.4",
                  "project": {"shape": "frontend"}}
        migrated = migrate_config(source, "2.5")
        self.assertEqual({**source, "schema_version": "2.5", "workflow_version": "2.5",
                          "setup_cli_version": "2.5"}, migrated)
        self.assertNotIn("rules", migrated)

    def test_migration_2_3_chains_through_2_4(self):
        source = {"schema_version": "2.3", "workflow_version": "2.3", "setup_cli_version": "2.3"}
        self.assertEqual("2.5", migrate_config(source, "2.5")["schema_version"])

    def test_effective_config_keeps_rules_block(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".agent-workflow").mkdir()
            (root / ".agent-workflow/config.yaml").write_text(
                "schema_version: '2.5'\nrules: {packs: [core, python]}\n", encoding="utf-8")
            config = resolve_effective_config(root, write=False).config.to_dict()
            self.assertEqual(["core", "python"], config["rules"]["packs"])


if __name__ == "__main__":
    unittest.main()

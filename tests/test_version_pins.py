"""Every location of the release version holds the version of plugins/gin-workflow/plugin.meta.json."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bump_version", ROOT / "scripts/bump_version.py")
bump_version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bump_version)


def reference_version() -> str:
    return json.loads((ROOT / "plugins/gin-workflow/plugin.meta.json").read_text(encoding="utf-8"))["version"]


class VersionPinTests(unittest.TestCase):
    def test_every_location_holds_the_reference_version(self):
        reference = reference_version()
        differing = {}
        for path, pattern in bump_version.locations(ROOT):
            match = pattern.search(path.read_text(encoding="utf-8"))
            self.assertIsNotNone(match, f"{path.relative_to(ROOT)}: no version found")
            if match.group(1) != reference:
                differing[f"{path.relative_to(ROOT)} ({pattern.pattern})"] = match.group(1)
        self.assertEqual({}, differing, f"these locations differ from the reference version {reference}")

    def test_every_plugin_manifest_is_a_location(self):
        tracked = subprocess.run(
            ["git", "ls-files", "plugins/*/plugin.meta.json", "plugins/*/plugin.json"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        ).stdout.split()
        listed = {path.relative_to(ROOT).as_posix() for path, _ in bump_version.locations(ROOT)}
        self.assertEqual([], sorted(set(tracked) - listed), "manifests that bump_version.py does not write")


if __name__ == "__main__":
    unittest.main()

"""scripts/bump_version.py writes one version to every location and refuses a bad value."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bump_version", ROOT / "scripts/bump_version.py")
bump_version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bump_version)


class BumpVersionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        for path, _ in bump_version.locations(ROOT):
            target = self.tmp / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)

    def snapshot(self) -> dict[Path, str]:
        return {path: path.read_text(encoding="utf-8") for path, _ in bump_version.locations(self.tmp)}

    def versions(self) -> set[str]:
        return {pattern.search(path.read_text(encoding="utf-8")).group(1) for path, pattern in bump_version.locations(self.tmp)}

    def test_bump_writes_every_location_and_a_second_run_changes_nothing(self):
        changed = bump_version.bump(self.tmp, "9.8.7")
        self.assertEqual({path for path, _ in bump_version.locations(self.tmp)}, set(changed))
        self.assertEqual({"9.8.7"}, self.versions())
        self.assertEqual([], bump_version.bump(self.tmp, "9.8.7"))

    def test_bump_keeps_the_line_endings_of_a_file(self):
        crlf = self.tmp / "install.ps1"
        crlf.write_bytes(crlf.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        bump_version.bump(self.tmp, "9.8.7")
        content = crlf.read_bytes()
        self.assertIn(b"$LauncherVersion = '9.8.7'\r\n", content)
        self.assertNotIn(b"\n", content.replace(b"\r\n", b""))

    def test_bad_version_raises_and_changes_nothing(self):
        before = self.snapshot()
        for bad in ("3.1", "3.1.0.1", "v3.1.0", "3.1.x", ""):
            with self.assertRaises(ValueError, msg=bad):
                bump_version.bump(self.tmp, bad)
        self.assertEqual(before, self.snapshot())

    def test_unmatched_location_raises_naming_the_file_and_changes_nothing(self):
        broken = self.tmp / "install.ps1"
        broken.write_text(broken.read_text(encoding="utf-8").replace("$QaLauncherVersion", "$QaVersion"), encoding="utf-8")
        before = self.snapshot()
        with self.assertRaises(ValueError) as caught:
            bump_version.bump(self.tmp, "9.8.7")
        self.assertIn("install.ps1", str(caught.exception))
        self.assertEqual(before, self.snapshot())

    def test_main_exits_2_on_a_bad_value(self):
        self.assertEqual(2, bump_version.main(["3.1"]))
        self.assertEqual(2, bump_version.main([]))


if __name__ == "__main__":
    unittest.main()

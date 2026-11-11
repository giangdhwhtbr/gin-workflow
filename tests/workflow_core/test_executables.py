from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core import executables  # noqa: E402
from workflow_core.executables import clear_cache, detect, read_local, tool, write_local  # noqa: E402


def make_fake(directory: Path) -> Path:
    if os.name == "nt":
        path = directory / "fake-bd.cmd"
        path.write_text("@exit 0\n", encoding="utf-8")
        return path
    path = directory / "fake-bd"
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


class ExecutablesTests(unittest.TestCase):
    def setUp(self):
        clear_cache()
        self.addCleanup(clear_cache)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root / ".agent-workflow").mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.fake = make_fake(self.bin)

    def put(self, text: str) -> None:
        (self.root / executables.LOCAL_FILE).write_text(text, encoding="utf-8")
        clear_cache()

    def test_prefers_a_valid_configured_path(self):
        write_local(self.root, {"bd": str(self.fake)})
        with mock.patch("shutil.which", return_value=None):
            self.assertEqual(str(self.fake), tool("bd", self.root))

    def test_falls_back_to_path_when_entry_is_stale(self):
        write_local(self.root, {"bd": str(self.bin / "gone")})
        with mock.patch("shutil.which", return_value="/x/bd"):
            self.assertEqual("/x/bd", tool("bd", self.root))

    def test_falls_back_when_file_is_missing_or_invalid(self):
        with mock.patch("shutil.which", return_value="/x/bd"):
            self.assertEqual("/x/bd", tool("bd", self.root))
            for text, problem in (
                ("executables: {bd: relative/bd}\n", "bd: path is not absolute"),
                ("executables: {foo: /a/b}\n", "foo: unknown tool"),
                ("- a\n- b\n", "executables: must be a mapping"),
            ):
                self.put(text)
                self.assertEqual("/x/bd", tool("bd", self.root))
                self.assertEqual([problem], read_local(self.root)[1])
            self.put("executables: [unclosed\n")
            self.assertEqual("/x/bd", tool("bd", self.root))
            self.assertIn("invalid YAML", read_local(self.root)[1][0])

    def test_detect_lists_only_found_tools(self):
        with mock.patch("shutil.which", side_effect={"bd": "/x/bd"}.get):
            self.assertEqual({"bd": os.path.abspath("/x/bd")}, detect(("bd", "gh"), self.root))

    def test_write_then_read_round_trip(self):
        found = {"bd": str(self.fake), "git": os.path.abspath("/usr/bin/git")}
        path = write_local(self.root, found)
        self.assertEqual((found, []), read_local(self.root))
        self.assertTrue(path.read_text(encoding="utf-8").startswith('schema_version: "2.10"'))

    def test_cache_is_per_root_and_clearable(self):
        write_local(self.root, {"bd": str(self.fake)})
        with mock.patch("shutil.which", return_value=None):
            self.assertEqual(str(self.fake), tool("bd", self.root))
            (self.root / executables.LOCAL_FILE).write_text("executables: {}\n", encoding="utf-8")
            self.assertEqual(str(self.fake), tool("bd", self.root))
            clear_cache()
            self.assertIsNone(tool("bd", self.root))


if __name__ == "__main__":
    unittest.main()

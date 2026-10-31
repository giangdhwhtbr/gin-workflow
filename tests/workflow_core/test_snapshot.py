import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins/gin-workflow/src/scripts"))

from workflow_core import setup_service, snapshot  # noqa: E402


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.src = base / "src"
        self.install = base / "install"
        (self.src / "skills").mkdir(parents=True)
        self.install.mkdir()
        (self.src / "skills/a.md").write_text("one\n", encoding="utf-8")

    def test_us7_matching_tree_has_no_warning(self):
        snapshot.write_stamp(self.src, self.install)
        self.assertIsNone(snapshot.check(self.install))

    def test_us7_edited_tree_warns(self):
        snapshot.write_stamp(self.src, self.install)
        (self.src / "skills/a.md").write_text("two\n", encoding="utf-8")
        self.assertIn("installed snapshot differs from src", snapshot.check(self.install))

    def test_us7_missing_stamp_or_src_is_silent(self):
        self.assertIsNone(snapshot.check(self.install))
        snapshot.write_stamp(self.src, self.install)
        (self.src / "skills/a.md").unlink()
        (self.src / "skills").rmdir()
        self.src.rmdir()
        self.assertIsNone(snapshot.check(self.install))

    def test_us7_unreadable_stamp_is_silent(self):
        (self.install / snapshot.STAMP).write_text("not json", encoding="utf-8")
        self.assertIsNone(snapshot.check(self.install))

    def test_us7_pycache_is_ignored(self):
        snapshot.write_stamp(self.src, self.install)
        (self.src / "__pycache__").mkdir()
        (self.src / "__pycache__/x.pyc").write_bytes(b"x")
        self.assertIsNone(snapshot.check(self.install))

    def test_us7_doctor_reports_the_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(snapshot, "check", return_value="installed snapshot differs from src (x)"):
                report = setup_service.doctor(Path(directory))
        self.assertIn("install: installed snapshot differs from src (x)", report["actions"])


if __name__ == "__main__":
    unittest.main()

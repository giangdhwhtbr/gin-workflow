from datetime import date
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.milestone import Roadmap  # noqa: E402
from workflow_core.roadmap_file import read_roadmap  # noqa: E402

HEAD = "# Roadmap: X\n\n## Constraints\n\n"


class ReadRoadmapTests(unittest.TestCase):
    def write(self, root, body, layout="legacy"):
        path = root / (".planning/roadmap.md" if layout == "legacy" else "docs/roadmap.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(HEAD + body, encoding="utf-8")

    def test_deadline_and_capacity_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root, "- AI capacity: 2 people building with AI agents, 1 Claude Max account\n- Deadline: 2026-12-31\n")
            self.assertEqual(Roadmap(date(2026, 12, 31), 2, None), read_roadmap(root, "legacy"))

    def test_missing_file_and_missing_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(Roadmap(), read_roadmap(root, "legacy"))
            self.write(root, "- AI capacity: one person\n- Deadline:\n")
            self.assertEqual(Roadmap(), read_roadmap(root, "legacy"))

    def test_zero_capacity_is_no_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root, "- AI capacity: 0\n")
            self.assertEqual(Roadmap(), read_roadmap(root, "legacy"))

    def test_malformed_deadline_is_an_error_not_an_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root, "- Deadline: soon\n- AI capacity: 1\n")
            found = read_roadmap(root, "legacy")
            self.assertEqual((None, 1), (found.deadline, found.lanes))
            self.assertEqual("Deadline: soon is not a date (YYYY-MM-DD)", found.error)

    def test_sdd_layout_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root, "- Deadline: 2027-01-15\n", layout="sdd")
            self.assertEqual(date(2027, 1, 15), read_roadmap(root, "sdd").deadline)
            self.assertIsNone(read_roadmap(root, "legacy").deadline)


if __name__ == "__main__":
    unittest.main()

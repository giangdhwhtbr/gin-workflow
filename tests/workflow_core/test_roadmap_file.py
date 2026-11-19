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

    def test_days_per_point_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root, "- AI capacity: 2\n- Days per point: 1.5 (assumed)\n")
            self.assertEqual(1.5, read_roadmap(root, "legacy").days_per_point)
            self.write(root, "- Days per point: none\n")
            self.assertIsNone(read_roadmap(root, "legacy").days_per_point)
            self.write(root, "- Days per point: 0\n")
            self.assertIsNone(read_roadmap(root, "legacy").days_per_point)

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

    def test_manager_view_sections_change_neither_deadline_nor_lanes(self):
        constraints = "- AI capacity: 3 lanes\n- Deadline: 2027-03-31\n\n"
        manager_view = (
            "## Summary\n\n| Milestone | Period | Outcome | Demo | Epics |\n|---|---|---|---|---|\n"
            "| M1 | 2027-01-04 to 2027-01-29 | Shop live | Browse and buy | Catalog |\n\n"
            "## Milestone: M1\n\nOutcome: Shop live\nDemo: Browse and buy\n\n"
            "### Catalog\nEpic: x-catalog\nFeatures: Browse\nLegacy: 12 screens\n\n"
            "## Legacy coverage\n\n| Capability | Legacy screens | Epics | Milestone | Status |\n|---|---|---|---|---|\n"
            "| catalog | 12 | x-catalog | M1 | planned |\n"
        )
        with tempfile.TemporaryDirectory() as plain, tempfile.TemporaryDirectory() as managed:
            self.write(Path(plain), constraints)
            self.write(Path(managed), constraints + manager_view)
            expected = read_roadmap(Path(plain), "legacy")
            self.assertEqual(Roadmap(date(2027, 3, 31), 3, None), expected)
            self.assertEqual(expected, read_roadmap(Path(managed), "legacy"))

    def test_result_block_changes_neither_deadline_nor_lanes(self):
        constraints = "- AI capacity: 3 lanes\n- Deadline: 2027-03-31\n\n"
        result = (
            "## Milestone: M1\n\nOutcome: Shop live\nDemo: Browse and buy\n"
            "Result: closed 2027-01-29; delivered 2 of 3 epics; 1 moved to M2\n"
            "- Outcome: partial; checkout pending\n"
            "- Spillover: Checkout: payment API late; re-estimate\n\n"
        )
        with tempfile.TemporaryDirectory() as plain, tempfile.TemporaryDirectory() as managed:
            self.write(Path(plain), constraints)
            self.write(Path(managed), constraints + result)
            expected = read_roadmap(Path(plain), "legacy")
            self.assertEqual(Roadmap(date(2027, 3, 31), 3, None), expected)
            self.assertEqual(expected, read_roadmap(Path(managed), "legacy"))

    def test_sdd_layout_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root, "- Deadline: 2027-01-15\n", layout="sdd")
            self.assertEqual(date(2027, 1, 15), read_roadmap(root, "sdd").deadline)
            self.assertIsNone(read_roadmap(root, "legacy").deadline)

    def test_unreadable_file_is_an_error_not_an_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / ".planning/roadmap.md"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"\xff\xfe- Deadline: 2026-12-31\n")
            found = read_roadmap(root, "legacy")
            self.assertEqual((None, None), (found.deadline, found.lanes))
            self.assertTrue(found.error.startswith("roadmap file unreadable: "), found.error)


if __name__ == "__main__":
    unittest.main()

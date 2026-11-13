from __future__ import annotations

from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core import prep  # noqa: E402


class PrepTests(unittest.TestCase):
    def test_constants(self):
        self.assertEqual("prep", prep.PREP)
        self.assertEqual(("capture", "mockup", "spike", "question", "other"), prep.TYPES)

    def test_is_prep(self):
        self.assertTrue(prep.is_prep({"labels": ["prep", "prep:capture"]}))
        self.assertFalse(prep.is_prep({"labels": ["prep", "track:2"]}))
        self.assertFalse(prep.is_prep({"labels": ["prep", "req:CAT-001"]}))
        self.assertFalse(prep.is_prep({"labels": []}))
        self.assertFalse(prep.is_prep({}))

    def test_tracks_of(self):
        prep_item = {"id": "p1", "labels": ["prep", "prep:spike"]}
        track_item = {"id": "t1", "labels": ["track:1"]}
        req_item = {"id": "t2", "labels": ["prep", "req:REQ-01"]}
        non_mapping = "not-a-mapping"
        non_dict_int = 42

        result = prep.tracks_of([prep_item, track_item, req_item, non_mapping, non_dict_int])
        self.assertEqual(result, [track_item, req_item, non_mapping, non_dict_int])


if __name__ == "__main__":
    unittest.main()

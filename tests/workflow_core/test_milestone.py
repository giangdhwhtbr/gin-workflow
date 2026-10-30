from datetime import date
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core import milestone  # noqa: E402

TODAY = date(2026, 10, 29)
D = date.fromisoformat


def bead(id, *, type="epic", status="open", parent=None, minutes=None, blocks=(), labels=(), meta=None, title=""):
    return {"id": id, "title": title or id, "description": "", "status": status, "issue_type": type,
            "parent": parent, "labels": list(labels), "estimated_minutes": minutes, "metadata": meta or {},
            "dependencies": [{"issue_id": id, "depends_on_id": d, "type": "blocks"} for d in blocks]}


def milestone_bead(id="m1", *, start="2026-11-02", end="2026-12-18", status="open", **meta):
    return bead(id, type="milestone", status=status, meta={"start": start, "end": end, **meta})


def world(*beads):
    return {item["id"]: item for item in beads}


def days(count):
    return count * milestone.WORKDAY_MINUTES


def plan(beads, start="2026-11-02", today=TODAY, milestone_id="m1"):
    return milestone.schedule(beads[milestone_id], beads, D(start), today)


def rows(result):
    return {row["id"]: row for row in result["epics"]}


def span(row):
    return row["planned_start"], row["planned_end"]


class ScheduleTests(unittest.TestCase):
    def test_req_007_chain_and_parallel(self):
        beads = world(milestone_bead(), bead("A", parent="m1", minutes=days(3)),
                      bead("B", parent="m1", minutes=days(2), blocks=["A"]), bead("C", parent="m1", minutes=days(4)))
        found = rows(plan(beads))
        self.assertEqual(("2026-11-02", "2026-11-04"), span(found["A"]))
        self.assertEqual(("2026-11-05", "2026-11-06"), span(found["B"]))
        self.assertEqual(("2026-11-02", "2026-11-05"), span(found["C"]))

    def test_req_007_weekend_skipped(self):
        beads = world(milestone_bead(), bead("A", parent="m1", minutes=days(3)))
        self.assertEqual(("2026-11-05", "2026-11-09"), span(rows(plan(beads, "2026-11-05"))["A"]))

    def test_req_007_schedule_start_on_saturday(self):
        beads = world(milestone_bead(), bead("A", parent="m1", minutes=days(1)))
        self.assertEqual(("2026-11-09", "2026-11-09"), span(rows(plan(beads, "2026-11-07"))["A"]))

    def test_req_007_unestimated_dependency(self):
        beads = world(milestone_bead(), bead("U", parent="m1"), bead("A", parent="m1", minutes=days(2)),
                      bead("B", parent="m1", minutes=days(1), blocks=["U", "A"]))
        found = rows(plan(beads))
        self.assertEqual(("2026-11-02", "2026-11-02"), span(found["U"]))
        self.assertEqual(("2026-11-02", "2026-11-03"), span(found["A"]))
        self.assertEqual(("2026-11-04", "2026-11-04"), span(found["B"]))

    def test_req_007_dependency_outside_the_milestone_is_ignored_for_dates(self):
        beads = world(milestone_bead(), milestone_bead("m2"), bead("X", parent="m2", minutes=days(5)),
                      bead("A", parent="m1", minutes=days(1), blocks=["X"]))
        self.assertEqual(("2026-11-02", "2026-11-02"), span(rows(plan(beads))["A"]))

    def test_req_007_closed_epics_are_scheduled_too(self):
        beads = world(milestone_bead(), bead("A", parent="m1", minutes=days(1), status="closed"))
        self.assertEqual(("2026-11-02", "2026-11-02"), span(rows(plan(beads))["A"]))

    def test_req_007_cycle_names_the_loop(self):
        beads = world(milestone_bead(), bead("A", parent="m1", blocks=["B"]), bead("B", parent="m1", blocks=["A"]))
        with self.assertRaises(milestone.CycleError) as caught:
            plan(beads)
        self.assertTrue("A -> B -> A" in str(caught.exception) or "B -> A -> B" in str(caught.exception))

    def test_req_008_overflow(self):
        beads = world(milestone_bead(end="2026-11-04"), bead("A", parent="m1", minutes=days(5)))
        result = plan(beads)
        self.assertIn({"code": "overflow", "days": 2}, rows(result)["A"]["warnings"])
        self.assertEqual(2, result["overflow_days"])

    def test_req_008_overflow_counts_working_days_when_end_is_a_weekend(self):
        beads = world(milestone_bead(end="2026-11-07"), bead("A", parent="m1", minutes=days(6)))
        self.assertEqual(1, plan(beads)["overflow_days"])

    def test_req_008_no_overflow_when_finish_is_on_or_before_end(self):
        beads = world(milestone_bead(end="2026-11-04"), bead("A", parent="m1", minutes=days(3)))
        result = plan(beads)
        self.assertEqual(0, result["overflow_days"])
        self.assertEqual([], rows(result)["A"]["warnings"])

    def test_req_008_late_needs_kickoff_open_epic_and_a_past_end(self):
        open_epic = bead("A", parent="m1", minutes=days(1))
        closed_epic = bead("B", parent="m1", minutes=days(1), status="closed")
        active = world(milestone_bead(start="2026-10-01", kickoff="2026-10-01"), open_epic, closed_epic)
        found = rows(plan(active, "2026-10-01"))
        self.assertIn({"code": "late"}, found["A"]["warnings"])
        self.assertNotIn({"code": "late"}, found["B"]["warnings"])

    def test_req_008_no_late_before_kick_start(self):
        beads = world(milestone_bead(start="2026-10-01"), bead("A", parent="m1", minutes=days(3)))
        self.assertNotIn({"code": "late"}, rows(plan(beads, "2026-10-01"))["A"]["warnings"])

    def test_req_008_unestimated(self):
        beads = world(milestone_bead(), bead("A", parent="m1"), bead("B", parent="m1", minutes=0))
        found = rows(plan(beads))
        self.assertIn({"code": "unestimated"}, found["A"]["warnings"])
        self.assertIn({"code": "unestimated"}, found["B"]["warnings"])

    def test_req_008_external_blocker(self):
        beads = world(milestone_bead(), milestone_bead("m2"), bead("E9", parent="m2", minutes=days(1)),
                      bead("E1", parent="m1", minutes=days(1), blocks=["E9"]))
        row = rows(plan(beads))["E1"]
        self.assertIn({"code": "external_blocker"}, row["warnings"])
        self.assertEqual([{"id": "E9", "milestone": "m2"}], row["external_depends_on"])

    def test_req_008_closed_external_dependency_is_listed_without_warning(self):
        beads = world(milestone_bead(), milestone_bead("m2"), bead("E9", parent="m2", status="closed"),
                      bead("E1", parent="m1", minutes=days(1), blocks=["E9"]))
        row = rows(plan(beads))["E1"]
        self.assertEqual([], row["warnings"])
        self.assertEqual([{"id": "E9", "milestone": "m2"}], row["external_depends_on"])

    def test_req_008_external_dependency_without_milestone_and_external_reference(self):
        beads = world(milestone_bead(), bead("E9"),
                      bead("E1", parent="m1", minutes=days(1), blocks=["E9", "external:proj:cap"]))
        self.assertEqual([{"id": "E9", "milestone": None}], rows(plan(beads))["E1"]["external_depends_on"])


class StatusTests(unittest.TestCase):
    def test_req_004_status(self):
        self.assertEqual("planned", milestone.status(milestone_bead(), TODAY))
        self.assertEqual("scheduled", milestone.status(milestone_bead(kickoff="2026-10-30"), TODAY))
        self.assertEqual("active", milestone.status(milestone_bead(kickoff="2026-10-29"), TODAY))
        self.assertEqual("closed", milestone.status(milestone_bead(status="closed", kickoff="2026-10-01"), TODAY))

    def test_req_006_estimate_days_rounds_up(self):
        self.assertEqual(5, milestone.estimate_days(2400))
        self.assertEqual(6, milestone.estimate_days(2401))
        for minutes in (None, 0, -5):
            self.assertIsNone(milestone.estimate_days(minutes))

    def test_period_requires_start_and_end(self):
        with self.assertRaisesRegex(ValueError, "m1 has no start/end metadata"):
            milestone.period(bead("m1", type="milestone"))

    def test_parse_date_rejects_garbage(self):
        with self.assertRaisesRegex(ValueError, "not an ISO date"):
            milestone.parse_date("11/02/2026")
        for text in ("20261102", "2026-W45-1"):
            with self.assertRaisesRegex(ValueError, "not an ISO date"):
                milestone.parse_date(text)


class PayloadTests(unittest.TestCase):
    def test_req_009_preview_start(self):
        beads = world(milestone_bead(), bead("A", parent="m1", minutes=days(1)))
        payload = milestone.show_payload(beads["m1"], beads, D("2026-11-16"), TODAY)
        self.assertEqual("2026-11-16", payload["schedule_start"])
        self.assertTrue(payload["preview"])

    def test_req_009_schedule_start_defaults_to_kickoff_then_start(self):
        beads = world(milestone_bead(kickoff="2026-11-09"))
        payload = milestone.show_payload(beads["m1"], beads, None, TODAY)
        self.assertEqual(("2026-11-09", False), (payload["schedule_start"], payload["preview"]))
        beads = world(milestone_bead())
        self.assertEqual("2026-11-02", milestone.show_payload(beads["m1"], beads, None, TODAY)["schedule_start"])

    def test_req_011_show_payload_shape(self):
        beads = world(milestone_bead(), bead("A", parent="m1", minutes=days(5), title="Alpha"))
        payload = milestone.show_payload(beads["m1"], beads, None, TODAY)
        self.assertEqual({
            "schema": 1, "id": "m1", "title": "m1", "description": "", "status": "planned",
            "start": "2026-11-02", "end": "2026-12-18", "kickoff": None, "schedule_start": "2026-11-02",
            "preview": False, "today": "2026-10-29", "finish": "2026-11-06", "overflow_days": 0,
            "epics": [{"id": "A", "title": "Alpha", "status": "open", "estimate_days": 5,
                       "planned_start": "2026-11-02", "planned_end": "2026-11-06", "depends_on": [],
                       "external_depends_on": [], "warnings": []}]}, payload)

    def test_req_011_show_payload_without_epics(self):
        beads = world(milestone_bead())
        payload = milestone.show_payload(beads["m1"], beads, None, TODAY)
        self.assertIsNone(payload["finish"])
        self.assertEqual(0, payload["overflow_days"])
        self.assertEqual([], payload["epics"])

    def test_req_011_list_payload_counts(self):
        items = [milestone_bead()]
        items += [bead(f"e{n}", parent="m1", minutes=days(1)) for n in range(1, 7)]
        items += [bead(f"r{n}", labels=["roadmap"]) for n in range(3)]
        items += [bead("rc", labels=["roadmap"], status="closed"),
                  bead("t1", type="task", labels=["roadmap"], parent="e1")]
        payload = milestone.list_payload(world(*items), TODAY, False)
        self.assertEqual(1, payload["schema"])
        self.assertEqual(1, len(payload["milestones"]))
        self.assertEqual({"total": 6, "closed": 0}, payload["milestones"][0]["epics"])
        self.assertEqual(3, payload["unassigned_epics"])
        self.assertEqual("2026-10-29", payload["today"])

    def test_req_011_list_omits_closed_unless_all(self):
        beads = world(milestone_bead(), milestone_bead("m0", status="closed", start="2026-09-01", end="2026-09-30"))
        self.assertEqual(["m1"], [m["id"] for m in milestone.list_payload(beads, TODAY, False)["milestones"]])
        self.assertEqual(["m0", "m1"], [m["id"] for m in milestone.list_payload(beads, TODAY, True)["milestones"]])

    def test_req_011_list_reports_a_cycle_on_that_milestone_only(self):
        beads = world(milestone_bead(), milestone_bead("m2", start="2026-12-01", end="2026-12-31"),
                      bead("A", parent="m2", blocks=["B"]), bead("B", parent="m2", blocks=["A"]),
                      bead("C", parent="m1", minutes=days(1)))
        first, second = milestone.list_payload(beads, TODAY, False)["milestones"]
        self.assertIsNone(first["error"])
        self.assertEqual(("2026-11-02", 0), (first["finish"], first["warnings"]))
        self.assertIn("dependency cycle", second["error"])
        self.assertIsNone(second["finish"])
        self.assertIsNone(second["warnings"])

    def test_req_011_list_reports_bad_kickoff_per_entry(self):
        beads = world(milestone_bead(kickoff="garbage"), milestone_bead("m2", start="2026-12-01", end="2026-12-31"),
                       bead("C", parent="m2", minutes=days(1)))
        bad, good = milestone.list_payload(beads, TODAY, False)["milestones"]
        self.assertIn("not an ISO date", bad["error"])
        self.assertEqual((None, None, None), (bad["status"], bad["finish"], bad["warnings"]))
        self.assertIsNone(good["error"])
        self.assertIsNotNone(good["status"])
        self.assertIsNotNone(good["finish"])

    def test_req_011_list_reports_missing_period(self):
        beads = world(bead("m1", type="milestone"))
        self.assertIn("no start/end metadata", milestone.list_payload(beads, TODAY, False)["milestones"][0]["error"])


if __name__ == "__main__":
    unittest.main()

"""Requirement sign-off: the requirement list of a gate, its sources, and 06-signoff.md."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specs_fixtures import ADDED_BLOCK, AUTH_SPEC, delta, make_change, make_repo, write  # noqa: E402
from workflow_core import signoff, specs  # noqa: E402
from workflow_core.events import WorkflowEvent  # noqa: E402

REMOVED = "### REQ-AUTH-002: Reject wrong password\n<!-- base: {base} -->\nReason: folded into REQ-AUTH-001\n"
WAIVER = {"gate": "requirement_confirmed", "gate_class": "process", "reason": "spike", "scope_hash": "s",
          "waived_by": "lead", "follow_up_task_id": None}


def event(event_type: str, workflow_id: str, payload: dict) -> WorkflowEvent:
    return WorkflowEvent.create(event_type=event_type, workflow_id=workflow_id, actor="ba", payload=payload)


class TestRequirements(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(Path(self.tmp.name) / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        self.cfg = specs.sdd_config(specs.load_config(self.root))

    def tearDown(self):
        self.tmp.cleanup()

    def test_each_delta_block_is_listed_with_its_hash(self):
        base = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-002")[1]
        make_change(self.root, spec_delta=delta(added=ADDED_BLOCK, removed=REMOVED.format(base=base)))
        added = specs.parse_blocks(ADDED_BLOCK)[0][0]
        self.assertEqual([{"id": "REQ-AUTH-003", "hash8": specs.block_hash(added.text)[:8], "op": "added"},
                          {"id": "REQ-AUTH-002", "hash8": base[:8], "op": "removed"}],
                         signoff.requirements_of(self.root, "ep-1"))

    def test_no_list_without_a_change_or_with_the_legacy_layout(self):
        make_change(self.root)
        self.assertIsNone(signoff.requirements_of(self.root, "ep-2"))
        legacy = make_repo(Path(self.tmp.name) / "legacy", layout="legacy")
        self.assertIsNone(signoff.requirements_of(legacy, "ep-1"))


class TestSources(unittest.TestCase):
    def test_bead_gates_come_first(self):
        gates = {"requirement_confirmed": {"pr_url": "https://h/pull/1", "actor": "an@corp.com",
                                           "at": "2026-11-01T00:00:00Z",
                                           "requirements": [{"id": "REQ-AUTH-003", "hash8": "1a2b3c4d", "op": "added"}]}}
        found = signoff.epic_signoff(gates, [event("requirement.confirmed", "ep-1", {"evidence": "x"})], "ep-1")
        self.assertEqual(("beads", "an@corp.com", "https://h/pull/1", "1a2b3c4d"),
                         (found.source, found.actor, found.evidence, found.hash_of("REQ-AUTH-003")))

    def test_newest_event_of_the_epic_then_its_waiver(self):
        events = [event("requirement.confirmed", "ep-1", {"evidence": "old"}),
                  event("requirement.confirmed", "ep-1", {"evidence": "new", "requirements": [
                      {"id": "REQ-AUTH-003", "hash8": "1a2b3c4d", "op": "added"}]}),
                  event("requirement.confirmed", "ep-2", {"evidence": "other"})]
        found = signoff.epic_signoff({}, events, "ep-1")
        self.assertEqual(("events", "new", "1a2b3c4d", False),
                         (found.source, found.evidence, found.hash_of("REQ-AUTH-003"), found.waived))
        waived = signoff.epic_signoff({}, [event("gate.waived", "ep-3", WAIVER)], "ep-3")
        self.assertEqual((True, "spike", "lead", None), (waived.waived, waived.evidence, waived.actor, waived.requirements))
        self.assertIsNone(signoff.epic_signoff({}, events, "ep-9"))

    def test_no_event_log_is_no_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(([], None), signoff.load_events(Path(tmp)))


class TestFile(unittest.TestCase):
    def test_round_trip_and_malformed(self):
        found = signoff.Signoff(at="2026-11-18T09:00:00Z", actor="ba", evidence="spec.md", source="events",
                                requirements=(("REQ-AUTH-003", "1a2b3c4d", "added"),))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / signoff.SIGNOFF_FILE
            path.write_text(signoff.render(found, "ep-1", [{"id": "REQ-AUTH-003", "hash8": "1a2b3c4d", "op": "added"}]),
                            encoding="utf-8")
            text = path.read_text(encoding="utf-8")
            for line in ("Epic: ep-1", "Signed off: 2026-11-18T09:00:00Z", "By: ba", "Evidence: spec.md",
                         "Source: events", "| REQ-AUTH-003 | 1a2b3c4d | added |"):
                self.assertIn(line, text)
            self.assertNotIn("Hashes: at archive", text)
            read = signoff.read_file(path)
            self.assertEqual(("git", "ba", "2026-11-18T09:00:00Z", "1a2b3c4d", False),
                             (read.source, read.actor, read.at, read.hash_of("REQ-AUTH-003"), read.waived))
            waiver = signoff.Signoff(at="2026-11-19T00:00:00Z", actor="lead", evidence="spike", source="events",
                                     requirements=None, waived=True)
            path.write_text(signoff.render(waiver, "ep-1", [{"id": "REQ-AUTH-003", "hash8": "1a2b3c4d", "op": "added"}],
                                           hashes_at_archive=True), encoding="utf-8")
            read = signoff.read_file(path)
            self.assertEqual((True, "spike", "lead", "2026-11-19T00:00:00Z"), (read.waived, read.evidence, read.actor, read.at))
            self.assertIn("Hashes: at archive", path.read_text(encoding="utf-8"))
            path.write_text("# Sign-off\n\nBy: ba\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                signoff.read_file(path)

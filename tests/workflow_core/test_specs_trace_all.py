"""`gin specs trace --all`: every requirement with its changes, sign-off, beads, cases, and tests."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specs_fixtures import (ADDED_BLOCK, AUTH_SPEC, LAUNCHER, commit_all, delta, make_change, make_repo,  # noqa: E402
                            write, write_activity)
from team_fixtures import fake_cli  # noqa: E402
from workflow_core import signoff, specs, specs_trace_all  # noqa: E402
from workflow_core.events import WorkflowEvent, WorkflowEventStore  # noqa: E402
from workflow_core.specs_archive import archive  # noqa: E402

TODAY = date(2026, 10, 3)
PROPOSED = ADDED_BLOCK.replace("REQ-AUTH-003", "REQ-AUTH-004").replace("Lock account after failed logins",
                                                                       "Second factor")
REMOVED = "### REQ-AUTH-002: Reject wrong password\n<!-- base: {base} -->\nReason: folded into REQ-AUTH-001\n"
TESTS_MD = ("| TC | REQ | type | evidence |\n|---|---|---|---|\n"
            "| TC-AUTH-003 | REQ-AUTH-003 | manual | passed |\n")


class TestTraceAll(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(Path(self.tmp.name) / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        write_activity(self.root)
        write(self.root, "docs/specs/README.md", "# Specs\n\n## Capabilities\n- [auth](auth/spec.md)\n")
        self.cfg = specs.sdd_config(specs.load_config(self.root))
        no_qa = mock.patch.object(specs_trace_all, "_gin_qa", return_value=None)
        no_qa.start()
        self.addCleanup(no_qa.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def signed_change(self, name: str, epic: str, spec_delta: str) -> Path:
        change = make_change(self.root, name, epic=epic, spec_delta=spec_delta)
        path = self.root / ".agent-workflow/runtime/events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        WorkflowEventStore(path).append(WorkflowEvent.create(
            event_type="requirement.confirmed", workflow_id=epic, actor="ba",
            payload={"evidence": name, "requirements": signoff.requirements_of(self.root, epic)}))
        return change

    def build(self) -> None:
        """REQ-AUTH-003 added and REQ-AUTH-002 removed by archived, signed changes; REQ-AUTH-004 proposed by an
        open, signed change; a test file names REQ-AUTH-001."""
        base = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-002")[1]
        lockout = self.signed_change("ep-1-lockout", "ep-1", delta(added=ADDED_BLOCK))
        write(self.root, "docs/changes/ep-1-lockout/05-tests.md", TESTS_MD)
        commit_all(self.root)
        archive(self.root, self.cfg, lockout, today=TODAY)
        cleanup = self.signed_change("ep-2-cleanup", "ep-2", delta(removed=REMOVED.format(base=base)))
        commit_all(self.root)
        archive(self.root, self.cfg, cleanup, today=TODAY)
        self.signed_change("ep-3-mfa", "ep-3", delta(added=PROPOSED))
        write(self.root, "tests/test_auth.py", "def test_sign_in():  # REQ-AUTH-001\n    pass\n")
        commit_all(self.root)

    def rows(self) -> dict[str, dict]:
        return {row["id"]: row for row in specs_trace_all.trace_all(self.root, self.cfg)["requirements"]}

    def test_living_proposed_and_removed_rows_carry_their_signoff(self):
        self.build()
        rows = self.rows()
        self.assertEqual({"REQ-AUTH-001": "living", "REQ-AUTH-002": "removed", "REQ-AUTH-003": "living",
                          "REQ-AUTH-004": "proposed"}, {req: row["state"] for req, row in rows.items()})
        lockout = rows["REQ-AUTH-003"]["signoff"]
        self.assertEqual(("git", "ep-1-lockout", True), (lockout["source"], lockout["change"], lockout["current"]))
        self.assertEqual([("ep-1-lockout", "ep-1", "added", "2026-10-03")],
                         [(c["change"], c["epic"], c["op"], c["archived"]) for c in rows["REQ-AUTH-003"]["changes"]])
        removed = rows["REQ-AUTH-002"]
        self.assertEqual((None, None, "git", "ep-2-cleanup", None),
                         (removed["hash8"], removed["source"], removed["signoff"]["source"],
                          removed["signoff"]["change"], removed["signoff"]["current"]))
        proposed = rows["REQ-AUTH-004"]
        self.assertEqual(("events", None, True),
                         (proposed["signoff"]["source"], proposed["changes"][0]["archived"], proposed["signoff"]["current"]))
        self.assertIsNone(rows["REQ-AUTH-001"]["signoff"])
        self.assertEqual(["tests/test_auth.py"], rows["REQ-AUTH-001"]["tests"])
        self.assertEqual(["docs/changes/archive/2026-10-03-ep-1-lockout/05-tests.md#TC-AUTH-003"],
                         rows["REQ-AUTH-003"]["tests"])

    def test_removed_rows_carry_the_reason_and_living_rows_none(self):
        self.build()
        rows = self.rows()
        self.assertEqual("folded into REQ-AUTH-001", rows["REQ-AUTH-002"]["reason"])
        self.assertIsNone(rows["REQ-AUTH-001"]["reason"])

    def test_a_living_retired_entry_is_a_removed_row(self):
        write(self.root, "docs/specs/auth/spec.md",
              AUTH_SPEC + "\n## Retired\n\n### REQ-AUTH-003: Lock out\nReason: dropped in review\n")
        row = self.rows()["REQ-AUTH-003"]
        self.assertEqual(("removed", None, None, "dropped in review"),
                         (row["state"], row["hash8"], row["source"], row["reason"]))

    def test_a_requirement_edited_after_signoff_is_stale(self):
        self.build()
        spec = self.root / "docs/specs/auth/spec.md"
        spec.write_text(spec.read_text(encoding="utf-8").replace("for 15 minutes", "for 30 minutes"),
                        encoding="utf-8")
        row = self.rows()["REQ-AUTH-003"]
        self.assertIs(False, row["signoff"]["current"])
        self.assertIn("signoff:stale", specs_trace_all.text_line(row))

    def test_beads_come_from_req_labels_and_gates_from_the_epic_bead(self):
        self.build()
        gates = {"requirement_confirmed": {"pr_url": "https://h/pull/3", "actor": "an@corp.com",
                                           "at": "2026-10-02T00:00:00Z"}}
        listed = [{"id": "ep-1.2", "title": "Lockout counter", "status": "closed", "labels": ["req:REQ-AUTH-003"]},
                  {"id": "ep-1.3", "title": "Other", "status": "open", "labels": ["req:REQ-AUTH-001"]},
                  {"id": "ep-3", "title": "MFA", "status": "open", "labels": [],
                   "metadata": {"gates": json.dumps(gates)}}]
        with mock.patch.object(specs_trace_all, "backend", return_value="beads"), \
                mock.patch.object(specs_trace_all, "query_result", return_value=(listed, None)):
            rows = self.rows()
        self.assertEqual([{"id": "ep-1.2", "title": "Lockout counter", "status": "closed"}], rows["REQ-AUTH-003"]["beads"])
        self.assertEqual([], rows["REQ-AUTH-004"]["beads"])
        self.assertEqual(("beads", "https://h/pull/3", None),
                         (rows["REQ-AUTH-004"]["signoff"]["source"], rows["REQ-AUTH-004"]["signoff"]["evidence"],
                          rows["REQ-AUTH-004"]["signoff"]["current"]))

    def test_cases_come_from_gin_qa_export(self):
        self.build()
        stub = fake_cli(Path(self.tmp.name) / "bin", "gin-qa", [{"argv": ["cases", "export"], "stdout": {"cases": [
            {"id": "TC-AUTH-002", "reqs": [{"id": "REQ-AUTH-001", "hash8": "x"}], "effective_result": "outdated"},
            {"id": "TC-AUTH-001", "reqs": [{"id": "REQ-AUTH-001", "hash8": "y"}], "effective_result": "passed"}]}}])
        with mock.patch.object(specs_trace_all, "_gin_qa", return_value=str(stub)):
            result = specs_trace_all.trace_all(self.root, self.cfg)
        rows = {row["id"]: row for row in result["requirements"]}
        self.assertEqual([{"id": "TC-AUTH-001", "effective_result": "passed"},
                          {"id": "TC-AUTH-002", "effective_result": "outdated"}], rows["REQ-AUTH-001"]["cases"])
        self.assertEqual([], rows["REQ-AUTH-003"]["cases"])
        self.assertEqual([], result["warnings"])

    def test_missing_sources_are_null_with_a_warning(self):
        self.build()
        result = specs_trace_all.trace_all(self.root, self.cfg)
        self.assertTrue(all(row["cases"] is None and row["beads"] is None for row in result["requirements"]))
        self.assertEqual(["cases: gin-qa not found on PATH"], result["warnings"])
        with mock.patch.object(specs_trace_all, "backend", return_value="beads"), \
                mock.patch.object(specs_trace_all, "query_result", return_value=(None, "bd not found")):
            self.assertIn("beads: bd not found", specs_trace_all.trace_all(self.root, self.cfg)["warnings"])

    def test_a_malformed_signoff_file_falls_back_to_the_event_log(self):
        self.build()
        (self.root / "docs/changes/archive/2026-10-03-ep-1-lockout/06-signoff.md").write_text("# Sign-off\n",
                                                                                           encoding="utf-8")
        result = specs_trace_all.trace_all(self.root, self.cfg)
        row = next(row for row in result["requirements"] if row["id"] == "REQ-AUTH-003")
        self.assertEqual("events", row["signoff"]["source"])
        self.assertTrue(any("06-signoff.md" in warning for warning in result["warnings"]))

    def test_a_block_outside_the_delta_sections_is_not_a_change(self):
        notes = ("# Spec Delta\n\n## Notes\n\n### REQ-AUTH-001: Sign in with password\n"
                 "The system SHALL sign a user in with a valid password.\n")
        make_change(self.root, "ep-5-notes", epic="ep-5", spec_delta=notes)
        result = specs_trace_all.trace_all(self.root, self.cfg)
        row = next(row for row in result["requirements"] if row["id"] == "REQ-AUTH-001")
        self.assertEqual([], row["changes"])
        self.assertTrue(any("outside ## ADDED/MODIFIED/REMOVED/RETIRED" in warning for warning in result["warnings"]))

    def test_an_open_modification_is_a_pending_change(self):
        base = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-002")[1]
        self.signed_change("ep-6-count", "ep-6", delta(modified=(
            f"### REQ-AUTH-002: Reject wrong password\n<!-- base: {base} -->\n"
            "The system SHALL reject a wrong password and count the failure.\n")))
        row = self.rows()["REQ-AUTH-002"]
        self.assertEqual("living", row["state"])
        self.assertEqual([("ep-6-count", "modified", None)],
                         [(c["change"], c["op"], c["archived"]) for c in row["changes"]])
        self.assertIs(False, row["signoff"]["current"])

    def test_a_proposal_without_an_epic_has_no_signoff(self):
        change = make_change(self.root, "ep-7-x", epic="ep-7")
        (change / "01-proposal.md").write_text("# X\n", encoding="utf-8")
        row = self.rows()["REQ-AUTH-003"]
        self.assertEqual("proposed", row["state"])
        self.assertIsNone(row["changes"][0]["epic"])
        self.assertIsNone(row["signoff"])

    def test_an_undated_archive_folder_is_skipped_with_a_warning(self):
        write(self.root, "docs/changes/archive/old-change/02-spec-delta.md", delta(added=ADDED_BLOCK))
        result = specs_trace_all.trace_all(self.root, self.cfg)
        self.assertIn("docs/changes/archive/old-change: archive folder has no YYYY-MM-DD- prefix; skipped",
                      result["warnings"])
        self.assertNotIn("REQ-AUTH-003", {row["id"] for row in result["requirements"]})

    def test_gin_qa_failures_are_warnings(self):
        bin_dir = Path(self.tmp.name) / "bin"
        for rule, expected in (({"argv": ["cases", "export"], "exit": 3, "stderr": "boom\n"},
                                "cases: gin-qa exited 3: boom"),
                               ({"argv": ["cases", "export"], "stdout": "not json"},
                                "cases: unreadable gin-qa output"),
                               ({"argv": ["cases", "export"], "stdout": {"cases": None}},
                                "cases: unreadable gin-qa output: cases is not a list")):
            with self.subTest(expected=expected):
                stub = fake_cli(bin_dir, "gin-qa", [rule])
                with mock.patch.object(specs_trace_all, "_gin_qa", return_value=str(stub)):
                    result = specs_trace_all.trace_all(self.root, self.cfg)
                self.assertTrue(all(row["cases"] is None for row in result["requirements"]))
                self.assertTrue(any(warning.startswith(expected) for warning in result["warnings"]),
                                result["warnings"])

    def test_legacy_layout_has_no_requirements(self):
        legacy = make_repo(Path(self.tmp.name) / "legacy", layout="legacy")
        cfg = specs.sdd_config(specs.load_config(legacy))
        self.assertEqual({"schema": 1, "layout": "legacy", "requirements": [], "warnings": [], "skipped": []},
                         specs_trace_all.trace_all(legacy, cfg))

    def test_cli_all_excludes_change_and_prints_json_and_text(self):
        self.build()

        def run(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run([sys.executable, str(LAUNCHER), "specs", "trace", *args, "--repository",
                                   str(self.root)], capture_output=True, text=True)

        self.assertEqual(2, run("--all", "--change", "ep-3").returncode)
        self.assertEqual(2, run().returncode)
        done = run("--all", "--format", "json")
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertEqual((1, "sdd"), (json.loads(done.stdout)["schema"], json.loads(done.stdout)["layout"]))
        self.assertIn("REQ-AUTH-004 proposed signoff:yes beads:- cases:", run("--all").stdout)

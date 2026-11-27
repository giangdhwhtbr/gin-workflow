"""`gin specs gaps`: requirement ids that were used and are gone without a `## Retired` entry."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specs_fixtures import (AUTH_SPEC, commit_all, delta, make_change, make_repo, write,  # noqa: E402
                            write_activity)
from workflow_core import specs, specs_cli, specs_gaps  # noqa: E402

REMOVED_REASON = "merged into REQ-AUTH-001"


class GapsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(Path(self.tmp.name) / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        write_activity(self.root)
        commit_all(self.root)
        self.cfg = specs.sdd_config(specs.load_config(self.root))

    def tearDown(self):
        self.tmp.cleanup()

    def drop_003_in_history(self):
        make_change(self.root)  # ADDED REQ-AUTH-003
        commit_all(self.root, "add REQ-AUTH-003")
        write(self.root, "docs/changes/ep-1-lockout/02-spec-delta.md", delta())
        commit_all(self.root, "drop REQ-AUTH-003")

    def archive_removed_002(self):
        write(self.root, "docs/changes/archive/2026-01-01-ep-0-merge/02-spec-delta.md",
              delta(removed=f"### REQ-AUTH-002: Reject wrong password\n<!-- base: {'0' * 64} -->\n"
                            f"Reason: {REMOVED_REASON}\n"))
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC.split("### REQ-AUTH-002")[0])
        commit_all(self.root, "archive ep-0")

    def test_lists_deleted_and_archived_ids_with_hints(self):
        self.drop_003_in_history()
        self.archive_removed_002()
        rows = specs_gaps.gaps(self.root, self.cfg, "auth")["gaps"]
        self.assertEqual(["REQ-AUTH-002", "REQ-AUTH-003"], [row["id"] for row in rows])
        self.assertEqual(("Reject wrong password", REMOVED_REASON, "2026-01-01-ep-0-merge", None),
                         (rows[0]["title"], rows[0]["reason"], rows[0]["change"], rows[0]["commit"]))
        self.assertEqual("", rows[1]["reason"])
        self.assertEqual(("drop REQ-AUTH-003", "Lock account after failed logins"),
                         (rows[1]["commit"]["subject"], rows[1]["commit"]["title"]))
        self.assertEqual(rows[1]["commit"]["title"], rows[1]["title"])

    def test_living_retired_and_added_ids_are_no_gaps(self):
        self.drop_003_in_history()
        make_change(self.root, "ep-2-again", epic="ep-2")  # ADDED REQ-AUTH-003 again
        self.assertEqual([], specs_gaps.gaps(self.root, self.cfg)["gaps"])
        write(self.root, "docs/changes/ep-2-again/02-spec-delta.md",
              delta(retired="### REQ-AUTH-003: Lock out\nReason: dropped\n"))
        self.assertEqual([], specs_gaps.gaps(self.root, self.cfg)["gaps"])

    def test_into_writes_retired_blocks_and_never_spec_md(self):
        self.drop_003_in_history()
        self.archive_removed_002()
        before = (self.root / "docs/specs/auth/spec.md").read_text(encoding="utf-8")
        change = make_change(self.root, "ep-3-gaps", epic="ep-3", spec_delta=delta())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = specs_cli.main(["gaps", "auth", "--into", "ep-3", "--repository", str(self.root),
                                   "--format", "json"])
        self.assertEqual(0, code)
        self.assertEqual(["REQ-AUTH-002", "REQ-AUTH-003"], json.loads(out.getvalue())["written"])
        text = (change / "02-spec-delta.md").read_text(encoding="utf-8")
        retired = text.split("## RETIRED", 1)[1]
        self.assertIn(f"### REQ-AUTH-002: Reject wrong password\nReason: {REMOVED_REASON}", retired)
        self.assertIn("### REQ-AUTH-003: Lock account after failed logins\nReason:\n", retired + "\n")
        errors = specs.lint_change(self.root, self.cfg, change)
        self.assertTrue(any("REQ-AUTH-003 needs a 'Reason: <why>' line" in e for e in errors), errors)
        self.assertFalse(any("REQ-AUTH-002 needs" in e for e in errors), errors)
        self.assertEqual(before, (self.root / "docs/specs/auth/spec.md").read_text(encoding="utf-8"))

    def test_text_output_and_unknown_change(self):
        self.drop_003_in_history()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(0, specs_cli.main(["gaps", "--repository", str(self.root)]))
        self.assertRegex(out.getvalue(), r"^REQ-AUTH-003 deleted in [0-9a-f]+ \d{4}-\d{2}-\d{2} "
                                         r"drop REQ-AUTH-003: Lock account after failed logins$")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, specs_cli.main(["gaps", "--into", "ep-9", "--repository", str(self.root)]))


if __name__ == "__main__":
    unittest.main()

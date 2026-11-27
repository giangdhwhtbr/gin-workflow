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

from specs_fixtures import (ADDED_BLOCK, AUTH_SPEC, commit_all, delta, git, make_change, make_repo,  # noqa: E402
                            write, write_activity)
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

    def test_unpushed_local_branch_that_adds_an_id_is_no_gap(self):
        git(self.root, "checkout", "-q", "-b", "feat-lockout")
        make_change(self.root)  # ADDED REQ-AUTH-003, on a branch no worktree has checked out
        commit_all(self.root, "add REQ-AUTH-003")
        git(self.root, "checkout", "-q", "main")
        self.assertEqual([], specs_gaps.gaps(self.root, self.cfg)["gaps"])

    def test_without_git_the_scan_warns(self):
        plain = Path(self.tmp.name) / "plain"
        write(plain, ".agent-workflow/config.yaml", "schema_version: '2.6'\nartifacts:\n  layout: sdd\n")
        write(plain, "docs/specs/auth/spec.md", AUTH_SPEC)
        result = specs_gaps.gaps(plain, specs.sdd_config(specs.load_config(plain)))
        self.assertIn("not a git repository; scanned this tree only", result["warnings"])

    def test_last_deletion_wins_over_a_newer_commit_that_only_adds(self):
        self.drop_003_in_history()
        write(self.root, "docs/changes/archive/2026-02-02-ep-1-lockout/02-spec-delta.md", delta(added=ADDED_BLOCK))
        commit_all(self.root, "archive REQ-AUTH-003")
        (row,) = specs_gaps.gaps(self.root, self.cfg)["gaps"]
        self.assertEqual(("REQ-AUTH-003", "drop REQ-AUTH-003", "deleted"),
                         (row["id"], row["commit"]["subject"], row["commit"]["action"]))

    def test_an_id_that_history_only_added_reads_last_changed(self):
        write(self.root, "docs/changes/archive/2026-02-02-ep-5-x/02-spec-delta.md", delta(added=ADDED_BLOCK))
        commit_all(self.root, "archive REQ-AUTH-003")
        (row,) = specs_gaps.gaps(self.root, self.cfg)["gaps"]
        self.assertEqual("changed", row["commit"]["action"])
        self.assertRegex(specs_gaps.text_line(row), r"^REQ-AUTH-003 last changed in [0-9a-f]+ \d{4}-\d{2}-\d{2} "
                                                    r"archive REQ-AUTH-003: Lock account after failed logins$")

    def test_title_comes_from_an_archived_block_when_no_commit_has_it(self):
        write(self.root, "docs/changes/archive/2026-02-02-ep-5-x/02-spec-delta.md", delta(added=ADDED_BLOCK))
        (row,) = specs_gaps.gaps(self.root, self.cfg)["gaps"]  # the archived folder is not committed
        self.assertEqual((None, "Lock account after failed logins"), (row["commit"], row["title"]))

    def test_into_appends_to_an_existing_retired_section(self):
        self.drop_003_in_history()
        change = make_change(self.root, "ep-3-gaps", epic="ep-3",
                             spec_delta=delta(retired="### REQ-AUTH-010: Old idea\nReason: kept\n"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(0, specs_cli.main(["gaps", "--into", "ep-3", "--repository", str(self.root)]))
        text = (change / "02-spec-delta.md").read_text(encoding="utf-8")
        self.assertEqual(1, text.count("## RETIRED"))
        self.assertLess(text.index("### REQ-AUTH-010: Old idea\nReason: kept"), text.index("### REQ-AUTH-003:"))
        self.assertTrue(out.getvalue().endswith("wrote 1 RETIRED blocks to ep-3-gaps\n"), out.getvalue())

    def test_a_bad_change_fails_before_the_scan(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, specs_cli.main(["gaps", "--into", "archive", "--repository", str(self.root)]))


if __name__ == "__main__":
    unittest.main()

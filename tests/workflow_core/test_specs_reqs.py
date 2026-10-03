"""`gin-workflow specs reqs`: requirement blocks as JSON for tools built on the specs, and the `qa:` config key."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specs_fixtures import (ADDED_BLOCK, AUTH_SPEC, LAUNCHER, commit_all, delta, make_change, make_repo,  # noqa: E402
                            write)


def reqs(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(LAUNCHER), "specs", "reqs", "--repository", str(root),
                           "--format", "json", *args], capture_output=True, text=True)


def specs(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(LAUNCHER), "specs", *args, "--repository", str(root)],
                          capture_output=True, text=True)


class TestSpecsReqs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(Path(self.tmp.name) / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)

    def tearDown(self):
        self.tmp.cleanup()

    def payload(self, *args: str) -> dict:
        result = reqs(self.root, *args)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def test_living_blocks_with_scenarios(self):
        payload = self.payload()
        self.assertEqual("sdd", payload["layout"])
        self.assertEqual({}, payload["qa"])
        self.assertIn("tests/**", payload["test_globs"])
        first = payload["requirements"][0]
        self.assertEqual(
            {"id": "REQ-AUTH-001", "title": "Sign in with password", "capability": "auth", "section": "LIVING",
             "change": None, "source": "docs/specs/auth/spec.md:9",
             "scenarios": [{"title": "valid password", "given": ["a registered user"],
                            "when": ["they submit the right password"], "then": ["they are signed in"]}]},
            {key: value for key, value in first.items() if key != "hash"})
        self.assertRegex(first["hash"], "^[0-9a-f]{64}$")
        self.assertEqual(["REQ-AUTH-001", "REQ-AUTH-002"], [row["id"] for row in payload["requirements"]])

    def test_and_bullets_continue_the_previous_step(self):
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC.replace(
            "- THEN they are signed in", "- THEN they are signed in\n- AND they see the dashboard"))
        scenario = self.payload()["requirements"][0]["scenarios"][0]
        self.assertEqual(["they are signed in", "they see the dashboard"], scenario["then"])

    def test_open_changes_follow_living_and_archive_is_skipped(self):
        modified = AUTH_SPEC.split("### REQ-AUTH-002")[1].replace("wrong password.", "wrong password twice.")
        make_change(self.root, spec_delta=delta(added=ADDED_BLOCK, modified="### REQ-AUTH-002" + modified))
        write(self.root, "docs/changes/archive/2026-01-01-ep-0-old/spec-delta.md",
              delta(added=ADDED_BLOCK.replace("003", "009")))
        rows = self.payload()["requirements"]
        self.assertEqual([("REQ-AUTH-001", "LIVING", None), ("REQ-AUTH-002", "LIVING", None),
                          ("REQ-AUTH-003", "ADDED", "ep-1-lockout"), ("REQ-AUTH-002", "MODIFIED", "ep-1-lockout")],
                         [(row["id"], row["section"], row["change"]) for row in rows])
        only = self.payload("--change", "ep-1")["requirements"]
        self.assertEqual(["REQ-AUTH-003", "REQ-AUTH-002"], [row["id"] for row in only])

    def test_delta_hash_equals_living_hash_after_archive(self):
        make_change(self.root)
        commit_all(self.root)
        before = {row["id"]: row["hash"] for row in self.payload()["requirements"]}
        archived = specs(self.root, "archive", "--change", "ep-1")
        self.assertEqual(0, archived.returncode, archived.stdout + archived.stderr)
        after = self.payload()["requirements"]
        self.assertEqual([("REQ-AUTH-003", "LIVING")], [(r["id"], r["section"]) for r in after if r["id"].endswith("3")])
        self.assertEqual(before, {row["id"]: row["hash"] for row in after})

    def test_removed_block_is_listed(self):
        removed = "### REQ-AUTH-002: Reject wrong password\n<!-- base: " + "0" * 64 + " -->\nReason: merged into 001\n"
        make_change(self.root, spec_delta=delta(removed=removed))
        rows = self.payload("--change", "ep-1")["requirements"]
        self.assertEqual([("REQ-AUTH-002", "REMOVED", [])], [(r["id"], r["section"], r["scenarios"]) for r in rows])

    def test_qa_key_is_passed_through_and_validated(self):
        config = self.root / ".agent-workflow/config.yaml"
        config.write_text(config.read_text() + "qa:\n  cases: tests-design/cases\n")
        self.assertEqual({"cases": "tests-design/cases"}, self.payload()["qa"])
        config.write_text(config.read_text() + "  other: x\n")
        result = reqs(self.root)
        self.assertEqual(2, result.returncode)
        self.assertIn("other", result.stderr)

    def test_legacy_layout_has_no_requirements(self):
        legacy = make_repo(Path(self.tmp.name) / "legacy", layout="legacy")
        result = reqs(legacy)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"layout": "legacy", "requirements": []},
                         {key: value for key, value in json.loads(result.stdout).items() if key in ("layout", "requirements")})
        self.assertEqual(2, reqs(legacy, "--change", "ep-1").returncode)

    def test_unknown_change_exits_2(self):
        result = reqs(self.root, "--change", "nope")
        self.assertEqual(2, result.returncode)
        self.assertIn("unknown change", result.stderr)


if __name__ == "__main__":
    unittest.main()

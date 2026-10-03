"""SDD specs core: blocks, hash, lint, next-id, new, hash/template commands, renumber."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specs_fixtures import (ADDED_BLOCK, AUTH_SPEC, LAUNCHER, commit_all, delta, git,  # noqa: E402
                            make_change, make_repo, write)
from workflow_core import specs  # noqa: E402
from workflow_core.specs import SpecsError  # noqa: E402


def run_specs(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(LAUNCHER), "specs", *args, "--repository", str(root)],
                          text=True, capture_output=True, check=False)


class TestBlocks(unittest.TestCase):
    def test_parse_blocks_sections_and_ranges(self):
        blocks, errors = specs.parse_blocks(AUTH_SPEC)
        self.assertEqual([], errors)
        self.assertEqual(["REQ-AUTH-001", "REQ-AUTH-002"], [b.id for b in blocks])
        self.assertEqual({"Requirements"}, {b.section for b in blocks})
        self.assertTrue(blocks[0].text.startswith("### REQ-AUTH-001: Sign in with password"))
        self.assertTrue(blocks[0].text.endswith("- THEN they are signed in"))
        self.assertEqual("auth", blocks[0].cap)

    def test_malformed_heading_is_reported(self):
        _, errors = specs.parse_blocks("## Requirements\n\n### Lockout\nThe system SHALL lock.\n")
        self.assertEqual(3, errors[0][0])

    def test_multi_word_capability(self):
        self.assertEqual("user-profile", specs.cap_of("REQ-USER-PROFILE-012"))
        with self.assertRaises(SpecsError):
            specs.cap_of("REQ-auth-1")

    def test_hash_ignores_base_line_and_trailing_space(self):
        plain = "### REQ-AUTH-001: X\nThe system SHALL x.\n"
        noisy = "\n### REQ-AUTH-001: X   \n<!-- base: " + "a" * 64 + " -->\nThe system SHALL x.\n\n"
        self.assertEqual(specs.block_hash(plain), specs.block_hash(noisy))
        self.assertNotEqual(specs.block_hash(plain), specs.block_hash(plain.replace("x.", "y.")))

    def test_lint_block_rules(self):
        block = specs.parse_blocks(ADDED_BLOCK)[0][0]
        self.assertEqual([], specs.lint_block(block))
        bare = specs.parse_blocks("### REQ-AUTH-009: X\nThe system locks.\n\n#### Scenario: s\n- GIVEN a\n- THEN b\n")[0][0]
        self.assertEqual(["REQ-AUTH-009: needs a SHALL or MUST statement", "REQ-AUTH-009: scenario 1 lacks WHEN"],
                         specs.lint_block(bare))
        none = specs.parse_blocks("### REQ-AUTH-009: X\nThe system MUST lock.\n")[0][0]
        self.assertEqual(["REQ-AUTH-009: needs at least one '#### Scenario:'"], specs.lint_block(none))


class TestRepositoryCommands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(Path(self.tmp.name) / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        self.cfg = specs.sdd_config(specs.load_config(self.root))

    def tearDown(self):
        self.tmp.cleanup()

    def test_sdd_config_defaults(self):
        self.assertEqual("docs/specs", self.cfg["specs"])
        self.assertEqual("chat", self.cfg["spec_review"])
        self.assertIn("**/test_*.py", self.cfg["test_globs"])

    def test_lint_living_ok_then_wrong_folder_and_duplicate(self):
        self.assertEqual([], specs.lint_living(self.root, self.cfg))
        write(self.root, "docs/specs/billing/spec.md", "# Billing\n\n## Requirements\n\n" + ADDED_BLOCK.replace("003", "001"))
        errors = specs.lint_living(self.root, self.cfg)
        self.assertTrue(any("REQ-AUTH-001 belongs in auth/spec.md" in e for e in errors), errors)
        self.assertTrue(any("REQ-AUTH-001 duplicates" in e for e in errors), errors)

    def test_lint_change_rules(self):
        change = make_change(self.root)
        self.assertEqual([], specs.lint_change(self.root, self.cfg, change))
        base = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-002")[1]
        bad = delta(added=ADDED_BLOCK.replace("003", "001"),
                    modified="### REQ-AUTH-002: Reject wrong password\nThe system SHALL reject.\n\n"
                             "#### Scenario: s\n- GIVEN a\n- WHEN b\n- THEN c\n",
                    removed=f"### REQ-AUTH-001: Sign in with password\n<!-- base: {base} -->\n")
        write(self.root, "docs/changes/ep-1-lockout/spec-delta.md", bad)
        errors = specs.lint_change(self.root, self.cfg, change)
        self.assertTrue(any("REQ-AUTH-001 already exists" in e for e in errors), errors)
        self.assertTrue(any("REQ-AUTH-002 needs '<!-- base: <hash> -->'" in e for e in errors), errors)
        self.assertTrue(any("REQ-AUTH-001 needs a 'Reason: <why>' line" in e for e in errors), errors)
        self.assertTrue(any("REQ-AUTH-001 appears twice" in e for e in errors), errors)

    def test_block_outside_delta_sections(self):
        change = make_change(self.root, spec_delta="# Delta\n\n## Other\n\n" + ADDED_BLOCK)
        self.assertTrue(any("outside ## ADDED/MODIFIED/REMOVED" in e for e in specs.lint_change(self.root, self.cfg, change)))

    def test_lint_against_base_flags_id_taken_on_base_but_not_own_change(self):
        make_change(self.root)
        commit_all(self.root)
        git(self.root, "checkout", "-q", "-b", "feature")
        other = make_change(self.root, "ep-2-other", epic="ep-2")
        self.assertEqual(["docs/changes/ep-2-other/spec-delta.md:5: REQ-AUTH-003 is already used on main"],
                         [e for e in specs.lint_change(self.root, self.cfg, other, against="main") if "already used" in e])
        own = self.root / "docs/changes/ep-1-lockout"
        self.assertEqual([], specs.lint_change(self.root, self.cfg, own, against="main"))

    def test_find_change_by_full_name_or_epic_prefix(self):
        change = make_change(self.root)
        self.assertEqual(change, specs.find_change(self.root, self.cfg, "ep-1-lockout"))
        self.assertEqual(change, specs.find_change(self.root, self.cfg, "ep-1"))
        with self.assertRaises(SpecsError):
            specs.find_change(self.root, self.cfg, "ep-9")

    def test_next_id_scans_tree_worktrees_and_remote(self):
        self.assertEqual("REQ-AUTH-003", specs.next_id(self.root, self.cfg, "auth")[0])
        self.assertEqual("REQ-BILLING-001", specs.next_id(self.root, self.cfg, "billing")[0])
        commit_all(self.root)
        worktree = Path(self.tmp.name) / "wt"
        git(self.root, "worktree", "add", "-q", "-b", "wt", str(worktree))
        make_change(worktree)
        self.assertEqual("REQ-AUTH-004", specs.next_id(self.root, self.cfg, "auth")[0])
        remote = Path(self.tmp.name) / "remote.git"
        git(Path(self.tmp.name), "init", "-q", "--bare", str(remote))
        git(self.root, "remote", "add", "origin", str(remote))
        git(self.root, "checkout", "-q", "-b", "pushed")
        write(self.root, "docs/changes/ep-5-x/spec-delta.md", delta(added=ADDED_BLOCK.replace("003", "007")))
        commit_all(self.root)
        git(self.root, "push", "-q", "origin", "pushed")
        git(self.root, "checkout", "-q", "main")
        self.assertEqual(("REQ-AUTH-008", []), specs.next_id(self.root, self.cfg, "auth"))

    def test_next_id_warns_without_remote(self):
        self.assertEqual(["no git remote; scanned local worktrees only"], specs.next_id(self.root, self.cfg, "auth")[1])

    def test_new_change_renders_templates_and_refuses_existing(self):
        change = specs.new_change(self.root, self.cfg, "lockout", "ep-1", "Account lockout")
        self.assertEqual(sorted(specs.CHANGE_TEMPLATES), sorted(p.name for p in change.iterdir()))
        proposal = (change / "proposal.md").read_text(encoding="utf-8")
        self.assertIn("# Account lockout", proposal)
        self.assertEqual("ep-1", specs.change_epic(change))
        with self.assertRaises(SpecsError):
            specs.new_change(self.root, self.cfg, "lockout", "ep-1")
        with self.assertRaises(SpecsError):
            specs.new_change(self.root, self.cfg, "Bad Slug", "ep-1")

    def test_project_template_overrides_plugin(self):
        write(self.root, ".agent-workflow/templates/proposal.md", "# {{title}} (team)\n\nEpic: {{epic}}\n")
        change = specs.new_change(self.root, self.cfg, "lockout", "ep-1", "Lockout")
        self.assertEqual("# Lockout (team)\n\nEpic: ep-1\n", (change / "proposal.md").read_text(encoding="utf-8"))

    def test_renumber_rewrites_change_tests_and_bead_labels(self):
        make_change(self.root)
        commit_all(self.root)
        git(self.root, "checkout", "-q", "-b", "feature")
        write(self.root, "tests/test_lockout.py", "def test_lock():  # REQ-AUTH-003\n    pass\n# REQ-AUTH-0030\n")
        write(self.root, "src/app.py", "# REQ-AUTH-003\n")
        commit_all(self.root)
        change = self.root / "docs/changes/ep-1-lockout"
        calls = []

        def fake_bd(_root, argv):
            calls.append(argv)
            return [{"id": "ep-1.1"}] if argv[0] == "list" else ""

        with mock.patch("workflow_core.specs._bd", fake_bd):
            result = specs.renumber(self.root, self.cfg, change, "REQ-AUTH-003", "REQ-AUTH-004", against="main")
        self.assertEqual(["docs/changes/ep-1-lockout/spec-delta.md", "tests/test_lockout.py"], result["files"])
        self.assertIn("# REQ-AUTH-0030", (self.root / "tests/test_lockout.py").read_text(encoding="utf-8"))
        self.assertIn("REQ-AUTH-004", (self.root / "tests/test_lockout.py").read_text(encoding="utf-8"))
        self.assertEqual("# REQ-AUTH-003\n", (self.root / "src/app.py").read_text(encoding="utf-8"))
        self.assertEqual(["list", "--parent", "ep-1", "--label", "req:REQ-AUTH-003", "--all", "--limit", "0", "--json"],
                         calls[0])
        self.assertEqual(["update", "ep-1.1", "--remove-label", "req:REQ-AUTH-003", "--add-label", "req:REQ-AUTH-004"],
                         calls[1])

    def test_renumber_refuses_taken_id(self):
        change = make_change(self.root)
        with self.assertRaises(SpecsError):
            specs.renumber(self.root, self.cfg, change, "REQ-AUTH-003", "REQ-AUTH-002", against="HEAD")


class TestSpecsCli(unittest.TestCase):
    def test_exit_codes_and_layout_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_repo(Path(directory), layout="legacy")
            result = run_specs(root, "lint")
            self.assertEqual(2, result.returncode)
            self.assertIn("artifacts.layout is 'legacy'", result.stderr)
            self.assertEqual(0, run_specs(root, "template", "proposal.md").returncode)
        with tempfile.TemporaryDirectory() as directory:
            root = make_repo(Path(directory))
            write(root, "docs/specs/auth/spec.md", AUTH_SPEC)
            self.assertEqual(0, run_specs(root, "lint").returncode)
            self.assertEqual("REQ-AUTH-003", run_specs(root, "next-id", "auth").stdout.strip())
            hashed = run_specs(root, "hash", "REQ-AUTH-001", "--format", "json")
            self.assertEqual(64, len(json.loads(hashed.stdout)["hash"]))
            created = run_specs(root, "new", "lockout", "--epic", "ep-1")
            self.assertEqual("docs/changes/ep-1-lockout", created.stdout.strip())
            write(root, "docs/changes/ep-1-lockout/spec-delta.md", delta(added="### REQ-AUTH-003: X\nNo statement.\n"))
            linted = run_specs(root, "lint", "--change", "ep-1", "--format", "json")
            self.assertEqual(1, linted.returncode)
            self.assertEqual("findings", json.loads(linted.stdout)["status"])
            self.assertEqual(2, run_specs(root, "lint", "--change", "nope").returncode)


if __name__ == "__main__":
    unittest.main()

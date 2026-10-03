"""Legacy .planning -> SDD docs/ migration, and the setup preset/doctor SDD report."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specs_fixtures import LAUNCHER, commit_all, git, make_repo, write  # noqa: E402
from workflow_core import specs  # noqa: E402
from workflow_core.specs_migrate import migrate, plan_moves, sdd_report  # noqa: E402


def run_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(LAUNCHER), *args, "--repository", str(root)],
                          text=True, capture_output=True, check=False)


class TestMigrate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(Path(self.tmp.name) / "repo", layout="legacy")
        self.assertEqual(0, run_cli(self.root, "setup", "refresh").returncode)
        write(self.root, ".planning/specs/2026-10-01-rules-design.md", "# Rules design\n")
        write(self.root, ".planning/plans/2026-10-02-rules.md", "# Rules plan\n")
        write(self.root, ".planning/specs/2026-09-01-lonely-design.md", "# Lonely\n")
        write(self.root, ".planning/plans/notes.md", "# Notes\n")
        write(self.root, ".planning/codebase/OVERVIEW.md", "# Overview\n")
        write(self.root, ".planning/reviews/x/review.json", "{}\n")
        commit_all(self.root)
        self.config = specs.load_config(self.root)
        self.cfg = specs.sdd_config(self.config)

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_pairs_by_slug_and_lists_skipped(self):
        plan = plan_moves(self.root, self.config, self.cfg)
        self.assertEqual([
            {"from": ".planning/specs/2026-09-01-lonely-design.md", "to": "docs/changes/archive/2026-09-01-lonely/design.md"},
            {"from": ".planning/specs/2026-10-01-rules-design.md", "to": "docs/changes/archive/2026-10-01-rules/design.md"},
            {"from": ".planning/plans/2026-10-02-rules.md", "to": "docs/changes/archive/2026-10-01-rules/plan.md"},
            {"from": ".planning/codebase", "to": "docs/codebase"},
        ], plan["moves"])
        self.assertEqual([".planning/plans/notes.md"], plan["skipped"])

    def test_dry_run_changes_nothing(self):
        result = run_cli(self.root, "specs", "migrate", "--dry-run", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("planned", json.loads(result.stdout)["status"])
        self.assertEqual("", git(self.root, "status", "--porcelain"))

    def test_migrate_moves_with_git_and_switches_layout(self):
        result = run_cli(self.root, "specs", "migrate", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.root / "docs/changes/archive/2026-10-01-rules/plan.md").is_file())
        self.assertTrue((self.root / "docs/codebase/OVERVIEW.md").is_file())
        self.assertTrue((self.root / ".planning/reviews/x/review.json").is_file())
        self.assertTrue((self.root / ".planning/plans/notes.md").is_file())
        self.assertTrue((self.root / "docs/specs/README.md").is_file())
        status = git(self.root, "status", "--porcelain").splitlines()
        self.assertIn("R  .planning/plans/2026-10-02-rules.md -> docs/changes/archive/2026-10-01-rules/plan.md", status)
        self.assertEqual("sdd", specs.sdd_config(specs.load_config(self.root))["layout"])
        again = run_cli(self.root, "specs", "migrate")
        self.assertEqual(2, again.returncode)

    def test_refusals(self):
        write(self.root, "dirty.txt", "x\n")
        result = migrate(self.root, self.config, self.cfg, dry_run=False, force=True)
        self.assertEqual("refused", result["status"])
        self.assertIn("uncommitted changes; commit or set them aside first", result["refusals"])
        (self.root / "dirty.txt").unlink()
        with mock.patch("workflow_core.specs_migrate.in_flight_workflows", return_value=["wf-1"]):
            blocked = migrate(self.root, self.config, self.cfg, dry_run=False, force=False)
            self.assertEqual(["workflow wf-1 is approved but not shipped (use --force to migrate anyway)"],
                             blocked["refusals"])
            self.assertTrue((self.root / ".planning/plans/2026-10-02-rules.md").is_file())
            forced = migrate(self.root, self.config, self.cfg, dry_run=False, force=True)
        self.assertEqual("migrated", forced["status"])

    def test_in_flight_reads_recorded_gates(self):
        from workflow_core.specs_migrate import in_flight_workflows

        self.assertEqual([], in_flight_workflows(self.root))
        recorded = run_cli(self.root, "record", "plan-approved", "--workflow-id", "wf-1", "--evidence", "p.md",
                           "--actor", "u")
        self.assertEqual(0, recorded.returncode, recorded.stderr)
        with mock.patch("workflow_core.lifecycle_cli._beads_json", return_value=None):
            self.assertEqual(["wf-1"], in_flight_workflows(self.root))

    def test_open_worktree_refuses(self):
        git(self.root, "worktree", "add", "-q", "-b", "t1", str(self.root / ".planning/worktrees/t1"))
        result = migrate(self.root, self.config, self.cfg, dry_run=True, force=False)
        self.assertTrue(any(r.startswith("worktree open at") for r in result["refusals"]), result["refusals"])


class TestSddReport(unittest.TestCase):
    def test_legacy_suggests_migration_and_sdd_flags_foreign_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            defaults = dict(specs.SDD_DEFAULTS)
            self.assertEqual({"layout": "legacy"}, sdd_report(root, {}, defaults))
            write(root, ".planning/specs/2026-10-01-x-design.md", "# x\n")
            self.assertIn("migrate-specs", sdd_report(root, {}, defaults)["suggestion"])
            write(root, "docs/specs/login.spec.ts", "test()\n")
            write(root, "docs/specs/auth/spec.md", "# Auth\n")
            report = sdd_report(root, {}, defaults, proposed=True)
            self.assertEqual(["login.spec.ts"], report["conflict"]["files"])

    def test_setup_preset_proposes_sdd_only_for_greenfield(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            green = json.loads(run_cli(root, "setup", "preset", "--project-stage", "greenfield", "--format", "json").stdout)
            self.assertIn('artifacts.layout="sdd"', green["assignments"])
            self.assertEqual({"layout": "sdd"}, green["sdd"])
            brown = json.loads(run_cli(root, "setup", "preset", "--project-stage", "brownfield", "--format", "json").stdout)
            self.assertFalse(any(a.startswith("artifacts.layout") for a in brown["assignments"]))
            self.assertEqual({"layout": "legacy"}, brown["sdd"])

    def test_doctor_reports_sdd_without_changing_health(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(0, run_cli(root, "setup", "init", "--approve", "--non-interactive").returncode)
            write(root, ".planning/plans/2026-10-01-x.md", "# x\n")
            payload = json.loads(run_cli(root, "setup", "doctor", "--format", "json").stdout)
            self.assertEqual("legacy", payload["checks_details"]["sdd"]["layout"])
            self.assertTrue(any(a.startswith("sdd: run /gin-workflow:migrate-specs") for a in payload["actions"]))
            self.assertNotIn("sdd", payload["checks"])


if __name__ == "__main__":
    unittest.main()

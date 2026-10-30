import contextlib
from datetime import date
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import TEAM, make_team_repo  # noqa: E402
from workflow_core import milestone_cli, team_beads  # noqa: E402

CLI = SCRIPTS / "gin-workflow"
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@t"}


TEAM_TEXT = TEAM.format(host="github") + "  permissions:\n    milestone: [ba]\n"


def gw(cwd, *argv):
    return subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=ENV, text=True, capture_output=True)


def make_template(directory, *assignments):
    root = Path(directory)
    (root / ".claude").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=root, env=ENV, check=True)
    sets = [arg for value in assignments for arg in ("--set", value)]
    done = gw(root, "setup", "init", "--harness", "claude", "--non-interactive", "--approve", *sets)
    assert done.returncode == 0, done.stdout + done.stderr
    return root


@unittest.skipUnless(shutil.which("bd"), "bd is not installed")
class MilestoneCliTests(unittest.TestCase):
    today = date(2026, 10, 29)

    @classmethod
    def setUpClass(cls):
        cls._templates = tempfile.TemporaryDirectory()
        base = Path(cls._templates.name)
        cls.beads_template = make_template(base / "beads", "providers.task_tracking=beads")
        cls.markdown_template = make_template(base / "markdown")

    @classmethod
    def tearDownClass(cls):
        cls._templates.cleanup()

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = self.copy_template(self.beads_template, "repo")
        subprocess.run(["bd", "init", "--prefix", "t", "-q"], cwd=self.root, check=True, capture_output=True,
                       stdin=subprocess.DEVNULL, timeout=60)

    def copy_template(self, template, name):
        root = Path(self._directory.name) / name
        shutil.copytree(template, root)
        return root

    def bd(self, *args):
        done = subprocess.run(["bd", *args], cwd=self.root, text=True, capture_output=True, check=True,
                              stdin=subprocess.DEVNULL, timeout=60)
        return done.stdout

    def run_cli(self, *argv, root=None):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(milestone_cli, "_today", return_value=self.today), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = milestone_cli.main([*argv, "--repository", str(root or self.root)])
        return code, out.getvalue(), err.getvalue()

    def epic(self, bead_id, title, parent, *extra):
        # bd 1.0.5 rejects `create --id` together with `--parent`, so attach the parent afterwards.
        self.bd("create", title, "--id", bead_id, "--type", "epic", *extra)
        self.bd("update", bead_id, "--parent", parent)

    def seed(self):
        self.bd("create", "M1", "--id", "t-m1", "--type", "milestone",
                "--metadata", '{"start":"2026-11-02","end":"2026-11-04"}')
        self.epic("t-a", "A", "t-m1", "--estimate", "1440")
        self.epic("t-b", "B", "t-m1", "--estimate", "960")
        self.bd("dep", "add", "t-b", "t-a")

    def test_req_011_show_exact_payload(self):
        self.seed()
        code, out, err = self.run_cli("show", "t-m1", "--json")
        self.assertEqual(0, code, err)
        self.assertEqual({
            "schema": 1, "id": "t-m1", "title": "M1", "description": "", "status": "planned",
            "start": "2026-11-02", "end": "2026-11-04", "kickoff": None, "schedule_start": "2026-11-02",
            "preview": False, "today": "2026-10-29", "finish": "2026-11-06", "overflow_days": 2,
            "epics": [
                {"id": "t-a", "title": "A", "status": "open", "estimate_days": 3, "planned_start": "2026-11-02",
                 "planned_end": "2026-11-04", "depends_on": [], "external_depends_on": [], "warnings": []},
                {"id": "t-b", "title": "B", "status": "open", "estimate_days": 2, "planned_start": "2026-11-05",
                 "planned_end": "2026-11-06", "depends_on": ["t-a"], "external_depends_on": [],
                 "warnings": [{"code": "overflow", "days": 2}]}]}, json.loads(out))

    def test_req_011_list_exact_payload(self):
        self.seed()
        code, out, err = self.run_cli("list", "--json")
        self.assertEqual(0, code, err)
        self.assertEqual({
            "schema": 1, "today": "2026-10-29", "unassigned_epics": 0,
            "milestones": [{"id": "t-m1", "title": "M1", "status": "planned", "start": "2026-11-02",
                            "end": "2026-11-04", "kickoff": None, "finish": "2026-11-06",
                            "epics": {"total": 2, "closed": 0}, "warnings": 1, "error": None}]}, json.loads(out))

    def test_req_009_preview_does_not_write(self):
        self.seed()
        before = self.bd("show", "t-m1", "--json")
        code, out, err = self.run_cli("show", "t-m1", "--start", "2026-11-16", "--json")
        self.assertEqual(0, code, err)
        payload = json.loads(out)
        self.assertEqual(("2026-11-16", True), (payload["schedule_start"], payload["preview"]))
        self.assertEqual(before, self.bd("show", "t-m1", "--json"))

    def test_req_011_cycle_fails_show_but_not_list(self):
        self.seed()
        self.bd("create", "M2", "--id", "t-m2", "--type", "milestone",
                "--metadata", '{"start":"2026-12-01","end":"2026-12-31"}')
        for name in ("x", "y"):
            self.epic(f"t-{name}", name.upper(), "t-m2")
        self.bd("dep", "add", "t-x", "t-y")
        # bd 1.0.5 refuses to store a cycle (even with --no-cycle-check or via import), so add the
        # second edge to the rows the CLI reads; a cycle can still arrive from a hand-edited shared database.
        real = milestone_cli._beads(self.root)
        real["t-y"]["dependencies"] = [{"issue_id": "t-y", "depends_on_id": "t-x", "type": "blocks"}]
        patch = mock.patch.object(milestone_cli, "_beads", return_value=real)
        patch.start()
        self.addCleanup(patch.stop)
        code, _, err = self.run_cli("show", "t-m2", "--json")
        self.assertEqual(1, code)
        self.assertIn("dependency cycle", err)
        code, out, err = self.run_cli("list", "--json")
        self.assertEqual(0, code, err)
        errors = {entry["id"]: entry["error"] for entry in json.loads(out)["milestones"]}
        self.assertIsNone(errors["t-m1"])
        self.assertIn("dependency cycle", errors["t-m2"])

    def test_show_unknown_id_or_epic_exits_1_naming_the_id(self):
        self.seed()
        for bead_id in ("t-nope", "t-a"):
            code, _, err = self.run_cli("show", bead_id, "--json")
            self.assertEqual(1, code)
            self.assertIn(bead_id, err)

    def test_show_rejects_a_bad_start_date(self):
        self.seed()
        code, _, err = self.run_cli("show", "t-m1", "--start", "soon", "--json")
        self.assertEqual(1, code)
        self.assertIn("not an ISO date", err)

    def test_list_text_output(self):
        self.seed()
        code, out, err = self.run_cli("list")
        self.assertEqual(0, code, err)
        self.assertIn("t-m1", out)
        self.assertIn("unassigned roadmap epics: 0", out)

    def test_req_011_list_text_with_bad_kickoff(self):
        self.bd("create", "Bad", "--id", "t-bad", "--type", "milestone",
                "--metadata", '{"start":"2026-11-02","end":"2026-11-04","kickoff":"garbage"}')
        self.bd("create", "Good", "--id", "t-good", "--type", "milestone",
                "--metadata", '{"start":"2026-12-01","end":"2026-12-31"}')
        code, out, err = self.run_cli("list")
        self.assertEqual(0, code, err)
        self.assertIn("t-bad", out)
        self.assertIn("t-good", out)
        self.assertIn("error:", out)

    def show(self, bead_id):
        return json.loads(self.bd("show", bead_id, "--json"))[0]

    def seed_writes(self):
        self.bd("create", "M1", "--id", "t-m1", "--type", "milestone",
                "--metadata", '{"start":"2026-11-02","end":"2026-11-30"}')
        self.bd("create", "M2", "--id", "t-m2", "--type", "milestone",
                "--metadata", '{"start":"2026-12-01","end":"2026-12-31"}')
        self.bd("create", "MC", "--id", "t-mc", "--type", "milestone",
                "--metadata", '{"start":"2026-01-01","end":"2026-01-31"}')
        self.epic("t-a", "A", "t-m1")
        self.epic("t-ac", "AC", "t-mc")
        self.bd("create", "task", "--id", "t-task", "--type", "task")
        self.bd("create", "E0", "--id", "t-e0", "--type", "epic")
        self.epic("t-x", "X", "t-e0")

    def refused(self, *argv):
        before = self.bd("list", "--all", "--limit", "0", "--json")
        code, _, err = self.run_cli(*argv)
        self.assertEqual(1, code, err)
        self.assertEqual(before, self.bd("list", "--all", "--limit", "0", "--json"))
        return err

    def test_req_001_create(self):
        code, out, err = self.run_cli("create", "M1", "--start", "2026-11-02", "--end", "2026-12-18")
        self.assertEqual(0, code, err)
        bead = self.show(out.strip())
        self.assertEqual("milestone", bead["issue_type"])
        self.assertEqual({"start": "2026-11-02", "end": "2026-12-18"}, bead["metadata"])
        self.assertFalse(bead.get("labels"))
        code, shown, _ = self.run_cli("show", bead["id"], "--json")
        self.assertEqual("planned", json.loads(shown)["status"])

    def test_req_001_create_refusals(self):
        err = self.refused("create", "M1", "--start", "2026-12-18", "--end", "2026-11-02")
        self.assertIn("2026-12-18", err)
        self.assertIn("2026-11-02", err)
        self.refused("create", "M1", "--start", "2026-13-01", "--end", "2026-12-18")

    def test_req_002_update(self):
        self.seed_writes()
        code, _, err = self.run_cli("update", "t-m1", "--end", "2027-01-15")
        self.assertEqual(0, code, err)
        self.assertEqual({"start": "2026-11-02", "end": "2027-01-15"}, self.show("t-m1")["metadata"])
        self.refused("update", "t-m1", "--start", "2027-02-01")
        self.bd("close", "t-ac")
        self.bd("close", "t-mc")
        self.refused("update", "t-mc", "--title", "Y")
        self.refused("update", "t-a", "--title", "X")

    def test_req_003_kickstart(self):
        self.seed_writes()
        self.assertEqual(0, self.run_cli("kickstart", "t-m1", "--date", "2026-11-16")[0])
        self.assertEqual("2026-11-16", self.show("t-m1")["metadata"]["kickoff"])
        status = lambda: json.loads(self.run_cli("show", "t-m1", "--json")[1])["status"]
        self.assertEqual("scheduled", status())
        self.assertEqual(0, self.run_cli("kickstart", "t-m1", "--date", "2026-10-26")[0])
        self.assertEqual("active", status())
        self.assertEqual(0, self.run_cli("kickstart", "t-m1")[0])
        self.assertEqual({"start": "2026-11-02", "end": "2026-11-30", "kickoff": "2026-10-29"},
                         self.show("t-m1")["metadata"])
        self.bd("close", "t-ac")
        self.bd("close", "t-mc")
        self.refused("kickstart", "t-mc")

    def test_req_005_move(self):
        self.seed_writes()
        self.assertEqual(0, self.run_cli("move", "t-a", "--to", "t-m2")[0])
        self.assertEqual("t-m2", self.show("t-a")["parent"])
        self.assertEqual(0, self.run_cli("move", "t-a", "--to", "none")[0])
        self.assertIsNone(self.show("t-a").get("parent"))
        self.refused("move", "t-a", "t-task", "--to", "t-m1")
        self.refused("move", "t-a", "--to", "t-task")
        self.assertIn("t-e0", self.refused("move", "t-x", "--to", "t-m1"))
        self.bd("close", "t-ac")
        self.bd("close", "t-mc")
        self.refused("move", "t-ac", "--to", "t-m2")
        self.refused("move", "t-ac", "--to", "none")
        self.refused("move", "t-a", "--to", "t-mc")
        self.epic("t-b", "B", "t-m1")
        self.bd("close", "t-b")
        self.assertEqual(0, self.run_cli("move", "t-b", "--to", "t-m2")[0])

    def test_req_005_partial_move_names_moved_and_failed(self):
        self.seed_writes()
        self.epic("t-b", "B", "t-m1")
        real, calls = milestone_cli._bd, []

        def flaky(root, argv, actor=""):
            if argv[0] == "update":
                calls.append(argv)
                if len(calls) == 2:
                    raise milestone_cli.MilestoneError("boom")
            return real(root, argv, actor)

        with mock.patch.object(milestone_cli, "_bd", flaky):
            code, _, err = self.run_cli("move", "t-a", "t-b", "--to", "t-m2")
        self.assertEqual(1, code)
        self.assertIn("moved t-a", err)
        self.assertIn("t-b failed", err)

    def test_req_006_estimate(self):
        self.seed_writes()
        self.assertEqual(0, self.run_cli("estimate", "t-a", "5")[0])
        self.assertEqual(2400, self.show("t-a")["estimated_minutes"])
        for bad in ("0", "-1", "1.5", "x"):
            self.assertEqual(1, self.run_cli("estimate", "t-a", bad)[0])
            self.assertEqual(2400, self.show("t-a")["estimated_minutes"])
        self.refused("estimate", "t-m1", "3")

    def test_req_010_close(self):
        self.seed_writes()
        self.assertIn("t-a", self.refused("close", "t-m1"))
        self.assertEqual("open", self.show("t-m1")["status"])
        self.bd("close", "t-a")
        self.assertEqual(0, self.run_cli("close", "t-m1")[0])
        self.assertEqual("closed", self.show("t-m1")["status"])

    def test_usage_error_exits_2(self):
        code, _, _ = self.run_cli("show")
        self.assertEqual(2, code)

    def test_req_014_markdown_tracking_exits_1(self):
        root = self.copy_template(self.markdown_template, "markdown-repo")
        code, out, err = self.run_cli("list", "--json", root=root)
        self.assertEqual(1, code)
        self.assertEqual("", out)
        self.assertIn("providers.task_tracking: beads", err)



@unittest.skipUnless(shutil.which("bd"), "bd is not installed")
class MilestoneTeamTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)

    def repo(self, name, email, team=TEAM_TEXT):
        root = make_team_repo(Path(self._directory.name) / name, email=email, team=team)
        self.bd(root, "init", "--prefix", "t", "-q")
        self.bd(root, "create", "M1", "--id", "t-m1", "--type", "milestone",
                "--metadata", '{"start":"2026-11-02","end":"2026-11-04"}')
        return root

    def bd(self, root, *args):
        return subprocess.run(["bd", *args], cwd=root, text=True, capture_output=True, check=True,
                              stdin=subprocess.DEVNULL, timeout=60).stdout

    def metadata(self, root, bead_id):
        return json.JSONDecoder().raw_decode(self.bd(root, "show", bead_id, "--json").lstrip())[0][0].get("metadata")

    def run_cli(self, root, *argv):
        err = io.StringIO()
        with mock.patch.object(milestone_cli, "_today", return_value=date(2026, 10, 29)), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = milestone_cli.main([*argv, "--repository", str(root)])
        return code, err.getvalue()

    def test_req_012_milestone_writes_need_a_permitted_role(self):
        root = self.repo("dev", "em@corp.com")
        code, err = self.run_cli(root, "kickstart", "t-m1")
        self.assertEqual(2, code)
        self.assertIn("ba", err)
        self.assertNotIn("kickoff", self.metadata(root, "t-m1") or {})
        self.assertEqual(0, self.run_cli(self.repo("ba", "an@corp.com"), "kickstart", "t-m1")[0])
        open_team = self.repo("open", "em@corp.com", TEAM.format(host="github"))
        self.assertEqual(0, self.run_cli(open_team, "kickstart", "t-m1")[0])

    def test_req_016_rejected_push_keeps_the_local_write(self):
        root = self.repo("ba", "an@corp.com", TEAM_TEXT + "  beads_sync: {remote: x}\n")
        with mock.patch.object(team_beads, "sync", return_value={"status": "synced"}), \
                mock.patch.object(team_beads, "push", side_effect=team_beads.SyncConflict("rejected")):
            code, err = self.run_cli(root, "kickstart", "t-m1", "--date", "2026-11-16")
        self.assertEqual(1, code)
        self.assertIn("kickoff written locally but not pushed", err)
        self.assertEqual("2026-11-16", self.metadata(root, "t-m1")["kickoff"])

    def test_req_016_failed_pull_writes_nothing(self):
        root = self.repo("ba", "an@corp.com", TEAM_TEXT + "  beads_sync: {remote: x}\n")
        with mock.patch.object(team_beads, "sync", side_effect=team_beads.SyncConflict("conflict")), \
                mock.patch.object(team_beads, "push") as push:
            code, err = self.run_cli(root, "create", "M2", "--start", "2026-12-01", "--end", "2026-12-31")
        self.assertEqual(1, code)
        self.assertIn("nothing written", err)
        push.assert_not_called()
        rows = json.JSONDecoder().raw_decode(self.bd(root, "list", "--all", "--json").lstrip())[0]
        self.assertEqual(["t-m1"], [row["id"] for row in rows])

if __name__ == "__main__":
    unittest.main()

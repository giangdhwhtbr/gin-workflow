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

from workflow_core import milestone_cli  # noqa: E402

CLI = SCRIPTS / "gin-workflow"
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@t"}


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

    def test_usage_error_exits_2(self):
        code, _, _ = self.run_cli("show")
        self.assertEqual(2, code)

    def test_req_014_markdown_tracking_exits_1(self):
        root = self.copy_template(self.markdown_template, "markdown-repo")
        code, out, err = self.run_cli("list", "--json", root=root)
        self.assertEqual(1, code)
        self.assertEqual("", out)
        self.assertIn("providers.task_tracking: beads", err)


if __name__ == "__main__":
    unittest.main()

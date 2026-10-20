import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core import tasks  # noqa: E402
from workflow_core.configuration import ConfigValidationError, validate_portable_config  # noqa: E402

CLI = SCRIPTS / "gin-workflow"
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@t"}


def gw(cwd, *argv):
    return subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=ENV, text=True, capture_output=True)


class TaskDispatchTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name) / "repo"
        (self.root / ".claude").mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=self.root, env=ENV, check=True)

    def tearDown(self):
        self._directory.cleanup()

    def init(self, *assignments):
        sets = [arg for value in assignments for arg in ("--set", value)]
        done = gw(self.root, "setup", "init", "--harness", "claude", "--non-interactive", "--approve", *sets)
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)

    def test_backend_defaults_to_beads_without_setup_or_setting(self):
        self.assertEqual("beads", tasks.backend(self.root))
        self.init()
        self.assertEqual("beads", tasks.backend(self.root))

    def test_beads_passes_argv_through_to_bd_unchanged(self):
        argv = ["update", "x-1", "--status", "in_progress", "--json"]
        with mock.patch("workflow_core.tasks.backend", return_value="beads"), \
                mock.patch("workflow_core.tasks.shutil.which", return_value="/opt/bd"), \
                mock.patch("workflow_core.tasks.subprocess.run",
                           return_value=subprocess.CompletedProcess([], 7)) as run:
            self.assertEqual(7, tasks.main(argv))
        run.assert_called_once_with(["/opt/bd", *argv], check=False)

    def test_beads_query_matches_the_previous_bd_call(self):
        done = subprocess.CompletedProcess([], 0, stdout='[{"id": "x-1", "status": "closed"}]')
        with mock.patch("workflow_core.tasks.backend", return_value="beads"), \
                mock.patch("workflow_core.tasks.shutil.which", return_value="/opt/bd"), \
                mock.patch("workflow_core.tasks.subprocess.run", return_value=done) as run:
            self.assertEqual([{"id": "x-1", "status": "closed"}], tasks.query(self.root, ["show", "x-1"]))
        run.assert_called_once_with(["/opt/bd", "show", "x-1", "--json"], cwd=self.root, text=True,
                                    capture_output=True, check=False, timeout=30)

    def test_beads_missing_bd_explains_the_markdown_option(self):
        with mock.patch("workflow_core.tasks.backend", return_value="beads"), \
                mock.patch("workflow_core.tasks.shutil.which", return_value=None):
            self.assertIsNone(tasks.query(self.root, ["show", "x"]))
            with mock.patch("sys.stderr") as stderr:
                self.assertEqual(127, tasks.main(["ready"]))
        self.assertIn("providers.task_tracking=markdown", "".join(c.args[0] for c in stderr.write.call_args_list))

    def test_markdown_lifecycle_gates_end_to_end(self):
        self.init("providers.task_tracking=markdown")
        self.assertEqual("markdown", tasks.backend(self.root))
        epic = json.loads(gw(self.root, "task", "create", "--type", "epic", "E", "--json").stdout)["id"]
        child = json.loads(gw(self.root, "task", "create", "T", "--parent", epic, "--json").stdout)["id"]
        gw(self.root, "record", "orchestration-ready", "--workflow-id", "w", "--epic", epic, "--evidence", "x",
           "--actor", "me")

        def gates():
            state = json.loads(gw(self.root, "state", "--workflow-id", "w", "--format", "json").stdout)
            return state["gates"]["implementation_complete"], state["gates"]["shipped"]

        self.assertEqual(("unmet", "unmet"), gates())
        self.assertEqual(0, gw(self.root, "task", "close", child, "--reason", "ok").returncode)
        self.assertEqual(("satisfied", "unmet"), gates())
        gw(self.root, "task", "close", epic, "--reason", "merged")
        self.assertEqual(("satisfied", "satisfied"), gates())

    def test_detect_reports_whether_bd_is_installed(self):
        from workflow_core import setup_service

        for found, expected in (("/opt/bd", True), (None, False)):
            with mock.patch("workflow_core.setup_service.shutil.which", return_value=found):
                self.assertIs(expected, setup_service.detect(self.root)["beads_installed"])

    def test_team_mode_rejects_markdown_task_tracking(self):
        config = {"schema_version": "2.7", "providers": {"task_tracking": "markdown"},
                  "team": {"host": "github", "members": {}}}
        with self.assertRaisesRegex(ConfigValidationError, "team mode requires Beads"):
            validate_portable_config(config)


if __name__ == "__main__":
    unittest.main()

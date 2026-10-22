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

    def test_backend_defaults_to_markdown(self):
        self.init()
        self.assertEqual("markdown", tasks.backend(self.root))
        self.assertEqual("markdown", tasks.backend_name({}))

    def test_backend_defaults_to_beads_with_a_team(self):
        self.assertEqual("beads", tasks.backend_name({"team": {"members": {}}}))

    def test_backend_without_setup_is_markdown(self):
        self.assertEqual("markdown", tasks.backend(self.root))

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


    def test_invalid_config_fails_instead_of_running_bd(self):
        self.init("providers.task_tracking=markdown")
        config = self.root / ".agent-workflow/generated/effective-config.yaml"
        config.write_text(config.read_text(encoding="utf-8") + "team:\n  host: github\n  members: {}\n",
                          encoding="utf-8")
        with mock.patch("workflow_core.tasks.shutil.which") as which, \
                mock.patch("workflow_core.tasks.Path.cwd", return_value=self.root), \
                mock.patch("sys.stderr") as stderr:
            self.assertEqual(1, tasks.main(["ready"]))
            self.assertIsNone(tasks.query(self.root, ["ready"]))
        which.assert_not_called()
        self.assertIn("team mode requires Beads", "".join(c.args[0] for c in stderr.write.call_args_list))
        from workflow_core import specs, usage

        with self.assertRaisesRegex(specs.SpecsError, "team mode requires Beads"):
            specs._bd(self.root, ["ready"])
        with self.assertRaisesRegex(usage.UsageError, "team mode requires Beads"):
            usage._bd(self.root, ["show", "x"])

    def test_specs_and_usage_follow_the_markdown_backend(self):
        from workflow_core import specs, usage

        self.init("providers.task_tracking=markdown")
        epic = json.loads(gw(self.root, "task", "create", "--type", "epic", "E", "--json").stdout)["id"]
        self.assertEqual(epic, specs._bd(self.root, ["show", epic])[0]["id"])
        with self.assertRaisesRegex(specs.SpecsError, "failed"):
            specs._bd(self.root, ["show", "nope-1"])
        with self.assertRaisesRegex(usage.UsageError, "AI usage tracking requires Beads"):
            usage._bd(self.root, ["show", epic])

@unittest.skipUnless(shutil.which("bd"), "bd is not installed")
class ExternalDependencyTests(unittest.TestCase):
    """bd 1.0.5 counts every external:<project>:<capability> blocker as resolved; task ready holds them."""

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        base = Path(self._directory.name)
        self.provider, self.consumer = base / "prov", base / "cons"
        for root, prefix in ((self.provider, "p"), (self.consumer, "c")):
            root.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            self.bd(root, "init", "--prefix", prefix, "-q")
        self.bd(self.consumer, "config", "set", "external_projects.prov", "../prov/.beads")
        (self.consumer / ".claude").mkdir(exist_ok=True)
        gw(self.consumer, "setup", "init", "--harness", "claude", "--non-interactive", "--approve",
           "--set", "providers.task_tracking=beads")

    def tearDown(self):
        self._directory.cleanup()

    def bd(self, root, *args):
        return subprocess.run(["bd", *args], cwd=root, env=ENV, check=True, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=60).stdout

    def create(self, root, title, *extra):
        return json.loads(self.bd(root, "create", title, "--json", *extra))["id"]

    def ready(self):
        done = gw(self.consumer, "task", "ready", "--json")
        self.assertEqual(0, done.returncode, done.stderr)
        text = gw(self.consumer, "task", "ready")
        ids = {issue["id"] for issue in json.loads(done.stdout)}
        self.assertEqual(ids, {issue["id"] for issue in tasks.query(self.consumer, ["ready"])})
        return ids, text.stdout

    def test_unshipped_external_dependency_is_held_until_shipped(self):
        provides = self.create(self.provider, "api", "-l", "export:cap")
        waiting = self.create(self.consumer, "uses api")
        unknown = self.create(self.consumer, "uses nothing that exists")
        free = self.create(self.consumer, "free")
        self.bd(self.consumer, "dep", "add", waiting, "external:prov:cap")
        self.bd(self.consumer, "dep", "add", unknown, "external:nope:cap")

        ids, text = self.ready()
        self.assertEqual({free}, ids)
        self.assertIn(free, text)
        self.assertNotIn(f"{waiting} ", text.split("Held")[0])
        self.assertIn("external:prov:cap", text)

        self.bd(self.provider, "close", provides, "--reason", "done")
        self.bd(self.provider, "ship", "cap")
        ids, _ = self.ready()
        self.assertEqual({free, waiting}, ids)


class ExternalDependencyFailureTests(unittest.TestCase):
    def test_unexplained_ready_fails_instead_of_releasing(self):
        with mock.patch("workflow_core.tasks.backend", return_value="beads"), \
                mock.patch("workflow_core.tasks.shutil.which", return_value="/opt/bd"), \
                mock.patch("workflow_core.tasks.held_by_external", return_value=None), \
                mock.patch("workflow_core.tasks.subprocess.run",
                           return_value=subprocess.CompletedProcess([], 0, stdout='[{"id": "x-1"}]')), \
                mock.patch("sys.stderr"):
            self.assertEqual(1, tasks.main(["ready"]))
            self.assertIsNone(tasks.query(Path("."), ["ready"]))

    def test_non_json_ready_output_fails_when_beads_are_held(self):
        with mock.patch("workflow_core.tasks.backend", return_value="beads"), \
                mock.patch("workflow_core.tasks.shutil.which", return_value="/opt/bd"), \
                mock.patch("workflow_core.tasks.held_by_external", return_value={"x-1": ["external:p:c"]}), \
                mock.patch("workflow_core.tasks.subprocess.run",
                           return_value=subprocess.CompletedProcess([], 0, stdout="not json", stderr="")), \
                mock.patch("sys.stderr"):
            self.assertEqual(1, tasks.main(["ready", "--json"]))

    def test_explain_output_is_filtered_too(self):
        explained = {"ready": [{"id": "x-1"}, {"id": "x-2"}], "blocked": []}
        self.assertEqual({"ready": [{"id": "x-2"}], "blocked": []},
                         tasks.without_held(explained, {"x-1": ["external:p:c"]}))


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.gin_orchestrator import paths  # noqa: F401
from tests.gin_qa.qa_fixtures import gin_workflow_bin

from workflow_core.models import EffectiveConfig  # noqa: E402
from gin_orchestrator.contracts import (  # noqa: E402
    OperationStatus,
    TaskClosureRequest,
    TaskCreateRequest,
    TaskDependencyRecord,
    TaskSyncRequest,
)
from gin_orchestrator.registry import ProviderRegistry  # noqa: E402
from gin_orchestrator import task_tracking_cli  # noqa: E402
from gin_orchestrator.task_tracking_cli import CliTaskTrackingProvider  # noqa: E402


class CliTaskTrackingProviderTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name) / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        self.addCleanup(self._directory.cleanup)
        bin_dir = gin_workflow_bin(Path(self._directory.name))
        patched = mock.patch.dict(os.environ, {"PATH": os.pathsep.join([str(bin_dir), os.environ["PATH"]])})
        patched.start()
        self.addCleanup(patched.stop)
        (self.root / ".claude").mkdir()
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "i"],
                       cwd=self.root, check=True)
        subprocess.run([shutil.which("gin-workflow"), "setup", "init", "--harness", "claude", "--non-interactive", "--approve",
                        "--set", "providers.task_tracking=markdown"], cwd=self.root, check=True, capture_output=True)
        self.provider = CliTaskTrackingProvider(self.root)

    def test_default_executable_comes_from_tool_for_the_repository(self):
        calls = []

        def runner(argv, cwd):
            calls.append(list(argv))
            return subprocess.CompletedProcess(argv, 1, "", "stub")

        with mock.patch("gin_orchestrator.task_tracking_cli.tool", return_value="/cfg/gin-workflow") as tool:
            provider = CliTaskTrackingProvider(self.root, runner=runner)
            provider.readiness("t1")

        tool.assert_called_once()
        self.assertEqual("gin-workflow", tool.call_args[0][0])
        self.assertEqual(["/cfg/gin-workflow", "task"], calls[0][:2])

    def test_same_contract_scenario_as_the_fake_provider(self):
        provider = self.provider
        dependency = provider.create_task(TaskCreateRequest("dependency"), idempotency_key="dep")
        created = provider.create_task(
            TaskCreateRequest("Task", notes=("implementation note",), acceptance_criteria=("tests pass",)),
            idempotency_key="create",
        )
        edge = TaskDependencyRecord(created.value.task_id, dependency.value.task_id)
        provider.add_dependency(edge, idempotency_key="edge")
        replayed_edge = provider.add_dependency(edge, idempotency_key="edge")
        blocked = provider.readiness(created.value.task_id)
        provider.close_task(
            TaskClosureRequest(dependency.value.task_id, "done", ("unit tests",)), idempotency_key="close-dependency"
        )
        ready = provider.readiness(created.value.task_id)
        closed = provider.close_task(
            TaskClosureRequest(created.value.task_id, "accepted", ("tests:0", "review:approved")),
            idempotency_key="close-task",
        )

        self.assertEqual(("implementation note",), created.value.notes)
        self.assertEqual(("tests pass",), created.value.acceptance_criteria)
        self.assertTrue(replayed_edge.idempotent)
        self.assertEqual((dependency.value.task_id,), blocked.value.blockers)
        self.assertTrue(ready.value.ready, ready.value)
        self.assertIsNotNone(closed.value, closed.message)
        self.assertEqual("closed", closed.value.status)
        self.assertEqual(("tests:0", "review:approved"), closed.value.acceptance_evidence)
        self.assertEqual("accepted", closed.value.closure_reason)

    def test_closed_provenance_survives_a_new_provider_and_mismatch_is_invalid(self):
        task = self.provider.create_task(TaskCreateRequest("T"), idempotency_key="c").value.task_id
        request = TaskClosureRequest(task, "accepted", ("tests:0",))
        self.provider.close_task(request, idempotency_key="close")
        fresh = CliTaskTrackingProvider(self.root)
        self.assertTrue(fresh.close_task(request, idempotency_key="other").idempotent)
        mismatch = fresh.close_task(TaskClosureRequest(task, "other", ("x",)), idempotency_key="m")
        self.assertEqual(OperationStatus.INVALID, mismatch.status)

    def test_update_attributes_unknown_task_and_sync(self):
        task = self.provider.create_task(TaskCreateRequest("T"), idempotency_key="c").value.task_id
        updated = self.provider.update_task(task, {"assignee": "dev", "status": "in_progress"}, idempotency_key="u")
        self.assertEqual(("dev", "in_progress"), (updated.value.attributes["assignee"], updated.value.status))
        self.assertIsNone(self.provider.read_task("nope-1").value)
        self.assertEqual(OperationStatus.INVALID,
                         self.provider.sync(TaskSyncRequest("flush"), idempotency_key="s").status)
        self.assertTrue(self.provider.preflight().value.healthy)

    def test_registry_selects_the_cli_provider_for_beads_and_markdown(self):
        for name in ("markdown", "beads"):
            config = EffectiveConfig({"providers": {"task_tracking": name}}, self.root)
            registry = ProviderRegistry.from_effective_config(config)
            self.assertIsInstance(registry.task_tracking, CliTaskTrackingProvider)
            self.assertEqual("gin-workflow", registry.task_tracking.metadata.name)

    def test_runner_receives_gin_workflow_task_argv(self):
        calls = []

        def runner(argv, cwd):
            calls.append((list(argv), cwd))
            return subprocess.CompletedProcess(argv, 0, '[{"id": "t-1", "title": "T"}]', "")

        provider = CliTaskTrackingProvider(self.root, runner=runner)
        self.assertEqual("t-1", provider.read_task("t-1").value.task_id)
        self.assertEqual([([provider.executable, "task", "show", "t-1", "--json"], self.root.resolve())], calls)

    def test_failures_are_reported_not_raised(self):
        failing = CliTaskTrackingProvider(
            self.root, runner=lambda argv, cwd: subprocess.CompletedProcess(argv, 1, "", "boom\n"))
        read = failing.read_task("t-1")
        self.assertEqual((OperationStatus.INVALID, "gin-workflow task show failed: boom"),
                         (read.status, read.message))
        self.assertFalse(failing.preflight().value.healthy)

        def missing(argv, cwd):
            raise FileNotFoundError("gin-workflow")

        self.assertEqual(OperationStatus.UNAVAILABLE,
                         CliTaskTrackingProvider(self.root, runner=missing).read_task("t-1").status)
        garbled = CliTaskTrackingProvider(
            self.root, runner=lambda argv, cwd: subprocess.CompletedProcess(argv, 0, "not json", ""))
        self.assertEqual(OperationStatus.UNAVAILABLE, garbled.read_task("t-1").status)

    def test_create_and_update_map_status_and_attributes_to_flags(self):
        calls = []

        def runner(argv, cwd):
            calls.append(list(argv))
            return subprocess.CompletedProcess(argv, 0, '{"id": "t-1", "title": "T"}', "")

        provider = CliTaskTrackingProvider(self.root, runner=runner)
        provider.create_task(TaskCreateRequest("T", status="in_progress", attributes={"priority": 1, "assignee": "a"}),
                             idempotency_key="c")
        provider.update_task("t-1", {"attributes": {"priority": 2}}, idempotency_key="u")
        self.assertEqual(
            [[provider.executable, "task", "create", "--title=T", "--status=in_progress", "--description=",
              "--assignee=a", "--priority=1", "--json"],
             [provider.executable, "task", "update", "t-1", "--priority=2", "--json"]],
            calls)

        calls.clear()
        for request in (TaskCreateRequest("T", status="done"), TaskCreateRequest("T", attributes={"labels": "x"})):
            self.assertEqual(OperationStatus.INVALID, provider.create_task(request, idempotency_key="bad").status)
        self.assertEqual([], calls)

    def test_responses_without_a_task_object_are_unavailable(self):
        for stdout in ('{"title": "T"}', '{"id": "t-1"}', '"t-1"'):
            provider = CliTaskTrackingProvider(
                self.root, runner=lambda argv, cwd, out=stdout: subprocess.CompletedProcess(argv, 0, out, ""))
            self.assertEqual(OperationStatus.UNAVAILABLE, provider.read_task("t-1").status, stdout)

    def test_values_that_look_like_flags_are_kept(self):
        created = self.provider.create_task(TaskCreateRequest("-x", description="--force", notes=("-n",)),
                                            idempotency_key="c")
        self.assertEqual(("-x", "--force", ("-n",)),
                         (created.value.title, created.value.description, created.value.notes))
        updated = self.provider.update_task(created.value.task_id, {"assignee": "-a"}, idempotency_key="u")
        self.assertEqual("-a", updated.value.attributes["assignee"])
        closed = self.provider.close_task(TaskClosureRequest(created.value.task_id, "-done", ("-e",)),
                                          idempotency_key="close")
        self.assertIsNotNone(closed.value, closed.message)
        self.assertEqual(("closed", "-done"), (closed.value.status, closed.value.closure_reason))



class NativeArgvTests(unittest.TestCase):
    REST = ["task", "update", "t-1", '--append-notes=a "b"\nc', "--json"]

    def _argv(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            shim = os.path.join(tmp, "gin-workflow.cmd")
            with open(shim, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
            with mock.patch.object(task_tracking_cli.os, "name", "nt"), \
                    mock.patch.object(task_tracking_cli.shutil, "which", return_value=shim):
                return task_tracking_cli._native_argv(["gin-workflow", *self.REST]), shim, tmp

    def test_shims_run_the_launcher_directly(self):
        target = "C:\\x\\gin-workflow"
        shapes = {
            "install.ps1": '@echo off\r\nwhere py >nul 2>nul\r\nif %%errorlevel%%==0 (py -3 -X utf8 "%s" %%*) else (python -X utf8 "%s" %%*)\r\n' % (target, target),
            "older": '@echo off\npython "%s" %%*\n' % target,
            "fixture": '@"%s" "%s" %%*\r\n' % (sys.executable, target),
        }
        for name, text in shapes.items():
            with self.subTest(shape=name):
                argv, _, _ = self._argv(text)
                self.assertEqual(argv, [sys.executable, "-X", "utf8", target, *self.REST])

    def test_dp0_expands_to_the_shim_directory(self):
        argv, _, tmp = self._argv('@"%s" "%%~dp0stub.py" %%*\r\n' % sys.executable)
        self.assertEqual(argv, [sys.executable, "-X", "utf8", tmp + os.sep + "stub.py", *self.REST])

    def test_cmd_without_target_falls_back(self):
        argv, shim, _ = self._argv("@echo off\r\n")
        self.assertEqual(argv, [shim, *self.REST])

    def test_non_shim_executable_on_nt(self):
        with mock.patch.object(task_tracking_cli.os, "name", "nt"), \
                mock.patch.object(task_tracking_cli.shutil, "which", return_value="C:\\bin\\gin-workflow.exe"):
            self.assertEqual(task_tracking_cli._native_argv(["gin-workflow", *self.REST]), ["C:\\bin\\gin-workflow.exe", *self.REST])

    @unittest.skipUnless(os.name == "posix", "POSIX passthrough")
    def test_posix_unchanged(self):
        self.assertEqual(task_tracking_cli._native_argv(["gin-workflow", *self.REST]), ["gin-workflow", *self.REST])


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import os
import subprocess
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
        subprocess.run(["gin-workflow", "setup", "init", "--harness", "claude", "--non-interactive", "--approve",
                        "--set", "providers.task_tracking=markdown"], cwd=self.root, check=True, capture_output=True)
        self.provider = CliTaskTrackingProvider(self.root)

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
        self.assertTrue(ready.value.ready)
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
        self.assertEqual([(["gin-workflow", "task", "show", "t-1", "--json"], self.root.resolve())], calls)

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


    def test_values_that_look_like_flags_are_kept(self):
        created = self.provider.create_task(TaskCreateRequest("-x", description="--force", notes=("-n",)),
                                            idempotency_key="c")
        self.assertEqual(("-x", "--force", ("-n",)),
                         (created.value.title, created.value.description, created.value.notes))
        updated = self.provider.update_task(created.value.task_id, {"assignee": "-a"}, idempotency_key="u")
        self.assertEqual("-a", updated.value.attributes["assignee"])
        closed = self.provider.close_task(TaskClosureRequest(created.value.task_id, "-done", ("-e",)),
                                          idempotency_key="close")
        self.assertEqual(("closed", "-done"), (closed.value.status, closed.value.closure_reason))

if __name__ == "__main__":
    unittest.main()

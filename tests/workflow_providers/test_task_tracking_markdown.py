from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.models import EffectiveConfig  # noqa: E402
from workflow_providers.contracts import (  # noqa: E402
    OperationStatus,
    TaskClosureRequest,
    TaskCreateRequest,
    TaskDependencyRecord,
    TaskSyncRequest,
)
from workflow_providers.registry import ProviderRegistry  # noqa: E402
from workflow_providers.task_tracking_markdown import MarkdownTaskTrackingProvider  # noqa: E402


class MarkdownTaskTrackingProviderTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        self.provider = MarkdownTaskTrackingProvider(self.root)

    def tearDown(self):
        self._directory.cleanup()

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
        fresh = MarkdownTaskTrackingProvider(self.root)
        self.assertTrue(fresh.close_task(request, idempotency_key="other").idempotent)
        mismatch = fresh.close_task(TaskClosureRequest(task, "other", ("x",)), idempotency_key="m")
        self.assertEqual(OperationStatus.INVALID, mismatch.status)

    def test_update_attributes_unknown_task_and_sync(self):
        task = self.provider.create_task(TaskCreateRequest("T"), idempotency_key="c").value.task_id
        updated = self.provider.update_task(task, {"assignee": "dev", "status": "in_progress"}, idempotency_key="u")
        self.assertEqual(("dev", "in_progress"), (updated.value.attributes["assignee"], updated.value.status))
        self.assertIsNone(self.provider.read_task("nope-1").value)
        self.assertEqual(OperationStatus.UNAVAILABLE,
                         self.provider.sync(TaskSyncRequest("flush"), idempotency_key="s").status)
        self.assertTrue(self.provider.preflight().value.healthy)

    def test_registry_selects_markdown(self):
        config = EffectiveConfig({"providers": {"task_tracking": "markdown"}}, self.root)
        registry = ProviderRegistry.from_effective_config(config)
        self.assertIsInstance(registry.task_tracking, MarkdownTaskTrackingProvider)
        self.assertEqual("markdown", registry.task_tracking.metadata.name)


if __name__ == "__main__":
    unittest.main()

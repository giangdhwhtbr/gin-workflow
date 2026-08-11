from pathlib import Path
import sys
import tempfile
import unittest
import json
import subprocess


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_providers.contracts import (  # noqa: E402
    EvidenceCategory,
    EvidenceQuery,
    EvidenceRecord,
    KnowledgeProposal,
    NotificationRequest,
    OperationStatus,
    ProviderHealth,
    ReviewRequest,
    TaskCreateRequest,
    WorkspaceRequest,
)
from workflow_providers.knowledge import ObsidianKnowledgeProvider, RepositoryKnowledgeProvider  # noqa: E402
from workflow_providers.notifications import TelegramNotificationProvider  # noqa: E402
from workflow_providers.review import ReviewLedgerProvider  # noqa: E402
from workflow_providers.task_tracking import BeadsTaskTrackingProvider  # noqa: E402
from workflow_providers.workspace import WorktreeWorkspaceProvider  # noqa: E402
from workflow_providers.fakes import (  # noqa: E402
    FakeEvidenceProvider,
    FakeKnowledgeProvider,
    FakeNotificationProvider,
    FakeReviewProvider,
    FakeTaskTrackingProvider,
    FakeWorkspaceProvider,
)


class ProviderContractTests(unittest.TestCase):
    def test_task_provider_normalizes_success_invalid_unavailable_and_idempotency(self):
        provider = FakeTaskTrackingProvider()

        invalid = provider.create_task(TaskCreateRequest(title=""), idempotency_key="bad")
        first = provider.create_task(
            TaskCreateRequest(title="Implement provider boundary", description="portable"),
            idempotency_key="create-1",
        )
        duplicate = provider.create_task(
            TaskCreateRequest(title="Implement provider boundary", description="portable"), idempotency_key="create-1"
        )
        provider.set_available(False)
        unavailable = provider.read_task(first.value.task_id)

        self.assertIs(OperationStatus.INVALID, invalid.status)
        self.assertIs(OperationStatus.SUCCESS, first.status)
        self.assertFalse(first.idempotent)
        self.assertEqual(first.value, duplicate.value)
        self.assertTrue(duplicate.idempotent)
        self.assertIs(OperationStatus.UNAVAILABLE, unavailable.status)

    def test_task_provider_supports_create_read_and_update(self):
        provider = FakeTaskTrackingProvider()
        created = provider.create_task(
            TaskCreateRequest(title="Track", description="initial"), idempotency_key="create"
        )

        updated = provider.update_task(
            created.value.task_id,
            {"status": "in_progress", "description": "changed"},
            idempotency_key="update",
        )
        read = provider.read_task(created.value.task_id)

        self.assertIs(OperationStatus.SUCCESS, updated.status)
        self.assertEqual("in_progress", read.value.status)
        self.assertEqual("changed", read.value.description)

    def test_task_providers_map_supported_fields_and_reject_unknown_attributes(self):
        calls = []

        def runner(argv, cwd):
            calls.append(tuple(argv))
            payload = {
                "id": "task-1",
                "title": "Task",
                "status": "in_progress",
                "priority": "P1",
                "assignee": "worker-1",
            }
            return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")

        real = BeadsTaskTrackingProvider(Path.cwd(), runner=runner)
        request = TaskCreateRequest(
            "Task",
            status="in_progress",
            attributes={"priority": "P1", "assignee": "worker-1"},
        )
        created = real.create_task(request, idempotency_key="create")
        invalid_status = real.create_task(
            TaskCreateRequest("Bad status", status="not-real"),
            idempotency_key="bad-status",
        )
        invalid = real.create_task(
            TaskCreateRequest("Bad", attributes={"labels": ["unsupported"]}),
            idempotency_key="bad",
        )
        updated = real.update_task(
            "task-1",
            {"attributes": {"priority": "P0"}},
            idempotency_key="update",
        )

        self.assertIs(OperationStatus.SUCCESS, created.status)
        self.assertIn(("--status", "in_progress"), tuple(zip(calls[0], calls[0][1:])))
        self.assertIn(("--priority", "P1"), tuple(zip(calls[0], calls[0][1:])))
        self.assertIn(("--assignee", "worker-1"), tuple(zip(calls[0], calls[0][1:])))
        self.assertIs(OperationStatus.INVALID, invalid.status)
        self.assertIs(OperationStatus.INVALID, invalid_status.status)
        self.assertIn(("--priority", "P0"), tuple(zip(calls[1], calls[1][1:])))
        self.assertIs(OperationStatus.SUCCESS, updated.status)
        self.assertEqual(2, len(calls))

        fake = FakeTaskTrackingProvider()
        fake_created = fake.create_task(request, idempotency_key="create")
        fake_invalid_status = fake.create_task(
            TaskCreateRequest("Bad status", status="not-real"),
            idempotency_key="bad-status",
        )
        fake_invalid = fake.create_task(
            TaskCreateRequest("Bad", attributes={"labels": ["unsupported"]}),
            idempotency_key="bad",
        )
        fake_updated = fake.update_task(
            fake_created.value.task_id,
            {"attributes": {"priority": "P0"}},
            idempotency_key="update",
        )

        self.assertEqual("P1", fake_created.value.attributes["priority"])
        self.assertIs(OperationStatus.INVALID, fake_invalid.status)
        self.assertIs(OperationStatus.INVALID, fake_invalid_status.status)
        self.assertEqual("P0", fake_updated.value.attributes["priority"])

    def test_knowledge_provider_searches_and_only_proposes_worker_writes(self):
        provider = FakeKnowledgeProvider(
            entries=[{"knowledge_id": "decision-1", "title": "Provider boundary", "body": "portable"}]
        )

        found = provider.search("portable")
        proposal = provider.propose(
            KnowledgeProposal(title="New decision", body="candidate", proposed_by="worker-1"),
            idempotency_key="proposal-1",
        )

        self.assertEqual(["decision-1"], [item.knowledge_id for item in found.value])
        self.assertEqual("proposed", proposal.value.status)
        self.assertFalse(hasattr(provider, "write"))
        self.assertFalse(hasattr(provider, "save"))

    def test_workspace_provider_creates_isolates_and_idempotently_cleans_up(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = FakeWorkspaceProvider(Path(directory))
            created = provider.create(
                WorkspaceRequest(workspace_id="track-1", branch="bead/track-1"),
                idempotency_key="create",
            )
            self.assertTrue(created.value.path.is_dir())

            isolated = provider.isolate("track-1")
            cleaned = provider.cleanup("track-1", idempotency_key="cleanup")
            replay = provider.cleanup("track-1", idempotency_key="cleanup")

            self.assertEqual(created.value, isolated.value)
            self.assertIs(OperationStatus.SUCCESS, cleaned.status)
            self.assertTrue(replay.idempotent)

    def test_review_and_notification_providers_share_normalized_contract(self):
        reviews = FakeReviewProvider()
        notifications = FakeNotificationProvider()

        requested = reviews.request(
            ReviewRequest(task_id="task-1", actor_id="worker-1"),
            idempotency_key="review-1",
        )
        status = reviews.status("task-1")
        notified = notifications.notify(
            NotificationRequest(event="review_requested", message="Task is ready"),
            idempotency_key="notify-1",
        )

        self.assertEqual("review-requested", requested.value.state)
        self.assertEqual(requested.value, status.value)
        self.assertIs(OperationStatus.SUCCESS, notified.status)
        self.assertEqual("Task is ready", notifications.sent[0].message)

    def test_all_fakes_share_invalid_success_replay_and_unavailable_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = EvidenceRecord(
                "evidence-1", "task-1", EvidenceCategory.TESTS, "passed", "tests"
            )
            cases = (
                (
                    FakeTaskTrackingProvider(),
                    lambda item: item.create_task(TaskCreateRequest(""), idempotency_key="bad"),
                    lambda item: item.create_task(TaskCreateRequest("Task"), idempotency_key="key"),
                    lambda item: item.create_task(TaskCreateRequest("Task"), idempotency_key="key"),
                    lambda item: item.read_task("task-1"),
                ),
                (
                    FakeKnowledgeProvider(),
                    lambda item: item.propose(KnowledgeProposal("", "", ""), idempotency_key="bad"),
                    lambda item: item.propose(KnowledgeProposal("Title", "Body", "worker"), idempotency_key="key"),
                    lambda item: item.propose(KnowledgeProposal("Title", "Body", "worker"), idempotency_key="key"),
                    lambda item: item.search("Title"),
                ),
                (
                    FakeWorkspaceProvider(Path(directory)),
                    lambda item: item.create(WorkspaceRequest("", ""), idempotency_key="bad"),
                    lambda item: item.create(WorkspaceRequest("track", "branch"), idempotency_key="key"),
                    lambda item: item.create(WorkspaceRequest("track", "branch"), idempotency_key="key"),
                    lambda item: item.isolate("track"),
                ),
                (
                    FakeReviewProvider(),
                    lambda item: item.request(ReviewRequest("", ""), idempotency_key="bad"),
                    lambda item: item.request(ReviewRequest("task", "worker"), idempotency_key="key"),
                    lambda item: item.request(ReviewRequest("task", "worker"), idempotency_key="key"),
                    lambda item: item.status("task"),
                ),
                (
                    FakeEvidenceProvider(),
                    lambda item: item.record(EvidenceRecord("", "task", EvidenceCategory.TESTS, "passed", "tests"), idempotency_key="bad"),
                    lambda item: item.record(evidence, idempotency_key="key"),
                    lambda item: item.record(evidence, idempotency_key="key"),
                    lambda item: item.query(EvidenceQuery(task_id="task-1")),
                ),
                (
                    FakeNotificationProvider(),
                    lambda item: item.notify(NotificationRequest("", ""), idempotency_key="bad"),
                    lambda item: item.notify(NotificationRequest("event", "message"), idempotency_key="key"),
                    lambda item: item.notify(NotificationRequest("event", "message"), idempotency_key="key"),
                    lambda item: item.notify(NotificationRequest("event", "message"), idempotency_key="other"),
                ),
            )
            for provider, invalid, succeed, replay, unavailable in cases:
                with self.subTest(provider=provider.provider_type):
                    self.assertIs(OperationStatus.INVALID, invalid(provider).status)
                    self.assertIs(OperationStatus.SUCCESS, succeed(provider).status)
                    self.assertTrue(replay(provider).idempotent)
                    provider.set_available(False)
                    self.assertIs(OperationStatus.UNAVAILABLE, unavailable(provider).status)

    def test_idempotency_is_scoped_by_operation_key_and_request_fingerprint(self):
        tasks = FakeTaskTrackingProvider()
        first = tasks.create_task(TaskCreateRequest("first"), idempotency_key="shared")
        different = tasks.create_task(TaskCreateRequest("second"), idempotency_key="shared")

        self.assertNotEqual(first.value.task_id, different.value.task_id)
        self.assertEqual("second", different.value.title)
        self.assertFalse(different.idempotent)

        with tempfile.TemporaryDirectory() as directory:
            workspaces = FakeWorkspaceProvider(Path(directory))
            created = workspaces.create(
                WorkspaceRequest("track", "branch"), idempotency_key="same"
            )
            cleaned = workspaces.cleanup("track", idempotency_key="same")

            self.assertTrue(cleaned.value)
            self.assertNotEqual(created.value, cleaned.value)
            self.assertFalse(created.value.path.exists())

    def test_provider_metadata_reports_health_and_capabilities(self):
        provider = FakeTaskTrackingProvider()
        self.assertIs(ProviderHealth.AVAILABLE, provider.metadata.health)
        self.assertEqual(
            {"task.create", "task.read", "task.update"},
            set(provider.metadata.capabilities),
        )

        provider.set_available(False)
        self.assertIs(ProviderHealth.UNAVAILABLE, provider.metadata.health)


    def test_subprocess_adapters_normalize_success_invalid_unavailable_and_replay(self):
        task_calls = []

        def task_runner(argv, cwd):
            task_calls.append(tuple(argv))
            status = "closed" if len(argv) > 1 and argv[1] == "update" else "open"
            payload = {"id": "task-7", "title": "Portable providers", "status": status}
            return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")

        tasks = BeadsTaskTrackingProvider(Path.cwd(), runner=task_runner)
        self.assertIs(
            OperationStatus.INVALID,
            tasks.create_task(TaskCreateRequest(title=""), idempotency_key="bad").status,
        )
        created = tasks.create_task(TaskCreateRequest("Portable providers"), idempotency_key="create")
        replayed = tasks.create_task(TaskCreateRequest("Portable providers"), idempotency_key="create")
        self.assertEqual("task-7", created.value.task_id)
        self.assertTrue(replayed.idempotent)
        self.assertEqual(1, len(task_calls))
        updated = tasks.update_task(
            "task-7", {"status": "closed"}, idempotency_key="create"
        )
        self.assertEqual("closed", updated.value.status)
        self.assertEqual(2, len(task_calls))
        offline_tasks = BeadsTaskTrackingProvider(
            Path.cwd(),
            runner=lambda argv, cwd: subprocess.CompletedProcess(argv, 1, "", "offline"),
        )
        self.assertIs(OperationStatus.UNAVAILABLE, offline_tasks.read_task("task-7").status)

        notification_calls = []

        def notification_runner(argv, cwd, env):
            notification_calls.append(tuple(argv))
            return subprocess.CompletedProcess(argv, 0, "", "")

        notifications = TelegramNotificationProvider(Path.cwd(), runner=notification_runner)
        request = NotificationRequest("task_completed", "Done")
        self.assertIs(
            OperationStatus.INVALID,
            notifications.notify(NotificationRequest("", ""), idempotency_key="bad").status,
        )
        delivered = notifications.notify(request, idempotency_key="send")
        replayed = notifications.notify(request, idempotency_key="send")
        self.assertTrue(delivered.value.delivered)
        self.assertTrue(replayed.idempotent)
        self.assertEqual(1, len(notification_calls))
        offline_notifications = TelegramNotificationProvider(
            Path.cwd(),
            runner=lambda argv, cwd, env: subprocess.CompletedProcess(argv, 1, "", "offline"),
        )
        self.assertIs(
            OperationStatus.UNAVAILABLE,
            offline_notifications.notify(request, idempotency_key="offline").status,
        )
        disabled = TelegramNotificationProvider(Path.cwd(), environment={})
        self.assertIs(ProviderHealth.UNAVAILABLE, disabled.metadata.health)
        self.assertIs(
            OperationStatus.UNAVAILABLE,
            disabled.notify(request, idempotency_key="disabled").status,
        )

    def test_knowledge_adapters_only_return_proposals_and_normalize_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "decision.md").write_text("Provider-neutral lifecycle", encoding="utf-8")
            repository = RepositoryKnowledgeProvider(root)
            proposal = KnowledgeProposal("Candidate", "body", "worker")
            first = repository.propose(proposal, idempotency_key="proposal")
            replayed = repository.propose(proposal, idempotency_key="proposal")
            self.assertEqual("decision.md", repository.search("provider-neutral").value[0].knowledge_id)
            self.assertEqual("proposed", first.value.status)
            self.assertTrue(replayed.idempotent)
            self.assertIs(
                OperationStatus.INVALID,
                repository.propose(KnowledgeProposal("", "", ""), idempotency_key="bad").status,
            )

        self.assertIs(OperationStatus.UNAVAILABLE, ObsidianKnowledgeProvider().search("x").status)
        obsidian = ObsidianKnowledgeProvider(
            lambda query: [{"path": "decisions/provider.md", "title": "Provider", "content": query}]
        )
        self.assertEqual("decisions/provider.md", obsidian.search("boundary").value[0].knowledge_id)
        proposal = KnowledgeProposal("Candidate", "Body", "worker")
        first = obsidian.propose(proposal, idempotency_key="proposal")
        replayed = obsidian.propose(proposal, idempotency_key="proposal")
        invalid = obsidian.propose(KnowledgeProposal("", "", ""), idempotency_key="bad")
        self.assertEqual("proposed", first.value.status)
        self.assertTrue(replayed.idempotent)
        self.assertIs(OperationStatus.INVALID, invalid.status)
        self.assertIs(
            OperationStatus.UNAVAILABLE,
            RepositoryKnowledgeProvider(root / "missing").search("anything").status,
        )

    def test_worktree_adapter_normalizes_script_results_and_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def runner(argv, cwd):
                target = root / ".planning/worktrees" / argv[1]
                if str(argv[0]).endswith("worktree-create.sh"):
                    target.mkdir(parents=True)
                else:
                    target.rmdir()
                return subprocess.CompletedProcess(argv, 0, "ok", "")

            workspaces = WorktreeWorkspaceProvider(root, runner=runner)
            self.assertIs(
                OperationStatus.INVALID,
                workspaces.create(WorkspaceRequest("../escape", "branch"), idempotency_key="bad").status,
            )
            created = workspaces.create(
                WorkspaceRequest("track-1", "bead/track-1"), idempotency_key="create"
            )
            replayed = workspaces.create(
                WorkspaceRequest("track-1", "bead/track-1"), idempotency_key="create"
            )
            self.assertTrue(created.value.path.is_dir())
            self.assertTrue(replayed.idempotent)
            cleaned = workspaces.cleanup("track-1", idempotency_key="create")
            self.assertTrue(cleaned.value)
            self.assertFalse(created.value.path.exists())
            offline = WorktreeWorkspaceProvider(
                root,
                runner=lambda argv, cwd: subprocess.CompletedProcess(argv, 1, "", "git failed"),
            )
            self.assertIs(
                OperationStatus.UNAVAILABLE,
                offline.create(WorkspaceRequest("track-2", "branch"), idempotency_key="fail").status,
            )

    def test_worktree_adapter_rejects_nondefault_root_before_runner_or_side_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = []

            def runner(argv, cwd):
                calls.append(tuple(argv))
                (root / ".planning/worktrees" / argv[1]).mkdir(parents=True)
                return subprocess.CompletedProcess(argv, 0, "ok", "")

            workspace = WorktreeWorkspaceProvider(
                root,
                worktree_root=root / ".custom/worktrees",
                runner=runner,
            )
            result = workspace.create(
                WorkspaceRequest("track-1", "bead/track-1"),
                idempotency_key="create",
            )

            self.assertIs(OperationStatus.INVALID, result.status)
            self.assertEqual([], calls)
            self.assertFalse((root / ".planning/worktrees/track-1").exists())
            self.assertFalse((root / ".custom/worktrees/track-1").exists())

    def test_review_adapter_wraps_real_ledger_status_and_request(self):
        from review_ledger.cli import mutate_ledger

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mutate_ledger(
                "task-1",
                "ledger-created",
                {"repositories": [{
                    "repository_id": "repo", "role": "primary", "review_ref": "bead/task-1",
                    "review_base_sha": "base", "reviewed_source_sha": "head",
                }]},
                "worker",
                "worker-1",
                base_dir=str(root),
            )
            reviews = ReviewLedgerProvider(root)
            self.assertIs(
                OperationStatus.INVALID,
                reviews.request(ReviewRequest("", ""), idempotency_key="bad").status,
            )
            first = reviews.request(ReviewRequest("task-1", "worker-1"), idempotency_key="request")
            replayed = reviews.request(ReviewRequest("task-1", "worker-1"), idempotency_key="request")
            self.assertEqual("review-requested", first.value.state)
            self.assertTrue(replayed.idempotent)
            self.assertIs(OperationStatus.UNAVAILABLE, ReviewLedgerProvider(root).status("missing").status)

            corrupt = root / ".planning/corrupt/review.json"
            corrupt.parent.mkdir(parents=True)
            corrupt.write_text("not json", encoding="utf-8")
            self.assertIs(
                OperationStatus.UNAVAILABLE,
                ReviewLedgerProvider(root).status("corrupt").status,
            )

if __name__ == "__main__":
    unittest.main()

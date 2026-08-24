from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import json
import subprocess


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.identity import AcceptanceIdentity, RepositorySnapshot  # noqa: E402
from workflow_providers.contracts import (  # noqa: E402
    EvidenceCategory,
    EvidenceQuery,
    EvidenceRecord,
    KnowledgeProposal,
    NotificationRequest,
    OperationStatus,
    ProviderHealth,
    ReviewRequest,
    ReviewFinding,
    ReviewOutcomeRequest,
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
from tests.workflow_providers.test_task_tracking_compatibility import CliFixture  # noqa: E402


class ProviderContractTests(unittest.TestCase):
    def test_review_outcome_batch_failure_is_atomic_and_retryable(self):
        from review_ledger import cli as ledger_cli

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger_cli.mutate_ledger(
                "atomic-review", "ledger-created", {"repositories": []},
                "worker", "worker-1", base_dir=str(root),
            )
            ledger_cli.mutate_ledger(
                "atomic-review", "implementation-complete", {},
                "worker", "worker-1", base_dir=str(root),
            )
            reviews = ReviewLedgerProvider(root)
            reviews.request(
                ReviewRequest("atomic-review", "worker-1"),
                idempotency_key="request",
            )
            outcome = ReviewOutcomeRequest(
                "atomic-review", "reviewer-1", "changes_requested",
                (ReviewFinding("F-1", "IMPORTANT", "open"),),
            )
            json_path = root / ".planning/atomic-review/review.json"
            markdown_path = root / ".planning/atomic-review/review.md"
            before = (json_path.read_bytes(), markdown_path.read_bytes())
            real_mutate = ledger_cli._mutate_ledger_unlocked

            def fail_terminal(bead_id, action, *args, **kwargs):
                if action == "changes-requested":
                    raise OSError("terminal write failed")
                return real_mutate(bead_id, action, *args, **kwargs)

            with mock.patch.object(
                ledger_cli, "_mutate_ledger_unlocked", side_effect=fail_terminal
            ):
                failed = reviews.record_outcome(outcome, idempotency_key="outcome")

            after = (json_path.read_bytes(), markdown_path.read_bytes())
            unchanged = reviews.status("atomic-review").value
            retried = reviews.record_outcome(outcome, idempotency_key="outcome")
            self.assertIs(OperationStatus.INVALID, failed.status)
            self.assertEqual(before, after)
            self.assertEqual("review-requested", unchanged.state)
            self.assertEqual((), unchanged.findings)
            self.assertEqual("changes-requested", retried.value.state)

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
        fixture = CliFixture()
        calls = fixture.calls
        real = BeadsTaskTrackingProvider(Path.cwd(), runner=fixture)
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
        create_call = next(
            call for call in calls if len(call) > 1 and call[1] == "create" and "--help" not in call
        )
        self.assertIn(("--status", "in_progress"), tuple(zip(create_call, create_call[1:])))
        self.assertIn(("--priority", "P1"), tuple(zip(create_call, create_call[1:])))
        self.assertIn(("--assignee", "worker-1"), tuple(zip(create_call, create_call[1:])))
        self.assertIs(OperationStatus.INVALID, invalid.status)
        self.assertIs(OperationStatus.INVALID, invalid_status.status)
        update_call = next(
            call for call in calls if len(call) > 1 and call[1] == "update" and "--help" not in call
        )
        self.assertIn(("--priority", "P0"), tuple(zip(update_call, update_call[1:])))
        self.assertIs(OperationStatus.SUCCESS, updated.status)
        self.assertEqual(2, len([call for call in calls if "--help" not in call and call[1] in {"create", "update"}]))

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
            {
                "task.create", "task.read", "task.update", "task.close",
                "task.dependency", "task.readiness", "task.preflight", "task.sync",
            },
            set(provider.metadata.capabilities),
        )

        provider.set_available(False)
        self.assertIs(ProviderHealth.UNAVAILABLE, provider.metadata.health)


    def test_subprocess_adapters_normalize_success_invalid_unavailable_and_replay(self):
        fixture = CliFixture()
        task_calls = fixture.calls
        tasks = BeadsTaskTrackingProvider(Path.cwd(), runner=fixture)
        self.assertIs(
            OperationStatus.INVALID,
            tasks.create_task(TaskCreateRequest(title=""), idempotency_key="bad").status,
        )
        created = tasks.create_task(TaskCreateRequest("Portable providers"), idempotency_key="create")
        replayed = tasks.create_task(TaskCreateRequest("Portable providers"), idempotency_key="create")
        self.assertEqual("task-1", created.value.task_id)
        self.assertTrue(replayed.idempotent)
        self.assertEqual(1, len([call for call in task_calls if call[1] == "create" and "--help" not in call]))
        updated = tasks.update_task(
            "task-7", {"status": "closed"}, idempotency_key="create"
        )
        self.assertEqual("closed", updated.value.status)
        self.assertEqual(1, len([call for call in task_calls if call[1] == "update" and "--help" not in call]))
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
            mutate_ledger(
                "task-1",
                "implementation-complete",
                {},
                "worker",
                "worker-1",
                base_dir=str(root),
            )
            mutate_ledger(
                "task-1",
                "lease-acquired",
                {
                    "lease_id": "lease-1",
                    "actor_role": "reviewer",
                    "actor_id": "reviewer-1",
                    "acquired_at": "2026-08-14T00:00:00Z",
                    "expires_at": "2999-08-14T00:00:00Z",
                },
                "reviewer",
                "reviewer-1",
                base_dir=str(root),
            )
            reviews = ReviewLedgerProvider(root)
            self.assertIs(
                OperationStatus.INVALID,
                reviews.request(ReviewRequest("", ""), idempotency_key="bad").status,
            )
            first = reviews.request(
                ReviewRequest("task-1", "worker-1", "lease-1"),
                idempotency_key="request",
            )
            replayed = reviews.request(
                ReviewRequest("task-1", "worker-1", "lease-1"),
                idempotency_key="request",
            )
            outcome = reviews.record_outcome(
                ReviewOutcomeRequest(
                    "task-1",
                    "reviewer-1",
                    "changes_requested",
                    (
                        ReviewFinding(
                            "F-001", "IMPORTANT", "open", "src/api.py:12",
                            "validate input", "unit test",
                        ),
                    ),
                    "lease-1",
                ),
                idempotency_key="outcome",
            )
            self.assertIs(OperationStatus.SUCCESS, outcome.status, outcome.message)
            finding = reviews.status("task-1").value.findings[0]
            self.assertEqual("review-requested", first.value.state)
            self.assertTrue(replayed.idempotent)
            self.assertEqual("changes-requested", outcome.value.state)
            self.assertIsInstance(finding, ReviewFinding)
            self.assertEqual("src/api.py:12", finding.location)
            self.assertEqual("validate input", finding.expected_behavior)
            revision = reviews.begin_revision(
                "task-1", actor_id="worker-1", lease_id="lease-1",
                idempotency_key="revision",
            )
            second_request = reviews.complete_revision(
                "task-1", ("F-001",), actor_id="worker-1", lease_id="lease-1",
                idempotency_key="complete-revision",
            )
            approved = reviews.record_outcome(
                ReviewOutcomeRequest(
                    "task-1", "reviewer-1", "approved",
                    (
                        ReviewFinding(
                            "F-001", "IMPORTANT", "verified", "src/api.py:12",
                            "validate input", "unit test passed",
                        ),
                    ),
                    "lease-1",
                ),
                idempotency_key="outcome-2",
            )
            self.assertEqual("implementation-in-progress", revision.value.state)
            self.assertEqual("review-requested", second_request.value.state)
            self.assertIs(OperationStatus.INVALID, approved.status)
            self.assertIn("acceptance_identity", approved.message)
            self.assertIs(OperationStatus.UNAVAILABLE, ReviewLedgerProvider(root).status("missing").status)

            corrupt = root / ".planning/corrupt/review.json"
            corrupt.parent.mkdir(parents=True)
            corrupt.write_text("not json", encoding="utf-8")
            self.assertIs(
                OperationStatus.UNAVAILABLE,
                ReviewLedgerProvider(root).status("corrupt").status,
            )



    def test_approved_state_retry_fails_closed_without_persisted_identity(self):
        from review_ledger.cli import mutate_ledger

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task_id = "legacy-approved"
            mutate_ledger(task_id, "ledger-created", {"repositories": []}, "worker", "w", base_dir=str(root))
            mutate_ledger(task_id, "implementation-complete", {}, "worker", "w", base_dir=str(root))
            mutate_ledger(task_id, "review-requested", {}, "worker", "w", base_dir=str(root))
            mutate_ledger(task_id, "review-started", {}, "reviewer", "r", base_dir=str(root))
            mutate_ledger(
                task_id,
                "review-approved",
                {
                    "approved_repositories": [],
                    "source_scope_hash": "",
                    "terminal_findings": [],
                },
                "reviewer",
                "r",
                base_dir=str(root),
            )

            result = ReviewLedgerProvider(root).record_outcome(
                ReviewOutcomeRequest(task_id, "r", "approved"),
                idempotency_key="retry",
            )

            self.assertIs(OperationStatus.INVALID, result.status)
            self.assertIn("persisted acceptance identity", result.message)

    def test_review_approval_replays_complete_git_identity_and_persists_provenance(self):
        from review_ledger.cli import (
            initialize_ledger,
            load_ledger,
            mutate_ledger,
            start_review,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            (root / "src").mkdir()
            (root / "src/app.py").write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "src/app.py"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True)
            initialize_ledger(
                bead_id="identity-review",
                repository_id="repo",
                role="primary",
                repo_path=str(root),
                review_ref="refs/gin/review/identity-review",
                base_ref="HEAD",
                scope={
                    "included_paths": ["src"],
                    "excluded_artifact_paths": [],
                    "allowed_generated_paths": [],
                    "nested_repository_paths": [],
                },
                actor_role="worker",
                actor_id="worker-1",
                base_dir=str(root),
            )
            reviews = ReviewLedgerProvider(root)
            requested = reviews.request(
                ReviewRequest("identity-review", "worker-1"),
                idempotency_key="request",
            )
            start_review(
                "identity-review",
                "reviewer-1",
                requested_lease_id="identity-lease",
                base_dir=str(root),
            )
            mutate_ledger(
                "identity-review",
                "finding-created",
                {"finding_id": "F-existing", "severity": "MINOR"},
                "reviewer",
                "reviewer-1",
                base_dir=str(root),
                lease_id="identity-lease",
            )
            mutate_ledger(
                "identity-review",
                "finding-fixed",
                {"finding_id": "F-existing"},
                "worker",
                "worker-1",
                base_dir=str(root),
                lease_id="identity-lease",
            )
            mutate_ledger(
                "identity-review",
                "finding-verified",
                {"finding_id": "F-existing"},
                "reviewer",
                "reviewer-1",
                base_dir=str(root),
                lease_id="identity-lease",
            )
            requested = reviews.status("identity-review")
            _, projection = load_ledger("identity-review", str(root))
            repository = projection.repositories[0]
            identity = AcceptanceIdentity(
                "workflow-1",
                "attempt-1",
                "identity-review",
                (RepositorySnapshot(
                    repository["repository_id"],
                    repository["source_scope_hash"],
                    repository["source_tree_hash"],
                    repository["checkpoint_sha"],
                    repository["checkpoint_ref"],
                ),),
            )
            approved = reviews.record_outcome(
                ReviewOutcomeRequest(
                    "identity-review",
                    "reviewer-1",
                    "approved",
                    (),
                    "",
                    identity,
                    requested.value.ledger_revision,
                ),
                idempotency_key="approve",
            )

            self.assertIs(OperationStatus.SUCCESS, approved.status, approved.message)
            log, final = load_ledger("identity-review", str(root))
            payload = log.events[-1].payload
            self.assertEqual("review-approved", final.review_state)
            self.assertTrue(payload["source_scope_hash"])
            self.assertEqual(["F-existing"], payload["terminal_findings"])
            self.assertEqual("workflow-1", payload["workflow_id"])
            self.assertEqual("attempt-1", payload["attempt_id"])
            self.assertEqual("reviewer-1", payload["reviewer_id"])
            self.assertTrue(payload["review_event_id"].startswith("EV-"))
            self.assertEqual(
                payload["review_event_id"],
                f"EV-{payload['review_start_revision']:06d}",
            )
            self.assertEqual(
                identity.repositories[0].source_tree_hash,
                payload["approved_repositories"][0]["source_tree_hash"],
            )
            replayed = ReviewLedgerProvider(root).record_outcome(
                ReviewOutcomeRequest(
                    "identity-review", "reviewer-1", "approved", (), "",
                    identity, requested.value.ledger_revision,
                ),
                idempotency_key="replay-from-new-provider",
            )
            mismatched = ReviewLedgerProvider(root).record_outcome(
                ReviewOutcomeRequest(
                    "identity-review", "reviewer-1", "approved", (), "",
                    identity, requested.value.ledger_revision - 1,
                ),
                idempotency_key="mismatched-revision",
            )
            self.assertIs(OperationStatus.SUCCESS, replayed.status, replayed.message)
            self.assertTrue(replayed.idempotent)
            self.assertIs(OperationStatus.INVALID, mismatched.status)

            (root / "src/app.py").write_text("value = 2\n", encoding="utf-8")
            subprocess.run(["git", "add", "src/app.py"], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "-m", "move review ref"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "update-ref", repository["checkpoint_ref"], "HEAD"],
                cwd=root,
                check=True,
            )
            moved_ref = ReviewLedgerProvider(root).record_outcome(
                ReviewOutcomeRequest(
                    "identity-review", "reviewer-1", "approved", (), "",
                    identity, requested.value.ledger_revision,
                ),
                idempotency_key="moved-ref",
            )
            self.assertIs(OperationStatus.INVALID, moved_ref.status)
            self.assertIn("checkpoint ref", moved_ref.message)

if __name__ == "__main__":
    unittest.main()

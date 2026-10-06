from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.models import EffectiveConfig  # noqa: E402
from workflow_core.manifests import ContextRequest, create_context_manifest  # noqa: E402
from workflow_core.identity import AcceptanceIdentity, RepositorySnapshot  # noqa: E402
from workflow_core.provider_config import ProviderModelConfig  # noqa: E402
from workflow_providers.circuit_breaker import CircuitState  # noqa: E402
from workflow_providers.contracts import (  # noqa: E402
    EvidenceCategory,
    EvidenceRecord,
    OperationStatus,
    WorkspaceRequest,
)
from workflow_providers.evidence import CompositeEvidenceAuthority, FileEvidenceProvider  # noqa: E402
from workflow_providers.fakes import (  # noqa: E402
    FakeEvidenceProvider,
    FakeKnowledgeProvider,
    FakeNotificationProvider,
    FakeReviewProvider,
    FakeTaskTrackingProvider,
    FakeWorkspaceProvider,
)
from workflow_providers.knowledge import RepositoryKnowledgeProvider  # noqa: E402
from workflow_providers.notifications import TelegramNotificationProvider  # noqa: E402
from workflow_providers.native_cli import (  # noqa: E402
    FailureKind,
    NativeCliError,
    NativeCliOutput,
    NativeHealth,
)
from workflow_providers.registry import ProviderRegistry, RegistryError  # noqa: E402
from workflow_providers.routed_worker import RoutedWorkerDispatcher  # noqa: E402
from workflow_providers.review import ReviewLedgerProvider  # noqa: E402
from workflow_providers.task_tracking import BeadsTaskTrackingProvider  # noqa: E402
from workflow_providers.workspace import WorktreeWorkspaceProvider  # noqa: E402
from workflow_providers.worker_dispatch import REQUIRED_RESULT_FIELDS, WorkerRequest  # noqa: E402


class ProviderRegistryTests(unittest.TestCase):
    @staticmethod
    def evidence_config(root):
        return EffectiveConfig(
            {
                "schema_version": "2.3",
                "providers": {
                    "task_tracking": "fake",
                    "knowledge": "fake",
                    "workspace": "fake",
                    "review": "fake",
                    "evidence": "fake",
                    "notifications": "fake",
                },
            },
            Path(root),
        )

    def antigravity_config(self, root):
        return EffectiveConfig(
            {
                "schema_version": "2.3",
                "harness": "codex",
                "providers": {
                    "task_tracking": "fake", "knowledge": "fake", "workspace": "fake",
                    "review": "fake", "evidence": "fake", "notifications": "fake",
                },
                "routing": {
                    "roles": {
                        "backend": {
                            "preferred": ["antigravity"],
                            "fallback": ["codex"],
                        }
                    },
                    "concurrency": {"antigravity": 1, "codex": 1},
                    "queue": {"max_wait_seconds": 0},
                    "worker": {"timeout_seconds": 17, "max_retries": 0},
                    "circuit_breaker": {
                        "failure_threshold": 1,
                        "cooldown_seconds": 10,
                        "half_open_max_probes": 1,
                    },
                },
            },
            Path(root),
        )

    @staticmethod
    def composite_authority():
        identity = AcceptanceIdentity(
            workflow_id="wf-1",
            attempt_id="attempt-1",
            task_id="task-1",
            repositories=(
                RepositorySnapshot(
                    "primary",
                    "scope-1",
                    "tree-1",
                    "checkpoint-1",
                    "refs/gin/review/task-1",
                ),
            ),
        ).to_dict()
        test_results = [
            {
                "argv": ["python3", "-m", "unittest"],
                "exit_code": 0,
                "started_at": "2026-08-20T09:58:00Z",
                "finished_at": "2026-08-20T09:59:00Z",
                "workspace_id": "ws-task-1",
                "repository_id": "primary",
                "attempt_id": "attempt-1",
                "source_tree_hash": "tree-1",
            }
        ]
        worker_store = {
            "worker-1": {
                "task_id": "task-1",
                "worker_id": "worker-1",
                "status": "completed",
                "schema_version": "2.3",
                "request_acceptance_identity": identity,
                "result_acceptance_identity": identity,
                "request_workspace_id": "ws-task-1",
                "tests": test_results,
                "recorded_at": "2026-08-20T10:00:00Z",
            }
        }
        checkpoint_store = {
            "checkpoint-event-1": {
                "task_id": "task-1",
                "checkpoint_event_id": "checkpoint-event-1",
                "acceptance_identity": identity,
                "repositories": identity["repositories"],
                "recorded_at": "2026-08-20T10:01:00Z",
            }
        }
        review_store = {
            "review-event-1": {
                "task_id": "task-1",
                "review_event_id": "review-event-1",
                "ledger_revision": 7,
                "acceptance_identity": identity,
                "status": "approved",
                "terminal": True,
                "recorded_at": "2026-08-20T10:01:30Z",
                "verification_event_id": "verification-event-1",
            }
        }
        verification_store = {
            "verification-event-1": {
                "task_id": "task-1",
                "verification_event_id": "verification-event-1",
                "review_event_id": "review-event-1",
                "acceptance_identity": identity,
                "status": "passed",
                "recorded_at": "2026-08-20T10:02:00Z",
            }
        }
        return CompositeEvidenceAuthority(
            worker_resolver=worker_store.get,
            checkpoint_resolver=checkpoint_store.get,
            review_resolver=review_store.get,
            verification_resolver=verification_store.get,
        )

    def test_schema_23_registry_rejects_non_composite_evidence_authority(self):
        class EchoAuthority:
            def resolve(self, _category, _reference):
                return {}

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RegistryError, "CompositeEvidenceAuthority"):
                ProviderRegistry.from_effective_config(
                    self.evidence_config(directory),
                    evidence_authority=EchoAuthority(),
                )

    def test_routed_runtime_state_lives_in_the_main_checkout_of_a_worktree(self):
        import subprocess

        def git(cwd, *args):
            subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)

        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            git(repo, "init", "-q", "-b", "main")
            git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "x")
            tree = repo / ".planning/worktrees/wt1"
            git(repo, "worktree", "add", "-q", "-b", "feat/wt1", str(tree))
            local = {"codex": ProviderModelConfig("codex", "codex", {"low": "a", "medium": "b", "high": "c"})}
            registry = ProviderRegistry.from_effective_config(
                self.antigravity_config(tree), provider_local=local,
                evidence_authority=self.composite_authority(),
            )
            self.assertEqual(
                registry.worker.breakers.path, repo / ".agent-workflow/runtime/circuit-breakers.json"
            )

    def test_schema_23_registry_auto_builds_composite_evidence_authority_when_omitted(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ProviderRegistry.from_effective_config(
                self.evidence_config(directory),
            )

            self.assertIsInstance(registry.evidence, FakeEvidenceProvider)
            self.assertIsInstance(registry.evidence.authority, CompositeEvidenceAuthority)

    def test_registry_wires_independent_composite_authority_and_rejects_forgery(self):
        authority = self.composite_authority()
        with tempfile.TemporaryDirectory() as directory:
            registry = ProviderRegistry.from_config(
                self.evidence_config(directory),
                evidence_authority=authority,
            )
            references = (
                ("test", EvidenceCategory.TESTS, "worker-1"),
                ("repo", EvidenceCategory.REPOSITORY, "checkpoint-event-1"),
                ("review", EvidenceCategory.REVIEWS, "review-event-1"),
            )
            records = []
            for evidence_id, category, reference in references:
                canonical = authority.resolve(category, reference)
                records.append(
                    EvidenceRecord(
                        evidence_id=evidence_id,
                        task_id=canonical["task_id"],
                        category=category,
                        outcome=canonical["outcome"],
                        reference=reference,
                        details=canonical["details"],
                        acceptance_identity=AcceptanceIdentity.from_mapping(
                            canonical["acceptance_identity"]
                        ),
                        recorded_at=canonical["recorded_at"],
                    )
                )
            for record in records:
                self.assertIs(
                    OperationStatus.SUCCESS,
                    registry.evidence.record(
                        record,
                        idempotency_key=record.evidence_id,
                    ).status,
                )
            complete = registry.evidence.completeness(
                "task-1",
                records[0].acceptance_identity,
            )
            forged = replace(
                records[0],
                evidence_id="forged",
                details={
                    **records[0].details,
                    "tests": [
                        {
                            **records[0].details["tests"][0],
                            "workspace_id": "ws-forged",
                        }
                    ],
                },
            )

            rejected = registry.evidence.record(forged, idempotency_key="forged")

            self.assertTrue(complete.value.complete)
            self.assertIs(OperationStatus.INVALID, rejected.status)
            self.assertIn("authoritative", rejected.message)
    def routed_config(self, root):
        return EffectiveConfig(
            {
                "schema_version": "2.2",
                "harness": "codex",
                "providers": {
                    "task_tracking": "fake", "knowledge": "fake", "workspace": "fake",
                    "review": "fake", "evidence": "fake", "notifications": "fake",
                },
                "routing": {
                    "roles": {
                        "backend": {"preferred": ["claude"], "fallback": []},
                        "review": {"preferred": ["claude"], "fallback": []},
                    },
                    "concurrency": {"claude": 2},
                    "queue": {"max_wait_seconds": 0},
                    "worker": {"timeout_seconds": 17, "max_retries": 3},
                    "circuit_breaker": {"failure_threshold": 1, "cooldown_seconds": 10, "half_open_max_probes": 1},
                },
            },
            Path(root),
        )

    def local(self):
        return {
            "claude": ProviderModelConfig(
                "claude", "claude", {"low": "haiku", "medium": "sonnet", "high": "opus"}
            )
        }

    def test_routed_worker_requires_explicit_machine_local_provider_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            config = EffectiveConfig(
                {
                    "schema_version": "2.2",
                    "harness": "codex",
                    "providers": {
                        "task_tracking": "fake", "knowledge": "fake", "workspace": "fake",
                        "review": "fake", "evidence": "fake", "notifications": "fake",
                    },
                    "routing": {
                        "roles": {"backend": {"preferred": ["claude"], "fallback": ["main_harness"]}},
                        "concurrency": {"claude": 1, "codex": 1},
                        "queue": {"max_wait_seconds": 0},
                        "circuit_breaker": {"failure_threshold": 1, "cooldown_seconds": 10, "half_open_max_probes": 1},
                    },
                },
                Path(directory),
            )
            local = {
                "claude": ProviderModelConfig("claude", "claude", {"low": "haiku", "medium": "sonnet", "high": "opus"}),
                "codex": ProviderModelConfig("codex", "codex", {"low": "mini", "medium": "coding", "high": "reasoning"}),
            }

            without_local = ProviderRegistry.from_effective_config(config)
            with_local = ProviderRegistry.from_effective_config(config, provider_local=local)

            self.assertIsNone(without_local.worker)
            self.assertIsInstance(with_local.worker, RoutedWorkerDispatcher)

    def test_registry_routes_provider_default_without_model_and_rejects_explicit_mode(self):
        class Runner:
            def __init__(self):
                self.invocations = []

            def run(self, invocation, *, cancel_event=None):
                self.invocations.append(invocation)
                return NativeCliOutput(({
                    "status": "completed",
                    "task_id": "api",
                    "summary": "done",
                    "changed_files": [],
                    "commits": [],
                    "tests": [],
                    "evidence": [],
                    "blockers": [],
                },))

        for antigravity_model, expected_provider in (
            ("provider_default", "antigravity"),
            ("gemini-pro", "codex"),
        ):
            with self.subTest(model=antigravity_model), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                runner = Runner()
                local = {
                    "antigravity": ProviderModelConfig(
                        "antigravity", "agy", {
                            "low": antigravity_model,
                            "medium": antigravity_model,
                            "high": antigravity_model,
                        }
                    ),
                    "codex": ProviderModelConfig(
                        "codex", "codex", {
                            "low": "mini", "medium": "coding", "high": "reasoning"
                        }
                    ),
                }
                registry = ProviderRegistry.from_effective_config(
                    self.antigravity_config(root),
                    provider_local=local,
                    evidence_authority=self.composite_authority(),
                    native_runner=runner,
                    worker_health={
                        "antigravity": lambda candidate: NativeHealth(
                            True, "explicit_model_selection_unverified", False
                        ),
                        "codex": lambda candidate: True,
                    },
                )
                registry.workspace.create(
                    WorkspaceRequest("ws-api", "task/api"), idempotency_key="create"
                )
                worker_request = WorkerRequest(
                    "Implement", (), create_context_manifest("execute", ContextRequest()),
                    {"mode": "isolated", "workspace_id": "ws-api", "branch": "task/api"},
                    REQUIRED_RESULT_FIELDS, "api", "wf", "try-1", "backend", "high",
                )

                receipt = registry.worker.dispatch(worker_request)
                normalized = registry.worker.collect_result(receipt.worker_id)

                self.assertEqual("completed", normalized.status)
                self.assertEqual(expected_provider, receipt.provider_name)
                if expected_provider == "antigravity":
                    self.assertEqual("agy", Path(runner.invocations[0].argv[0]).name)
                    self.assertEqual("--add-dir", runner.invocations[0].argv[1])
                    self.assertIn("--sandbox", runner.invocations[0].argv)
                    self.assertEqual("--print", runner.invocations[0].argv[-2])

                else:
                    self.assertEqual("codex", Path(runner.invocations[0].argv[0]).name)
                    self.assertEqual("exec", runner.invocations[0].argv[1])

    def test_registry_wires_real_health_probe_cached_per_provider_and_model(self):
        class _ModelAwareRunner:
            def __init__(self):
                self.probe_invocations = []

            def run(self, invocation, *, cancel_event=None):
                self.probe_invocations.append(invocation)
                if "reasoning" in invocation.argv:
                    raise NativeCliError(FailureKind.INVALID_MODEL, "model not supported for this account")
                return NativeCliOutput(())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = _ModelAwareRunner()
            codex_script = root / "codex"
            codex_script.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "if sys.argv[1:3] == ['exec', '--help']:\n"
                "    print('usage: codex exec --model MODEL --json --ephemeral "
                "--dangerously-bypass-approvals-and-sandbox --cd DIR')\n"
                "    sys.exit(0)\n"
                "sys.exit(1)\n",
                encoding="utf-8",
            )
            codex_script.chmod(0o755)
            local = {
                "codex": ProviderModelConfig(
                    "codex", str(codex_script), {"low": "mini", "medium": "coding", "high": "reasoning"}
                ),
            }
            config = EffectiveConfig(
                {
                    "schema_version": "2.3",
                    "harness": "codex",
                    "providers": {
                        "task_tracking": "fake", "knowledge": "fake", "workspace": "fake",
                        "review": "fake", "evidence": "fake", "notifications": "fake",
                    },
                    "routing": {
                        "roles": {"backend": {"preferred": ["codex"], "fallback": []}},
                        "concurrency": {"codex": 1},
                        "queue": {"max_wait_seconds": 0},
                        "worker": {"timeout_seconds": 17, "max_retries": 0},
                        "circuit_breaker": {
                            "failure_threshold": 1,
                            "cooldown_seconds": 10,
                            "half_open_max_probes": 1,
                        },
                    },
                },
                root,
            )
            registry = ProviderRegistry.from_effective_config(
                config,
                provider_local=local,
                evidence_authority=self.composite_authority(),
                native_runner=runner,
            )

            from types import SimpleNamespace

            health_check = registry.worker.health["codex"]
            reasoning_health = health_check(SimpleNamespace(model="reasoning"))
            self.assertFalse(reasoning_health.available)
            self.assertEqual("invalid_model", reasoning_health.reason)

            # Same (provider, model) pair is cached -- no second probe invocation.
            health_check(SimpleNamespace(model="reasoning"))
            self.assertEqual(1, len(runner.probe_invocations))

            coding_health = health_check(SimpleNamespace(model="coding"))
            self.assertTrue(coding_health.available)
            self.assertEqual(2, len(runner.probe_invocations))

            probe_dir = root / ".agent-workflow/runtime/health-probe/codex"
            self.assertTrue(probe_dir.is_dir())
            for invocation in runner.probe_invocations:
                self.assertEqual(probe_dir.resolve(), invocation.cwd)

    def test_registry_rejects_provider_default_for_non_antigravity_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            local = {
                "codex": ProviderModelConfig(
                    "codex", "codex", {
                        "low": "provider_default",
                        "medium": "provider_default",
                        "high": "provider_default",
                    }
                )
            }

            with self.assertRaisesRegex(
                RegistryError, "provider_default is only supported for antigravity"
            ):
                ProviderRegistry.from_effective_config(
                    self.routed_config(directory), provider_local=local
                )

    def test_builds_every_selected_fake_from_effective_config(self):
        with tempfile.TemporaryDirectory() as directory:
            config = EffectiveConfig(
                {
                    "schema_version": "2.1",
                    "providers": {
                        "task_tracking": "fake",
                        "knowledge": "fake",
                        "workspace": "fake",
                        "review": "fake",
                        "evidence": "fake",
                        "notifications": "fake",
                    },
                },
                Path(directory),
            )

            registry = ProviderRegistry.from_config(config)

            self.assertIsInstance(registry.task_tracking, FakeTaskTrackingProvider)
            self.assertIsInstance(registry.knowledge, FakeKnowledgeProvider)
            self.assertIsInstance(registry.workspace, FakeWorkspaceProvider)
            self.assertIsInstance(registry.review, FakeReviewProvider)
            self.assertIsInstance(registry.evidence, FakeEvidenceProvider)
            self.assertIsInstance(registry.notifications, FakeNotificationProvider)

    def test_builds_registry_through_exact_from_effective_config_api(self):
        with tempfile.TemporaryDirectory() as directory:
            config = EffectiveConfig(
                {
                    "schema_version": "2.1",
                    "providers": {
                        "task_tracking": "fake",
                        "knowledge": "fake",
                        "workspace": "fake",
                        "review": "fake",
                        "evidence": "fake",
                        "notifications": "fake",
                    },
                },
                Path(directory),
            )

            registry = ProviderRegistry.from_effective_config(config)

            self.assertIsInstance(registry.task_tracking, FakeTaskTrackingProvider)

    def test_registry_selects_bd_or_br_task_executable_without_guessing(self):
        with tempfile.TemporaryDirectory() as directory:
            base = {
                "schema_version": "2.1",
                "providers": {
                    "task_tracking": {"name": "beads", "executable": "br"},
                    "knowledge": "fake",
                    "workspace": "fake",
                    "review": "fake",
                    "evidence": "fake",
                    "notifications": "fake",
                },
            }
            registry = ProviderRegistry.from_effective_config(
                EffectiveConfig(base, Path(directory))
            )
            self.assertEqual("br", registry.task_tracking.executable)

            base["providers"]["task_tracking"]["executable"] = "unknown"
            with self.assertRaisesRegex(RegistryError, "must be bd or br"):
                ProviderRegistry.from_effective_config(EffectiveConfig(base, Path(directory)))

    def test_default_registry_contains_only_the_existing_provider_integrations(self):
        with tempfile.TemporaryDirectory() as directory:
            config = EffectiveConfig(
                {
                    "schema_version": "2.1",
                    "artifacts": {
                        "worktrees": ".planning/worktrees",
                        "knowledge": ".planning/knowledge",
                        "evidence": ".agent-workflow/runtime/evidence",
                    },
                },
                Path(directory),
            )

            registry = ProviderRegistry.from_config(config)

            self.assertIsInstance(registry.task_tracking, BeadsTaskTrackingProvider)
            self.assertIsInstance(registry.knowledge, RepositoryKnowledgeProvider)
            self.assertIsInstance(registry.workspace, WorktreeWorkspaceProvider)
            self.assertIsInstance(registry.review, ReviewLedgerProvider)
            self.assertIsInstance(registry.evidence, FileEvidenceProvider)
            self.assertIsInstance(registry.notifications, TelegramNotificationProvider)

    def test_rejects_nondefault_worktree_root_that_safety_scripts_cannot_honor(self):
        with tempfile.TemporaryDirectory() as directory:
            config = EffectiveConfig(
                {
                    "schema_version": "2.1",
                    "artifacts": {"worktrees": ".custom/worktrees"},
                },
                Path(directory),
            )

            with self.assertRaisesRegex(RegistryError, "non-default worktree root"):
                ProviderRegistry.from_config(config)

    def test_rejects_unknown_provider_without_falling_back(self):
        config = EffectiveConfig(
            {"schema_version": "2.1", "providers": {"task_tracking": "not-real"}},
            Path.cwd(),
        )

        with self.assertRaisesRegex(RegistryError, "task_tracking.*not-real"):
            ProviderRegistry.from_config(config)

    def test_worker_uses_authoritative_workspace_record_and_rejects_path_mismatch(self):
        class Runner:
            def __init__(self):
                self.invocations = []

            def run(self, invocation, *, cancel_event=None):
                self.invocations.append(invocation)
                raise AssertionError("must not execute outside authoritative workspace")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = Runner()
            registry = ProviderRegistry.from_effective_config(
                self.routed_config(root),
                provider_local=self.local(),
                native_runner=runner,
                worker_health={"claude": lambda candidate: True},
            )
            registry.workspace.create(
                WorkspaceRequest("ws-api", "task/api"), idempotency_key="create"
            )
            request = WorkerRequest(
                "Implement", (), create_context_manifest("execute", ContextRequest()),
                {
                    "mode": "isolated",
                    "workspace_id": "ws-api",
                    "branch": "task/api",
                    "workspace_path": str(root),
                },
                REQUIRED_RESULT_FIELDS, "api", "wf", "try-1", "backend", "high",
            )

            receipt = registry.worker.dispatch(request)
            result = registry.worker.collect_result(receipt.worker_id)

            self.assertEqual(("worker_routes_unavailable",), result.blockers)
            self.assertEqual([], runner.invocations)
            reasons = [
                event.payload.get("reason")
                for event in registry.worker.event_store.read_all()
                if event.event_type == "worker.unavailable"
            ]
            self.assertEqual(["workspace_unavailable"], reasons)
            self.assertEqual(
                CircuitState.CLOSED, registry.worker.breakers.state("claude", "opus").state
            )

    def test_review_worker_without_workspace_runs_in_repository_root(self):
        class Runner:
            def __init__(self):
                self.invocations = []

            def run(self, invocation, *, cancel_event=None):
                self.invocations.append(invocation)
                return NativeCliOutput(())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = Runner()
            registry = ProviderRegistry.from_effective_config(
                self.routed_config(root),
                provider_local=self.local(),
                native_runner=runner,
                worker_health={"claude": lambda candidate: True},
            )
            review = WorkerRequest(
                "Review", (), create_context_manifest("review", ContextRequest()), {},
                REQUIRED_RESULT_FIELDS, "rev", "wf", "try-1", "review", "high",
            )
            registry.worker.collect_result(registry.worker.dispatch(review).worker_id)
            self.assertEqual([root.resolve()], [invocation.cwd for invocation in runner.invocations])

            implement = WorkerRequest(
                "Implement", (), create_context_manifest("execute", ContextRequest()), {},
                REQUIRED_RESULT_FIELDS, "api", "wf", "try-1", "backend", "high",
            )
            result = registry.worker.collect_result(registry.worker.dispatch(implement).worker_id)
            self.assertEqual(("worker_routes_unavailable",), result.blockers)
            self.assertEqual(1, len(runner.invocations))

    def test_registry_builds_scheduler_from_configured_worker_runtime_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ProviderRegistry.from_effective_config(
                self.routed_config(directory),
                provider_local=self.local(),
                worker_health={"claude": lambda candidate: True},
            )

            scheduler = registry.build_worker_scheduler()

            self.assertEqual(17, scheduler.worker_timeout_seconds)
            self.assertEqual(3, scheduler.max_retries)
            self.assertEqual(2, scheduler.max_parallel_workers)

    def test_registry_health_cache_distinguishes_codex_effort_and_probes_antigravity(self):
        from types import SimpleNamespace

        class _RecordingRunner:
            def __init__(self):
                self.invocations = []

            def run(self, invocation, *, cancel_event=None):
                self.invocations.append(invocation)
                return NativeCliOutput(())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = _RecordingRunner()
            codex_script = root / "codex"
            codex_script.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "if sys.argv[1:3] == ['exec', '--help']:\n"
                "    print('usage: codex exec --model MODEL -c CONFIG --json --ephemeral "
                "--dangerously-bypass-approvals-and-sandbox --cd DIR')\n"
                "    sys.exit(0)\n"
                "sys.exit(1)\n",
                encoding="utf-8",
            )
            codex_script.chmod(0o755)

            agy_script = root / "agy"
            agy_script.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "if '--help' in sys.argv:\n"
                "    print('usage: agy --print --sandbox --model MODEL --output-format FORMAT')\n"
                "    sys.exit(0)\n"
                "sys.exit(1)\n",
                encoding="utf-8",
            )
            agy_script.chmod(0o755)

            local = {
                "codex": ProviderModelConfig(
                    "codex", str(codex_script), {"low": "gpt-6-astra", "high": "gpt-6-astra"}
                ),
                "antigravity": ProviderModelConfig(
                    "antigravity", str(agy_script), {"low": "gemini-3.8-flash", "high": "gemini-3.8-flash"}
                ),
            }
            config = EffectiveConfig(
                {
                    "schema_version": "2.3",
                    "harness": "codex",
                    "providers": {
                        "task_tracking": "fake", "knowledge": "fake", "workspace": "fake",
                        "review": "fake", "evidence": "fake", "notifications": "fake",
                    },
                    "routing": {
                        "roles": {"backend": {"preferred": ["codex", "antigravity"], "fallback": []}},
                        "concurrency": {"codex": 1, "antigravity": 1},
                        "queue": {"max_wait_seconds": 0},
                        "worker": {"timeout_seconds": 17, "max_retries": 0},
                        "circuit_breaker": {
                            "failure_threshold": 1,
                            "cooldown_seconds": 10,
                            "half_open_max_probes": 1,
                        },
                    },
                },
                root,
            )
            registry = ProviderRegistry.from_effective_config(
                config,
                provider_local=local,
                evidence_authority=self.composite_authority(),
                native_runner=runner,
            )

            codex_check = registry.worker.health["codex"]
            # First with high effort
            res_high = codex_check(SimpleNamespace(model="gpt-6-astra", effort="high"))
            self.assertTrue(res_high.available)
            self.assertEqual(1, len(runner.invocations))
            self.assertIn("model_reasoning_effort=high", runner.invocations[0].argv)

            # Re-check high effort -> cached
            codex_check(SimpleNamespace(model="gpt-6-astra", effort="high"))
            self.assertEqual(1, len(runner.invocations))

            # Check low effort -> distinct cache key, new probe
            res_low = codex_check(SimpleNamespace(model="gpt-6-astra", effort="low"))
            self.assertTrue(res_low.available)
            self.assertEqual(2, len(runner.invocations))
            self.assertIn("model_reasoning_effort=low", runner.invocations[1].argv)

            # Test antigravity model probe
            agy_check = registry.worker.health["antigravity"]
            res_agy = agy_check(SimpleNamespace(model="gemini-3.8-flash"))
            self.assertTrue(res_agy.available)
            self.assertEqual(3, len(runner.invocations))
            self.assertIn("gemini-3.8-flash", runner.invocations[2].argv)
            self.assertTrue((root / ".agent-workflow/runtime/health-probe/antigravity").is_dir())

    def test_registry_resolves_harness_executable_for_worker_and_health_check(self):
        from types import SimpleNamespace
        import os

        class _RecordingRunner:
            def __init__(self):
                self.invocations = []

            def run(self, invocation, *, cancel_event=None):
                self.invocations.append(invocation)
                return NativeCliOutput(({"status": "completed", "task_id": "api", "summary": "ok", "changed_files": [], "commits": [], "tests": [], "evidence": [], "blockers": []},))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake_agy = bin_dir / "agy"
            fake_agy.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"--help\" ]; then\n"
                "    echo 'usage: agy --print --sandbox --model MODEL --output-format FORMAT'\n"
                "    exit 0\n"
                "fi\n"
                "exit 0\n"
            )
            fake_agy.chmod(0o755)

            orig_path = os.environ.get("PATH", "")
            os.environ["PATH"] = f"{bin_dir}:{orig_path}"
            try:
                runner = _RecordingRunner()
                local = {
                    "antigravity": ProviderModelConfig(
                        "antigravity", "antigravity", {"low": "gemini-3.8-flash", "high": "gemini-3.8-flash"}
                    ),
                }
                config = EffectiveConfig(
                    {
                        "schema_version": "2.3",
                        "harness": "antigravity",
                        "providers": {
                            "task_tracking": "fake", "knowledge": "fake", "workspace": "fake",
                            "review": "fake", "evidence": "fake", "notifications": "fake",
                        },
                        "routing": {
                            "roles": {"backend": {"preferred": ["antigravity"], "fallback": []}},
                            "concurrency": {"antigravity": 1},
                            "queue": {"max_wait_seconds": 0},
                            "worker": {"timeout_seconds": 17, "max_retries": 0},
                            "circuit_breaker": {
                                "failure_threshold": 1,
                                "cooldown_seconds": 10,
                                "half_open_max_probes": 1,
                            },
                        },
                    },
                    root,
                )
                registry = ProviderRegistry.from_effective_config(
                    config,
                    provider_local=local,
                    evidence_authority=self.composite_authority(),
                    native_runner=runner,
                )

                # Check health check resolves "antigravity" -> fake_agy
                agy_check = registry.worker.health["antigravity"]
                agy_check(SimpleNamespace(model="gemini-3.8-flash"))
                self.assertEqual(str(fake_agy.resolve()), runner.invocations[0].argv[0])

                # Check factory resolves "antigravity" -> fake_agy
                registry.workspace.create(
                    WorkspaceRequest("ws-api", "task/api"), idempotency_key="create"
                )
                worker_request = WorkerRequest(
                    "Implement", (), create_context_manifest("execute", ContextRequest()),
                    {"mode": "isolated", "workspace_id": "ws-api", "branch": "task/api"},
                    REQUIRED_RESULT_FIELDS, "api", "wf", "try-1", "backend", "high",
                )
                receipt = registry.worker.dispatch(worker_request)
                registry.worker.collect_result(receipt.worker_id)
                self.assertEqual(str(fake_agy.resolve()), runner.invocations[1].argv[0])
            finally:
                os.environ["PATH"] = orig_path


if __name__ == "__main__":
    unittest.main()

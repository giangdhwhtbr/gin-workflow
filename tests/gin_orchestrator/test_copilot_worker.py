"""Tests for GitHub Copilot CLI worker adapter and flag pass-through."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from types import MappingProxyType
import unittest
from unittest.mock import patch

from tests.gin_orchestrator import paths  # noqa: F401

from workflow_core.models import EffectiveConfig
from workflow_core.manifests import ContextRequest, create_context_manifest
from workflow_core.provider_config import ProviderModelConfig
from gin_orchestrator.antigravity_worker import build_antigravity_invocation
from gin_orchestrator.circuit_breaker import FailureKind
from gin_orchestrator.claude_worker import build_claude_invocation
from gin_orchestrator.contracts import WorkspaceRequest
from gin_orchestrator.copilot_worker import (
    COPILOT_ENV_KEYS,
    CopilotWorkerAdapter,
    _copilot_env_extra,
    build_copilot_invocation,
    copilot_health,
)
from gin_orchestrator.native_cli import (
    NativeCliError,
    NativeCliInvocation,
    NativeCliOutput,
    NativeCliRunner,
    NativeHealth,
    _diagnostic_from_stdout,
    classify_native_failure,
    direct_worker_result,
)
from gin_orchestrator.opencode_worker import build_opencode_invocation
from gin_orchestrator.registry import ProviderRegistry
from gin_orchestrator.worker_dispatch import REQUIRED_RESULT_FIELDS, WorkerRequest

HELP_FULL = "--prompt --allow-all-tools --no-ask-user --output-format --model --reasoning-effort --agent"


def sample_request() -> WorkerRequest:
    return WorkerRequest(
        objective="Implement task",
        constraints=("scope",),
        generated_manifest=create_context_manifest("execute", ContextRequest()),
        isolation_policy={"mode": "isolated", "workspace_id": "ws-task-1"},
        expected_output=REQUIRED_RESULT_FIELDS,
        task_id="task-1",
        workflow_id="wf-1",
        retry_identity="retry-1",
        provider_role="backend",
        model="claude-sonnet-4.5",
        effort="high",
    )


def sample_result() -> dict:
    return {
        "status": "completed",
        "task_id": "task-1",
        "summary": "done",
        "changed_files": [],
        "commits": [],
        "tests": [],
        "evidence": [],
        "blockers": [],
    }


class FakeRunner:
    def __init__(self, records: tuple | None = None):
        self.invocations: list[NativeCliInvocation] = []
        self.records = records or (
            {"type": "assistant.message", "data": {"content": json.dumps(sample_result())}},
        )

    def run(self, invocation: NativeCliInvocation, *, cancel_event=None) -> NativeCliOutput:
        self.invocations.append(invocation)
        return NativeCliOutput(self.records)


class CopilotWorkerTests(unittest.TestCase):
    def test_build_copilot_invocation_full(self):
        workspace = Path("/tmp/test-copilot-ws")
        invocation = build_copilot_invocation(
            "copilot",
            "claude-sonnet-4.5",
            workspace,
            "do work",
            timeout_seconds=120,
            effort="high",
            agent="developer",
        )
        self.assertEqual(
            (
                "copilot",
                "-p",
                "do work",
                "--allow-all-tools",
                "--no-ask-user",
                "--output-format",
                "json",
                "--add-dir",
                str(workspace.resolve()),
                "--model",
                "claude-sonnet-4.5",
                "--reasoning-effort",
                "high",
                "--agent",
                "developer",
            ),
            invocation.argv,
        )
        self.assertEqual(workspace.resolve(), invocation.cwd)
        self.assertEqual(b"", invocation.stdin)
        self.assertEqual(120, invocation.timeout_seconds)

    def test_build_copilot_invocation_provider_default(self):
        workspace = Path("/tmp/test-copilot-ws")
        invocation = build_copilot_invocation(
            "copilot",
            "provider_default",
            workspace,
            "do work",
        )
        self.assertEqual(
            (
                "copilot",
                "-p",
                "do work",
                "--allow-all-tools",
                "--no-ask-user",
                "--output-format",
                "json",
                "--add-dir",
                str(workspace.resolve()),
            ),
            invocation.argv,
        )
        self.assertNotIn("--model", invocation.argv)
        self.assertNotIn("--reasoning-effort", invocation.argv)
        self.assertNotIn("--agent", invocation.argv)

    def test_env_extra_filtering_and_repr(self):
        custom_env = {
            "COPILOT_HOME": "/home/copilot",
            "GH_TOKEN": "gh_secret_123",
            "GITHUB_TOKEN": "gh_secret_456",
            "COPILOT_GITHUB_TOKEN": "gh_secret_789",
            "GH_HOST": "github.com",
            "COPILOT_GH_HOST": "github.mycompany.com",
            "OTHER_SECRET": "should_not_leak",
            "EMPTY_VAL": "",
        }
        filtered = _copilot_env_extra(custom_env)
        for key in COPILOT_ENV_KEYS:
            self.assertEqual(custom_env[key], filtered[key])
        self.assertNotIn("OTHER_SECRET", filtered)
        self.assertNotIn("EMPTY_VAL", filtered)

        workspace = Path("/tmp/test-copilot-ws")
        invocation = NativeCliInvocation(
            ("copilot",),
            workspace,
            b"",
            100,
            env_extra=filtered,
        )
        self.assertIsInstance(invocation.env_extra, MappingProxyType)
        repr_str = repr(invocation)
        self.assertNotIn("gh_secret", repr_str)
        self.assertNotIn("env_extra", repr_str)

    def test_direct_worker_result_extracts_nested_data(self):
        result_payload = sample_result()
        output = NativeCliOutput(
            (
                {
                    "type": "assistant.message",
                    "data": {"content": json.dumps(result_payload)},
                },
            )
        )
        extracted = direct_worker_result(output)
        self.assertEqual("completed", extracted["status"])
        self.assertEqual("task-1", extracted["task_id"])

        output_msg = NativeCliOutput(
            (
                {
                    "type": "result",
                    "data": {"message": json.dumps(result_payload)},
                },
            )
        )
        extracted_msg = direct_worker_result(output_msg)
        self.assertEqual("completed", extracted_msg["status"])

    def test_diagnostic_from_stdout_nested_data(self):
        stdout_bytes = json.dumps(
            {"type": "error", "data": {"message": "unauthorized token expired"}}
        ).encode("utf-8")
        diag = _diagnostic_from_stdout(stdout_bytes)
        self.assertEqual("unauthorized token expired", diag)

        stdout_reason = json.dumps(
            {"type": "error", "data": {"reason": "rate limit exceeded"}}
        ).encode("utf-8")
        self.assertEqual("rate limit exceeded", _diagnostic_from_stdout(stdout_reason))

        stdout_detail = json.dumps(
            {"type": "error", "data": {"detail": "model not found"}}
        ).encode("utf-8")
        self.assertEqual("model not found", _diagnostic_from_stdout(stdout_detail))

        # Content in assistant message must not be extracted as error diagnostic
        assistant_content = json.dumps(
            {"type": "assistant.message", "data": {"content": "Let us talk about quota and auth"}}
        ).encode("utf-8")
        self.assertIsNone(_diagnostic_from_stdout(assistant_content))

    def test_copilot_health(self):
        # Missing required flags
        h1 = copilot_health("copilot", help_text="--model --output-format")
        self.assertFalse(h1.available)
        self.assertEqual("required_flags_unverified", h1.reason)

        # Missing --reasoning-effort when effort is requested
        h2 = copilot_health(
            "copilot",
            help_text="--prompt --allow-all-tools --output-format --model",
            effort="high",
        )
        self.assertFalse(h2.available)
        self.assertEqual("required_flags_unverified", h2.reason)

        # Ready when flags present
        h3 = copilot_health("copilot", help_text=HELP_FULL)
        self.assertTrue(h3.available)
        self.assertEqual("ready", h3.reason)
        self.assertTrue(h3.explicit_model_selection)

        # Model probe failure with invalid model
        class BoomRunner:
            def run(self, invocation, *, cancel_event=None):
                raise NativeCliError(FailureKind.INVALID_MODEL, "model not found")

        h4 = copilot_health(
            "copilot",
            help_text=HELP_FULL,
            model="nonexistent-model",
            native_runner=BoomRunner(),
            workspace=Path("/tmp/ws"),
        )
        self.assertFalse(h4.available)
        self.assertEqual("invalid_model", h4.reason)

    def test_pass_through_effort_and_agent_other_workers(self):
        workspace = Path("/tmp/ws")
        # Antigravity accepts effort and agent
        ag_inv = build_antigravity_invocation(
            "antigravity",
            "gemini-2.5-pro",
            workspace,
            "prompt",
            effort="high",
            agent="developer",
        )
        self.assertIn("--effort", ag_inv.argv)
        self.assertEqual("high", ag_inv.argv[ag_inv.argv.index("--effort") + 1])
        self.assertIn("--agent", ag_inv.argv)
        self.assertEqual("developer", ag_inv.argv[ag_inv.argv.index("--agent") + 1])

        # OpenCode accepts agent
        oc_inv = build_opencode_invocation(
            "opencode",
            "model-x",
            workspace,
            "prompt",
            agent="reviewer",
        )
        self.assertIn("--agent", oc_inv.argv)
        self.assertEqual("reviewer", oc_inv.argv[oc_inv.argv.index("--agent") + 1])

        # Claude accepts agent
        claude_inv = build_claude_invocation(
            "claude",
            "claude-sonnet-4.5",
            workspace,
            "prompt",
            effort="medium",
            agent="tester",
        )
        self.assertIn("--agent", claude_inv.argv)
        self.assertEqual("tester", claude_inv.argv[claude_inv.argv.index("--agent") + 1])
        self.assertIn("--effort", claude_inv.argv)
        self.assertEqual("medium", claude_inv.argv[claude_inv.argv.index("--effort") + 1])

    def test_copilot_worker_adapter_dispatch_and_collect(self):
        runner = FakeRunner()
        adapter = CopilotWorkerAdapter(
            native_runner=runner,
            executable="copilot",
            model="claude-sonnet-4.5",
            workspace=Path("/tmp/test-copilot-ws"),
            effort="high",
            agent="developer",
        )
        self.assertEqual("copilot", adapter.provider_name)
        receipt = adapter.dispatch(sample_request())
        res = adapter.collect_result(receipt.worker_id)
        self.assertEqual("completed", res.status)
        self.assertEqual(1, len(runner.invocations))
        argv = runner.invocations[0].argv
        self.assertIn("--model", argv)
        self.assertIn("--reasoning-effort", argv)
        self.assertIn("--agent", argv)

    def test_classify_native_failure_copilot_model_not_available(self):
        stderr = 'Error: Model "claude-haiku-4.5" from --model flag is not available.'
        self.assertIs(FailureKind.INVALID_MODEL, classify_native_failure(stderr))

    def test_env_extra_compare_and_hashable(self):
        ws = Path("/tmp/test-copilot-ws")
        inv1 = NativeCliInvocation(("copilot",), ws, b"", 10, env_extra={"GH_TOKEN": "token-1"})
        inv2 = NativeCliInvocation(("copilot",), ws, b"", 10, env_extra={"GH_TOKEN": "token-2"})
        self.assertEqual(inv1, inv2)
        self.assertEqual(hash(inv1), hash(inv2))

    def test_runner_run_merges_env_extra(self):
        import io

        class FakeProc:
            pid = 4242
            returncode = 0

            def __init__(self):
                self.stdin = io.BytesIO()
                self.stdout = io.BytesIO(b'{"status": "completed"}\n')
                self.stderr = io.BytesIO()

            def poll(self):
                return 0

            def wait(self, timeout=None):
                return 0

        captured_kwargs = []

        def fake_popen(argv, **kwargs):
            captured_kwargs.append(kwargs)
            return FakeProc()

        with patch("subprocess.Popen", side_effect=fake_popen):
            runner = NativeCliRunner()
            invocation = NativeCliInvocation(
                ("copilot",),
                Path("/tmp"),
                b"",
                10,
                env_extra={"COPILOT_CUSTOM_KEY": "custom_val_123"},
            )
            runner.run(invocation)
            self.assertEqual(1, len(captured_kwargs))
            call_kwargs = captured_kwargs[0]
            self.assertIn("env", call_kwargs)
            self.assertEqual("custom_val_123", call_kwargs["env"].get("COPILOT_CUSTOM_KEY"))

    def test_build_copilot_invocation_reads_os_environ_when_env_none(self):
        with patch.dict(os.environ, {"GH_TOKEN": "token_from_os", "COPILOT_HOME": "/custom/copilot"}):
            inv = build_copilot_invocation("copilot", "claude-sonnet-4.5", Path("/tmp"), "do work")
            self.assertEqual("token_from_os", inv.env_extra.get("GH_TOKEN"))
            self.assertEqual("/custom/copilot", inv.env_extra.get("COPILOT_HOME"))

    def test_provider_registry_passes_agent_when_request_has_agent(self):
        class CapturingRunner:
            def __init__(self):
                self.invocations: list[NativeCliInvocation] = []

            def run(self, invocation, *, cancel_event=None):
                self.invocations.append(invocation)
                return NativeCliOutput(({
                    "type": "assistant.message",
                    "data": {"content": json.dumps(sample_result())},
                },))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = CapturingRunner()
            config = EffectiveConfig(
                {
                    "schema_version": "2.9",
                    "harness": "copilot",
                    "models": {
                        "copilot": {
                            "models": ["claude-sonnet-4.5"],
                            "efforts": ["high"],
                        }
                    },
                    "providers": {
                        "task_tracking": "fake",
                        "knowledge": "fake",
                        "workspace": "fake",
                        "review": "fake",
                        "evidence": "fake",
                    },
                    "orchestrator": {
                        "roles": {"backend": {"preferred": ["copilot"]}},
                        "concurrency": {"copilot": 1},
                        "queue": {"max_wait_seconds": 0},
                        "worker": {"timeout_seconds": 10, "max_retries": 0},
                        "circuit_breaker": {
                            "failure_threshold": 1,
                            "cooldown_seconds": 10,
                            "half_open_max_probes": 1,
                        },
                    },
                },
                root,
            )
            local = {"copilot": ProviderModelConfig("copilot", "copilot")}
            registry = ProviderRegistry.from_effective_config(
                config,
                provider_local=local,
                native_runner=runner,
                worker_health={"copilot": lambda c: NativeHealth(True, "ready", True)},
            )
            registry.workspace.create(WorkspaceRequest("ws-task-1", "task/api"), idempotency_key="create")
            req = WorkerRequest(
                objective="Implement task",
                constraints=("scope",),
                generated_manifest=create_context_manifest("execute", ContextRequest()),
                isolation_policy={"mode": "isolated", "workspace_id": "ws-task-1", "branch": "task/api"},
                expected_output=REQUIRED_RESULT_FIELDS,
                task_id="task-1",
                workflow_id="wf-1",
                retry_identity="retry-1",
                provider_role="backend",
                model="claude-sonnet-4.5",
                effort="high",
            )
            object.__setattr__(req, "agent", "developer")

            receipt = registry.worker.dispatch(req)
            registry.worker.collect_result(receipt.worker_id)

            self.assertEqual(1, len(runner.invocations))
            argv = runner.invocations[0].argv
            self.assertIn("--agent", argv)
            idx = argv.index("--agent")
            self.assertEqual("developer", argv[idx + 1])


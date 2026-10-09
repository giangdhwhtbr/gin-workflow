from pathlib import Path
import json
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.manifests import ContextRequest, create_context_manifest  # noqa: E402
from workflow_providers.circuit_breaker import FailureKind  # noqa: E402
from workflow_providers.native_cli import (  # noqa: E402
    NativeCliError,
    NativeCliOutput,
    classify_native_failure,
    direct_worker_result,
)
from workflow_providers.opencode_worker import OpenCodeWorkerAdapter, opencode_health  # noqa: E402
from workflow_providers.worker_dispatch import REQUIRED_RESULT_FIELDS, WorkerRequest  # noqa: E402

# Captured from `opencode run --standalone --auto --format json --model nonexistent/model ok` (exit 1, stdout).
OPENCODE_INVALID_MODEL_TEXT = "Model unavailable: nonexistent/model"
HELP = "--model --auto --format"


def request():
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
        reasoning="medium",
    )


def result():
    return {
        "status": "completed", "task_id": "task-1", "summary": "done", "changed_files": [],
        "commits": [], "tests": [], "evidence": [], "blockers": [],
    }


class FakeRunner:
    def __init__(self):
        self.invocations = []

    def run(self, invocation, *, cancel_event=None):
        self.invocations.append(invocation)
        return NativeCliOutput(({"type": "text", "part": {"text": json.dumps(result())}},))


class OpenCodeWorkerTests(unittest.TestCase):
    def test_explicit_model_argv_and_cwd(self):
        runner = FakeRunner()
        adapter = OpenCodeWorkerAdapter(
            native_runner=runner, executable="opencode",
            model="github-copilot/claude-sonnet-5.5", workspace=Path.cwd(),
        )
        receipt = adapter.dispatch(request())
        self.assertEqual("completed", adapter.collect_result(receipt.worker_id).status)
        invocation = runner.invocations[0]
        self.assertEqual(
            ("opencode", "run", "--standalone", "--auto", "--format", "json",
             "--model", "github-copilot/claude-sonnet-5.5"),
            invocation.argv[:8],
        )
        self.assertEqual(Path.cwd().resolve(), invocation.cwd)

    def test_provider_default_omits_model(self):
        runner = FakeRunner()
        adapter = OpenCodeWorkerAdapter(
            native_runner=runner, executable="opencode", model="provider_default", workspace=Path.cwd(),
        )
        receipt = adapter.dispatch(request())
        adapter.collect_result(receipt.worker_id)
        self.assertNotIn("--model", runner.invocations[0].argv)

    def test_health_requires_flags(self):
        self.assertFalse(opencode_health("opencode", help_text="--model --format").available)
        self.assertFalse(opencode_health("opencode", help_text="--model --auto").available)
        self.assertTrue(opencode_health("opencode", help_text=HELP).available)
        no_model = opencode_health("opencode", help_text="--auto --format")
        self.assertTrue(no_model.available)
        self.assertFalse(no_model.explicit_model_selection)

    def test_health_reports_invalid_model(self):
        class Boom:
            def run(self, invocation, *, cancel_event=None):
                raise NativeCliError(FailureKind.INVALID_MODEL, OPENCODE_INVALID_MODEL_TEXT)

        health = opencode_health(
            "opencode", help_text=HELP, model="x/y", native_runner=Boom(), workspace=Path.cwd(),
        )
        self.assertEqual("invalid_model", health.reason)
        self.assertFalse(health.available)

    def test_part_text_without_contract_is_invalid_result(self):
        with self.assertRaises(NativeCliError):
            direct_worker_result(NativeCliOutput(({"type": "text", "part": {"text": "no json"}},)))

    def test_unavailable_model_is_classified_invalid_model(self):
        self.assertIs(FailureKind.INVALID_MODEL, classify_native_failure(OPENCODE_INVALID_MODEL_TEXT))


if __name__ == "__main__":
    unittest.main()

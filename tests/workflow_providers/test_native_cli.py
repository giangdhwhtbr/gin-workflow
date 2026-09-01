import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_providers.antigravity_worker import (  # noqa: E402
    antigravity_health,
    build_antigravity_invocation,
)
from workflow_providers.claude_worker import build_claude_invocation, claude_health  # noqa: E402
from workflow_providers.codex_worker import build_codex_invocation, codex_health  # noqa: E402
from workflow_providers.native_cli import (  # noqa: E402
    FailureKind,
    NativeCliError,
    NativeCliInvocation,
    NativeCliOutput,
    NativeCliRunner,
)


class NativeCliTests(unittest.TestCase):
    def test_provider_builders_use_explicit_model_noninteractive_argv_and_no_shell(self):
        workspace = Path("/tmp/workspace")
        claude = build_claude_invocation("claude", "opus", workspace, "{}")
        codex = build_codex_invocation("codex", "reasoning", workspace, "{}")
        agy = build_antigravity_invocation("agy", "flash", workspace, "{}")

        self.assertEqual(
            ("claude", "-p", "--model", "opus", "--output-format", "json", "--permission-mode", "acceptEdits"),
            claude.argv[:8],
        )
        self.assertIn("--allowedTools", claude.argv)
        allowed_tools = claude.argv[claude.argv.index("--allowedTools") + 1]
        self.assertIn("Bash(git status:*)", allowed_tools)
        self.assertIn("Bash(npm test:*)", allowed_tools)
        self.assertEqual(("codex", "exec"), codex.argv[:2])
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", codex.argv)
        self.assertNotIn("--sandbox", codex.argv)
        self.assertNotIn("workspace-write", codex.argv)
        self.assertIn("--cd", codex.argv)
        self.assertNotIn("-C", codex.argv)
        self.assertEqual(
            ("agy", "--add-dir", str(workspace.resolve()), "--sandbox", "--print-timeout", "900s", "--print", "{}"),
            agy.argv,
        )
        self.assertEqual(b"", agy.stdin)
        self.assertFalse(claude.shell or codex.shell or agy.shell)


    def test_codex_health_requires_exact_safe_noninteractive_flags(self):
        required = (
            "usage: codex exec --model MODEL --json --ephemeral "
            "--dangerously-bypass-approvals-and-sandbox --cd DIR"
        )
        missing_approval = "usage: codex exec --model MODEL --json --ephemeral --cd DIR"
        prefixed = (
            "usage: codex exec --model-cache --json-lines --ephemeral-mode "
            "--dangerously-bypass-approvals-and-sandboxed"
        )

        ready = codex_health("codex", help_text=required)
        unavailable = codex_health("codex", help_text=missing_approval)
        prefix_only = codex_health("codex", help_text=prefixed)

        self.assertTrue(ready.available)
        self.assertEqual("ready", ready.reason)
        self.assertFalse(unavailable.available)
        self.assertEqual("required_flags_unverified", unavailable.reason)
        self.assertFalse(prefix_only.available)

    def test_runner_bounds_stdin_sanitizes_environment_and_parses_jsonl(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "worker.py"
            script.write_text(
                "import json, os, sys\n"
                "data = sys.stdin.read()\n"
                "print(json.dumps({'size': len(data), 'secret': os.getenv('SECRET_SHOULD_DROP')}))\n"
                "print(json.dumps({'status': 'ok'}))\n",
                encoding="utf-8",
            )
            invocation = NativeCliInvocation(
                (sys.executable, str(script)), Path(directory), b"bounded", 2.0
            )
            previous = os.environ.get("SECRET_SHOULD_DROP")
            os.environ["SECRET_SHOULD_DROP"] = "must-not-leak"
            try:
                output = NativeCliRunner(max_stdin_bytes=16).run(invocation)
            finally:
                if previous is None:
                    os.environ.pop("SECRET_SHOULD_DROP", None)
                else:
                    os.environ["SECRET_SHOULD_DROP"] = previous

            self.assertEqual(7, output.records[0]["size"])
            self.assertIsNone(output.records[0]["secret"])
            self.assertEqual("ok", output.records[1]["status"])
            with self.assertRaisesRegex(NativeCliError, "input exceeds"):
                NativeCliRunner(max_stdin_bytes=2).run(invocation)

    def test_runner_classifies_quota_timeout_cancellation_and_malformed_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            failing = root / "failing.py"
            failing.write_text("import sys\nsys.stderr.write('quota exhausted')\nsys.exit(1)\n", encoding="utf-8")
            sleeping = root / "sleeping.py"
            sleeping.write_text("import time\ntime.sleep(2)\n", encoding="utf-8")
            malformed = root / "malformed.py"
            malformed.write_text("print('not-json')\n", encoding="utf-8")
            runner = NativeCliRunner()

            with self.assertRaises(NativeCliError) as quota:
                runner.run(NativeCliInvocation((sys.executable, str(failing)), root, b"", 1))
            self.assertEqual(FailureKind.QUOTA, quota.exception.kind)
            with self.assertRaises(NativeCliError) as timeout:
                runner.run(NativeCliInvocation((sys.executable, str(sleeping)), root, b"", 0.05))
            self.assertEqual(FailureKind.TIMEOUT, timeout.exception.kind)
            cancelled = threading.Event()
            cancelled.set()
            with self.assertRaises(NativeCliError) as cancellation:
                runner.run(NativeCliInvocation((sys.executable, str(sleeping)), root, b"", 1), cancel_event=cancelled)
            self.assertEqual(FailureKind.CANCELLED, cancellation.exception.kind)
            with self.assertRaises(NativeCliError) as invalid:
                runner.run(NativeCliInvocation((sys.executable, str(malformed)), root, b"", 1))
            self.assertEqual(FailureKind.INVALID_RESULT, invalid.exception.kind)

    def test_runner_classifies_unsupported_model_rejection_as_invalid_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rejected = root / "rejected.py"
            rejected.write_text(
                "import sys\n"
                "sys.stderr.write(\"The 'reasoning' model is not supported when using "
                "Codex with a ChatGPT account.\")\n"
                "sys.exit(1)\n",
                encoding="utf-8",
            )
            runner = NativeCliRunner()
            with self.assertRaises(NativeCliError) as invalid_model:
                runner.run(NativeCliInvocation((sys.executable, str(rejected)), root, b"", 1))
            self.assertEqual(FailureKind.INVALID_MODEL, invalid_model.exception.kind)

    def test_runner_idle_timeout_fires_independently_of_larger_hard_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            quiet = root / "quiet.py"
            quiet.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
            runner = NativeCliRunner()
            started = time.monotonic()
            with self.assertRaises(NativeCliError) as idle_case:
                runner.run(
                    NativeCliInvocation(
                        (sys.executable, str(quiet)), root, b"", 30, 0.15
                    )
                )
            elapsed = time.monotonic() - started
            self.assertEqual(FailureKind.TIMEOUT, idle_case.exception.kind)
            self.assertIn("idle timeout", str(idle_case.exception))
            self.assertLess(elapsed, 5, "idle timeout should fire well before the 30s hard timeout")

    def test_runner_completing_run_within_idle_and_hard_timeouts_is_unaffected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "worker.py"
            script.write_text(
                "import json\n"
                "print(json.dumps({'status': 'completed', 'task_id': 't', 'summary': 'ok',"
                "'changed_files': [], 'commits': [], 'tests': [], 'evidence': [], 'blockers': []}))\n",
                encoding="utf-8",
            )
            runner = NativeCliRunner()
            output = runner.run(
                NativeCliInvocation((sys.executable, str(script)), root, b"", 10, 5)
            )
            self.assertEqual("completed", output.records[0]["status"])

    def test_runner_reports_real_changed_files_after_hard_timeout_kill(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            script = root / "editor.py"
            script.write_text(
                "from pathlib import Path\nimport time\n"
                "Path('created.txt').write_text('partial work')\n"
                "time.sleep(30)\n",
                encoding="utf-8",
            )
            runner = NativeCliRunner()
            with self.assertRaises(NativeCliError) as timeout_case:
                runner.run(NativeCliInvocation((sys.executable, str(script)), root, b"", 0.3))
            self.assertEqual(FailureKind.TIMEOUT, timeout_case.exception.kind)
            self.assertIn("created.txt", timeout_case.exception.changed_files)

    def test_runner_sends_graceful_stop_signal_before_force_kill(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "graceful.py"
            script.write_text(
                "import signal, sys, time\n"
                "def handler(signum, frame):\n"
                "    open('graceful-stop.marker', 'w').write('stopped')\n"
                "    sys.exit(0)\n"
                "signal.signal(signal.SIGINT, handler)\n"
                "time.sleep(30)\n",
                encoding="utf-8",
            )
            runner = NativeCliRunner()
            with self.assertRaises(NativeCliError) as timeout_case:
                runner.run(NativeCliInvocation((sys.executable, str(script)), root, b"", 0.2))
            self.assertEqual(FailureKind.TIMEOUT, timeout_case.exception.kind)
            marker = root / "graceful-stop.marker"
            deadline = time.monotonic() + 1
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(marker.exists(), "process should have had a chance to trap SIGINT and exit cleanly")

    def test_cancellation_reports_real_changed_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            script = root / "editor.py"
            script.write_text(
                "from pathlib import Path\nimport time\n"
                "Path('created.txt').write_text('partial work')\n"
                "time.sleep(30)\n",
                encoding="utf-8",
            )
            runner = NativeCliRunner()
            cancelled = threading.Event()

            def cancel_soon():
                time.sleep(0.15)
                cancelled.set()

            threading.Thread(target=cancel_soon, daemon=True).start()
            with self.assertRaises(NativeCliError) as cancel_case:
                runner.run(
                    NativeCliInvocation((sys.executable, str(script)), root, b"", 30),
                    cancel_event=cancelled,
                )
            self.assertEqual(FailureKind.CANCELLED, cancel_case.exception.kind)
            self.assertIn("created.txt", cancel_case.exception.changed_files)

    def test_runner_preserves_sanitized_diagnostic_text_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stderr_only = root / "stderr_only.py"
            stderr_only.write_text(
                "import sys\nsys.stderr.write('boom: disk is full')\nsys.exit(1)\n",
                encoding="utf-8",
            )
            stdout_json_error = root / "stdout_json_error.py"
            stdout_json_error.write_text(
                "import sys\n"
                "print('{\"status\": \"error\", \"message\": \"account lacks scope for this action\"}')\n"
                "sys.exit(1)\n",
                encoding="utf-8",
            )
            secret_bearing = root / "secret_bearing.py"
            secret_bearing.write_text(
                "import sys\n"
                "sys.stderr.write('auth failed for token sk-abcdef1234567890')\n"
                "sys.exit(1)\n",
                encoding="utf-8",
            )
            runner = NativeCliRunner()

            with self.assertRaises(NativeCliError) as stderr_case:
                runner.run(NativeCliInvocation((sys.executable, str(stderr_only)), root, b"", 1))
            self.assertIn("disk is full", str(stderr_case.exception))

            with self.assertRaises(NativeCliError) as stdout_case:
                runner.run(NativeCliInvocation((sys.executable, str(stdout_json_error)), root, b"", 1))
            self.assertIn("account lacks scope for this action", str(stdout_case.exception))

            with self.assertRaises(NativeCliError) as secret_case:
                runner.run(NativeCliInvocation((sys.executable, str(secret_bearing)), root, b"", 1))
            self.assertNotIn("sk-abcdef1234567890", str(secret_case.exception))
            self.assertIn("[REDACTED]", str(secret_case.exception))

    def test_codex_health_probes_configured_model_and_rejects_invalid_model(self):
        required = (
            "usage: codex exec --model MODEL --json --ephemeral "
            "--dangerously-bypass-approvals-and-sandbox --cd DIR"
        )

        class _RejectingRunner:
            def run(self, invocation, *, cancel_event=None):
                raise NativeCliError(FailureKind.INVALID_MODEL, "model not supported for this account")

        class _AcceptingRunner:
            def __init__(self):
                self.invocations = []

            def run(self, invocation, *, cancel_event=None):
                self.invocations.append(invocation)
                return None

        rejected = codex_health(
            "codex",
            help_text=required,
            model="reasoning",
            native_runner=_RejectingRunner(),
            workspace=Path("/tmp/health-probe"),
        )
        self.assertFalse(rejected.available)
        self.assertEqual("invalid_model", rejected.reason)

        accepting_runner = _AcceptingRunner()
        accepted = codex_health(
            "codex",
            help_text=required,
            model="gpt-5",
            native_runner=accepting_runner,
            workspace=Path("/tmp/health-probe"),
        )
        self.assertTrue(accepted.available)
        self.assertEqual("ready", accepted.reason)
        self.assertEqual(1, len(accepting_runner.invocations))
        self.assertIn("gpt-5", accepting_runner.invocations[0].argv)

        no_probe = codex_health("codex", help_text=required)
        self.assertTrue(no_probe.available)
        self.assertEqual("ready", no_probe.reason)

    def test_claude_health_probes_configured_model_and_rejects_invalid_model(self):
        class _RejectingRunner:
            def run(self, invocation, *, cancel_event=None):
                raise NativeCliError(FailureKind.INVALID_MODEL, "model not supported for this account")

        rejected = claude_health(
            "claude",
            help_text="usage: claude --model --output-format --allowedTools",
            model="reasoning",
            native_runner=_RejectingRunner(),
            workspace=Path("/tmp/health-probe"),
        )
        self.assertFalse(rejected.available)
        self.assertEqual("invalid_model", rejected.reason)

    def test_antigravity_health_degrades_to_provider_default_without_model_flag(self):
        degraded = antigravity_health("agy", help_text="usage: agy --print --sandbox")
        available = antigravity_health("agy", help_text="usage: agy --print --model MODEL --sandbox")

        self.assertTrue(degraded.available)
        self.assertEqual("explicit_model_selection_unverified", degraded.reason)
        self.assertFalse(degraded.explicit_model_selection)
        self.assertTrue(available.available)
        self.assertTrue(available.explicit_model_selection)
        self.assertFalse(antigravity_health("/definitely/missing-agy").available)

        missing_runtime_flag = antigravity_health(
            "agy", help_text="usage: agy --print --model MODEL"
        )
        self.assertFalse(missing_runtime_flag.available)
        self.assertEqual("required_flags_unverified", missing_runtime_flag.reason)

        prefix_only = antigravity_health(
            "agy",
            help_text="usage: agy --printable --model-cache --sandboxed",
        )
        self.assertFalse(prefix_only.available)
        self.assertFalse(prefix_only.explicit_model_selection)
        self.assertEqual("required_flags_unverified", prefix_only.reason)


if __name__ == "__main__":
    unittest.main()

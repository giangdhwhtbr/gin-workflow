import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_providers.antigravity_worker import (  # noqa: E402
    antigravity_health,
    build_antigravity_invocation,
)
from workflow_providers.claude_worker import build_claude_invocation  # noqa: E402
from workflow_providers.codex_worker import build_codex_invocation  # noqa: E402
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
            claude.argv,
        )
        self.assertEqual(("codex", "exec"), codex.argv[:2])
        self.assertIn("workspace-write", codex.argv)
        self.assertIn("--approve-for-me", codex.argv)
        self.assertEqual(("agy", "--print", "--model", "flash", "--sandbox"), agy.argv)
        self.assertFalse(claude.shell or codex.shell or agy.shell)

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

    def test_antigravity_health_requires_verified_explicit_model_capability(self):
        unavailable = antigravity_health("agy", help_text="usage: agy --print --sandbox")
        available = antigravity_health("agy", help_text="usage: agy --print --model MODEL --sandbox")

        self.assertFalse(unavailable.available)
        self.assertEqual("explicit_model_selection_unverified", unavailable.reason)
        self.assertTrue(available.available)
        self.assertFalse(antigravity_health("/definitely/missing-agy").available)


if __name__ == "__main__":
    unittest.main()

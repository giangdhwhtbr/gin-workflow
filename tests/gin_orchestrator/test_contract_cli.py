"""The `python -m gin_orchestrator` orchestrator contract CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.gin_orchestrator import paths  # noqa: F401
from gin_orchestrator.native_cli import list_models  # noqa: E402


def run(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "gin_orchestrator", *argv],
        env={**os.environ, "PYTHONPATH": os.pathsep.join((str(paths.CORE_SCRIPTS), str(paths.ORCH_SCRIPTS)))},
        capture_output=True,
        text=True,
        check=False,
    )


class ContractCliTests(unittest.TestCase):
    def test_version_prints_the_contract(self):
        result = run("version", "--json")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"contract_version": 1, "orchestrator_version": "bundled"}, json.loads(result.stdout))

    def test_health_reports_a_supported_stub(self):
        with tempfile.TemporaryDirectory() as directory:
            stub = Path(directory) / "fake-codex"
            stub.write_text(
                "#!/bin/sh\nif [ \"$1\" = \"exec\" ] && [ \"$2\" = \"--help\" ]; then\n"
                "  echo 'usage: codex exec --model MODEL --json --ephemeral"
                " --dangerously-bypass-approvals-and-sandbox --cd DIR'\n  exit 0\nfi\nexit 0\n",
                encoding="utf-8",
            )
            stub.chmod(0o755)

            result = run("health", "--provider", "codex", "--executable", str(stub), "--json")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(json.loads(result.stdout)["available"])

    def test_health_reports_a_missing_executable(self):
        result = run("health", "--provider", "codex", "--executable", "/nonexistent", "--json")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(json.loads(result.stdout)["available"])

    def test_unknown_provider_exits_two(self):
        result = run("health", "--provider", "nope", "--executable", "/nonexistent", "--json")

        self.assertEqual(2, result.returncode)

    def test_models_prints_the_native_list(self):
        result = run("models", "--provider", "claude", "--json")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(list_models("claude"), json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()

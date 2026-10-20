"""Tests for workflow_core.orchestrator_client."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins/gin-workflow/src/scripts"))

from workflow_core import orchestrator_client  # noqa: E402


class OrchestratorClientTests(unittest.TestCase):
    def setUp(self) -> None:
        orchestrator_client._checked.cache_clear()

    def test_bundled_health_reports_unavailable_for_nonexistent(self) -> None:
        result = orchestrator_client.health("codex", "/nonexistent")
        self.assertFalse(result["available"])

    def test_contract_mismatch_raises_orchestrator_error(self) -> None:
        with tempfile.TemporaryDirectory() as fake_dir:
            stub = Path(fake_dir) / "gin-orchestrator"
            stub.write_text(
                "#!/bin/sh\n"
                "echo '{\"contract_version\": 2, \"orchestrator_version\": \"x\"}'\n"
                "exit 0\n",
                encoding="utf-8",
            )
            stub.chmod(0o755)

            with mock.patch.dict(os.environ, {"PATH": f"{fake_dir}{os.pathsep}{os.environ.get('PATH', '')}"}):
                with self.assertRaises(orchestrator_client.OrchestratorError) as ctx:
                    orchestrator_client.health("codex", "/nonexistent")
                self.assertEqual("orchestrator_contract_mismatch", str(ctx.exception))

                orchestrator_client._checked.cache_clear()
                with self.assertRaises(orchestrator_client.OrchestratorError) as ctx:
                    orchestrator_client.models("codex")
                self.assertEqual("orchestrator_contract_mismatch", str(ctx.exception))

    def test_command_failure_raises_failed_or_returns_empty_models(self) -> None:
        with tempfile.TemporaryDirectory() as fake_dir:
            stub = Path(fake_dir) / "gin-orchestrator"
            stub.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            stub.chmod(0o755)

            with mock.patch.dict(os.environ, {"PATH": f"{fake_dir}{os.pathsep}{os.environ.get('PATH', '')}"}):
                with self.assertRaises(orchestrator_client.OrchestratorError) as ctx:
                    orchestrator_client.health("codex", "/nonexistent")
                self.assertEqual("orchestrator_failed", str(ctx.exception))

                orchestrator_client._checked.cache_clear()
                self.assertEqual([], orchestrator_client.models("codex"))

    def test_path_orchestrator_precedence_over_bundled(self) -> None:
        with tempfile.TemporaryDirectory() as fake_dir:
            stub = Path(fake_dir) / "gin-orchestrator"
            stub.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"version\" ]; then\n"
                "  echo '{\"contract_version\": 1, \"orchestrator_version\": \"fake\"}'\n"
                "  exit 0\n"
                "fi\n"
                "if [ \"$1\" = \"models\" ]; then\n"
                "  echo '[{\"id\": \"m\"}]'\n"
                "  exit 0\n"
                "fi\n"
                "exit 0\n",
                encoding="utf-8",
            )
            stub.chmod(0o755)

            with mock.patch.dict(os.environ, {"PATH": f"{fake_dir}{os.pathsep}{os.environ.get('PATH', '')}"}):
                self.assertEqual([{"id": "m"}], orchestrator_client.models("codex"))


if __name__ == "__main__":
    unittest.main()

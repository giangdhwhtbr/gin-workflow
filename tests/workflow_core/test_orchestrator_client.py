"""Tests for workflow_core.orchestrator_client."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins/gin-workflow/src/scripts"))

from tests.workflow_core.orchestrator_fakes import (  # noqa: E402
    call_count,
    fake_orchestrator,
    on_path,
)
from workflow_core import orchestrator_client  # noqa: E402


class OrchestratorClientTests(unittest.TestCase):
    def test_status_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as empty_dir:
            with on_path(empty_dir):
                # Ensure gin-orchestrator is not found on PATH
                os.environ["PATH"] = empty_dir
                st = orchestrator_client.status()
                self.assertFalse(st["available"])
                self.assertEqual(orchestrator_client.MISSING, st["reason"])
                self.assertIsNone(st["version"])
                self.assertIsNone(st["contract"])
                self.assertEqual([], st["capabilities"])

    def test_status_with_contract_1_is_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as fake_dir:
            fake_orchestrator(fake_dir, contract=1)
            with on_path(fake_dir):
                st = orchestrator_client.status()
                self.assertFalse(st["available"])
                self.assertEqual(orchestrator_client.MISMATCH, st["reason"])

    def test_status_lists_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as fake_dir:
            fake_orchestrator(fake_dir, contract=2, capabilities=["routes", "reviewer"])
            with on_path(fake_dir):
                st = orchestrator_client.status()
                self.assertTrue(st["available"])
                self.assertIsNone(st["reason"])
                self.assertEqual(2, st["contract"])
                self.assertEqual(["routes", "reviewer"], st["capabilities"])

    def test_delegates_only_in_multi_mode_with_the_capability(self) -> None:
        with tempfile.TemporaryDirectory() as fake_dir:
            fake_orchestrator(fake_dir, contract=2, capabilities=["routes"])
            with on_path(fake_dir):
                self.assertTrue(orchestrator_client.delegates({"provider_mode": "multi"}, "routes"))
                self.assertFalse(orchestrator_client.delegates({"provider_mode": "single"}, "routes"))
                self.assertFalse(orchestrator_client.delegates({"provider_mode": "multi"}, "reviewer"))
                self.assertFalse(orchestrator_client.delegates({}, "routes"))

    def test_call_failure_raises_failed(self) -> None:
        with tempfile.TemporaryDirectory() as fake_dir:
            fake_orchestrator(fake_dir, contract=2, fail=["health"])
            with on_path(fake_dir):
                with self.assertRaises(orchestrator_client.OrchestratorError) as ctx:
                    orchestrator_client.call(["health"])
                self.assertEqual(orchestrator_client.FAILED, str(ctx.exception))

    def test_status_runs_version_once(self) -> None:
        with tempfile.TemporaryDirectory() as fake_dir:
            fake_orchestrator(fake_dir, contract=2)
            with on_path(fake_dir):
                self.assertEqual(0, call_count(fake_dir, "version"))
                orchestrator_client.status()
                orchestrator_client.status()
                orchestrator_client.status()
                self.assertEqual(1, call_count(fake_dir, "version"))

    def test_models_delegation(self) -> None:
        with tempfile.TemporaryDirectory() as fake_dir:
            fake_orchestrator(fake_dir, contract=2, replies={"models": [{"id": "m1"}]})
            with on_path(fake_dir):
                self.assertEqual([{"id": "m1"}], orchestrator_client.models("codex"))

        with tempfile.TemporaryDirectory() as fake_dir:
            fake_orchestrator(fake_dir, contract=2, fail=["models"])
            with on_path(fake_dir):
                self.assertEqual([], orchestrator_client.models("codex"))

        with tempfile.TemporaryDirectory() as empty_dir:
            with on_path(empty_dir):
                os.environ["PATH"] = empty_dir
                self.assertEqual([], orchestrator_client.models("codex"))

    def test_models_needs_an_available_orchestrator_with_the_capability(self) -> None:
        for kwargs in ({"contract": 1}, {"contract": 2, "capabilities": ["routes"]}):
            with tempfile.TemporaryDirectory() as fake_dir:
                fake_orchestrator(fake_dir, replies={"models": [{"id": "m1"}]}, **kwargs)
                with on_path(fake_dir):
                    self.assertEqual([], orchestrator_client.models("codex"), kwargs)
                    self.assertEqual(0, call_count(fake_dir, "models"), kwargs)


if __name__ == "__main__":
    unittest.main()

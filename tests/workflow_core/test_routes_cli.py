import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core import cli, routes
from workflow_core.setup_service import refresh
from tests.workflow_core.orchestrator_fakes import fake_orchestrator, on_path


class TestRoutesCLI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        cfg_dir = self.root / ".agent-workflow"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        config_content = (
            "harness: claude\n"
            "provider_mode: single\n"
            "schema_version: '2.7'\n"
            "routing:\n"
            "  roles:\n"
            "    backend:\n"
            "      preferred:\n"
            "      - main_harness\n"
        )
        (cfg_dir / "config.yaml").write_text(config_content, encoding="utf-8")
        refresh(self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_single_harness_routes_every_track_to_the_main_harness(self):
        tracks_file = self.root / "tracks.json"
        tracks_data = [
            {"task_id": "t1", "provider_role": "backend", "reasoning": "medium"},
            {"task_id": "t2", "provider_role": "backend", "reasoning": "low"},
        ]
        tracks_file.write_text(json.dumps(tracks_data), encoding="utf-8")

        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = routes.main([
                "resolve",
                "--workflow-id", "wf-1",
                "--tracks", str(tracks_file),
                "--repository", str(self.root),
                "--json",
            ])
        self.assertEqual(code, 0)
        output = json.loads(stdout.getvalue())
        self.assertEqual(output["workflow_id"], "wf-1")
        self.assertEqual(output["main_harness"], "claude")
        self.assertEqual(len(output["routes"]), 2)
        self.assertEqual(output["routes"][0]["resolved"]["provider"], "claude")
        self.assertEqual(output["routes"][1]["resolved"]["provider"], "claude")
        self.assertEqual(output["diagnostics"], [])
        manifest_path = self.root / output["manifest"]
        self.assertTrue(manifest_path.is_file())

    def test_unknown_role_writes_nothing_and_lists_every_diagnostic(self):
        tracks_file = self.root / "tracks.json"
        tracks_data = [
            {"task_id": "t1", "provider_role": "unknown_role", "reasoning": "invalid_tier"},
        ]
        tracks_file.write_text(json.dumps(tracks_data), encoding="utf-8")

        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = routes.main([
                "resolve",
                "--workflow-id", "wf-2",
                "--tracks", str(tracks_file),
                "--repository", str(self.root),
                "--json",
            ])
        self.assertEqual(code, 2)
        output = json.loads(stdout.getvalue())
        self.assertEqual(len(output["diagnostics"]), 2)
        self.assertIn("t1.provider_role: unknown provider role: unknown_role", output["diagnostics"])
        self.assertIn("t1.reasoning: reasoning must be one of: low, medium, high", output["diagnostics"])
        manifest = self.root / ".agent-workflow/runtime/assignments/wf-2.yaml"
        self.assertFalse(manifest.exists())

    def _resolve(self, workflow_id, tracks):
        tracks_file = self.root / "tracks.json"
        tracks_file.write_text(json.dumps(tracks), encoding="utf-8")
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = routes.main(["resolve", "--workflow-id", workflow_id, "--tracks", str(tracks_file),
                                "--repository", str(self.root)])
        return code, json.loads(stdout.getvalue())

    def test_unsafe_workflow_id_is_a_diagnostic(self):
        code, output = self._resolve("../evil", [{"task_id": "t1", "provider_role": "backend", "reasoning": "low"}])
        self.assertEqual(code, 2)
        self.assertEqual(len(output["diagnostics"]), 1)
        self.assertTrue(output["diagnostics"][0].startswith("workflow_id: "))
        self.assertIsNone(output["manifest"])

    def test_missing_and_duplicate_task_ids_are_diagnostics(self):
        track = {"provider_role": "backend", "reasoning": "low"}
        code, output = self._resolve("wf-3", [{"task_id": "t1", **track}, {"task_id": "t1", **track}, track])
        self.assertEqual(code, 2)
        self.assertEqual(output["diagnostics"], ["t1.task_id: duplicate task_id",
                                                 "task-3.task_id: task_id is required"])
        self.assertFalse((self.root / ".agent-workflow/runtime/assignments/wf-3.yaml").exists())

    def test_paths_prints_the_library_dir(self):
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = cli.main(["paths", "--json"])
        self.assertEqual(code, 0)
        output = json.loads(stdout.getvalue())
        lib_dir = Path(output["lib_dir"])
        self.assertTrue((lib_dir / "workflow_core/ext.py").is_file())

    def _set_multi_mode(self):
        cfg_dir = self.root / ".agent-workflow"
        config_content = (
            "harness: claude\n"
            "provider_mode: multi\n"
            "schema_version: '2.8'\n"
            "routing:\n"
            "  roles:\n"
            "    backend:\n"
            "      preferred:\n"
            "      - main_harness\n"
        )
        (cfg_dir / "config.yaml").write_text(config_content, encoding="utf-8")
        refresh(self.root)

    def test_multi_mode_delegates_and_writes_the_returned_routes(self):
        self._set_multi_mode()
        codex_route = {
            "task_id": "t1",
            "requested": {"provider_role": "backend", "reasoning": "medium"},
            "resolved": {"provider": "codex", "model": "opus", "fallback": False},
            "fallback": [],
        }
        with tempfile.TemporaryDirectory() as fake_dir:
            fake_orchestrator(
                fake_dir,
                contract=2,
                capabilities=["routes"],
                replies={
                    "routes resolve": {
                        "workflow_id": "wf-multi",
                        "main_harness": "claude",
                        "routes": [codex_route],
                        "diagnostics": [],
                    }
                },
            )
            with on_path(fake_dir):
                code, output = self._resolve(
                    "wf-multi",
                    [{"task_id": "t1", "provider_role": "backend", "reasoning": "medium"}],
                )
                self.assertEqual(0, code)
                self.assertEqual("wf-multi", output["workflow_id"])
                self.assertEqual("codex", output["routes"][0]["resolved"]["provider"])
                manifest_path = self.root / output["manifest"]
                self.assertTrue(manifest_path.is_file())
                self.assertIn("codex", manifest_path.read_text(encoding="utf-8"))

    def test_multi_mode_diagnostics_from_orchestrator_exit_2_and_write_nothing(self):
        self._set_multi_mode()
        with tempfile.TemporaryDirectory() as fake_dir:
            fake_orchestrator(
                fake_dir,
                contract=2,
                capabilities=["routes"],
                replies={
                    "routes resolve": {
                        "workflow_id": "wf-diag",
                        "main_harness": "claude",
                        "routes": [],
                        "diagnostics": ["t1.route: capacity exceeded"],
                    }
                },
            )
            with on_path(fake_dir):
                code, output = self._resolve(
                    "wf-diag",
                    [{"task_id": "t1", "provider_role": "backend", "reasoning": "medium"}],
                )
                self.assertEqual(2, code)
                self.assertEqual(["t1.route: capacity exceeded"], output["diagnostics"])
                self.assertFalse((self.root / ".agent-workflow/runtime/assignments/wf-diag.yaml").exists())

    def test_failing_orchestrator_falls_back_with_a_warning(self):
        self._set_multi_mode()
        with tempfile.TemporaryDirectory() as fake_dir:
            fake_orchestrator(fake_dir, contract=2, capabilities=["routes"], fail=["routes resolve"])
            with on_path(fake_dir):
                code, output = self._resolve(
                    "wf-fail",
                    [{"task_id": "t1", "provider_role": "backend", "reasoning": "medium"}],
                )
                self.assertEqual(0, code)
                self.assertEqual("claude", output["routes"][0]["resolved"]["provider"])
                self.assertTrue(
                    any("gin-orchestrator failed" in w and "routing every track to the main harness" in w for w in output["warnings"]),
                    output["warnings"],
                )
                manifest_path = self.root / output["manifest"]
                self.assertTrue(manifest_path.is_file())

    def test_missing_routes_capability_falls_back(self):
        self._set_multi_mode()
        with tempfile.TemporaryDirectory() as fake_dir:
            fake_orchestrator(fake_dir, contract=2, capabilities=["doctor"])
            with on_path(fake_dir):
                code, output = self._resolve(
                    "wf-nocap",
                    [{"task_id": "t1", "provider_role": "backend", "reasoning": "medium"}],
                )
                self.assertEqual(0, code)
                self.assertEqual("claude", output["routes"][0]["resolved"]["provider"])

    def test_single_mode_never_calls_the_orchestrator(self):
        with tempfile.TemporaryDirectory() as fake_dir:
            fake_orchestrator(
                fake_dir,
                contract=2,
                fail=["version", "routes", "routes resolve"],
            )
            with on_path(fake_dir):
                code, output = self._resolve(
                    "wf-single",
                    [{"task_id": "t1", "provider_role": "backend", "reasoning": "medium"}],
                )
                self.assertEqual(0, code)
                self.assertEqual("claude", output["routes"][0]["resolved"]["provider"])



if __name__ == "__main__":
    unittest.main()

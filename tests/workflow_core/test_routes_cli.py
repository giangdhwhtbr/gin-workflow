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
            {"task_id": "t1", "provider_role": "backend", "model": "sonnet", "effort": "medium"},
            {"task_id": "t2", "provider_role": "backend", "model": "haiku", "effort": "low"},
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
        r1 = output["routes"][0]
        self.assertEqual(r1["requested"]["model"], "sonnet")
        self.assertEqual(r1["requested"]["effort"], "medium")
        self.assertEqual(r1["resolved"]["provider"], "claude")
        self.assertEqual(r1["resolved"]["model"], "sonnet")
        self.assertEqual(r1["resolved"]["effort"], "medium")
        r2 = output["routes"][1]
        self.assertEqual(r2["requested"]["model"], "haiku")
        self.assertEqual(r2["requested"]["effort"], "low")
        self.assertEqual(r2["resolved"]["provider"], "claude")
        self.assertEqual(r2["resolved"]["model"], "haiku")
        self.assertEqual(r2["resolved"]["effort"], "low")
        self.assertEqual(output["diagnostics"], [])
        manifest_path = self.root / output["manifest"]
        self.assertTrue(manifest_path.is_file())

    def test_unknown_role_writes_nothing_and_lists_every_diagnostic(self):
        tracks_file = self.root / "tracks.json"
        tracks_data = [
            {"task_id": "t1", "provider_role": "unknown_role", "model": "sonnet", "effort": "medium"},
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
        self.assertEqual(len(output["diagnostics"]), 1)
        self.assertIn("track t1: unknown provider role: unknown_role", output["diagnostics"])
        manifest = self.root / ".agent-workflow/runtime/assignments/wf-2.yaml"
        self.assertFalse(manifest.exists())

    def test_diagnostics_unknown_model_effort_antigravity_and_reasoning_only(self):
        tracks = [
            {"task_id": "t1", "provider_role": "backend", "model": "bad_model", "effort": "low"},
            {"task_id": "t2", "provider_role": "backend", "model": "sonnet", "effort": "bad_effort"},
            {"task_id": "t3", "provider_role": "backend", "reasoning": "medium"},
        ]
        code, output = self._resolve("wf-diag-all", tracks)
        self.assertEqual(code, 2)
        diags = output["diagnostics"]
        self.assertTrue(any("track t1: model 'bad_model' is not in the catalog; allowed:" in d for d in diags), diags)
        self.assertTrue(any("track t2: effort 'bad_effort' is not in the catalog; allowed:" in d for d in diags), diags)
        self.assertIn("track t3: reasoning is replaced by model and effort", diags)
        self.assertFalse((self.root / ".agent-workflow/runtime/assignments/wf-diag-all.yaml").exists())

        # Antigravity main harness with effort
        cfg_dir = self.root / ".agent-workflow"
        (cfg_dir / "config.yaml").write_text(
            "harness: antigravity\nprovider_mode: single\nschema_version: '2.9'\nrouting:\n  roles:\n    backend:\n      preferred: [main_harness]\n",
            encoding="utf-8",
        )
        refresh(self.root)
        code, output = self._resolve("wf-ag", [{"task_id": "t4", "provider_role": "backend", "model": "provider_default", "effort": "low"}])
        self.assertEqual(code, 2)
        self.assertIn("track t4: effort 'low' given, but the catalog lists no efforts", output["diagnostics"])
        self.assertFalse((self.root / ".agent-workflow/runtime/assignments/wf-ag.yaml").exists())

    def test_claude_accepts_high_effort(self):
        tracks = [{"task_id": "t1", "provider_role": "backend", "model": "sonnet", "effort": "high"}]
        code, output = self._resolve("wf-high", tracks)
        self.assertEqual(code, 0)
        self.assertEqual("high", output["routes"][0]["resolved"]["effort"])

    def _resolve(self, workflow_id, tracks):
        tracks_file = self.root / "tracks.json"
        tracks_file.write_text(json.dumps(tracks), encoding="utf-8")
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = routes.main(["resolve", "--workflow-id", workflow_id, "--tracks", str(tracks_file),
                                "--repository", str(self.root)])
        return code, json.loads(stdout.getvalue())

    def test_unsafe_workflow_id_is_a_diagnostic(self):
        code, output = self._resolve("../evil", [{"task_id": "t1", "provider_role": "backend", "model": "haiku", "effort": "low"}])
        self.assertEqual(code, 2)
        self.assertEqual(len(output["diagnostics"]), 1)
        self.assertTrue(output["diagnostics"][0].startswith("workflow_id: "))
        self.assertIsNone(output["manifest"])

    def test_missing_and_duplicate_task_ids_are_diagnostics(self):
        track = {"provider_role": "backend", "model": "haiku", "effort": "low"}
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
            "requested": {"provider_role": "backend", "model": "sonnet", "effort": "medium"},
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
                    [{"task_id": "t1", "provider_role": "backend", "model": "sonnet", "effort": "medium"}],
                )
                self.assertEqual(0, code)
                self.assertEqual("wf-multi", output["workflow_id"])
                self.assertEqual("codex", output["routes"][0]["resolved"]["provider"])
                manifest_path = self.root / output["manifest"]
                self.assertTrue(manifest_path.is_file())
                self.assertIn("codex", manifest_path.read_text(encoding="utf-8"))

    def test_delegation_forwards_model_and_effort(self):
        self._set_multi_mode()
        received_tracks = None

        def fake_call(cmd):
            nonlocal received_tracks
            tracks_idx = cmd.index("--tracks") + 1
            received_tracks = json.loads(Path(cmd[tracks_idx]).read_text(encoding="utf-8"))
            return {
                "workflow_id": "wf-fwd",
                "main_harness": "claude",
                "routes": [{
                    "task_id": "t1",
                    "requested": {"provider_role": "backend", "model": "sonnet", "effort": "medium"},
                    "resolved": {"provider": "claude", "model": "sonnet", "effort": "medium", "selection_mode": "explicit"},
                    "fallback": [],
                }],
                "diagnostics": [],
            }

        with patch("workflow_core.orchestrator_client.delegates", return_value=True), \
             patch("workflow_core.orchestrator_client.call", side_effect=fake_call):
            code, output = self._resolve(
                "wf-fwd",
                [{"task_id": "t1", "provider_role": "backend", "model": "sonnet", "effort": "medium"}],
            )
            self.assertEqual(0, code)
            self.assertIsNotNone(received_tracks)
            self.assertEqual("sonnet", received_tracks[0]["model"])
            self.assertEqual("medium", received_tracks[0]["effort"])

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
                    [{"task_id": "t1", "provider_role": "backend", "model": "sonnet", "effort": "medium"}],
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
                    [{"task_id": "t1", "provider_role": "backend", "model": "sonnet", "effort": "medium"}],
                )
                self.assertEqual(0, code)
                self.assertEqual("claude", output["routes"][0]["resolved"]["provider"])
                self.assertTrue(
                    any("gin-orchestrator failed" in w and "routing every track to the main harness" in w for w in output["warnings"]),
                    output["warnings"],
                )
                manifest_path = self.root / output["manifest"]
                self.assertTrue(manifest_path.is_file())

    def test_role_owned_by_the_absent_orchestrator_routes_to_the_main_harness(self):
        self._set_multi_mode()
        config = self.root / ".agent-workflow/config.yaml"
        config.write_text(config.read_text(encoding="utf-8")
                          + "orchestrator:\n  roles:\n    mobile:\n      preferred:\n      - codex\n", encoding="utf-8")
        refresh(self.root)
        with tempfile.TemporaryDirectory() as empty_dir, on_path(empty_dir), patch.dict("os.environ", {"PATH": empty_dir}):
            code, output = self._resolve("wf-owned", [{"task_id": "t1", "provider_role": "mobile", "model": "haiku", "effort": "low"},
                                                      {"task_id": "t2", "provider_role": "nope", "model": "haiku", "effort": "low"}])
            self.assertEqual(2, code)
            self.assertEqual(["track t2: unknown provider role: nope"], output["diagnostics"])
            code, output = self._resolve("wf-owned", [{"task_id": "t1", "provider_role": "mobile", "model": "haiku", "effort": "low"}])
            self.assertEqual(0, code, output)
            self.assertEqual("claude", output["routes"][0]["resolved"]["provider"])
            self.assertTrue(any("orchestrator_missing" in w for w in output["warnings"]), output["warnings"])

    def test_malformed_orchestrator_reply_falls_back_with_a_warning(self):
        self._set_multi_mode()
        for reply in (["t1"], {"routes": None}, {"diagnostics": "bad"}):
            with tempfile.TemporaryDirectory() as fake_dir:
                fake_orchestrator(fake_dir, contract=2, capabilities=["routes"], replies={"routes resolve": reply})
                with on_path(fake_dir):
                    code, output = self._resolve(
                        "wf-bad",
                        [{"task_id": "t1", "provider_role": "backend", "model": "sonnet", "effort": "medium"}],
                    )
                    self.assertEqual(0, code, reply)
                    self.assertEqual("claude", output["routes"][0]["resolved"]["provider"])
                    self.assertTrue(any("orchestrator_failed" in w for w in output["warnings"]), output["warnings"])

    def test_missing_routes_capability_falls_back(self):
        self._set_multi_mode()
        with tempfile.TemporaryDirectory() as fake_dir:
            fake_orchestrator(fake_dir, contract=2, capabilities=["doctor"])
            with on_path(fake_dir):
                code, output = self._resolve(
                    "wf-nocap",
                    [{"task_id": "t1", "provider_role": "backend", "model": "sonnet", "effort": "medium"}],
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
                    [{"task_id": "t1", "provider_role": "backend", "model": "sonnet", "effort": "medium"}],
                )
                self.assertEqual(0, code)
                self.assertEqual("claude", output["routes"][0]["resolved"]["provider"])

    def _write_manifest(self, workflow_id, entries):
        import yaml
        manifest_dir = self.root / ".agent-workflow/runtime/assignments"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = manifest_dir / f"{workflow_id}.yaml"
        tracks_map = {}
        for entry in entries:
            tid = entry["task_id"]
            tracks_map[tid] = {k: v for k, v in entry.items() if k != "task_id"}
        manifest_file.write_text(yaml.safe_dump({"workflow_id": workflow_id, "assignments": entries, "tracks": tracks_map}), encoding="utf-8")
        return manifest_file

    def test_dispatch_prints_route_and_appends_dispatched_event(self):
        entry = {
            "task_id": "t1",
            "requested": {"provider_role": "backend", "model": "sonnet", "effort": "medium"},
            "resolved": {"provider": "claude", "model": "sonnet", "effort": "medium", "selection_mode": "explicit"},
            "fallback": [],
            "escalations": [],
        }
        self._write_manifest("wf-disp", [entry])

        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = routes.main([
                "dispatch",
                "--workflow-id", "wf-disp",
                "--task-id", "t1",
                "--repository", str(self.root),
                "--json",
            ])
        self.assertEqual(0, code)
        data = json.loads(stdout.getvalue())
        self.assertEqual("t1", data["task_id"])
        self.assertEqual("claude", data["provider"])
        self.assertEqual("sonnet", data["model"])
        self.assertEqual("medium", data["effort"])
        self.assertFalse(data["escalated"])

        events_file = self.root / ".agent-workflow/runtime/events.jsonl"
        self.assertTrue(events_file.is_file())
        events = [json.loads(line) for line in events_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        e = events[0]
        self.assertEqual("route.dispatched", e["event_type"])
        self.assertEqual("t1", e["task_id"])
        self.assertEqual("wf-disp", e["workflow_id"])
        self.assertEqual("claude", e["payload"]["provider"])
        self.assertEqual("sonnet", e["payload"]["model"])
        self.assertEqual("medium", e["payload"]["effort"])
        self.assertIsNone(e["payload"]["reason"])

    def test_dispatch_escalate_haiku_low_gives_sonnet_low(self):
        entry = {
            "task_id": "t1",
            "requested": {"provider_role": "backend", "model": "haiku", "effort": "low"},
            "resolved": {"provider": "claude", "model": "haiku", "effort": "low", "selection_mode": "explicit"},
            "fallback": [],
            "escalations": [],
        }
        self._write_manifest("wf-esc-haiku", [entry])

        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = routes.main([
                "dispatch",
                "--workflow-id", "wf-esc-haiku",
                "--task-id", "t1",
                "--escalate", "tests fail",
                "--repository", str(self.root),
                "--json",
            ])
        self.assertEqual(0, code)
        data = json.loads(stdout.getvalue())
        self.assertEqual("sonnet", data["model"])
        self.assertEqual("low", data["effort"])
        self.assertTrue(data["escalated"])

        # Check manifest updated
        import yaml
        manifest_data = yaml.safe_load((self.root / ".agent-workflow/runtime/assignments/wf-esc-haiku.yaml").read_text(encoding="utf-8"))
        res = manifest_data["tracks"]["t1"]["resolved"]
        self.assertEqual("sonnet", res["model"])
        self.assertEqual("low", res["effort"])
        escs = manifest_data["tracks"]["t1"]["escalations"]
        self.assertEqual(1, len(escs))
        self.assertEqual({"model": "haiku", "effort": "low"}, escs[0]["from"])
        self.assertEqual({"model": "sonnet", "effort": "low"}, escs[0]["to"])
        self.assertEqual("tests fail", escs[0]["reason"])

    def test_dispatch_escalate_opus_max_exits_2_and_leaves_manifest_unchanged(self):
        entry = {
            "task_id": "t1",
            "requested": {"provider_role": "backend", "model": "opus", "effort": "max"},
            "resolved": {"provider": "claude", "model": "opus", "effort": "max", "selection_mode": "explicit"},
            "fallback": [],
            "escalations": [],
        }
        manifest_file = self._write_manifest("wf-esc-opus", [entry])
        initial_content = manifest_file.read_text(encoding="utf-8")

        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = routes.main([
                "dispatch",
                "--workflow-id", "wf-esc-opus",
                "--task-id", "t1",
                "--escalate", "cannot pass",
                "--repository", str(self.root),
                "--json",
            ])
        self.assertEqual(2, code)
        data = json.loads(stdout.getvalue())
        self.assertEqual("human_decision_required", data["status"])
        self.assertEqual(initial_content, manifest_file.read_text(encoding="utf-8"))

    def test_dispatch_escalate_codex_high_gives_xhigh(self):
        entry = {
            "task_id": "t1",
            "requested": {"provider_role": "backend", "model": "sonnet", "effort": "medium"},
            "resolved": {"provider": "codex", "model": "gpt-6-astra", "effort": "high", "selection_mode": "explicit"},
            "fallback": [],
            "escalations": [],
        }
        self._write_manifest("wf-esc-codex", [entry])

        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = routes.main([
                "dispatch",
                "--workflow-id", "wf-esc-codex",
                "--task-id", "t1",
                "--escalate", "codex retry",
                "--repository", str(self.root),
                "--json",
            ])
        self.assertEqual(0, code)
        data = json.loads(stdout.getvalue())
        self.assertEqual("gpt-6-astra", data["model"])
        self.assertEqual("xhigh", data["effort"])
        self.assertTrue(data["escalated"])

    def test_dispatch_reads_manifest_with_requested_reasoning(self):
        import yaml
        manifest_dir = self.root / ".agent-workflow/runtime/assignments"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        old_data = {
            "workflow_id": "wf-old",
            "assignments": [
                {
                    "task_id": "t1",
                    "requested": {"provider_role": "backend", "reasoning": "medium"},
                    "resolved": {"provider": "claude", "model": "sonnet", "selection_mode": "explicit"},
                    "fallback": [],
                }
            ],
        }
        (manifest_dir / "wf-old.yaml").write_text(yaml.safe_dump(old_data), encoding="utf-8")

        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = routes.main([
                "dispatch",
                "--workflow-id", "wf-old",
                "--task-id", "t1",
                "--repository", str(self.root),
                "--json",
            ])
        self.assertEqual(0, code)
        data = json.loads(stdout.getvalue())
        self.assertEqual("t1", data["task_id"])
        self.assertEqual("claude", data["provider"])
        self.assertEqual("sonnet", data["model"])
        self.assertIsNone(data["effort"])
        self.assertFalse(data["escalated"])



if __name__ == "__main__":
    unittest.main()

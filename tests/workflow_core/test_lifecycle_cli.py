"""Unit tests for gin-workflow state and gin-workflow unblock CLI subcommands."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from workflow_core.cli import main as cli_main
from workflow_core.events import WorkflowEvent, WorkflowEventStore
from workflow_core.lifecycle_cli import main as lifecycle_main


class TestLifecycleCLI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.test_dir)
        # Create minimal setup config so EffectiveConfig resolves
        self.workflow_dir = self.repo_path / ".agent-workflow"
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        (self.workflow_dir / "config.yaml").write_text("schema_version: '2.3'\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_version_flag_returns_version(self):
        exit_code = cli_main(["--version"])
        self.assertEqual(0, exit_code)

    def test_unknown_command_returns_error(self):
        exit_code = cli_main(["unknown"])
        self.assertEqual(2, exit_code)

    def test_state_command_returns_unmet_gate_and_remedies(self):
        exit_code = lifecycle_main([
            "state",
            "--repository", str(self.repo_path),
            "--format", "json",
        ])
        self.assertEqual(0, exit_code)

    def test_state_json_format_has_required_keys(self):
        import io
        from unittest.mock import patch

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            exit_code = lifecycle_main([
                "state",
                "--repository", str(self.repo_path),
                "--format", "json",
            ])
            output = fake_out.getvalue()

        data = json.loads(output)
        self.assertIn("stage", data)
        self.assertIn("decision", data)
        self.assertIn("gates", data)
        self.assertIn("evidence", data)
        self.assertIn("remedies", data)
        self.assertEqual("unmet", data["gates"]["requirement_confirmed"])

    def test_state_derives_completed_process_gates_from_matching_workflow_events(self):
        workflow_id = "two-factor"
        event_store = WorkflowEventStore(self.workflow_dir / "runtime" / "events.jsonl")
        for event_type, payload in (
            ("requirement.confirmed", {"stage": "discuss"}),
            (
                "approval.recorded",
                {
                    "action": "plan_approved",
                    "decision": {"status": "approved"},
                },
            ),
            ("orchestration.ready", {"stage": "orchestrate"}),
        ):
            event_store.append(
                WorkflowEvent.create(
                    event_type=event_type,
                    workflow_id=workflow_id,
                    payload=payload,
                )
            )
        event_store.append(
            WorkflowEvent.create(
                event_type="requirement.confirmed",
                workflow_id="another-workflow",
                payload={"state": "requirement_confirmed"},
            )
        )

        import io
        from unittest.mock import patch

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            exit_code = lifecycle_main([
                "state",
                "--repository", str(self.repo_path),
                "--workflow-id", workflow_id,
                "--format", "json",
            ])
            output = fake_out.getvalue()

        self.assertEqual(0, exit_code)
        data = json.loads(output)
        self.assertEqual("execute", data["stage"])
        self.assertEqual("satisfied", data["gates"]["requirement_confirmed"])
        self.assertEqual("satisfied", data["gates"]["plan_approved"])
        self.assertEqual("satisfied", data["gates"]["orchestration_ready"])

    def _state_json(self):
        import io
        from unittest.mock import patch

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            lifecycle_main(["state", "--repository", str(self.repo_path), "--format", "json"])
        return json.loads(fake_out.getvalue())

    def test_state_reports_project_block(self):
        self.assertEqual("fullstack", self._state_json()["project"]["shape"])
        (self.workflow_dir / "config.yaml").write_text("schema_version: '2.4'\nproject: {shape: frontend}\n")
        self.assertEqual("frontend", self._state_json()["project"]["shape"])

    def _write_config(self, text):
        (self.workflow_dir / "config.yaml").write_text(text)

    def _quick(self, *extra):
        import io
        from unittest.mock import patch
        with patch("sys.stdout", new=io.StringIO()) as out:
            code = cli_main(["quick-check", "--repository", str(self.repo_path), "--format", "json", *extra])
        return code, json.loads(out.getvalue())

    def test_quick_check_allows_small_change_with_rigor_commands(self):
        self._write_config("schema_version: '2.4'\nproject: {rigor: easy}\n"
                           "verify: {checks: {lint: l, typecheck: t, test: u, build: b, e2e: e}}\n")
        code, payload = self._quick("--changed-files", "2", "--modules", "1")
        self.assertEqual((0, "allowed", "self_check"), (code, payload["decision"], payload["review"]))
        self.assertEqual({"lint": "l", "typecheck": "t", "test": "u"}, payload["verify_commands"])

    def test_quick_check_escalates_over_threshold_or_multiple_modules(self):
        self._write_config("schema_version: '2.4'\nproject: {rigor: standard}\nquick: {max_files: 3}\n")
        self.assertEqual(3, self._quick("--changed-files", "4", "--modules", "1")[0])
        self.assertEqual(3, self._quick("--changed-files", "1", "--modules", "2")[0])

    def test_quick_check_refuses_strict_without_waiver(self):
        self._write_config("schema_version: '2.4'\nproject: {rigor: strict}\n")
        code, payload = self._quick("--changed-files", "1", "--modules", "1")
        self.assertEqual((4, "refused"), (code, payload["decision"]))
        cli_main(["unblock", "--repository", str(self.repo_path), "--gate", "requirement_confirmed",
                  "--reason", "hotfix", "--actor", "user"])
        self.assertEqual(0, self._quick("--changed-files", "1", "--modules", "1")[0])

    def test_record_quick_completed_shows_in_state(self):
        self.assertEqual(0, cli_main(["record", "quick-completed", "--repository", str(self.repo_path),
                                      "--evidence", "lint ok; 3 tests ok", "--actor", "user"]))
        self.assertEqual("lint ok; 3 tests ok", self._state_json()["recent_quick"][-1]["evidence"])

    def test_unblock_safety_gate_without_followup_fails(self):
        exit_code = lifecycle_main([
            "unblock",
            "--gate", "verification_passed",
            "--reason", "skipping verification for doc change",
            "--actor", "operator",
            "--repository", str(self.repo_path),
        ])
        self.assertNotEqual(0, exit_code)

    def test_unblock_non_waivable_gate_fails(self):
        exit_code = lifecycle_main([
            "unblock",
            "--gate", "implementation_complete",
            "--reason", "cannot waive fact",
            "--actor", "operator",
            "--repository", str(self.repo_path),
        ])
        self.assertNotEqual(0, exit_code)

    def test_unblock_process_gate_and_state_reflects_waiver(self):
        # 1. Unblock plan_approved
        unblock_code = lifecycle_main([
            "unblock",
            "--gate", "requirement_confirmed",
            "--reason", "requirement confirmed in conversation",
            "--actor", "operator",
            "--repository", str(self.repo_path),
        ])
        self.assertEqual(0, unblock_code)

        # 2. Check state reflects waived gate
        import io
        from unittest.mock import patch

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            state_code = lifecycle_main([
                "state",
                "--repository", str(self.repo_path),
                "--format", "json",
            ])
            output = fake_out.getvalue()

        data = json.loads(output)
        self.assertIn("waived", data["gates"]["requirement_confirmed"])

    def test_resolve_scope_hash_discovers_scoped_and_legacy_ledgers(self):
        from workflow_core.lifecycle_cli import _resolve_scope_hash

        # When only scoped exists
        scoped_dir = self.repo_path / ".planning" / "reviews" / "scoped-bead"
        scoped_dir.mkdir(parents=True, exist_ok=True)
        (scoped_dir / "review.json").write_text(json.dumps({"repositories": [{"source_scope_hash": "sha-scoped-123"}]}))
        self.assertEqual(_resolve_scope_hash(self.repo_path), "sha-scoped-123")

        # When legacy exists in a clean repo
        legacy_repo = Path(tempfile.mkdtemp())
        try:
            legacy_dir = legacy_repo / ".planning" / "legacy-bead"
            legacy_dir.mkdir(parents=True, exist_ok=True)
            (legacy_dir / "review.json").write_text(json.dumps({"repositories": [{"source_scope_hash": "sha-legacy-456"}]}))
            self.assertEqual(_resolve_scope_hash(legacy_repo), "sha-legacy-456")
        finally:
            shutil.rmtree(legacy_repo)

    def _state_gates(self, workflow_id="default-workflow"):
        import io
        from unittest.mock import patch

        with patch("sys.stdout", new=io.StringIO()) as out:
            lifecycle_main(["state", "--repository", str(self.repo_path), "--format", "json", "--workflow-id", workflow_id])
        return json.loads(out.getvalue())["gates"]

    def test_record_marks_each_process_gate_satisfied(self):
        for gate in ("requirement-confirmed", "plan-approved", "orchestration-ready"):
            exit_code = cli_main([
                "record", gate,
                "--repository", str(self.repo_path),
                "--evidence", ".planning/specs/x.md",
                "--actor", "user",
            ])
            self.assertEqual(0, exit_code)
        gates = self._state_gates()
        for gate in ("requirement_confirmed", "plan_approved", "orchestration_ready"):
            self.assertEqual("satisfied", gates[gate])

    def test_record_is_scoped_to_workflow_id(self):
        cli_main(["record", "requirement-confirmed", "--repository", str(self.repo_path),
                  "--evidence", "spec.md", "--actor", "user", "--workflow-id", "other"])
        self.assertEqual("unmet", self._state_gates()["requirement_confirmed"])
        self.assertEqual("satisfied", self._state_gates("other")["requirement_confirmed"])

    def test_record_is_idempotent_for_same_evidence(self):
        args = ["record", "plan-approved", "--repository", str(self.repo_path),
                "--evidence", "plan.md", "--actor", "user"]
        self.assertEqual(0, cli_main(args))
        self.assertEqual(0, cli_main(args))
        events = WorkflowEventStore(self.repo_path / ".agent-workflow/runtime/events.jsonl").read_all()
        self.assertEqual(1, sum(1 for event in events if event.event_type == "approval.recorded"))

    def _fake_beads(self, children, epic_status="open"):
        def run(repo, argv):
            if argv[:2] == ["list", "--parent"]:
                return [{"id": f"epic.{i}", "status": status} for i, status in enumerate(children)]
            if argv[0] == "show":
                return [{"id": "epic", "status": epic_status}]
            raise AssertionError(argv)
        return run

    def _record_orchestration(self, epic="epic"):
        args = ["record", "orchestration-ready", "--repository", str(self.repo_path),
                "--evidence", "beads", "--actor", "user"]
        self.assertEqual(0, cli_main(args + (["--epic", epic] if epic else [])))

    def test_implementation_complete_derives_from_closed_epic_children(self):
        from unittest.mock import patch

        self._record_orchestration()
        with patch("workflow_core.lifecycle_cli._beads_json", self._fake_beads(["closed", "open"])):
            self.assertEqual("unmet", self._state_gates()["implementation_complete"])
        with patch("workflow_core.lifecycle_cli._beads_json", self._fake_beads(["closed", "closed"])):
            gates = self._state_gates()
        self.assertEqual("satisfied", gates["implementation_complete"])
        self.assertEqual("unmet", gates["shipped"])

    def test_implementation_complete_unmet_without_epic_children_or_beads(self):
        from unittest.mock import patch

        self._record_orchestration(epic=None)
        with patch("workflow_core.lifecycle_cli._beads_json", self._fake_beads(["closed"])):
            self.assertEqual("unmet", self._state_gates()["implementation_complete"])
        self._record_orchestration()
        with patch("workflow_core.lifecycle_cli._beads_json", self._fake_beads([])):
            self.assertEqual("unmet", self._state_gates()["implementation_complete"])
        with patch("workflow_core.lifecycle_cli._beads_json", lambda repo, argv: None):
            self.assertEqual("unmet", self._state_gates()["implementation_complete"])

    def test_verification_passed_is_recordable_and_shipped_follows_closed_epic(self):
        from unittest.mock import patch

        self._record_orchestration()
        self.assertEqual(0, cli_main(["record", "verification-passed", "--repository", str(self.repo_path),
                                      "--evidence", "547 tests OK", "--actor", "user"]))
        with patch("workflow_core.lifecycle_cli._beads_json", self._fake_beads(["closed"], epic_status="closed")):
            gates = self._state_gates()
        self.assertEqual("satisfied", gates["verification_passed"])
        self.assertEqual("satisfied", gates["shipped"])

    def test_record_rejects_epic_on_other_gates(self):
        self.assertEqual(2, cli_main(["record", "plan-approved", "--repository", str(self.repo_path),
                                      "--evidence", "plan.md", "--actor", "user", "--epic", "epic"]))

    def test_record_rejects_unknown_gate_and_missing_evidence(self):
        self.assertEqual(2, cli_main(["record", "shipped", "--repository", str(self.repo_path),
                                      "--evidence", "x", "--actor", "user"]))
        self.assertEqual(2, cli_main(["record", "plan-approved", "--repository", str(self.repo_path),
                                      "--actor", "user"]))


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

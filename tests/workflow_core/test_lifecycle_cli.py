"""Unit tests for gin state and gin unblock CLI subcommands."""

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock

from workflow_core.cli import main as cli_main
from workflow_core.events import EventPersistenceError, WorkflowEvent, WorkflowEventStore
from workflow_core.lifecycle_cli import main as lifecycle_main
from tests.workflow_core.orchestrator_fakes import fake_orchestrator, on_path
from tests.workflow_core.team_fixtures import calls, fake_cli, path_with
from tests.workflow_core.test_workspace import make_workspace


class TestLifecycleCLI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.test_dir)
        # Create minimal setup config so EffectiveConfig resolves
        self.workflow_dir = self.repo_path / ".agent-workflow"
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        (self.workflow_dir / "config.yaml").write_text("schema_version: '2.3'\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_version_flag_returns_version(self):
        exit_code = cli_main(["--version"])
        self.assertEqual(0, exit_code)

    def test_unknown_command_returns_error(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = cli_main(["unknown"])
        self.assertEqual(2, exit_code)
        self.assertIn(",task,", stderr.getvalue())

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

    def test_state_json_catalog_for_claude_repository_without_models(self):
        (self.workflow_dir / "config.yaml").write_text("schema_version: '2.8'\nharness: claude\n")
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_out:
            exit_code = lifecycle_main([
                "state",
                "--repository", str(self.repo_path),
                "--format", "json",
            ])
            data = json.loads(fake_out.getvalue())
        self.assertEqual(0, exit_code)
        self.assertIn("catalog", data)
        self.assertEqual("claude", data["catalog"]["harness"])
        self.assertEqual(["haiku", "sonnet", "opus"], data["catalog"]["models"])

    def test_state_json_names_the_epic_recorded_at_orchestration_ready(self):
        def epic(workflow_id: str):
            with mock.patch("sys.stdout", new=io.StringIO()) as out:
                lifecycle_main(["state", "--workflow-id", workflow_id, "--repository", str(self.repo_path),
                                "--format", "json"])
            return json.loads(out.getvalue())["epic"]

        self.assertIsNone(epic("wf"))
        with mock.patch("sys.stdout", new=io.StringIO()), mock.patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(0, cli_main(["record", "orchestration-ready", "--workflow-id", "wf", "--epic", "ep-9",
                                          "--evidence", "beads", "--actor", "user",
                                          "--repository", str(self.repo_path)]))
        self.assertEqual("ep-9", epic("wf"))
        self.assertIsNone(epic("other"))

    def test_state_json_catalog_is_null_without_harness(self):
        (self.workflow_dir / "config.yaml").write_text("schema_version: '2.8'\n")
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_out:
            exit_code = lifecycle_main([
                "state",
                "--repository", str(self.repo_path),
                "--format", "json",
            ])
            data = json.loads(fake_out.getvalue())
        self.assertEqual(0, exit_code)
        self.assertIsNone(data["catalog"])

    def test_state_reports_extensions_orchestrator(self):
        import io
        from unittest.mock import patch

        expected_keys = {"available", "version", "contract", "capabilities", "reason"}
        # Unavailable
        with tempfile.TemporaryDirectory() as empty_dir:
            with on_path(empty_dir):
                import os
                os.environ["PATH"] = empty_dir
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    lifecycle_main([
                        "state",
                        "--repository", str(self.repo_path),
                        "--format", "json",
                    ])
                data = json.loads(fake_out.getvalue())
                self.assertIn("extensions", data)
                self.assertIn("orchestrator", data["extensions"])
                orch = data["extensions"]["orchestrator"]
                self.assertEqual(expected_keys, set(orch.keys()))
                self.assertFalse(orch["available"])
                self.assertEqual("orchestrator_missing", orch["reason"])

        # Available
        with tempfile.TemporaryDirectory() as fake_dir:
            fake_orchestrator(fake_dir, contract=2, capabilities=["health", "doctor"])
            with on_path(fake_dir):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    lifecycle_main([
                        "state",
                        "--repository", str(self.repo_path),
                        "--format", "json",
                    ])
                data = json.loads(fake_out.getvalue())
                self.assertIn("extensions", data)
                orch = data["extensions"]["orchestrator"]
                self.assertEqual(expected_keys, set(orch.keys()))
                self.assertTrue(orch["available"])
                self.assertIsNone(orch["reason"])
                self.assertEqual(2, orch["contract"])
                self.assertEqual(["health", "doctor"], orch["capabilities"])

    def test_state_warns_in_multi_mode_without_orchestrator(self):
        import io
        from unittest.mock import patch

        (self.workflow_dir / "config.yaml").write_text("schema_version: '2.8'\nprovider_mode: multi\n")
        with tempfile.TemporaryDirectory() as empty_dir:
            with on_path(empty_dir):
                import os
                os.environ["PATH"] = empty_dir
                # JSON format has warnings
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    lifecycle_main([
                        "state",
                        "--repository", str(self.repo_path),
                        "--format", "json",
                    ])
                data = json.loads(fake_out.getvalue())
                self.assertIn("warnings", data)
                self.assertTrue(
                    any("orchestrator_missing" in w and "./install.sh --plugin gin-orchestrator" in w for w in data["warnings"]),
                    data["warnings"],
                )

                # Text format prints Warning: ...
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    lifecycle_main([
                        "state",
                        "--repository", str(self.repo_path),
                        "--format", "text",
                    ])
                text = fake_out.getvalue()
                self.assertIn("Warning: orchestrator_missing; install with ./install.sh --plugin gin-orchestrator", text)


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

    def test_quick_check_in_a_child_uses_its_checks(self):
        root = make_workspace(Path(tempfile.mkdtemp()).resolve())
        self.addCleanup(shutil.rmtree, root.parent, True)
        config = root / ".agent-workflow/config.yaml"
        config.write_text(config.read_text(encoding="utf-8").replace(
            'verify: {checks: {test: "echo api-test"}}', 'verify: {checks: {lint: "touch child-lint", test: "true"}}')
            + "verify: {checks: {lint: touch parent-lint}}\n", encoding="utf-8")
        before = os.getcwd()
        self.addCleanup(os.chdir, before)
        os.chdir(root / "services/api")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli_main(["quick-check", "--changed-files", "1", "--modules", "1", "--format", "json"])
        self.assertEqual(0, code)
        self.assertEqual({"lint": "touch child-lint", "test": "true"}, json.loads(out.getvalue())["verify_commands"])

    def test_quick_check_with_an_explicit_child_uses_the_workspace_rigor(self):
        root = make_workspace(Path(tempfile.mkdtemp()).resolve())
        self.addCleanup(shutil.rmtree, root.parent, True)
        config = root / ".agent-workflow/config.yaml"
        config.write_text(config.read_text(encoding="utf-8").replace(
            'verify: {checks: {test: "echo api-test"}}',
            'verify: {checks: {lint: "l", test: "t", build: "b"}}') + "project: {rigor: easy}\n", encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli_main(["quick-check", "--repository", str(root / "services/api"),
                             "--changed-files", "1", "--modules", "1", "--format", "json"])
        payload = json.loads(out.getvalue())
        self.assertEqual((0, "easy", {"lint": "l", "test": "t"}), (code, payload["rigor"], payload["verify_commands"]))

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

    def test_state_lists_review_waivers_of_the_workflow(self):
        store = WorkflowEventStore(self.workflow_dir / "runtime/events.jsonl")
        for workflow in ("default-workflow", "other"):
            store.append(WorkflowEvent.create(event_type="review.waived", workflow_id=workflow, task_id=f"{workflow}.1",
                                              actor="u", payload={"reason": "spike"}, idempotency_key=workflow))
        self.assertEqual([{"task_id": "default-workflow.1", "reason": "spike", "actor": "u"}],
                         self._state_json()["review_waivers"])

    def test_invalid_config_exits_2_without_traceback(self):
        (self.workflow_dir / "config.yaml").write_text("schema_version: '2.3'\nverify: nope\n")

        def run(*argv):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = lifecycle_main([*argv, "--repository", str(self.repo_path)])
            return code, out.getvalue(), err.getvalue()

        for fmt in (["--format", "json"], ["--format=json"]):
            code, out, err = run("state", *fmt)
            self.assertEqual(2, code, err)
            self.assertEqual("error", json.loads(out)["status"])
            self.assertTrue(json.loads(out)["message"])
        for argv in (["state"], ["record", "requirement-confirmed", "--evidence", "json", "--actor", "me"]):
            code, out, err = run(*argv)
            self.assertEqual(2, code, err)
            self.assertEqual("", out)
            self.assertIn("error:", err)
            self.assertNotIn("Traceback", err)

    def test_unblock_safety_gate_without_followup_fails(self):
        exit_code = lifecycle_main([
            "unblock",
            "--gate", "review_approved",
            "--reason", "skipping review for doc change",
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

    def _record_requirement(self, evidence):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
            code = cli_main(["record", "requirement-confirmed", "--repository", str(self.repo_path),
                             "--evidence", evidence, "--actor", "user"])
        return code, stderr.getvalue()

    def test_us5_requirement_confirmed_refuses_spec_without_criteria(self):
        (self.repo_path / "spec.md").write_text("### US-7: a\n\ntext\n")
        code, err = self._record_requirement("spec.md")
        self.assertEqual(1, code)
        self.assertIn("US-7", err)
        self.assertEqual("unmet", self._state_gates()["requirement_confirmed"])

    def test_us5_requirement_confirmed_records_linted_spec(self):
        (self.repo_path / "spec.md").write_text("### US-1: a\n\nAcceptance criteria:\n- x\n")
        self.assertEqual(0, self._record_requirement("spec.md")[0])
        self.assertEqual("satisfied", self._state_gates()["requirement_confirmed"])

    def test_us5_non_markdown_evidence_is_not_linted(self):
        self.assertEqual(0, self._record_requirement("chat 2026-10-31")[0])

    def test_record_requirement_refuses_an_epic_kind_mismatch(self):
        """epic-kinds R4, US-3: the spec's `Kind:` must match the epic bead's `kind:` label."""
        from workflow_core.configuration import resolve_effective_config

        (self.workflow_dir / "config.yaml").write_text("schema_version: '2.7'\nproviders:\n  task_tracking: beads\n")
        resolve_effective_config(self.repo_path)
        bin_dir = self.repo_path / "fakebin"
        fake_cli(bin_dir, "bd", [{"argv": ["show", "ep-1"], "stdout": [{"id": "ep-1", "labels": ["kind:technical"]}]}])
        spec = self.repo_path / "spec.md"
        args = ["record", "requirement-confirmed", "--repository", str(self.repo_path), "--evidence", "spec.md",
                "--actor", "user", "--workflow-id", "ep-1"]

        def record() -> tuple[int, str]:
            stderr = io.StringIO()
            with mock.patch.dict(os.environ, path_with(bin_dir)), contextlib.redirect_stderr(stderr), \
                    contextlib.redirect_stdout(io.StringIO()):
                return cli_main(args), stderr.getvalue()

        spec.write_text("# Login\n\nKind: capability\n\n### US-1: a\n\nAcceptance criteria:\n- x\n")
        code, err = record()
        self.assertEqual(1, code)
        self.assertIn("kind mismatch: epic ep-1 is kind:technical, spec spec.md says Kind: capability", err)
        events = WorkflowEventStore(self.workflow_dir / "runtime/events.jsonl").read_all()
        self.assertFalse([event for event in events if event.event_type == "requirement.confirmed"])
        spec.write_text("# Login\n\nKind: technical\n")
        code, err = record()
        self.assertEqual(0, code, err)
        # A tracker that cannot answer refuses the record instead of trusting the spec's Kind:.
        fake_cli(bin_dir, "bd", [{"argv": ["show"], "exit": 1, "stderr": "Error: failed to connect to dolt server\n"}])
        args[-1] = "ep-2"
        code, err = record()
        self.assertEqual(1, code)
        self.assertIn("cannot read the kind of epic ep-2: bd exited 1: Error: failed to connect to dolt server", err)

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

    def test_record_reports_an_unwritten_gate(self):
        args = ["record", "plan-approved", "--repository", str(self.repo_path),
                "--evidence", "plan.md", "--actor", "user"]
        for error in (EventPersistenceError("cannot lock events"), RuntimeError("atomic write failed"),
                      PermissionError(13, "denied")):
            with self.subTest(error=type(error).__name__), \
                    mock.patch("workflow_core.lifecycle_cli.WorkflowEventStore.transaction", side_effect=error), \
                    contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(1, cli_main(args))
            self.assertIn("error: plan-approved not recorded for default-workflow: ", stderr.getvalue())
        self.assertEqual("unmet", self._state_gates()["plan_approved"])

    def _fake_beads(self, children, epic_status="open"):
        def run(repo, argv):
            if argv[:2] == ["list", "--parent"]:
                return [{"id": f"epic.{i}", "status": status} for i, status in enumerate(children)], None
            if argv[0] == "show":
                return [{"id": "epic", "status": epic_status}], None
            raise AssertionError(argv)
        return run

    def _git(self, *args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd or self.repo_path, check=True, capture_output=True,
                              text=True).stdout.strip()

    def _git_repo(self):
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "t@example.com")
        self._git("config", "user.name", "T")
        self._git("commit", "-q", "--allow-empty", "-m", "base")

    def test_verification_passed_gate_is_removed(self):
        self._git_repo()
        self.assertNotIn("verification_passed", self._state_gates())
        for argv in (["record", "verification-passed", "--evidence", "tests OK", "--actor", "user"],):
            self.assertEqual(2, cli_main([argv[0], argv[1], "--repository", str(self.repo_path), *argv[2:]]))
        events = WorkflowEventStore(self.workflow_dir / "runtime/events.jsonl").read_all()
        self.assertEqual([], [e for e in events if e.event_type == "verification.passed"])

    def test_record_verification_passed_points_at_the_hooks(self):
        import io
        from unittest.mock import patch

        with patch("sys.stderr", new=io.StringIO()) as err:
            code = lifecycle_main(["record", "verification-passed", "--repository", str(self.repo_path),
                                   "--evidence", "x", "--actor", "user"])
        self.assertEqual(2, code)
        self.assertIn("gin hooks install", err.getvalue())

    def test_unblock_verification_passed_is_rejected(self):
        import io
        from unittest.mock import patch

        with patch("sys.stderr", new=io.StringIO()) as err:
            code = lifecycle_main(["unblock", "--gate", "verification_passed", "--reason", "x", "--actor", "op",
                                   "--follow-up", "t-1", "--repository", str(self.repo_path)])
        self.assertEqual(2, code)
        self.assertIn("gin hooks install", err.getvalue())

    def test_old_verification_events_are_ignored(self):
        self._git_repo()
        WorkflowEventStore(self.workflow_dir / "runtime/events.jsonl").append(WorkflowEvent.create(
            event_type="verification.passed", workflow_id="default-workflow", actor="user",
            payload={"evidence": "old", "head": "abc", "branch": "main"}, idempotency_key="old"))
        self.assertEqual({"requirement_confirmed", "plan_approved", "orchestration_ready",
                          "implementation_complete", "shipped"}, set(self._state_gates()))

    def _record_orchestration(self, epic="epic"):
        args = ["record", "orchestration-ready", "--repository", str(self.repo_path),
                "--evidence", "beads", "--actor", "user"]
        self.assertEqual(0, cli_main(args + (["--epic", epic] if epic else [])))

    def _record_with_fake_bd(self, rule, *extra):
        bin_dir = self.repo_path / "fakebin"
        fake_cli(bin_dir, "bd", rule if isinstance(rule, list) else [rule])
        out = io.StringIO()
        with mock.patch.dict(os.environ, path_with(bin_dir)), contextlib.redirect_stdout(out), \
                mock.patch("workflow_core.lifecycle_cli.tasks_backend", return_value="beads"):
            code = cli_main(["record", "orchestration-ready", "--repository", str(self.repo_path),
                             "--evidence", "beads", "--actor", "user", "--format", "json", *extra])
        return code, json.loads(out.getvalue()), calls(bin_dir)

    def _epic(self, assignee):
        return {"argv": ["show"], "stdout": [{"id": "ep-1", "assignee": assignee}]}

    def test_record_orchestration_ready_claims_an_unassigned_epic(self):
        code, result, made = self._record_with_fake_bd([self._epic(""), {"argv": ["update"]}], "--epic", "ep-1")
        self.assertEqual((0, "recorded"), (code, result["status"]))
        self.assertNotIn("warning", result)
        self.assertEqual([["bd", "show", "ep-1", "--json"], ["bd", "update", "ep-1", "--claim"]], made)

    def test_record_orchestration_ready_keeps_an_existing_epic_assignee(self):
        code, result, made = self._record_with_fake_bd([self._epic("an@x.io"), {"argv": ["update"]}],
                                                       "--epic", "ep-1")
        self.assertEqual((0, "recorded"), (code, result["status"]))
        self.assertNotIn("warning", result)
        self.assertEqual(["bd", "update", "ep-1", "--status", "in_progress"], made[-1])

    def test_record_orchestration_ready_keeps_the_gate_when_bd_fails(self):
        code, result, _ = self._record_with_fake_bd([self._epic(""), {"argv": ["update"], "exit": 1, "stderr": "boom"}],
                                                    "--epic", "ep-1")
        self.assertEqual((0, "recorded"), (code, result["status"]))
        self.assertIn("ep-1", result["warning"])
        self.assertIn("boom", result["warning"])

    def test_record_orchestration_ready_warns_when_the_effective_config_is_broken(self):
        generated = self.workflow_dir / "generated"
        generated.mkdir()
        (generated / "effective-config.yaml").write_text("a: [unclosed\n")
        bin_dir = self.repo_path / "fakebin"
        fake_cli(bin_dir, "bd", [{"argv": ["update"]}])
        out = io.StringIO()
        with mock.patch.dict(os.environ, path_with(bin_dir)), contextlib.redirect_stdout(out):
            code = cli_main(["record", "orchestration-ready", "--repository", str(self.repo_path),
                             "--evidence", "beads", "--actor", "user", "--format", "json", "--epic", "ep-1"])
        result = json.loads(out.getvalue())
        self.assertEqual((0, "recorded"), (code, result["status"]))
        self.assertIn("ep-1", result["warning"])
        self.assertEqual([], calls(bin_dir))

    def test_record_orchestration_ready_without_epic_leaves_beads_alone(self):
        code, result, made = self._record_with_fake_bd({"argv": ["update"]})
        self.assertEqual((0, "recorded"), (code, result["status"]))
        self.assertEqual([], made)

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
        with patch("workflow_core.lifecycle_cli._beads_json", lambda repo, argv: (None, "bd not found")):
            self.assertEqual("unknown", self._state_gates()["implementation_complete"])

    def test_shipped_follows_closed_epic(self):
        from unittest.mock import patch

        self._git_repo()
        self._record_orchestration()
        with patch("workflow_core.lifecycle_cli._beads_json", self._fake_beads(["closed"], epic_status="closed")):
            gates = self._state_gates()
        self.assertEqual("satisfied", gates["shipped"])

    def test_standalone_bead_is_its_own_epic_and_records_shipped_after_merge(self):
        from unittest.mock import patch

        self._record_orchestration(epic="bug-1")
        with patch("workflow_core.lifecycle_cli._beads_json", self._fake_beads([], epic_status="open")):
            self.assertEqual("unmet", self._state_gates()["implementation_complete"])
        closed = self._fake_beads([], epic_status="closed")
        with patch("workflow_core.lifecycle_cli._beads_json", closed):
            gates = self._state_gates()
            self.assertEqual(("satisfied", "unmet"), (gates["implementation_complete"], gates["shipped"]))
            self.assertEqual(0, cli_main(["record", "shipped", "--repository", str(self.repo_path),
                                          "--evidence", "merged abc123 into master", "--actor", "user"]))
            self.assertEqual("satisfied", self._state_gates()["shipped"])

    def _state(self):
        import io
        from unittest.mock import patch

        with patch("sys.stdout", new=io.StringIO()) as out:
            lifecycle_main(["state", "--repository", str(self.repo_path), "--format", "json"])
        return json.loads(out.getvalue())

    def test_standalone_bead_reaches_ship_without_discuss_or_plan_gates(self):
        from unittest.mock import patch

        self._git_repo()
        self._record_orchestration(epic="bug-1")
        with patch("workflow_core.lifecycle_cli._beads_json", self._fake_beads([], epic_status="closed")):
            state = self._state()
        self.assertEqual(("satisfied", "satisfied"),
                         (state["gates"]["requirement_confirmed"], state["gates"]["plan_approved"]))
        self.assertEqual("ship", state["stage"])

    def test_planned_epic_still_needs_discuss_and_plan_gates(self):
        from unittest.mock import patch

        self._record_orchestration()
        with patch("workflow_core.lifecycle_cli._beads_json", self._fake_beads(["closed"])):
            state = self._state()
        self.assertEqual(("unmet", "unmet"),
                         (state["gates"]["requirement_confirmed"], state["gates"]["plan_approved"]))
        self.assertEqual("discuss", state["stage"])

    def test_record_shipped_is_refused_for_epics_with_children_or_without_epic(self):
        from unittest.mock import patch

        shipped = ["record", "shipped", "--repository", str(self.repo_path), "--evidence", "merge", "--actor", "user"]
        self.assertEqual(2, cli_main(shipped))
        self._record_orchestration()
        with patch("workflow_core.lifecycle_cli._beads_json", self._fake_beads(["closed"], epic_status="closed")):
            self.assertEqual(2, cli_main(shipped))

    def test_process_gates_are_refused_for_a_shipped_workflow(self):
        from unittest.mock import patch

        self._record_orchestration(epic="bug-1")
        with patch("workflow_core.lifecycle_cli._beads_json", self._fake_beads([], epic_status="closed")):
            self.assertEqual(0, cli_main(["record", "shipped", "--repository", str(self.repo_path),
                                          "--evidence", "merged abc123 into master", "--actor", "user"]))
            self.assertEqual(2, cli_main(["record", "requirement-confirmed", "--repository", str(self.repo_path),
                                          "--evidence", "spec.md", "--actor", "user"]))
            self.assertEqual(0, cli_main(["record", "requirement-confirmed", "--repository", str(self.repo_path),
                                          "--evidence", "spec.md", "--actor", "user", "--workflow-id", "fresh"]))

    def test_record_rejects_epic_on_other_gates(self):
        self.assertEqual(2, cli_main(["record", "plan-approved", "--repository", str(self.repo_path),
                                      "--evidence", "plan.md", "--actor", "user", "--epic", "epic"]))

    def test_record_rejects_unknown_gate_and_missing_evidence(self):
        self.assertEqual(2, cli_main(["record", "no-such-gate", "--repository", str(self.repo_path),
                                      "--evidence", "x", "--actor", "user"]))
        self.assertEqual(2, cli_main(["record", "plan-approved", "--repository", str(self.repo_path),
                                      "--actor", "user"]))

    def _state_payload(self, workflow_id="default-workflow"):
        with mock.patch("sys.stdout", new=io.StringIO()) as out:
            code = lifecycle_main(["state", "--repository", str(self.repo_path), "--format", "json",
                                   "--workflow-id", workflow_id])
        return json.loads(out.getvalue()), code

    def test_us1_tracker_failure_is_unknown_and_holds(self):
        self._record_orchestration()
        with mock.patch("workflow_core.lifecycle_cli._beads_json", lambda repo, argv: (None, "bd not found")):
            payload, code = self._state_payload()
        self.assertEqual(1, code)
        self.assertEqual(("unknown", "unknown"),
                         (payload["gates"]["implementation_complete"], payload["gates"]["shipped"]))
        self.assertEqual(("progress", "hold"), (payload["stage"], payload["decision"]))
        self.assertIn("tracker unavailable: bd not found", payload["warnings"])
        self.assertIn("tracker unavailable: bd not found", payload["remedies"])

    def test_us1_unrecorded_process_gates_are_unknown_when_standalone_cannot_be_checked(self):
        self._record_orchestration()
        with mock.patch("workflow_core.lifecycle_cli._beads_json", lambda repo, argv: (None, "bd not found")):
            gates = self._state_gates()
        self.assertEqual(("unknown", "unknown", "satisfied"),
                         (gates["requirement_confirmed"], gates["plan_approved"], gates["orchestration_ready"]))

    def test_us1_record_shipped_names_the_tracker_failure(self):
        self._record_orchestration()
        with mock.patch("workflow_core.lifecycle_cli._beads_json", lambda repo, argv: (None, "bd not found")), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(2, cli_main(["record", "shipped", "--repository", str(self.repo_path),
                                          "--evidence", "merge", "--actor", "user"]))
        self.assertIn("tracker unavailable: bd not found", err.getvalue())
        self.assertNotIn("standalone", err.getvalue())

    def test_us2_corrupt_event_log_is_reported(self):
        path = self.workflow_dir / "runtime/events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json\n", encoding="utf-8")
        payload, code = self._state_payload()
        self.assertEqual(1, code)
        self.assertEqual({"unknown"}, set(payload["gates"].values()))
        self.assertEqual("hold", payload["decision"])
        self.assertTrue(any(warning.startswith("event log unreadable: ") and warning.endswith("; waivers not applied")
                            for warning in payload["warnings"]), payload["warnings"])

    def test_us3_concurrent_record_shipped_writes_one_event(self):
        self._record_orchestration()
        fake = self._fake_beads([], epic_status="closed")

        def slow(repo, argv):
            time.sleep(0.2)
            return fake(repo, argv)

        codes = []

        def record(evidence):
            codes.append(cli_main(["record", "shipped", "--repository", str(self.repo_path),
                                   "--evidence", evidence, "--actor", "user"]))

        with mock.patch("workflow_core.lifecycle_cli._beads_json", slow), contextlib.redirect_stdout(io.StringIO()):
            threads = [threading.Thread(target=record, args=(evidence,)) for evidence in ("merge-a", "merge-b")]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        self.assertEqual([0, 0], codes)
        events = WorkflowEventStore(self.workflow_dir / "runtime/events.jsonl").read_all()
        self.assertEqual(1, sum(event.event_type == "delivery.shipped" for event in events))

    def test_us5_state_reads_the_log_once_and_lists_children_once(self):
        self._record_orchestration()
        calls = []
        fake = self._fake_beads(["closed", "open"])

        def counting(repo, argv):
            calls.append(argv[0])
            return fake(repo, argv)

        original = WorkflowEventStore.read_all
        with mock.patch("workflow_core.lifecycle_cli._beads_json", counting), \
                mock.patch.object(WorkflowEventStore, "read_all", autospec=True, side_effect=original) as reads:
            self._state_payload()
        self.assertEqual(1, reads.call_count)
        self.assertEqual(1, calls.count("list"))

    def _us6_warnings(self, complete=True, knowledge_commit=False, git_error=None):
        self._git_repo()
        knowledge = self.repo_path / ".planning/knowledge"
        knowledge.mkdir(parents=True)
        (knowledge / "note.md").write_text("n\n")
        WorkflowEventStore(self.workflow_dir / "runtime/events.jsonl").append(WorkflowEvent.create(
            event_type="orchestration.ready", workflow_id="default-workflow", actor="user",
            payload={"epic": "epic"}, timestamp="2026-10-01T00:00:00Z", idempotency_key="us6"))
        if knowledge_commit:
            self._git("add", ".planning/knowledge")
            subprocess.run(["git", "commit", "-q", "-m", "knowledge"], cwd=self.repo_path, check=True,
                           env={**os.environ, "GIT_COMMITTER_DATE": "2026-10-02T00:00:00Z"})
        delivery = {"orchestration_ready": True, "implementation_complete": complete, "shipped": False}
        real_run = subprocess.run

        def run(argv, *args, **kwargs):
            if git_error and argv[:2] == ["git", "log"]:
                raise git_error
            return real_run(argv, *args, **kwargs)

        with mock.patch("workflow_core.lifecycle_cli._delivery_state", return_value=(delivery, False, None)), \
                mock.patch("workflow_core.lifecycle_cli.subprocess.run", side_effect=run), \
                mock.patch("sys.stdout", new=io.StringIO()) as out:
            lifecycle_main(["state", "--repository", str(self.repo_path), "--format", "json"])
        return json.loads(out.getvalue())["warnings"]

    def test_us6_state_warns_when_knowledge_unchanged_since_orchestration(self):
        warnings = self._us6_warnings()
        self.assertTrue(any("reconcile knowledge" in w for w in warnings), warnings)

    def test_us6_no_warning_after_knowledge_commit(self):
        warnings = self._us6_warnings(knowledge_commit=True)
        self.assertFalse(any("reconcile knowledge" in w for w in warnings), warnings)

    def test_us6_missing_git_does_not_break_state(self):
        warnings = self._us6_warnings(git_error=FileNotFoundError("git"))
        self.assertFalse(any("reconcile knowledge" in w for w in warnings), warnings)

    def test_us6_git_timeout_does_not_break_state(self):
        warnings = self._us6_warnings(git_error=subprocess.TimeoutExpired("git", 10))
        self.assertFalse(any("reconcile knowledge" in w for w in warnings), warnings)

    def test_us6_no_warning_before_implementation_complete(self):
        warnings = self._us6_warnings(complete=False)
        self.assertFalse(any("reconcile knowledge" in w for w in warnings), warnings)

    def test_orchestrated_epic_tracks_closed_prep_open_satisfied(self):
        from unittest.mock import patch
        self._record_orchestration("ep-1")
        children = [
            {"id": "ep-1.1", "status": "closed", "labels": ["track:1"]},
            {"id": "ep-1.2", "status": "open", "labels": ["prep", "prep:capture"]},
        ]
        def fake_beads(repo, argv):
            if argv[:2] == ["list", "--parent"]:
                return children, None
            if argv[0] == "show":
                return [{"id": "ep-1", "status": "open"}], None
            raise AssertionError(argv)

        with patch("workflow_core.lifecycle_cli._beads_json", fake_beads):
            self.assertEqual("satisfied", self._state_gates()["implementation_complete"])
            # Reopening the prep task still leaves implementation_complete satisfied:
            children[1]["status"] = "in_progress"
            self.assertEqual("satisfied", self._state_gates()["implementation_complete"])

    def test_team_mode_unorchestrated_epic_with_closed_prep_tasks_not_satisfied(self):
        from unittest.mock import patch, Mock
        children = [
            {"id": "ep-shared.1", "status": "closed", "labels": ["prep", "prep:capture"]},
        ]
        def fake_beads(repo, argv):
            if argv[:2] == ["list", "--parent"]:
                return children, None
            if argv[0] == "show":
                return [{"id": "ep-shared", "status": "open"}], None
            raise AssertionError(argv)

        with patch("workflow_core.lifecycle_cli.load_team", return_value=Mock()), \
             patch("workflow_core.lifecycle_cli.team_summary", return_value={}), \
             patch("workflow_core.lifecycle_cli.tasks_backend", return_value="beads"), \
             patch("workflow_core.team_beads.shared_gates", return_value=("ep-shared", set(), None)), \
             patch("workflow_core.lifecycle_cli._beads_json", fake_beads):
            self.assertEqual("unmet", self._state_gates()["implementation_complete"])

    def test_record_shipped_standalone_with_only_prep_children_not_refused(self):
        from unittest.mock import patch
        self._record_orchestration(epic="standalone-1")
        prep_children = [{"id": "p.1", "status": "closed", "labels": ["prep", "prep:mockup"]}]
        def fake_beads(repo, argv):
            if argv[:2] == ["list", "--parent"]:
                return prep_children, None
            if argv[0] == "show":
                return [{"id": "standalone-1", "status": "closed"}], None
            raise AssertionError(argv)
        with patch("workflow_core.lifecycle_cli._beads_json", fake_beads):
            code = cli_main(["record", "shipped", "--repository", str(self.repo_path),
                             "--evidence", "merged into main", "--actor", "user"])
            self.assertEqual(0, code)

    def test_record_orchestration_ready_refuses_prep_task(self):
        from unittest.mock import patch
        prep_bead = [{"id": "prep-1", "status": "open", "labels": ["prep", "prep:spike"]}]
        with patch("workflow_core.lifecycle_cli._beads_json", return_value=(prep_bead, None)):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = cli_main(["record", "orchestration-ready", "--repository", str(self.repo_path),
                                 "--evidence", "beads", "--actor", "user", "--format", "json",
                                 "--epic", "prep-1"])
            self.assertEqual(1, code)
            result = json.loads(out.getvalue())
            self.assertEqual("rejected", result["status"])
            self.assertEqual("orchestration-ready refused: prep-1 is a prep task, not implementation work",
                             result["message"])

    def test_record_orchestration_ready_with_tracker_failing_records_as_today(self):
        code, result, _ = self._record_with_fake_bd(
            [{"argv": ["show"], "exit": 1, "stderr": "bd unavailable"}],
            "--epic", "ep-1")
        self.assertEqual((0, "recorded"), (code, result["status"]))

    def test_lifecycle_cli_uses_tracks_of(self):
        from unittest.mock import patch
        from workflow_core import prep
        self._record_orchestration("ep-1")
        with patch("workflow_core.lifecycle_cli.tracks_of", wraps=prep.tracks_of) as mock_tracks_of:
            with patch("workflow_core.lifecycle_cli._beads_json", self._fake_beads(["closed"])):
                self._state_gates()
                mock_tracks_of.assert_called()


if __name__ == "__main__":
    unittest.main()

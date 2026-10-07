"""Unit tests for gin-workflow state and gin-workflow unblock CLI subcommands."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
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

    def _git(self, *args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd or self.repo_path, check=True, capture_output=True,
                              text=True).stdout.strip()

    def _git_repo(self):
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "t@example.com")
        self._git("config", "user.name", "T")
        self._git("commit", "-q", "--allow-empty", "-m", "base")

    def _verify(self, repo=None):
        return cli_main(["record", "verification-passed", "--repository", str(repo or self.repo_path),
                         "--evidence", "tests OK", "--actor", "user"])

    def _commit_file(self, relative, cwd=None):
        root = Path(cwd or self.repo_path)
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(relative, encoding="utf-8")
        self._git("add", relative, cwd=root)
        self._git("commit", "-q", "-m", relative, cwd=root)

    def _verification_events(self):
        return [event for event in WorkflowEventStore(self.workflow_dir / "runtime/events.jsonl").read_all()
                if event.event_type == "verification.passed"]

    def test_new_commit_invalidates_verification(self):
        self._git_repo()
        self.assertEqual(0, self._verify())
        self.assertEqual("satisfied", self._state_gates()["verification_passed"])
        self._commit_file("src/code.py")
        self.assertEqual("unmet", self._state_gates()["verification_passed"])
        self.assertEqual(0, self._verify())
        self.assertEqual(self._git("rev-parse", "HEAD"), self._verification_events()[-1].payload["head"])
        self.assertEqual("main", self._verification_events()[-1].payload["branch"])
        self.assertEqual("satisfied", self._state_gates()["verification_passed"])

    def test_spec_only_commit_keeps_verification(self):
        self._git_repo()
        self.assertEqual(0, self._verify())
        self._commit_file(".planning/specs/x.md")
        self._commit_file("docs/changes/archive/c/spec-delta.md")
        self.assertEqual("satisfied", self._state_gates()["verification_passed"])
        self._commit_file("src/a.py")
        self.assertEqual("unmet", self._state_gates()["verification_passed"])

    def test_reverted_code_commit_still_invalidates(self):
        self._git_repo()
        self.assertEqual(0, self._verify())
        self._commit_file("src/a.py")
        self._git("revert", "--no-edit", "HEAD")
        self._commit_file(".planning/specs/x.md")
        self.assertEqual("unmet", self._state_gates()["verification_passed"])

    def test_merge_bringing_code_invalidates(self):
        self._git_repo()
        self._git("checkout", "-q", "-b", "side")
        self._commit_file("src/side.py")
        self._git("checkout", "-q", "main")
        self.assertEqual(0, self._verify())
        self._git("merge", "-q", "--no-ff", "--no-edit", "side")
        self.assertEqual("unmet", self._state_gates()["verification_passed"])

    def test_failing_git_history_is_unmet(self):
        from unittest.mock import patch

        self._git_repo()
        self.assertEqual(0, self._verify())
        self._commit_file(".planning/specs/x.md")
        real = subprocess.run

        def failing_log(argv, *args, **kwargs):
            if argv[:2] == ["git", "log"]:
                return subprocess.CompletedProcess(argv, 128, "", "fatal: bad object")
            return real(argv, *args, **kwargs)

        with patch("workflow_core.lifecycle_cli.subprocess.run", side_effect=failing_log):
            self.assertEqual("unmet", self._state_gates()["verification_passed"])

    def test_reverifying_an_earlier_commit_records_again(self):
        self._git_repo()
        first = self._git("rev-parse", "HEAD")
        self.assertEqual(0, self._verify())
        self._commit_file("src/a.py")
        self.assertEqual(0, self._verify())
        self._git("reset", "-q", "--hard", first)
        self.assertEqual(0, self._verify())
        self.assertEqual(first, self._verification_events()[-1].payload["head"])
        self.assertEqual(3, len(self._verification_events()))
        self.assertEqual("satisfied", self._state_gates()["verification_passed"])
        self.assertEqual(0, self._verify())
        self.assertEqual(3, len(self._verification_events()))

    def test_event_without_head_is_unmet(self):
        self._git_repo()
        WorkflowEventStore(self.workflow_dir / "runtime/events.jsonl").append(WorkflowEvent.create(
            event_type="verification.passed", workflow_id="default-workflow", actor="user",
            payload={"evidence": "old"}, idempotency_key="old"))
        self.assertEqual("unmet", self._state_gates()["verification_passed"])

    def test_worktree_record_is_read_from_main_checkout(self):
        self._git_repo()
        worktree = Path(self.test_dir) / "wt"
        self._git("worktree", "add", "-q", "-b", "feat/x", str(worktree))
        self.assertEqual(0, self._verify(worktree))
        self.assertEqual("satisfied", self._state_gates()["verification_passed"])
        self._commit_file("src/b.py", cwd=worktree)
        self.assertEqual("unmet", self._state_gates()["verification_passed"])

    def test_detached_head_refuses_to_record(self):
        self._git_repo()
        self._git("checkout", "-q", "--detach")
        self.assertEqual(2, self._verify())
        self.assertEqual([], self._verification_events())

    def test_deleted_branch_after_ship_keeps_shipped(self):
        from unittest.mock import patch

        self._git_repo()
        self._record_orchestration(epic="bug-1")
        self._git("checkout", "-q", "-b", "feat/y")
        self.assertEqual(0, self._verify())
        with patch("workflow_core.lifecycle_cli._beads_json", self._fake_beads([], epic_status="closed")):
            self.assertEqual(0, cli_main(["record", "shipped", "--repository", str(self.repo_path),
                                          "--evidence", "merged feat/y", "--actor", "user"]))
            before = self._state()
            self._git("checkout", "-q", "main")
            self._git("branch", "-q", "-D", "feat/y")
            after = self._state()
        self.assertEqual("satisfied", after["gates"]["shipped"])
        self.assertEqual("satisfied", after["gates"]["verification_passed"])
        self.assertEqual(before["stage"], after["stage"])

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

        self._git_repo()
        self._record_orchestration()
        self.assertEqual(0, cli_main(["record", "verification-passed", "--repository", str(self.repo_path),
                                      "--evidence", "547 tests OK", "--actor", "user"]))
        with patch("workflow_core.lifecycle_cli._beads_json", self._fake_beads(["closed"], epic_status="closed")):
            gates = self._state_gates()
        self.assertEqual("satisfied", gates["verification_passed"])
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
        self.assertEqual(0, cli_main(["record", "verification-passed", "--repository", str(self.repo_path),
                                      "--evidence", "tests OK", "--actor", "user"]))
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

    def test_record_rejects_epic_on_other_gates(self):
        self.assertEqual(2, cli_main(["record", "plan-approved", "--repository", str(self.repo_path),
                                      "--evidence", "plan.md", "--actor", "user", "--epic", "epic"]))

    def test_record_rejects_unknown_gate_and_missing_evidence(self):
        self.assertEqual(2, cli_main(["record", "no-such-gate", "--repository", str(self.repo_path),
                                      "--evidence", "x", "--actor", "user"]))
        self.assertEqual(2, cli_main(["record", "plan-approved", "--repository", str(self.repo_path),
                                      "--actor", "user"]))


if __name__ == "__main__":
    unittest.main()

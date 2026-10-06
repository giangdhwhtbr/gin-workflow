"""Local workflow state lives in the main checkout, also when commands run inside a linked worktree."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from workflow_core.assignments import (
    AssignmentManifest,
    AssignmentRequest,
    RouteCandidate,
    write_assignment_manifest,
)
from workflow_core.checkout import main_checkout
from workflow_core.cli import main as cli_main
from workflow_core.configuration import (
    get_session_harness_override,
    load_effective_config,
    resolve_effective_config,
)
from workflow_core.provider_config import load_provider_local_config
from workflow_core.setup_service import harness_override


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


class WorktreeStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name).resolve() / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / ".agent-workflow").mkdir()
        (self.repo / ".agent-workflow/config.yaml").write_text("schema_version: '2.3'\n")
        git(self.repo, "add", ".")
        git(self.repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x")
        self.tree = self.repo / ".planning/worktrees/wt1"
        git(self.repo, "worktree", "add", "-q", "-b", "feat/wt1", str(self.tree))

    def tearDown(self):
        self.tmp.cleanup()

    def gates(self, repository: Path, workflow_id: str) -> dict[str, str]:
        from contextlib import redirect_stdout
        import io

        out = io.StringIO()
        with redirect_stdout(out):
            cli_main(["state", "--repository", str(repository), "--format", "json", "--workflow-id", workflow_id])
        return json.loads(out.getvalue())["gates"]

    def test_main_checkout_of_a_linked_worktree_is_the_main_checkout(self):
        self.assertEqual(main_checkout(self.tree), self.repo)
        self.assertEqual(main_checkout(self.repo), self.repo)

    def test_main_checkout_outside_git_is_the_path_itself(self):
        plain = Path(self.tmp.name).resolve() / "plain"
        plain.mkdir()
        self.assertEqual(main_checkout(plain), plain)

    def test_gates_recorded_in_either_checkout_are_one_state(self):
        self.assertEqual(0, cli_main(["record", "requirement-confirmed", "--repository", str(self.repo),
                                      "--workflow-id", "wf", "--evidence", "spec.md", "--actor", "u"]))
        self.assertEqual(0, cli_main(["record", "plan-approved", "--repository", str(self.tree),
                                      "--workflow-id", "wf", "--evidence", "plan.md", "--actor", "u"]))
        for checkout in (self.repo, self.tree):
            gates = self.gates(checkout, "wf")
            self.assertEqual(gates["requirement_confirmed"], "satisfied", checkout)
            self.assertEqual(gates["plan_approved"], "satisfied", checkout)
        self.assertFalse((self.tree / ".agent-workflow/runtime/events.jsonl").exists())

    def test_generated_and_provider_local_config_are_read_from_the_main_checkout(self):
        resolve_effective_config(self.repo, repository_config={"schema_version": "2.3", "harness": "claude"})
        (self.repo / ".agent-workflow/providers.local.yaml").write_text(
            "schema_version: '2.3'\nproviders:\n  claude:\n    executable: claude\n"
            "    models:\n      low: haiku\n      medium: sonnet\n      high: opus\n")

        config = load_effective_config(self.tree)
        self.assertEqual(config.harness, "claude")
        self.assertEqual(config.repository_root, self.tree)
        self.assertEqual(load_provider_local_config(self.tree)["claude"].executable, "claude")

    def test_assignment_manifest_written_from_a_worktree_lands_in_the_main_checkout(self):
        request = AssignmentRequest("t1", "general", "medium", "claude", "wf")
        path = write_assignment_manifest(self.tree, AssignmentManifest("wf", request, (RouteCandidate("claude", "sonnet", False),)))
        self.assertEqual(path, self.repo / ".agent-workflow/runtime/assignments/wf.yaml")

    def test_session_harness_override_is_shared(self):
        harness_override(self.tree, harness="codex")
        self.assertEqual(get_session_harness_override(self.repo), "codex")

    def test_specs_migrate_sees_in_flight_workflows_recorded_in_the_main_checkout(self):
        from workflow_core.specs_migrate import in_flight_workflows

        self.assertEqual(0, cli_main(["record", "plan-approved", "--repository", str(self.repo),
                                      "--workflow-id", "wf", "--evidence", "plan.md", "--actor", "u"]))
        self.assertEqual(in_flight_workflows(self.tree), ["wf"])

"""The `python -m gin_orchestrator` orchestrator contract CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

import yaml

from tests.gin_orchestrator import paths  # noqa: F401
from gin_orchestrator.native_cli import list_models  # noqa: E402


def run(*argv: str, path: str | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": os.pathsep.join((str(paths.CORE_SCRIPTS), str(paths.ORCH_SCRIPTS)))}
    if path is not None:
        env["PATH"] = path + os.pathsep + env["PATH"]
    return subprocess.run(
        [sys.executable, "-m", "gin_orchestrator", *argv],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
    )


def git(root: Path, *argv: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *argv], cwd=root, check=True, capture_output=True)


CODEX_WORKER_STUB = (
    "#!/usr/bin/env python3\n"
    "import sys, json, re\n"
    "if sys.argv[1:3] == ['exec', '--help']:\n"
    "    print('usage: codex exec --model MODEL --json --ephemeral --dangerously-bypass-approvals-and-sandbox --cd DIR')\n"
    "    sys.exit(0)\n"
    "stdin_data = sys.stdin.read()\n"
    "if 'Reply with exactly the single word OK' in stdin_data:\n"
    "    print('OK')\n"
    "    sys.exit(0)\n"
    "match = re.search(r'\"task_id\":\\s*\"([^\"]+)\"', stdin_data)\n"
    "task_id = match.group(1) if match else 'task-1'\n"
    "status = 'failed' if 'fail-this-task' in stdin_data else 'completed'\n"
    "blockers = ['manual_failure'] if status == 'failed' else []\n"
    "result = {\n"
    "    'status': status,\n"
    "    'task_id': task_id,\n"
    "    'summary': 'stub executed',\n"
    "    'changed_files': [],\n"
    "    'commits': [],\n"
    "    'tests': [],\n"
    "    'evidence': [],\n"
    "    'blockers': blockers,\n"
    "}\n"
    "print(json.dumps(result))\n"
)


class ContractCliTests(unittest.TestCase):
    def test_version_prints_the_contract(self):
        result = run("version", "--json")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"contract": 2, "orchestrator_version": "0.2.0", "requires_gin_workflow": ">=3.0,<4",
                          "capabilities": ["health", "models", "routes", "reviewer", "doctor", "dispatch"]},
                         json.loads(result.stdout))

    @unittest.skipIf(os.name == "nt", "runs a #! stub script, which needs POSIX")
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

    @unittest.skipIf(os.name == "nt", "runs a #! stub script, which needs POSIX")
    def test_dispatch_runs_worker_without_orchestrator_local_yaml_in_single_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            bin_dir = base / "bin"
            bin_dir.mkdir()
            stub = bin_dir / "codex"
            stub.write_text(CODEX_WORKER_STUB, encoding="utf-8")
            stub.chmod(0o755)

            repo = base / "repo"
            workflow = repo / ".agent-workflow"
            workflow.mkdir(parents=True)
            git(repo, "init", "-q", "-b", "main")
            (workflow / "config.yaml").write_text(
                yaml.safe_dump({
                    "schema_version": "2.9",
                    "workflow_version": "2.9",
                    "provider_mode": "single",
                    "harness": "codex",
                }),
                encoding="utf-8",
            )
            launcher = paths.CORE_SCRIPTS / "gin"
            subprocess.run([sys.executable, str(launcher), "setup", "refresh", "--repository", str(repo)], check=True, capture_output=True)

            worktree = repo / ".planning/worktrees/task-1"
            worktree.mkdir(parents=True)

            result = run(
                "dispatch",
                "--workflow-id", "wf-1",
                "--task-id", "task-1",
                "--role", "backend",
                "--model", "gpt-6-astra",
                "--workspace", str(worktree),
                "--objective", "Implement task 1",
                "--stage", "execute",
                "--provider", "codex",
                "--repository", str(repo),
                "--json",
                path=str(bin_dir),
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("completed", payload["status"])
            self.assertEqual("task-1", payload["task_id"])

    @unittest.skipIf(os.name == "nt", "runs a #! stub script, which needs POSIX")
    def test_dispatch_from_inside_a_track_worktree_finds_the_owning_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            bin_dir = base / "bin"
            bin_dir.mkdir()
            stub = bin_dir / "codex"
            stub.write_text(CODEX_WORKER_STUB, encoding="utf-8")
            stub.chmod(0o755)

            repo = base / "repo"
            workflow = repo / ".agent-workflow"
            workflow.mkdir(parents=True)
            git(repo, "init", "-q", "-b", "main")
            (workflow / "config.yaml").write_text(
                yaml.safe_dump({
                    "schema_version": "2.9",
                    "workflow_version": "2.9",
                    "provider_mode": "single",
                    "harness": "codex",
                }),
                encoding="utf-8",
            )
            launcher = paths.CORE_SCRIPTS / "gin"
            subprocess.run([sys.executable, str(launcher), "setup", "refresh", "--repository", str(repo)], check=True, capture_output=True)

            worktree = repo / ".planning/worktrees/task-1"
            worktree.mkdir(parents=True)

            # No --repository, run from inside the track: the root is the repository that owns .planning/worktrees.
            result = run(
                "dispatch",
                "--workflow-id", "wf-1",
                "--task-id", "task-1",
                "--role", "backend",
                "--model", "gpt-6-astra",
                "--workspace", str(worktree),
                "--objective", "Implement task 1",
                "--stage", "execute",
                "--provider", "codex",
                "--json",
                path=str(bin_dir),
                cwd=worktree,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual("completed", json.loads(result.stdout)["status"])

    @unittest.skipIf(os.name == "nt", "runs a #! stub script, which needs POSIX")
    def test_dispatch_rejects_main_checkout_workspace_for_execute_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            bin_dir = base / "bin"
            bin_dir.mkdir()
            stub = bin_dir / "codex"
            stub.write_text(CODEX_WORKER_STUB, encoding="utf-8")
            stub.chmod(0o755)

            repo = base / "repo"
            workflow = repo / ".agent-workflow"
            workflow.mkdir(parents=True)
            git(repo, "init", "-q", "-b", "main")
            (workflow / "config.yaml").write_text(
                yaml.safe_dump({
                    "schema_version": "2.9",
                    "workflow_version": "2.9",
                    "provider_mode": "single",
                    "harness": "codex",
                }),
                encoding="utf-8",
            )
            launcher = paths.CORE_SCRIPTS / "gin"
            subprocess.run([sys.executable, str(launcher), "setup", "refresh", "--repository", str(repo)], check=True, capture_output=True)

            result = run(
                "dispatch",
                "--workflow-id", "wf-1",
                "--task-id", "task-1",
                "--role", "backend",
                "--model", "gpt-6-astra",
                "--workspace", str(repo),
                "--objective", "Implement task 1 in repo root",
                "--stage", "execute",
                "--provider", "codex",
                "--repository", str(repo),
                "--json",
                path=str(bin_dir),
            )
            self.assertEqual(1, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("failed", payload["status"])
            self.assertIn("worker_routes_unavailable", payload["blockers"])

    @unittest.skipIf(os.name == "nt", "runs a #! stub script, which needs POSIX")
    def test_dispatch_allows_main_checkout_workspace_for_review_and_plan_stages(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            bin_dir = base / "bin"
            bin_dir.mkdir()
            stub = bin_dir / "codex"
            stub.write_text(CODEX_WORKER_STUB, encoding="utf-8")
            stub.chmod(0o755)

            repo = base / "repo"
            workflow = repo / ".agent-workflow"
            workflow.mkdir(parents=True)
            git(repo, "init", "-q", "-b", "main")
            (workflow / "config.yaml").write_text(
                yaml.safe_dump({
                    "schema_version": "2.9",
                    "workflow_version": "2.9",
                    "provider_mode": "single",
                    "harness": "codex",
                }),
                encoding="utf-8",
            )
            launcher = paths.CORE_SCRIPTS / "gin"
            subprocess.run([sys.executable, str(launcher), "setup", "refresh", "--repository", str(repo)], check=True, capture_output=True)

            result_review = run(
                "dispatch",
                "--workflow-id", "wf-1",
                "--task-id", "task-1",
                "--role", "review",
                "--model", "gpt-6-astra",
                "--workspace", str(repo),
                "--objective", "Review changes",
                "--stage", "review",
                "--provider", "codex",
                "--repository", str(repo),
                "--json",
                path=str(bin_dir),
            )
            self.assertEqual(0, result_review.returncode, result_review.stderr)
            payload_review = json.loads(result_review.stdout)
            self.assertEqual("completed", payload_review["status"])

            result_discuss = run(
                "dispatch",
                "--workflow-id", "wf-1",
                "--task-id", "task-1",
                "--role", "general",
                "--model", "gpt-6-astra",
                "--workspace", str(repo),
                "--objective", "Discuss architecture",
                "--stage", "discuss",
                "--provider", "codex",
                "--repository", str(repo),
                "--json",
                path=str(bin_dir),
            )
            self.assertEqual(0, result_discuss.returncode, result_discuss.stderr)
            payload_discuss = json.loads(result_discuss.stdout)
            self.assertEqual("completed", payload_discuss["status"])

    @unittest.skipIf(os.name == "nt", "runs a #! stub script, which needs POSIX")
    def test_dispatch_exits_one_when_worker_result_is_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            bin_dir = base / "bin"
            bin_dir.mkdir()
            stub = bin_dir / "codex"
            stub.write_text(CODEX_WORKER_STUB, encoding="utf-8")
            stub.chmod(0o755)

            repo = base / "repo"
            workflow = repo / ".agent-workflow"
            workflow.mkdir(parents=True)
            git(repo, "init", "-q", "-b", "main")
            (workflow / "config.yaml").write_text(
                yaml.safe_dump({
                    "schema_version": "2.9",
                    "workflow_version": "2.9",
                    "provider_mode": "single",
                    "harness": "codex",
                }),
                encoding="utf-8",
            )
            launcher = paths.CORE_SCRIPTS / "gin"
            subprocess.run([sys.executable, str(launcher), "setup", "refresh", "--repository", str(repo)], check=True, capture_output=True)

            worktree = repo / ".planning/worktrees/task-1"
            worktree.mkdir(parents=True)

            result = run(
                "dispatch",
                "--workflow-id", "wf-1",
                "--task-id", "task-1",
                "--role", "backend",
                "--model", "gpt-6-astra",
                "--workspace", str(worktree),
                "--objective", "fail-this-task: intentional test failure",
                "--stage", "execute",
                "--provider", "codex",
                "--repository", str(repo),
                "--json",
                path=str(bin_dir),
            )
            self.assertEqual(1, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("failed", payload["status"])
            self.assertIn("manual_failure", payload["blockers"])

    @unittest.skipIf(os.name == "nt", "runs a #! stub script, which needs POSIX")
    def test_dispatch_reads_objective_from_file(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            bin_dir = base / "bin"
            bin_dir.mkdir()
            stub = bin_dir / "codex"
            stub.write_text(CODEX_WORKER_STUB, encoding="utf-8")
            stub.chmod(0o755)

            repo = base / "repo"
            workflow = repo / ".agent-workflow"
            workflow.mkdir(parents=True)
            git(repo, "init", "-q", "-b", "main")
            (workflow / "config.yaml").write_text(
                yaml.safe_dump({
                    "schema_version": "2.9",
                    "workflow_version": "2.9",
                    "provider_mode": "single",
                    "harness": "codex",
                }),
                encoding="utf-8",
            )
            launcher = paths.CORE_SCRIPTS / "gin"
            subprocess.run([sys.executable, str(launcher), "setup", "refresh", "--repository", str(repo)], check=True, capture_output=True)

            worktree = repo / ".planning/worktrees/task-1"
            worktree.mkdir(parents=True)

            obj_file = base / "prompt.txt"
            obj_file.write_text("Objective read from file\n", encoding="utf-8")

            result = run(
                "dispatch",
                "--workflow-id", "wf-1",
                "--task-id", "task-1",
                "--role", "backend",
                "--model", "gpt-6-astra",
                "--workspace", str(worktree),
                "--objective-file", str(obj_file),
                "--stage", "execute",
                "--provider", "codex",
                "--repository", str(repo),
                "--json",
                path=str(bin_dir),
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("completed", payload["status"])

    @unittest.skipIf(os.name == "nt", "runs a #! stub script, which needs POSIX")
    def test_dispatch_rejects_symlink_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            bin_dir = base / "bin"
            bin_dir.mkdir()
            stub = bin_dir / "codex"
            stub.write_text(CODEX_WORKER_STUB, encoding="utf-8")
            stub.chmod(0o755)

            repo = base / "repo"
            workflow = repo / ".agent-workflow"
            workflow.mkdir(parents=True)
            git(repo, "init", "-q", "-b", "main")
            (workflow / "config.yaml").write_text(
                yaml.safe_dump({
                    "schema_version": "2.9",
                    "workflow_version": "2.9",
                    "provider_mode": "single",
                    "harness": "codex",
                }),
                encoding="utf-8",
            )
            launcher = paths.CORE_SCRIPTS / "gin"
            subprocess.run([sys.executable, str(launcher), "setup", "refresh", "--repository", str(repo)], check=True, capture_output=True)

            worktree = repo / ".planning/worktrees/task-1"
            worktree.mkdir(parents=True)

            symlink_ws = base / "symlink_ws"
            symlink_ws.symlink_to(worktree)

            result = run(
                "dispatch",
                "--workflow-id", "wf-1",
                "--task-id", "task-1",
                "--role", "backend",
                "--model", "gpt-6-astra",
                "--workspace", str(symlink_ws),
                "--objective", "Implement task 1",
                "--stage", "execute",
                "--provider", "codex",
                "--repository", str(repo),
                "--json",
                path=str(bin_dir),
            )
            self.assertEqual(1, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("failed", payload["status"])
            self.assertIn("worker_routes_unavailable", payload["blockers"])


if __name__ == "__main__":
    unittest.main()

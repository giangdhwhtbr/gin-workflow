"""Orchestrator contract v2: version, routes resolve, reviewer, doctor and configure."""

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

from tests.gin_orchestrator import paths
from workflow_core.assignments import AssignmentRequest  # noqa: E402
from workflow_core.configuration import load_effective_config  # noqa: E402
from workflow_core.migrations import migrate_config  # noqa: E402
from gin_orchestrator.local_config import LOCAL_FILE, load_local_config  # noqa: E402
from gin_orchestrator.routes import resolve_all_assignments  # noqa: E402
from tests.workflow_core.test_schema_2_8 import LEGACY  # noqa: E402

LAUNCHER = paths.CORE_SCRIPTS / "gin-workflow"
CODEX_STUB = (
    "#!/bin/sh\nif [ \"$1\" = \"exec\" ] && [ \"$2\" = \"--help\" ]; then\n"
    "  echo 'usage: codex exec --model MODEL --json --ephemeral"
    " --dangerously-bypass-approvals-and-sandbox --cd DIR'\n  exit 0\nfi\nexit 0\n"
)
TRACKS = [
    {"task_id": "t1", "provider_role": "backend", "reasoning": "high"},
    {"task_id": "t2", "provider_role": "backend", "reasoning": "low"},
]


def run(*argv: str, path: str | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": os.pathsep.join((str(paths.CORE_SCRIPTS), str(paths.ORCH_SCRIPTS)))}
    if path is not None:
        env["PATH"] = path + os.pathsep + env["PATH"]
    return subprocess.run([sys.executable, "-m", "gin_orchestrator", *argv], env=env, capture_output=True,
                          text=True, check=False)


def git(root: Path, *argv: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *argv], cwd=root, check=True,
                   capture_output=True)


class ContractV2Tests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "repo"
        workflow = self.root / ".agent-workflow"
        workflow.mkdir(parents=True)
        git(self.root, "init", "-q", "-b", "main")
        config = migrate_config(LEGACY, "2.8")
        config["orchestrator"]["roles"]["review"] = {"preferred": ["codex", "main_harness"]}
        (workflow / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
        self.stub = Path(self.directory.name) / "fake-codex"
        self.stub.write_text(CODEX_STUB, encoding="utf-8")
        self.stub.chmod(self.stub.stat().st_mode | stat.S_IEXEC)
        models = {"low": "haiku", "medium": "sonnet", "high": "opus"}
        (self.root / LOCAL_FILE).write_text(yaml.safe_dump({
            "schema_version": "2.8",
            "providers": {"claude": {"executable": "claude", "models": models},
                          "codex": {"executable": str(self.stub), "models": models}},
        }), encoding="utf-8")
        self.refresh()

    def refresh(self) -> None:
        done = subprocess.run([sys.executable, str(LAUNCHER), "setup", "refresh", "--repository", str(self.root)],
                              capture_output=True, text=True, check=False)
        self.assertEqual(0, done.returncode, done.stderr)

    def tracks_file(self, tracks) -> Path:
        path = Path(self.directory.name) / "tracks.json"
        path.write_text(json.dumps(tracks), encoding="utf-8")
        return path

    def test_version_reports_contract_2_and_capabilities(self):
        result = run("version", "--json")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"contract": 2, "orchestrator_version": "0.0.0", "requires_gin_workflow": ">=2.0,<3",
                          "capabilities": ["health", "models", "routes", "reviewer", "doctor"]},
                         json.loads(result.stdout))

    def test_routes_resolve_matches_the_library(self):
        result = run("routes", "resolve", "--workflow-id", "wf", "--tracks", str(self.tracks_file(TRACKS)),
                     "--main-harness", "claude", "--repository", str(self.root), "--json")

        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        requests = [AssignmentRequest(t["task_id"], t["provider_role"], t["reasoning"], "claude", "wf")
                    for t in TRACKS]
        expected = resolve_all_assignments(requests, load_effective_config(self.root), load_local_config(self.root))
        self.assertEqual([m.to_dict() for m in expected], payload["routes"])
        self.assertEqual({"workflow_id": "wf", "main_harness": "claude", "diagnostics": []},
                         {key: payload[key] for key in ("workflow_id", "main_harness", "diagnostics")})
        self.assertFalse((self.root / ".agent-workflow/runtime/assignments").exists())

    def test_routes_resolve_reports_diagnostics_with_exit_0(self):
        tracks = [{"task_id": "t1", "provider_role": "nope", "reasoning": "high"}]

        result = run("routes", "resolve", "--workflow-id", "wf", "--tracks", str(self.tracks_file(tracks)),
                     "--main-harness", "claude", "--repository", str(self.root), "--json")

        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual([], payload["routes"])
        self.assertEqual(["t1.provider_role: unknown provider role: nope"], payload["diagnostics"])

    def test_reviewer_prefers_a_provider_other_than_the_implementer(self):
        (self.root / "a.txt").write_text("a", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-q", "-m", "base")
        git(self.root, "branch", "base")
        (self.root / "b.py").write_text("b = 1\n", encoding="utf-8")
        git(self.root, "add", "b.py")
        git(self.root, "commit", "-q", "-m", "change")

        result = run("reviewer", "--base", "base", "--implementer", "claude", "--tier", "high",
                     "--repository", str(self.root), "--json")

        self.assertEqual(0, result.returncode, result.stderr)
        routes = json.loads(result.stdout)
        self.assertEqual([("codex", "opus", None, "reviewer:codex")],
                         [(r["provider"], r["model"], r["effort"], r["actor_id"]) for r in routes])

    def test_doctor_reports_each_provider_tier(self):
        result = run("doctor", "--repository", str(self.root), "--json")

        self.assertEqual(0, result.returncode, result.stderr)
        providers = json.loads(result.stdout)["providers"]
        for tier in ("low", "medium", "high"):
            self.assertIn(f"codex.{tier}", providers)
            self.assertTrue(providers[f"codex.{tier}"]["available"], providers)

    def gin_workflow_path(self) -> str:
        bin_dir = Path(self.directory.name) / "bin"
        bin_dir.mkdir(exist_ok=True)
        if not (bin_dir / "gin-workflow").exists():
            (bin_dir / "gin-workflow").symlink_to(LAUNCHER)
        return str(bin_dir)

    def test_configure_writes_orchestrator_keys_through_gin_workflow(self):
        result = run("configure", "--set", "orchestrator.concurrency.codex=2", "--local-set",
                     "providers.codex.executable=codex", "--approve", "--repository", str(self.root), "--json",
                     path=self.gin_workflow_path())

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("configured", json.loads(result.stdout)["status"])
        config = yaml.safe_load((self.root / ".agent-workflow/config.yaml").read_text(encoding="utf-8"))
        self.assertEqual(2, config["orchestrator"]["concurrency"]["codex"])
        local = yaml.safe_load((self.root / LOCAL_FILE).read_text(encoding="utf-8"))
        self.assertEqual("codex", local["providers"]["codex"]["executable"])
        self.assertEqual(2, load_effective_config(self.root)["orchestrator"]["concurrency"]["codex"])
        ignored = (self.root / ".agent-workflow/.gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("orchestrator.local.yaml", ignored)

    def test_configure_dry_run_changes_nothing(self):
        before = (self.root / ".agent-workflow/config.yaml").read_bytes()

        result = run("configure", "--set", "orchestrator.concurrency.codex=2", "--dry-run",
                     "--repository", str(self.root), "--json")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("would_configure", json.loads(result.stdout)["status"])
        self.assertEqual(before, (self.root / ".agent-workflow/config.yaml").read_bytes())

    def test_configure_rejects_keys_outside_orchestrator(self):
        before = (self.root / ".agent-workflow/config.yaml").read_bytes()

        result = run("configure", "--set", "harness=codex", "--approve", "--repository", str(self.root), "--json",
                     path=self.gin_workflow_path())

        self.assertEqual(2, result.returncode)
        self.assertIn("orchestrator.", result.stderr)
        self.assertEqual(before, (self.root / ".agent-workflow/config.yaml").read_bytes())


    def test_configure_reports_a_malformed_local_file(self):
        for content in ("providers: [", "- not a mapping\n"):
            (self.root / LOCAL_FILE).write_text(content, encoding="utf-8")

            result = run("configure", "--local-set", "providers.claude.executable=claude", "--dry-run",
                         "--repository", str(self.root), "--json")

            self.assertEqual(2, result.returncode, result.stderr)
            self.assertIn("error: invalid orchestrator.local.yaml", result.stderr)

if __name__ == "__main__":
    unittest.main()

"""Tests for `gin team complete`: closes an epic once every track bead is closed and every PR merged."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import TEAM, fake_cli, git, init_beads, make_team_repo, path_with, write  # noqa: E402
from team_fixtures import run_cli as run_cli_subprocess, run_cli_in_process as run_cli  # noqa: E402
from workflow_core.configuration import resolve_effective_config  # noqa: E402


def bd(root: Path, *args: str, actor: str = "") -> str:
    env = None if not actor else {**os.environ, "BD_ACTOR": actor}
    return subprocess.run(["bd", *args], cwd=root, check=True, capture_output=True, text=True, env=env,
                          stdin=subprocess.DEVNULL, timeout=60).stdout


def create(root: Path, title: str, *labels: str, bead_type: str = "task", parent: str | None = None,
           description: str = "") -> str:
    argv = ["create", title, "-t", bead_type, "--json"]
    if labels:
        argv += ["-l", ",".join(labels)]
    if parent:
        argv += ["--parent", parent]
    if description:
        argv += ["-d", description]
    return json.loads(bd(root, *argv))["id"]


def show(root: Path, bead: str) -> dict:
    data = json.loads(bd(root, "show", bead, "--json"))
    return data[0] if isinstance(data, list) else data


HAS_BD = shutil.which("bd") is not None


@unittest.skipUnless(HAS_BD, "bd is not installed")
class TestTeamComplete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpl = tempfile.TemporaryDirectory()
        tmpl_root = Path(cls.tmpl.name) / "repo"
        cls.origin_bare = Path(cls.tmpl.name) / "origin.git"
        git(Path(cls.tmpl.name), "init", "-q", "--bare", "-b", "main", str(cls.origin_bare))
        make_team_repo(tmpl_root, email="binh@corp.com", host="github")
        git(tmpl_root, "remote", "set-url", "origin", str(cls.origin_bare))
        git(tmpl_root, "commit", "-q", "--allow-empty", "-m", "init")
        git(tmpl_root, "push", "-q", "origin", "main")
        init_beads(tmpl_root)
        resolve_effective_config(tmpl_root)

        cls.epic = create(tmpl_root, "Login epic", bead_type="epic")
        cls.t1 = create(tmpl_root, "Track 1", parent=cls.epic,
                        description="Plan: .planning/plans/2026-11-14-login.md, Track 1")
        cls.t2 = create(tmpl_root, "Track 2", parent=cls.epic,
                        description="Plan: .planning/plans/2026-11-14-login.md, Track 2")
        bd(tmpl_root, "close", cls.t1)
        bd(tmpl_root, "close", cls.t2)
        cls.tmpl_root = tmpl_root

    @classmethod
    def tearDownClass(cls):
        cls.tmpl.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo"
        shutil.copytree(self.tmpl_root, self.root)
        self.bin = Path(self.tmp.name) / "bin"
        self.env = path_with(self.bin)

    def gh(self, *rules: dict) -> None:
        fake_cli(self.bin, "gh", [
            *rules,
            {"argv": ["pr", "list"], "stdout": []},
        ])

    def test_both_tracks_closed_and_both_pull_requests_merged(self):
        self.gh(
            {"argv": ["pr", "list", "--head", "feat/login-t1"],
             "stdout": [{"url": "https://github.com/org/app/pull/1", "state": "MERGED",
                         "mergeCommit": {"oid": "m" * 40}}]},
            {"argv": ["pr", "list", "--head", "feat/login-t2"],
             "stdout": [{"url": "https://github.com/org/app/pull/2", "state": "MERGED",
                         "mergeCommit": {"oid": "m" * 40}}]},
        )
        result = run_cli_subprocess(self.root, "team", "complete", self.epic, env=self.env)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(f"completed {self.epic}", result.stdout)
        self.assertIn("merged https://github.com/org/app/pull/1", result.stdout)
        self.assertIn("merged https://github.com/org/app/pull/2", result.stdout)

        epic_data = show(self.root, self.epic)
        self.assertEqual("closed", epic_data["status"])
        reason = epic_data.get("close_reason") or ""
        self.assertIn("https://github.com/org/app/pull/1", reason)
        self.assertIn("https://github.com/org/app/pull/2", reason)

    def test_one_pull_request_open_leaves_epic_open_and_exits_1(self):
        self.gh(
            {"argv": ["pr", "list", "--head", "feat/login-t1"],
             "stdout": [{"url": "https://github.com/org/app/pull/1", "state": "MERGED",
                         "mergeCommit": {"oid": "m" * 40}}]},
            {"argv": ["pr", "list", "--head", "feat/login-t2"],
             "stdout": [{"url": "https://github.com/org/app/pull/2", "state": "OPEN",
                         "mergeCommit": None}]},
        )
        result = run_cli(self.root, "team", "complete", self.epic, env=self.env)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn(f"incomplete {self.epic}", result.stdout)
        self.assertIn("missing feat/login-t2: open", result.stdout)
        self.assertEqual("open", show(self.root, self.epic)["status"])

    def test_one_track_bead_open_leaves_epic_open_and_exits_1(self):
        bd(self.root, "reopen", self.t2)
        self.gh(
            {"argv": ["pr", "list", "--head", "feat/login-t1"],
             "stdout": [{"url": "https://github.com/org/app/pull/1", "state": "MERGED",
                         "mergeCommit": {"oid": "m" * 40}}]},
            {"argv": ["pr", "list", "--head", "feat/login-t2"],
             "stdout": [{"url": "https://github.com/org/app/pull/2", "state": "MERGED",
                         "mergeCommit": {"oid": "m" * 40}}]},
        )
        result = run_cli(self.root, "team", "complete", self.epic, env=self.env)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn(f"incomplete {self.epic}", result.stdout)
        self.assertIn(f"missing {self.t2} is open", result.stdout)
        self.assertEqual("open", show(self.root, self.epic)["status"])

    def test_member_without_lead_role_exits_2(self):
        git(self.root, "config", "user.email", "em@corp.com")
        result = run_cli(self.root, "team", "complete", self.epic, env=self.env)
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn("only an area lead completes an epic", result.stderr)

    def test_team_mode_off_exits_2(self):
        write(self.root, ".agent-workflow/config.yaml", "schema_version: '2.7'\n")
        resolve_effective_config(self.root)
        result = run_cli(self.root, "team", "complete", self.epic, env=self.env)
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn("team mode is off", result.stderr)

    def test_gh_fake_exiting_with_auth_error_exits_2_and_leaves_epic_open(self):
        fake_cli(self.bin, "gh", [
            {"argv": ["pr", "list"], "exit": 4, "stderr": "authentication failed"},
        ])
        result = run_cli(self.root, "team", "complete", self.epic, env=self.env)
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertEqual("open", show(self.root, self.epic)["status"])

    def test_refuses_non_epic_bead_with_exit_2(self):
        self.gh()
        result = run_cli(self.root, "team", "complete", self.t1, env=self.env)
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn(f"{self.t1} is not an epic", result.stderr)

    def merged_gh(self) -> None:
        self.gh(
            {"argv": ["pr", "list", "--head", "feat/login-t1"],
             "stdout": [{"url": "https://github.com/org/app/pull/1", "state": "MERGED",
                         "mergeCommit": {"oid": "m" * 40}}]},
            {"argv": ["pr", "list", "--head", "feat/login-t2"],
             "stdout": [{"url": "https://github.com/org/app/pull/2", "state": "MERGED",
                         "mergeCommit": {"oid": "m" * 40}}]},
        )

    def test_open_prep_child_is_closed_with_a_reason_before_the_epic(self):
        prep = create(self.root, "Capture notes", "prep", parent=self.epic)
        self.merged_gh()
        result = run_cli(self.root, "team", "complete", self.epic, env=self.env)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(f"closed prep {prep}", result.stdout)
        self.assertEqual("closed", show(self.root, self.epic)["status"])
        prep_data = show(self.root, prep)
        self.assertEqual("closed", prep_data["status"])
        self.assertEqual(f"not needed: {self.epic} shipped", prep_data.get("close_reason"))

    def test_closed_prep_is_listed_in_json(self):
        prep = create(self.root, "Capture notes", "prep", parent=self.epic)
        self.merged_gh()
        result = run_cli(self.root, "team", "complete", self.epic, "--format", "json", env=self.env)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual([prep], json.loads(result.stdout)["closed_prep"])

    def test_json_format(self):
        self.merged_gh()
        result = run_cli(self.root, "team", "complete", self.epic, "--format", "json", env=self.env)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("completed", payload["status"])
        self.assertEqual(self.epic, payload["epic"])
        self.assertEqual([], payload["missing"])
        self.assertEqual(["https://github.com/org/app/pull/1", "https://github.com/org/app/pull/2"],
                         payload["pull_requests"])

    def test_sync_hint_when_beads_sync_is_configured(self):
        extra = "  beads_sync:\n    remote: origin\n"
        write(self.root, ".agent-workflow/config.yaml",
              f"schema_version: '2.7'\n{TEAM.format(host='github')}{extra}")
        resolve_effective_config(self.root)
        self.merged_gh()
        result = run_cli(self.root, "team", "complete", self.epic, env=self.env)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("next: gin team sync", result.stdout)

    def test_unknown_epic_exits_2(self):
        self.gh()
        result = run_cli(self.root, "team", "complete", "t-nope", env=self.env)
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)

    def test_failed_bd_close_exits_2_and_reports_nothing_completed(self):
        real = shutil.which("bd")
        script = self.bin / "bd"
        self.bin.mkdir(parents=True, exist_ok=True)
        script.write_text(f'#!/bin/sh\nif [ "$1" = close ]; then echo "close refused" >&2; exit 1; fi\n'
                          f'exec {real} "$@"\n', encoding="utf-8")
        script.chmod(0o755)
        self.merged_gh()
        result = run_cli(self.root, "team", "complete", self.epic, env=self.env)
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn("close refused", result.stderr)
        self.assertNotIn("completed", result.stdout)
        self.assertEqual("open", show(self.root, self.epic)["status"])


@unittest.skipUnless(HAS_BD, "bd is not installed")
class TestTeamCompleteWorkspace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.child_bare = self.base / "child.git"
        git(self.base, "init", "-q", "--bare", "-b", "main", str(self.child_bare))

        self.parent_bare = self.base / "parent.git"
        git(self.base, "init", "-q", "--bare", "-b", "main", str(self.parent_bare))

        self.root = make_team_repo(self.base / "ws", email="binh@corp.com", host="github", extra=(
            "workspace:\n  repos:\n    - path: services/order-api\n"
            f"      url: file://{self.child_bare}\n      default_branch: main\n      shape: backend\n"
        ))
        git(self.root, "remote", "set-url", "origin", str(self.parent_bare))
        git(self.root, "commit", "-q", "--allow-empty", "-m", "parent base")
        git(self.root, "push", "-q", "origin", "main")
        init_beads(self.root)
        resolve_effective_config(self.root)

        self.child_dir = self.root / "services/order-api"
        git(self.root, "clone", "-q", str(self.child_bare), str(self.child_dir))
        git(self.child_dir, "config", "user.email", "binh@corp.com")
        git(self.child_dir, "config", "user.name", "T")

        self.bin = self.base / "bin"
        self.env = path_with(self.bin)

        self.epic = create(self.root, "Order epic", bead_type="epic")
        self.t1 = create(self.root, "Order track", parent=self.epic,
                         description="Plan: .planning/plans/2026-11-14-order.md, Track 1\nRepo: services/order-api")
        bd(self.root, "close", self.t1)

    def gh(self, *rules: dict) -> None:
        fake_cli(self.bin, "gh", [
            *rules,
            {"argv": ["pr", "list"], "stdout": []},
        ])

    def test_workspace_parent_whose_origin_has_feat_x_with_open_pr_exits_1(self):
        # Push feat/order to origin parent
        git(self.root, "branch", "feat/order")
        git(self.root, "push", "-q", "origin", "feat/order")

        # Track 1 PR is merged in child repo, but parent feat/order PR is OPEN
        self.gh(
            {"argv": ["pr", "list", "--head", "feat/order-t1"],
             "stdout": [{"url": "https://github.com/org/child/pull/1", "state": "MERGED",
                         "mergeCommit": {"oid": "m" * 40}}]},
            {"argv": ["pr", "list", "--head", "feat/order"],
             "stdout": [{"url": "https://github.com/org/parent/pull/10", "state": "OPEN",
                         "mergeCommit": None}]},
        )
        result = run_cli(self.root, "team", "complete", self.epic, env=self.env)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn(f"incomplete {self.epic}", result.stdout)
        self.assertIn("missing feat/order: open", result.stdout)
        self.assertEqual("open", show(self.root, self.epic)["status"])

    def test_uncloned_child_repo_reports_missing_clone_and_exits_1(self):
        # Remove cloned child dir
        shutil.rmtree(self.child_dir)
        self.gh()
        result = run_cli(self.root, "team", "complete", self.epic, env=self.env)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn(f"incomplete {self.epic}", result.stdout)
        self.assertIn(f"missing {self.t1}: services/order-api is not cloned; run gin workspace clone services/order-api",
                      result.stdout)

    def push_parent_branch(self, topic: str) -> None:
        git(self.root, "branch", f"feat/{topic}")
        git(self.root, "push", "-q", "origin", f"feat/{topic}")

    def track_pr(self, topic: str, url: str) -> dict:
        return {"argv": ["pr", "list", "--head", f"feat/{topic}-t1"],
                "stdout": [{"url": url, "state": "MERGED", "mergeCommit": {"oid": "m" * 40}}]}

    def test_merged_parent_pull_request_is_listed_in_the_close_reason(self):
        self.push_parent_branch("order")
        self.gh(self.track_pr("order", "https://github.com/org/child/pull/1"),
                {"argv": ["pr", "list", "--head", "feat/order"],
                 "stdout": [{"url": "https://github.com/org/parent/pull/10", "state": "MERGED",
                             "mergeCommit": {"oid": "m" * 40}}]})
        result = run_cli(self.root, "team", "complete", self.epic, env=self.env)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("merged https://github.com/org/parent/pull/10", result.stdout)
        self.assertIn("https://github.com/org/parent/pull/10", show(self.root, self.epic).get("close_reason") or "")

    def test_parent_branch_without_pull_request_is_missing(self):
        self.push_parent_branch("order")
        self.gh(self.track_pr("order", "https://github.com/org/child/pull/1"))
        result = run_cli(self.root, "team", "complete", self.epic, env=self.env)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("missing feat/order: no pull request", result.stdout)
        self.assertEqual("open", show(self.root, self.epic)["status"])

    def test_ls_remote_failure_exits_2(self):
        git(self.root, "remote", "set-url", "origin", str(self.base / "does-not-exist.git"))
        self.gh(self.track_pr("order", "https://github.com/org/child/pull/1"))
        result = run_cli(self.root, "team", "complete", self.epic, env=self.env)
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn("git ls-remote failed in parent repository", result.stderr)
        self.assertEqual("open", show(self.root, self.epic)["status"])

    def test_every_plan_topic_is_checked_on_the_parent(self):
        t2 = create(self.root, "Cart track", parent=self.epic,
                    description="Plan: .planning/plans/2026-11-14-cart.md, Track 1\nRepo: services/order-api")
        bd(self.root, "close", t2)
        self.push_parent_branch("cart")
        self.gh(self.track_pr("order", "https://github.com/org/child/pull/1"),
                self.track_pr("cart", "https://github.com/org/child/pull/2"),
                {"argv": ["pr", "list", "--head", "feat/cart"],
                 "stdout": [{"url": "https://github.com/org/parent/pull/11", "state": "OPEN",
                             "mergeCommit": None}]})
        result = run_cli(self.root, "team", "complete", self.epic, env=self.env)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("missing feat/cart: open", result.stdout)
        self.assertEqual("open", show(self.root, self.epic)["status"])

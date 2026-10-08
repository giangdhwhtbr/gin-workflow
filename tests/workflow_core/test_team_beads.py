"""Team Beads: my ready work, claims, external placeholders, and Dolt sync through a git remote (real bd/dolt)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import pty
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import TEAM, fake_cli, git, make_team_repo, path_with, run_cli  # noqa: E402
from workflow_core import team_beads  # noqa: E402
from workflow_core.team import team_for_repo  # noqa: E402

HAS_BD = shutil.which("bd") is not None
HAS_DOLT = shutil.which("dolt") is not None


def bd(root: Path, *args: str, actor: str = "") -> str:
    env = None if not actor else {**os.environ, "BD_ACTOR": actor}
    return subprocess.run(["bd", *args], cwd=root, check=True, capture_output=True, text=True, env=env,
                          stdin=subprocess.DEVNULL, timeout=60).stdout


def create(root: Path, title: str, *labels: str) -> str:
    argv = ["create", title, "--json"] + (["-l", ",".join(labels)] if labels else [])
    return json.loads(bd(root, *argv))["id"]


def show(root: Path, bead: str) -> dict:
    data = json.loads(bd(root, "show", bead, "--json"))
    return data[0] if isinstance(data, list) else data


@unittest.skipUnless(HAS_BD, "bd is not installed")
class TestBdHelperUnderATerminal(unittest.TestCase):
    """`bd init` waits on a terminal stdin, so the suite hung when run from a pseudo-terminal."""

    def test_bd_init_does_not_wait_on_a_terminal_stdin(self):
        master, slave = pty.openpty()
        saved = os.dup(0)
        os.dup2(slave, 0)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                git(Path(tmp), "init", "-q")
                bd(Path(tmp), "init", "--prefix", "t", "-q")
        finally:
            os.dup2(saved, 0)
            for fd in (saved, master, slave):
                os.close(fd)


@unittest.skipUnless(HAS_BD, "bd is not installed")
class TestTeamBeadsLocal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_team_repo(Path(self.tmp.name) / "repo")
        git(self.root, "commit", "-q", "--allow-empty", "-m", "base")
        bd(self.root, "init", "--prefix", "t", "-q")

    def tearDown(self):
        self.tmp.cleanup()

    def test_ready_lists_mine_and_my_areas(self):
        mine = create(self.root, "mine")
        bd(self.root, "update", mine, "--assignee", "binh@corp.com")
        backend = create(self.root, "backend", "area:backend", "track:1")
        create(self.root, "frontend", "area:frontend")
        theirs = create(self.root, "theirs", "area:backend")
        bd(self.root, "update", theirs, "--assignee", "em@corp.com")
        rows = json.loads(run_cli(self.root, "team", "ready", "--format", "json").stdout)["ready"]
        self.assertEqual({mine, backend}, {row["id"] for row in rows})

    def test_claim_and_already_claimed(self):
        free = create(self.root, "free", "area:backend")
        result = run_cli(self.root, "team", "claim", free)
        self.assertEqual(0, result.returncode, result.stderr)
        claimed = show(self.root, free)
        self.assertEqual(("binh@corp.com", "in_progress"), (claimed["assignee"], claimed["status"]))
        held = create(self.root, "held", "area:backend")
        bd(self.root, "update", held, "--claim", actor="em@corp.com")
        refused = run_cli(self.root, "team", "claim", held)
        self.assertEqual(1, refused.returncode)
        self.assertIn("already claimed by em@corp.com", refused.stdout)

    def test_reassign_lead_takes_over_and_checks_eligibility(self):
        bead = create(self.root, "work", "area:backend")
        bd(self.root, "update", bead, "--claim", actor="em@corp.com")
        refused = run_cli(self.root, "team", "reassign", bead, "chi@corp.com")
        self.assertEqual(1, refused.returncode)
        self.assertIn("may not own tracks in backend", refused.stdout)
        self.assertEqual(2, run_cli(self.root, "team", "reassign", bead, "nobody@corp.com").returncode)
        done = run_cli(self.root, "team", "reassign", bead, "binh@corp.com")
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        moved = show(self.root, bead)
        self.assertEqual("binh@corp.com", moved["assignee"])
        self.assertIn("reassigned em@corp.com -> binh@corp.com by binh@corp.com", moved["notes"])
        again = run_cli(self.root, "team", "reassign", bead, "binh@corp.com")
        self.assertEqual(1, again.returncode)
        self.assertIn("already assigned", again.stdout)

    def test_reassign_by_non_holder_non_lead_is_refused(self):
        bead = create(self.root, "work", "area:backend")
        bd(self.root, "update", bead, "--claim", actor="binh@corp.com")
        git(self.root, "config", "user.email", "em@corp.com")
        refused = run_cli(self.root, "team", "reassign", bead, "em@corp.com")
        self.assertEqual(1, refused.returncode)
        self.assertIn("only binh@corp.com or the lead", refused.stdout)
        mine = create(self.root, "mine", "area:backend")
        bd(self.root, "update", mine, "--claim", actor="em@corp.com")
        self.assertEqual(0, run_cli(self.root, "team", "reassign", mine, "binh@corp.com").returncode)

    def test_deps_closes_placeholders_whose_track_merged(self):
        done = create(self.root, "external: .planning/plans/p.md#2")
        pending = create(self.root, "external: .planning/plans/p.md#3")
        create(self.root, "unrelated")
        bin_dir = Path(self.tmp.name) / "bin"
        fake_cli(bin_dir, "gh", [{"argv": ["pr", "list"], "stdout": [
            {"url": "https://github.com/org/app/pull/9", "mergeCommit": {"oid": "abc"},
             "body": "Plan: .planning/plans/p.md\nTracks: 1, 2\n"},
            {"url": "https://github.com/org/app/pull/8", "mergeCommit": {"oid": "def"},
             "body": "Plan: .planning/plans/other.md\nTracks: 3\n"}]}])
        result = run_cli(self.root, "team", "deps", "--format", "json", env=path_with(bin_dir))
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual([{"id": done, "pr": "https://github.com/org/app/pull/9"}], payload["closed"])
        self.assertEqual([pending], payload["waiting"])
        self.assertEqual("closed", show(self.root, done)["status"])
        self.assertEqual("abc", show(self.root, done)["metadata"]["merge_commit"])

    def merged_pr(self, commit: str, track: int = 2) -> dict[str, str]:
        bin_dir = Path(self.tmp.name) / "bin"
        fake_cli(bin_dir, "gh", [{"argv": ["pr", "list"], "stdout": [
            {"url": "https://github.com/org/app/pull/9", "mergeCommit": {"oid": commit},
             "body": f"Plan: .planning/plans/p.md\nTracks: {track}\n"}]}])
        return path_with(bin_dir)

    def test_deps_for_bead_checks_ancestry_in_this_workspace(self):
        base = git(self.root, "rev-parse", "HEAD").strip()
        git(self.root, "commit", "-q", "--allow-empty", "-m", "merged")
        merged = git(self.root, "rev-parse", "HEAD").strip()
        work = create(self.root, "work", "area:backend")
        ext = create(self.root, "external: .planning/plans/p.md#2")
        bd(self.root, "dep", "add", work, ext)
        env = self.merged_pr(merged)
        self.assertEqual(0, run_cli(self.root, "team", "deps", env=env).returncode)
        self.assertEqual(0, run_cli(self.root, "team", "claim", work).returncode)
        result = run_cli(self.root, "team", "deps", "--bead", work, "--format", "json", env=env)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual([ext], json.loads(result.stdout)["ok"])
        git(self.root, "checkout", "-q", "--detach", base)
        result = run_cli(self.root, "team", "deps", "--bead", work, env=env)
        self.assertEqual(1, result.returncode)
        self.assertIn("fetch/rebase", result.stdout)
        self.assertIn(merged, result.stdout)

    def test_deps_for_bead_ignores_other_beads(self):
        a = create(self.root, "a")
        b = create(self.root, "b")
        ext = create(self.root, "external: .planning/plans/p.md#5")
        bd(self.root, "dep", "add", b, ext)
        result = run_cli(self.root, "team", "deps", "--bead", a)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(f"{a} has no external dependencies", result.stdout)
        result = run_cli(self.root, "team", "deps", "--bead", b)
        self.assertEqual(1, result.returncode)
        self.assertIn("has not merged; run team deps", result.stdout)

    def test_deps_keeps_placeholder_open_without_merge_commit(self):
        ext = create(self.root, "external: .planning/plans/p.md#2")
        result = run_cli(self.root, "team", "deps", env=self.merged_pr(""))
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn(f"unresolved {ext}: https://github.com/org/app/pull/9 merged without a merge commit", result.stdout)
        self.assertEqual("open", show(self.root, ext)["status"])

    def test_gitlab_merged_list_falls_back_to_squash_commit(self):
        from workflow_core.team_host import merged_with_text
        bin_dir = Path(self.tmp.name) / "bin"
        fake_cli(bin_dir, "glab", [{"argv": ["mr", "list"], "stdout": [
            {"web_url": "https://gitlab.corp.com/group/app/-/merge_requests/3", "merge_commit_sha": None,
             "squash_commit_sha": "def", "description": "Plan: p.md"}]}])
        with mock.patch.dict(os.environ, path_with(bin_dir)):
            self.assertEqual("def", merged_with_text("gitlab", "p.md", self.root)[0].merge_commit)

    def test_refresh_unblocks_ready_without_deadlock(self):
        work = create(self.root, "work", "area:backend")
        ext = create(self.root, "external: .planning/plans/p.md#2")
        bd(self.root, "dep", "add", work, ext)
        ready = lambda: {row["id"] for row in json.loads(run_cli(self.root, "team", "ready", "--format", "json").stdout)["ready"]}
        self.assertNotIn(work, ready())
        self.assertEqual(0, run_cli(self.root, "team", "deps", env=self.merged_pr("abc")).returncode)
        self.assertIn(work, ready())

    def test_sync_needs_a_remote(self):
        result = run_cli(self.root, "team", "sync")
        self.assertEqual(2, result.returncode)
        self.assertIn("team.beads_sync.remote is not set", result.stderr)


@unittest.skipUnless(HAS_BD and HAS_DOLT, "bd and dolt are required")
class TestTeamBeadsSync(unittest.TestCase):
    """Two members share Beads through a bare git repository used as the Dolt remote."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        remote = base / "beads.git"
        git(base, "init", "-q", "--bare", str(remote))
        seed = base / "seed"
        git(base, "clone", "-q", str(remote), str(seed))
        git(seed, "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-q", "--allow-empty", "-m", "init")
        git(seed, "push", "-q", "origin", "HEAD:main")
        self.url = f"git+file://{remote}"
        team = TEAM.format(host="github") + f"  beads_sync: {{remote: '{self.url}'}}\n"
        self.lead = make_team_repo(base / "lead", team=team)
        bd(self.lead, "init", "--prefix", "t", "-q")
        bd(self.lead, "dolt", "remote", "add", "origin", self.url)
        self.member = make_team_repo(base / "member", email="em@corp.com", team=team)
        self.bead = create(self.lead, "API", "area:backend")
        self.assertEqual(0, run_cli(self.lead, "team", "sync").returncode)
        bd(self.member, "init", "--prefix", "t", "-q", "--remote", self.url)

    def tearDown(self):
        self.tmp.cleanup()

    def test_member_sees_lead_beads_and_claim_is_shared(self):
        self.assertEqual("API", show(self.member, self.bead)["title"])
        result = run_cli(self.member, "team", "claim", self.bead)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(0, run_cli(self.lead, "team", "sync").returncode)
        self.assertEqual("em@corp.com", show(self.lead, self.bead)["assignee"])
        refused = run_cli(self.lead, "team", "claim", self.bead)
        self.assertEqual(1, refused.returncode)
        self.assertIn("already claimed by em@corp.com", refused.stdout)

    def test_lost_race_resets_local_beads_to_the_remote(self):
        team = team_for_repo(self.lead)
        member = team.member("binh@corp.com")
        bd(self.member, "update", self.bead, "--claim", actor="em@corp.com")
        bd(self.member, "dolt", "push")
        with mock.patch.object(team_beads, "sync", return_value={"status": "synced"}):
            with self.assertRaisesRegex(team_beads.SyncConflict, f"{self.bead} is held by em@corp.com"):
                team_beads.claim(self.lead, team, member, self.bead)
        self.assertEqual("em@corp.com", show(self.lead, self.bead)["assignee"])
        self.assertEqual(0, run_cli(self.lead, "team", "sync").returncode)


if __name__ == "__main__":
    unittest.main()

"""Team Beads: my ready work, claims, external placeholders, and Dolt sync through a git remote (real bd/dolt)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import TEAM, fake_cli, gh_pr, git, init_beads, make_team_repo, path_with, write  # noqa: E402
# One test per subcommand keeps the subprocess; the rest run gin in this process.
from team_fixtures import run_cli as run_cli_subprocess, run_cli_in_process as run_cli  # noqa: E402
from workflow_core import team_beads, worktrees  # noqa: E402
from workflow_core.team import TeamConfig, team_for_repo  # noqa: E402

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


def claim_meta(root: Path, bead: str, holder: str, expires_at: str) -> None:
    bd(root, "update", bead, "--set-metadata",
       f'claim={json.dumps({"holder": holder, "expires_at": expires_at})}')


@unittest.skipIf(os.name == "nt", "needs a POSIX pseudo-terminal (pty)")
@unittest.skipUnless(HAS_BD, "bd is not installed")
class TestBdHelperUnderATerminal(unittest.TestCase):
    """`bd init` waits on a terminal stdin, so the suite hung when run from a pseudo-terminal."""

    def test_bd_init_does_not_wait_on_a_terminal_stdin(self):
        import pty

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
        init_beads(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_ready_lists_mine_and_my_areas(self):
        mine = create(self.root, "mine")
        bd(self.root, "update", mine, "--assignee", "binh@corp.com")
        backend = create(self.root, "backend", "area:backend", "track:1")
        create(self.root, "frontend", "area:frontend")
        theirs = create(self.root, "theirs", "area:backend")
        bd(self.root, "update", theirs, "--assignee", "em@corp.com")
        rows = json.loads(run_cli_subprocess(self.root, "team", "ready", "--format", "json").stdout)["ready"]
        self.assertEqual({mine, backend}, {row["id"] for row in rows})

    def test_ready_holds_an_unshipped_external_dependency(self):
        free = create(self.root, "free", "area:backend")
        waits = create(self.root, "waits", "area:backend")
        bd(self.root, "dep", "add", waits, "external:nope:cap")
        rows = json.loads(run_cli(self.root, "team", "ready", "--format", "json").stdout)["ready"]
        self.assertEqual({free}, {row["id"] for row in rows})

    def test_claim_and_already_claimed(self):
        free = create(self.root, "free", "area:backend")
        result = run_cli_subprocess(self.root, "team", "claim", free)
        self.assertEqual(0, result.returncode, result.stderr)
        claimed = show(self.root, free)
        self.assertEqual(("binh@corp.com", "in_progress"), (claimed["assignee"], claimed["status"]))
        meta = team_beads.claim_of(claimed)
        self.assertEqual("binh@corp.com", meta["holder"])
        self.assertAlmostEqual(48, self.lease_hours(meta), delta=0.1)
        again = run_cli(self.root, "team", "claim", free, "--format", "json")
        self.assertEqual("renewed", json.loads(again.stdout)["status"])
        self.assertTrue(json.loads(again.stdout)["advisory"])
        self.assertIn("advisory: no Beads remote", run_cli(self.root, "team", "claim", free).stdout)
        held = create(self.root, "held", "area:backend")
        bd(self.root, "update", held, "--claim", actor="em@corp.com")
        claim_meta(self.root, held, "em@corp.com", "2999-01-01T00:00:00Z")
        refused = run_cli(self.root, "team", "claim", held)
        self.assertEqual(1, refused.returncode)
        self.assertIn("already claimed by em@corp.com until 2999-01-01T00:00:00Z", refused.stdout)

    def lease_hours(self, meta: dict) -> float:
        from datetime import datetime, timezone
        expires = datetime.strptime(meta["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return (expires - datetime.now(timezone.utc)).total_seconds() / 3600

    def test_claim_ttl_hours_sets_the_lease_length(self):
        config = self.root / ".agent-workflow/config.yaml"
        config.write_text(config.read_text() + "  claim_ttl_hours: 6\n", encoding="utf-8")
        bead = create(self.root, "short", "area:backend")
        self.assertEqual(0, run_cli(self.root, "team", "claim", bead).returncode)
        self.assertAlmostEqual(6, self.lease_hours(team_beads.claim_of(show(self.root, bead))), delta=0.1)

    def test_claim_refuses_an_area_the_member_may_not_own(self):
        frontend = create(self.root, "form", "area:frontend")
        refused = run_cli(self.root, "team", "claim", frontend)
        self.assertEqual(1, refused.returncode)
        self.assertIn("binh@corp.com may not own tracks in frontend", refused.stdout)

    def test_released_bead_is_ready_and_claimable_outside_its_areas(self):
        frontend = create(self.root, "form", "area:frontend", "released")
        listed = run_cli(self.root, "team", "ready", "--format", "json")
        self.assertEqual(0, listed.returncode)
        row = next(r for r in json.loads(listed.stdout)["ready"] if r["id"] == frontend)
        self.assertTrue(row["released"])
        claimed = run_cli(self.root, "team", "claim", frontend)
        self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
        issue = show(self.root, frontend)
        self.assertEqual("binh@corp.com", issue["assignee"])
        self.assertNotIn("released", issue.get("labels") or [])

    def test_expired_claim_is_listed_and_taken_over(self):
        held = create(self.root, "held", "area:backend")
        bd(self.root, "update", held, "--claim", actor="em@corp.com")
        claim_meta(self.root, held, "em@corp.com", "2000-01-01T00:00:00Z")
        legacy = create(self.root, "legacy", "area:backend")
        bd(self.root, "update", legacy, "--claim", actor="em@corp.com")
        rows = json.loads(run_cli(self.root, "team", "ready", "--format", "json").stdout)["ready"]
        self.assertEqual({held: "em@corp.com", legacy: "em@corp.com"},
                         {row["id"]: row.get("expired_claim") for row in rows if row.get("expired_claim")})
        self.assertIn("(expired claim: em@corp.com)", run_cli(self.root, "team", "ready").stdout)
        result = run_cli(self.root, "team", "claim", held)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        taken = show(self.root, held)
        self.assertEqual(("binh@corp.com", "in_progress"), (taken["assignee"], taken["status"]))
        self.assertIn("took over expired claim from em@corp.com", taken.get("notes", ""))
        self.assertEqual("binh@corp.com", team_beads.claim_of(taken)["holder"])

    def test_reassign_lead_takes_over_and_checks_eligibility(self):
        bead = create(self.root, "work", "area:backend")
        bd(self.root, "update", bead, "--claim", actor="em@corp.com")
        refused = run_cli_subprocess(self.root, "team", "reassign", bead, "chi@corp.com")
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

    def test_reassign_refuses_closed_and_unowned_unlabelled_beads_and_lead_takes_unassigned(self):
        closed = create(self.root, "done", "area:backend")
        bd(self.root, "close", closed)
        refused = run_cli(self.root, "team", "reassign", closed, "em@corp.com")
        self.assertEqual(1, refused.returncode)
        self.assertIn("is closed", refused.stdout)
        unlabelled = create(self.root, "orphan")
        refused = run_cli(self.root, "team", "reassign", unlabelled, "em@corp.com")
        self.assertEqual(1, refused.returncode)
        self.assertIn("an area lead", refused.stdout)
        free = create(self.root, "free", "area:backend")
        done = run_cli(self.root, "team", "reassign", free, "em@corp.com")
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        self.assertIn("reassigned nobody -> em@corp.com", show(self.root, free)["notes"])

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
        result = run_cli_subprocess(self.root, "team", "deps", "--format", "json", env=path_with(bin_dir))
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
        result = run_cli_subprocess(self.root, "team", "sync")
        self.assertEqual(2, result.returncode)
        self.assertIn("team.beads_sync.remote is not set", result.stderr)


@unittest.skipUnless(HAS_BD, "bd is not installed")
class TestTeamHandoff(unittest.TestCase):
    """The origin, the claimed bead, and the committed track branch are built once per class; each test copies them
    and checks the branch out in its own worktree (a copied linked worktree would still point at the template)."""

    @classmethod
    def setUpClass(cls):
        cls.template = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.template.cleanup)
        base = Path(cls.template.name)
        git(base, "init", "-q", "--bare", str(base / "origin.git"))
        root = make_team_repo(base / "repo")
        git(root, "remote", "set-url", "origin", str(base / "origin.git"))
        git(root, "commit", "-q", "--allow-empty", "-m", "base")
        git(root, "push", "-q", "origin", "main")
        init_beads(root)
        cls.bead = create(root, "API", "area:backend")
        claimed = run_cli(root, "team", "claim", cls.bead)
        if claimed.returncode != 0:
            raise AssertionError(f"team claim failed: {claimed.stdout}{claimed.stderr}")
        worktree = worktrees.create(root, cls.bead, "feat/api-t1")
        (worktree / "api.txt").write_text("v1", encoding="utf-8")
        git(worktree, "add", "api.txt")
        git(worktree, "commit", "-q", "-m", "api v1")
        worktrees.cleanup(root, cls.bead)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        shutil.copytree(self.template.name, base, dirs_exist_ok=True)
        self.origin = base / "origin.git"
        self.root = base / "repo"
        git(self.root, "remote", "set-url", "origin", str(self.origin))
        self.worktree = worktrees.checkout(self.root, self.bead, "feat/api-t1")

    def tearDown(self):
        self.tmp.cleanup()

    def remote_branches(self):
        return git(self.origin, "branch", "--list", "feat/api-t1").split()

    def test_handoff_refuses_a_dirty_worktree_and_changes_nothing(self):
        (self.worktree / "scratch.txt").write_text("x", encoding="utf-8")
        refused = run_cli(self.root, "team", "handoff", self.bead, "em@corp.com")
        self.assertEqual(1, refused.returncode)
        self.assertIn("scratch.txt", refused.stdout)
        self.assertEqual([], self.remote_branches())
        self.assertEqual("binh@corp.com", show(self.root, self.bead)["assignee"])

    def test_handoff_pushes_branch_records_metadata_and_reassigns(self):
        done = run_cli_subprocess(self.root, "team", "handoff", self.bead, "em@corp.com")
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        self.assertEqual(["feat/api-t1"], self.remote_branches())
        issue = show(self.root, self.bead)
        self.assertEqual("em@corp.com", issue["assignee"])
        handoff = team_beads.handoff_of(issue)
        self.assertEqual({"branch": "feat/api-t1", "from": "binh@corp.com", "to": "em@corp.com"},
                         {k: handoff[k] for k in ("branch", "from", "to")})
        self.assertEqual("em@corp.com", team_beads.claim_of(issue)["holder"])
        self.assertIn("next: gin team takeover", done.stderr)

    def test_handoff_release_reopens_and_labels_the_bead(self):
        done = run_cli(self.root, "team", "handoff", self.bead, "--release")
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        issue = show(self.root, self.bead)
        self.assertFalse(issue.get("assignee"))
        self.assertEqual("open", issue["status"])
        self.assertIn("released", issue["labels"])
        self.assertEqual({}, team_beads.claim_of(issue))
        self.assertIsNone(team_beads.handoff_of(issue)["to"])
        git(self.root, "config", "user.email", "chi@corp.com")
        listed = run_cli(self.root, "team", "ready", "--format", "json")
        self.assertIn(self.bead, [r["id"] for r in json.loads(listed.stdout)["ready"]])

    def test_handoff_refuses_missing_worktree_and_bad_arguments(self):
        other = create(self.root, "DB", "area:backend")
        self.assertEqual(0, run_cli(self.root, "team", "claim", other).returncode)
        missing = run_cli(self.root, "team", "handoff", other, "em@corp.com")
        self.assertEqual(1, missing.returncode)
        self.assertIn("no worktree for", missing.stdout)
        self.assertEqual(2, run_cli(self.root, "team", "handoff", self.bead).returncode)
        self.assertEqual(2, run_cli(self.root, "team", "handoff", self.bead, "em@corp.com", "--release").returncode)

    def test_handoff_rejected_push_leaves_the_bead_untouched(self):
        git(self.root, "remote", "set-url", "origin", str(Path(self.tmp.name) / "missing.git"))
        refused = run_cli(self.root, "team", "handoff", self.bead, "em@corp.com")
        self.assertEqual(1, refused.returncode)
        self.assertIn("git push of feat/api-t1 failed", refused.stdout)
        issue = show(self.root, self.bead)
        self.assertEqual("binh@corp.com", issue["assignee"])
        self.assertEqual({}, team_beads.handoff_of(issue))

    def test_handoff_refuses_a_non_git_worktree_and_a_broken_ledger(self):
        plain = Path(self.tmp.name) / "plain"
        plain.mkdir()
        refused = run_cli(self.root, "team", "handoff", self.bead, "em@corp.com", "--worktree", str(plain))
        self.assertEqual(1, refused.returncode)
        self.assertIn("is not a git worktree", refused.stdout)
        ledger = self.worktree / ".planning/reviews" / self.bead / "review.json"
        ledger.parent.mkdir(parents=True)
        ledger.write_text("{not json", encoding="utf-8")
        git(self.worktree, "add", "-A")
        git(self.worktree, "commit", "-q", "-m", "broken ledger")
        broken = run_cli(self.root, "team", "handoff", self.bead, "em@corp.com")
        self.assertEqual(1, broken.returncode)
        self.assertIn("cannot read review ledger", broken.stdout)
        self.assertEqual("binh@corp.com", show(self.root, self.bead)["assignee"])

    def test_takeover_checks_out_the_handed_off_branch_and_claims(self):
        git(self.worktree, "update-ref", f"refs/gin/review/{self.bead}", "HEAD")
        sha = git(self.worktree, "rev-parse", "HEAD").strip()
        self.assertEqual(0, run_cli(self.root, "team", "handoff", self.bead, "em@corp.com").returncode)
        worktrees.cleanup(self.root, self.bead)
        git(self.root, "branch", "-D", "feat/api-t1")
        git(self.root, "update-ref", "-d", f"refs/gin/review/{self.bead}")
        git(self.root, "config", "user.email", "em@corp.com")
        taken = run_cli_subprocess(self.root, "team", "takeover", self.bead, "--format", "json")
        self.assertEqual(0, taken.returncode, taken.stdout + taken.stderr)
        result = json.loads(taken.stdout)
        path = Path(result["worktree"])
        self.assertEqual(self.root / ".planning/worktrees" / self.bead, path)
        self.assertEqual("feat/api-t1", git(path, "rev-parse", "--abbrev-ref", "HEAD").strip())
        self.assertEqual("v1", (path / "api.txt").read_text(encoding="utf-8"))
        self.assertEqual("em@corp.com", show(self.root, self.bead)["assignee"])
        self.assertIn("next: gin team deps --bead", taken.stderr)
        self.assertEqual(sha, git(path, "rev-parse", "--verify", f"refs/gin/review/{self.bead}").strip())

    def test_takeover_refuses_worktree_cwd_missing_branch_and_existing_directory(self):
        shutil.copytree(self.root / ".agent-workflow", self.worktree / ".agent-workflow")
        inside = run_cli(self.worktree, "team", "takeover", self.bead)
        self.assertEqual(1, inside.returncode)
        self.assertIn("main checkout", inside.stdout)
        other = create(self.root, "DB", "area:backend")
        missing = run_cli(self.root, "team", "takeover", other)
        self.assertEqual(1, missing.returncode)
        self.assertIn("pass --branch", missing.stdout)
        bd(self.root, "update", other, "--set-metadata", 'handoff={"branch": "--upload-pack=touch /tmp/pwned"}')
        hostile = run_cli(self.root, "team", "takeover", other)
        self.assertEqual(1, hostile.returncode)
        self.assertIn("starts with '-'", hostile.stdout)
        self.assertFalse((self.root / ".planning/worktrees" / other).exists())
        git(self.worktree, "push", "-q", "-u", "origin", "feat/api-t1")
        existing = run_cli(self.root, "team", "takeover", self.bead, "--branch", "feat/api-t1")
        self.assertEqual(1, existing.returncode)
        self.assertIn("already exists", existing.stdout)

    def test_takeover_with_explicit_branch_when_no_metadata(self):
        git(self.worktree, "push", "-q", "-u", "origin", "feat/api-t1")
        worktrees.cleanup(self.root, self.bead)
        git(self.root, "branch", "-D", "feat/api-t1")
        taken = run_cli(self.root, "team", "takeover", self.bead, "--branch", "feat/api-t1")
        self.assertEqual(0, taken.returncode, taken.stdout + taken.stderr)
        self.assertTrue((self.root / ".planning/worktrees" / self.bead / "api.txt").is_file())

    def test_takeover_names_the_worktree_when_the_claim_is_refused(self):
        self.assertEqual(0, run_cli(self.root, "team", "handoff", self.bead, "em@corp.com").returncode)
        worktrees.cleanup(self.root, self.bead)
        git(self.root, "branch", "-D", "feat/api-t1")
        git(self.root, "config", "user.email", "chi@corp.com")
        refused = run_cli(self.root, "team", "takeover", self.bead)
        self.assertEqual(1, refused.returncode)
        self.assertIn("worktree left at", refused.stdout)
        self.assertIn(f"gin worktree cleanup {self.bead}", refused.stdout)
        self.assertTrue((self.root / ".planning/worktrees" / self.bead / "api.txt").is_file())


class TestDoltTimeout(unittest.TestCase):
    """bd dolt pull and push get a long timeout, and a timeout is a clear error, not a traceback."""

    def test_sync_and_push_give_dolt_the_long_timeout(self):
        done = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(team_beads, "tool", return_value="bd"), \
                mock.patch.object(team_beads.subprocess, "run", return_value=done) as run:
            team_beads.sync(Path("."))
            team_beads.push(Path("."), TeamConfig(beads_remote="x"))
        self.assertEqual([["bd", "dolt", "pull"], ["bd", "dolt", "push"], ["bd", "dolt", "push"]],
                         [call.args[0] for call in run.call_args_list])
        self.assertEqual({team_beads.DOLT_TIMEOUT}, {call.kwargs["timeout"] for call in run.call_args_list})
        self.assertGreaterEqual(team_beads.DOLT_TIMEOUT, 1000)

    def test_each_dolt_step_is_announced_on_stderr(self):
        done = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(team_beads, "tool", return_value="bd"), \
                mock.patch.object(team_beads.subprocess, "run", return_value=done), \
                mock.patch("sys.stderr", new_callable=__import__("io").StringIO) as err:
            team_beads.sync(Path("."))
        self.assertEqual(["bd dolt pull (up to 1000s)...", "bd dolt push (up to 1000s)..."], err.getvalue().splitlines())

    def test_a_timed_out_push_keeps_the_local_write(self):
        expired = subprocess.TimeoutExpired(["bd", "dolt", "push"], team_beads.DOLT_TIMEOUT)
        with mock.patch.object(team_beads, "tool", return_value="bd"), \
                mock.patch.object(team_beads.subprocess, "run", side_effect=expired):
            with self.assertRaisesRegex(team_beads.SyncConflict,
                                        r"push of t-1 failed; local Beads kept, run gin team sync \(bd dolt push timed out"):
                team_beads._push(Path("."), TeamConfig(beads_remote="x"), "t-1")

    def test_a_timeout_is_a_team_error_naming_the_command(self):
        expired = subprocess.TimeoutExpired(["bd", "dolt", "pull"], team_beads.DOLT_TIMEOUT)
        with mock.patch.object(team_beads, "tool", return_value="bd"), \
                mock.patch.object(team_beads.subprocess, "run", side_effect=expired):
            with self.assertRaisesRegex(team_beads.TeamError, r"bd dolt pull timed out after 1000s"):
                team_beads.sync(Path("."))


class TestPushWithoutReset(unittest.TestCase):
    """A rejected push retries through sync once; local Beads are never reset."""

    def test_req_016_rejected_push_raises_and_never_resets(self):
        rejected = subprocess.CompletedProcess([], 1, "", "rejected")
        with mock.patch.object(team_beads, "_bd", return_value=rejected):
            with self.assertRaisesRegex(team_beads.SyncConflict, "rejected"):
                team_beads.push(Path("."), TeamConfig(beads_remote="x"))
        self.assertFalse(hasattr(team_beads, "reset_to_remote"))

    def test_req_016_push_without_remote_calls_nothing(self):
        with mock.patch.object(team_beads, "_bd") as run:
            team_beads.push(Path("."), TeamConfig())
            team_beads._push(Path("."), TeamConfig(), "t-1")
        run.assert_not_called()

    def test_rejected_push_syncs_once_and_succeeds(self):
        rejected = subprocess.CompletedProcess([], 1, "", "rejected")
        with mock.patch.object(team_beads, "_bd", return_value=rejected) as run, \
                mock.patch.object(team_beads, "sync", return_value={"status": "synced"}) as synced:
            team_beads._push(Path("."), TeamConfig(beads_remote="x"), "t-1")
        synced.assert_called_once()
        self.assertEqual([["dolt", "push"]], [call.args[1] for call in run.call_args_list])

    def test_rejected_push_then_conflict_keeps_local_beads(self):
        rejected = subprocess.CompletedProcess([], 1, "", "rejected")
        with mock.patch.object(team_beads, "_bd", return_value=rejected), \
                mock.patch.object(team_beads, "sync", side_effect=team_beads.SyncConflict("bd dolt pull: conflict")):
            with self.assertRaisesRegex(team_beads.SyncConflict,
                                        "push rejected for t-1; local Beads kept, run gin team sync"):
                team_beads._push(Path("."), TeamConfig(beads_remote="x"), "t-1")


@unittest.skipUnless(HAS_BD and HAS_DOLT, "bd and dolt are required")
class TestTeamBeadsSync(unittest.TestCase):
    """Two members share Beads through a bare git repository used as the Dolt remote. The remote, lead, and member are
    built once per class; each test copies them and points both Dolt remotes and the team config at its own copy."""

    @classmethod
    def setUpClass(cls):
        cls.template = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.template.cleanup)
        base = Path(cls.template.name)
        remote = base / "beads.git"
        git(base, "init", "-q", "--bare", str(remote))
        seed = base / "seed"
        git(base, "clone", "-q", str(remote), str(seed))
        git(seed, "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-q", "--allow-empty", "-m", "init")
        git(seed, "push", "-q", "origin", "HEAD:main")
        cls.template_url = f"git+file://{remote}"
        team = TEAM.format(host="github") + f"  beads_sync: {{remote: '{cls.template_url}'}}\n"
        lead = make_team_repo(base / "lead", team=team)
        bd(lead, "init", "--prefix", "t", "-q")
        bd(lead, "dolt", "remote", "add", "origin", cls.template_url)
        member = make_team_repo(base / "member", email="em@corp.com", team=team)
        cls.bead = create(lead, "API", "area:backend")
        synced = run_cli_subprocess(lead, "team", "sync")
        if synced.returncode != 0:
            raise AssertionError(f"team sync failed: {synced.stdout}{synced.stderr}")
        bd(member, "init", "--prefix", "t", "-q", "--remote", cls.template_url)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        shutil.copytree(self.template.name, base, dirs_exist_ok=True)
        self.url = f"git+file://{base / 'beads.git'}"
        self.lead, self.member = base / "lead", base / "member"
        for root in (self.lead, self.member):
            bd(root, "dolt", "remote", "remove", "origin")
            bd(root, "dolt", "remote", "add", "origin", self.url)
            config = root / ".agent-workflow/config.yaml"
            config.write_text(config.read_text(encoding="utf-8").replace(self.template_url, self.url), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_member_sees_lead_beads_and_claim_is_shared(self):
        self.assertEqual("API", show(self.member, self.bead)["title"])
        result = run_cli(self.member, "team", "claim", self.bead, "--format", "json")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertFalse(json.loads(result.stdout)["advisory"])
        self.assertEqual(0, run_cli(self.lead, "team", "sync").returncode)
        self.assertEqual("em@corp.com", show(self.lead, self.bead)["assignee"])
        refused = run_cli(self.lead, "team", "claim", self.bead)
        self.assertEqual(1, refused.returncode)
        self.assertIn("already claimed by em@corp.com", refused.stdout)

    def test_lost_race_keeps_local_beads(self):
        team = team_for_repo(self.lead)
        member = team.member("binh@corp.com")
        bd(self.member, "update", self.bead, "--claim", actor="em@corp.com")
        bd(self.member, "dolt", "push")
        with mock.patch.object(team_beads, "sync", side_effect=[{"status": "synced"},
                                                                team_beads.SyncConflict("bd dolt pull: conflict")]):
            with self.assertRaisesRegex(team_beads.SyncConflict, f"push rejected for {self.bead}; local Beads kept"):
                team_beads.claim(self.lead, team, member, self.bead)
        self.assertEqual("binh@corp.com", show(self.lead, self.bead)["assignee"])


class TestTeamBeadsReadyFakeBd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_team_repo(Path(self.tmp.name) / "repo", email="an@corp.com")
        self.bin = Path(self.tmp.name) / "bin"
        self.team = team_for_repo(self.root)
        self.ba = self.team.member("an@corp.com")
        self.lead = self.team.member("binh@corp.com")

    def tearDown(self):
        self.tmp.cleanup()

    def test_ready_with_prep_tasks_sorting_and_exclusions(self):
        rules = [
            {"argv": ["ready", "--explain"], "stdout": {"ready": []}},
            {"argv": ["ready", "--exclude-type", "milestone"], "stdout": [
                {"id": "ready-2", "title": "Ready 2", "assignee": "an@corp.com", "labels": [], "priority": 2},
                {"id": "ready-1", "title": "Ready 1", "assignee": "an@corp.com", "labels": [], "priority": 1},
            ]},
            {"argv": ["blocked"], "stdout": [
                {"id": "prep-ba", "title": "BA Prep", "blocked_by": ["epic-1"], "labels": ["prep", "prep:capture"],
                 "priority": 1, "assignee": "an@corp.com"},
                {"id": "prep-blocked", "title": "Blocked Prep", "blocked_by": ["epic-1"],
                 "labels": ["prep", "prep:spike"], "priority": 0, "assignee": "an@corp.com"},
                {"id": "prep-other", "title": "Other Prep", "blocked_by": ["epic-1"],
                 "labels": ["prep", "prep:mockup"], "priority": 0, "assignee": "binh@corp.com"},
            ]},
            {"argv": ["list", "--label", "prep", "--status", "open", "--limit", "0"], "stdout": [
                {"id": "prep-ba", "title": "BA Prep", "parent": "epic-1", "labels": ["prep", "prep:capture"],
                 "priority": 1, "assignee": "an@corp.com",
                 "dependencies": [{"depends_on_id": "epic-1", "type": "parent-child"}]},
                {"id": "prep-blocked", "title": "Blocked Prep", "parent": "epic-1", "labels": ["prep", "prep:spike"],
                 "priority": 0, "assignee": "an@corp.com",
                 "dependencies": [{"depends_on_id": "epic-1", "type": "parent-child"},
                                  {"depends_on_id": "other", "type": "blocks"}]},
                {"id": "prep-other", "title": "Other Prep", "parent": "epic-1", "labels": ["prep", "prep:mockup"],
                 "priority": 0, "assignee": "binh@corp.com",
                 "dependencies": [{"depends_on_id": "epic-1", "type": "parent-child"}]},
            ]},
            {"argv": ["list", "--status", "in_progress"], "stdout": [
                {"id": "exp-2", "title": "Expired 2", "assignee": "em@corp.com", "labels": ["area:backend"],
                 "priority": 2, "metadata": {"claim": {"expires_at": "2000-01-01T00:00:00Z"}}},
                {"id": "exp-1", "title": "Expired 1", "assignee": "em@corp.com", "labels": ["area:backend"],
                 "priority": 1, "metadata": {"claim": {"expires_at": "2000-01-01T00:00:00Z"}}},
                {"id": "exp-prep", "title": "Expired Prep", "assignee": "em@corp.com",
                 "labels": ["area:backend", "prep", "prep:spike"], "priority": 0,
                 "metadata": {"claim": {"expires_at": "2000-01-01T00:00:00Z"}}},
            ]},
        ]
        fake_cli(self.bin, "bd", rules)

        with mock.patch.dict(os.environ, path_with(self.bin)):
            # 1. BA sees prep-ba (held by epic-1), but not prep-blocked or prep-other
            # Also ready rows sorted by priority then id: ready-1 (p1), prep-ba (p1), ready-2 (p2)
            # prep-ba and ready-1 both have priority 1; prep-ba < ready-1
            rows = team_beads.ready(self.root, self.team, self.ba)
            self.assertEqual(["prep-ba", "ready-1", "ready-2"], [r["id"] for r in rows])
            for r in rows:
                self.assertIn("priority", r)
                self.assertIsNotNone(r["priority"])

            # 2. exclude=["prep"] drops prep rows from ready group
            rows_no_prep = team_beads.ready(self.root, self.team, self.ba, exclude=["prep"])
            self.assertEqual(["ready-1", "ready-2"], [r["id"] for r in rows_no_prep])

            # 3. For lead (in area:backend): sees expired claims after ready rows, sorted by priority then id
            lead_rows = team_beads.ready(self.root, self.team, self.lead)
            # Expired claim rows: exp-prep (p0), exp-1 (p1), exp-2 (p2)
            self.assertEqual(["exp-prep", "exp-1", "exp-2"], [r["id"] for r in lead_rows if "expired_claim" in r])

            # 4. exclude=["prep"] drops prep rows from expired-claim group too
            lead_no_prep = team_beads.ready(self.root, self.team, self.lead, exclude=["prep"])
            self.assertEqual(["exp-1", "exp-2"], [r["id"] for r in lead_no_prep if "expired_claim" in r])

            # 5. CLI invocation passes exclude-label
            cli_res = run_cli_subprocess(self.root, "team", "ready", "--exclude-label", "prep", "--format", "json",
                                         env=path_with(self.bin))
            self.assertEqual(0, cli_res.returncode, cli_res.stderr)
            cli_data = json.loads(cli_res.stdout)["ready"]
            self.assertEqual(["ready-1", "ready-2"], [r["id"] for r in cli_data])

    def test_failing_bd_blocked_raises_team_error(self):
        rules = [
            {"argv": ["ready", "--explain"], "stdout": {"ready": []}},
            {"argv": ["ready", "--exclude-type", "milestone"], "stdout": []},
            {"argv": ["blocked"], "exit": 1, "stderr": "database disk image is malformed\n"},
        ]
        fake_cli(self.bin, "bd", rules)
        with mock.patch.dict(os.environ, path_with(self.bin)):
            with self.assertRaises(team_beads.TeamError) as cm:
                team_beads.ready(self.root, self.team, self.ba)
            self.assertIn("bd blocked failed: database disk image is malformed", str(cm.exception))

    def test_failing_bd_list_raises_team_error(self):
        rules = [
            {"argv": ["ready", "--explain"], "stdout": {"ready": []}},
            {"argv": ["ready", "--exclude-type", "milestone"], "stdout": []},
            {"argv": ["blocked"], "stdout": []},
            {"argv": ["list", "--label", "prep", "--status", "open", "--limit", "0"], "exit": 1,
             "stderr": "database disk image is malformed\n"},
        ]
        fake_cli(self.bin, "bd", rules)
        with mock.patch.dict(os.environ, path_with(self.bin)):
            with self.assertRaises(team_beads.TeamError):
                team_beads.ready(self.root, self.team, self.ba)

    def test_exclude_label_comma_separated_drops_both_labels(self):
        rules = [
            {"argv": ["ready", "--explain"], "stdout": {"ready": []}},
            {"argv": ["ready", "--exclude-type", "milestone"], "stdout": [
                {"id": "a", "title": "A", "assignee": "an@corp.com", "labels": ["x"], "priority": 1},
                {"id": "b", "title": "B", "assignee": "an@corp.com", "labels": ["y"], "priority": 1},
                {"id": "c", "title": "C", "assignee": "an@corp.com", "labels": [], "priority": 1},
            ]},
            {"argv": ["blocked"], "stdout": []},
            {"argv": ["list", "--label", "prep", "--status", "open", "--limit", "0"], "stdout": []},
            {"argv": ["list", "--status", "in_progress"], "stdout": []},
        ]
        fake_cli(self.bin, "bd", rules)
        with mock.patch.dict(os.environ, path_with(self.bin)):
            cli_res = run_cli_subprocess(self.root, "team", "ready", "--exclude-label", "x,y", "--format", "json",
                                         env=path_with(self.bin))
            self.assertEqual(0, cli_res.returncode, cli_res.stderr)
            self.assertEqual(["c"], [r["id"] for r in json.loads(cli_res.stdout)["ready"]])

    def test_project_with_no_prep_tasks_returns_same_rows_ordered_by_priority(self):
        rules = [
            {"argv": ["ready", "--explain"], "stdout": {"ready": []}},
            {"argv": ["ready", "--exclude-type", "milestone"], "stdout": [
                {"id": "t-b", "title": "B", "assignee": "an@corp.com", "labels": [], "priority": 2},
                {"id": "t-c", "title": "C", "assignee": "an@corp.com", "labels": [], "priority": 1},
                {"id": "t-a", "title": "A", "assignee": "an@corp.com", "labels": []},  # priority None -> 99
            ]},
            {"argv": ["blocked"], "stdout": []},
            {"argv": ["list", "--label", "prep", "--status", "open", "--limit", "0"], "stdout": []},
            {"argv": ["list", "--status", "in_progress"], "stdout": []},
        ]
        fake_cli(self.bin, "bd", rules)
        with mock.patch.dict(os.environ, path_with(self.bin)):
            rows = team_beads.ready(self.root, self.team, self.ba)
            self.assertEqual(["t-c", "t-b", "t-a"], [r["id"] for r in rows])
            self.assertIsNone(rows[2]["priority"])
            self.assertEqual(1, rows[0]["priority"])
            self.assertEqual(2, rows[1]["priority"])


@unittest.skipUnless(HAS_BD, "bd is not installed")
class TestTeamClaimWorktree(unittest.TestCase):
    """R3, R4, US-1, US-2: claim creates the track worktree in the bead's `Repo:`; takeover works in that child."""

    PLAN = "Plan: .planning/plans/2026-11-14-x.md, Track 2\nRepo: services/order-api"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.child_bare = self.base / "remotes/order-api.git"
        git(self.base, "init", "-q", "--bare", "-b", "main", str(self.child_bare))
        self.scratch = self.base / "scratch"
        self.scratch.mkdir()
        git(self.scratch, "init", "-q", "-b", "main")
        git(self.scratch, "config", "user.email", "binh@corp.com")
        git(self.scratch, "config", "user.name", "T")
        self.child_head = self.child_commit("README.md", "order-api\n")
        parent_bare = self.base / "remotes/parent.git"
        git(self.base, "init", "-q", "--bare", "-b", "main", str(parent_bare))
        self.root = make_team_repo(self.base / "ws", extra=(
            "workspace:\n  repos:\n    - path: services/order-api\n"
            f"      url: file://{self.child_bare}\n      default_branch: main\n      shape: backend\n"
            "    - path: libs/legacy\n      url: file:///nowhere/legacy.git\n      frozen: true\n"
            "    - path: .beads\n      url: file:///nowhere/beads.git\n      shape: beads\n"))
        git(self.root, "remote", "set-url", "origin", str(parent_bare))
        git(self.root, "commit", "-q", "--allow-empty", "-m", "parent base")
        git(self.root, "push", "-q", "origin", "main")
        init_beads(self.root)
        self.child_dir = self.root / "services/order-api"
        git(self.root, "clone", "-q", str(self.child_bare), str(self.child_dir))
        git(self.child_dir, "config", "user.email", "binh@corp.com")
        git(self.child_dir, "config", "user.name", "T")
        self.target = self.root / ".planning/worktrees"

    def child_commit(self, name: str, text: str) -> str:
        """Commit `name` on the child's origin `main` from a scratch clone; returns the new sha."""
        (self.scratch / name).write_text(text, encoding="utf-8")
        git(self.scratch, "add", name)
        git(self.scratch, "commit", "-q", "-m", name)
        git(self.scratch, "push", "-q", str(self.child_bare), "main")
        return git(self.scratch, "rev-parse", "HEAD").strip()

    def track_bead(self, title: str, description: str = PLAN) -> str:
        bead = create(self.root, title, "area:backend")
        bd(self.root, "update", bead, "--description", description)
        return bead

    def test_claim_creates_the_child_worktree_from_the_fetched_default_branch(self):
        # origin/main of the child moves after the clone: claim must fetch it and branch from the new tip
        tip = self.child_commit("api.txt", "v2\n")
        bead = self.track_bead("Order track")
        claimed = run_cli(self.root, "team", "claim", bead)
        self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
        target = self.target / bead
        self.assertIn(f"claimed {bead} at {target} on feat/x-t2", claimed.stdout)
        self.assertEqual("feat/x-t2", git(target, "rev-parse", "--abbrev-ref", "HEAD").strip())
        self.assertEqual(tip, git(target, "rev-parse", "HEAD").strip())
        self.assertNotEqual(self.child_head, tip)
        common = Path(git(target, "rev-parse", "--path-format=absolute", "--git-common-dir").strip())
        self.assertEqual((self.child_dir / ".git").resolve(), common.resolve())
        self.assertEqual("binh@corp.com", show(self.root, bead)["assignee"])

    def test_claiming_again_renews_the_lease_and_keeps_the_worktree(self):
        bead = self.track_bead("Order track")
        first = run_cli(self.root, "team", "claim", bead, "--format", "json")
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        self.assertTrue(json.loads(first.stdout)["created"])
        marker = self.target / bead / "work.txt"
        marker.write_text("in progress", encoding="utf-8")
        again = run_cli(self.root, "team", "claim", bead, "--format", "json")
        self.assertEqual(0, again.returncode, again.stdout + again.stderr)
        data = json.loads(again.stdout)
        self.assertEqual({"status": "renewed", "worktree": str(self.target / bead), "branch": "feat/x-t2",
                          "created": False}, {key: data[key] for key in ("status", "worktree", "branch", "created")})
        self.assertEqual("in progress", marker.read_text(encoding="utf-8"))
        text = run_cli(self.root, "team", "claim", bead)
        self.assertIn(f"renewed {bead} at {self.target / bead} on feat/x-t2", text.stdout)

    def test_uncloned_child_refuses_claim_and_takeover_without_a_lease(self):
        shutil.rmtree(self.child_dir)
        bead = self.track_bead("Uncloned")
        refused = run_cli(self.root, "team", "claim", bead)
        self.assertEqual(1, refused.returncode, refused.stdout + refused.stderr)
        self.assertIn("gin workspace clone services/order-api", refused.stdout)
        self.assertFalse(show(self.root, bead).get("assignee"))
        taken = run_cli(self.root, "team", "takeover", bead, "--branch", "feat/x-t2")
        self.assertEqual(1, taken.returncode, taken.stdout + taken.stderr)
        self.assertIn("gin workspace clone services/order-api", taken.stdout)
        self.assertFalse(show(self.root, bead).get("assignee"))

    def test_repo_outside_the_workspace_is_refused_without_a_lease(self):
        bead = self.track_bead("Elsewhere", "Plan: .planning/plans/2026-11-14-x.md, Track 2\nRepo: ../evil")
        refused = run_cli(self.root, "team", "claim", bead)
        self.assertEqual(1, refused.returncode, refused.stdout + refused.stderr)
        self.assertIn("Repo: ../evil is not in workspace.repos", refused.stdout)
        self.assertFalse(show(self.root, bead).get("assignee"))
        self.assertFalse(self.target.exists())

    def test_fetch_failure_keeps_the_lease_and_says_to_claim_again(self):
        git(self.child_dir, "remote", "set-url", "origin", str(self.base / "missing.git"))
        bead = self.track_bead("Fetch fail")
        failed = run_cli(self.root, "team", "claim", bead)
        self.assertEqual(1, failed.returncode, failed.stdout + failed.stderr)
        self.assertIn(f"the claim is kept; run gin team claim {bead} again", failed.stdout)
        self.assertEqual("binh@corp.com", show(self.root, bead)["assignee"])
        self.assertFalse((self.target / bead).exists())

    def test_bead_without_a_plan_line_gets_the_lease_only(self):
        bead = create(self.root, "No plan", "area:backend")
        claimed = run_cli(self.root, "team", "claim", bead, "--format", "json")
        self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
        data = json.loads(claimed.stdout)
        self.assertEqual({"status", "bead", "lane", "beads", "assignee", "expires_at", "advisory"}, set(data))
        self.assertEqual((None, [bead]), (data["lane"], data["beads"]))
        self.assertFalse(self.target.exists())

    def test_single_repository_team_creates_the_worktree_in_the_parent(self):
        origin = self.base / "remotes/single.git"
        git(self.base, "init", "-q", "--bare", "-b", "main", str(origin))
        root = make_team_repo(self.base / "single")
        git(root, "remote", "set-url", "origin", str(origin))
        git(root, "commit", "-q", "--allow-empty", "-m", "base")
        git(root, "push", "-q", "origin", "main")
        # origin/HEAD names trunk, a branch ahead of main: the default branch comes from it
        git(root, "commit", "-q", "--allow-empty", "-m", "trunk only")
        git(root, "push", "-q", "origin", "HEAD:trunk")
        base = git(root, "rev-parse", "HEAD").strip()
        git(root, "reset", "-q", "--hard", "HEAD~1")
        git(root, "remote", "set-head", "origin", "trunk")
        init_beads(root)
        bead = create(root, "Single", "area:backend")
        bd(root, "update", bead, "--description", "Plan: .planning/plans/2026-11-14-y.md, Track 1")
        claimed = run_cli(root, "team", "claim", bead)
        self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
        target = root / ".planning/worktrees" / bead
        self.assertEqual("feat/y-t1", git(target, "rev-parse", "--abbrev-ref", "HEAD").strip())
        self.assertEqual(base, git(target, "rev-parse", "HEAD").strip())

    def test_takeover_of_a_child_track_checks_it_out_in_the_child(self):
        bead = self.track_bead("Takeover")
        claimed = run_cli(self.root, "team", "claim", bead)
        self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
        target = self.target / bead
        (target / "work.txt").write_text("handed off", encoding="utf-8")
        git(target, "add", "work.txt")
        git(target, "commit", "-q", "-m", "work")
        handed = run_cli(self.root, "team", "handoff", bead, "em@corp.com")
        self.assertEqual(0, handed.returncode, handed.stdout + handed.stderr)
        # em's machine: no worktree, no local branch, no remote-tracking ref for it
        worktrees.cleanup(self.child_dir, bead, self.root)
        git(self.child_dir, "branch", "-D", "feat/x-t2")
        git(self.child_dir, "update-ref", "-d", "refs/remotes/origin/feat/x-t2")
        git(self.root, "config", "user.email", "em@corp.com")
        taken = run_cli(self.root, "team", "takeover", bead, "--format", "json")
        self.assertEqual(0, taken.returncode, taken.stdout + taken.stderr)
        result = json.loads(taken.stdout)
        self.assertEqual((str(target), "feat/x-t2", True),
                         (result["worktree"], result["branch"], result["created"]))
        self.assertEqual("handed off", (target / "work.txt").read_text(encoding="utf-8"))
        common = Path(git(target, "rev-parse", "--path-format=absolute", "--git-common-dir").strip())
        self.assertEqual((self.child_dir / ".git").resolve(), common.resolve())
        self.assertEqual("em@corp.com", show(self.root, bead)["assignee"])

    def test_claim_after_a_worktree_cleanup_reuses_the_local_track_branch(self):
        bead = self.track_bead("Again")
        claimed = run_cli(self.root, "team", "claim", bead)
        self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
        target = self.target / bead
        (target / "work.txt").write_text("kept", encoding="utf-8")
        git(target, "add", "work.txt")
        git(target, "commit", "-q", "-m", "work")
        work = git(target, "rev-parse", "HEAD").strip()
        worktrees.cleanup(self.child_dir, bead, self.root)
        again = run_cli(self.root, "team", "claim", bead, "--format", "json")
        self.assertEqual(0, again.returncode, again.stdout + again.stderr)
        data = json.loads(again.stdout)
        self.assertEqual(("feat/x-t2", True), (data["branch"], data["created"]))
        self.assertEqual("feat/x-t2", git(target, "rev-parse", "--abbrev-ref", "HEAD").strip())
        self.assertEqual(work, git(target, "rev-parse", "HEAD").strip())

    def test_claim_checks_out_a_track_branch_found_only_on_the_child_origin(self):
        # a previous owner pushed feat/x-t2 to the child's origin; this machine has never seen it
        git(self.scratch, "checkout", "-q", "-b", "feat/x-t2")
        (self.scratch / "previous.txt").write_text("previous owner", encoding="utf-8")
        git(self.scratch, "add", "previous.txt")
        git(self.scratch, "commit", "-q", "-m", "previous owner")
        git(self.scratch, "push", "-q", str(self.child_bare), "feat/x-t2")
        previous = git(self.scratch, "rev-parse", "HEAD").strip()
        bead = self.track_bead("Released track")
        claimed = run_cli(self.root, "team", "claim", bead, "--format", "json")
        self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
        target = self.target / bead
        self.assertEqual("feat/x-t2", git(target, "rev-parse", "--abbrev-ref", "HEAD").strip())
        self.assertEqual(previous, git(target, "rev-parse", "HEAD").strip())

    def test_track_branch_name_git_refuses_is_refused_before_the_lease(self):
        bead = self.track_bead("Spaced", "Plan: .planning/plans/2026-11-14-a b.md, Track 1\nRepo: services/order-api")
        refused = run_cli(self.root, "team", "claim", bead)
        self.assertEqual(1, refused.returncode, refused.stdout + refused.stderr)
        self.assertIn("feat/a b-t1", refused.stdout)
        self.assertNotIn("the claim is kept", refused.stdout)
        self.assertFalse(show(self.root, bead).get("assignee"))
        self.assertFalse(self.target.exists())

    def test_frozen_and_beads_entries_are_refused_before_the_lease(self):
        for repo, reason in (("libs/legacy", "Repo: libs/legacy is frozen"),
                             (".beads", "Repo: .beads is the beads repository")):
            with self.subTest(repo=repo):
                bead = self.track_bead(repo, f"Plan: .planning/plans/2026-11-14-x.md, Track 2\nRepo: {repo}")
                refused = run_cli(self.root, "team", "claim", bead)
                self.assertEqual(1, refused.returncode, refused.stdout + refused.stderr)
                self.assertIn(reason, refused.stdout)
                self.assertFalse(show(self.root, bead).get("assignee"))

    def test_a_directory_at_the_target_that_is_no_worktree_of_the_child_is_refused(self):
        bead = self.track_bead("Stray")
        stray = self.target / bead
        stray.mkdir(parents=True)
        plain = run_cli(self.root, "team", "claim", bead)
        self.assertEqual(1, plain.returncode, plain.stdout + plain.stderr)
        self.assertIn(f"{stray} is not a worktree of {self.child_dir}; remove it", plain.stdout)
        stray.rmdir()
        worktrees.create(self.root, bead, "feat/other")  # a worktree of the parent, not of the child
        parent = run_cli(self.root, "team", "claim", bead)
        self.assertEqual(1, parent.returncode, parent.stdout + parent.stderr)
        self.assertIn(f"{stray} is not a worktree of {self.child_dir}; remove it", parent.stdout)

    def test_handoff_pushes_the_parent_ledger_branch_and_takeover_pulls_it_first(self):
        """R4: the child track's ledger is committed on the parent's feat/x; handoff pushes that branch and the
        review ref the ledger names; takeover pulls the branch before it reads the ledger."""
        parent_bare = self.base / "remotes/parent.git"
        git(self.root, "checkout", "-q", "-b", "feat/x")
        git(self.root, "push", "-q", "-u", "origin", "feat/x")
        bead = self.track_bead("Ledger sync")
        claimed = run_cli(self.root, "team", "claim", bead)
        self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
        target = self.target / bead
        (target / "work.txt").write_text("handed off", encoding="utf-8")
        git(target, "add", "work.txt")
        git(target, "commit", "-q", "-m", "work")
        # not the default refs/gin/review/<bead>: only a ledger read in the parent names this ref
        ref = f"refs/gin/review/{bead}-c2"
        git(target, "update-ref", ref, "HEAD")
        sha = git(target, "rev-parse", "HEAD").strip()
        ledger = f".planning/reviews/{bead}/review.json"
        write(self.root, ledger, json.dumps({"repositories": [{"checkpoint_ref": ref}]}))
        git(self.root, "add", ledger)
        git(self.root, "commit", "-q", "-m", "ledger")
        ledger_commit = git(self.root, "rev-parse", "HEAD").strip()
        handed = run_cli(self.root, "team", "handoff", bead, "em@corp.com")
        self.assertEqual(0, handed.returncode, handed.stdout + handed.stderr)
        self.assertEqual(ledger_commit, git(parent_bare, "rev-parse", "feat/x").strip())
        self.assertEqual(sha, git(self.child_bare, "rev-parse", ref).strip())
        # em's machine: behind the parent's origin, without the track worktree, branch, or review ref
        git(self.root, "reset", "-q", "--hard", "HEAD~1")
        worktrees.cleanup(self.child_dir, bead, self.root)
        git(self.child_dir, "branch", "-D", "feat/x-t2")
        git(self.child_dir, "update-ref", "-d", "refs/remotes/origin/feat/x-t2")
        git(self.child_dir, "update-ref", "-d", ref)
        git(self.root, "config", "user.email", "em@corp.com")
        stray = write(self.root, ledger, "{}")  # an untracked copy the pull would overwrite: refused before checkout
        refused = run_cli(self.root, "team", "takeover", bead)
        self.assertEqual(1, refused.returncode, refused.stdout + refused.stderr)
        self.assertIn("git pull --rebase of feat/x", refused.stdout)
        self.assertFalse(target.exists())
        stray.unlink()
        taken = run_cli(self.root, "team", "takeover", bead)
        self.assertEqual(0, taken.returncode, taken.stdout + taken.stderr)
        self.assertEqual(ledger_commit, git(self.root, "rev-parse", "HEAD").strip())
        self.assertEqual(sha, git(self.child_dir, "rev-parse", ref).strip())
        self.assertEqual("handed off", (target / "work.txt").read_text(encoding="utf-8"))

    def test_handoff_pushes_only_a_parent_feat_branch_and_a_rejected_push_keeps_the_bead(self):
        parent_bare = self.base / "remotes/parent.git"
        bead = self.track_bead("Parent branch")
        claimed = run_cli(self.root, "team", "claim", bead)
        self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
        # the parent's main with a commit its upstream lacks: a handoff never pushes it
        git(self.root, "push", "-q", "-u", "origin", "main")
        git(self.root, "commit", "-q", "--allow-empty", "-m", "ledger on main")
        on_main = run_cli(self.root, "team", "handoff", bead, "em@corp.com")
        self.assertEqual(1, on_main.returncode, on_main.stdout + on_main.stderr)
        self.assertIn(f"main in {self.root} has commits that are not pushed; commit the review ledger on the "
                      "parent's feat/<topic>", on_main.stdout)
        self.assertNotEqual(git(self.root, "rev-parse", "HEAD"), git(parent_bare, "rev-parse", "main"))
        self.assertEqual("binh@corp.com", show(self.root, bead)["assignee"])
        # a feat/ branch that was never pushed is pushed with an upstream
        git(self.root, "checkout", "-q", "-b", "feat/x")
        git(self.root, "remote", "set-url", "origin", str(self.base / "missing.git"))
        refused = run_cli(self.root, "team", "handoff", bead, "em@corp.com")
        self.assertEqual(1, refused.returncode, refused.stdout + refused.stderr)
        self.assertIn(f"git push of feat/x in {self.root} failed", refused.stdout)
        self.assertEqual("binh@corp.com", show(self.root, bead)["assignee"])
        git(self.root, "remote", "set-url", "origin", str(parent_bare))
        handed = run_cli(self.root, "team", "handoff", bead, "em@corp.com")
        self.assertEqual(0, handed.returncode, handed.stdout + handed.stderr)
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), git(parent_bare, "rev-parse", "feat/x"))
        self.assertEqual("origin/feat/x", git(self.root, "rev-parse", "--abbrev-ref", "@{u}").strip())
        self.assertEqual("em@corp.com", show(self.root, bead)["assignee"])


@unittest.skipUnless(HAS_BD, "bd is not installed")
class TestTeamLaneClaim(unittest.TestCase):
    """R3, R6, R7, US-1, US-4: claim takes every open track of the lane on one branch and one worktree."""

    PLAN = ".planning/plans/2026-11-19-shop.md"
    URL = "https://github.com/org/app/pull/9"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.origin = self.base / "remotes/shop.git"
        git(self.base, "init", "-q", "--bare", "-b", "main", str(self.origin))
        self.root = make_team_repo(self.base / "shop")
        git(self.root, "remote", "set-url", "origin", str(self.origin))
        git(self.root, "commit", "-q", "--allow-empty", "-m", "base")
        git(self.root, "push", "-q", "origin", "main")
        init_beads(self.root)
        self.epic = json.loads(bd(self.root, "create", "Shop", "-t", "epic", "--json"))["id"]
        self.bin = self.base / "bin"

    def track(self, number: int, lane: str | None = "be", area: str = "backend") -> str:
        text = f"Plan: {self.PLAN}, Track {number}" + (f"\nLane: {lane}" if lane else "")
        return json.loads(bd(self.root, "create", f"Track {number}", "--parent", self.epic, "-l", f"area:{area}",
                             "--description", text, "--json"))["id"]

    def claim(self, bead: str, rules: list[dict] | None = None):
        if rules is None:
            return run_cli(self.root, "team", "claim", bead, "--format", "json")
        fake_cli(self.bin, "gh", rules)
        return run_cli(self.root, "team", "claim", bead, "--format", "json", env=path_with(self.bin))

    def commit(self, worktree: Path, name: str) -> str:
        (worktree / name).write_text(name, encoding="utf-8")
        git(worktree, "add", name)
        git(worktree, "commit", "-q", "-m", name)
        return git(worktree, "rev-parse", "HEAD").strip()

    def test_claim_takes_every_open_track_of_the_lane(self):
        t1, t2, t3, t4 = self.track(1), self.track(2), self.track(3), self.track(4, "fe", "frontend")
        claimed = self.claim(t1)
        self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
        data = json.loads(claimed.stdout)
        self.assertEqual(("be", [t1, t2, t3], "feat/shop-be", True),
                         (data["lane"], data["beads"], data["branch"], data["created"]))
        self.assertTrue(data["worktree"].endswith(f".planning/worktrees/{self.epic}-be"), data["worktree"])
        self.assertEqual("in_progress", show(self.root, t1)["status"])
        expires = team_beads.claim_of(show(self.root, t1))["expires_at"]
        for other in (t2, t3):
            row = show(self.root, other)
            self.assertEqual(("open", "binh@corp.com", expires),
                             (row["status"], row.get("assignee"), team_beads.claim_of(row)["expires_at"]))
        self.assertFalse(show(self.root, t4).get("assignee"))

    def test_claiming_the_next_track_keeps_the_lane_worktree(self):
        t1, t2, _t3 = self.track(1), self.track(2), self.track(3)
        first = json.loads(self.claim(t1).stdout)
        work = self.commit(Path(first["worktree"]), "one.txt")
        bd(self.root, "close", t1)
        claimed = self.claim(t2, [{"argv": ["pr", "list"], "stdout": []}])
        self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
        data = json.loads(claimed.stdout)
        self.assertEqual((False, first["worktree"], [t2, _t3]), (data["created"], data["worktree"], data["beads"]))
        self.assertIn(work, git(Path(data["worktree"]), "log", "--format=%H"))
        self.assertEqual("in_progress", show(self.root, t2)["status"])

    def test_a_foreign_lease_on_a_track_of_the_lane_refuses_without_change(self):
        t1, _t2, t3 = self.track(1), self.track(2), self.track(3)
        bd(self.root, "update", t3, "--claim", actor="em@corp.com")
        claim_meta(self.root, t3, "em@corp.com", "2999-01-01T00:00:00Z")
        refused = self.claim(t1)
        self.assertEqual(1, refused.returncode, refused.stdout + refused.stderr)
        self.assertIn(f"lane be is claimed by em@corp.com until 2999-01-01T00:00:00Z ({t3})", refused.stdout)
        row = show(self.root, t1)
        self.assertFalse(row.get("assignee"))
        self.assertNotIn("claim", row.get("metadata") or {})

    def test_an_expired_lease_on_a_track_of_the_lane_is_taken_over(self):
        t1, _t2, t3 = self.track(1), self.track(2), self.track(3)
        bd(self.root, "update", t3, "--claim", actor="em@corp.com")
        claim_meta(self.root, t3, "em@corp.com", "2000-01-01T00:00:00Z")
        claimed = self.claim(t1)
        self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
        row = show(self.root, t3)
        self.assertEqual("binh@corp.com", row.get("assignee"))
        self.assertIn("took over expired claim from em@corp.com", row.get("notes") or "")

    def test_an_area_the_member_may_not_own_in_the_lane_refuses_without_change(self):
        t1, t2 = self.track(1), self.track(2, area="frontend")
        refused = self.claim(t1)
        self.assertEqual(1, refused.returncode, refused.stdout + refused.stderr)
        self.assertIn("may not own tracks in frontend", refused.stdout)
        self.assertFalse(show(self.root, t1).get("assignee"))
        self.assertFalse(show(self.root, t2).get("assignee"))

    def test_a_track_without_a_lane_line_is_its_own_lane(self):
        first, second = self.track(1, None), self.track(2, None)
        claimed = self.claim(first)
        self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
        data = json.loads(claimed.stdout)
        self.assertEqual(("t1", [first], "feat/shop-t1"), (data["lane"], data["beads"], data["branch"]))
        self.assertTrue(data["worktree"].endswith(f".planning/worktrees/{first}"), data["worktree"])
        self.assertFalse(show(self.root, second).get("assignee"))

    def test_a_foreign_lease_on_a_track_without_a_lane_keeps_the_earlier_message(self):
        first = self.track(1, None)
        bd(self.root, "update", first, "--claim", actor="em@corp.com")
        claim_meta(self.root, first, "em@corp.com", "2999-01-01T00:00:00Z")
        refused = self.claim(first)
        self.assertEqual(1, refused.returncode, refused.stdout + refused.stderr)
        self.assertIn(f"{first} is already claimed by em@corp.com until", refused.stdout)

    def delivered_lane(self, after_merge: bool) -> tuple[str, Path, list[dict]]:
        """Claim t1, commit and push the lane branch, close t1, move origin/main; the fake host says the lane's
        pull request merged at the pushed head. Returns (t2, worktree, gh rules)."""
        t1, t2 = self.track(1), self.track(2)
        worktree = Path(json.loads(self.claim(t1).stdout)["worktree"])
        head = self.commit(worktree, "one.txt")
        git(worktree, "push", "-q", "-u", "origin", "feat/shop-be")
        if after_merge:
            self.commit(worktree, "late.txt")
        bd(self.root, "close", t1)
        git(self.root, "commit", "-q", "--allow-empty", "-m", "merged upstream")
        git(self.root, "push", "-q", "origin", "main")
        rules = [{"argv": ["pr", "list", "--head", "feat/shop-be"],
                  "stdout": [{"url": self.URL, "state": "MERGED", "mergeCommit": {"oid": "m" * 40}}]},
                 {"argv": ["pr", "view", self.URL], "stdout": gh_pr(self.URL, state="MERGED", head=head)}]
        return t2, worktree, rules

    def test_a_merged_lane_branch_restarts_from_the_default_branch(self):
        t2, worktree, rules = self.delivered_lane(after_merge=False)
        claimed = self.claim(t2, rules)
        self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
        self.assertEqual(git(self.root, "rev-parse", "main").strip(), git(worktree, "rev-parse", "HEAD").strip())
        self.assertEqual("feat/shop-be", git(worktree, "rev-parse", "--abbrev-ref", "HEAD").strip())
        self.assertIn("restarted from origin/main", json.loads(claimed.stdout)["note"])

    def test_commits_after_the_merged_head_keep_the_branch(self):
        t2, worktree, rules = self.delivered_lane(after_merge=True)
        before = git(worktree, "rev-parse", "HEAD").strip()
        claimed = self.claim(t2, rules)
        self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
        self.assertEqual(before, git(worktree, "rev-parse", "HEAD").strip())
        self.assertIn("has commits after its merged pull request", json.loads(claimed.stdout)["note"])

    def test_an_unreachable_host_keeps_the_branch_and_says_so(self):
        t2, worktree, _rules = self.delivered_lane(after_merge=False)
        before = git(worktree, "rev-parse", "HEAD").strip()
        claimed = self.claim(t2, [{"argv": ["pr", "list"], "exit": 1, "stderr": "offline"}])
        self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
        self.assertEqual(before, git(worktree, "rev-parse", "HEAD").strip())
        self.assertTrue(json.loads(claimed.stdout)["note"].startswith("cannot ask the host"))


if __name__ == "__main__":
    unittest.main()



@unittest.skipUnless(HAS_BD, "bd is not installed")
class TestTeamDepsWorkspaceChild(unittest.TestCase):
    """R5, R6, US-3: `team deps` searches the child that owns the blocking track and checks ancestry there."""

    PLAN_FILE = ".planning/plans/p.md"
    BODY = "Plan: .planning/plans/p.md\nTracks: 2\n"
    child_commit = TestTeamClaimWorktree.child_commit

    def setUp(self):
        TestTeamClaimWorktree.setUp(self)
        write(self.root, self.PLAN_FILE, "# P\n\n### Track 1: parent\n- **Files**:\n  - a\n\n"
                                         "### Track 2: child\n- **Repo**: services/order-api\n- **Files**:\n  - b\n")
        self.ext = create(self.root, f"external: {self.PLAN_FILE}#2")
        self.work = create(self.root, "work", "area:backend")
        bd(self.root, "update", self.work, "--description", TestTeamClaimWorktree.PLAN)
        bd(self.root, "dep", "add", self.work, self.ext)
        self.bin = self.base / "bin"

    def gh(self, commit: str, parent_commit: str = "") -> dict[str, str]:
        """A `gh` that lists the merged pull requests of the child (track 2) in the child directory, and of the
        parent (track 1) in the parent directory when `parent_commit` is given."""
        self.bin.mkdir(exist_ok=True)
        child = [{"url": "https://github.com/org/api/pull/4", "mergeCommit": {"oid": commit}, "body": self.BODY}]
        parent = [{"url": "https://github.com/org/app/pull/5", "mergeCommit": {"oid": parent_commit},
                   "body": "Plan: .planning/plans/p.md\nTracks: 1\n"}] if parent_commit else []
        script = self.bin / "gh"
        script.write_text(f"#!{sys.executable}\nimport json, os, sys\n"
                          f"rows = {{{str(self.child_dir)!r}: {child!r}, {str(self.root)!r}: {parent!r}}}\n"
                          "sys.stdout.write(json.dumps(rows.get(os.getcwd(), [])))\n", encoding="utf-8")
        script.chmod(0o755)
        return path_with(self.bin)

    def run_from(self, cwd: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        import contextlib
        import io
        from workflow_core import cli, executables

        out, err = io.StringIO(), io.StringIO()
        executables.clear_cache()
        with mock.patch.dict(os.environ, env or {}), contextlib.chdir(cwd), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main([*args, "--repository", str(self.root)])
        return subprocess.CompletedProcess(list(args), code, out.getvalue(), err.getvalue())

    def test_deps_closes_the_placeholder_from_the_child_pull_request(self):
        merged = self.child_commit("api.txt", "v2\n")
        result = run_cli(self.root, "team", "deps", "--format", "json", env=self.gh(merged))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual([{"id": self.ext, "pr": "https://github.com/org/api/pull/4"}], payload["closed"])
        self.assertEqual({}, payload["reasons"])
        metadata = show(self.root, self.ext)["metadata"]
        self.assertEqual((merged, "services/order-api"), (metadata["merge_commit"], metadata["repo"]))

    def test_uncloned_child_leaves_the_placeholder_waiting_with_a_reason(self):
        shutil.rmtree(self.child_dir)
        result = run_cli(self.root, "team", "deps", "--format", "json", env=self.gh("abc"))
        payload = json.loads(result.stdout)
        self.assertEqual(([self.ext], []), (payload["waiting"], payload["closed"]))
        self.assertIn("gin workspace clone services/order-api", payload["reasons"][self.ext])
        text = run_cli(self.root, "team", "deps", env=self.gh("abc"))
        self.assertIn(f"waiting {self.ext} (", text.stdout)
        self.assertIn("gin workspace clone services/order-api", text.stdout)
        self.assertEqual("open", show(self.root, self.ext)["status"])

    def test_missing_plan_file_says_to_pull_the_merged_plan(self):
        (self.root / self.PLAN_FILE).unlink()
        payload = json.loads(run_cli(self.root, "team", "deps", "--format", "json", env=self.gh("abc")).stdout)
        self.assertEqual([self.ext], payload["waiting"])
        self.assertIn(f"{self.PLAN_FILE} is not in this checkout; pull the merged plan", payload["reasons"][self.ext])

    def close_with(self, commit: str) -> None:
        self.assertEqual(0, run_cli(self.root, "team", "deps", env=self.gh(commit)).returncode)
        self.assertEqual("closed", show(self.root, self.ext)["status"])

    def test_bead_check_from_the_child_worktree_uses_that_repository(self):
        merged = self.child_commit("api.txt", "v2\n")
        self.close_with(merged)
        self.assertEqual(0, run_cli(self.root, "team", "claim", self.work).returncode)
        worktree = self.target / self.work
        later = self.child_commit("more.txt", "v3\n")
        self.assertEqual(0, self.run_from(worktree, "team", "deps", "--bead", self.work).returncode)
        bd(self.root, "update", self.ext, "--set-metadata", f"merge_commit={later}")
        result = self.run_from(worktree, "team", "deps", "--bead", self.work)
        self.assertEqual(1, result.returncode)
        self.assertIn("fetch/rebase", result.stdout)
        self.assertIn(later, result.stdout)

    def test_bead_check_from_the_parent_uses_origin_of_the_child(self):
        merged = self.child_commit("api.txt", "v2\n")
        self.close_with(merged)
        result = run_cli(self.root, "team", "deps", "--bead", self.work)
        self.assertEqual(1, result.returncode)
        self.assertIn(f"run git -C {self.child_dir} fetch origin", result.stdout)
        self.assertIn("origin/main", result.stdout)
        git(self.child_dir, "fetch", "-q", "origin")
        result = run_cli(self.root, "team", "deps", "--bead", self.work, "--format", "json")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual([self.ext], json.loads(result.stdout)["ok"])

    def placeholder(self, title: str, commit: str, repo: str | None) -> str:
        """A closed placeholder blocking `self.work`, as an older or a current gin would have left it."""
        bead = create(self.root, title)
        bd(self.root, "update", bead, "--set-metadata", f"merge_commit={commit}")
        if repo is not None:
            bd(self.root, "update", bead, "--set-metadata", f"repo={repo}")
        bd(self.root, "dep", "add", self.work, bead)
        bd(self.root, "close", bead)
        return bead

    def verdict(self, cwd: Path, bead: str) -> tuple[str, str]:
        result = self.run_from(cwd, "team", "deps", "--bead", self.work, "--format", "json")
        payload = json.loads(result.stdout)
        if bead in payload["ok"]:
            return "ok", ""
        return "missing", next(row["reason"] for row in payload["missing"] if row["id"] == bead)

    def claimed_worktree(self) -> Path:
        self.close_with(self.child_commit("api.txt", "v2\n"))
        self.assertEqual(0, run_cli(self.root, "team", "claim", self.work).returncode)
        return self.target / self.work

    def test_placeholder_without_repo_checks_head_of_the_current_repository(self):
        worktree = self.claimed_worktree()
        have = git(worktree, "rev-parse", "HEAD").strip()
        old = self.placeholder("external: old#1", have, None)
        self.assertEqual(("ok", ""), self.verdict(worktree, old))
        later = self.child_commit("more.txt", "v3\n")
        missing = self.placeholder("external: old#2", later, None)
        self.assertIn("fetch/rebase", self.verdict(worktree, missing)[1])

    def test_parent_placeholder_checks_head_in_the_parent_and_origin_from_a_child(self):
        worktree = self.claimed_worktree()
        pushed = git(self.root, "rev-parse", "HEAD").strip()
        git(self.root, "commit", "-q", "--allow-empty", "-m", "unpushed")
        local = git(self.root, "rev-parse", "HEAD").strip()
        on_origin = self.placeholder("external: p#1", pushed, ".")
        only_local = self.placeholder("external: p#2", local, ".")
        self.assertEqual(("ok", ""), self.verdict(self.root, on_origin))
        self.assertEqual(("ok", ""), self.verdict(self.root, only_local))
        self.assertEqual(("ok", ""), self.verdict(worktree, on_origin))
        status, reason = self.verdict(worktree, only_local)
        self.assertEqual(("missing", f"{local} is not on origin/main of {self.root}; run git -C {self.root} fetch origin"),
                         (status, reason))

    def test_deps_records_dot_for_a_parent_track_in_a_workspace(self):
        parent_commit = git(self.root, "rev-parse", "HEAD").strip()
        parent = create(self.root, f"external: {self.PLAN_FILE}#1")
        result = run_cli(self.root, "team", "deps", "--format", "json", env=self.gh("c" * 40, parent_commit))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(".", show(self.root, parent)["metadata"]["repo"])

    def test_missing_origin_branch_is_named_instead_of_asking_for_a_fetch(self):
        worktree = self.claimed_worktree()
        commit = git(self.root, "rev-parse", "HEAD").strip()
        git(self.root, "update-ref", "-d", "refs/remotes/origin/main")
        parent = self.placeholder("external: p#3", commit, ".")
        self.assertEqual(("missing", f"origin/main does not exist in {self.root}; "
                                     f"run git -C {self.root} remote set-head origin -a"), self.verdict(worktree, parent))

    def test_track_missing_from_the_plan_waits_with_a_reason(self):
        lost = create(self.root, f"external: {self.PLAN_FILE}#9")
        payload = json.loads(run_cli(self.root, "team", "deps", "--format", "json", env=self.gh("abc")).stdout)
        self.assertIn(lost, payload["waiting"])
        self.assertEqual(f"track 9 is not in {self.PLAN_FILE}", payload["reasons"][lost])

    def test_each_placeholder_is_handled_and_none_aborts_the_others(self):
        config = self.root / ".agent-workflow/config.yaml"
        config.write_text(config.read_text(encoding="utf-8").replace(
            "    - path: libs/legacy", "    - path: services/billing\n      url: file:///nowhere/billing.git\n"
            "      shape: backend\n    - path: libs/legacy"), encoding="utf-8")
        plan = self.root / self.PLAN_FILE
        plan.write_text(plan.read_text(encoding="utf-8") + "\n### Track 3: billing\n- **Repo**: services/billing\n", encoding="utf-8")
        parent = create(self.root, f"external: {self.PLAN_FILE}#1")
        uncloned = create(self.root, f"external: {self.PLAN_FILE}#3")
        merged = self.child_commit("api.txt", "v2\n")
        parent_commit = git(self.root, "rev-parse", "HEAD").strip()
        payload = json.loads(run_cli(self.root, "team", "deps", "--format", "json",
                                     env=self.gh(merged, parent_commit)).stdout)
        self.assertEqual({parent, self.ext}, {row["id"] for row in payload["closed"]})
        self.assertEqual([uncloned], payload["waiting"])
        self.assertIn("gin workspace clone services/billing", payload["reasons"][uncloned])


@unittest.skipUnless(HAS_BD, "bd is not installed")
class TestTeamDepsWaitingReasons(unittest.TestCase):
    """R5: placeholders that cannot be resolved wait with a reason; one fixture serves the class (nothing closes)."""

    PLAN_FILE = ".planning/plans/w.md"

    @classmethod
    def setUpClass(cls):
        cls.fixture = TestTeamClaimWorktree("test_claim_creates_the_child_worktree_from_the_fetched_default_branch")
        cls.fixture.setUp()
        cls.root = cls.fixture.root
        write(cls.root, cls.PLAN_FILE, "### Track 1: frozen\n- **Repo**: libs/legacy\n\n"
                                       "### Track 2: elsewhere\n- **Repo**: ../evil\n")

    @classmethod
    def tearDownClass(cls):
        cls.fixture.tmp.cleanup()

    def waiting(self, title: str) -> str:
        bead = create(self.root, title)
        payload = json.loads(run_cli(self.root, "team", "deps", "--format", "json").stdout)
        self.assertIn(bead, payload["waiting"])
        return payload["reasons"][bead]

    def test_a_frozen_child_waits_with_its_reason(self):
        self.assertEqual("Repo: libs/legacy is frozen", self.waiting(f"external: {self.PLAN_FILE}#1"))

    def test_a_repo_outside_the_workspace_waits_with_its_reason(self):
        self.assertEqual("Repo: ../evil is not in workspace.repos", self.waiting(f"external: {self.PLAN_FILE}#2"))

    def test_a_plan_outside_the_root_is_not_read(self):
        outside = self.root.parent / "x.md"
        outside.write_text("### Track 1: x\n- **Repo**: services/order-api\n", encoding="utf-8")
        reason = self.waiting("external: ../x.md#1")
        self.assertEqual("../x.md is not in this checkout; pull the merged plan", reason)

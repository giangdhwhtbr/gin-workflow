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

from team_fixtures import TEAM, fake_cli, git, init_beads, make_team_repo, path_with, run_cli  # noqa: E402
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
        rows = json.loads(run_cli(self.root, "team", "ready", "--format", "json").stdout)["ready"]
        self.assertEqual({mine, backend}, {row["id"] for row in rows})

    def test_ready_holds_an_unshipped_external_dependency(self):
        free = create(self.root, "free", "area:backend")
        waits = create(self.root, "waits", "area:backend")
        bd(self.root, "dep", "add", waits, "external:nope:cap")
        rows = json.loads(run_cli(self.root, "team", "ready", "--format", "json").stdout)["ready"]
        self.assertEqual({free}, {row["id"] for row in rows})

    def test_claim_and_already_claimed(self):
        free = create(self.root, "free", "area:backend")
        result = run_cli(self.root, "team", "claim", free)
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
        done = run_cli(self.root, "team", "handoff", self.bead, "em@corp.com")
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
        taken = run_cli(self.root, "team", "takeover", self.bead, "--format", "json")
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
        synced = run_cli(lead, "team", "sync")
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
            cli_res = run_cli(self.root, "team", "ready", "--exclude-label", "prep", "--format", "json",
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
            cli_res = run_cli(self.root, "team", "ready", "--exclude-label", "x,y", "--format", "json",
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


if __name__ == "__main__":
    unittest.main()

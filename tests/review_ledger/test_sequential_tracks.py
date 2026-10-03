"""gin-workflow-6h2: validate approved ledgers of sequential tracks that share one branch."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../plugins/gin-workflow/src/scripts"))

LEDGER = os.path.join(SCRIPTS, "review-ledger.py")
REVIEWER = "reviewer:other:model"


class SequentialTracks(unittest.TestCase):
    """Track A is approved at commit A; track B then changes the branch and is approved at commit B."""

    def setUp(self):
        self.repo = tempfile.mkdtemp()
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "T"]):
            self.git(*args)
        self.write("src/a.py", "a = 1\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").strip()

    def tearDown(self):
        shutil.rmtree(self.repo)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, text=True).stdout

    def write(self, relative, text):
        path = os.path.join(self.repo, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(text)

    def cli(self, *args):
        return subprocess.run([sys.executable, LEDGER, *args], cwd=self.repo, capture_output=True, text=True)

    def ok(self, *args):
        result = self.cli(*args)
        if result.returncode != 0:
            self.fail(f"review-ledger {' '.join(args)} failed: {result.stdout}{result.stderr}")
        return result.stdout

    def commit(self, relative, text, message):
        self.write(relative, text)
        self.git("add", ".")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD").strip()

    def approve_track(self, bead, base):
        self.ok("init", "--bead-id", bead, "--repo-id", "r", "--repo-path", ".",
                "--review-ref", f"refs/gin/review/{bead}", "--base-sha", base, "--actor-id", "w1")
        self.ok("checkpoint", "--bead-id", bead, "--repo-id", "r", "--commit-msg", "cp", "--actor-id", "w1")
        self.ok("transition-requested", "--bead-id", bead, "--to", "review-requested", "--actor-id", "w1")
        lease = self.ok("start-review", "--bead-id", bead, "--actor-role", "reviewer",
                        "--actor-id", REVIEWER).strip().split()[-1].rstrip(".")
        self.ok("approve", "--bead-id", bead, "--actor-role", "reviewer", "--actor-id", REVIEWER, "--lease-id", lease)

    def two_tracks(self):
        commit_a = self.commit("src/a.py", "a = 2\n", "track A")
        self.approve_track("bead-a", self.base)
        commit_b = self.commit("src/b.py", "b = 1\n", "track B")
        self.approve_track("bead-b", commit_a)
        return commit_a, commit_b

    def test_earlier_track_fails_at_head_but_passes_in_history(self):
        commit_a, _ = self.two_tracks()
        self.assertNotEqual(0, self.cli("validate", "--bead-id", "bead-a").returncode)
        result = self.cli("validate", "--bead-id", "bead-a", "--in-history")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(commit_a, result.stdout)

    def test_latest_track_passes_both_ways(self):
        _, commit_b = self.two_tracks()
        self.ok("validate", "--bead-id", "bead-b")
        self.assertIn(commit_b, self.ok("validate", "--bead-id", "bead-b", "--in-history"))

    def test_in_history_survives_a_merge_into_another_branch(self):
        commit_a, _ = self.two_tracks()
        feature = self.git("branch", "--show-current").strip()
        self.git("checkout", "-qb", "main-line", self.base)
        self.commit("README.md", "x\n", "unrelated")
        self.git("merge", "-q", "--no-edit", feature)
        self.assertIn(commit_a, self.ok("validate", "--bead-id", "bead-a", "--in-history"))

    def test_in_history_fails_when_reviewed_source_never_reached_the_branch(self):
        self.write("src/a.py", "a = 99\n")
        self.approve_track("bead-a", self.base)
        self.commit("src/a.py", "a = 3\n", "different change")
        result = self.cli("validate", "--bead-id", "bead-a", "--in-history")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("no commit", result.stderr)

    def test_in_history_fails_when_base_is_not_an_ancestor(self):
        self.two_tracks()
        self.git("checkout", "-q", "--orphan", "rewritten")
        self.git("commit", "-qm", "squashed")
        result = self.cli("validate", "--bead-id", "bead-a", "--in-history")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("not an ancestor", result.stderr)


if __name__ == "__main__":
    unittest.main()

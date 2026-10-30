"""gin-workflow-50lr: review refs never prompt for credentials, push for every repo, and are deleted on origin."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../plugins/gin-workflow/src/scripts"))
sys.path.insert(0, SCRIPTS)
LEDGER = os.path.join(SCRIPTS, "review-ledger.py")

from review_ledger.cleanup import cleanup_review_ledgers  # noqa: E402

BEAD = "bead-a"
REF = f"refs/gin/review/{BEAD}"


def run(cwd, *cmd, env=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)


def git(cwd, *args):
    result = run(cwd, "git", *args)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def new_repo():
    path = tempfile.mkdtemp()
    for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "T"]):
        git(path, *args)
    with open(os.path.join(path, "a.py"), "w", encoding="utf-8") as stream:
        stream.write("a = 1\n")
    git(path, "add", ".")
    git(path, "commit", "-qm", "base")
    return path


def make_ledger(repo):
    """Init a ledger and take its checkpoint, which creates REF locally."""
    for args in (
        ("init", "--bead-id", BEAD, "--repo-id", "r", "--repo-path", ".", "--review-ref", REF, "--actor-id", "w1"),
        ("checkpoint", "--bead-id", BEAD, "--repo-id", "r", "--commit-msg", "cp", "--actor-id", "w1"),
    ):
        result = run(repo, sys.executable, LEDGER, *args)
        assert result.returncode == 0, result.stdout + result.stderr


class Unauthorized(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="x"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


class NoCredentialPrompt(unittest.TestCase):
    def test_fetch_of_a_missing_review_base_fails_instead_of_prompting(self):
        server = HTTPServer(("127.0.0.1", 0), Unauthorized)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        source, clone = new_repo(), tempfile.mkdtemp()
        try:
            make_ledger(source)
            # The clone has the ledger but not the review base, as after a squash merge.
            shutil.copytree(os.path.join(source, ".planning"), os.path.join(clone, ".planning"))
            git(clone, "init", "-q")
            git(clone, "config", "user.email", "t@example.com")
            git(clone, "config", "user.name", "T")
            git(clone, "commit", "-q", "--allow-empty", "-m", "other")
            git(clone, "remote", "add", "origin", f"http://127.0.0.1:{server.server_port}/repo.git")
            env = {k: v for k, v in os.environ.items() if k not in ("GIT_ASKPASS", "SSH_ASKPASS", "GIT_TERMINAL_PROMPT")}
            env.update(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
            result = run(clone, sys.executable, LEDGER, "validate", "--bead-id", BEAD, "--in-history", env=env)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("terminal prompts disabled", result.stderr)
        finally:
            server.shutdown()
            server.server_close()
            shutil.rmtree(source)
            shutil.rmtree(clone)


class Origin(unittest.TestCase):
    def setUp(self):
        self.repo = new_repo()
        self.origin = tempfile.mkdtemp()
        git(self.origin, "init", "-q", "--bare")
        git(self.repo, "remote", "add", "origin", self.origin)

    def tearDown(self):
        shutil.rmtree(self.repo)
        shutil.rmtree(self.origin)

    def remote_refs(self):
        return git(self.origin, "for-each-ref", "--format=%(refname)", "refs/gin/review/").split()

    def push_ref(self, ref=REF):
        git(self.repo, "update-ref", ref, "HEAD")
        git(self.repo, "push", "-q", "origin", f"{ref}:{ref}")


class PushRefs(Origin):
    def test_push_refs_force_pushes_the_ledger_ref(self):
        make_ledger(self.repo)
        result = run(self.repo, sys.executable, LEDGER, "push-refs", "--bead-id", BEAD)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(REF, result.stdout)
        self.assertEqual([REF], self.remote_refs())
        # A retaken checkpoint rewrites the ref; the next push must still succeed.
        git(self.repo, "update-ref", REF, git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(0, run(self.repo, sys.executable, LEDGER, "push-refs", "--bead-id", BEAD).returncode)

    def test_push_refs_failure_names_the_repository_and_ref(self):
        make_ledger(self.repo)
        git(self.repo, "remote", "set-url", "origin", os.path.join(self.origin, "missing"))
        result = run(self.repo, sys.executable, LEDGER, "push-refs", "--bead-id", BEAD)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("'r'", result.stderr)
        self.assertIn(REF, result.stderr)


@patch("review_ledger.cleanup._query_beads_status", return_value=("closed", "bead status is closed"))
class CleanupOnOrigin(Origin):
    def test_cleanup_deletes_the_ref_on_origin(self, _beads):
        make_ledger(self.repo)
        run(self.repo, sys.executable, LEDGER, "push-refs", "--bead-id", BEAD)
        result = cleanup_review_ledgers(Path(self.repo), bead_id=BEAD)
        self.assertEqual([REF], result["cleaned"][0]["remote_refs"])
        self.assertNotIn("remote_error", result)
        self.assertEqual([], self.remote_refs())

    def test_all_closed_cleans_a_ref_only_on_origin(self, _beads):
        self.push_ref()
        git(self.repo, "update-ref", "-d", REF)
        result = cleanup_review_ledgers(Path(self.repo), all_closed=True)
        self.assertEqual([REF], result["cleaned"][0]["remote_refs"])
        self.assertEqual([], self.remote_refs())

    def test_dry_run_keeps_the_ref_on_origin(self, _beads):
        self.push_ref()
        result = cleanup_review_ledgers(Path(self.repo), bead_id=BEAD, dry_run=True)
        self.assertEqual([REF], result["cleaned"][0]["remote_refs"])
        self.assertEqual([REF], self.remote_refs())

    def test_unreachable_origin_still_cleans_locally(self, _beads):
        self.push_ref()
        git(self.repo, "remote", "set-url", "origin", os.path.join(self.origin, "missing"))
        result = cleanup_review_ledgers(Path(self.repo), bead_id=BEAD)
        self.assertTrue(result["remote_error"])
        self.assertEqual([REF], result["cleaned"][0]["refs"])
        self.assertEqual("", git(self.repo, "for-each-ref", "refs/gin/review/"))

    def test_rejected_remote_deletes_report_every_error(self, _beads):
        other = "refs/gin/review/bead-b"
        self.push_ref()
        self.push_ref(other)
        hook = os.path.join(self.origin, "hooks", "pre-receive")
        with open(hook, "w", encoding="utf-8") as stream:
            stream.write("#!/bin/sh\nexit 1\n")
        os.chmod(hook, 0o755)
        result = cleanup_review_ledgers(Path(self.repo), all_closed=True)
        self.assertEqual(2, len(result["cleaned"]))
        self.assertEqual(2, result["remote_error"].count("; ") + 1)
        self.assertEqual(sorted([REF, other]), sorted(self.remote_refs()))

    def test_bead_id_without_ledger_keeps_remote_error(self, _beads):
        git(self.repo, "remote", "set-url", "origin", os.path.join(self.origin, "missing"))
        result = cleanup_review_ledgers(Path(self.repo), bead_id="nothing")
        self.assertEqual("No review directory found", result["skipped"][0]["reason"])
        self.assertTrue(result["remote_error"])

    def test_no_origin_reports_no_remote_refs_and_no_error(self, _beads):
        git(self.repo, "remote", "remove", "origin")
        git(self.repo, "update-ref", REF, "HEAD")
        result = cleanup_review_ledgers(Path(self.repo), bead_id=BEAD)
        self.assertEqual([], result["cleaned"][0]["remote_refs"])
        self.assertNotIn("remote_error", result)


if __name__ == "__main__":
    unittest.main()

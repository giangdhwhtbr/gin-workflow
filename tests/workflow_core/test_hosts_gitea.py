"""Gitea host adapter through a fake `gt`: PR mapping, self-hosted instances, doctor checks, `team init`, and gates."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import calls, fake_cli, git, gitea_pr, make_team_repo, path_with, run_cli, write  # noqa: E402
from workflow_core.hosts import adapter  # noqa: E402
from workflow_core.team_host import HostCliMissing, HostUnavailable  # noqa: E402

BASE = "https://git.example.com/gitea"
PR = f"{BASE}/org/app/pulls/5"
SSH_REMOTE = "ssh://git@git.example.com:2222/org/app.git"
SPEC_PATH = ".planning/specs/2026-10-03-login-design.md"
VERSION = "gt version 1.0.0 (2026-10-01)\nhttps://gitea.com/gitea/cli/releases/tag/v1.0.0\nbuilt with go1.27.2\n"
PAGES = ["-f", "limit=50", "--paginate", "--slurp"]


def review(login: str, state: str, commit: str, number: int, *, dismissed: bool = False, stale: bool = False) -> dict:
    return {"id": number, "state": state, "commit_id": commit, "dismissed": dismissed, "stale": stale,
            "user": {"login": login}}


def pull_rules(pull: dict, reviews: list[dict] = (), files: list[str] = (), *, base: str = BASE,
               repo: str = "org/app", number: int = 5) -> list[dict]:
    """The three `gt api` answers behind one PR; list endpoints answer `--slurp` as a list of pages."""
    path = f"repos/{repo}/pulls/{number}"
    return [{"argv": ["api", "--host", base, path], "stdout": pull},
            {"argv": ["api", "--host", base, f"{path}/reviews", *PAGES], "stdout": [list(reviews)]},
            {"argv": ["api", "--host", base, f"{path}/files", *PAGES], "stdout": [[{"filename": f} for f in files]]}]


class GiteaCase(unittest.TestCase):
    remote = SSH_REMOTE

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_team_repo(Path(self.tmp.name) / "repo", host="gitea")
        git(self.root, "remote", "set-url", "origin", self.remote)
        self.bin = Path(self.tmp.name) / "bin"
        self.env = path_with(self.bin)
        self.addCleanup(self.tmp.cleanup)

    def gt(self, rules: list[dict]) -> None:
        fake_cli(self.bin, "gt", rules)

    def fetch(self, url: str = PR):
        with mock.patch.dict(os.environ, self.env):
            return adapter("gitea").fetch_pr(url, self.root)


class TestFetchPr(GiteaCase):
    def test_merged_pr_maps_approvals_on_the_head_commit(self):
        head = "f" * 40
        self.gt(pull_rules(
            gitea_pr(head=head, author="binh-dev", body="Plan: p"),
            [review("an-ba", "APPROVED", head, 1),
             review("chi-fe", "APPROVED", head, 2, dismissed=True),
             review("dung-qe", "APPROVED", "c" * 40, 3, stale=True)],
            [SPEC_PATH, "README.md"]))
        pr = self.fetch()
        self.assertEqual((PR, "merged", True, "m" * 40, head, "binh-dev"),
                         (pr.url, pr.state, pr.merged, pr.merge_commit, pr.head_sha, pr.author))
        self.assertEqual((("an-ba", head), ("dung-qe", "c" * 40)), pr.approvals)
        self.assertEqual((SPEC_PATH, "README.md"), pr.files)
        self.assertEqual("Plan: p", pr.body)
        self.assertEqual("", pr.approval_note)

    def test_every_gt_api_call_carries_the_instance_host(self):
        self.gt(pull_rules(gitea_pr(), [review("an-ba", "APPROVED", "c", 1)], [SPEC_PATH]))
        self.fetch()
        logged = calls(self.bin)
        self.assertEqual(3, len(logged))
        for call in logged:
            self.assertEqual(["gt", "api", "--host", BASE], call[:4])

    def test_the_latest_review_per_reviewer_decides(self):
        self.gt(pull_rules(gitea_pr(), [
            review("an-ba", "APPROVED", "a", 1), review("an-ba", "REQUEST_CHANGES", "b", 2),
            review("binh-dev", "REQUEST_CHANGES", "a", 3), review("binh-dev", "APPROVED", "b", 4),
            review("chi-fe", "APPROVED", "a", 5), review("chi-fe", "COMMENT", "b", 6)]))
        self.assertEqual((("binh-dev", "b"), ("chi-fe", "a")), self.fetch().approvals)

    def test_a_review_without_commit_id_says_it_predates_commit_tracking(self):
        self.gt(pull_rules(gitea_pr(), [review("an-ba", "APPROVED", "", 1)]))
        pr = self.fetch()
        self.assertEqual((("an-ba", ""),), pr.approvals)
        self.assertIn("predates commit tracking", pr.approval_note)

    def test_open_and_closed_unmerged_states_and_review_pages(self):
        rules = pull_rules(gitea_pr(merged=False), [], [])
        rules[1]["stdout"] = [[review("an-ba", "APPROVED", "c", 1)], [review("binh-dev", "APPROVED", "c", 2)]]
        self.gt(rules)
        pr = self.fetch()
        self.assertEqual(("open", False, ""), (pr.state, pr.merged, pr.merge_commit))
        self.assertEqual(("an-ba", "binh-dev"), tuple(login for login, _ in pr.approvals))
        self.gt(pull_rules(gitea_pr(merged=False, state="closed")))
        self.assertEqual("closed", self.fetch().state)

    def test_url_with_a_trailing_path_or_query_is_normalised(self):
        self.gt(pull_rules(gitea_pr()))
        self.assertEqual(PR, self.fetch(f"{PR}/files?w=1").url)

    def test_instance_forms_name_their_own_host(self):
        for base in ("https://gitea.com", "http://localhost:3000", "https://git.example.com:8443/a/b"):
            with self.subTest(base):
                self.gt(pull_rules(gitea_pr(), base=base))
                self.assertEqual(f"{base}/org/app/pulls/5", self.fetch(f"{base}/org/app/pulls/5").url)
                self.assertEqual(base, calls(self.bin)[-1][3])

    def test_exit_4_names_the_login_for_that_instance(self):
        self.gt([{"argv": ["api"], "exit": 4, "stderr": "not logged in"}])
        with self.assertRaises(HostUnavailable) as raised:
            self.fetch()
        self.assertEqual(f"gt is not logged in: run gt auth login --host {BASE}", str(raised.exception))

    def test_missing_gt_names_the_login_for_that_instance(self):
        with mock.patch("workflow_core.team_host.tool", return_value=None), self.assertRaises(HostCliMissing) as raised:
            self.fetch()
        self.assertIn(f"gt auth login --host {BASE}", str(raised.exception))

    def test_other_gt_failures_and_bad_output_are_host_unavailable(self):
        self.gt([{"argv": ["api"], "exit": 1, "stderr": "HTTP 404: not found"}])
        with self.assertRaisesRegex(HostUnavailable, "HTTP 404.*gt auth login --host " + BASE):
            self.fetch()
        for stdout in ("not json", [1, 2], ["x"]):
            with self.subTest(stdout=stdout):
                self.gt([{"argv": ["api"], "stdout": stdout}])
                with self.assertRaises(HostUnavailable):
                    self.fetch()
        rules = pull_rules(gitea_pr())
        rules[1]["stdout"] = {"message": "oops"}
        self.gt(rules)
        with self.assertRaisesRegex(HostUnavailable, "unexpected"):
            self.fetch()

    def test_a_url_that_is_not_a_pull_request_names_the_expected_form(self):
        for url in ("https://git.example.com/org/app", "https://git.example.com/org/app/issues/5",
                    "git.example.com/org/app/pulls/5", "ssh://git@git.example.com/org/app/pulls/5",
                    "https://git.example.com/app/pulls/5"):
            with self.subTest(url), self.assertRaisesRegex(HostUnavailable, r"<owner>/<repo>/pulls/<n>"):
                adapter("gitea").fetch_pr(url, self.root)
        self.assertEqual([], calls(self.bin))


class TestSearch(GiteaCase):
    def test_merged_with_text_keeps_only_merged_pull_requests(self):
        self.gt([
            {"argv": ["api", "repos/{owner}/{repo}/issues", "-f", "type=pulls", "-f", "state=closed",
                      "-f", "q=Plan: p", "-f", "limit=50", "--paginate", "--slurp", "--max-pages", "2"],
             "stdout": [[{"number": 1}, {"number": 2}], [{"number": 3}]]},
            {"argv": ["api", "repos/{owner}/{repo}/pulls/1"],
             "stdout": {**gitea_pr(1, body="Plan: p\nTracks: 1"), "html_url": f"{BASE}/org/app/pulls/1"}},
            {"argv": ["api", "repos/{owner}/{repo}/pulls/2"], "stdout": gitea_pr(2, merged=False, state="closed")},
            {"argv": ["api", "repos/{owner}/{repo}/pulls/3"],
             "stdout": {**gitea_pr(3, body="Plan: p"), "html_url": f"{BASE}/org/app/pulls/3"}}])
        with mock.patch.dict(os.environ, self.env):
            found = adapter("gitea").merged_with_text("Plan: p", self.root)
        self.assertEqual([f"{BASE}/org/app/pulls/1", f"{BASE}/org/app/pulls/3"], [pr.url for pr in found])
        self.assertEqual([("merged", True, "m" * 40, "Plan: p\nTracks: 1")],
                         [(pr.state, pr.merged, pr.merge_commit, pr.body) for pr in found[:1]])

    def test_pr_for_branch_is_the_newest_pull_request_of_the_branch(self):
        listing = ["api", "repos/{owner}/{repo}/pulls", "-f", "state=all", "-f", "limit=50", "--paginate", "--slurp",
                   "--max-pages", "10"]
        pulls = [{**gitea_pr(3, branch="spec/x"), "html_url": "u3"},
                 {**gitea_pr(7, merged=False, state="closed", branch="spec/x"), "html_url": "u7"},
                 {**gitea_pr(9, branch="other"), "html_url": "u9"}]
        self.gt([{"argv": listing, "stdout": [pulls[:2], pulls[2:]]}])
        with mock.patch.dict(os.environ, self.env):
            newest = adapter("gitea").pr_for_branch("spec/x", self.root)
            self.assertEqual(("u7", "closed", False, ""), (newest.url, newest.state, newest.merged, newest.merge_commit))
            merged = adapter("gitea").pr_for_branch("other", self.root)
            self.assertEqual(("u9", "merged", "m" * 40), (merged.url, merged.state, merged.merge_commit))
            self.assertIsNone(adapter("gitea").pr_for_branch("nothing", self.root))


class TestRepoId(unittest.TestCase):
    def test_pull_request_and_remote_forms_compare_equal(self):
        gitea = adapter("gitea")
        forms = [(f"{BASE}/Org/App/pulls/5", True), (f"{BASE}/Org/App/pulls/5/files?x=1", True),
                 ("https://git.example.com:8443/org/app/pulls/5", True), (SSH_REMOTE, False),
                 ("git@git.example.com:org/app.git", False), (f"{BASE}/org/app.git", False),
                 ("https://git.example.com/org/app", False), ("http://git.example.com:3000/org/App.git", False)]
        for form, is_pr in forms:
            with self.subTest(form):
                self.assertEqual("git.example.com/org/app", gitea.repo_id(form, pr=is_pr))

    def test_another_host_or_repository_differs(self):
        gitea = adapter("gitea")
        expected = gitea.repo_id(SSH_REMOTE)
        for other in (f"{BASE}/org/other/pulls/5", f"{BASE}/other/app/pulls/5", "https://gitea.com/org/app/pulls/5"):
            with self.subTest(other):
                self.assertNotEqual(expected, gitea.repo_id(other, pr=True))

    def test_malformed_locations_are_host_unavailable(self):
        for location, is_pr in (("https://git.example.com/app/pulls/5", True), ("not a url", False), ("", False),
                                ("https://git.example.com/app.git", False)):
            with self.subTest(location), self.assertRaises(HostUnavailable):
                adapter("gitea").repo_id(location, pr=is_pr)


class TestDoctor(GiteaCase):
    remote = f"{BASE}/org/app.git"

    def checks(self) -> dict:
        with mock.patch.dict(os.environ, self.env):
            return adapter("gitea").doctor_checks(self.root)

    def gitea_gt(self, *, login: bool = True, version: str = "28.0.0") -> None:
        self.gt([{"argv": ["--version"], "stdout": VERSION},
                 {"argv": ["auth", "status"], "exit": 0 if login else 4},
                 {"argv": ["auth", "status", "--host", BASE], "exit": 0 if login else 4},
                 {"argv": ["api", "--host", BASE, "version"], "stdout": {"version": version}}])

    def test_a_gt_that_is_not_the_gitea_cli_fails_alone(self):
        self.gt([{"argv": ["--version"], "stdout": "1.4.3\n"}])
        checks = self.checks()
        self.assertEqual(["gitea_cli"], list(checks))
        ok, fix = checks["gitea_cli"]
        self.assertFalse(ok)
        self.assertIn("docs.gitea.com/cli", fix)
        self.assertEqual([["gt", "--version"]], calls(self.bin))

    def test_no_login_for_the_instance_names_the_login(self):
        self.gitea_gt(login=False)
        checks = self.checks()
        self.assertEqual({"gitea_cli": (True, checks["gitea_cli"][1]),
                          "host_login": (False, f"gt auth login --host {BASE}")}, checks)

    def test_server_older_than_gitea_28_fails_and_28_passes(self):
        for version, ok in (("27.1.0", False), ("1.22.0", False), ("28.0.0", True), ("29.0.0+dev-160-g55186ca39b", True)):
            with self.subTest(version):
                self.gitea_gt(version=version)
                checks = self.checks()
                self.assertEqual((True, True, ok), (checks["gitea_cli"][0], checks["host_login"][0],
                                                    checks["server_version"][0]))
                if not ok:
                    self.assertIn(f"{BASE} runs Gitea {version}", checks["server_version"][1])

    def test_an_unreadable_server_version_fails_with_a_fix(self):
        self.gt([{"argv": ["--version"], "stdout": VERSION}, {"argv": ["auth", "status"], "exit": 0},
                 {"argv": ["api"], "stdout": "<html>"}])
        ok, fix = self.checks()["server_version"]
        self.assertFalse(ok)
        self.assertIn("could not read", fix)

    def test_an_ssh_remote_checks_the_bare_host(self):
        git(self.root, "remote", "set-url", "origin", SSH_REMOTE)
        self.gt([{"argv": ["--version"], "stdout": VERSION}, {"argv": ["auth", "status", "--host", "git.example.com"]},
                 {"argv": ["api", "--host", "git.example.com", "version"], "stdout": {"version": "28.0.0"}}])
        checks = self.checks()
        self.assertTrue(all(ok for ok, _ in checks.values()), checks)
        self.assertIn(["gt", "auth", "status", "--host", "git.example.com"], calls(self.bin))

    def test_setup_doctor_reports_the_failing_checks_and_fixes(self):
        write(self.root, ".agent-workflow/config.yaml",
              (self.root / ".agent-workflow/config.yaml").read_text() + "artifacts:\n  spec_review: pr\n")
        self.gitea_gt(version="27.1.0")
        result = run_cli(self.root, "setup", "doctor", "--format", "json", env=self.env)
        detail = json.loads(result.stdout)["checks_details"]["team"]
        self.assertEqual((True, True, True, False), tuple(detail["checks"][name] for name in (
            "host_cli", "gitea_cli", "host_login", "server_version")))
        self.assertTrue(any("runs Gitea 27.1.0" in action for action in detail["actions"]), detail["actions"])


class TestTeamInit(GiteaCase):
    def test_init_writes_gitea_files_and_ci(self):
        result = run_cli(self.root, "team", "init", "--ci")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([f"wrote {item}" for item in (
            ".gitea/CODEOWNERS", ".gitea/PULL_REQUEST_TEMPLATE.md", ".githooks/commit-msg",
            ".gitea/workflows/gin-workflow.yml")], result.stdout.splitlines())
        ci = (self.root / ".gitea/workflows/gin-workflow.yml").read_text()
        self.assertIn("'conventional' != 'none'", ci)
        self.assertNotIn("hashFiles", ci)
        self.assertIn("test -f .agent-workflow/config.yaml || exit 0", ci)
        self.assertIn("/web/** @chi-fe\n", (self.root / ".gitea/CODEOWNERS").read_text())
        self.assertEqual(0, run_cli(self.root, "team", "codeowners", "--check").returncode)


class TestGates(GiteaCase):
    """The gate flows of test_team_gates.py on a self-hosted instance under a subpath with an SSH remote on port 2222."""

    def record(self, gate: str = "requirement-confirmed", evidence: str = PR):
        return run_cli(self.root, "record", gate, "--evidence", evidence, "--workflow-id", "w", env=self.env)

    def check_ship(self, evidence: str = PR):
        return run_cli(self.root, "team", "check", evidence, "--gate", "ship", env=self.env)

    def events(self) -> list[dict]:
        path = self.root / ".agent-workflow/runtime/events.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.is_file() else []

    def commit(self) -> str:
        write(self.root, SPEC_PATH, "# Login\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "feat: x")
        return git(self.root, "rev-parse", "HEAD").strip()

    def test_merged_spec_gate_passes_with_a_listed_role(self):
        self.gt(pull_rules(gitea_pr(author="binh-dev"), [review("an-ba", "APPROVED", "c1", 1)], [SPEC_PATH]))
        result = self.record()
        self.assertEqual(0, result.returncode, result.stderr)
        event = self.events()[-1]
        self.assertEqual({"evidence": PR, "pr_url": PR, "merge_commit": "m" * 40,
                          "approvers": [{"login": "an-ba", "email": "an@corp.com", "roles": ["ba"]}],
                          "repository": "git.example.com/org/app", "artifact": SPEC_PATH}, event["payload"])
        self.assertTrue(all(call[3] == BASE for call in calls(self.bin) if call[1] == "api"))

    def test_rejections_record_nothing(self):
        cases = [
            ("open PR", gitea_pr(merged=False), [review("an-ba", "APPROVED", "c", 1)], "PR is open, not merged"),
            ("wrong role", gitea_pr(author="binh-dev"), [review("dung-qe", "APPROVED", "c", 1)],
             "missing approval from one of ba, be_lead, fe_lead"),
            ("author excluded", gitea_pr(author="an-ba"), [review("an-ba", "APPROVED", "c", 1)], "missing approval"),
            ("dismissed", gitea_pr(), [review("an-ba", "APPROVED", "c", 1, dismissed=True)], "missing approval"),
            ("withdrawn", gitea_pr(), [review("an-ba", "APPROVED", "c", 1), review("an-ba", "REQUEST_CHANGES", "c", 2)],
             "missing approval"),
        ]
        for name, pull, reviews, reason in cases:
            with self.subTest(name):
                self.gt(pull_rules(pull, reviews, [SPEC_PATH]))
                result = self.record()
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertIn(reason, result.stderr)
        self.assertEqual([], self.events())

    def test_ship_counts_only_approvals_on_the_head_commit(self):
        head = self.commit()
        self.gt(pull_rules(gitea_pr(merged=False, head=head), [review("dung-qe", "APPROVED", "old", 1)]))
        result = self.check_ship()
        self.assertEqual(1, result.returncode)
        self.assertIn("missing approval from one of qe", result.stdout)
        self.gt(pull_rules(gitea_pr(merged=False, head="f" * 40), [review("dung-qe", "APPROVED", "f" * 40, 1)]))
        self.assertIn("is not local HEAD", self.check_ship().stdout)
        self.gt(pull_rules(gitea_pr(merged=False, head=head), [review("dung-qe", "APPROVED", head, 1)]))
        self.assertEqual(0, self.check_ship().returncode)

    def test_ship_with_a_review_that_has_no_commit_id_says_why(self):
        head = self.commit()
        self.gt(pull_rules(gitea_pr(merged=False, head=head), [review("dung-qe", "APPROVED", "", 1)]))
        result = self.check_ship()
        self.assertEqual(1, result.returncode)
        self.assertIn("predates commit tracking", result.stdout)

    def test_pull_request_of_another_repository_is_rejected(self):
        other = f"{BASE}/other/app/pulls/5"
        self.gt(pull_rules(gitea_pr(), [review("an-ba", "APPROVED", "c", 1)], [SPEC_PATH], repo="other/app"))
        result = self.record(evidence=other)
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn("PR belongs to git.example.com/other/app, not this repository (git.example.com/org/app)",
                      result.stderr)
        self.assertEqual([], self.events())

    def test_logged_out_instance_exits_2_with_its_login_command(self):
        self.gt([{"argv": ["api"], "exit": 4, "stderr": "not logged in"}])
        result = self.record()
        self.assertEqual(2, result.returncode)
        self.assertIn(f"gt auth login --host {BASE}", result.stderr)
        self.assertEqual([], self.events())


if __name__ == "__main__":
    unittest.main()

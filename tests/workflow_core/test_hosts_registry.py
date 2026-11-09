"""Host adapter registry: GitHub and GitLab adapters, unknown hosts, stub hosts, and `specs trace` per host."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import calls, fake_cli, make_team_repo, path_with  # noqa: E402
from specs_fixtures import make_change  # noqa: E402
from workflow_core import specs_trace, team_init  # noqa: E402
from workflow_core.hosts import HOSTS, adapter  # noqa: E402
from workflow_core.team import TeamError, load_team  # noqa: E402
from workflow_core.team_host import HostUnavailable  # noqa: E402

import yaml  # noqa: E402

BRANCH_LIST = ["mr", "list", "--source-branch", "spec/ep-1-lockout", "--all", "-F", "json"]


class TestRegistry(unittest.TestCase):
    def test_known_hosts_resolve_to_their_cli(self):
        self.assertEqual(("github", "gitlab", "gitea", "codecommit"), HOSTS)
        self.assertEqual(("gh", "gh auth login"), (adapter("github").executable, adapter("github").login_fix))
        self.assertEqual(("glab", "glab auth login"), (adapter("gitlab").executable, adapter("gitlab").login_fix))
        for host in HOSTS:
            with self.subTest(host=host):
                self.assertEqual(host, adapter(host).name)

    def test_unknown_host_is_a_value_error(self):
        with self.assertRaises(ValueError):
            adapter("nope")

    def test_github_and_gitlab_keep_their_files_and_notes(self):
        self.assertEqual(".github/CODEOWNERS", adapter("github").files.codeowners)
        self.assertEqual("team/gitlab-ci.yml", adapter("gitlab").files.ci_template)
        self.assertEqual([], adapter("github").doctor_notes())
        self.assertEqual(["GitLab Free cannot require code-owner approval; the gin check still applies"],
                         adapter("gitlab").doctor_notes())

    def test_stub_hosts_are_not_built_yet(self):
        for host in ("gitea", "codecommit"):
            with self.subTest(host=host), self.assertRaisesRegex(HostUnavailable, f"{host} support is not built yet"):
                adapter(host).fetch_pr("https://example.com/x", Path("."))


class HostRepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = Path(self.tmp.name) / "bin"

    def tearDown(self):
        self.tmp.cleanup()

    def repo(self, host: str) -> Path:
        return make_team_repo(Path(self.tmp.name) / "repo", host=host)


class TestSpecsTraceStatus(HostRepoCase):
    def test_gitlab_status_uses_glab(self):
        root = self.repo("gitlab")
        change = make_change(root)
        url = "https://gitlab.corp.com/group/app/-/merge_requests/3"
        fake_cli(self.bin, "glab", [{"argv": BRANCH_LIST, "stdout": [
            {"web_url": url, "state": "merged", "merge_commit_sha": "abc"}]}])
        with mock.patch.dict(os.environ, path_with(self.bin)):
            result = specs_trace.status(root, change)
        self.assertEqual({"change": "ep-1-lockout", "branch": "spec/ep-1-lockout", "status": "merged", "url": url,
                          "merge_commit": "abc"}, result)
        self.assertEqual([["glab", *BRANCH_LIST]], calls(self.bin))

    def test_gitlab_status_open_and_none(self):
        root = self.repo("gitlab")
        change = make_change(root)
        with mock.patch.dict(os.environ, path_with(self.bin)):
            fake_cli(self.bin, "glab", [{"argv": BRANCH_LIST, "stdout": [{"web_url": "u", "state": "opened"}]}])
            self.assertEqual({"change": "ep-1-lockout", "branch": "spec/ep-1-lockout", "status": "open", "url": "u"},
                             specs_trace.status(root, change))
            fake_cli(self.bin, "glab", [{"argv": BRANCH_LIST, "stdout": []}])
            self.assertEqual("none", specs_trace.status(root, change)["status"])

    def test_missing_cli_names_the_host_cli(self):
        root = self.repo("gitlab")
        with mock.patch("workflow_core.team_host.tool", return_value=None):
            result = specs_trace.status(root, make_change(root))
        self.assertEqual("glab_unavailable", result["status"])
        self.assertTrue(result["message"].startswith("glab unavailable; check the PR for spec/ep-1-lockout by hand"))


class TestTeamInitCi(HostRepoCase):
    def test_ci_on_a_host_without_a_ci_file_is_refused(self):
        root = self.repo("codecommit")
        config = yaml.safe_load((root / ".agent-workflow/config.yaml").read_text())
        with self.assertRaises(TeamError):
            team_init.planned_files(root, load_team(config), config, ci=True)


if __name__ == "__main__":
    unittest.main()

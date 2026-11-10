"""AWS CodeCommit host: `aws codecommit` adapter, `aws_identity` members, files, doctor, and gates (US-2, R3, R4)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import TEAM, calls, fake_cli, git, make_team_repo, path_with, run_cli, write  # noqa: E402
from workflow_core.configuration import ConfigValidationError, validate_portable_config  # noqa: E402
from workflow_core.hosts import adapter  # noqa: E402
from workflow_core.team import load_team, validate_team  # noqa: E402
from workflow_core.team_host import HostUnavailable  # noqa: E402

import yaml  # noqa: E402

REGION = "eu-west-1"
ORIGIN = f"https://git-codecommit.{REGION}.amazonaws.com/v1/repos/app"
URL = f"https://{REGION}.console.aws.amazon.com/codesuite/codecommit/repositories/app/pull-requests/7?region={REGION}"
SPEC_PATH = ".planning/specs/2026-10-03-login-design.md"
TAIL = ["--region", REGION, "--output", "json"]
ALICE = "arn:aws:sts::111122223333:assumed-role/Dev/alice"
BOB = "arn:aws:iam::111122223333:user/bob"
DAVE = "arn:aws:iam::111122223333:user/ops/dave"

# `TEAM` with an `aws_identity` on every approving member; em (be_dev) holds no approving role.
CC_TEAM = (TEAM.format(host="codecommit")
           .replace("login: an-ba}", "login: an-ba, aws_identity: Dev/alice}")
           .replace("login: binh-dev}", "login: binh-dev, aws_identity: bob}")
           .replace("login: chi-fe}", "login: chi-fe, aws_identity: carol}")
           .replace("login: dung-qe}", "login: dung-qe, aws_identity: dave}"))


def pull_request(*, status: str = "OPEN", merged: bool = False, source: str = "s" * 40, revision: str = "rev1",
                 author: str = BOB, description: str = "", ref: str = "refs/heads/spec/x", repo: str = "app") -> dict:
    meta = {"isMerged": merged, **({"mergeCommitId": "m" * 40} if merged else {})}
    return {"pullRequest": {"pullRequestStatus": status, "authorArn": author, "title": "t", "description": description,
                            "revisionId": revision,
                            "pullRequestTargets": [{"repositoryName": repo, "sourceReference": ref,
                                                    "destinationReference": "refs/heads/main",
                                                    "sourceCommit": source, "destinationCommit": "d" * 40,
                                                    "mergeBase": "b" * 40, "mergeMetadata": meta}]}}


def rule(*argv: str, **fields) -> dict:
    return {"argv": ["codecommit", *argv], **fields}


def diff(*paths: str, token: str = "") -> dict:
    return {"differences": [{"afterBlob": {"path": item}, "changeType": "A"} for item in paths],
            **({"NextToken": token} if token else {})}


def approvals(*arns: str) -> dict:
    return {"approvals": [{"userArn": arn, "approvalState": "APPROVE"} for arn in arns]}


class CodeCommitCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = Path(self.tmp.name) / "bin"
        self.root = self.repo(Path(self.tmp.name) / "repo")
        self.env = path_with(self.bin)

    def tearDown(self):
        self.tmp.cleanup()

    def repo(self, path: Path, *, team: str = CC_TEAM, origin: str = ORIGIN, extra: str = "") -> Path:
        root = make_team_repo(path, team=team, extra=extra)
        git(root, "remote", "set-url", "origin", origin)
        return root

    def aws(self, rules: list[dict]) -> None:
        fake_cli(self.bin, "aws", rules)

    def fetch(self, url: str = URL):
        with mock.patch.dict(os.environ, self.env):
            return adapter("codecommit").fetch_pr(url, self.root)

    def aws_calls(self) -> list[list[str]]:
        return [call[1:] for call in calls(self.bin)]


class TestFetchPr(CodeCommitCase):
    def test_open_pull_request_counts_approvals_of_the_current_revision(self):
        self.aws([
            rule("get-pull-request", "--pull-request-id", "7", *TAIL, stdout=pull_request(revision="rev2")),
            rule("get-pull-request-approval-states", "--pull-request-id", "7", "--revision-id", "rev1",
                 stdout=approvals(DAVE)),
            rule("get-pull-request-approval-states", "--pull-request-id", "7", "--revision-id", "rev2",
                 stdout={"approvals": [{"userArn": ALICE, "approvalState": "APPROVE"},
                                       {"userArn": BOB, "approvalState": "APPROVE"},
                                       {"userArn": DAVE, "approvalState": "REVOKE"}]}),
            rule("get-differences", "--repository-name", "app", "--before-commit-specifier", "b" * 40,
                 "--after-commit-specifier", "s" * 40, stdout=diff("a.py")),
        ])
        pr = self.fetch()
        self.assertEqual(("open", False, "", "s" * 40, "bob"), (pr.state, pr.merged, pr.merge_commit, pr.head_sha, pr.author))
        self.assertEqual((("Dev/alice", "s" * 40), ("bob", "s" * 40)), pr.approvals)
        self.assertEqual(URL, pr.url)
        self.assertIn(["codecommit", "get-pull-request-approval-states", "--pull-request-id", "7", "--revision-id",
                       "rev2", *TAIL], self.aws_calls())
        self.assertNotIn("rev1", [item for call in self.aws_calls() for item in call])

    def test_closed_pull_request_is_merged_only_when_merge_metadata_says_so(self):
        for merged, state in ((True, "merged"), (False, "closed")):
            with self.subTest(state=state):
                self.aws([rule("get-pull-request", stdout=pull_request(status="CLOSED", merged=merged,
                                                                        description="spec for ep-1")),
                          rule("get-pull-request-approval-states", stdout=approvals()),
                          rule("get-differences", stdout=diff())])
                pr = self.fetch()
                self.assertEqual((state, merged, "m" * 40 if merged else "", "spec for ep-1"),
                                 (pr.state, pr.merged, pr.merge_commit, pr.body))

    def test_files_follow_every_get_differences_page(self):
        base = ["get-differences", "--repository-name", "app", "--before-commit-specifier", "b" * 40,
                "--after-commit-specifier", "s" * 40]
        self.aws([
            rule("get-pull-request", stdout=pull_request()),
            rule("get-pull-request-approval-states", stdout=approvals()),
            rule(*base, stdout=diff("a.py", "b.py", token="T1")),
            rule(*base, "--starting-token", "T1",
                 stdout={"differences": [{"beforeBlob": {"path": "old.py"}, "changeType": "D"}]}),
        ])
        self.assertEqual(("a.py", "b.py", "old.py"), self.fetch().files)

    def test_a_pull_request_of_another_repository_than_the_url_is_refused(self):
        self.aws([rule("get-pull-request", stdout=pull_request(repo="other"))])
        with self.assertRaisesRegex(HostUnavailable, "belongs to repository other, not app"):
            self.fetch()

    def test_unexpected_output_and_cli_failure_are_host_errors(self):
        self.aws([rule("get-pull-request", stdout={"pullRequest": {"pullRequestTargets": []}})])
        with self.assertRaisesRegex(HostUnavailable, "unexpected"):
            self.fetch()
        self.aws([rule("get-pull-request", exit=254, stderr="ExpiredToken")])
        with self.assertRaisesRegex(HostUnavailable, "ExpiredToken.*aws configure or aws sso login"):
            self.fetch()

    def test_missing_cli_names_the_fix(self):
        with mock.patch("workflow_core.team_host.tool", return_value=None), \
                self.assertRaisesRegex(HostUnavailable, "aws is not installed.*aws configure or aws sso login"):
            self.fetch()

    def test_non_console_url_shows_the_expected_form(self):
        for url in ("https://github.com/org/app/pull/7", ORIGIN,
                    f"https://{REGION}.console.aws.amazon.com/codesuite/codecommit/repositories/app"):
            with self.subTest(url=url), self.assertRaisesRegex(
                    HostUnavailable, r"https://<region>\.console\.aws\.amazon\.com/codesuite/codecommit/repositories/"
                                     r"<repo>/pull-requests/<id>"):
                self.fetch(url)


class TestSearch(CodeCommitCase):
    def test_merged_with_text_pages_and_keeps_merged_matches(self):
        listing = ["list-pull-requests", "--repository-name", "app", "--pull-request-status", "CLOSED"]
        self.aws([
            rule(*listing, stdout={"pullRequestIds": ["3", "5"], "nextToken": "T1"}),
            rule(*listing, "--starting-token", "T1", stdout={"pullRequestIds": ["9"], "nextToken": ""}),
            rule("get-pull-request", "--pull-request-id", "3",
                 stdout=pull_request(status="CLOSED", merged=True, description="ep-1 spec")),
            rule("get-pull-request", "--pull-request-id", "5",
                 stdout=pull_request(status="CLOSED", description="ep-1 spec, abandoned")),
            rule("get-pull-request", "--pull-request-id", "9",
                 stdout=pull_request(status="CLOSED", merged=True, description="other")),
        ])
        with mock.patch.dict(os.environ, self.env):
            found = adapter("codecommit").merged_with_text("ep-1", self.root)
        self.assertEqual([(URL.replace("/7?", "/3?"), "merged", "m" * 40, "ep-1 spec")],
                         [(item.url, item.state, item.merge_commit, item.body) for item in found])

    def test_merged_with_text_reads_at_most_100_pull_requests(self):
        self.aws([rule("list-pull-requests", stdout={"pullRequestIds": [str(n) for n in range(1, 151)]}),
                  rule("get-pull-request", stdout=pull_request(status="CLOSED", description="x"))])
        with mock.patch.dict(os.environ, self.env):
            adapter("codecommit").merged_with_text("ep-1", self.root)
        self.assertEqual(100, len([call for call in self.aws_calls() if call[1] == "get-pull-request"]))

    def test_pr_for_branch_returns_the_newest_pull_request_of_the_branch(self):
        self.aws([
            rule("list-pull-requests", "--repository-name", "app", stdout={"pullRequestIds": ["4", "6", "5"]}),
            rule("get-pull-request", "--pull-request-id", "6", stdout=pull_request(ref="refs/heads/other")),
            rule("get-pull-request", "--pull-request-id", "5",
                 stdout=pull_request(status="CLOSED", merged=True, ref="refs/heads/spec/x")),
        ])
        with mock.patch.dict(os.environ, self.env):
            found = adapter("codecommit").pr_for_branch("spec/x", self.root)
        self.assertEqual((URL.replace("/7?", "/5?"), "merged", True, "m" * 40),
                         (found.url, found.state, found.merged, found.merge_commit))
        self.assertNotIn("4", [item for call in self.aws_calls() for item in call])

    def test_pr_for_branch_without_a_match_is_none(self):
        self.aws([rule("list-pull-requests", stdout={"pullRequestIds": []})])
        with mock.patch.dict(os.environ, self.env):
            self.assertIsNone(adapter("codecommit").pr_for_branch("spec/x", self.root))

    def test_searching_needs_a_region(self):
        root = self.repo(Path(self.tmp.name) / "noregion", origin="codecommit://dev@app")
        with mock.patch.dict(os.environ, {**self.env, "AWS_REGION": "", "AWS_DEFAULT_REGION": ""}), \
                self.assertRaisesRegex(HostUnavailable, "AWS_REGION"):
            adapter("codecommit").pr_for_branch("spec/x", root)


class TestRepoId(unittest.TestCase):
    def test_every_location_form_of_one_repository_compares_equal(self):
        host = adapter("codecommit")
        console = host.repo_id(URL, pr=True)
        with mock.patch.dict(os.environ, {"AWS_REGION": REGION}):
            profile = host.repo_id("codecommit://dev@app")
        for remote in ("codecommit::eu-west-1://app", ORIGIN, f"ssh://git-codecommit.{REGION}.amazonaws.com/v1/repos/app",
                       "codecommit::eu-west-1://dev@app"):
            with self.subTest(remote=remote):
                self.assertEqual(console, host.repo_id(remote))
        self.assertEqual(console, profile)
        self.assertEqual("codecommit/eu-west-1/app", console)

    def test_another_region_or_repository_differs(self):
        host = adapter("codecommit")
        console = host.repo_id(URL, pr=True)
        self.assertNotEqual(console, host.repo_id("codecommit::us-east-1://app"))
        self.assertNotEqual(console, host.repo_id("codecommit::eu-west-1://other"))
        self.assertNotEqual(console, host.repo_id(URL.replace("/app/", "/other/"), pr=True))

    def test_remote_without_a_region_fails_closed(self):
        with mock.patch.dict(os.environ, {"AWS_REGION": "", "AWS_DEFAULT_REGION": ""}), \
                self.assertRaisesRegex(HostUnavailable, "region of origin is unknown; set AWS_REGION"):
            adapter("codecommit").repo_id("codecommit://dev@app")

    def test_default_region_variable_is_used_after_aws_region(self):
        with mock.patch.dict(os.environ, {"AWS_REGION": "", "AWS_DEFAULT_REGION": "us-east-1"}):
            self.assertEqual("codecommit/us-east-1/app", adapter("codecommit").repo_id("codecommit://app"))

    def test_other_locations_show_the_expected_forms(self):
        host = adapter("codecommit")
        with self.assertRaisesRegex(HostUnavailable, r"codecommit::<region>://<repo>"):
            host.repo_id("git@github.com:org/app.git")
        with self.assertRaisesRegex(HostUnavailable, r"pull-requests/<id>"):
            host.repo_id("https://github.com/org/app/pull/7", pr=True)


class TestAwsIdentityConfig(unittest.TestCase):
    RAW = yaml.safe_load(CC_TEAM)["team"]

    def test_schema_accepts_aws_identity_and_rejects_an_empty_one(self):
        validate_portable_config({"schema_version": "2.7", "team": self.RAW})
        raw = yaml.safe_load(CC_TEAM)["team"]
        raw["members"]["an@corp.com"]["aws_identity"] = ""
        with self.assertRaises(ConfigValidationError):
            validate_portable_config({"schema_version": "2.7", "team": raw})

    def test_load_team_reads_aws_identity_with_an_empty_default(self):
        team = load_team({"team": self.RAW})
        self.assertEqual(("Dev/alice", ""), (team.member("an@corp.com").aws_identity, team.member("em@corp.com").aws_identity))
        self.assertEqual("an@corp.com", team.by_identity("DEV/ALICE", "aws_identity").email)
        self.assertIsNone(team.by_identity("", "aws_identity"))

    def test_duplicate_aws_identity_is_an_error(self):
        raw = yaml.safe_load(CC_TEAM)["team"]
        raw["members"]["em@corp.com"]["aws_identity"] = "DEV/ALICE"
        self.assertEqual(["team.members: aws_identity DEV/ALICE used by an@corp.com and em@corp.com"], validate_team(raw))

    def test_an_approver_without_aws_identity_is_an_error_on_codecommit_only(self):
        raw = yaml.safe_load(CC_TEAM)["team"]
        del raw["members"]["dung@corp.com"]["aws_identity"]
        self.assertEqual(["team.members: dung@corp.com holds approving role qe but has no aws_identity "
                          "(required on host codecommit)"], validate_team(raw))
        self.assertEqual([], validate_team({**raw, "host": "github"}))
        with self.assertRaisesRegex(ConfigValidationError, "dung@corp.com holds approving role qe"):
            validate_portable_config({"schema_version": "2.7", "team": raw})

    def test_area_leads_count_as_approvers_through_the_plan_policy(self):
        raw = yaml.safe_load(CC_TEAM)["team"]
        del raw["members"]["chi@corp.com"]["aws_identity"]
        self.assertEqual(["team.members: chi@corp.com holds approving role fe_lead but has no aws_identity "
                          "(required on host codecommit)"], validate_team(raw))


class TestCodeCommitCli(CodeCommitCase):
    def test_team_check_warns_for_a_member_without_aws_identity(self):
        self.aws([rule("get-pull-request", stdout=pull_request()), rule("get-pull-request-approval-states",
                                                                       stdout=approvals()),
                  rule("get-differences", stdout=diff())])
        result = run_cli(self.root, "team", "check", URL, "--gate", "ship", env=self.env)
        self.assertIn("warning: em@corp.com has no aws_identity; its approvals cannot be matched", result.stderr)
        self.assertNotIn("an@corp.com", result.stderr)

    def test_init_writes_only_the_commit_msg_hook(self):
        result = run_cli(self.root, "team", "init")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["wrote .githooks/commit-msg"], result.stdout.splitlines()[:1])
        self.assertEqual([".githooks"], sorted(item.name for item in self.root.iterdir()
                                               if item.name in (".githooks", ".github", ".gitlab", ".gitea")))
        self.assertEqual(0, run_cli(self.root, "team", "codeowners", "--check").returncode)

    def test_ci_is_refused(self):
        result = run_cli(self.root, "team", "init", "--ci")
        self.assertEqual(2, result.returncode)
        self.assertIn("CodeCommit has no CI workflow file; use CodeBuild or CodePipeline", result.stderr)
        self.assertFalse((self.root / ".githooks").exists())

    def test_codeowners_has_no_file_to_print(self):
        result = run_cli(self.root, "team", "codeowners")
        self.assertEqual(2, result.returncode)
        self.assertIn("team.host codecommit has no CODEOWNERS file", result.stderr)
        self.assertNotIn("None", result.stdout + result.stderr)

    def test_doctor_checks_sts_identity_and_shows_the_approval_rule_note(self):
        root = self.repo(Path(self.tmp.name) / "doctor", extra="artifacts:\n  spec_review: pr\n")
        self.aws([{"argv": ["sts", "get-caller-identity"], "stdout": {"Arn": ALICE}}])
        run_cli(root, "team", "init")
        run_cli(root, "team", "hooks")
        payload = json.loads(run_cli(root, "setup", "doctor", "--format", "json", env=self.env).stdout)
        detail = payload["checks_details"]["team"]
        self.assertTrue(detail["checks"]["host_cli"], detail)
        self.assertTrue(payload["checks"]["team"], detail)
        self.assertIn(["aws", "sts", "get-caller-identity"], calls(self.bin))
        self.assertEqual("CodeCommit does not enforce code owners; create an approval rule template "
                         "(see docs/guides/team.md)", "; ".join(detail["note"].split("; ")[:2]))
        self.aws([{"argv": ["sts", "get-caller-identity"], "exit": 255, "stderr": "Unable to locate credentials"}])
        detail = json.loads(run_cli(root, "setup", "doctor", "--format", "json", env=self.env).stdout
                            )["checks_details"]["team"]
        self.assertFalse(detail["checks"]["host_cli"])
        self.assertIn("aws configure or aws sso login", " ".join(detail["actions"]))


class TestCodeCommitGates(CodeCommitCase):
    def setUp(self):
        super().setUp()
        write(self.root, SPEC_PATH, "# Login\n")

    def events(self) -> list[dict]:
        path = self.root / ".agent-workflow/runtime/events.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.is_file() else []

    def record(self, url: str = URL):
        return run_cli(self.root, "record", "requirement-confirmed", "--evidence", url, "--workflow-id", "w", env=self.env)

    def spec_pr(self, *, approver: str = ALICE, repo: str = "app") -> None:
        self.aws([rule("get-pull-request", stdout=pull_request(status="CLOSED", merged=True, author=BOB, repo=repo)),
                  rule("get-pull-request-approval-states", stdout=approvals(approver)),
                  rule("get-differences", stdout=diff(SPEC_PATH))])

    def test_ba_approval_by_assumed_role_passes_the_spec_gate_and_is_recorded(self):
        self.spec_pr()
        result = self.record()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"evidence": URL, "pr_url": URL, "merge_commit": "m" * 40,
                          "approvers": [{"login": "Dev/alice", "email": "an@corp.com", "roles": ["ba"]}],
                          "repository": "codecommit/eu-west-1/app", "artifact": SPEC_PATH},
                         self.events()[-1]["payload"])

    def test_rejections_record_nothing(self):
        self.spec_pr(approver=DAVE)
        result = self.record()
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn("missing approval from one of ba, be_lead, fe_lead", result.stderr)
        self.spec_pr(approver=BOB)  # the author cannot approve their own pull request
        self.assertIn("missing approval", self.record().stderr)
        self.spec_pr(approver="arn:aws:iam::111122223333:user/mallory")
        self.assertIn("missing approval", self.record().stderr)
        self.assertEqual([], self.events())

    def test_a_session_named_after_a_member_under_another_role_is_not_that_member(self):
        self.spec_pr(approver="arn:aws:sts::111122223333:assumed-role/Other/alice")
        result = self.record()
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn("missing approval from one of ba, be_lead, fe_lead", result.stderr)
        self.assertEqual([], self.events())

    def test_another_repository_or_region_is_rejected_as_not_this_repository(self):
        other_repo = URL.replace("/app/", "/other/")
        self.spec_pr(repo="other")
        self.assertIn("PR belongs to codecommit/eu-west-1/other, not this repository (codecommit/eu-west-1/app)",
                      self.record(other_repo).stderr)
        self.spec_pr()
        other_region = URL.replace(REGION, "us-east-1")
        self.assertIn("PR belongs to codecommit/us-east-1/app, not this repository (codecommit/eu-west-1/app)",
                      self.record(other_region).stderr)
        self.assertEqual([], self.events())

    def ship(self):
        return run_cli(self.root, "team", "check", URL, "--gate", "ship", "--format", "json", env=self.env)

    def test_ship_counts_only_current_revision_approvals_on_local_head(self):
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "feat: x")
        head = git(self.root, "rev-parse", "HEAD").strip()
        states = lambda current: [  # noqa: E731
            rule("get-pull-request-approval-states", "--pull-request-id", "7", "--revision-id", "old",
                 stdout=approvals(DAVE)),
            rule("get-pull-request-approval-states", "--pull-request-id", "7", "--revision-id", "new",
                 stdout=approvals(*current)),
            rule("get-differences", stdout=diff())]
        self.aws([rule("get-pull-request", stdout=pull_request(source=head, revision="new")), *states([])])
        result = self.ship()
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("missing approval from one of qe", result.stdout)
        self.aws([rule("get-pull-request", stdout=pull_request(source="f" * 40, revision="new")), *states([DAVE])])
        self.assertIn("is not local HEAD", self.ship().stdout)
        self.aws([rule("get-pull-request", stdout=pull_request(source=head, revision="new")), *states([DAVE])])
        result = self.ship()
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertEqual([{"login": "dave", "email": "dung@corp.com", "roles": ["qe"]}],
                         json.loads(result.stdout)["approvers"])


if __name__ == "__main__":
    unittest.main()

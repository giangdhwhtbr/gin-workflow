"""Role-gated gate recording: PR/MR evidence through fake gh/glab, waivers, `team check`, and plan checks."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import PLAN, calls, fake_cli, gh_pr, git, make_team_repo, path_with, run_cli, write  # noqa: E402
from workflow_core.team import check_plan, load_team, plan_tracks, repo_slug  # noqa: E402
from workflow_core.team_host import fetch_pr  # noqa: E402

import yaml  # noqa: E402

PR = "https://github.com/org/app/pull/7"
MR = "https://gitlab.corp.com/group/app/-/merge_requests/12"
PLAN_PATH = ".planning/plans/2026-10-03-login.md"
SPEC_PATH = ".planning/specs/2026-10-03-login-design.md"


class GateCase(unittest.TestCase):
    host = "github"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_team_repo(Path(self.tmp.name) / "repo", host=self.host)
        write(self.root, PLAN_PATH, PLAN)
        write(self.root, SPEC_PATH, "# Login\n")
        self.bin = Path(self.tmp.name) / "bin"
        self.env = path_with(self.bin)

    def tearDown(self):
        self.tmp.cleanup()

    def gh(self, pr: dict, exit_code: int = 0) -> None:
        fake_cli(self.bin, "gh", [{"argv": ["pr", "view", PR], "stdout": pr, "exit": exit_code,
                                   "stderr": "" if exit_code == 0 else "HTTP 401: Bad credentials"}])

    def record(self, gate: str, evidence: str = PR, *extra: str):
        return run_cli(self.root, "record", gate, "--evidence", evidence, "--workflow-id", "w", *extra, env=self.env)

    def events(self) -> list[dict]:
        path = self.root / ".agent-workflow/runtime/events.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.is_file() else []


class TestRecordGitHub(GateCase):
    def test_requirement_confirmed_by_ba_is_recorded_with_proof(self):
        self.gh(gh_pr(author="binh-dev", files=[SPEC_PATH], reviews=[("an-ba", "APPROVED", "c1")]))
        result = self.record("requirement-confirmed")
        self.assertEqual(0, result.returncode, result.stderr)
        event = self.events()[-1]
        self.assertEqual("binh@corp.com", event["actor"])
        self.assertEqual({"evidence": PR, "pr_url": PR, "merge_commit": "m" * 40,
                          "approvers": [{"login": "an-ba", "email": "an@corp.com", "roles": ["ba"]}],
                          "repository": "github.com/org/app", "artifact": SPEC_PATH},
                         event["payload"])

    def test_rejections_record_nothing(self):
        cases = [
            ("open PR", gh_pr(state="OPEN", files=[SPEC_PATH], reviews=[("an-ba", "APPROVED", "c")]),
             "PR is open, not merged"),
            ("wrong role", gh_pr(author="binh-dev", files=[SPEC_PATH], reviews=[("dung-qe", "APPROVED", "c")]),
             "missing approval from one of ba, be_lead, fe_lead"),
            ("self approval", gh_pr(author="an-ba", files=[SPEC_PATH], reviews=[("an-ba", "APPROVED", "c")]),
             "missing approval"),
            ("approval withdrawn",
             gh_pr(files=[SPEC_PATH], reviews=[("binh-dev", "APPROVED", "c"), ("binh-dev", "CHANGES_REQUESTED", "d")]),
             "missing approval"),
            ("non-member approver", gh_pr(files=[SPEC_PATH], reviews=[("outsider", "APPROVED", "c")]),
             "missing approval"),
        ]
        for name, pr, reason in cases:
            with self.subTest(name):
                self.gh(pr)
                result = self.record("requirement-confirmed")
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertIn(reason, result.stderr)
        self.assertEqual([], self.events())

    def test_plan_approved_needs_every_area_lead(self):
        self.gh(gh_pr(files=[PLAN_PATH], reviews=[("binh-dev", "APPROVED", "c")]))
        result = self.record("plan-approved")
        self.assertEqual(1, result.returncode)
        self.assertIn("missing approval from fe_lead for area frontend", result.stderr)
        self.gh(gh_pr(files=[PLAN_PATH], reviews=[("binh-dev", "APPROVED", "c"), ("chi-fe", "APPROVED", "c")]))
        self.assertEqual(0, self.record("plan-approved").returncode)

    def test_plan_approved_without_plan_file_needs_plan_flag(self):
        self.gh(gh_pr(files=["README.md"], reviews=[("binh-dev", "APPROVED", "c"), ("chi-fe", "APPROVED", "c")]))
        result = self.record("plan-approved")
        self.assertEqual(2, result.returncode)
        self.assertIn("pass --plan", result.stderr)
        result = self.record("plan-approved", PR, "--plan", PLAN_PATH)
        self.assertEqual(1, result.returncode)
        self.assertIn(f"PR does not change {PLAN_PATH}", result.stderr)

    def test_verification_needs_qe_approval_on_local_head(self):
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "feat: x")
        head = git(self.root, "rev-parse", "HEAD").strip()
        self.gh(gh_pr(state="OPEN", head=head, reviews=[("dung-qe", "APPROVED", "old")]))
        result = self.record("verification-passed")
        self.assertEqual(1, result.returncode)
        self.assertIn("missing approval from one of qe", result.stderr)
        self.gh(gh_pr(state="OPEN", head="f" * 40, reviews=[("dung-qe", "APPROVED", "f" * 40)]))
        self.assertIn("is not local HEAD", self.record("verification-passed").stderr)
        self.gh(gh_pr(state="OPEN", head=head, reviews=[("dung-qe", "APPROVED", head)]))
        self.assertEqual(0, self.record("verification-passed").returncode)

    def test_gate_without_policy_records_member_email(self):
        result = self.record("orchestration-ready", "beads", "--epic", "ep-1")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("binh@corp.com", self.events()[-1]["actor"])
        self.assertEqual([], calls(self.bin))

    def test_identity_errors_exit_2(self):
        self.gh(gh_pr(files=[SPEC_PATH], reviews=[("an-ba", "APPROVED", "c")]))
        mismatch = self.record("requirement-confirmed", PR, "--actor", "someone@corp.com")
        self.assertEqual(2, mismatch.returncode)
        self.assertIn("does not match git user.email", mismatch.stderr)
        self.assertEqual(2, self.record("requirement-confirmed", "spec.md").returncode)
        git(self.root, "config", "user.email", "stranger@corp.com")
        self.assertIn("not in team.members", self.record("requirement-confirmed").stderr)
        self.assertEqual([], self.events())

    def test_host_unavailable_exits_2(self):
        self.gh(gh_pr(), exit_code=1)
        result = self.record("requirement-confirmed")
        self.assertEqual(2, result.returncode)
        self.assertIn("gh auth login", result.stderr)
        self.assertEqual([], self.events())

    def test_team_check_reverifies_without_recording(self):
        self.gh(gh_pr(files=[SPEC_PATH], reviews=[("chi-fe", "APPROVED", "c")]))
        result = run_cli(self.root, "team", "check", PR, "--gate", "requirement_confirmed", env=self.env)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], self.events())


    def test_repo_slug_forms_compare_equal(self):
        for form in ("git@github.com:Org/App.git", "ssh://git@github.com/org/app", "https://github.com/org/app.git",
                     "https://github.com/org/app/pull/7"):
            with self.subTest(form):
                self.assertEqual("github.com/org/app", repo_slug(form))
        self.assertEqual("gitlab.corp.com/group/app", repo_slug(MR))
        self.assertEqual("gitlab.corp.com/group/pull/app",
                         repo_slug("https://gitlab.corp.com/group/pull/app/-/merge_requests/3"))
        self.assertNotEqual(repo_slug("https://gitlab.corp.com/group/pull/other/-/merge_requests/3"),
                            repo_slug("git@gitlab.corp.com:group/pull/app.git"))

    def test_pr_from_another_repository_is_rejected(self):
        self.gh(gh_pr(url="https://github.com/other/app/pull/7", files=[SPEC_PATH],
                      reviews=[("an-ba", "APPROVED", "c")]))
        result = self.record("requirement-confirmed")
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn("PR belongs to github.com/other/app, not this repository (github.com/org/app)", result.stderr)
        self.assertEqual([], self.events())

    def test_no_origin_exits_2(self):
        git(self.root, "remote", "remove", "origin")
        self.gh(gh_pr(files=[SPEC_PATH], reviews=[("an-ba", "APPROVED", "c")]))
        result = self.record("requirement-confirmed")
        self.assertEqual(2, result.returncode)
        self.assertIn("no git remote 'origin'", result.stderr)

    def test_requirement_needs_exactly_one_spec_in_the_pr(self):
        other = ".planning/specs/other.md"
        self.gh(gh_pr(files=["README.md"], author="binh-dev", reviews=[("an-ba", "APPROVED", "c")]))
        result = self.record("requirement-confirmed")
        self.assertEqual(2, result.returncode)
        self.assertIn("pass --spec", result.stderr)
        self.gh(gh_pr(files=[SPEC_PATH, other], author="binh-dev", reviews=[("an-ba", "APPROVED", "c")]))
        result = self.record("requirement-confirmed")
        self.assertEqual(2, result.returncode)
        self.assertIn(f"found: {SPEC_PATH}, {other}", result.stderr)
        self.gh(gh_pr(files=[SPEC_PATH], author="binh-dev", reviews=[("an-ba", "APPROVED", "c")]))
        result = self.record("requirement-confirmed", PR, "--spec", other)
        self.assertEqual(1, result.returncode)
        self.assertIn(f"PR does not change {other}", result.stderr)
        self.gh(gh_pr(files=[SPEC_PATH, other], author="binh-dev", reviews=[("an-ba", "APPROVED", "c")]))
        self.assertEqual(0, self.record("requirement-confirmed", PR, "--spec", SPEC_PATH).returncode)

    def test_plan_gate_runs_check_plan(self):
        self.gh(gh_pr(files=[PLAN_PATH], reviews=[("binh-dev", "APPROVED", "c"), ("chi-fe", "APPROVED", "c")]))
        write(self.root, PLAN_PATH, "# Plan\n")
        result = self.record("plan-approved")
        self.assertEqual(1, result.returncode)
        self.assertIn("no '### Track N:' sections", result.stderr)
        write(self.root, PLAN_PATH, PLAN.replace("- Area: backend", "- Area: nowhere"))
        result = self.record("plan-approved")
        self.assertEqual(1, result.returncode)
        self.assertIn("unknown area nowhere", result.stderr)
        self.assertEqual([], self.events())

    def test_verification_ignores_approval_without_commit(self):
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "feat: x")
        head = git(self.root, "rev-parse", "HEAD").strip()
        self.gh(gh_pr(state="OPEN", head=head, reviews=[("dung-qe", "APPROVED", "")]))
        result = self.record("verification-passed")
        self.assertEqual(1, result.returncode)
        self.assertIn("missing approval from one of qe", result.stderr)


class TestWaivers(GateCase):
    def test_waiver_needs_a_gate_role(self):
        git(self.root, "config", "user.email", "em@corp.com")
        denied = run_cli(self.root, "unblock", "--gate", "plan_approved", "--reason", "r")
        self.assertEqual(2, denied.returncode)
        self.assertIn("needs one of the roles be_lead, fe_lead", denied.stdout + denied.stderr)
        git(self.root, "config", "user.email", "chi@corp.com")
        allowed = run_cli(self.root, "unblock", "--gate", "plan_approved", "--reason", "r")
        self.assertEqual(0, allowed.returncode, allowed.stdout + allowed.stderr)
        self.assertEqual(0, run_cli(self.root, "unblock", "--clear-blocker", "--reason", "r").returncode)


class TestRecordGitLab(GateCase):
    host = "gitlab"

    def glab(self, *, state: str = "merged", approvers: list[str] = (), author: str = "em-dev",
             files: list[str] = (PLAN_PATH, SPEC_PATH), reset: bool = True, status: str = "mergeable",
             patch: str | None = "p1", head: str = "h" * 40) -> None:
        base = "projects/42/merge_requests/12"
        fake_cli(self.bin, "glab", [
            {"argv": ["mr", "view", "12", "-R", "https://gitlab.corp.com/group/app"],
             "stdout": {"web_url": MR, "state": state, "merge_commit_sha": "m" * 40, "sha": head,
                        "author": {"username": author}, "project_id": 42, "description": "",
                        "detailed_merge_status": status}},
            {"argv": ["api", "--hostname", "gitlab.corp.com", f"{base}/approvals"],
             "stdout": {"approved_by": [{"user": {"username": login}} for login in approvers]}},
            {"argv": ["api", "--hostname", "gitlab.corp.com", f"{base}/changes"],
             "stdout": {"changes": [{"new_path": item} for item in files]}},
            {"argv": ["api", "--hostname", "gitlab.corp.com", "projects/42/approvals"],
             "stdout": {"reset_approvals_on_push": reset}},
            {"argv": ["api", "--hostname", "gitlab.corp.com", f"{base}/versions"],
             "stdout": [{"head_commit_sha": head, "patch_id_sha": patch}]},
        ])

    def test_merge_request_approvals(self):
        self.glab(approvers=["binh-dev"])
        self.assertIn("missing approval from fe_lead for area frontend", self.record("plan-approved", MR).stderr)
        self.glab(approvers=["binh-dev", "chi-fe"])
        result = self.record("plan-approved", MR)
        self.assertEqual(0, result.returncode, result.stderr)
        self.glab(state="opened", approvers=["an-ba"])
        self.assertIn("PR is open, not merged", self.record("requirement-confirmed", MR).stderr)

    def test_verification_needs_reset_on_push(self):
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "feat: x")
        head = git(self.root, "rev-parse", "HEAD").strip()
        common = {"head": head, "state": "opened", "approvers": ["dung-qe"]}
        self.glab(reset=False, **common)
        self.assertIn("reset_approvals_on_push", self.record("verification-passed", MR).stderr)
        self.glab(status="approvals_syncing", **common)
        self.assertIn("approvals still syncing; retry", self.record("verification-passed", MR).stderr)
        self.glab(patch=None, **common)
        self.assertIn("approvals still syncing; retry", self.record("verification-passed", MR).stderr)
        self.assertEqual([], self.events())
        self.glab(**common)
        result = self.record("verification-passed", MR)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_head_change_between_reads_is_unsettled(self):
        views = iter(["a" * 40, "b" * 40])
        base = "projects/42/merge_requests/12"

        def fake(host, argv, cwd):
            if argv[:2] == ["mr", "view"]:
                return {"web_url": MR, "state": "opened", "sha": next(views), "author": {"username": "em-dev"},
                        "project_id": 42, "detailed_merge_status": "mergeable"}
            return {f"{base}/approvals": {"approved_by": [{"user": {"username": "dung-qe"}}]},
                    f"{base}/changes": {"changes": []},
                    "projects/42/approvals": {"reset_approvals_on_push": True},
                    f"{base}/versions": [{"head_commit_sha": "a" * 40, "patch_id_sha": "p"}]}[argv[-1]]

        with mock.patch("workflow_core.team_host._run", side_effect=fake):
            pr = fetch_pr(MR, "gitlab", self.root)
        self.assertEqual((("dung-qe", ""),), pr.approvals)
        self.assertEqual("approvals still syncing; retry", pr.approval_note)

    def test_not_a_merge_request_url(self):
        fake_cli(self.bin, "glab", [])
        self.assertEqual(2, self.record("requirement-confirmed", "https://gitlab.corp.com/group/app").returncode)


class TestPlanChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_team_repo(Path(self.tmp.name) / "repo")
        self.team = load_team(yaml.safe_load((self.root / ".agent-workflow/config.yaml").read_text()))

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_tracks_reads_area_owner_and_files(self):
        path = write(self.root, PLAN_PATH, PLAN)
        tracks = plan_tracks(path)
        self.assertEqual([(1, "API", "backend", "em@corp.com",
                           ("services/auth/login.py", "tests/services/test_login.py")),
                          (2, "Form", "frontend", "", ("web/login.tsx",))],
                         [(t.number, t.title, t.area, t.owner, t.files) for t in tracks])
        self.assertEqual([], check_plan(self.team, path))

    def test_fenced_code_is_not_a_track(self):
        sample = "```markdown\n### Track 9: Sample\n- Area: nowhere\n## Integration\n```\n"
        path = write(self.root, PLAN_PATH, PLAN.replace("### Track 2: Form", sample + "\n### Track 2: Form"))
        self.assertEqual([1, 2], [track.number for track in plan_tracks(path)])
        self.assertEqual("frontend", plan_tracks(path)[1].area)

    def test_check_plan_findings(self):
        bad = (PLAN.replace("- Area: frontend\n", "").replace("em@corp.com", "chi@corp.com")
               .replace("`services/auth/login.py`", "`services/auth/login.py`, `web/shared.ts`"))
        path = write(self.root, PLAN_PATH, bad)
        self.assertEqual(["Track 1: web/shared.ts is outside area backend",
                          "Track 1: owner chi@corp.com holds no role allowed in area backend",
                          "Track 2: missing Area:"], check_plan(self.team, path))
        result = run_cli(self.root, "team", "check-plan", str(path))
        self.assertEqual(1, result.returncode)


if __name__ == "__main__":
    unittest.main()

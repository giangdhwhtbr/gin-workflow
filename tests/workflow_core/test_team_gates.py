"""Role-gated gate recording: PR/MR evidence through fake gh/glab, waivers, `team check`, and plan checks."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import PLAN, TEAM, calls, fake_cli, gh_pr, git, make_team_repo, path_with, run_cli, write  # noqa: E402
from workflow_core.configuration import resolve_effective_config  # noqa: E402
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

    def check_ship(self, evidence: str = PR):
        return run_cli(self.root, "team", "check", evidence, "--gate", "ship", env=self.env)

    def events(self) -> list[dict]:
        path = self.root / ".agent-workflow/runtime/events.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.is_file() else []

    def bd(self, beads: dict[str, dict]) -> None:
        """A fake bd: `show <id> --json` answers from `beads`; `list ... --json` returns []; updates succeed."""
        rules = [{"argv": ["show", bead], "stdout": [row]} for bead, row in beads.items()]
        rules += [{"argv": ["show"], "exit": 1, "stderr": "not found"}, {"argv": ["list"], "stdout": []},
                  {"argv": ["update"], "stdout": ""}]
        fake_cli(self.bin, "bd", rules)

    def bd_updates(self) -> list[list[str]]:
        return [call for call in calls(self.bin) if call[:2] == ["bd", "update"]]


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

    def test_requirement_confirmed_picks_the_numbered_spec_delta(self):
        delta = "docs/changes/ep-1-login/02-spec-delta.md"
        write(self.root, delta, "# Spec Delta\n")
        self.gh(gh_pr(author="binh-dev", files=["docs/changes/ep-1-login/01-proposal.md", delta],
                      reviews=[("an-ba", "APPROVED", "c1")]))
        result = self.record("requirement-confirmed")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(delta, self.events()[-1]["payload"]["artifact"])

    def test_requirement_confirmed_picks_a_spec_delta_from_before_numbering(self):
        delta = "docs/changes/ep-1-login/spec-delta.md"
        write(self.root, delta, "# Spec Delta\n")
        self.gh(gh_pr(author="binh-dev", files=[delta], reviews=[("an-ba", "APPROVED", "c1")]))
        self.assertEqual(0, self.record("requirement-confirmed").returncode)
        self.assertEqual(delta, self.events()[-1]["payload"]["artifact"])

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

    def test_ship_needs_qe_approval_on_local_head(self):
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "feat: x")
        head = git(self.root, "rev-parse", "HEAD").strip()
        self.gh(gh_pr(state="OPEN", head=head, reviews=[("dung-qe", "APPROVED", "old")]))
        result = self.check_ship()
        self.assertEqual(1, result.returncode)
        self.assertIn("missing approval from one of qe", result.stdout)
        self.gh(gh_pr(state="OPEN", head="f" * 40, reviews=[("dung-qe", "APPROVED", "f" * 40)]))
        self.assertIn("is not local HEAD", self.check_ship().stdout)
        self.gh(gh_pr(state="OPEN", head=head, reviews=[("dung-qe", "APPROVED", head)]))
        self.assertEqual(0, self.check_ship().returncode)

    def test_check_lists_only_head_approvers_for_ship(self):
        head = "h" * 40
        self.gh(gh_pr(state="OPEN", head=head, reviews=[("binh-dev", "APPROVED", "old"), ("dung-qe", "APPROVED", head)]))

        def approvers(gate: str) -> set[str]:
            out = run_cli(self.root, "team", "check", PR, "--gate", gate, "--format", "json", env=self.env)
            return {row["login"] for row in json.loads(out.stdout)["approvers"]}

        self.assertEqual({"dung-qe"}, approvers("ship"))
        self.assertEqual({"binh-dev", "dung-qe"}, approvers("roadmap"))

    def test_deprecated_verification_passed_key_maps_to_ship(self):
        team = TEAM.format(host="github").replace("    ship: [qe]\n", "    verification_passed: [qe]\n")
        root = make_team_repo(Path(self.tmp.name) / "legacy-repo", team=team)
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "feat: x")
        head = git(root, "rev-parse", "HEAD").strip()
        self.gh(gh_pr(state="OPEN", head=head, reviews=[]))
        result = run_cli(root, "team", "check", PR, "--gate", "ship", env=self.env)
        self.assertEqual(1, result.returncode)
        self.assertIn("missing approval from one of qe", result.stdout)
        self.assertIn("team.approvals.verification_passed is deprecated", result.stderr)

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
                self.assertEqual("github.com/org/app", repo_slug(form, pr=form.endswith("/7")))
        self.assertEqual("gitlab.corp.com/group/app", repo_slug(MR, pr=True))
        for namespace in ("group/pull/app", "group/pull/123/app", "group/sub/pull/5"):
            with self.subTest(namespace):
                remote = repo_slug(f"git@gitlab.corp.com:{namespace}.git")
                self.assertEqual(f"gitlab.corp.com/{namespace}", remote)
                self.assertEqual(remote, repo_slug(f"https://gitlab.corp.com/{namespace}/-/merge_requests/3/diffs",
                                                   pr=True))
        self.assertNotEqual(repo_slug("https://gitlab.corp.com/group/pull/123/other/-/merge_requests/3", pr=True),
                            repo_slug("git@gitlab.corp.com:group/pull/123/app.git"))

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

    def test_shipped_needs_approval_on_the_merged_pr_head(self):
        write(self.root, ".agent-workflow/config.yaml",
              (self.root / ".agent-workflow/config.yaml").read_text() + "providers:\n  task_tracking: beads\n")
        resolve_effective_config(self.root)
        self.bd({"w": {"id": "w", "issue_type": "task", "status": "closed", "metadata": {}}})
        self.assertEqual(0, run_cli(self.root, "record", "orchestration-ready", "--evidence", "w", "--workflow-id", "w",
                                    "--epic", "w", env=self.env).returncode)
        sha = self.record("shipped", "m" * 40)
        self.assertEqual(2, sha.returncode)
        self.assertIn("shipped needs the PR URL as --evidence in team mode", sha.stderr)
        self.gh(gh_pr(state="MERGED", head="f" * 40, author="em-dev", reviews=[("dung-qe", "APPROVED", "old")]))
        older = self.record("shipped")
        self.assertEqual(1, older.returncode)
        self.assertIn("missing approval from one of qe", older.stderr)
        self.gh(gh_pr(state="MERGED", head="f" * 40, author="em-dev",
                      reviews=[("binh-dev", "APPROVED", "old"), ("dung-qe", "APPROVED", "f" * 40)]))
        result = self.record("shipped")
        self.assertEqual(0, result.returncode, result.stderr)
        event = self.events()[-1]
        self.assertEqual(("delivery.shipped", "m" * 40, PR), (event["event_type"], event["payload"]["merge_commit"],
                                                              event["payload"]["pr_url"]))
        self.assertEqual(["dung-qe"], [a["login"] for a in event["payload"]["approvers"]])
        self.assertNotIn("is not local HEAD", result.stderr)
        update = next(u for u in self.bd_updates() if u[2:4] == ["w", "--set-metadata"])
        self.assertEqual(PR, json.loads(update[4].removeprefix("gates="))["shipped"]["pr_url"])

    def test_shipped_on_a_closed_unmerged_pr_gives_one_reason(self):
        self.bd({"w": {"id": "w", "issue_type": "task", "status": "closed", "metadata": {}}})
        self.assertEqual(0, run_cli(self.root, "record", "orchestration-ready", "--evidence", "w", "--workflow-id", "w",
                                    "--epic", "w", env=self.env).returncode)
        self.gh(gh_pr(state="CLOSED", head="f" * 40, author="em-dev", reviews=[("dung-qe", "APPROVED", "f" * 40)]))
        result = self.record("shipped")
        self.assertEqual(1, result.returncode)
        self.assertIn("PR is closed, not merged", result.stderr)
        self.assertEqual(1, result.stderr.count("PR is closed"), result.stderr)

    def test_ship_ignores_approval_without_commit(self):
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "feat: x")
        head = git(self.root, "rev-parse", "HEAD").strip()
        self.gh(gh_pr(state="OPEN", head=head, reviews=[("dung-qe", "APPROVED", "")]))
        result = self.check_ship()
        self.assertEqual(1, result.returncode)
        self.assertIn("missing approval from one of qe", result.stdout)


class TestSharedGates(GateCase):
    """Team mode with Beads: `record` mirrors gate proofs into the epic bead; `state` reads them back."""

    def setUp(self):
        super().setUp()
        write(self.root, ".agent-workflow/config.yaml",
              (self.root / ".agent-workflow/config.yaml").read_text() + "providers:\n  task_tracking: beads\n")
        resolve_effective_config(self.root)

    def test_record_writes_the_proof_into_the_epic_bead(self):
        self.gh(gh_pr(author="em-dev", files=[PLAN_PATH], reviews=[("binh-dev", "APPROVED", "c"),
                                                                    ("chi-fe", "APPROVED", "c")]))
        self.bd({"e-1": {"id": "e-1", "issue_type": "epic", "status": "open", "metadata": {}}})
        result = run_cli(self.root, "record", "plan-approved", "--evidence", PR, "--workflow-id", "e-1", env=self.env)
        self.assertEqual(0, result.returncode, result.stderr)
        update = self.bd_updates()[-1]
        self.assertEqual(["bd", "update", "e-1", "--set-metadata"], update[:4])
        gates = json.loads(update[4].removeprefix("gates="))
        proof = gates["plan_approved"]
        self.assertEqual((PR, "m" * 40, ["binh@corp.com", "chi@corp.com"], "binh@corp.com"),
                         (proof["pr_url"], proof["merge_commit"], proof["approvers"], proof["actor"]))
        self.assertRegex(proof["at"], r"^\d{4}-\d{2}-\d{2}T")

    def test_state_reads_a_gate_from_the_epic_bead(self):
        proof = {"pr_url": PR, "merge_commit": "m" * 40, "approvers": ["binh@corp.com"], "actor": "binh@corp.com",
                 "at": "2026-11-01T00:00:00Z"}
        self.bd({"e-1": {"id": "e-1", "issue_type": "epic", "status": "open",
                         "metadata": {"gates": json.dumps({"plan_approved": proof})}}})
        state = json.loads(run_cli(self.root, "state", "--workflow-id", "e-1", "--format", "json", env=self.env).stdout)
        self.assertEqual("satisfied", state["gates"]["plan_approved"])
        self.assertEqual("unmet", state["gates"]["requirement_confirmed"])

    def test_orchestration_ready_seeds_the_epic_and_labels_it(self):
        self.gh(gh_pr(author="binh-dev", files=[SPEC_PATH], reviews=[("an-ba", "APPROVED", "c1")]))
        self.bd({"e-2": {"id": "e-2", "issue_type": "epic", "status": "open", "metadata": {}}})
        confirmed = self.record("requirement-confirmed")
        self.assertEqual(0, confirmed.returncode, confirmed.stderr)
        self.assertIn("warning: gate requirement_confirmed proven locally; no epic bead to share it", confirmed.stderr)
        ready = run_cli(self.root, "record", "orchestration-ready", "--evidence", "w", "--workflow-id", "w",
                        "--epic", "e-2", env=self.env)
        self.assertEqual(0, ready.returncode, ready.stderr)
        updates = self.bd_updates()
        self.assertIn(["bd", "update", "e-2", "--add-label", "workflow:w"], updates)
        gates = next(json.loads(u[4].removeprefix("gates=")) for u in updates if u[2] == "e-2" and u[3] == "--set-metadata")
        self.assertEqual(PR, gates["requirement_confirmed"]["pr_url"])

    def test_state_finds_the_epic_by_workflow_label(self):
        proof = {"pr_url": PR, "merge_commit": "m" * 40, "approvers": ["an@corp.com"], "actor": "binh@corp.com",
                 "at": "2026-11-01T00:00:00Z"}
        epic = {"id": "e-3", "issue_type": "epic", "status": "open", "labels": ["workflow:w"],
                "metadata": {"gates": json.dumps({"requirement_confirmed": proof})}}
        self.bd({"e-3": epic})
        fake_cli(self.bin, "bd", json.loads((self.bin / "bd.json").read_text())[:-2]
                 + [{"argv": ["list", "--label", "workflow:w"], "stdout": [epic]}, {"argv": ["list"], "stdout": []},
                    {"argv": ["update"], "stdout": ""}])
        state = json.loads(run_cli(self.root, "state", "--workflow-id", "w", "--format", "json", env=self.env).stdout)
        self.assertEqual("satisfied", state["gates"]["requirement_confirmed"])

    def test_state_warns_when_a_proven_gate_has_no_epic(self):
        self.gh(gh_pr(author="binh-dev", files=[SPEC_PATH], reviews=[("an-ba", "APPROVED", "c1")]))
        self.bd({})
        self.assertEqual(0, self.record("requirement-confirmed").returncode)
        state = json.loads(run_cli(self.root, "state", "--workflow-id", "w", "--format", "json", env=self.env).stdout)
        self.assertIn("gate requirement_confirmed proven locally; no epic bead to share it", state["warnings"])

    def test_bead_write_failure_still_records(self):
        self.gh(gh_pr(author="binh-dev", files=[SPEC_PATH], reviews=[("an-ba", "APPROVED", "c1")]))
        fake_cli(self.bin, "bd", [{"argv": ["show", "e-1"], "stdout": [{"id": "e-1", "metadata": {}}]},
                                  {"argv": ["list"], "stdout": []},
                                  {"argv": ["update"], "exit": 1, "stderr": "dolt: connection refused"}])
        result = run_cli(self.root, "record", "requirement-confirmed", "--evidence", PR, "--workflow-id", "e-1",
                         env=self.env)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("warning: gate recorded locally; could not write it to e-1", result.stderr)
        self.assertEqual("requirement.confirmed", self.events()[-1]["event_type"])

    def test_tracker_failure_keeps_the_local_value_and_warns(self):
        fake_cli(self.bin, "bd", [{"argv": [], "exit": 1, "stderr": "dolt: connection refused"}])
        state = json.loads(run_cli(self.root, "state", "--workflow-id", "e-1", "--format", "json", env=self.env).stdout)
        self.assertEqual("unmet", state["gates"]["plan_approved"])
        self.assertTrue(any("tracker unavailable" in w for w in state["warnings"]), state["warnings"])

    def test_solo_mode_never_writes_gates(self):
        root = make_team_repo(Path(self.tmp.name) / "solo", team="", extra="providers:\n  task_tracking: beads\n")
        resolve_effective_config(root)
        self.bd({})
        self.assertEqual(0, run_cli(root, "record", "plan-approved", "--evidence", PLAN_PATH, "--workflow-id", "w",
                                    "--actor", "me", env=self.env).returncode)
        self.assertEqual([], self.bd_updates())
        before = len(calls(self.bin))
        self.assertEqual(0, run_cli(root, "state", "--workflow-id", "w", "--format", "json", env=self.env).returncode)
        self.assertEqual([], [c for c in calls(self.bin)[before:] if c[0] == "bd"])

    def test_orchestration_ready_without_epic_touches_no_bead(self):
        self.bd({})
        result = run_cli(self.root, "record", "orchestration-ready", "--evidence", "w", "--workflow-id", "w",
                         env=self.env)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], self.bd_updates())


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


ROADMAP_TEAM = TEAM.format(host="github").replace(
    "    em@corp.com:", "    lan@corp.com: {roles: [pm], login: lan-pm}\n    em@corp.com:").replace(
    "    ship: [qe]\n", "    ship: [qe]\n    roadmap: [pm]\n")
ROADMAP_PATH = ".planning/roadmap.md"


class TestRoadmapApproval(GateCase):
    def setUp(self):
        super().setUp()
        self.root = make_team_repo(Path(self.tmp.name) / "roadmap-repo", team=ROADMAP_TEAM)

    def check(self):
        return run_cli(self.root, "team", "check", PR, "--gate", "roadmap", env=self.env)

    def test_pm_approval_of_a_merged_roadmap_pr_passes_without_recording(self):
        self.gh(gh_pr(author="binh-dev", files=[ROADMAP_PATH], reviews=[("lan-pm", "APPROVED", "c")]))
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], self.events())

    def test_rejections(self):
        cases = [
            (gh_pr(author="binh-dev", files=[ROADMAP_PATH], reviews=[("an-ba", "APPROVED", "c")]),
             "missing approval from one of pm"),
            (gh_pr(author="lan-pm", files=[ROADMAP_PATH], reviews=[("lan-pm", "APPROVED", "c")]),
             "missing approval from one of pm"),
            (gh_pr(author="binh-dev", files=["README.md"], reviews=[("lan-pm", "APPROVED", "c")]),
             f"PR does not change {ROADMAP_PATH}"),
            (gh_pr(state="OPEN", author="binh-dev", files=[ROADMAP_PATH], reviews=[("lan-pm", "APPROVED", "c")]),
             "not merged"),
        ]
        for pr, reason in cases:
            with self.subTest(reason=reason):
                self.gh(pr)
                result = self.check()
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertIn(reason, result.stdout)

    def test_sdd_layout_uses_docs_roadmap(self):
        root = make_team_repo(Path(self.tmp.name) / "sdd-repo", team=ROADMAP_TEAM,
                              extra="artifacts:\n  layout: sdd\n")
        self.gh(gh_pr(author="binh-dev", files=["docs/roadmap.md"], reviews=[("lan-pm", "APPROVED", "c")]))
        result = run_cli(root, "team", "check", PR, "--gate", "roadmap", env=self.env)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_roadmap_role_held_by_no_member_is_a_config_error(self):
        team = TEAM.format(host="github").replace("    ship: [qe]\n",
                                                  "    ship: [qe]\n    roadmap: [pm]\n")
        root = make_team_repo(Path(self.tmp.name) / "no-pm-repo", team=team)
        result = run_cli(root, "team", "check", PR, "--gate", "roadmap", env=self.env)
        self.assertEqual(2, result.returncode)
        self.assertIn("team.approvals.roadmap: role pm is held by no member", result.stderr)


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

    def test_ship_needs_reset_on_push(self):
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "feat: x")
        head = git(self.root, "rev-parse", "HEAD").strip()
        common = {"head": head, "state": "opened", "approvers": ["dung-qe"]}
        self.glab(reset=False, **common)
        self.assertIn("reset_approvals_on_push", (lambda r: r.stdout + r.stderr)(self.check_ship(MR)))
        self.glab(status="approvals_syncing", **common)
        self.assertIn("approvals still syncing; retry", (lambda r: r.stdout + r.stderr)(self.check_ship(MR)))
        self.glab(patch=None, **common)
        self.assertIn("approvals still syncing; retry", (lambda r: r.stdout + r.stderr)(self.check_ship(MR)))
        self.assertEqual([], self.events())
        self.glab(**common)
        result = self.check_ship(MR)
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
                          (2, "Form", "frontend", "chi@corp.com", ("web/login.tsx",))],
                         [(t.number, t.title, t.area, t.owner, t.files) for t in tracks])
        self.assertEqual([], check_plan(self.team, path))

    def test_local_mode_requires_owner(self):
        path = write(self.root, PLAN_PATH, PLAN.replace("- Owner: chi@corp.com\n", ""))
        self.assertIn("Track 2: missing Owner: (required when Beads are not shared)", check_plan(self.team, path))
        config = yaml.safe_load((self.root / ".agent-workflow/config.yaml").read_text())
        config["team"]["beads_sync"] = {"remote": "file:///tmp/x"}
        self.assertEqual([], check_plan(load_team(config), path))

    def test_fenced_code_is_not_a_track(self):
        sample = "```markdown\n### Track 9: Sample\n- Area: nowhere\n## Integration\n```\n"
        path = write(self.root, PLAN_PATH, PLAN.replace("### Track 2: Form", sample + "\n### Track 2: Form"))
        self.assertEqual([1, 2], [track.number for track in plan_tracks(path)])
        self.assertEqual("frontend", plan_tracks(path)[1].area)

    def test_behavior_bullets_outside_files_are_not_files(self):
        plan = PLAN.replace("- Modify: `web/login.tsx:10-20`\n",
                            "- Modify: `web/login.tsx:10-20`\n\n**Steps:**\n"
                            "   - **Modify:** the row's button opens \"...\" filled from `GET /:id`, then saves\n")
        path = write(self.root, PLAN_PATH, plan)
        self.assertEqual(("web/login.tsx",), plan_tracks(path)[1].files)
        self.assertEqual([], check_plan(self.team, path))

    def test_area_and_owner_after_a_files_block_are_metadata(self):
        plan = PLAN.replace("**Metadata:**\n- Area: frontend\n- Owner: chi@corp.com\n\n**Files:**\n- Modify: `web/login.tsx:10-20`\n",
                            "**Files:**\n- Modify: `web/login.tsx:10-20`\n- **Area**: frontend\n- **Owner**: chi@corp.com\n")
        path = write(self.root, PLAN_PATH, plan)
        self.assertEqual((2, "frontend", "chi@corp.com", ("web/login.tsx",)),
                         (lambda t: (t.number, t.area, t.owner, t.files))(plan_tracks(path)[1]))
        self.assertEqual([], check_plan(self.team, path))

    def test_plan_schema_files_block_ignores_notes(self):
        plan = ("# Plan: Login\n\n## Tasks\n\n### Track 1: API\n- **Area**: backend\n- **Owner**: em@corp.com\n"
                "- **Files**:\n  - Create `services/auth/login.py`\n"
                "  - Modify `services/auth/session.py:10-20` (the `refresh` helper next to `web/shared.ts`)\n"
                "  - Test `tests/services/test_login.py`, `tests/services/test_session.py`\n"
                "- **Acceptance criteria**: `web/login.tsx` is untouched\n\n## Integration\n")
        path = write(self.root, PLAN_PATH, plan)
        self.assertEqual(("services/auth/login.py", "services/auth/session.py",
                          "tests/services/test_login.py", "tests/services/test_session.py"),
                         plan_tracks(path)[0].files)
        self.assertEqual([], check_plan(self.team, path))

    def test_check_plan_findings(self):
        bad = (PLAN.replace("- Area: frontend\n", "").replace("em@corp.com", "chi@corp.com")
               .replace("`services/auth/login.py`", "`services/auth/login.py`, `web/shared.ts`"))
        path = write(self.root, PLAN_PATH, bad)
        self.assertEqual(["Track 1: web/shared.ts is outside area backend",
                          "Track 1: owner chi@corp.com holds no role allowed in area backend",
                          "Track 2: missing Area:"], check_plan(self.team, path))
        result = run_cli(self.root, "team", "check-plan", str(path))
        self.assertEqual(1, result.returncode)

    def test_a_file_in_two_tracks_is_rejected(self):
        plan = PLAN.replace("- Modify: `web/login.tsx:10-20`\n",
                            "- Modify: `web/login.tsx:10-20`\n- Modify: `services/auth/login.py`\n") + \
            "\n### Track 3: Docs\n**Metadata:**\n- Area: backend\n- Owner: em@corp.com\n\n**Files:**\n" \
            "- Modify: `services/auth/login.py:1-5`\n"
        path = write(self.root, PLAN_PATH, plan)
        self.assertIn("`services/auth/login.py` is listed by tracks 1, 2 and 3", check_plan(self.team, path))
        self.assertEqual(1, run_cli(self.root, "team", "check-plan", str(path)).returncode)


if __name__ == "__main__":
    unittest.main()

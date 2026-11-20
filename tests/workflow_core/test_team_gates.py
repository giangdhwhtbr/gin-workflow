"""Role-gated gate recording: PR/MR evidence through fake gh/glab, waivers, `team check`, and plan checks."""

from __future__ import annotations

import os
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import LAUNCHER, PLAN, TEAM, calls, fake_cli, gh_pr, git, make_team_repo, path_with, write  # noqa: E402
# One test per subcommand keeps the subprocess; the rest run gin in this process.
from team_fixtures import run_cli as run_cli_subprocess, run_cli_in_process as run_cli  # noqa: E402
from workflow_core.configuration import ConfigValidationError, resolve_effective_config, validate_portable_config  # noqa: E402
from workflow_core.epic_kind import KINDS  # noqa: E402
from workflow_core.team import (  # noqa: E402
    can_waive, check_lane_plan, check_plan, check_plan_repos, gate_roles, has_policy, load_team, plan_lanes, plan_tracks, policy_for, repo_slug,
    verify_gate)
from workflow_core.workspace import Workspace, repos_from  # noqa: E402
from workflow_core.team_host import fetch_pr  # noqa: E402

import yaml  # noqa: E402

PR = "https://github.com/org/app/pull/7"
MR = "https://gitlab.corp.com/group/app/-/merge_requests/12"
PLAN_PATH = ".planning/plans/2026-10-03-login.md"
WORKSPACE = """workspace:
  repos:
    - {path: services/api, url: u1, shape: backend}
    - {path: apps/web, url: u2, shape: frontend}
    - {path: legacy/portal, url: u3, frozen: true}
    - {path: .beads, url: u4, shape: beads}
"""
SPEC_PATH = ".planning/specs/2026-10-03-login-design.md"

LANES = """# Plan: Login

## Lanes

### Lane api
- **Owner**: em@corp.com
- **Area**: backend
- **Scope**: the login API
- **Acceptance criteria**: POST /login answers 200 or 401
- **Contracts**: produces `POST /login`

### Lane web
- **Owner**: chi@corp.com
- **Area**: frontend
- **Scope**: the login form
- **Acceptance criteria**: the form posts to /login
- **Contracts**: consumes `POST /login`
- **Depends on lanes**: api

## Contracts

- `POST /login`: request `{"email": str, "password": str}`; 200 `{"session": str}`; 401.

## Tasks

## Integration
- Branch: feat/login
"""


def lanes_plan(*blocks: str) -> str:
    """A plan whose `## Lanes` holds `blocks` and that has no track."""
    return "# Plan\n\n## Lanes\n\n" + "\n".join(blocks) + "\n## Tasks\n"


MIXED = LANES.replace("## Tasks\n\n", PLAN[PLAN.index("## Tasks"):PLAN.index("## Integration")])



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
        """A fake bd: `show <id> --json` answers from `beads`, else bd's not-found; `list ... --json` returns [];
        updates succeed."""
        rules = [{"argv": ["show", bead], "stdout": [row]} for bead, row in beads.items()]
        rules += [{"argv": ["show"], "exit": 1, "stderr": 'Error fetching w: no issue found matching "w"\n'},
                  {"argv": ["list"], "stdout": []},
                  {"argv": ["update"], "stdout": ""}]
        fake_cli(self.bin, "bd", rules)

    def bd_updates(self) -> list[list[str]]:
        return [call for call in calls(self.bin) if call[:2] == ["bd", "update"]]


class TestRecordGitHub(GateCase):
    def test_plan_approved_needs_the_lead_of_each_declared_lane_area(self):
        write(self.root, PLAN_PATH, LANES)
        self.gh(gh_pr(files=[PLAN_PATH], reviews=[("binh-dev", "APPROVED", "c")]))
        result = self.record("plan-approved")
        self.assertEqual(1, result.returncode)
        self.assertIn("missing approval from fe_lead for area frontend", result.stderr)
        self.gh(gh_pr(files=[PLAN_PATH], reviews=[("binh-dev", "APPROVED", "c"), ("chi-fe", "APPROVED", "c")]))
        self.assertEqual(0, self.record("plan-approved").returncode)

    def test_plan_approved_with_an_open_lane_question_needs_the_plan_file(self):
        write(self.root, PLAN_PATH, LANES)
        questions = "# Login\n\nEpic: w\n\n## Open Technical Questions\n\n- TQ-4 (lane api): Which cache?\n"
        write(self.root, SPEC_PATH, questions)
        self.gh(gh_pr(files=[PLAN_PATH], reviews=[("binh-dev", "APPROVED", "c"), ("chi-fe", "APPROVED", "c")]))
        result = self.record("plan-approved")
        self.assertEqual(1, result.returncode)
        self.assertIn("questions marked for a lane need the plan file as --plan or --evidence", result.stderr)
        self.assertEqual([], calls(self.bin))
        write(self.root, SPEC_PATH, questions + "- TQ-5: Which queue?\n")
        result = self.record("plan-approved", PR, "--plan", PLAN_PATH)
        self.assertEqual(1, result.returncode)
        self.assertIn("plan-approved refused: open technical questions", result.stderr)
        write(self.root, SPEC_PATH, questions)
        result = self.record("plan-approved", PR, "--plan", PLAN_PATH)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_requirement_confirmed_by_ba_is_recorded_with_proof(self):
        self.gh(gh_pr(author="binh-dev", files=[SPEC_PATH], reviews=[("an-ba", "APPROVED", "c1")]))
        result = run_cli_subprocess(self.root, "record", "requirement-confirmed", "--evidence", PR, "--workflow-id", "w",
                                    env=self.env)
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
        update = next(u for u in self.bd_updates() if u[2:4] == ["w", "--set-metadata"] and '"shipped"' in u[4])
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
        state = json.loads(run_cli_subprocess(self.root, "state", "--workflow-id", "e-1", "--format", "json",
                                              env=self.env).stdout)
        self.assertEqual("satisfied", state["gates"]["plan_approved"])
        self.assertEqual("unmet", state["gates"]["requirement_confirmed"])

    @unittest.skipIf(os.name == "nt", "runs a #! stub script, which needs POSIX")
    def test_standalone_shipped_stays_unknown_when_the_tracker_read_fails(self):
        # The shared-gates reads succeed (first two `bd show`); the later closed-check read fails.
        proof = {"pr_url": PR, "merge_commit": "m" * 40, "approvers": ["an@corp.com"], "actor": "binh@corp.com",
                 "at": "2026-11-01T00:00:00Z"}
        bead = [{"id": "e-1", "issue_type": "task", "status": "closed", "metadata": {"gates": json.dumps({"shipped": proof})}}]
        self.bin.mkdir(parents=True, exist_ok=True)
        script = self.bin / "bd"
        script.write_text(f"#!/bin/sh\n[ \"$1\" = list ] && echo '[]' && exit 0\n"
                          f"n=$(cat \"$0.n\" 2>/dev/null || echo 0); echo $((n+1)) > \"$0.n\"\n"
                          f"[ $n -lt 2 ] && echo '{json.dumps(bead)}' && exit 0\necho boom >&2; exit 1\n")
        script.chmod(0o755)
        state = json.loads(run_cli(self.root, "state", "--workflow-id", "e-1", "--format", "json", env=self.env).stdout)
        self.assertEqual("unknown", state["gates"]["shipped"])

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

    def test_orchestration_ready_writes_its_own_gate(self):
        self.bd({"e-2": {"id": "e-2", "issue_type": "epic", "status": "open", "metadata": {}}})
        ready = run_cli(self.root, "record", "orchestration-ready", "--evidence", "w", "--workflow-id", "w",
                        "--epic", "e-2", env=self.env)
        self.assertEqual(0, ready.returncode, ready.stderr)
        writes = [json.loads(u[4].removeprefix("gates=")) for u in self.bd_updates()
                  if u[2] == "e-2" and u[3] == "--set-metadata"]
        gate = writes[-1]["orchestration_ready"]
        self.assertEqual("e-2", gate["epic"])
        self.assertRegex(gate["at"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertTrue(gate["actor"])

    def test_state_reads_orchestration_ready_from_the_epic_bead(self):
        gate = {"actor": "binh@corp.com", "at": "2026-11-01T00:00:00Z", "epic": "e-1"}
        self.bd({"e-1": {"id": "e-1", "issue_type": "epic", "status": "open",
                         "metadata": {"gates": json.dumps({"orchestration_ready": gate})}}})
        state = json.loads(run_cli(self.root, "state", "--workflow-id", "e-1", "--format", "json", env=self.env).stdout)
        self.assertEqual("satisfied", state["gates"]["orchestration_ready"])

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
        self.assertEqual(0, run_cli(root, "record", "orchestration-ready", "--evidence", "w", "--workflow-id", "w",
                                    "--epic", "e-9", "--actor", "me", env=self.env).returncode)
        self.assertEqual([], self.bd_updates())

    def test_orchestration_ready_without_epic_touches_no_bead(self):
        self.bd({})
        result = run_cli(self.root, "record", "orchestration-ready", "--evidence", "w", "--workflow-id", "w",
                         env=self.env)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], self.bd_updates())


class TestWaivers(GateCase):
    def test_waiver_needs_a_gate_role(self):
        git(self.root, "config", "user.email", "em@corp.com")
        denied = run_cli_subprocess(self.root, "unblock", "--gate", "plan_approved", "--reason", "r")
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


class TestHostCliResolution(GateCase):
    def test_host_runs_the_cli_that_tool_resolves(self):
        fake = fake_cli(self.bin, "gh", [{"argv": ["pr", "view", PR], "stdout": gh_pr()}])
        with mock.patch("workflow_core.team_host.tool", return_value=str(fake)) as tool, \
                mock.patch("shutil.which", return_value=None):
            pr = fetch_pr(PR, "github", self.root)
        self.assertEqual("merged", pr.state)
        tool.assert_called_once_with("gh", self.root)


class TestPlanChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_team_repo(Path(self.tmp.name) / "repo")
        self.team = load_team(yaml.safe_load((self.root / ".agent-workflow/config.yaml").read_text()))

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_lanes_reads_the_declarations(self):
        path = write(self.root, PLAN_PATH, LANES)
        self.assertEqual([("api", "em@corp.com", ("backend",), "", ()),
                          ("web", "chi@corp.com", ("frontend",), "", ("api",))],
                         [(lane.name, lane.owner, lane.areas, lane.repo, lane.depends) for lane in plan_lanes(path)])
        plain = lanes_plan("### Lane `api`\n- Owner: `em@corp.com`\n- Area: backend\n- Area: frontend\n"
                           "- Repo: services/api\n- Depends on lanes: web, `qa`\n")
        self.assertEqual([("api", "em@corp.com", ("backend", "frontend"), "services/api", ("web", "qa"))],
                         [(lane.name, lane.owner, lane.areas, lane.repo, lane.depends)
                          for lane in plan_lanes(write(self.root, PLAN_PATH, plain))])
        fenced = "```markdown\n## Lanes\n\n### Lane x\n- Owner: em@corp.com\n```\n"
        self.assertEqual([], plan_lanes(write(self.root, PLAN_PATH, PLAN + fenced)))
        self.assertEqual([], plan_lanes(write(self.root, PLAN_PATH, PLAN)))

    def test_a_plan_with_lanes_and_no_track_passes(self):
        path = write(self.root, PLAN_PATH, LANES)
        self.assertEqual([], plan_tracks(path))
        self.assertEqual([], check_plan(self.team, path))
        result = run_cli(self.root, "team", "check-plan", str(path))
        self.assertEqual((0, "ok"), (result.returncode, result.stdout.strip()), result.stderr)
        self.assertEqual([f"{path}: no '### Track N:' sections"],
                         check_plan(self.team, write(self.root, PLAN_PATH, "# Plan\n\n## Lanes\n\n## Tasks\n")))

    def test_lane_declaration_findings(self):
        good = "### Lane api\n- Owner: em@corp.com\n- Area: backend\n"
        cases = [
            (lanes_plan("### Lane api\n- Area: backend\n"), "lane api: missing Owner:"),
            (lanes_plan("### Lane API\n- Owner: em@corp.com\n- Area: backend\n"), "lane API: invalid lane name"),
            (lanes_plan("### Lane t3\n- Owner: em@corp.com\n- Area: backend\n"), "lane t3: invalid lane name"),
            (lanes_plan(good, good), "lane api: declared twice"),
            (lanes_plan("### Lane api\n- Owner: chi@corp.com\n- Area: backend\n"),
             "lane api: owner chi@corp.com holds no role allowed in area backend"),
            (lanes_plan("### Lane api\n- Owner: zed@corp.com\n- Area: backend\n"),
             "lane api: owner zed@corp.com is not in team.members"),
            (lanes_plan("### Lane api\n- Owner: em@corp.com\n- Area: nowhere\n"), "lane api: unknown area nowhere"),
            (lanes_plan("### Lane api\n- Owner: em@corp.com\n"), "lane api: missing Area:"),
            (lanes_plan(good + "- Depends on lanes: web\n"), "lane api: Depends on lanes: web is not a declared lane"),
        ]
        for text, finding in cases:
            with self.subTest(finding):
                self.assertEqual([finding], check_plan(self.team, write(self.root, PLAN_PATH, text)))

    def test_tracks_are_checked_against_their_declared_lane(self):
        self.assertEqual([], check_plan(self.team, write(self.root, PLAN_PATH, MIXED)))
        cases = [
            (MIXED.replace("- Lane: api", "- Lane: ops"), "Track 1: lane ops is not declared in ## Lanes"),
            (MIXED.replace("- Owner: em@corp.com\n- Lane: api", "- Owner: binh@corp.com\n- Lane: api"),
             "Track 1: Owner: binh@corp.com is not the owner of lane api (em@corp.com)"),
            (MIXED.replace("- Lane: api\n", "- Lane: api\n- Repo: services/a\n"),
             "Track 1: Repo: services/a is not the repository of lane api (.)"),
        ]
        for text, finding in cases:
            with self.subTest(finding):
                self.assertEqual([finding], check_plan(self.team, write(self.root, PLAN_PATH, text)))
        other_area = MIXED.replace("### Lane api\n- **Owner**: em@corp.com\n- **Area**: backend",
                                   "### Lane api\n- **Owner**: em@corp.com\n- **Area**: frontend")
        self.assertIn("Track 1: area backend is not an area of lane api",
                      check_plan(self.team, write(self.root, PLAN_PATH, other_area)))

    def test_a_plan_without_lanes_is_checked_as_before(self):
        self.assertEqual([], check_plan(self.team, write(self.root, PLAN_PATH, PLAN)))
        self.assertIn("Track 1: missing Lane:",
                      check_plan(self.team, write(self.root, PLAN_PATH, PLAN.replace("- Lane: api\n", ""))))

    def test_plan_tracks_reads_area_owner_and_files(self):
        path = write(self.root, PLAN_PATH, PLAN)
        tracks = plan_tracks(path)
        self.assertEqual([(1, "API", "backend", "em@corp.com",
                           ("services/auth/login.py", "tests/services/test_login.py")),
                          (2, "Form", "frontend", "chi@corp.com", ("web/login.tsx",))],
                         [(t.number, t.title, t.area, t.owner, t.files) for t in tracks])
        self.assertEqual([], check_plan(self.team, path))

    def test_lane_is_parsed_and_checked(self):
        path = write(self.root, PLAN_PATH, PLAN)
        self.assertEqual(["api", "web"], [t.lane for t in plan_tracks(path)])
        self.assertEqual([], check_plan(self.team, path))
        bold = write(self.root, PLAN_PATH, PLAN.replace("- Lane: api", "- **Lane**: `api`"))
        self.assertEqual("api", plan_tracks(bold)[0].lane)

    def test_missing_and_invalid_lane(self):
        path = write(self.root, PLAN_PATH, PLAN.replace("- Lane: api\n", ""))
        self.assertIn("Track 1: missing Lane:", check_plan(self.team, path))
        for name in ("API", "t3", "-x"):
            path = write(self.root, PLAN_PATH, PLAN.replace("- Lane: api", f"- Lane: {name}"))
            self.assertIn(f"Track 1: invalid lane {name}", check_plan(self.team, path))

    def test_lane_needs_one_owner_and_one_repository(self):
        one = PLAN.replace("- Lane: web", "- Lane: api")
        self.assertIn("lane api: tracks 1 and 2 have different owners",
                      check_plan(self.team, write(self.root, PLAN_PATH, one)))
        same = one.replace("- Owner: chi@corp.com", "- Owner: em@corp.com").replace(
            "- Lane: api\n\n**Files:**\n- Create", "- Lane: api\n- Repo: services/a\n\n**Files:**\n- Create")
        self.assertIn("lane api: tracks 1 and 2 are in different repositories",
                      check_plan(self.team, write(self.root, PLAN_PATH, same)))
        config = yaml.safe_load((self.root / ".agent-workflow/config.yaml").read_text())
        config["team"]["beads_sync"] = {"remote": "file:///tmp/x"}
        unowned = one.replace("- Owner: chi@corp.com\n", "")
        self.assertIn("lane api: tracks 1 and 2 have different owners",
                      check_plan(load_team(config), write(self.root, PLAN_PATH, unowned)))

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
        plan = PLAN.replace("**Metadata:**\n- Area: frontend\n- Owner: chi@corp.com\n- Lane: web\n\n**Files:**\n- Modify: `web/login.tsx:10-20`\n",
                            "**Files:**\n- Modify: `web/login.tsx:10-20`\n- **Area**: frontend\n- **Owner**: chi@corp.com\n- **Lane**: web\n")
        path = write(self.root, PLAN_PATH, plan)
        self.assertEqual((2, "frontend", "chi@corp.com", ("web/login.tsx",)),
                         (lambda t: (t.number, t.area, t.owner, t.files))(plan_tracks(path)[1]))
        self.assertEqual([], check_plan(self.team, path))

    def test_plan_schema_files_block_ignores_notes(self):
        plan = ("# Plan: Login\n\n## Tasks\n\n### Track 1: API\n- **Area**: backend\n- **Owner**: em@corp.com\n- **Lane**: api\n"
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
        result = run_cli_subprocess(self.root, "team", "check-plan", str(path))
        self.assertEqual(1, result.returncode)

    def test_plan_tracks_reads_repo(self):
        plan = (PLAN.replace("- Owner: em@corp.com\n", "- Owner: em@corp.com\n- **Repo**: `services/api`\n")
                .replace("- Owner: chi@corp.com\n", "- Owner: chi@corp.com\n- Repo: apps/web\n"))
        path = write(self.root, PLAN_PATH, plan)
        self.assertEqual(["services/api", "apps/web"], [track.repo for track in plan_tracks(path)])
        self.assertEqual("", plan_tracks(write(self.root, PLAN_PATH, PLAN))[0].repo)

    def test_check_plan_repos_findings(self):
        space = Workspace(self.root, repos_from(yaml.safe_load(WORKSPACE)))
        plan = ("# Plan\n\n## Tasks\n\n"
                "### Track 1: None\n- **Files**:\n  - Modify `services/api/a.py`\n\n"
                "### Track 2: Unknown\n- **Repo**: `services/billing`\n- **Files**:\n  - Modify `services/billing/a.py`\n\n"
                "### Track 3: Frozen\n- **Repo**: `legacy/portal`\n- **Files**:\n  - Modify `legacy/portal/a.php`\n\n"
                "### Track 4: Outside\n- **Repo**: `services/api`\n- **Files**:\n"
                "  - Modify `services/api/b.py`, `apps/web/b.tsx`\n\n"
                "### Track 5: Beads\n- **Repo**: `.beads`\n- **Files**:\n  - Modify `.beads/x.jsonl`\n\n"
                "### Track 6: Fine\n- **Repo**: `apps/web`\n- **Files**:\n  - Modify `apps/web/c.tsx`\n\n"
                "## Integration\n")
        path = write(self.root, PLAN_PATH, plan)
        self.assertEqual(["Track 1: missing Repo:",
                          "Track 2: Repo: services/billing is not in workspace.repos",
                          "Track 3: Repo: legacy/portal is frozen",
                          "Track 4: `apps/web/b.tsx` is outside repo services/api",
                          "Track 5: Repo: .beads is the beads repository"], check_plan_repos(space, path))

    def test_plan_tracks_reads_paths(self):
        # R2: Reads: in both spellings, absent, and repeated
        def reads(line: str) -> tuple[str, ...]:
            plan = PLAN.replace("- Owner: em@corp.com\n", "- Owner: em@corp.com\n" + line, 1)
            return plan_tracks(write(self.root, PLAN_PATH, plan))[0].reads
        self.assertEqual(("legacy/portal", "apps/web"), reads("- **Reads**: `legacy/portal`, `apps/web`\n"))
        self.assertEqual(("legacy/portal", "apps/web"), reads("- Reads: legacy/portal, apps/web\n"))
        self.assertEqual(("apps/web",), reads("- Reads: apps/web, `apps/web`,\n"))
        self.assertEqual((), reads(""))

    def test_check_plan_repos_reads_findings(self):
        # R3: unknown, beads, and own repository; frozen is allowed; findings follow the Repo: ones
        space = Workspace(self.root, repos_from(yaml.safe_load(WORKSPACE)))
        plan = ("# Plan\n\n## Tasks\n\n"
                "### Track 1: Fine\n- **Repo**: `services/api`\n- **Reads**: `legacy/portal`, `apps/web`\n"
                "- **Files**:\n  - Modify `services/api/a.py`\n\n"
                "### Track 2: Bad\n- **Repo**: `apps/web`\n- **Reads**: `services/billing`, `.beads`, `apps/web`\n"
                "- **Files**:\n  - Modify `apps/web/a.tsx`\n\n"
                "### Track 3: None\n- **Reads**: nope\n- **Files**:\n  - Modify `x`\n\n"
                "## Integration\n")
        path = write(self.root, PLAN_PATH, plan)
        self.assertEqual(["Track 2: Reads: services/billing is not in workspace.repos",
                          "Track 2: Reads: .beads is the beads repository",
                          "Track 2: Reads: apps/web is the track's own Repo:",
                          "Track 3: missing Repo:",
                          "Track 3: Reads: nope is not in workspace.repos"], check_plan_repos(space, path))

    def test_check_plan_cli_reports_reads_findings(self):
        root = make_team_repo(Path(self.tmp.name) / "ws", extra=WORKSPACE)
        plan = ("# Plan\n\n## Tasks\n\n### Track 1: API\n- **Repo**: `services/api`\n"
                "- **Reads**: `services/billing`\n- **Files**:\n  - Modify `services/api/a.py`\n\n## Integration\n")
        path = write(root, PLAN_PATH, plan)
        result = run_cli(root, "team", "check-plan", str(path), "--format", "json")
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn("Track 1: Reads: services/billing is not in workspace.repos", json.loads(result.stdout)["findings"])

    def test_check_plan_cli_adds_workspace_findings(self):
        root = make_team_repo(Path(self.tmp.name) / "ws", extra=WORKSPACE)
        path = write(root, PLAN_PATH, PLAN)
        result = run_cli(root, "team", "check-plan", str(path), "--format", "json")
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertEqual(["Track 1: missing Repo:", "Track 2: missing Repo:"], json.loads(result.stdout)["findings"])

    def test_a_file_in_two_tracks_is_rejected(self):
        plan = PLAN.replace("- Modify: `web/login.tsx:10-20`\n",
                            "- Modify: `web/login.tsx:10-20`\n- Modify: `services/auth/login.py`\n") + \
            "\n### Track 3: Docs\n**Metadata:**\n- Area: backend\n- Owner: em@corp.com\n\n**Files:**\n" \
            "- Modify: `services/auth/login.py:1-5`\n"
        path = write(self.root, PLAN_PATH, plan)
        self.assertIn("`services/auth/login.py` is listed by tracks 1, 2 and 3", check_plan(self.team, path))
        self.assertEqual(1, run_cli(self.root, "team", "check-plan", str(path)).returncode)


CHILD_PR = "https://github.com/org/api/pull/9"
CHILD_WORKSPACE = """workspace:
  repos:
    - {path: services/api, url: "git@github.com:org/api.git", shape: backend}
    - {path: apps/web, url: "git@github.com:org/web.git", shape: frontend}
"""


class TestChildShipGate(GateCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_team_repo(Path(self.tmp.name) / "repo", host=self.host, extra=CHILD_WORKSPACE)
        self.bin = Path(self.tmp.name) / "bin"
        self.env = path_with(self.bin)
        self.child = self.root / "services/api"
        self.child.mkdir(parents=True)
        git(self.child, "init", "-q", "-b", "main")
        git(self.child, "config", "user.email", "binh@corp.com")
        git(self.child, "config", "user.name", "T")
        git(self.child, "remote", "add", "origin", "git@github.com:org/api.git")
        git(self.child, "commit", "-q", "--allow-empty", "-m", "feat: api")
        self.head = git(self.child, "rev-parse", "HEAD").strip()

    def child_pr(self, head, state="OPEN", url=CHILD_PR):
        fake_cli(self.bin, "gh", [{"argv": ["pr", "view", url], "exit": 0,
                                   "stdout": gh_pr(url, state=state, head=head,
                                                   reviews=[("dung-qe", "APPROVED", head)])}])

    def run_in(self, cwd, *args):
        return subprocess.run([sys.executable, str(LAUNCHER), *args], cwd=cwd, text=True, capture_output=True,
                              env={**os.environ, **self.env}, check=False)

    def test_child_pr_passes_from_parent_child_and_worktree(self):
        self.child_pr(self.head)
        self.assertEqual(0, run_cli(self.root, "team", "check", CHILD_PR, "--gate", "ship", env=self.env).returncode)
        self.assertEqual(0, self.run_in(self.child, "team", "check", CHILD_PR, "--gate", "ship").returncode)
        worktree = Path(self.tmp.name) / "wt"
        git(self.child, "worktree", "add", "-q", "-b", "track", str(worktree))
        git(worktree, "commit", "-q", "--allow-empty", "-m", "feat: track")
        track_head = git(worktree, "rev-parse", "HEAD").strip()
        self.child_pr(track_head)
        self.assertEqual(0, self.run_in(worktree, "team", "check", CHILD_PR, "--gate", "ship").returncode)
        mismatch = self.run_in(self.child, "team", "check", CHILD_PR, "--gate", "ship")
        self.assertEqual(1, mismatch.returncode)
        self.assertIn("is not local HEAD", mismatch.stdout)

    def test_unlisted_repository_is_refused_with_accepted_ids(self):
        other = "https://github.com/org/other/pull/3"
        self.child_pr(self.head, url=other)
        result = run_cli(self.root, "team", "check", other, "--gate", "ship", env=self.env)
        self.assertEqual(1, result.returncode)
        self.assertIn("not this repository", result.stdout)
        self.assertIn("github.com/org/api", result.stdout)

    def test_uncloned_child_names_workspace_clone(self):
        url = "https://github.com/org/web/pull/4"
        self.child_pr(self.head, url=url)
        result = run_cli(self.root, "team", "check", url, "--gate", "ship", env=self.env)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("gin workspace clone apps/web", result.stdout + result.stderr)

    def test_record_shipped_accepts_a_merged_child_pr(self):
        write(self.root, ".agent-workflow/config.yaml",
              (self.root / ".agent-workflow/config.yaml").read_text() + "providers:\n  task_tracking: beads\n")
        resolve_effective_config(self.root)
        self.bd({"w": {"id": "w", "issue_type": "task", "status": "closed", "metadata": {}}})
        self.assertEqual(0, run_cli(self.root, "record", "orchestration-ready", "--evidence", "w", "--workflow-id", "w",
                                    "--epic", "w", env=self.env).returncode)
        self.child_pr(self.head, state="MERGED")
        result = run_cli(self.root, "record", "shipped", "--evidence", CHILD_PR, "--workflow-id", "w", env=self.env)
        self.assertEqual(0, result.returncode, result.stderr)

    def ship_ready(self, *prs: dict) -> None:
        """Beads on, a closed standalone bead w recorded orchestration-ready, and `gh pr view` answering each PR."""
        write(self.root, ".agent-workflow/config.yaml",
              (self.root / ".agent-workflow/config.yaml").read_text() + "providers:\n  task_tracking: beads\n")
        resolve_effective_config(self.root)
        self.bd({"w": {"id": "w", "issue_type": "task", "status": "closed", "metadata": {}}})
        self.assertEqual(0, run_cli(self.root, "record", "orchestration-ready", "--evidence", "w", "--workflow-id", "w",
                                    "--epic", "w", env=self.env).returncode)
        fake_cli(self.bin, "gh", [{"argv": ["pr", "view", pr["url"]], "stdout": pr} for pr in prs])

    def record_shipped(self, *urls: str):
        return run_cli(self.root, "record", "shipped", *(arg for url in urls for arg in ("--evidence", url)),
                       "--workflow-id", "w", env=self.env)

    def shipped_events(self) -> list[dict]:
        path = self.root / ".agent-workflow/runtime/events.jsonl"
        return [event for event in map(json.loads, path.read_text().splitlines())
                if event["event_type"] == "delivery.shipped"]

    def test_record_shipped_takes_one_pr_per_repository(self):
        """lean-lifecycle R3, R4, US-2: the parent and the child PR prove one shipped record."""
        self.ship_ready(gh_pr(PR, reviews=[("dung-qe", "APPROVED", "h" * 40)]),
                        gh_pr(CHILD_PR, head=self.head, reviews=[("dung-qe", "APPROVED", self.head)]))
        result = self.record_shipped(PR, CHILD_PR)
        self.assertEqual(0, result.returncode, result.stderr)
        [event] = self.shipped_events()
        expected = [{"pr_url": PR, "merge_commit": "m" * 40, "repository": "github.com/org/app"},
                    {"pr_url": CHILD_PR, "merge_commit": "m" * 40, "repository": "github.com/org/api"}]
        self.assertEqual((f"{PR}, {CHILD_PR}", PR, expected),
                         (event["payload"]["evidence"], event["payload"]["pr_url"], event["payload"]["pull_requests"]))
        update = next(u for u in self.bd_updates() if u[2:4] == ["w", "--set-metadata"] and '"shipped"' in u[4])
        proof = json.loads(update[4].removeprefix("gates="))["shipped"]
        self.assertEqual((PR, expected), (proof["pr_url"], proof["pull_requests"]))

    def test_two_prs_of_one_repository_record_nothing(self):
        other = "https://github.com/org/app/pull/8"
        self.ship_ready(gh_pr(PR, reviews=[("dung-qe", "APPROVED", "h" * 40)]),
                        gh_pr(other, reviews=[("dung-qe", "APPROVED", "h" * 40)]))
        result = self.record_shipped(PR, other)
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn(f"{other}: github.com/org/app is already covered by {PR}", result.stderr)
        self.assertEqual([], self.shipped_events())

    def test_one_unmerged_pr_refuses_both_naming_it(self):
        self.ship_ready(gh_pr(PR, reviews=[("dung-qe", "APPROVED", "h" * 40)]),
                        gh_pr(CHILD_PR, state="OPEN", head=self.head, reviews=[("dung-qe", "APPROVED", self.head)]))
        result = self.record_shipped(PR, CHILD_PR)
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn(f"{CHILD_PR}: PR is open, not merged", result.stderr)
        self.assertNotIn(f"{PR}:", result.stderr)
        self.assertEqual([], self.shipped_events())


class TestObjectPolicies(GateCase):
    """`{all, any}` approval policies and the sole-holder fallback (gin-workflow-approval-roles R1-R5)."""

    def use_policy(self, ship: str | None = None, *, plan: str | None = None, members: str = "") -> None:
        team = TEAM.format(host="github")
        if ship is not None:
            team = team.replace("    ship: [qe]\n", f"    ship: {ship}\n")
        if plan is not None:
            team = team.replace("    plan_approved: area_lead\n", f"    plan_approved: {plan}\n")
        team = team.replace("  areas:\n", members + "  areas:\n")
        write(self.root, ".agent-workflow/config.yaml", f"schema_version: '2.7'\n{team}")

    def ship_pr(self, author: str, *approvers: str) -> None:
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "--allow-empty", "-m", "feat: x")
        head = git(self.root, "rev-parse", "HEAD").strip()
        self.gh(gh_pr(state="OPEN", author=author, head=head, reviews=[(login, "APPROVED", head) for login in approvers]))

    def test_all_requires_each_role(self):
        self.use_policy("{all: [qe], any: [be_lead, fe_lead]}")
        self.ship_pr("an-ba", "binh-dev")
        result = self.check_ship()
        self.assertEqual(1, result.returncode)
        self.assertIn("missing approval from qe", result.stdout)
        self.ship_pr("an-ba", "dung-qe", "chi-fe")
        self.assertEqual(0, self.check_ship().returncode)

    def test_any_required_with_all(self):
        self.use_policy("{all: [qe], any: [be_lead, fe_lead]}")
        self.ship_pr("an-ba", "dung-qe")
        result = self.check_ship()
        self.assertEqual(1, result.returncode)
        self.assertIn("missing approval from one of be_lead, fe_lead", result.stdout)

    def test_list_policy_unchanged(self):
        self.use_policy("[qe, be_lead]")
        self.ship_pr("an-ba", "binh-dev")
        self.assertEqual(0, self.check_ship().returncode)

    def test_sole_holder_author_falls_back_to_any(self):
        self.use_policy("{all: [qe], any: [be_lead]}")
        self.ship_pr("dung-qe", "binh-dev")
        result = self.check_ship()
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("note: qe skipped: the author is its only holder", result.stdout)
        out = run_cli(self.root, "team", "check", PR, "--gate", "ship", "--format", "json", env=self.env)
        self.assertEqual(["qe skipped: the author is its only holder"], json.loads(out.stdout)["notes"])

    def test_sole_holder_fallback_still_requires_any(self):
        self.use_policy("{all: [qe], any: [be_lead]}")
        self.ship_pr("dung-qe", "chi-fe")
        result = self.check_ship()
        self.assertEqual(1, result.returncode)
        self.assertIn("missing approval from one of be_lead", result.stdout)

    def test_sole_holder_without_any_is_refused(self):
        self.use_policy("{all: [qe]}")
        self.ship_pr("dung-qe", "binh-dev")
        result = self.check_ship()
        self.assertEqual(1, result.returncode)
        self.assertIn("qe has no holder other than the author; add a holder or an `any` role", result.stdout)

    def test_second_holder_disables_fallback(self):
        self.use_policy("{all: [qe], any: [be_lead]}", members="    eve@corp.com: {roles: [qe], login: eve-qe}\n")
        self.ship_pr("dung-qe", "binh-dev")
        result = self.check_ship()
        self.assertEqual(1, result.returncode)
        self.assertIn("missing approval from qe", result.stdout)
        self.assertNotIn("skipped", result.stdout)

    def test_area_lead_author_substituted_by_other_lead(self):
        self.gh(gh_pr(author="binh-dev", files=[PLAN_PATH], reviews=[("chi-fe", "APPROVED", "c")]))
        result = run_cli(self.root, "team", "check", PR, "--gate", "plan_approved", env=self.env)
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("note: be_lead for area backend skipped: the author is its only holder; approved by fe_lead",
                      result.stdout)
        self.assertEqual(0, self.record("plan-approved").returncode)

    def test_area_lead_without_another_lead_approval_is_refused(self):
        self.gh(gh_pr(author="binh-dev", files=[PLAN_PATH], reviews=[("dung-qe", "APPROVED", "c")]))
        result = self.record("plan-approved")
        self.assertEqual(1, result.returncode)
        self.assertIn("missing approval from be_lead for area backend", result.stderr)

    def test_area_lead_with_a_second_holder_is_not_substituted(self):
        self.use_policy(members="    fay@corp.com: {roles: [be_lead], login: fay-be}\n")
        self.gh(gh_pr(author="binh-dev", files=[PLAN_PATH], reviews=[("chi-fe", "APPROVED", "c")]))
        result = self.record("plan-approved")
        self.assertEqual(1, result.returncode)
        self.assertIn("missing approval from be_lead for area backend", result.stderr)

    def test_area_lead_substitution_needs_another_area(self):
        solo = ("team:\n  members:\n    binh@corp.com: {roles: [be_lead], login: binh-dev}\n"
                "    chi@corp.com: {roles: [fe_lead], login: chi-fe}\n"
                "  areas:\n    backend: {paths: [\"services/**\", \"tests/services/**\"], lead: be_lead}\n"
                "  approvals:\n    plan_approved: area_lead\n")
        write(self.root, ".agent-workflow/config.yaml", f"schema_version: '2.7'\n{solo}")
        write(self.root, PLAN_PATH, PLAN.split("### Track 2")[0] + "## Integration\n- Branch: feat/login\n")
        self.gh(gh_pr(author="binh-dev", files=[PLAN_PATH], reviews=[("chi-fe", "APPROVED", "c")]))
        result = self.record("plan-approved")
        self.assertEqual(1, result.returncode)
        self.assertIn("missing approval from be_lead for area backend", result.stderr)

    def test_object_policy_unknown_key_is_refused(self):
        raw = yaml.safe_load(TEAM.format(host="github"))["team"]
        validate_portable_config({"schema_version": "2.7", "team": {**raw, "approvals": {"ship": {"all": ["qe"]}}}})
        for bad in ({"every": ["qe"]}, {}, {"all": "qe"}):
            with self.subTest(bad=bad), self.assertRaises(ConfigValidationError):
                validate_portable_config({"schema_version": "2.7", "team": {**raw, "approvals": {"ship": bad}}})

    def test_policy_roles_held_by_no_member_are_config_errors(self):
        from workflow_core.team import validate_team

        raw = yaml.safe_load(TEAM.format(host="github"))["team"]
        raw["approvals"] = {"ship": {"all": ["qe", "ghost"], "any": ["phantom"]}}
        errors = validate_team(raw)
        self.assertIn("team.approvals.ship: role ghost is held by no member", errors)
        self.assertIn("team.approvals.ship: role phantom is held by no member", errors)
        raw["approvals"] = {"ship": {"all": [], "any": []}}
        self.assertIn("team.approvals.ship: all and any are both empty", validate_team(raw))


class TestKindPolicies(unittest.TestCase):
    """epic-kinds R8: `requirement_confirmed` per epic kind; a single policy applies to every kind."""

    @staticmethod
    def team(requirement):
        raw = yaml.safe_load(TEAM.format(host="github"))
        raw["team"]["approvals"]["requirement_confirmed"] = requirement
        return load_team(raw)

    def test_policy_for_picks_the_kind_and_falls_back_to_capability(self):
        team = self.team({"capability": ["ba"], "technical": {"any": ["be_lead"]}})
        for kind, policy in ((None, ["ba"]), ("capability", ["ba"]), ("technical", {"any": ["be_lead"]}),
                             ("parity", ["ba"])):
            with self.subTest(kind=kind):
                self.assertEqual(policy, policy_for(team, "requirement_confirmed", kind))
        self.assertEqual("area_lead", policy_for(team, "plan_approved", "technical"))

    def test_single_policy_applies_to_every_kind(self):
        for policy in (["ba", "be_lead"], {"all": ["ba"], "any": ["be_lead"]}):
            team = self.team(policy)
            for kind in (None, *KINDS):
                with self.subTest(policy=policy, kind=kind):
                    self.assertEqual(policy, policy_for(team, "requirement_confirmed", kind))

    def test_waiver_and_policy_presence_follow_the_kind(self):
        team = self.team({"capability": ["ba"], "technical": ["be_lead"], "parity": []})
        lead, analyst = team.member("binh@corp.com"), team.member("an@corp.com")
        self.assertEqual({"be_lead"}, gate_roles("requirement_confirmed", team, "technical"))
        self.assertEqual((True, False), (can_waive(lead, "requirement_confirmed", team, "technical"),
                                         can_waive(lead, "requirement_confirmed", team)))
        self.assertEqual((True, False), (can_waive(analyst, "requirement_confirmed", team, "capability"),
                                         can_waive(analyst, "requirement_confirmed", team, "technical")))
        self.assertEqual((True, False), (has_policy("requirement_confirmed", team),
                                         has_policy("requirement_confirmed", team, "parity")))


class TestKindApproval(GateCase):
    """epic-kinds R4, R9, US-1, US-3: record, team check, and unblock use the policy of the epic's kind."""

    def setUp(self):
        super().setUp()
        self.configure("{capability: [ba], technical: [be_lead]}")
        self.gh(gh_pr(author="em-dev", files=[SPEC_PATH], reviews=[("binh-dev", "APPROVED", "c")]))

    def configure(self, requirement: str, extra: str = "") -> None:
        team = TEAM.format(host="github").replace("requirement_confirmed: [ba, be_lead, fe_lead]",
                                                  f"requirement_confirmed: {requirement}")
        write(self.root, ".agent-workflow/config.yaml",
              f"schema_version: '2.7'\nproviders:\n  task_tracking: beads\n{extra}{team}")
        resolve_effective_config(self.root)

    def epic(self, *labels: str) -> None:
        self.bd({"e-1": {"id": "e-1", "issue_type": "epic", "status": "open", "labels": list(labels), "metadata": {}}})

    def spec(self, kind: str = "") -> None:
        write(self.root, SPEC_PATH, "# Login\n\n" + (f"Kind: {kind}\n" if kind else ""))

    def record_epic(self):
        return run_cli(self.root, "record", "requirement-confirmed", "--evidence", PR, "--workflow-id", "e-1",
                       env=self.env)

    def check(self, *extra: str) -> tuple[int, dict]:
        result = run_cli(self.root, "team", "check", PR, "--gate", "requirement_confirmed", "--format", "json",
                         *extra, env=self.env)
        return result.returncode, json.loads(result.stdout)

    def test_technical_epic_is_confirmed_by_its_lead(self):
        self.epic("roadmap", "kind:technical")
        self.spec("technical")
        result = self.record_epic()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(SPEC_PATH, self.events()[-1]["payload"]["artifact"])

    def test_epic_and_spec_without_a_kind_need_the_capability_policy(self):
        self.epic("roadmap")
        self.spec()
        result = self.record_epic()
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn("missing approval from one of ba", result.stderr)
        self.assertEqual([], self.events())

    def test_spec_kind_decides_when_the_bead_has_none(self):
        self.epic("roadmap")
        self.spec("technical")
        result = self.record_epic()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_kind_mismatch_is_refused_naming_both(self):
        self.epic("kind:technical")
        self.spec("capability")
        for extra in ((), ("--spec", SPEC_PATH)):
            with self.subTest(extra=extra):
                result = run_cli(self.root, "record", "requirement-confirmed", "--evidence", PR, "--workflow-id", "e-1",
                                 *extra, env=self.env)
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertIn(f"kind mismatch: epic e-1 is kind:technical, spec {SPEC_PATH} says Kind: capability",
                              result.stderr)
        self.assertEqual([], self.events())

    def test_team_check_reports_the_kind(self):
        self.epic("kind:technical")
        self.spec("technical")
        code, payload = self.check("--workflow-id", "e-1")
        self.assertEqual((0, "ok", "technical"), (code, payload["status"], payload["kind"]))
        self.spec()
        code, payload = self.check()
        self.assertEqual((1, "capability", ["missing approval from one of ba"]),
                         (code, payload["kind"], payload["reasons"]))
        self.spec("capability")
        code, payload = self.check("--workflow-id", "e-1")
        self.assertEqual(1, code)
        self.assertEqual([f"kind mismatch: epic e-1 is kind:technical, spec {SPEC_PATH} says Kind: capability"],
                         payload["reasons"])

    def test_waiver_needs_a_role_of_the_epic_kind(self):
        def unblock():
            return run_cli(self.root, "unblock", "--gate", "requirement_confirmed", "--workflow-id", "e-1",
                           "--reason", "r", env=self.env)

        self.epic("kind:technical")
        allowed = unblock()
        self.assertEqual(0, allowed.returncode, allowed.stdout + allowed.stderr)
        self.epic("roadmap")
        denied = unblock()
        self.assertEqual(2, denied.returncode)
        self.assertIn("waiving requirement_confirmed needs one of the roles ba", denied.stdout + denied.stderr)

    def test_an_unreadable_epic_kind_refuses_record_and_check_and_waives_as_capability(self):
        """F-1: a failing tracker, or a missing Beads database in team mode, never lets the spec's Kind: pick the
        policy."""
        self.spec("technical")
        for failure in ("Error: failed to connect to dolt server", "Error: no beads database found"):
            with self.subTest(failure=failure):
                fake_cli(self.bin, "bd", [{"argv": ["show"], "exit": 1, "stderr": failure + "\n"},
                                          {"argv": ["list"], "stdout": []}, {"argv": ["update"], "stdout": ""}])
                reason = f"cannot read the kind of epic e-1: bd exited 1: {failure}"
                result = self.record_epic()
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertIn(reason, result.stderr)
                self.assertEqual([], self.events())
                code, payload = self.check("--workflow-id", "e-1")
                self.assertEqual((1, "rejected", [reason]), (code, payload["status"], payload["reasons"]))
                denied = run_cli(self.root, "unblock", "--gate", "requirement_confirmed", "--workflow-id", "e-1",
                                 "--reason", "r", env=self.env)
                self.assertEqual(2, denied.returncode)
                self.assertIn("waiving requirement_confirmed needs one of the roles ba", denied.stdout + denied.stderr)

    def test_an_invalid_or_doubled_kind_label_is_refused(self):
        """F-2: the bead's kind: label is validated, never taken unchecked."""
        self.spec()
        self.epic("kind:foo")
        code, payload = self.check("--workflow-id", "e-1")
        self.assertEqual((1, ["epic e-1: Kind: foo is not one of capability, technical, parity"]),
                         (code, payload["reasons"]))
        self.epic("kind:technical", "kind:capability")
        result = self.record_epic()
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn("epic e-1 has several kind labels: technical, capability", result.stderr)
        self.assertEqual([], self.events())

    def test_sdd_change_without_a_spec_delta_is_approved_through_its_proposal(self):
        """F-3, epic-kinds R6: a technical change may have no 02-spec-delta.md; the PR's proposal is the artifact."""
        self.configure("{capability: [ba], technical: [be_lead]}", "artifacts:\n  layout: sdd\n")
        change = "docs/changes/2026-11-12-cache"
        proposal = f"{change}/01-proposal.md"
        write(self.root, proposal, "# Proposal\n\nEpic: e-1\nKind: technical\n")
        self.gh(gh_pr(author="em-dev", files=[proposal, f"{change}/03-design.md"],
                      reviews=[("binh-dev", "APPROVED", "c")]))
        self.epic("kind:technical")
        code, payload = self.check("--workflow-id", "e-1")
        self.assertEqual((0, "ok", proposal, "technical"),
                         (code, payload["status"], payload["artifact"], payload["kind"]))
        self.epic("kind:capability")
        code, payload = self.check("--workflow-id", "e-1")
        self.assertEqual((1, [f"kind mismatch: epic e-1 is kind:capability, spec {proposal} says Kind: technical"]),
                         (code, payload["reasons"]))
        # A change that has a spec delta is approved through it, so a PR without the delta names no spec.
        write(self.root, f"{change}/02-spec-delta.md", "# Spec Delta\n")
        result = run_cli(self.root, "team", "check", PR, "--gate", "requirement_confirmed", env=self.env)
        self.assertEqual(2, result.returncode, result.stdout)
        self.assertIn("the PR must change exactly one spec file (found: none)", result.stderr)

    def test_host_for_one_kind_and_roles_for_the_other(self):
        """lean-lifecycle R1: a kind map may trust the host for capability epics and keep roles for technical ones."""
        self.configure("{capability: host, technical: [be_lead]}")
        self.gh(gh_pr(author="em-dev", files=[SPEC_PATH], reviews=[]))
        self.epic("kind:capability")
        self.spec("capability")
        code, payload = self.check("--workflow-id", "e-1")
        self.assertEqual((0, []), (code, payload["reasons"]))
        self.epic("kind:technical")
        self.spec("technical")
        code, payload = self.check("--workflow-id", "e-1")
        self.assertEqual((1, ["missing approval from one of be_lead"]), (code, payload["reasons"]))

    def test_a_policy_for_any_kind_needs_a_merged_pr(self):
        """F-4: with no approvers for technical epics, their requirement is still proven by a merged PR."""
        self.configure("{capability: [ba], technical: []}")
        self.epic("kind:technical")
        self.spec("technical")
        local = run_cli(self.root, "record", "requirement-confirmed", "--evidence", SPEC_PATH, "--workflow-id", "e-1",
                        env=self.env)
        self.assertEqual(2, local.returncode, local.stderr)
        self.assertIn("requirement_confirmed needs a PR/MR URL as --evidence in team mode", local.stderr)
        self.gh(gh_pr(author="em-dev", files=[SPEC_PATH], reviews=[]))
        result = self.record_epic()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual((PR, []), (self.events()[-1]["payload"]["pr_url"], self.events()[-1]["payload"]["approvers"]))


HOST_GATES = {"requirement_confirmed: [ba, be_lead, fe_lead]": "requirement_confirmed: host",
              "plan_approved: area_lead": "plan_approved: host", "ship: [qe]": "ship: host"}


class TestHostApprovals(GateCase):
    """lean-lifecycle R1, US-1: `host` trusts a merged PR; gin checks no approver, author, or head commit."""

    def configure(self, gates: dict[str, str] = HOST_GATES, extra: str = "") -> None:
        team = TEAM.format(host="github")
        for old, new in gates.items():
            team = team.replace(old, new)
        write(self.root, ".agent-workflow/config.yaml", f"schema_version: '2.7'\n{extra}{team}")
        if extra:
            resolve_effective_config(self.root)

    def test_record_shipped_trusts_a_merged_pr_and_refuses_an_open_one(self):
        self.configure(extra="providers:\n  task_tracking: beads\n")
        self.bd({"w": {"id": "w", "issue_type": "task", "status": "closed", "metadata": {}}})
        self.assertEqual(0, run_cli(self.root, "record", "orchestration-ready", "--evidence", "w", "--workflow-id", "w",
                                    "--epic", "w", env=self.env).returncode)
        self.gh(gh_pr(state="OPEN", author="em-dev", reviews=[]))
        refused = self.record("shipped")
        self.assertEqual(1, refused.returncode, refused.stderr)
        self.assertEqual("error: PR is open, not merged", refused.stderr.strip())
        self.gh(gh_pr(author="em-dev", reviews=[]))
        result = self.record("shipped")
        self.assertEqual(0, result.returncode, result.stderr)
        payload = self.events()[-1]["payload"]
        self.assertEqual((PR, [], [{"pr_url": PR, "merge_commit": "m" * 40, "repository": "github.com/org/app"}]),
                         (payload["pr_url"], payload["approvers"], payload["pull_requests"]))

    def test_team_check_ship_of_an_open_unapproved_pr_skips_the_head(self):
        self.configure()
        git(self.root, "commit", "-q", "--allow-empty", "-m", "feat: x")  # local HEAD is not the PR head
        self.gh(gh_pr(state="OPEN", author="em-dev", head="f" * 40, reviews=[]))
        result = self.check_ship()
        self.assertEqual((0, "ok (approvals are enforced by the host)"), (result.returncode, result.stdout.strip()))
        self.gh(gh_pr(state="CLOSED", author="em-dev", reviews=[]))
        self.assertEqual("PR is closed", self.check_ship().stdout.strip())

    def test_requirement_confirmed_needs_only_a_merged_pr_that_changes_the_spec(self):
        self.configure()
        self.gh(gh_pr(author="em-dev", files=["README.md"], reviews=[]))
        self.assertIn(f"PR does not change {SPEC_PATH}", self.record("requirement-confirmed", PR, "--spec",
                                                                     SPEC_PATH).stderr)
        self.gh(gh_pr(author="em-dev", files=[SPEC_PATH], reviews=[]))
        result = self.record("requirement-confirmed")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual((PR, []), (self.events()[-1]["payload"]["pr_url"], self.events()[-1]["payload"]["approvers"]))

    def test_plan_approved_still_runs_check_plan(self):
        self.configure()
        self.gh(gh_pr(author="em-dev", files=[PLAN_PATH], reviews=[]))
        write(self.root, PLAN_PATH, PLAN.replace("- Area: backend", "- Area: nowhere"))
        refused = self.record("plan-approved")
        self.assertEqual(1, refused.returncode)
        self.assertIn("unknown area nowhere", refused.stderr)
        write(self.root, PLAN_PATH, PLAN)
        self.assertEqual(0, self.record("plan-approved").returncode)

    def test_any_member_waives_a_host_gate(self):
        self.configure()
        git(self.root, "config", "user.email", "em@corp.com")
        for gate in ("requirement_confirmed", "plan_approved"):
            with self.subTest(gate=gate):
                result = run_cli(self.root, "unblock", "--gate", gate, "--reason", "r")
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_team_init_names_no_gate_without_a_policy_and_no_spec_approver(self):
        self.configure()
        result = run_cli(self.root, "team", "init")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("gates without a role policy", result.stdout)
        owners = (self.root / ".github/CODEOWNERS").read_text()
        self.assertIn("/.planning/specs/ @binh-dev @chi-fe\n", owners)  # the area leads only, no spec approver

    def test_a_pr_of_another_repository_is_refused_before_the_host_shortcut(self):
        self.configure()
        other = "https://github.com/org/other/pull/3"
        fake_cli(self.bin, "gh", [{"argv": ["pr", "view", other], "stdout": gh_pr(other, state="OPEN", reviews=[])}])
        result = self.check_ship(other)
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn("PR belongs to github.com/org/other, not this repository", result.stdout)

    def test_roadmap_host_needs_a_merged_pr_that_changes_the_roadmap(self):
        self.configure({"ship: [qe]\n": "ship: [qe]\n    roadmap: host\n"})
        check = ("team", "check", PR, "--gate", "roadmap")
        self.gh(gh_pr(author="binh-dev", files=[ROADMAP_PATH], reviews=[]))
        result = run_cli(self.root, *check, env=self.env)
        self.assertEqual((0, "ok (approvals are enforced by the host)"), (result.returncode, result.stdout.strip()))
        self.gh(gh_pr(state="OPEN", author="binh-dev", files=[ROADMAP_PATH], reviews=[]))
        refused = run_cli(self.root, *check, env=self.env)
        self.assertEqual((1, "PR is open, not merged"), (refused.returncode, refused.stdout.strip()))

    def test_a_role_policy_still_needs_its_approval(self):
        self.configure({"ship: [qe]": "ship: [be_lead]"})
        self.gh(gh_pr(state="OPEN", author="em-dev", reviews=[]))
        self.assertIn("missing approval from one of be_lead", self.check_ship().stdout)

    def test_host_is_the_only_new_string_policy(self):
        from workflow_core.team import validate_team

        raw = yaml.safe_load(TEAM.format(host="github"))["team"]
        approvals = {"requirement_confirmed": {"capability": "host", "technical": ["be_lead"]},
                     "plan_approved": "host", "ship": "host", "roadmap": "host"}
        validate_portable_config({"schema_version": "2.7", "team": {**raw, "approvals": approvals}})
        self.assertEqual([], validate_team({**raw, "approvals": approvals, "strict": True}))
        for gate in ("ship", "requirement_confirmed", "plan_approved", "roadmap"):
            with self.subTest(gate=gate), self.assertRaises(ConfigValidationError):
                validate_portable_config({"schema_version": "2.7", "team": {**raw, "approvals": {gate: "hosted"}}})


class TestBeforeMerge(GateCase):
    """team-progress R4: `verify_gate(before_merge=True, artifact_text=...)` checks an open PR the way `gin team
    pending` does; the defaults keep the checks of `gin record` and `gin team check`."""

    def setUp(self):
        super().setUp()
        self.team = load_team(yaml.safe_load((self.root / ".agent-workflow/config.yaml").read_text()))

    def verify(self, gate: str, url: str = PR, **options) -> list[str]:
        with mock.patch.dict(os.environ, self.env):
            return verify_gate(self.root, self.team, gate, url, **options)[2]

    def test_before_merge_drops_only_the_merged_requirement(self):
        self.gh(gh_pr(state="OPEN", files=[SPEC_PATH], author="binh-dev", reviews=[("dung-qe", "APPROVED", "c")]))
        missing = "missing approval from one of ba, be_lead, fe_lead"
        self.assertEqual(["PR is open, not merged", missing], self.verify("requirement_confirmed"))
        self.assertEqual([missing], self.verify("requirement_confirmed", before_merge=True))

    def test_before_merge_skips_the_local_head_of_ship_but_not_the_approval_on_the_pr_head(self):
        git(self.root, "commit", "-q", "--allow-empty", "-m", "feat: x")
        self.gh(gh_pr(state="OPEN", head="f" * 40, reviews=[("dung-qe", "APPROVED", "old")]))
        self.assertTrue(any("is not local HEAD" in reason for reason in self.verify("ship")))
        self.assertEqual(["missing approval from one of qe"], self.verify("ship", before_merge=True))

    def test_before_merge_keeps_the_repository_check(self):
        other = "https://github.com/other/app/pull/7"
        fake_cli(self.bin, "gh", [{"argv": ["pr", "view", other], "stdout": gh_pr(
            other, state="OPEN", author="em-dev", files=[SPEC_PATH], reviews=[("an-ba", "APPROVED", "c")])}])
        [reason] = self.verify("requirement_confirmed", other, before_merge=True)
        self.assertTrue(reason.startswith("PR belongs to github.com/other/app, not this repository"), reason)

    def test_artifact_text_stands_in_for_a_plan_missing_from_the_checkout(self):
        (self.root / PLAN_PATH).unlink()
        self.gh(gh_pr(state="OPEN", files=[PLAN_PATH], reviews=[("binh-dev", "APPROVED", "c")]))
        self.assertEqual([f"{PLAN_PATH} is not in this checkout; pull the merged plan"],
                         self.verify("plan_approved", before_merge=True))
        self.assertEqual(["missing approval from fe_lead for area frontend"],
                         self.verify("plan_approved", before_merge=True, artifact_text=PLAN))
        self.assertIn("Track 1: unknown area nowhere", self.verify(
            "plan_approved", before_merge=True, artifact_text=PLAN.replace("- Area: backend", "- Area: nowhere")))


LANE_PATH = ".planning/plans/2026-10-03-login.lane-api.md"
LANE_PLAN = """# Plan: Login API

Spec: .planning/specs/2026-10-03-login-design.md

## Tasks

### Track 1: API
- **Area**: backend
- **Owner**: em@corp.com
- **Lane**: api
- **Files**:
  - Create `services/auth/login.py`
  - Test `tests/services/test_login.py`

### Track 2: Session
- **Area**: backend
- **Owner**: em@corp.com
- **Lane**: api
- **Files**:
  - Create `services/auth/session.py`

## Integration
"""
QUESTIONS = "# Login\n\nEpic: w\n\n## Open Technical Questions\n\n- TQ-4 (lane api): Which cache?\n"


class TestLanePlanChecks(unittest.TestCase):
    """R7, R10, US-2, US-3: a lane plan is checked against its lane's declaration and its lane's questions."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = make_team_repo(Path(self.tmp.name) / "repo")
        self.team = load_team(yaml.safe_load((self.root / ".agent-workflow/config.yaml").read_text()))
        self.lead = write(self.root, PLAN_PATH, LANES)
        write(self.root, SPEC_PATH, QUESTIONS + "  Decision: redis.\n- TQ-5 (lane web): Which store?\n")

    def check(self, text: str = LANE_PLAN, relative: str = LANE_PATH) -> list[str]:
        return check_lane_plan(self.team, write(self.root, relative, text), self.root)

    def test_a_lane_plan_that_follows_its_lane_passes(self):
        self.assertEqual([], self.check())
        result = run_cli(self.root, "team", "check-plan", LANE_PATH, "--format", "json")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_another_lane_another_owner_or_a_file_outside_the_area_fails(self):
        second = LANE_PLAN.index("### Track 2")
        head, tail = LANE_PLAN[:second], LANE_PLAN[second:]
        cases = [
            (head + tail.replace("- **Lane**: api", "- **Lane**: web"), ["Track 2: lane web is not lane api"]),
            (head + tail.replace("- **Owner**: em@corp.com", "- **Owner**: binh@corp.com"),
             ["lane api: tracks 1 and 2 have different owners",
              "Track 2: Owner: binh@corp.com is not the owner of lane api (em@corp.com)"]),
            (head + tail.replace("`services/auth/session.py`", "`web/session.tsx`"),
             ["Track 2: web/session.tsx is outside area backend"]),
        ]
        for text, findings in cases:
            with self.subTest(findings[-1]):
                self.assertEqual(findings, self.check(text))
        result = run_cli(self.root, "team", "check-plan", LANE_PATH)
        self.assertEqual(1, result.returncode)
        self.assertIn("Track 2: web/session.tsx is outside area backend", result.stdout)

    def test_a_track_in_another_area_of_the_team_is_reported(self):
        second = LANE_PLAN.index("### Track 2")
        text = LANE_PLAN[:second] + LANE_PLAN[second:].replace("- **Area**: backend", "- **Area**: frontend")
        self.assertIn("Track 2: area frontend is not an area of lane api", self.check(text))

    def test_the_lead_plan_must_declare_the_lane_without_tracks(self):
        ops = self.check(relative=".planning/plans/2026-10-03-login.lane-ops.md")
        self.assertEqual([f"{self.root / '.planning/plans/2026-10-03-login.lane-ops.md'}: lane ops is not declared in "
                          f"{self.lead}"], ops)
        write(self.root, PLAN_PATH, MIXED)
        self.assertEqual([f"{self.root / LANE_PATH}: lane api has tracks in {self.lead}; the lead plans it there"],
                         self.check())
        self.lead.unlink()
        self.assertEqual([f"{self.root / LANE_PATH}: lead plan {self.lead} not found"], self.check())

    def test_an_open_question_of_the_lane_fails_and_others_are_ignored(self):
        write(self.root, SPEC_PATH, QUESTIONS + "- TQ-5 (lane web): Which store?\n- TQ-6: Which queue?\n")
        self.assertEqual([f"{SPEC_PATH}:7: TQ-4 (lane api) has no Decision:"], self.check())
        result = run_cli(self.root, "team", "check-plan", LANE_PATH)
        self.assertEqual(1, result.returncode)

    def test_the_lane_plan_names_its_design_doc(self):
        path = self.root / LANE_PATH
        self.assertEqual([f"{path}: missing Spec: <design doc path> line"],
                         self.check(LANE_PLAN.replace(f"Spec: {SPEC_PATH}\n", "")))
        self.assertEqual([f"{path}: Spec: .planning/specs/nope.md is not a file"],
                         self.check(LANE_PLAN.replace(SPEC_PATH, ".planning/specs/nope.md")))

    def test_a_malformed_lane_question_is_reported(self):
        write(self.root, SPEC_PATH, QUESTIONS + "- TQ-7 (lane BE): Which queue?\n")
        findings = self.check()
        self.assertTrue(any(item.startswith(f"{SPEC_PATH}:") and "not a question" in item for item in findings), findings)

    def test_the_spec_stays_inside_the_repository(self):
        (Path(self.tmp.name) / "outside.md").write_text("# Outside\n", encoding="utf-8")
        path = self.root / LANE_PATH
        self.assertEqual([f"{path}: Spec: ../outside.md is outside the repository"],
                         self.check(LANE_PLAN.replace(SPEC_PATH, "../outside.md")))


if __name__ == "__main__":
    unittest.main()

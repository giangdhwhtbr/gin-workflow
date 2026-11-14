"""`gin team pending` (team-progress R4, US-2): open gate pull requests and track pull requests with what they need.

`origin` stays the GitHub URL that `gin team check` compares pull requests with, so the git network calls (ls-remote,
fetch, show) are faked at `team_pending.git`; `gh` and `bd` are fake CLIs on PATH."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import PLAN, TEAM, calls, fake_cli, gh_pr, git, make_team_repo, path_with, write  # noqa: E402
from team_fixtures import run_cli_in_process as run_cli  # noqa: E402
from workflow_core import team_pending  # noqa: E402
from workflow_core.configuration import resolve_effective_config  # noqa: E402
from workflow_core.team import TeamError  # noqa: E402

REAL_GIT = team_pending.git
PR_SPEC, PR_PLAN, PR_SHIP, PR_TRACK = (f"https://github.com/org/app/pull/{number}" for number in (1, 2, 3, 4))
SPEC_PATH = ".planning/specs/2026-10-03-login-design.md"
PLAN_PATH = ".planning/plans/2026-10-03-login.md"
ASSET = ".planning/specs/assets/2026-10-03/login.png"  # binary: never read from the branch
TRACK = {"id": "e-1.2", "parent": "e-1", "status": "open", "description": f"Form\n\nPlan: {PLAN_PATH}, Track 2\n"}
CLOSED_TRACK = {**TRACK, "status": "closed"}
EPIC = {"id": "e-1", "issue_type": "epic", "status": "open", "description": "Login"}


class TestTopicOf(unittest.TestCase):
    def test_strips_the_date_from_the_plan_file_stem(self):
        self.assertEqual("team-progress", team_pending.topic_of(".planning/plans/2026-11-14-team-progress.md"))
        self.assertEqual("login", team_pending.topic_of("plans/login.md"))


class PendingCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = make_team_repo(Path(self.tmp.name) / "repo")
        resolve_effective_config(self.root)  # team mode defaults to Beads, so bead reads go to the fake bd
        self.bin = Path(self.tmp.name) / "bin"
        self.env = path_with(self.bin)
        self.branches: dict[str, dict[str, str] | None] = {}  # remote branch -> its files; None: fetch fails
        patcher = mock.patch.object(team_pending, "git", side_effect=self.fake_git)
        self.git = patcher.start()
        self.addCleanup(patcher.stop)
        self.bd()
        self.gh()

    def fake_git(self, root: Path, *argv: str) -> str:
        if argv[0] == "ls-remote":
            return "".join(f"{'a' * 40}\trefs/heads/{branch}\n" for branch in self.branches)
        if argv[0] == "fetch":
            self.fetched = self.branches.get(argv[-1].removeprefix("refs/heads/"))
            if self.fetched is None:
                raise TeamError(f"git fetch failed: fatal: couldn't find remote ref {argv[-1]}")
            return ""
        return self.fetched[argv[1].removeprefix("FETCH_HEAD:")]

    def bd(self, *beads: dict, labels: tuple[str, ...] = (), milestone_epics: tuple[str, ...] = ()) -> None:
        """`list` gives `beads`; `list --parent m-1` the epics of milestone m-1; `show e-1` an epic with `labels`."""
        fake_cli(self.bin, "bd", [
            {"argv": ["list"], "stdout": list(beads)},
            {"argv": ["list", "--parent", "m-1"], "stdout": [{"id": epic, "issue_type": "epic"}
                                                             for epic in milestone_epics]},
            {"argv": ["show", "e-1"], "stdout": [{"id": "e-1", "issue_type": "epic", "labels": list(labels)}]},
            {"argv": ["show"], "exit": 1, "stderr": 'Error: no issue found matching "x"\n'},
        ])

    def gh(self, *prs: tuple[str, dict], extra: tuple[dict, ...] = ()) -> None:
        """Each (branch, PR) answers `pr list --head <branch>` and `pr view <url>`; other branches have no PR."""
        rules = [{"argv": ["pr", "list"], "stdout": []}, *extra]
        for branch, pr in prs:
            rules += [{"argv": ["pr", "list", "--head", branch], "stdout": [
                         {"url": pr["url"], "state": pr["state"], "mergeCommit": pr["mergeCommit"]}]},
                      {"argv": ["pr", "view", pr["url"]], "stdout": pr}]
        fake_cli(self.bin, "gh", rules)

    def configure(self, old: str, new: str) -> None:
        write(self.root, ".agent-workflow/config.yaml", "schema_version: '2.7'\n" + TEAM.format(host="github")
              .replace(old, new))
        resolve_effective_config(self.root)

    def pending(self, *flags: str) -> list[dict]:
        result = run_cli(self.root, "team", "pending", "--format", "json", *flags, env=self.env)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)["pending"]


class TestGateRows(PendingCase):
    def test_open_spec_pr_is_requirement_confirmed_with_its_epic_and_only_the_missing_role(self):
        self.branches["spec/login"] = {SPEC_PATH: "# Login\n\nEpic: e-1\n"}
        self.gh(("spec/login", gh_pr(PR_SPEC, state="OPEN", author="binh-dev", files=[ASSET, SPEC_PATH],
                                     reviews=[("dung-qe", "APPROVED", "c1")])))
        self.assertEqual([{"gate": "requirement_confirmed", "branch": "spec/login", "url": PR_SPEC,
                           "author": "binh-dev", "epic": "e-1", "approvals": ["dung-qe"],
                           "missing": ["missing approval from one of ba, be_lead, fe_lead"], "notes": []}],
                         self.pending())
        self.assertEqual([("ls-remote", "--heads", "origin"), ("fetch", "--quiet", "origin", "refs/heads/spec/login"),
                          ("show", f"FETCH_HEAD:{SPEC_PATH}")], [call.args[1:] for call in self.git.call_args_list])

    def test_open_spec_pr_whose_approvals_meet_the_policy_misses_nothing(self):
        self.branches["spec/login"] = {SPEC_PATH: "# Login\n\nEpic: e-1\n"}
        self.gh(("spec/login", gh_pr(PR_SPEC, state="OPEN", author="binh-dev", files=[SPEC_PATH],
                                     reviews=[("an-ba", "APPROVED", "c1")])))
        self.assertEqual([], self.pending()[0]["missing"])

    def test_spec_row_applies_the_policy_of_the_epic_kind(self):
        self.configure("requirement_confirmed: [ba, be_lead, fe_lead]",
                       "requirement_confirmed: {capability: [ba], technical: [be_lead]}")
        self.bd(labels=("kind:technical",))
        self.branches["spec/login"] = {SPEC_PATH: "# Login\n\nEpic: e-1\n"}
        self.gh(("spec/login", gh_pr(PR_SPEC, state="OPEN", author="em-dev", files=[SPEC_PATH],
                                     reviews=[("an-ba", "APPROVED", "c1")])))
        self.assertEqual(["missing approval from one of be_lead"], self.pending()[0]["missing"])

    def test_open_plan_pr_names_the_missing_area_leads_from_the_plan_on_its_branch(self):
        self.branches["plan/login"] = {PLAN_PATH: f"{PLAN}\nEpic: e-1\n"}
        self.gh(("plan/login", gh_pr(PR_PLAN, state="OPEN", author="em-dev", files=[PLAN_PATH],
                                     reviews=[("binh-dev", "APPROVED", "c1")])))
        [row] = self.pending()
        self.assertFalse((self.root / PLAN_PATH).exists())
        self.assertEqual(("plan_approved", "e-1", ["binh-dev"], ["missing approval from fe_lead for area frontend"]),
                         (row["gate"], row["epic"], row["approvals"], row["missing"]))

    def test_merged_closed_or_absent_pull_requests_give_no_row(self):
        self.branches.update({"spec/merged": {}, "spec/closed": {}, "plan/none": {}})
        self.gh(("spec/merged", gh_pr(PR_SPEC, state="MERGED")), ("spec/closed", gh_pr(PR_PLAN, state="CLOSED")))
        self.assertEqual([], self.pending())
        self.assertEqual(1, self.git.call_count)  # ls-remote only: nothing is fetched for a closed PR

    def test_open_epic_whose_tracks_all_closed_gives_a_ship_row(self):
        self.bd(EPIC, CLOSED_TRACK)
        git(self.root, "commit", "-q", "--allow-empty", "-m", "feat: x")  # local HEAD is not the PR head
        self.gh(("feat/login", gh_pr(PR_SHIP, state="OPEN", author="binh-dev", files=["services/auth/login.py"])))
        [row] = self.pending()
        self.assertEqual(("ship", "feat/login", "e-1", ["missing approval from one of qe"]),
                         (row["gate"], row["branch"], row["epic"], row["missing"]))
        self.assertEqual([["gh", "pr", "list", "--head", "feat/login"]],
                         [call[:5] for call in calls(self.bin) if call[:3] == ["gh", "pr", "list"]])

    def test_closed_epic_gives_no_ship_candidate(self):
        self.bd({**EPIC, "status": "closed"}, CLOSED_TRACK)
        self.assertEqual([], self.pending())
        self.assertEqual([], [call for call in calls(self.bin) if call[0] == "gh"])

    def test_no_ship_candidate_without_ship_roles(self):
        self.configure("    ship: [qe]\n", "")
        self.bd(EPIC, TRACK)
        self.assertEqual([], self.pending())
        self.assertEqual([["gh", "pr", "list", "--head", "feat/login-t2"]],
                         [call[:5] for call in calls(self.bin) if call[0] == "gh"])


class TestTrackRows(PendingCase):
    def test_open_track_pr_lists_its_approvers_and_no_gate(self):
        self.bd(TRACK)
        self.gh(("feat/login-t2", gh_pr(PR_TRACK, state="OPEN", author="em-dev", files=["services/auth/login.py"],
                                        reviews=[("binh-dev", "APPROVED", "c1")])))
        self.assertEqual([{"gate": None, "branch": "feat/login-t2", "url": PR_TRACK, "author": "em-dev",
                           "epic": "e-1", "approvals": ["binh-dev"], "missing": [], "notes": []}], self.pending())


class TestFiltersAndErrors(PendingCase):
    def test_workflow_id_and_milestone_keep_the_rows_of_those_epics(self):
        self.bd(milestone_epics=("e-1",))
        self.branches.update({"spec/login": {SPEC_PATH: "Epic: e-1\n"}, "spec/other": {SPEC_PATH: "Epic: e-2\n"}})
        self.gh(("spec/login", gh_pr(PR_SPEC, state="OPEN", files=[SPEC_PATH])),
                ("spec/other", gh_pr(PR_PLAN, state="OPEN", files=[SPEC_PATH])))
        self.assertEqual(["spec/other"], [row["branch"] for row in self.pending("--workflow-id", "e-2")])
        self.assertEqual(["spec/login"], [row["branch"] for row in self.pending("--milestone", "m-1")])
        both = run_cli(self.root, "team", "pending", "--workflow-id", "e-1", "--milestone", "m-1", env=self.env)
        self.assertEqual(2, both.returncode)

    def test_team_mode_off_exits_2(self):
        write(self.root, ".agent-workflow/config.yaml", "schema_version: '2.7'\n")
        result = run_cli(self.root, "team", "pending", env=self.env)
        self.assertEqual(2, result.returncode)
        self.assertIn("team mode is off", result.stderr)

    def test_missing_host_cli_exits_2_naming_it(self):
        self.branches["spec/login"] = {}
        only_bd = Path(self.tmp.name) / "only-bd"
        fake_cli(only_bd, "bd", [{"argv": ["list"], "stdout": []}])
        result = run_cli(self.root, "team", "pending", env={"PATH": str(only_bd)})
        self.assertEqual(2, result.returncode)
        self.assertIn("gh is not installed", result.stderr)

    def test_host_failing_before_any_lookup_succeeds_exits_2_naming_the_cause(self):
        self.branches.update({"spec/login": {}, "spec/other": {}})
        fake_cli(self.bin, "gh", [{"argv": ["pr"], "exit": 1, "stderr": "HTTP 401: Bad credentials"}])
        result = run_cli(self.root, "team", "pending", env=self.env)
        self.assertEqual((2, ""), (result.returncode, result.stdout))
        self.assertIn("gh pr failed: HTTP 401: Bad credentials", result.stderr)
        self.assertEqual(1, len([call for call in calls(self.bin) if call[0] == "gh"]))

    def test_failed_git_ls_remote_exits_2_naming_it(self):
        git(self.root, "remote", "set-url", "origin", str(Path(self.tmp.name) / "missing.git"))
        self.git.side_effect = REAL_GIT
        result = run_cli(self.root, "team", "pending", env=self.env)
        self.assertEqual(2, result.returncode)
        self.assertIn("git ls-remote failed", result.stderr)

    def test_unreadable_beads_exit_2_naming_the_cause(self):
        fake_cli(self.bin, "bd", [{"argv": ["list"], "exit": 1, "stderr": "database locked"}])
        result = run_cli(self.root, "team", "pending", env=self.env)
        self.assertEqual(2, result.returncode)
        self.assertIn("cannot read beads: bd exited 1: database locked", result.stderr)

    def test_a_failed_lookup_gives_its_row_an_error_and_keeps_the_others(self):
        self.branches.update({"spec/good": {SPEC_PATH: "Epic: e-1\n"}, "spec/down": {}, "plan/gone": None})
        self.gh(("spec/good", gh_pr(PR_SPEC, state="OPEN", files=[SPEC_PATH])),
                ("plan/gone", gh_pr(PR_PLAN, state="OPEN", author="chi-fe", files=[PLAN_PATH])),
                extra=({"argv": ["pr", "list", "--head", "spec/down"], "exit": 1, "stderr": "HTTP 502"},))
        rows = {row["branch"]: row for row in self.pending()}
        self.assertNotIn("error", rows["spec/good"])
        self.assertEqual("", rows["spec/down"]["url"])
        self.assertIn("HTTP 502", rows["spec/down"]["error"])
        self.assertEqual((PR_PLAN, "chi-fe"), (rows["plan/gone"]["url"], rows["plan/gone"]["author"]))
        self.assertIn("git fetch failed", rows["plan/gone"]["error"])


class TestText(PendingCase):
    def test_text_lists_gate_rows_by_gate_then_track_rows(self):
        self.bd(TRACK)
        self.branches.update({"plan/login": {PLAN_PATH: "Epic: e-1\n"}, "spec/login": {SPEC_PATH: "Epic: e-1\n"},
                              "spec/down": {}})
        self.gh(("spec/login", gh_pr(PR_SPEC, state="OPEN", files=[SPEC_PATH])),
                ("plan/login", gh_pr(PR_PLAN, state="OPEN", files=[PLAN_PATH])),
                ("feat/login-t2", gh_pr(PR_TRACK, state="OPEN", files=["web/login.tsx"])),
                extra=({"argv": ["pr", "list", "--head", "spec/down"], "exit": 1, "stderr": "HTTP 502"},))
        result = run_cli(self.root, "team", "pending", env=self.env)
        self.assertEqual(0, result.returncode, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(["requirement_confirmed", "requirement_confirmed", "plan_approved", "track"],
                         [line.split()[0] for line in lines])
        self.assertEqual(f"requirement_confirmed {PR_SPEC} e-1 missing: missing approval from one of ba, be_lead, "
                         "fe_lead", lines[0])
        self.assertTrue(lines[1].startswith("requirement_confirmed spec/down - missing: - "
                                            "(error: gh pr failed: HTTP 502"), lines[1])
        self.assertEqual(f"track {PR_TRACK} e-1 missing: -", lines[3])


if __name__ == "__main__":
    unittest.main()

"""Schema 2.7: the team block, its semantic validation, identity, state, and the solo guarantee."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import TEAM, calls, fake_cli, make_team_repo, path_with, run_cli  # noqa: E402
from workflow_core.configuration import ConfigValidationError, validate_portable_config  # noqa: E402
from workflow_core.migrations import migrate_config  # noqa: E402
from workflow_core.schemas import SUPPORTED_CONFIG_VERSIONS  # noqa: E402
from workflow_core.team import load_team, summary, validate_team  # noqa: E402

import yaml  # noqa: E402

RAW = yaml.safe_load(TEAM.format(host="github"))["team"]


class TestSchema27(unittest.TestCase):
    def test_2_7_and_older_versions_load(self):
        self.assertEqual(("2.3", "2.4", "2.5", "2.6", "2.7"), SUPPORTED_CONFIG_VERSIONS[:5])
        for version in SUPPORTED_CONFIG_VERSIONS:
            with self.subTest(version=version):
                validate_portable_config({"schema_version": version})

    def test_migration_from_2_6_only_bumps_versions(self):
        source = {"schema_version": "2.6", "workflow_version": "2.6", "setup_cli_version": "2.6",
                  "artifacts": {"layout": "sdd"}}
        self.assertEqual({**source, "schema_version": "2.7", "workflow_version": "2.7", "setup_cli_version": "2.7"},
                         migrate_config(source, "2.7"))

    def test_team_block_validates_and_loads_with_defaults(self):
        validate_portable_config({"schema_version": "2.7", "team": RAW})
        team = load_team({"team": {"members": {"A@Corp.com": {"roles": ["dev"], "login": "a"}}}})
        self.assertEqual(("github", "conventional", ""), (team.host, team.commit_convention, team.beads_remote))
        self.assertEqual("area_lead", team.approvals["plan_approved"])
        self.assertEqual("a@corp.com", team.member("a@CORP.com").email)
        self.assertIsNone(load_team({}))

    def test_schema_rejects_malformed_team(self):
        for bad in ({"members": {}}, {"members": {"not-an-email": {"roles": ["x"], "login": "x"}}},
                    {"members": {"a@b.c": {"roles": [], "login": "a"}}}, {**RAW, "host": "bitbucket"},
                    {**RAW, "approvals": {"shipped": ["qe"]}}, {**RAW, "approvals": {"plan_approved": "lead"}}):
            with self.subTest(bad=bad), self.assertRaises(ConfigValidationError):
                validate_portable_config({"schema_version": "2.7", "team": bad})

    def test_team_values_are_not_model_names_or_secret_keys(self):
        raw = {"members": {"token@corp.com": {"roles": ["claude-dev"], "login": "claude-dev"}},
               "areas": {"ai": {"paths": ["services/gemini-client/**"], "lead": "claude-dev"}},
               "beads_sync": {"remote": "git+ssh://git@github.com/org/claude-beads.git"}}
        validate_portable_config({"schema_version": "2.7", "team": raw})
        leaked = {**raw, "beads_sync": {"remote": "https://ghp_abcdefgh123456@github.com/org/beads.git"}}
        with self.assertRaisesRegex(ConfigValidationError, "secret-like value"):
            validate_portable_config({"schema_version": "2.7", "team": leaked})
        with self.assertRaisesRegex(ConfigValidationError, "provider-model name"):
            validate_portable_config({"schema_version": "2.7", "team": raw, "artifacts": {"plans": "claude-plans"}})

    def test_semantic_rules_report_every_finding(self):
        raw = {
            "members": {"a@corp.com": {"roles": ["dev"], "login": "same"},
                        "A@corp.com": {"roles": ["dev"], "login": "other"},
                        "b@corp.com": {"roles": ["dev"], "login": "SAME"}},
            "areas": {"api": {"paths": ["services/**"], "lead": "be_lead"},
                      "auth": {"paths": ["services/auth/**"], "lead": "dev", "roles": ["sec"]}},
            "approvals": {"requirement_confirmed": ["ba"]},
        }
        errors = validate_team(raw)
        self.assertEqual(6, len(errors), errors)
        joined = "\n".join(errors)
        for needle in ("duplicate email A@corp.com", "login SAME", "requirement_confirmed: role ba",
                       "api.lead: role be_lead", "auth.roles: role sec", "api and auth overlap"):
            self.assertIn(needle, joined)
        with self.assertRaisesRegex(ConfigValidationError, "role ba is held by no member"):
            validate_portable_config({"schema_version": "2.7", "team": raw})

    def test_req_012_milestone_permissions_validate_and_load(self):
        raw = {**RAW, "permissions": {"milestone": ["ba"]}}
        validate_portable_config({"schema_version": "2.7", "team": raw})
        self.assertEqual(["team.permissions.milestone: role pm is held by no member"],
                         validate_team({**RAW, "permissions": {"milestone": ["pm"]}}))
        with self.assertRaises(ConfigValidationError):
            validate_portable_config({"schema_version": "2.7", "team": {**RAW, "permissions": {"other": ["ba"]}}})
        team = load_team({"team": raw})
        self.assertEqual({"milestone": ("ba",)}, team.permissions)
        self.assertEqual({"milestone": ["ba"]}, summary(Path(tempfile.gettempdir()), team)["permissions"])

    def test_strict_and_claim_ttl_hours(self):
        validate_portable_config({"schema_version": "2.7", "team": {**RAW, "strict": True, "claim_ttl_hours": 12}})
        with self.assertRaises(ConfigValidationError):
            validate_portable_config({"schema_version": "2.7", "team": {**RAW, "claim_ttl_hours": 0}})
        team = load_team({"team": RAW})
        self.assertEqual((False, 48), (team.strict, team.claim_ttl_hours))
        team = load_team({"team": {**RAW, "strict": True, "claim_ttl_hours": 12}})
        self.assertEqual((True, 12), (team.strict, team.claim_ttl_hours))

    def test_strict_requires_a_policy_for_every_gate(self):
        raw = {"members": {"a@b.c": {"roles": ["dev"], "login": "a"}}, "strict": True,
               "approvals": {"requirement_confirmed": ["dev"]}}
        self.assertEqual(["team.strict: team.approvals.plan_approved has no role policy",
                          "team.strict: team.approvals.ship has no role policy"], validate_team(raw))
        self.assertEqual([], validate_team({**raw, "strict": False}))
        self.assertEqual([], validate_team({**raw, "approvals": {"requirement_confirmed": ["dev"], "ship": ["dev"]},
                                            "areas": {"api": {"paths": ["api/**"], "lead": "dev"}}}))

    def test_requirement_confirmed_per_kind_map(self):
        """epic-kinds R8, US-4: the per-kind map validates next to today's forms; its errors name the key."""
        for valid in ({"capability": ["ba"]}, ["ba", "be_lead"], {"all": ["ba"], "any": ["be_lead"]},
                      {"capability": {"all": ["ba"], "any": ["be_lead"]}, "technical": ["be_lead"], "parity": []}):
            with self.subTest(valid=valid):
                validate_portable_config({"schema_version": "2.7",
                                          "team": {**RAW, "approvals": {"requirement_confirmed": valid}}})
        for bad, message in (({"technical": ["be_lead"]}, "'capability' is a required property"),
                             ({"capability": ["ba"], "review": ["be_lead"]}, "'review' was unexpected"),
                             ({"capability": ["ba"], "all": ["ba"]}, "requirement_confirmed"),
                             ({"capability": {"every": ["ba"]}}, "requirement_confirmed.capability")):
            with self.subTest(bad=bad), self.assertRaisesRegex(ConfigValidationError, re.escape(message)):
                validate_portable_config({"schema_version": "2.7",
                                          "team": {**RAW, "approvals": {"requirement_confirmed": bad}}})
        with self.assertRaises(ConfigValidationError):  # the map is for requirement_confirmed only
            validate_portable_config({"schema_version": "2.7",
                                      "team": {**RAW, "approvals": {"ship": {"capability": ["qe"]}}}})

    def test_per_kind_policies_follow_the_semantic_rules(self):
        kinds = {"capability": ["ba"], "technical": ["ghost"], "parity": {"all": [], "any": []}}
        self.assertEqual(["team.approvals.requirement_confirmed.parity: all and any are both empty",
                          "team.approvals.requirement_confirmed.technical: role ghost is held by no member"],
                         validate_team({**RAW, "approvals": {"requirement_confirmed": kinds}}))
        strict = {**RAW, "strict": True, "approvals": {"ship": ["qe"]}}
        for kinds, missing in (({"capability": [], "technical": ["be_lead"]}, "capability"),
                               ({"capability": ["ba"], "parity": []}, "parity")):
            with self.subTest(kinds=kinds):
                self.assertEqual([f"team.strict: team.approvals.requirement_confirmed.{missing} has no role policy"],
                                 validate_team({**strict, "approvals": {**strict["approvals"],
                                                                        "requirement_confirmed": kinds}}))
        aws = {"host": "codecommit",
               "members": {"a@x.io": {"roles": ["ba"], "login": "a", "aws_identity": "a"},
                           "b@x.io": {"roles": ["be_lead"], "login": "b"}},
               "approvals": {"requirement_confirmed": {"capability": ["ba"], "technical": ["be_lead"]}}}
        self.assertEqual(["team.members: b@x.io holds approving role be_lead but has no aws_identity "
                          "(required on host codecommit)"], validate_team(aws))


class TestTechnicalMember(unittest.TestCase):
    def test_area_lead_and_area_role_are_technical_others_are_not(self):
        team = load_team({"team": RAW})
        self.assertEqual({"an@corp.com": False, "binh@corp.com": True, "chi@corp.com": True,
                          "dung@corp.com": False, "em@corp.com": True},
                         {email: team.technical(member) for email, member in team.members.items()})

    def test_area_without_roles_counts_only_its_lead(self):
        team = load_team({"team": {"members": {"a@b.c": {"roles": ["ba"], "login": "a"},
                                               "l@b.c": {"roles": ["lead"], "login": "l"}},
                                   "areas": {"api": {"paths": ["api/**"], "lead": "lead"}}}})
        self.assertEqual(["api"], team.areas_for(team.member("a@b.c")))
        self.assertFalse(team.technical(team.member("a@b.c")))
        self.assertTrue(team.technical(team.member("l@b.c")))

    def test_business_and_technical_roles_make_a_technical_member(self):
        members = {**RAW["members"], "an@corp.com": {"roles": ["ba", "be_dev"], "login": "an-ba"}}
        team = load_team({"team": {**RAW, "members": members}})
        self.assertTrue(team.technical(team.member("an@corp.com")))


class TestTeamIdentityAndSolo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        self.bin = Path(self.tmp.name) / "bin"

    def tearDown(self):
        self.tmp.cleanup()

    def test_state_and_whoami_report_a_business_member(self):
        make_team_repo(self.root, email="an@corp.com")
        me = json.loads(run_cli(self.root, "state", "--format", "json").stdout)["project"]["team"]["me"]
        self.assertEqual({"email": "an@corp.com", "roles": ["ba"], "areas": [], "technical": False}, me)
        self.assertFalse(json.loads(run_cli(self.root, "team", "whoami", "--format", "json").stdout)["technical"])
        self.assertIn("technical: no", run_cli(self.root, "team", "whoami").stdout)

    def test_whoami_reports_a_technical_member(self):
        make_team_repo(self.root)
        self.assertIn("technical: yes", run_cli(self.root, "team", "whoami").stdout)

    def test_state_reports_team_and_me(self):
        make_team_repo(self.root)
        project = json.loads(run_cli(self.root, "state", "--format", "json").stdout)["project"]
        self.assertEqual({"enabled": True, "host": "github",
                          "me": {"email": "binh@corp.com", "roles": ["be_lead", "be_dev"], "areas": ["backend"],
                                 "technical": True},
                          "permissions": {}},
                         project["team"])

    def test_whoami_and_non_member(self):
        make_team_repo(self.root)
        self.assertIn("binh@corp.com (binh-dev)", run_cli(self.root, "team", "whoami").stdout)
        make_team_repo(Path(self.tmp.name) / "other", email="stranger@corp.com")
        result = run_cli(Path(self.tmp.name) / "other", "team", "whoami")
        self.assertEqual(2, result.returncode)
        self.assertIn("stranger@corp.com is not in team.members", result.stderr)

    def test_team_command_without_team_block(self):
        make_team_repo(self.root, team="")
        result = run_cli(self.root, "team", "whoami")
        self.assertEqual(2, result.returncode)
        self.assertIn("team mode is off", result.stderr)

    def test_solo_record_and_unblock_never_call_the_host(self):
        make_team_repo(self.root, team="")
        fake_cli(self.bin, "gh", [])
        fake_cli(self.bin, "glab", [])
        env = path_with(self.bin)
        missing = run_cli(self.root, "record", "requirement-confirmed", "--evidence", "spec.md", env=env)
        self.assertEqual(2, missing.returncode)
        self.assertIn("--actor is required", missing.stderr)
        recorded = run_cli(self.root, "record", "requirement-confirmed", "--evidence", "spec.md", "--actor", "me",
                           env=env)
        self.assertEqual(0, recorded.returncode, recorded.stderr)
        waived = run_cli(self.root, "unblock", "--gate", "plan_approved", "--reason", "r", "--actor", "me", env=env)
        self.assertEqual(0, waived.returncode, waived.stdout + waived.stderr)
        state = json.loads(run_cli(self.root, "state", "--format", "json", env=env).stdout)
        self.assertEqual({"enabled": False, "host": None, "me": None}, state["project"]["team"])
        self.assertEqual("satisfied", state["gates"]["requirement_confirmed"])
        event = json.loads((self.root / ".agent-workflow/runtime/events.jsonl").read_text().splitlines()[0])
        self.assertEqual(("me", {"evidence": "spec.md"}),
                         (event["actor"], event["payload"]))
        self.assertEqual([], calls(self.bin))


if __name__ == "__main__":
    unittest.main()

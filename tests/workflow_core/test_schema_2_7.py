"""Schema 2.7: the team block, its semantic validation, identity, state, and the solo guarantee."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import TEAM, calls, fake_cli, make_team_repo, path_with, run_cli  # noqa: E402
from workflow_core.configuration import ConfigValidationError, validate_portable_config  # noqa: E402
from workflow_core.migrations import CURRENT_VERSION, migrate_config  # noqa: E402
from workflow_core.schemas import SUPPORTED_CONFIG_VERSIONS  # noqa: E402
from workflow_core.team import load_team, validate_team  # noqa: E402

import yaml  # noqa: E402

RAW = yaml.safe_load(TEAM.format(host="github"))["team"]


class TestSchema27(unittest.TestCase):
    def test_current_version_is_2_7_and_older_versions_load(self):
        self.assertEqual("2.7", CURRENT_VERSION)
        self.assertEqual(("2.3", "2.4", "2.5", "2.6", "2.7"), SUPPORTED_CONFIG_VERSIONS)
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


class TestTeamIdentityAndSolo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        self.bin = Path(self.tmp.name) / "bin"

    def tearDown(self):
        self.tmp.cleanup()

    def test_state_reports_team_and_me(self):
        make_team_repo(self.root)
        project = json.loads(run_cli(self.root, "state", "--format", "json").stdout)["project"]
        self.assertEqual({"enabled": True, "host": "github",
                          "me": {"email": "binh@corp.com", "roles": ["be_lead", "be_dev"], "areas": ["backend"]}},
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

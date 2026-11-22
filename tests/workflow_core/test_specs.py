"""SDD specs core: blocks, hash, lint, next-id, new, hash/template commands, renumber."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specs_fixtures import (ADDED_BLOCK, AUTH_SPEC, LAUNCHER, commit_all, delta, git,  # noqa: E402
                            make_change, make_repo, write, write_activity, ACTIVITY, STATE, USE_CASE)
from workflow_core import docs_check, specs, specs_reqs, specs_trace  # noqa: E402
from workflow_core.specs import SpecsError  # noqa: E402

MODIFIED_003 = ("### REQ-AUTH-003: Lock account after failed logins\n<!-- base: {base} -->\n"
                "The system SHALL lock an account for 30 minutes after 5 failed logins.\n\n"
                "#### Scenario: fifth failure locks\n- GIVEN a user with 4 failed logins\n"
                "- WHEN the next login fails\n- THEN the account is locked\n")


NFR = ("### REQ-AUTH-004: Sign-in response time\nType: non-functional\nCategory: performance\n"
       "Measure: p95 below 300 ms at 200 requests per second\n"
       "The system SHALL answer a sign-in request within 300 ms at the 95th percentile.\n")
RULE = ("### REQ-AUTH-005: Lockout threshold\nType: business-rule\n"
        "The system MUST lock an account after 5 failed sign-ins within 15 minutes.\n\n"
        "#### Scenario: fifth failure\n- GIVEN a user with 4 failed sign-ins\n- WHEN the next sign-in fails\n"
        "- THEN the account is locked\n")


def block(text: str) -> specs.Block:
    return specs.parse_blocks(text)[0][0]


def run_specs(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(LAUNCHER), "specs", *args, "--repository", str(root)],
                          text=True, capture_output=True, check=False)


class TestBlocks(unittest.TestCase):
    def test_block_type_category_measure(self):
        nfr = block(NFR)
        self.assertEqual(("non-functional", "performance", "p95 below 300 ms at 200 requests per second"),
                         (nfr.type, nfr.category, nfr.measure))
        plain = block(ADDED_BLOCK)
        self.assertEqual(("functional", "", ""), (plain.type, plain.category, plain.measure))
        self.assertEqual("functional", specs.type_of(block(RULE.replace("business-rule", "policy"))))
        self.assertEqual("The system MUST lock an account after 5 failed sign-ins within 15 minutes.",
                         specs.statement(block(RULE)))
        scenario_type = block(ADDED_BLOCK + "Type: business-rule\n")  # inside the scenario section: ignored
        self.assertEqual("functional", scenario_type.type)

    def test_lint_requirement_types(self):
        self.assertEqual([], specs.lint_block(block(NFR)))
        self.assertEqual([], specs.lint_block(block(RULE)))
        categories = ", ".join(specs.NFR_CATEGORIES)
        self.assertEqual([f"REQ-AUTH-004: Category must be one of {categories}"],
                         specs.lint_block(block(NFR.replace("Category: performance\n", ""))))
        self.assertEqual([f"REQ-AUTH-004: Category must be one of {categories}"],
                         specs.lint_block(block(NFR.replace("performance", "speed"))))
        self.assertEqual(["REQ-AUTH-004: needs at least one '#### Scenario:' or a 'Measure:' line"],
                         specs.lint_block(block(NFR.replace("Measure: p95 below 300 ms at 200 requests per second\n", ""))))
        self.assertEqual(["REQ-AUTH-005: Type must be one of functional, non-functional, business-rule"],
                         specs.lint_block(block(RULE.replace("business-rule", "policy"))))
        self.assertIn("REQ-AUTH-005: needs at least one '#### Scenario:'",
                      specs.lint_block(block(RULE.split("\n\n#### ")[0] + "\n")))
        self.assertEqual(["REQ-AUTH-003: Category and Measure are only for Type: non-functional"],
                         specs.lint_block(block(ADDED_BLOCK.replace("The system SHALL", "Measure: 5 tries\nThe system SHALL"))))
        with_scenario = NFR + "\n#### Scenario: slow\n- GIVEN load\n- THEN fast\n"
        self.assertEqual(["REQ-AUTH-004: scenario 1 lacks WHEN"], specs.lint_block(block(with_scenario)))

    def test_blocks_without_type_keep_findings_and_hash(self):
        for text in (ADDED_BLOCK, AUTH_SPEC.split("## Requirements\n\n", 1)[1]):
            with self.subTest(text=text[:30]):
                self.assertEqual([], specs.lint_block(block(text)))
        self.assertEqual("8f31b417", specs.block_hash(block(ADDED_BLOCK).text)[:8])

    def test_parse_blocks_sections_and_ranges(self):
        blocks, errors = specs.parse_blocks(AUTH_SPEC)
        self.assertEqual([], errors)
        self.assertEqual(["REQ-AUTH-001", "REQ-AUTH-002"], [b.id for b in blocks])
        self.assertEqual({"Requirements"}, {b.section for b in blocks})
        self.assertTrue(blocks[0].text.startswith("### REQ-AUTH-001: Sign in with password"))
        self.assertTrue(blocks[0].text.endswith("- THEN they are signed in"))
        self.assertEqual("auth", blocks[0].cap)

    def test_malformed_heading_is_reported(self):
        _, errors = specs.parse_blocks("## Requirements\n\n### Lockout\nThe system SHALL lock.\n")
        self.assertEqual(3, errors[0][0])

    def test_multi_word_capability(self):
        self.assertEqual("user-profile", specs.cap_of("REQ-USER-PROFILE-012"))
        with self.assertRaises(SpecsError):
            specs.cap_of("REQ-auth-1")

    def test_hash_ignores_base_line_and_trailing_space(self):
        plain = "### REQ-AUTH-001: X\nThe system SHALL x.\n"
        noisy = "\n### REQ-AUTH-001: X   \n<!-- base: " + "a" * 64 + " -->\nThe system SHALL x.\n\n"
        self.assertEqual(specs.block_hash(plain), specs.block_hash(noisy))
        self.assertNotEqual(specs.block_hash(plain), specs.block_hash(plain.replace("x.", "y.")))

    def test_lint_block_rules(self):
        block = specs.parse_blocks(ADDED_BLOCK)[0][0]
        self.assertEqual([], specs.lint_block(block))
        bare = specs.parse_blocks("### REQ-AUTH-009: X\nThe system locks.\n\n#### Scenario: s\n- GIVEN a\n- THEN b\n")[0][0]
        self.assertEqual(["REQ-AUTH-009: needs a SHALL or MUST statement", "REQ-AUTH-009: scenario 1 lacks WHEN"],
                         specs.lint_block(bare))
        none = specs.parse_blocks("### REQ-AUTH-009: X\nThe system MUST lock.\n")[0][0]
        self.assertEqual(["REQ-AUTH-009: needs at least one '#### Scenario:'"], specs.lint_block(none))



class TestRepositoryCommands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(Path(self.tmp.name) / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        write_activity(self.root)
        self.cfg = specs.sdd_config(specs.load_config(self.root))

    def tearDown(self):
        self.tmp.cleanup()

    def test_sdd_config_defaults(self):
        self.assertEqual("docs/specs", self.cfg["specs"])
        self.assertEqual("chat", self.cfg["spec_review"])
        self.assertIn("**/test_*.py", self.cfg["test_globs"])

    def test_lint_living_ok_then_wrong_folder_and_duplicate(self):
        self.assertEqual([], specs.lint_living(self.root, self.cfg))
        write(self.root, "docs/specs/billing/spec.md", "# Billing\n\n## Requirements\n\n" + ADDED_BLOCK.replace("003", "001"))
        errors = specs.lint_living(self.root, self.cfg)
        self.assertTrue(any("REQ-AUTH-001 belongs in auth/spec.md" in e for e in errors), errors)
        self.assertTrue(any("REQ-AUTH-001 duplicates" in e for e in errors), errors)

    def test_lint_change_rules(self):
        change = make_change(self.root)
        self.assertEqual([], specs.lint_change(self.root, self.cfg, change))
        base = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-002")[1]
        bad = delta(added=ADDED_BLOCK.replace("003", "001"),
                    modified="### REQ-AUTH-002: Reject wrong password\nThe system SHALL reject.\n\n"
                             "#### Scenario: s\n- GIVEN a\n- WHEN b\n- THEN c\n",
                    removed=f"### REQ-AUTH-001: Sign in with password\n<!-- base: {base} -->\n")
        write(self.root, "docs/changes/ep-1-lockout/02-spec-delta.md", bad)
        errors = specs.lint_change(self.root, self.cfg, change)
        self.assertTrue(any("REQ-AUTH-001 already exists" in e for e in errors), errors)
        self.assertTrue(any("REQ-AUTH-002 needs '<!-- base: <hash> -->'" in e for e in errors), errors)
        self.assertTrue(any("REQ-AUTH-001 needs a 'Reason: <why>' line" in e for e in errors), errors)
        self.assertTrue(any("REQ-AUTH-001 appears twice" in e for e in errors), errors)

    def test_lint_change_flags_cited_paths_git_does_not_track(self):
        write(self.root, "src/tracked.py", "x = 1\n")
        write(self.root, ".gitignore", "*.log\n")
        commit_all(self.root)
        write(self.root, "build.log", "ignored")
        write(self.root, "docs/assets/mockup/shot.png", "png")
        write(self.root, "docs/assets/mockup.html", "<html>")
        change = make_change(self.root)
        write(self.root, "docs/changes/ep-1-lockout/03-design.md",
              "# Design\n\nSee `docs/assets/mockup.html` and `src/tracked.py:1`.\n"
              "Screens: `docs/assets/mockup/`, planned `src/new.py`, outside `../other/x.md`, `/etc/hosts`,\n"
              f"own `docs/changes/ep-1-lockout/01-proposal.md`, `docs/changes/`, ignored `build.log`, `{'a' * 300}`.\n")
        self.assertEqual(
            ["docs/changes/ep-1-lockout/03-design.md:3: `docs/assets/mockup.html` is not tracked by git; commit it",
             "docs/changes/ep-1-lockout/03-design.md:4: `docs/assets/mockup/` is not tracked by git; commit it"],
            specs.lint_change(self.root, self.cfg, change))

    def test_lint_flags_dated_asset_folder_without_description(self):
        write(self.root, "docs/specs/auth/assets/2026-05-11/legacy/login.png", "png")
        write(self.root, "docs/specs/reports/assets/2026-12-01/filter.png", "png")  # capability without spec.md
        write(self.root, "docs/specs/auth/assets/mockup/index.html", "<html>")
        write(self.root, "docs/specs/auth/assets/login-form.png", "png")
        write(self.root, "docs/specs/auth/assets/110526/shot.png", "png")
        expected = [
            "docs/specs/auth/assets/2026-05-11: missing description.md (gin specs template iteration.md)",
            "docs/specs/reports/assets/2026-12-01: missing description.md (gin specs template iteration.md)"]
        self.assertEqual(expected, specs.lint_living(self.root, self.cfg))
        self.assertEqual(expected, specs.lint_change(self.root, self.cfg, make_change(self.root)))
        result = run_specs(self.root, "lint")
        self.assertEqual(1, result.returncode)
        self.assertIn(expected[0], result.stdout)
        write(self.root, "docs/specs/auth/assets/2026-05-11/description.md", "# Auth: 2026-05-11\n")
        write(self.root, "docs/specs/reports/assets/2026-12-01/description.md", "# Reports: 2026-12-01\n")
        self.assertEqual([], specs.lint_living(self.root, self.cfg))
        self.assertEqual([], specs.lint_change(self.root, self.cfg, make_change(self.root)))

    def test_lint_checks_each_diagram_holds_a_block_of_its_kind(self):
        write(self.root, "docs/specs/auth/diagrams/login-activity.md", "# Login\n\nNo diagram yet.\n")
        write(self.root, "docs/specs/auth/diagrams/account-state.md",
              "# Account\n\n```mermaid\nflowchart TD\n  a --> b\n```\n")
        write(self.root, "docs/specs/auth/diagrams/token-state.md", STATE)
        write(self.root, "docs/specs/auth/diagrams/sso-sequence.md", "# SSO\n\nNo block.\n")
        expected = ["docs/specs/auth/diagrams/account-state.md: no mermaid block starting with stateDiagram",
                    "docs/specs/auth/diagrams/login-activity.md: no mermaid block starting with flowchart or graph"]
        self.assertEqual(expected, specs.lint_living(self.root, self.cfg))
        self.assertEqual(expected, specs.lint_change(self.root, self.cfg, make_change(self.root)))
        result = run_specs(self.root, "lint")
        self.assertEqual(1, result.returncode)
        self.assertIn(expected[0], result.stdout)
        write(self.root, "docs/specs/auth/diagrams/login-activity.md",
              specs.template_text(self.root, "activity.md").replace("Use case: <slug>\n\n", ""))
        write(self.root, "docs/specs/auth/diagrams/account-state.md", specs.template_text(self.root, "state.md"))
        self.assertEqual([], specs.lint_living(self.root, self.cfg))

    def test_lint_warns_about_diagrams_added_with_technical_changes(self):
        write(self.root, "docs/specs/auth/use-cases/sign-in.md", USE_CASE)
        commit_all(self.root, "base")
        tech = "docs/changes/ep-7-cache"
        write(self.root, f"{tech}/01-proposal.md", "# Cache\n\nEpic: ep-7\nKind: technical\n")
        for name in ("cache", "kept"):
            write(self.root, f"docs/specs/auth/diagrams/{name}-activity.md", ACTIVITY)
        write(self.root, "docs/specs/auth/diagrams/flow-activity.md",
              ACTIVITY.replace("# Login\n", "# Flow\n\nUse case: sign-in\n"))
        write(self.root, f"{tech}/03-design.md", "## Data Flow\n\n`docs/specs/auth/diagrams/cache-activity.md#start`, "
              "`./docs/specs/auth/diagrams/kept-activity.md:3`, `docs/specs/auth/diagrams/flow-activity.md`, "
              "`docs/specs/auth/diagrams/login-activity.md`\n")
        commit_all(self.root, "technical change")
        (self.root / "docs/changes/archive").mkdir()
        git(self.root, "mv", tech, "docs/changes/archive/2026-10-01-ep-7-cache")
        commit_all(self.root, "archive")
        write(self.root, "docs/changes/ep-8-feature/01-proposal.md", "# Feature\n\nEpic: ep-8\n")
        write(self.root, "docs/changes/ep-8-feature/03-design.md",
              f"Flow: `{self.root.resolve()}/docs/specs/auth/diagrams/kept-activity.md`\n")
        write(self.root, "docs/changes/ep-9-open/01-proposal.md", "# Open\n\nEpic: ep-9\nKind: technical\n")
        write(self.root, "docs/specs/auth/diagrams/open-activity.md", ACTIVITY)
        write(self.root, "docs/changes/ep-9-open/03-design.md", "`docs/specs/auth/diagrams/open-activity.md`\n")
        commit_all(self.root, "more")
        warning = ("docs/specs/auth/diagrams/cache-activity.md was added with technical change 2026-10-01-ep-7-cache "
                   "and no feature change cites it; delete it and its link in spec.md ## Diagrams unless a feature "
                   "needs it")
        with mock.patch.object(specs, "_epic_kinds", return_value=None):
            self.assertEqual([warning], specs.technical_diagram_warnings(self.root, self.cfg))
        with mock.patch.object(specs, "_epic_kinds", return_value={"ep-7": "capability"}):
            self.assertEqual([], specs.technical_diagram_warnings(self.root, self.cfg))
        with mock.patch.object(specs, "_epic_kinds", return_value={}) as kinds:
            write(self.root, "docs/changes/archive/2026-10-01-ep-7-cache/03-design.md", "No diagrams.\n")
            self.assertEqual([], specs.technical_diagram_warnings(self.root, self.cfg))
            kinds.assert_not_called()
        git(self.root, "checkout", "-q", "--", "docs/changes/archive/2026-10-01-ep-7-cache/03-design.md")
        shallow = Path(self.tmp.name) / "shallow"
        subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{self.root}", str(shallow)], check=True)
        with mock.patch.object(specs, "_epic_kinds", return_value=None):
            self.assertEqual([], specs.technical_diagram_warnings(shallow, specs.sdd_config(specs.load_config(shallow))))
        result = run_specs(self.root, "lint")
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn(f"warning: {warning}", result.stderr)
        self.assertNotIn("cache-activity", run_specs(self.root, "lint", "--change", "ep-8").stderr)

    def test_lint_actors_file(self):
        self.assertEqual([], specs.lint_actors(self.root, self.cfg))
        write(self.root, "docs/specs/auth/use-cases/sign-in.md", USE_CASE)
        write(self.root, "docs/specs/actors.md",
              "# Actors\n\n| Actor | Description |\n|---|---|\n| registered USER | Has an account |\n| Auditor | Reads logs |\n")
        self.assertEqual(["docs/specs/actors.md:6: actor 'Auditor' is in no use case"],
                         specs.lint_actors(self.root, self.cfg))
        self.assertEqual(1, run_specs(self.root, "lint").returncode)
        write(self.root, "docs/specs/actors.md", "# Actors\n\nCustomer: buys.\n")
        self.assertEqual(["docs/specs/actors.md: needs a table with Actor and Description columns"],
                         specs.lint_actors(self.root, self.cfg))

    def test_lint_accepts_a_valid_use_case_and_no_folder(self):
        self.assertEqual([], specs.lint_use_cases(self.root, self.cfg))
        write(self.root, "docs/specs/auth/use-cases/sign-in.md", USE_CASE)
        self.assertEqual([], specs.lint_use_cases(self.root, self.cfg))
        self.assertNotIn("use-cases", "\n".join(specs.lint_living(self.root, self.cfg)))

    def test_lint_reports_each_missing_part_of_a_use_case(self):
        path = "docs/specs/auth/use-cases/sign-in.md"
        cases = {
            "missing '# <use case name>' title": USE_CASE.replace("# Sign in\n", ""),
            "missing 'Actor: <primary actor>' line": USE_CASE.replace("Actor: Registered user\n", "Actor:\n"),
            "missing 'Requirements: REQ-…' line": USE_CASE.replace("Requirements: REQ-AUTH-001, REQ-AUTH-002\n", ""),
            "no REQ-ID on its Requirements line": USE_CASE.replace("REQ-AUTH-001, REQ-AUTH-002", "none yet"),
            "missing '## Main flow' with a numbered list": USE_CASE.replace("1. The user enters", "- The user enters")
                                                                  .replace("2. The system signs", "- The system signs"),
            "REQ-AUTH-009 is not in a living spec or an open change": USE_CASE.replace("REQ-AUTH-002", "REQ-AUTH-009"),
        }
        for message, text in cases.items():
            with self.subTest(message=message):
                write(self.root, path, text)
                expected = [f"{path}: {message}"]
                self.assertEqual(expected, specs.lint_use_cases(self.root, self.cfg))
                self.assertIn(expected[0], specs.lint_change(self.root, self.cfg, make_change(self.root)))

    def test_lint_use_case_accepts_requirements_added_in_an_open_change(self):
        make_change(self.root, spec_delta=delta(added=ADDED_BLOCK))          # adds REQ-AUTH-003
        write(self.root, "docs/specs/auth/use-cases/lock.md", USE_CASE.replace("REQ-AUTH-002", "REQ-AUTH-003"))
        self.assertEqual([], specs.lint_use_cases(self.root, self.cfg))

    def test_lint_use_case_reports_a_requirement_only_removed(self):
        removed = ADDED_BLOCK.replace("REQ-AUTH-003", "REQ-AUTH-009") + "Reason: gone\n"
        make_change(self.root, spec_delta=delta(removed=removed))
        write(self.root, "docs/specs/auth/use-cases/lock.md", USE_CASE.replace("REQ-AUTH-002", "REQ-AUTH-009"))
        self.assertEqual(["docs/specs/auth/use-cases/lock.md: REQ-AUTH-009 is not in a living spec or an open change"],
                         specs.lint_use_cases(self.root, self.cfg))

    def test_lint_change_needs_an_activity_diagram_where_requirements_are_added_or_modified(self):
        (self.root / "docs/specs/auth/diagrams/login-activity.md").unlink()
        missing = "auth: no activity diagram in docs/specs/auth/diagrams/ (gin specs template activity.md)"
        change = make_change(self.root)
        self.assertEqual([missing], specs.lint_change(self.root, self.cfg, change))
        result = run_specs(self.root, "lint", "--change", "ep-1")
        self.assertEqual(1, result.returncode)
        self.assertIn(missing, result.stdout)
        base2 = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-002")[1]
        modified = (f"### REQ-AUTH-002: Reject wrong password\n<!-- base: {base2} -->\n"
                    "The system SHALL reject a wrong password twice.\n\n#### Scenario: wrong password\n"
                    "- GIVEN a registered user\n- WHEN they submit a wrong password\n- THEN they see an error\n")
        write(self.root, "docs/changes/ep-1-lockout/02-spec-delta.md", delta(modified=modified))
        self.assertEqual([missing], specs.lint_change(self.root, self.cfg, change))
        base1 = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-001")[1]
        write(self.root, "docs/changes/ep-1-lockout/02-spec-delta.md", delta(
            removed=f"### REQ-AUTH-001: Sign in with password\n<!-- base: {base1} -->\nReason: replaced by SSO\n"))
        self.assertEqual([], specs.lint_change(self.root, self.cfg, change))
        write_activity(self.root)
        write(self.root, "docs/changes/ep-1-lockout/02-spec-delta.md", delta(added=ADDED_BLOCK))
        self.assertEqual([], specs.lint_change(self.root, self.cfg, change))

    def test_block_outside_delta_sections(self):
        change = make_change(self.root, spec_delta="# Delta\n\n## Other\n\n" + ADDED_BLOCK)
        self.assertTrue(any("outside ## ADDED/MODIFIED/REMOVED" in e for e in specs.lint_change(self.root, self.cfg, change)))

    def test_lint_against_base_flags_id_taken_on_base_but_not_own_change(self):
        make_change(self.root)
        commit_all(self.root)
        git(self.root, "checkout", "-q", "-b", "feature")
        other = make_change(self.root, "ep-2-other", epic="ep-2")
        self.assertEqual(["docs/changes/ep-2-other/02-spec-delta.md:5: REQ-AUTH-003 is already used on main"],
                         [e for e in specs.lint_change(self.root, self.cfg, other, against="main") if "already used" in e])
        own = self.root / "docs/changes/ep-1-lockout"
        write_activity(self.root, name="lockout")
        self.assertEqual([], specs.lint_change(self.root, self.cfg, own, against="main"))

    def test_unlabelled_decision_edges(self):
        text = ("# F\n\n```mermaid\nflowchart TD\n  subgraph user[User]\n    a([Start]) --> check{Valid?}\n  end\n"
                "  %% check --> skipped\n  check -->|yes| b[Save]\n  check --> c[Error]\n  check -- retry --> a\n"
                "  check -.-> d\n  check -. later .-> d\n  check ==> e\n  check ==>|now| e\n"
                "  b --> check --> c\n  hex{{Prepare}} --> b\n```\n")
        self.assertEqual([(10, "check"), (12, "check"), (14, "check")], specs.unlabelled_decision_edges(text))
        self.assertEqual([], specs.unlabelled_decision_edges("```python\ncheck{x} --> y\n```\n"))

    def test_lint_against_base_needs_a_changed_activity_diagram_per_capability(self):
        commit_all(self.root)
        git(self.root, "checkout", "-q", "-b", "feature")
        change = make_change(self.root)
        missing = ("auth: no activity diagram added or changed in docs/specs/auth/diagrams/ since main "
                   "(gin specs template activity.md)")
        self.assertIn(missing, specs.lint_change(self.root, self.cfg, change, against="main"))
        self.assertNotIn(missing, specs.lint_change(self.root, self.cfg, change))
        write_activity(self.root, name="lockout")
        self.assertNotIn(missing, specs.lint_change(self.root, self.cfg, change, against="main"))

    def test_non_functional_added_blocks_need_no_activity_diagram(self):
        commit_all(self.root)
        git(self.root, "checkout", "-q", "-b", "feature")
        nfr = NFR.replace("REQ-AUTH-004", "REQ-AUTH-003")
        change = make_change(self.root, spec_delta=delta(added=nfr))
        self.assertFalse([e for e in specs.lint_change(self.root, self.cfg, change, against="main") if "activity diagram" in e])
        (self.root / "docs/specs/auth/diagrams/login-activity.md").unlink()
        self.assertFalse([e for e in specs.lint_change(self.root, self.cfg, change) if "activity diagram" in e])
        rule = RULE.replace("REQ-AUTH-005", "REQ-AUTH-003")
        write(self.root, "docs/changes/ep-1-lockout/02-spec-delta.md", delta(added=rule))
        self.assertTrue([e for e in specs.lint_change(self.root, self.cfg, change, against="main") if "activity diagram" in e])

    def test_lint_against_base_needs_no_diagram_for_a_modified_only_delta(self):
        commit_all(self.root)
        git(self.root, "checkout", "-q", "-b", "feature")
        base2 = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-002")[1]
        modified = (f"### REQ-AUTH-002: Reject wrong password\n<!-- base: {base2} -->\n"
                    "The system SHALL reject a wrong password twice.\n\n#### Scenario: wrong password\n"
                    "- GIVEN a registered user\n- WHEN they submit a wrong password\n- THEN they see an error\n")
        change = make_change(self.root, spec_delta=delta(modified=modified))
        self.assertEqual([], specs.lint_change(self.root, self.cfg, change, against="main"))

    def test_lint_against_base_needs_an_activity_diagram_per_changed_use_case(self):
        commit_all(self.root)
        git(self.root, "checkout", "-q", "-b", "feature")
        change = make_change(self.root)
        write(self.root, "docs/specs/auth/use-cases/sign-in.md", USE_CASE)
        finding = "docs/specs/auth/use-cases/sign-in.md: no activity diagram with 'Use case: sign-in'"
        self.assertIn(finding, specs.lint_change(self.root, self.cfg, change, against="main"))
        write(self.root, "docs/specs/auth/diagrams/sign-in-activity.md",
              ACTIVITY.replace("# Login\n", "# Sign in\n\nUse case: sign-in\n"))
        self.assertEqual([], specs.lint_change(self.root, self.cfg, change, against="main"))
        simple = USE_CASE.replace("# Sign in", "# Sign out").split("## Alternative flows")[0] + "## Postconditions\nOut.\n"
        write(self.root, "docs/specs/auth/use-cases/sign-out.md", simple)
        self.assertEqual([], specs.lint_change(self.root, self.cfg, change, against="main"))

    def test_lint_against_base_checks_decision_labels_only_in_changed_diagrams(self):
        write(self.root, "docs/specs/auth/diagrams/old-activity.md",
              "# Old\n\n```mermaid\nflowchart TD\n  q{Ok?} --> r\n```\n")
        commit_all(self.root)
        git(self.root, "checkout", "-q", "-b", "feature")
        change = make_change(self.root)
        write(self.root, "docs/specs/auth/diagrams/new-activity.md",
              "# New\n\n```mermaid\nflowchart TD\n  s{Stock?} -->|yes| t\n  s --> u\n```\n")
        self.assertEqual(["docs/specs/auth/diagrams/new-activity.md:6: edge from decision 's' has no label"],
                         specs.lint_change(self.root, self.cfg, change, against="main"))

    def test_lint_against_an_unknown_ref_is_a_usage_error(self):
        change = make_change(self.root)
        with self.assertRaisesRegex(specs.SpecsError, "cannot resolve nope"):
            specs.lint_change(self.root, self.cfg, change, against="nope")
        self.assertEqual(2, run_specs(self.root, "lint", "--change", "ep-1", "--against", "nope").returncode)

    def test_technical_change_skips_diagram_rules(self):
        (self.root / "docs/specs/auth/diagrams/login-activity.md").unlink()
        change = make_change(self.root)
        write(self.root, "docs/changes/ep-1-lockout/01-proposal.md", "# Lockout\n\nEpic: ep-1\nKind: technical\n")
        self.assertEqual([], specs.lint_change(self.root, self.cfg, change))
        commit_all(self.root)
        self.assertEqual([], specs.lint_change(self.root, self.cfg, change, against="HEAD"))

    def test_lint_reads_the_kind_from_the_epic_label_first(self):
        (self.root / "docs/specs/auth/diagrams/login-activity.md").unlink()
        change = make_change(self.root)
        write(self.root, "docs/changes/ep-1-lockout/01-proposal.md", "# Lockout\n\nEpic: ep-1\nKind: capability\n")
        with mock.patch("workflow_core.epic_kind._bead_kind", return_value=("technical", None)):
            self.assertEqual(["docs/changes/ep-1-lockout/01-proposal.md: kind mismatch: epic ep-1 is kind:technical, "
                              "spec docs/changes/ep-1-lockout/01-proposal.md says Kind: capability"],
                             specs.lint_change(self.root, self.cfg, change))
        write(self.root, "docs/changes/ep-1-lockout/01-proposal.md", "# Lockout\n\nEpic: ep-1\nKind: technical\n")
        with mock.patch("workflow_core.epic_kind._bead_kind",
                        return_value=(None, "cannot read the kind of epic ep-1: bd not found")):
            self.assertEqual([], specs.lint_change(self.root, self.cfg, change))

    def test_specs_new_writes_the_kind(self):
        self.assertIn("Kind: technical\n", (specs.new_change(self.root, self.cfg, "a", "ep-7", kind="technical")
                                              / "01-proposal.md").read_text(encoding="utf-8"))
        with mock.patch("workflow_core.epic_kind._bead_kind", return_value=("parity", None)):
            self.assertIn("Kind: parity\n", (specs.new_change(self.root, self.cfg, "b", "ep-8")
                                             / "01-proposal.md").read_text(encoding="utf-8"))
        self.assertIn("Kind: capability\n", (specs.new_change(self.root, self.cfg, "c", "ep-9")
                                               / "01-proposal.md").read_text(encoding="utf-8"))
        result = run_specs(self.root, "new", "d", "--epic", "ep-10", "--kind", "technical")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, run_specs(self.root, "new", "e", "--epic", "ep-11", "--kind", "other").returncode)

    def test_find_change_by_full_name_or_epic_prefix(self):
        change = make_change(self.root)
        self.assertEqual(change, specs.find_change(self.root, self.cfg, "ep-1-lockout"))
        self.assertEqual(change, specs.find_change(self.root, self.cfg, "ep-1"))
        with self.assertRaises(SpecsError):
            specs.find_change(self.root, self.cfg, "ep-9")

    def test_next_id_scans_tree_worktrees_and_remote(self):
        self.assertEqual("REQ-AUTH-003", specs.next_id(self.root, self.cfg, "auth")[0])
        self.assertEqual("REQ-BILLING-001", specs.next_id(self.root, self.cfg, "billing")[0])
        commit_all(self.root)
        worktree = Path(self.tmp.name) / "wt"
        git(self.root, "worktree", "add", "-q", "-b", "wt", str(worktree))
        make_change(worktree)
        self.assertEqual("REQ-AUTH-004", specs.next_id(self.root, self.cfg, "auth")[0])
        remote = Path(self.tmp.name) / "remote.git"
        git(Path(self.tmp.name), "init", "-q", "--bare", str(remote))
        git(self.root, "remote", "add", "origin", str(remote))
        git(self.root, "checkout", "-q", "-b", "pushed")
        write(self.root, "docs/changes/ep-5-x/02-spec-delta.md", delta(added=ADDED_BLOCK.replace("003", "007")))
        commit_all(self.root)
        git(self.root, "push", "-q", "origin", "pushed")
        git(self.root, "checkout", "-q", "main")
        self.assertEqual(("REQ-AUTH-008", []), specs.next_id(self.root, self.cfg, "auth"))

    def test_next_id_warns_without_remote(self):
        self.assertEqual(["no git remote; scanned local worktrees only"], specs.next_id(self.root, self.cfg, "auth")[1])

    def test_new_change_renders_templates_and_refuses_existing(self):
        change = specs.new_change(self.root, self.cfg, "lockout", "ep-1", "Account lockout")
        self.assertEqual(["01-proposal.md", "02-spec-delta.md", "03-design.md", "05-tests.md"],
                         sorted(p.name for p in change.iterdir()))
        proposal = (change / "01-proposal.md").read_text(encoding="utf-8")
        self.assertIn("# Account lockout", proposal)
        self.assertEqual("ep-1", specs.change_epic(change))
        with self.assertRaises(SpecsError):
            specs.new_change(self.root, self.cfg, "lockout", "ep-1")
        with self.assertRaises(SpecsError):
            specs.new_change(self.root, self.cfg, "Bad Slug", "ep-1")

    def test_change_folder_from_before_numbering_still_reads(self):
        write(self.root, "docs/changes/ep-1-lockout/proposal.md", "# Lockout\n\nEpic: ep-1\n")
        write(self.root, "docs/changes/ep-1-lockout/spec-delta.md", delta(added=ADDED_BLOCK))
        change = specs.find_change(self.root, self.cfg, "ep-1")
        self.assertEqual("ep-1", specs.change_epic(change))
        self.assertEqual(["REQ-AUTH-003"], [block.id for block in specs.delta_blocks(self.root, change)[0]])
        self.assertEqual([], specs.lint_change(self.root, self.cfg, change))
        self.assertEqual("REQ-AUTH-004", specs.next_id(self.root, self.cfg, "auth")[0])
        self.assertEqual(["REQ-AUTH-003"], [row["id"] for row in specs_reqs.requirements(
            self.root, {}, self.cfg, change)["requirements"]])
        write(self.root, "docs/changes/ep-1-lockout/tests.md", "| TC | REQ | type | evidence |\n|---|---|---|---|\n"
              "| TC-1 | REQ-AUTH-003 | manual | run 1 |\n")
        self.assertEqual(["docs/changes/ep-1-lockout/tests.md#TC-1"],
                         specs_trace.trace(self.root, self.cfg, change)["requirements"][0]["sources"])
        write(self.root, "docs/changes/ep-1-lockout/02-spec-delta.md", delta())
        self.assertEqual([], specs.delta_blocks(self.root, change)[0])

    def test_project_template_overrides_plugin(self):
        write(self.root, ".agent-workflow/templates/proposal.md", "# {{title}} (team)\n\nEpic: {{epic}}\n")
        change = specs.new_change(self.root, self.cfg, "lockout", "ep-1", "Lockout")
        self.assertEqual("# Lockout (team)\n\nEpic: ep-1\n", (change / "01-proposal.md").read_text(encoding="utf-8"))

    def test_renumber_rewrites_change_tests_and_bead_labels(self):
        make_change(self.root)
        commit_all(self.root)
        git(self.root, "checkout", "-q", "-b", "feature")
        write(self.root, "tests/test_lockout.py", "def test_lock():  # REQ-AUTH-003\n    pass\n# REQ-AUTH-0030\n")
        write(self.root, "src/app.py", "# REQ-AUTH-003\n")
        commit_all(self.root)
        change = self.root / "docs/changes/ep-1-lockout"
        calls = []

        def fake_bd(_root, argv):
            calls.append(argv)
            return [{"id": "ep-1.1"}] if argv[0] == "list" else ""

        with mock.patch("workflow_core.specs._bd", fake_bd):
            result = specs.renumber(self.root, self.cfg, change, "REQ-AUTH-003", "REQ-AUTH-004", against="main")
        self.assertEqual(["docs/changes/ep-1-lockout/02-spec-delta.md", "tests/test_lockout.py"], result["files"])
        self.assertIn("# REQ-AUTH-0030", (self.root / "tests/test_lockout.py").read_text(encoding="utf-8"))
        self.assertIn("REQ-AUTH-004", (self.root / "tests/test_lockout.py").read_text(encoding="utf-8"))
        self.assertEqual("# REQ-AUTH-003\n", (self.root / "src/app.py").read_text(encoding="utf-8"))
        self.assertEqual(["list", "--parent", "ep-1", "--label", "req:REQ-AUTH-003", "--all", "--limit", "0", "--json"],
                         calls[0])
        self.assertEqual(["update", "ep-1.1", "--remove-label", "req:REQ-AUTH-003", "--add-label", "req:REQ-AUTH-004"],
                         calls[1])

    def test_renumber_refuses_taken_id(self):
        change = make_change(self.root)
        with self.assertRaises(SpecsError):
            specs.renumber(self.root, self.cfg, change, "REQ-AUTH-003", "REQ-AUTH-002", against="HEAD")

    def test_lint_accepts_modified_on_in_flight_req(self):
        make_change(self.root)
        block, base, source = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-003")
        self.assertEqual("ep-1-lockout", source.name)
        self.assertEqual(specs.block_hash(ADDED_BLOCK), base)
        second = make_change(self.root, "ep-2-longer", epic="ep-2",
                             spec_delta=delta(modified=MODIFIED_003.format(base=base)))
        self.assertEqual([], specs.lint_change(self.root, self.cfg, second))
        removed = make_change(self.root, "ep-4-drop", epic="ep-4", spec_delta=delta(
            removed=f"### REQ-AUTH-003: Lock account after failed logins\n<!-- base: {base} -->\nReason: dropped\n"))
        self.assertEqual([], specs.lint_change(self.root, self.cfg, removed))

    def test_lint_rejects_req_neither_living_nor_in_flight(self):
        change = make_change(self.root, spec_delta=delta(
            modified=MODIFIED_003.format(base="0" * 64).replace("REQ-AUTH-003", "REQ-AUTH-999")))
        errors = specs.lint_change(self.root, self.cfg, change)
        self.assertTrue(any(e.endswith("REQ-AUTH-999 is not in the living spec or an open change") for e in errors), errors)

    def test_req_added_by_two_open_changes(self):
        make_change(self.root)
        make_change(self.root, "ep-3-dup", epic="ep-3")
        message = "REQ-AUTH-003 is added by ep-1-lockout and ep-3-dup; renumber one"
        with self.assertRaises(SpecsError) as raised:
            specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-003")
        self.assertEqual(message, str(raised.exception))
        third = make_change(self.root, "ep-5-third", epic="ep-5",
                            spec_delta=delta(modified=MODIFIED_003.format(base="0" * 64)))
        errors = specs.lint_change(self.root, self.cfg, third)
        self.assertTrue(any(e.endswith(message) for e in errors), errors)

    def test_living_hash_unchanged(self):
        block, digest, source = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-002")
        self.assertIsNone(source)
        self.assertEqual(specs.block_hash(block.text), digest)

    def test_lint_references_of_use_cases_and_activity_diagrams(self):
        write(self.root, "docs/specs/auth/use-cases/sign-in.md", USE_CASE + "Includes: verify-otp, \nExtends: sign-in\n")
        write(self.root, "docs/specs/auth/diagrams/reset-activity.md", ACTIVITY.replace("# Login\n", "# Reset\n\nUse case: reset\n"))
        self.assertEqual([
            "docs/specs/auth/use-cases/sign-in.md: Includes names unknown use case 'verify-otp'",
            "docs/specs/auth/use-cases/sign-in.md: Extends names the use case itself",
            "docs/specs/auth/diagrams/reset-activity.md: Use case names unknown use case 'reset'",
        ], specs.lint_references(self.root, self.cfg))
        write(self.root, "docs/specs/auth/use-cases/verify-otp.md", USE_CASE.replace("# Sign in", "# Verify OTP"))
        write(self.root, "docs/specs/auth/use-cases/reset.md", USE_CASE.replace("# Sign in", "# Reset"))
        write(self.root, "docs/specs/auth/use-cases/sign-in.md", USE_CASE + "Includes: verify-otp\nExtends:\n")
        self.assertEqual([], specs.lint_references(self.root, self.cfg))
        self.assertEqual(0, run_specs(self.root, "lint").returncode)

    def test_lint_references_ignore_comments_and_the_old_template(self):
        write(self.root, "docs/specs/auth/use-cases/sign-in.md", "<!-- Includes: nothing -->\n" + USE_CASE)
        self.assertEqual([], specs.lint_references(self.root, self.cfg))
        self.assertEqual(["a", "b"], specs.line_values("Includes:  a , ,b\n", "Includes"))
        self.assertEqual("", specs.line_value("Actor:\n", "Actor"))

    def test_lint_use_case_actor_is_optional_only_for_an_included_use_case(self):
        write(self.root, "docs/specs/auth/use-cases/verify-otp.md",
              USE_CASE.replace("# Sign in", "# Verify OTP").replace("Actor: Registered user\n", ""))
        self.assertEqual(["docs/specs/auth/use-cases/verify-otp.md: missing 'Actor: <primary actor>' line"],
                         specs.lint_use_cases(self.root, self.cfg))
        write(self.root, "docs/specs/auth/use-cases/sign-in.md",
              USE_CASE.replace("Requirements:", "Includes: verify-otp\nRequirements:"))
        self.assertEqual([], specs.lint_use_cases(self.root, self.cfg))

    def test_lint_references_across_capabilities(self):
        pay = "docs/specs/orders/use-cases/pay.md"
        write(self.root, "docs/specs/auth/use-cases/sign-in.md", USE_CASE)
        write(self.root, pay, USE_CASE + "Includes: auth/sign-in\n")
        self.assertEqual([], specs.lint_references(self.root, self.cfg))
        write(self.root, pay, USE_CASE + "Includes: auth/verify-otp\n")
        self.assertEqual([f"{pay}: Includes names unknown use case 'auth/verify-otp'"],
                         specs.lint_references(self.root, self.cfg))
        write(self.root, pay, USE_CASE + "Extends: orders/pay\n")
        self.assertEqual([f"{pay}: Extends names the use case itself"], specs.lint_references(self.root, self.cfg))
        write(self.root, pay, USE_CASE + "Includes: a/b/c\n")
        self.assertEqual([f"{pay}: Includes names unknown use case 'a/b/c'"], specs.lint_references(self.root, self.cfg))

    def test_lint_use_case_actor_is_optional_for_a_use_case_included_from_another_capability(self):
        write(self.root, "docs/specs/auth/use-cases/verify-otp.md",
              USE_CASE.replace("# Sign in", "# Verify OTP").replace("Actor: Registered user\n", ""))
        write(self.root, "docs/specs/orders/use-cases/pay.md", USE_CASE.replace("Requirements:", "Includes: auth/verify-otp\nRequirements:"))
        self.assertEqual([], specs.lint_use_cases(self.root, self.cfg))

    def test_lint_specializes_and_generalization_cycles(self):
        base = "docs/specs/auth/use-cases/"
        write(self.root, base + "sign-in.md", USE_CASE)
        write(self.root, base + "sign-in-sso.md", USE_CASE + "Specializes: sign-in\n")
        self.assertEqual([], specs.lint_references(self.root, self.cfg))
        self.assertEqual([], specs.lint_use_cases(self.root, self.cfg))
        write(self.root, base + "sign-in-sso.md", USE_CASE + "Specializes: nope\n")
        self.assertEqual([f"{base}sign-in-sso.md: Specializes names unknown use case 'nope'"],
                         specs.lint_references(self.root, self.cfg))
        write(self.root, base + "a.md", USE_CASE + "Specializes: b\n")
        write(self.root, base + "b.md", USE_CASE + "Specializes: a\n")
        self.assertEqual([f"{base}a.md: use case generalization cycle: auth/a, auth/b"],
                         specs.lint_use_cases(self.root, self.cfg))
        self.assertEqual([["a", "b"]], specs.generalization_cycles({"a": ["b"], "b": ["a"]}))

    def test_use_case_ref(self):
        self.assertEqual(("auth", "x"), specs.use_case_ref("auth", "x"))
        self.assertEqual(("other", "x"), specs.use_case_ref("auth", "other/x"))
        for bad in ("a/b/c", "/x", "x/", "", "../x", "./x"):
            self.assertIsNone(specs.use_case_ref("auth", bad))

    def test_lint_refuses_a_reference_that_leaves_the_specs_folder(self):
        pay = "docs/specs/orders/use-cases/pay.md"
        write(self.root, pay, USE_CASE + "Includes: ../x\n")
        self.assertEqual([f"{pay}: Includes names unknown use case '../x'"], specs.lint_references(self.root, self.cfg))

    def test_actors_generalize_with_an_is_a_column(self):
        write(self.root, "docs/specs/auth/use-cases/sign-in.md", USE_CASE)
        write(self.root, "docs/specs/auth/use-cases/manage.md",
              USE_CASE.replace("# Sign in", "# Manage").replace("Actor: Registered user", "Actor: Admin\nSecondary actors: User"))
        header = "# Actors\n\n| Actor | Description | Is a |\n|---|---|---|\n"
        path = "docs/specs/actors.md"
        write(self.root, path, header + "| Admin | Manages users | User |\n| User | Signs in |  |\n")
        self.assertEqual([], specs.lint_actors(self.root, self.cfg))
        self.assertEqual({"admin": "User"}, specs.actor_parents(self.root, self.cfg))
        write(self.root, path, header + "| Admin | Manages users | Superuser |\n| User | Signs in |  |\n")
        self.assertEqual([f"{path}:5: actor 'Admin' is a 'Superuser', which is no actor"],
                         specs.lint_actors(self.root, self.cfg))
        write(self.root, path, header + "| Admin | Manages users | User |\n| User | Signs in | Admin |\n")
        self.assertEqual([f"{path}: actor generalization cycle: Admin, User"], specs.lint_actors(self.root, self.cfg))
        write(self.root, path, "# Actors\n\n| Actor | Description |\n|---|---|\n| Admin | x |\n")
        self.assertEqual({}, specs.actor_parents(self.root, self.cfg))

    def test_changed_since_in_a_subdirectory_of_the_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            top = Path(tmp) / "top"
            top.mkdir()
            git(top, "init", "-q", "-b", "main")
            git(top, "config", "user.email", "t@example.com")
            git(top, "config", "user.name", "T")
            proj = top / "proj"
            write(proj, "docs/specs/auth/diagrams/a-activity.md", ACTIVITY)
            commit_all(top, "init")
            write(proj, "docs/specs/auth/diagrams/a-activity.md", ACTIVITY + "\nmore\n")
            write(proj, "docs/specs/auth/diagrams/b-activity.md", ACTIVITY)
            self.assertEqual({"docs/specs/auth/diagrams/a-activity.md", "docs/specs/auth/diagrams/b-activity.md"},
                             specs.changed_since(proj, "main", proj / "docs/specs"))


class TestSpecsCli(unittest.TestCase):
    def test_pm_and_ba_templates_ship_and_can_be_overridden(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_repo(Path(directory), layout="legacy")
            for name in ("roadmap.md", "epic.md", "user-story.md", "design-spec.md", "iteration.md", "readme.md", "runbook.md", "changelog.md", "activity.md", "state.md", "task.md", "use-case.md"):
                with self.subTest(name=name):
                    self.assertEqual(0, run_specs(root, "template", name).returncode)
            self.assertIn("## User Stories", run_specs(root, "template", "design-spec.md").stdout)
            self.assertIn("## User Stories", run_specs(root, "template", "proposal.md").stdout)
            for name, kind in (("design-spec.md", "capability"), ("technical-design.md", "technical"),
                               ("proposal.md", "capability")):
                with self.subTest(template=name):
                    self.assertIn(f"\nKind: {kind}\nPoints: {{{{points}}}} ({{{{points_reason}}}})\n",
                                  run_specs(root, "template", name).stdout)
            self.assertIn("Depends on:", run_specs(root, "template", "roadmap.md").stdout)
            self.assertIn("- Deadline:", run_specs(root, "template", "roadmap.md").stdout)
            self.assertIn("## Way of working", run_specs(root, "template", "roadmap.md").stdout)
            self.assertIn("Spec ready by:", run_specs(root, "template", "roadmap.md").stdout)
            self.assertIn("Integration point:", run_specs(root, "template", "roadmap.md").stdout)
            self.assertIn("```mermaid\nflowchart TD", run_specs(root, "template", "activity.md").stdout)
            activity = run_specs(root, "template", "activity.md").stdout
            for needle in ("Use case:", "subgraph", "-->|2a", "((Start))", "(((End)))"):
                with self.subTest(needle=needle):
                    self.assertIn(needle, activity)
            self.assertIn("```mermaid\nstateDiagram-v2", run_specs(root, "template", "state.md").stdout)
            living = run_specs(root, "template", "spec.md").stdout
            self.assertLess(living.index("## Diagrams"), living.index("## Requirements"))
            use_case = run_specs(root, "template", "use-case.md").stdout
            for needle in ("Actor:", "Requirements:", "## Goal", "## Preconditions", "## Main flow", "## Alternative flows", "## Postconditions",
                           "Secondary actors:", "Trigger:", "Includes:", "Extends:", "Specializes:", "cap/slug", "## Exception flows", "## Business rules",
                           "Scheduler", "Include <slug>", "Resume at step", "Use case ends"):
                with self.subTest(needle=needle):
                    self.assertIn(needle, use_case)
            self.assertLess(living.index("## Diagrams"), living.index("## Use Cases"))
            self.assertLess(living.index("## Use Cases"), living.index("## Requirements"))
            self.assertIn("Capabilities:", run_specs(root, "template", "roadmap.md").stdout)
            self.assertIn("Capabilities: {{capabilities}}", run_specs(root, "template", "epic.md").stdout)
            task = run_specs(root, "template", "task.md").stdout
            self.assertIn("Plan: {{plan_path}}, Track {{track}}", task)
            self.assertIn("Route: {{provider_role}} / {{model}} / {{effort}}", task)
            self.assertIn("Complexity: {{complexity}}", run_specs(root, "template", "epic.md").stdout)
            self.assertIn("Complexity:", run_specs(root, "template", "roadmap.md").stdout)
            roadmap = run_specs(root, "template", "roadmap.md").stdout
            for needle in ("## Summary", "| Milestone | Period | Outcome | Demo | Epics |", "Outcome:", "Demo:", "Result:",
                           "Features:", "Legacy:", "## Legacy coverage",
                           "| Capability | Legacy screens | Epics | Milestone | Status |"):
                with self.subTest(needle=needle):
                    self.assertIn(needle, roadmap)
            epic = run_specs(root, "template", "epic.md").stdout
            self.assertIn("Features: {{features}}", epic)
            self.assertIn("Legacy: {{legacy}}", epic)
            self.assertNotIn("Demo:", epic)
            self.assertNotIn("Outcome:", epic)
            iteration = run_specs(root, "template", "iteration.md").stdout
            for needle in ("Kind:", "Source:", "Previous: none", "Confirmed: no", "## Summary", "## Changes", "## Files"):
                with self.subTest(needle=needle):
                    self.assertIn(needle, iteration)
            self.assertIn("Previous: none\nConfirmed: no\n", iteration)
            self.assertIn('"Source:"', run_specs(root, "template", "spec-delta.md").stdout)
            template = run_specs(root, "template", "spec-delta.md").stdout
            for needle in ("Type:", "Category:", "Measure:", "non-functional", "business-rule"):
                with self.subTest(needle=needle):
                    self.assertIn(needle, template)
            self.assertNotIn("--", template.split("<!--", 1)[1].split("-->", 1)[0])
            write(root, ".agent-workflow/templates/user-story.md", "### Story {{n}}\n")
            self.assertEqual("### Story {{n}}\n", run_specs(root, "template", "user-story.md").stdout)

    def test_template_comments_close_only_at_their_end(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_repo(Path(directory), layout="legacy")
            for name, hidden in (("activity.md", "Cite the file"), ("use-case.md", None)):
                with self.subTest(name=name):
                    text = run_specs(root, "template", name).stdout
                    head = text.split("```mermaid")[0]
                    self.assertEqual(head.count("<!--"), head.count("-->"))
                    if hidden:
                        self.assertIn(hidden, text)
                        self.assertNotIn(hidden, specs._COMMENT.sub("", text))

    def test_doc_templates_pass_docs_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = {"title": "Example", "version": "1.0.0", "date": "2026-10-30"}
            for name in ("readme.md", "runbook.md", "adr.md", "changelog.md"):
                with self.subTest(name=name):
                    text = specs.render(specs.template_text(root, name), values)
                    required = docs_check.required_sections(root, name)
                    self.assertEqual([], docs_check.page_findings(root / name, text, required))

    def test_exit_codes_and_layout_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_repo(Path(directory), layout="legacy")
            result = run_specs(root, "lint")
            self.assertEqual(2, result.returncode)
            self.assertIn("artifacts.layout is 'legacy'", result.stderr)
            self.assertEqual(0, run_specs(root, "template", "proposal.md").returncode)
        with tempfile.TemporaryDirectory() as directory:
            root = make_repo(Path(directory))
            write(root, "docs/specs/auth/spec.md", AUTH_SPEC)
            self.assertEqual(0, run_specs(root, "lint").returncode)
            self.assertEqual("REQ-AUTH-003", run_specs(root, "next-id", "auth").stdout.strip())
            hashed = run_specs(root, "hash", "REQ-AUTH-001", "--format", "json")
            self.assertEqual(64, len(json.loads(hashed.stdout)["hash"]))
            created = run_specs(root, "new", "lockout", "--epic", "ep-1")
            self.assertEqual("docs/changes/ep-1-lockout", created.stdout.strip())
            write(root, "docs/changes/ep-1-lockout/02-spec-delta.md", delta(added="### REQ-AUTH-003: X\nNo statement.\n"))
            linted = run_specs(root, "lint", "--change", "ep-1", "--format", "json")
            self.assertEqual(1, linted.returncode)
            self.assertEqual("findings", json.loads(linted.stdout)["status"])
            self.assertEqual(2, run_specs(root, "lint", "--change", "nope").returncode)


    def test_hash_names_in_flight_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_repo(Path(directory))
            write(root, "docs/specs/auth/spec.md", AUTH_SPEC)
            make_change(root)
            as_json = run_specs(root, "hash", "REQ-AUTH-003", "--format", "json")
            self.assertEqual("ep-1-lockout", json.loads(as_json.stdout)["change"])
            as_text = run_specs(root, "hash", "REQ-AUTH-003")
            self.assertTrue(as_text.stdout.startswith("<!-- base: "))
            self.assertIn("note: REQ-AUTH-003 is added by open change ep-1-lockout; archive it first", as_text.stderr)
            self.assertIsNone(json.loads(run_specs(root, "hash", "REQ-AUTH-001", "--format", "json").stdout)["change"])


class TestEpicKindsInSpecs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(Path(self.tmp.name) / "r", layout="legacy")

    def tearDown(self):
        self.tmp.cleanup()

    def test_kind_technical_without_stories_lints_clean(self):
        spec = write(self.root, "spec.md", "# Tech\n\nKind: technical\n\n## Goal and scope\nText\n")
        self.assertEqual([], specs.lint_design_spec(spec, self.root))

    def test_kind_parity_with_confirmed_legacy_folder_without_stories_lints_clean(self):
        p_good = "docs/specs/catalog/assets/2026-11-01"
        write(self.root, f"{p_good}/description.md", "Kind: legacy\nConfirmed: 2026-11-02\n")
        spec = write(self.root, "spec.md", f"# Parity\n\nKind: parity\nParity with: `{p_good}`\n")
        self.assertEqual([], specs.lint_design_spec(spec, self.root))

    def test_kind_parity_without_parity_line_or_bad_folders(self):
        spec_no_line = write(self.root, "no_line.md", "# Parity\n\nKind: parity\n")
        self.assertEqual(
            [f"{specs.shown(self.root, spec_no_line)}: Kind: parity needs a 'Parity with:' line naming confirmed legacy asset folders"],
            specs.lint_design_spec(spec_no_line, self.root),
        )

        spec_bad = write(self.root, "bad.md", "# Parity\n\nKind: parity\nParity with: `missing/folder`\n")
        self.assertEqual(
            [f"{specs.shown(self.root, spec_bad)}: Parity with: missing/folder is missing"],
            specs.lint_design_spec(spec_bad, self.root),
        )

    def test_kind_invalid_fails_lint(self):
        spec = write(self.root, "spec.md", "# Other\n\nKind: other\n\n### US-1: a\n\nAcceptance criteria:\n- x\n")
        self.assertEqual(
            [f"{specs.shown(self.root, spec)}:3: Kind: other is not one of capability, technical, parity"],
            specs.lint_design_spec(spec, self.root),
        )

    def test_spec_without_kind_still_needs_stories(self):
        spec = write(self.root, "spec.md", "# Cap\n\nNo stories.\n")
        self.assertEqual(
            [f"{spec}:1: no user stories (### US-<n>:)"],
            specs.lint_design_spec(spec, self.root),
        )

    def test_lint_design_spec_without_root_resolves_git_toplevel(self):
        p_good = "docs/specs/catalog/assets/2026-11-01"
        write(self.root, f"{p_good}/description.md", "Kind: legacy\nConfirmed: 2026-11-02\n")
        spec = write(self.root, "sub/spec.md", f"# Parity\n\nKind: parity\nParity with: `{p_good}`\n")
        self.assertEqual([], specs.lint_design_spec(spec))

    def test_lint_change_proposal_kinds(self):
        sdd_root = make_repo(Path(self.tmp.name) / "sdd_repo")
        write(sdd_root, "docs/specs/auth/spec.md", AUTH_SPEC)
        write_activity(sdd_root)
        cfg = specs.sdd_config(specs.load_config(sdd_root))
        change = make_change(sdd_root)

        # 1. Proposal Kind: parity with a bad folder (missing folder)
        write(sdd_root, "docs/changes/ep-1-lockout/01-proposal.md",
              "# Lockout\n\nEpic: ep-1\nKind: parity\nParity with: `docs/specs/catalog/assets/missing`\n")
        errors = specs.lint_change(sdd_root, cfg, change)
        self.assertTrue(
            any("docs/changes/ep-1-lockout/01-proposal.md: Parity with: docs/specs/catalog/assets/missing is missing" in e for e in errors),
            errors,
        )

        # 2. Proposal Kind: parity with confirmed Kind: legacy folder passes
        p_good = "docs/specs/catalog/assets/2026-11-01"
        write(sdd_root, f"{p_good}/description.md", "Kind: legacy\nConfirmed: 2026-11-02\n")
        commit_all(sdd_root)
        write(sdd_root, "docs/changes/ep-1-lockout/01-proposal.md",
              f"# Lockout\n\nEpic: ep-1\nKind: parity\nParity with: `{p_good}`\n")
        self.assertEqual([], specs.lint_change(sdd_root, cfg, change))

        # 3. Proposal Kind: other fails with invalid-kind message including location
        write(sdd_root, "docs/changes/ep-1-lockout/01-proposal.md",
              "# Lockout\n\nEpic: ep-1\nKind: other\n")
        errors = specs.lint_change(sdd_root, cfg, change)
        self.assertIn(
            "docs/changes/ep-1-lockout/01-proposal.md:4: Kind: other is not one of capability, technical, parity",
            errors,
        )

    def test_cli_specs_lint_spec_invalid_kind(self):
        spec = write(self.root, "spec.md", "# Other\n\nKind: other\n\n### US-1: a\n\nAcceptance criteria:\n- x\n")
        result = run_specs(self.root, "lint", "--spec", str(spec))
        self.assertEqual(1, result.returncode)
        self.assertIn(
            f"{specs.shown(self.root, spec)}:3: Kind: other is not one of capability, technical, parity",
            result.stdout,
        )


if __name__ == "__main__":
    unittest.main()

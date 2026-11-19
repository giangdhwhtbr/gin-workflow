"""SRS document matter as data (gin-workflow-414v.1: REQ-SRS-DATA)."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specs_fixtures import ADDED_BLOCK, AUTH_SPEC, TYPED_SPEC, USE_CASE, commit_all, delta, make_repo, write  # noqa: E402
from workflow_core import specs, specs_matter  # noqa: E402

GLOSSARY = """# GLOSSARY

## Terms

| Term | Lang | English | Meaning | Legacy identifiers | Evidence | Status |
|---|---|---|---|---|---|---|
| Đơn hàng | vi | Order | A customer's purchase | don_hang | db | confirmed |
| Giỏ | vi | Cart | Items before checkout | gio | ui | proposed |
| Hóa đơn | vi | invoice | A bill | hoa_don | db | confirmed |

## Conflicts

| Term | Lang | Existing English | Candidate | Evidence |
|---|---|---|---|---|
"""


class TestSpecsMatter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(Path(self.tmp.name) / "r")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        self.cfg = specs.sdd_config(specs.load_config(self.root))

    def tearDown(self):
        self.tmp.cleanup()

    def test_nonfunctional_and_business_rules_catalogues(self):
        write(self.root, "docs/specs/auth/spec.md", TYPED_SPEC)
        write(self.root, "docs/specs/auth/use-cases/sign-in.md", USE_CASE.replace("REQ-AUTH-002", "REQ-AUTH-005"))
        self.assertEqual([
            {"id": "REQ-AUTH-004", "title": "Sign-in response time", "capability": "auth", "category": "performance",
             "measure": "p95 below 300 ms"},
            {"id": "REQ-AUTH-006", "title": "Password storage", "capability": "auth", "category": "security",
             "measure": "bcrypt cost 12"},
        ], specs_matter.nonfunctional(self.root, self.cfg))
        self.assertEqual([
            {"id": "REQ-AUTH-005", "title": "Lockout threshold", "capability": "auth",
             "statement": "The system MUST lock an account after 5 failed sign-ins.", "use_cases": ["auth/sign-in"]},
        ], specs_matter.business_rules(self.root, self.cfg))
        self.assertEqual([], specs_matter.nonfunctional(self.root, self.cfg, "billing"))
        types = {row["id"]: row["type"] for row in specs_matter.traceability(self.root, self.cfg)}
        self.assertEqual({"REQ-AUTH-001": "functional", "REQ-AUTH-002": "functional", "REQ-AUTH-004": "non-functional",
                          "REQ-AUTH-005": "business-rule", "REQ-AUTH-006": "non-functional"}, types)

    def test_revisions_newest_first_with_capabilities_and_reqs(self):
        archive = "docs/changes/archive"
        write(self.root, f"{archive}/2026-11-01-ep-1-lockout/01-proposal.md", "# Lock accounts\n\nEpic: ep-1\n")
        write(self.root, f"{archive}/2026-11-01-ep-1-lockout/02-spec-delta.md", delta(added=ADDED_BLOCK))
        write(self.root, f"{archive}/2026-11-03-ep-2-tech/01-proposal.md", "# Faster login\n\nEpic: ep-2\nKind: technical\n")
        write(self.root, f"{archive}/notes/readme.md", "not a change\n")
        self.assertEqual([
            {"date": "2026-11-03", "epic": "ep-2", "title": "Faster login", "capabilities": [],
             "added": [], "modified": [], "removed": []},
            {"date": "2026-11-01", "epic": "ep-1", "title": "Lock accounts", "capabilities": ["auth"],
             "added": ["REQ-AUTH-003"], "modified": [], "removed": []},
        ], specs_matter.revisions(self.root, self.cfg))
        self.assertEqual(["2026-11-01"], [row["date"] for row in specs_matter.revisions(self.root, self.cfg, "auth")])

    def test_revisions_without_archive_or_proposal(self):
        self.assertEqual([], specs_matter.revisions(self.root, self.cfg))
        write(self.root, "docs/changes/archive/2026-11-05-ep-3-misc/02-spec-delta.md", delta(added=ADDED_BLOCK))
        row = specs_matter.revisions(self.root, self.cfg)[0]
        self.assertEqual(("ep-3-misc", ""), (row["title"], row["epic"]))

    def test_glossary_keeps_confirmed_rows_sorted_by_english(self):
        self.assertEqual([], specs_matter.glossary(self.root, self.cfg))
        write(self.root, "docs/codebase/11-GLOSSARY.md", GLOSSARY)
        self.assertEqual([
            {"english": "invoice", "term": "Hóa đơn", "lang": "vi", "meaning": "A bill"},
            {"english": "Order", "term": "Đơn hàng", "lang": "vi", "meaning": "A customer's purchase"},
        ], specs_matter.glossary(self.root, self.cfg))

    def test_glossary_reads_columns_by_header(self):
        write(self.root, "docs/codebase/11-GLOSSARY.md",
              "# G\n\n## Terms\n\n| Status | English | Term | Lang | Meaning |\n|---|---|---|---|---|\n"
              "| confirmed | Invoice | Hóa đơn | vi | A bill |\n")
        self.assertEqual(["Invoice"], [row["english"] for row in specs_matter.glossary(self.root, self.cfg)])

    def test_actors_merge_spellings_mark_secondary_and_take_descriptions(self):
        write(self.root, "docs/specs/auth/use-cases/sign-in.md", USE_CASE.replace("Registered user", "Customer").replace(
            "Requirements:", "Secondary actors: Mail service\nRequirements:"))
        write(self.root, "docs/specs/auth/use-cases/sign-out.md", USE_CASE.replace("Registered user", "customer"))
        write(self.root, "docs/specs/billing/spec.md", "# Billing\n\n## Purpose\n\nInvoices.\n\n## Requirements\n")
        write(self.root, "docs/specs/billing/use-cases/pay.md", USE_CASE.replace("Registered user", "Accountant"))
        write(self.root, "docs/specs/actors.md", "| Actor | Description |\n|---|---|\n| CUSTOMER | Buys things |\n")
        self.assertEqual([
            {"actor": "Accountant", "description": "", "use_cases": [{"ref": "billing/pay", "secondary": False}]},
            {"actor": "Customer", "description": "Buys things",
             "use_cases": [{"ref": "auth/sign-in", "secondary": False}, {"ref": "auth/sign-out", "secondary": False}]},
            {"actor": "Mail service", "description": "", "use_cases": [{"ref": "auth/sign-in", "secondary": True}]},
        ], specs_matter.actors(self.root, self.cfg))
        self.assertEqual(["Customer", "Mail service"],
                         [row["actor"] for row in specs_matter.actors(self.root, self.cfg, "auth")])

    def test_traceability_rows_link_use_cases_tests_and_qa_cases(self):
        write(self.root, "docs/specs/auth/use-cases/sign-in.md", USE_CASE)
        write(self.root, "tests/test_login.py", "def test_login():  # REQ-AUTH-001\n    pass\n")
        write(self.root, "qa/cases/auth/TC-AUTH-001-login.md", "# Login\n\nREQ: REQ-AUTH-001\n")
        commit_all(self.root)
        self.assertEqual([
            {"id": "REQ-AUTH-001", "title": "Sign in with password", "capability": "auth", "type": "functional",
             "use_cases": ["auth/sign-in"], "tests": ["tests/test_login.py"], "qa_cases": ["TC-AUTH-001"],
             "status": "covered"},
            {"id": "REQ-AUTH-002", "title": "Reject wrong password", "capability": "auth", "type": "functional",
             "use_cases": ["auth/sign-in"], "tests": [], "qa_cases": [], "status": "missing"},
        ], specs_matter.traceability(self.root, self.cfg))

    def test_traceability_reads_configured_qa_cases_and_filters_by_capability(self):
        root = make_repo(Path(self.tmp.name) / "q", extra="qa:\n  cases: spec-cases\n")
        write(root, "docs/specs/auth/spec.md", AUTH_SPEC)
        write(root, "spec-cases/TC-AUTH-002-wrong.md", "Covers REQ-AUTH-002.\n")
        cfg = specs.sdd_config(specs.load_config(root))
        self.assertEqual(["TC-AUTH-002"], specs_matter.traceability(root, cfg, "auth")[1]["qa_cases"])
        self.assertEqual([], specs_matter.traceability(root, cfg, "billing"))


class TestSpecsMatterEdges(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(Path(self.tmp.name) / "r")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        self.cfg = specs.sdd_config(specs.load_config(self.root))

    def tearDown(self):
        self.tmp.cleanup()

    def bad(self, relative):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\xff\xfe")

    def test_unreadable_files_are_skipped(self):
        self.bad("docs/codebase/11-GLOSSARY.md")
        self.assertEqual([], specs_matter.glossary(self.root, self.cfg))
        self.bad("docs/specs/actors.md")
        self.bad("docs/specs/auth/use-cases/broken.md")
        write(self.root, "docs/specs/auth/use-cases/sign-in.md", USE_CASE)
        self.assertEqual(["Registered user"], [row["actor"] for row in specs_matter.actors(self.root, self.cfg)])
        self.assertEqual(["auth/sign-in"], specs_matter.traceability(self.root, self.cfg)[0]["use_cases"])
        self.bad("docs/changes/archive/2026-11-01-ep-1-x/01-proposal.md")
        write(self.root, "docs/changes/archive/2026-11-01-ep-1-x/02-spec-delta.md", delta(added=ADDED_BLOCK))
        row = specs_matter.revisions(self.root, self.cfg)[0]
        self.assertEqual(("ep-1-x", ["REQ-AUTH-003"]), (row["title"], row["added"]))
        self.assertEqual(["docs/specs/actors.md: cannot be read as UTF-8 text"], specs.lint_actors(self.root, self.cfg))

    def test_table_rows_escaped_pipe_padding_and_comments(self):
        table = specs.table_rows("| A | B |\n|---|---|\n| x \\| y | z |\n| only |\n")
        self.assertEqual([(3, {"A": "x | y", "B": "z"}), (4, {"A": "only", "B": ""})], table[1])
        text = "<!--\n| Actor | Description |\n|---|---|\n| Example | e |\n-->\n| Actor | Description |\n|---|---|\n| Real | r |\n"
        self.assertEqual([(8, {"Actor": "Real", "Description": "r"})], specs.table_rows(text)[1])

    def test_traceability_sorts_ids_by_number(self):
        spec = AUTH_SPEC + "\n### REQ-AUTH-1000: Big\n\nThe system SHALL be big.\n\n#### Scenario: s\n- GIVEN a\n- WHEN b\n- THEN c\n"
        spec = spec.replace("REQ-AUTH-002", "REQ-AUTH-999")
        write(self.root, "docs/specs/auth/spec.md", spec)
        ids = [row["id"] for row in specs_matter.traceability(self.root, self.cfg)]
        self.assertEqual(["REQ-AUTH-001", "REQ-AUTH-999", "REQ-AUTH-1000"], ids)

    def test_qa_cases_dir_stays_inside_the_repository(self):
        root = make_repo(Path(self.tmp.name) / "q1", extra="qa:\n  dir: checks\n")
        write(root, "docs/specs/auth/spec.md", AUTH_SPEC)
        write(root, "checks/cases/TC-AUTH-001-a.md", "REQ-AUTH-001\n")
        cfg = specs.sdd_config(specs.load_config(root))
        self.assertEqual(["TC-AUTH-001"], specs_matter.traceability(root, cfg)[0]["qa_cases"])
        outside = make_repo(Path(self.tmp.name) / "q2", extra="qa:\n  cases: ../outside\n")
        write(outside, "docs/specs/auth/spec.md", AUTH_SPEC)
        write(outside, "../outside/TC-AUTH-001-a.md", "REQ-AUTH-001\n")
        cfg = specs.sdd_config(specs.load_config(outside))
        self.assertEqual([], specs_matter.traceability(outside, cfg)[0]["qa_cases"])

    def test_actor_named_primary_and_secondary_counts_once(self):
        write(self.root, "docs/specs/auth/use-cases/sign-in.md", USE_CASE.replace(
            "Requirements:", "Secondary actors: registered user\nRequirements:"))
        self.assertEqual([{"actor": "Registered user", "description": "",
                           "use_cases": [{"ref": "auth/sign-in", "secondary": False}]}],
                         specs_matter.actors(self.root, self.cfg))

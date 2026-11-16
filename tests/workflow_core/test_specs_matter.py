"""SRS document matter as data (gin-workflow-414v.1: REQ-SRS-DATA)."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specs_fixtures import ADDED_BLOCK, AUTH_SPEC, USE_CASE, commit_all, delta, make_repo, write  # noqa: E402
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
            {"id": "REQ-AUTH-001", "title": "Sign in with password", "capability": "auth",
             "use_cases": ["auth/sign-in"], "tests": ["tests/test_login.py"], "qa_cases": ["TC-AUTH-001"],
             "status": "covered"},
            {"id": "REQ-AUTH-002", "title": "Reject wrong password", "capability": "auth",
             "use_cases": ["auth/sign-in"], "tests": [], "qa_cases": [], "status": "missing"},
        ], specs_matter.traceability(self.root, self.cfg))

    def test_traceability_reads_configured_qa_cases_and_filters_by_capability(self):
        root = make_repo(Path(self.tmp.name) / "q", extra="qa:\n  cases: spec-cases\n")
        write(root, "docs/specs/auth/spec.md", AUTH_SPEC)
        write(root, "spec-cases/TC-AUTH-002-wrong.md", "Covers REQ-AUTH-002.\n")
        cfg = specs.sdd_config(specs.load_config(root))
        self.assertEqual(["TC-AUTH-002"], specs_matter.traceability(root, cfg, "auth")[1]["qa_cases"])
        self.assertEqual([], specs_matter.traceability(root, cfg, "billing"))

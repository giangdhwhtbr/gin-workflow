"""Open technical questions: parser, lint, design doc lookup, and the plan-approved check (gin-workflow-746z)."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tests.workflow_core.specs_fixtures import make_change, make_repo, write, write_activity
from tests.workflow_core.team_fixtures import calls, fake_cli, make_team_repo, path_with, run_cli
from tests.workflow_core.test_workspace import make_workspace
from workflow_core import specs
from workflow_core.cli import main as cli_main

SPEC_PATH = ".planning/specs/2026-01-01-x-design.md"


def spec(questions: str, id_line: str = "Epic: ep-1") -> str:
    """A legacy spec whose first question sits on line 12."""
    return (f"# T\n\n{id_line}\n\n### US-1: a\n\nAcceptance criteria:\n- x\n\n"
            f"## Open Technical Questions\n\n{questions}")


class _Repo(unittest.TestCase):
    layout = "legacy"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = make_repo(Path(self.tmp.name) / "r", layout=self.layout)

    def cfg(self):
        return specs.sdd_config(specs.load_config(self.root))


class TestParse(_Repo):
    def parse(self, text: str):
        return specs.technical_questions(write(self.root, "spec.md", text))

    def test_open_and_decided_questions(self):
        found, errors = self.parse(spec("- TQ-1: Table or JSON column?\n  Decision: a table, queried by date.\n"
                                        "- TQ-2: Which queue?\n"))
        self.assertEqual([], errors)
        self.assertEqual([("TQ-1", 12, "a table, queried by date."), ("TQ-2", 14, "")],
                         [(q.id, q.line, q.decision) for q in found])

    def test_format_errors(self):
        found, errors = self.parse(spec("- TQ-1: a\n  Decision:\n- TQ-1: b\nfree text\n  Decision: orphan\n"))
        self.assertEqual(["TQ-1", "TQ-1"], [q.id for q in found])
        self.assertEqual(4, len(errors), errors)
        for expected, error in zip((":13: TQ-1 has an empty Decision:", ":14: TQ-1 appears twice",
                                    ":15: not a question", ":16: Decision: without a question"), errors):
            self.assertIn(expected, error)

    def test_comments_fences_and_other_sections_are_ignored(self):
        found, errors = self.parse(spec("<!-- - TQ-9: in a comment\n     spanning lines -->\n"
                                        "```\n- TQ-8: in code\n```\n- TQ-1: real\n\n## Notes\n\n- TQ-7: elsewhere\n"))
        self.assertEqual([], errors)
        self.assertEqual([("TQ-1", 17)], [(q.id, q.line) for q in found])

    def test_no_section(self):
        self.assertEqual(([], []), self.parse("# T\n\ntext\n"))

    def test_label_names_the_file_in_errors(self):
        path = write(self.root, "spec.md", spec("stray\n"))
        self.assertTrue(specs.technical_questions(path, "x/spec.md")[1][0].startswith("x/spec.md:12: "))


class TestLint(_Repo):
    def test_legacy_lint_reports_format_but_not_open_questions(self):
        self.assertEqual([], specs.lint_design_spec(write(self.root, "open.md", spec("- TQ-1: a\n"))))
        errors = specs.lint_design_spec(write(self.root, "bad.md", spec("- TQ-1: a\n  Decision:\n")))
        self.assertEqual(1, len(errors))
        self.assertIn(":13: TQ-1 has an empty Decision:", errors[0])


class TestChangeLint(_Repo):
    layout = "sdd"

    def test_change_lint_reads_the_design_file(self):
        change = make_change(self.root)
        write_activity(self.root)
        before = specs.lint_change(self.root, self.cfg(), change)
        write(self.root, "docs/changes/ep-1-lockout/03-design.md",
              "# Design\n\n## Open Technical Questions\n\nstray\n")
        after = specs.lint_change(self.root, self.cfg(), change)
        self.assertEqual(["docs/changes/ep-1-lockout/03-design.md:5: not a question (- TQ-<n>: <question>) "
                          "or its Decision: line"], [error for error in after if error not in before])


class TestDesignDoc(_Repo):
    def test_legacy_spec_by_epic_or_workflow_line(self):
        first = write(self.root, SPEC_PATH, spec(""))
        second = write(self.root, ".planning/specs/2026-01-02-b-design.md", spec("", "Workflow: topic-b"))
        self.assertEqual(first, specs.design_doc(self.root, self.cfg(), "ep-1"))
        self.assertEqual(second, specs.design_doc(self.root, self.cfg(), "topic-b"))
        self.assertIsNone(specs.design_doc(self.root, self.cfg(), "ep-10"))
        self.assertIsNone(specs.design_doc(self.root, self.cfg(), "ep"))

    def test_legacy_without_specs_folder(self):
        self.assertIsNone(specs.design_doc(self.root, self.cfg(), "ep-1"))

    def test_two_legacy_specs_for_one_id_is_an_error(self):
        write(self.root, SPEC_PATH, spec(""))
        write(self.root, ".planning/specs/2026-01-02-b-design.md", spec(""))
        with self.assertRaisesRegex(specs.SpecsError, "several specs name ep-1: .planning/specs/2026-01-01"):
            specs.design_doc(self.root, self.cfg(), "ep-1")


class TestSddDesignDoc(_Repo):
    layout = "sdd"

    def test_change_design_file(self):
        make_change(self.root)
        self.assertIsNone(specs.design_doc(self.root, self.cfg(), "ep-1"))
        design = write(self.root, "docs/changes/ep-1-lockout/03-design.md", "# Design\n")
        self.assertEqual(design, specs.design_doc(self.root, self.cfg(), "ep-1"))
        self.assertIsNone(specs.design_doc(self.root, self.cfg(), "ep-2"))

    def test_ambiguous_change_is_an_error(self):
        make_change(self.root, "ep-1-a")
        make_change(self.root, "ep-1-b")
        with self.assertRaisesRegex(specs.SpecsError, "ambiguous"):
            specs.design_doc(self.root, self.cfg(), "ep-1")


class TestPlanApprovedCheck(_Repo):
    def setUp(self):
        super().setUp()
        self.spec = write(self.root, SPEC_PATH, spec("- TQ-1: Table or JSON column?\n"))

    def record(self, workflow: str = "ep-1"):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = cli_main(["record", "plan-approved", "--repository", str(self.root), "--evidence", "plan.md",
                             "--actor", "user", "--workflow-id", workflow])
        return code, err.getvalue()

    def gate(self, workflow: str = "ep-1") -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli_main(["state", "--repository", str(self.root), "--format", "json", "--workflow-id", workflow])
        return json.loads(out.getvalue())["gates"]["plan_approved"]

    def test_open_question_refuses_the_gate(self):
        code, err = self.record()
        self.assertEqual(1, code)
        self.assertIn("plan-approved refused: open technical questions", err)
        self.assertIn(f"{SPEC_PATH}:12: TQ-1", err)
        self.assertEqual("unmet", self.gate())

    def test_decided_questions_record_the_gate(self):
        self.spec.write_text(spec("- TQ-1: Table or JSON column?\n  Decision: a table.\n"), encoding="utf-8")
        self.assertEqual(0, self.record()[0])
        self.assertEqual("satisfied", self.gate())

    def test_workflow_without_design_doc_records_as_today(self):
        self.assertEqual(0, self.record("other")[0])
        self.assertEqual("satisfied", self.gate("other"))

    def test_unrelated_non_utf8_spec_does_not_stop_the_check(self):
        (self.root / ".planning/specs/2026-01-03-bad-design.md").write_bytes(b"# B\n\nEpic: other\n\ncaf\xe9\n")
        code, err = self.record()
        self.assertEqual(1, code)
        self.assertIn("TQ-1", err)
        self.assertEqual(0, self.record("no-spec-workflow")[0])

    def test_non_utf8_design_doc_is_a_usage_error_naming_the_file(self):
        bad = ".planning/specs/2026-01-03-bad-design.md"
        (self.root / bad).write_bytes(b"# B\n\nEpic: ep-9\n\ncaf\xe9\n")
        code, err = self.record("ep-9")
        self.assertEqual(2, code)
        self.assertIn(bad, err)
        self.assertEqual("unmet", self.gate("ep-9"))

    def test_two_specs_for_one_epic_is_a_usage_error(self):
        write(self.root, ".planning/specs/2026-01-02-y-design.md", spec(""))
        code, err = self.record()
        self.assertEqual(2, code)
        self.assertIn("several specs name ep-1", err)

    def test_check_runs_before_the_team_pull_request_check(self):
        root = make_team_repo(Path(self.tmp.name) / "team")
        write(root, SPEC_PATH, spec("- TQ-1: a\n"))
        bin_dir = Path(self.tmp.name) / "bin"
        fake_cli(bin_dir, "gh", [])
        result = run_cli(root, "record", "plan-approved", "--evidence", "https://github.com/org/app/pull/7",
                         "--workflow-id", "ep-1", env=path_with(bin_dir))
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn("open technical questions", result.stderr)
        self.assertEqual([], calls(bin_dir))


class PlanApprovedWorkspaceTests(unittest.TestCase):
    """In a workspace, plan-approved also needs every track on one workable `Repo:` (gin-workflow-workspace)."""

    PLAN = ("# Plan\n\n## Tasks\n\n### Track 1: API\n- **Repo**: `services/api`\n- **Files**:\n"
            "  - Modify `services/api/a.py`\n\n## Integration\n")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = make_workspace(Path(self.tmp.name))

    def record(self, workflow: str = "ep-1", evidence: str = ".planning/plans/p.md"):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = cli_main(["record", "plan-approved", "--repository", str(self.root), "--evidence", evidence,
                             "--actor", "user", "--workflow-id", workflow])
        return code, err.getvalue()

    gate = TestPlanApprovedCheck.gate

    def test_valid_plan_records_the_gate(self):
        write(self.root, ".planning/plans/p.md", self.PLAN)
        self.assertEqual(0, self.record()[0])
        self.assertEqual("satisfied", self.gate())

    def test_bad_tracks_refuse_the_gate(self):
        write(self.root, ".planning/plans/p.md", self.PLAN.replace("services/api", "legacy/portal"))
        code, err = self.record()
        self.assertEqual(1, code)
        self.assertIn("plan-approved refused: workspace tracks\nTrack 1: Repo: legacy/portal is frozen", err)
        self.assertEqual("unmet", self.gate())

    def test_evidence_without_a_plan_file_is_refused(self):
        code, err = self.record(evidence="pr-123")
        self.assertEqual(1, code)
        self.assertIn("plan-approved refused: a workspace needs the plan file as --plan or --evidence", err)
        self.assertEqual("unmet", self.gate())


if __name__ == "__main__":
    unittest.main()

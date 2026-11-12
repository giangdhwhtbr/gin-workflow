"""Unit tests for workflow_core.epic_kind."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.workflow_core.specs_fixtures import make_repo, write
from workflow_core import epic_kind


class TestEpicKind(unittest.TestCase):
    def test_kinds_and_default(self):
        self.assertEqual(("capability", "technical", "parity"), epic_kind.KINDS)
        self.assertEqual("capability", epic_kind.DEFAULT)

    def test_spec_kind_parsing(self):
        self.assertIsNone(epic_kind.spec_kind(""))
        self.assertIsNone(epic_kind.spec_kind("# Title\n\nSome text\n"))
        self.assertEqual("technical", epic_kind.spec_kind("# Title\n\nKind: technical\n"))
        self.assertEqual("parity", epic_kind.spec_kind("Kind: parity\n"))
        self.assertEqual("capability", epic_kind.spec_kind("Kind:   capability  \n"))

    def test_spec_kind_line(self):
        self.assertIsNone(epic_kind.spec_kind_line(""))
        self.assertIsNone(epic_kind.spec_kind_line("# Title\n\nSome text\n"))
        self.assertEqual(("technical", 3), epic_kind.spec_kind_line("# Title\n\nKind: technical\n"))
        self.assertEqual(("parity", 1), epic_kind.spec_kind_line("Kind: parity\n"))

    def test_spec_kind_ignores_code_fences(self):
        text = """# Title

```markdown
Kind: technical
```

Kind: parity
"""
        self.assertEqual("parity", epic_kind.spec_kind(text))
        self.assertEqual(("parity", 7), epic_kind.spec_kind_line(text))

        fenced_only = """# Title
```
Kind: technical
```
"""
        self.assertIsNone(epic_kind.spec_kind(fenced_only))
        self.assertIsNone(epic_kind.spec_kind_line(fenced_only))

    def test_label_kinds(self):
        self.assertEqual([], epic_kind.label_kinds([]))
        self.assertEqual([], epic_kind.label_kinds(["roadmap", "team-ready"]))
        self.assertEqual(["technical"], epic_kind.label_kinds(["roadmap", "kind:technical", "kind:technical"]))
        self.assertEqual(["parity", "technical"], epic_kind.label_kinds(["kind:parity", "kind:technical"]))

    def test_invalid_message(self):
        self.assertIsNone(epic_kind.invalid(None))
        self.assertIsNone(epic_kind.invalid("capability"))
        self.assertIsNone(epic_kind.invalid("technical"))
        self.assertIsNone(epic_kind.invalid("parity"))
        self.assertEqual(
            "Kind: other is not one of capability, technical, parity",
            epic_kind.invalid("other"),
        )
        self.assertEqual(
            "Kind: foo is not one of capability, technical, parity",
            epic_kind.invalid("foo"),
        )

    def test_parity_sources(self):
        self.assertEqual([], epic_kind.parity_sources(""))
        self.assertEqual([], epic_kind.parity_sources("No parity line here"))
        self.assertEqual(
            ["docs/specs/catalog/assets/2026-11-01"],
            epic_kind.parity_sources("Parity with: `docs/specs/catalog/assets/2026-11-01`"),
        )
        self.assertEqual(
            ["assets/a", "assets/b"],
            epic_kind.parity_sources("Parity with: `assets/a`, `assets/b`\nSome other text"),
        )

    def test_parity_errors_for_all_reasons(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "r")

            # 1. No parity line or no paths
            errors = epic_kind.parity_errors(root, "Kind: parity\n", "spec.md")
            self.assertEqual(
                ["spec.md: Kind: parity needs a 'Parity with:' line naming confirmed legacy asset folders"],
                errors,
            )

            # 2. Confirmed legacy asset folder -> ok
            p_good = "docs/specs/catalog/assets/2026-11-01"
            write(root, f"{p_good}/description.md", "Kind: legacy\nConfirmed: 2026-11-02\n")
            text_good = f"Kind: parity\nParity with: `{p_good}`\n"
            self.assertEqual([], epic_kind.parity_errors(root, text_good, "spec.md"))

            # 3. Missing folder
            p_missing = "docs/specs/catalog/assets/missing"
            text_missing = f"Parity with: `{p_missing}`\n"
            self.assertEqual(
                [f"spec.md: Parity with: {p_missing} is missing"],
                epic_kind.parity_errors(root, text_missing, "spec.md"),
            )

            # 4. Folder has no description.md
            p_no_desc = "docs/specs/catalog/assets/no-desc"
            (root / p_no_desc).mkdir(parents=True)
            text_no_desc = f"Parity with: `{p_no_desc}`\n"
            self.assertEqual(
                [f"spec.md: Parity with: {p_no_desc} has no description.md"],
                epic_kind.parity_errors(root, text_no_desc, "spec.md"),
            )

            # 5. Not Kind: legacy (e.g. Kind: new)
            p_new = "docs/specs/catalog/assets/new"
            write(root, f"{p_new}/description.md", "Kind: new\nConfirmed: 2026-11-02\n")
            text_new = f"Parity with: `{p_new}`\n"
            self.assertEqual(
                [f"spec.md: Parity with: {p_new} is not Kind: legacy"],
                epic_kind.parity_errors(root, text_new, "spec.md"),
            )

            # 6. Not confirmed
            p_unconf = "docs/specs/catalog/assets/unconf"
            write(root, f"{p_unconf}/description.md", "Kind: legacy\n")
            text_unconf = f"Parity with: `{p_unconf}`\n"
            self.assertEqual(
                [f"spec.md: Parity with: {p_unconf} is not confirmed"],
                epic_kind.parity_errors(root, text_unconf, "spec.md"),
            )

            # 7. Two folders: one good, one unconfirmed -> exactly one error
            text_two = f"Parity with: `{p_good}`, `{p_unconf}`\n"
            self.assertEqual(
                [f"spec.md: Parity with: {p_unconf} is not confirmed"],
                epic_kind.parity_errors(root, text_two, "spec.md"),
            )


NOT_FOUND = 'bd exited 1: Error fetching e-1: no issue found matching "e-1"'


class TestLookup(unittest.TestCase):
    """epic-kinds R2, R4, R9: the bead's `kind:` label, else the spec's `Kind:` line, else capability. A bead whose
    kind cannot be read is an error: the spec's `Kind:` never stands in for it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write(self.root, "spec.md", "# Spec\n\nKind: technical\n")

    def tearDown(self):
        self.tmp.cleanup()

    def lookup(self, shown, workflow_id, spec_path, cause=None):
        with mock.patch("workflow_core.tasks.query_result", return_value=(shown, cause)) as query:
            return epic_kind.lookup(self.root, workflow_id, spec_path), query

    def test_default_without_a_bead_or_a_spec(self):
        result, query = self.lookup(None, None, None)
        self.assertEqual(("capability", None), result)
        query.assert_not_called()
        self.assertEqual(("capability", None), self.lookup(None, "e-1", "missing.md", NOT_FOUND)[0])

    def test_bead_label_in_either_json_shape(self):
        for shown in ([{"id": "e-1", "labels": ["roadmap", "kind:parity"]}], {"id": "e-1", "labels": ["kind:parity"]}):
            with self.subTest(shown=shown):
                result, query = self.lookup(shown, "e-1", None)
                self.assertEqual(("parity", None), result)
                query.assert_called_once_with(self.root, ["show", "e-1"])

    def test_spec_kind_when_the_bead_has_none(self):
        # bd's not-found: the workflow id is not a bead; or a bead without a kind: label.
        for shown, cause in ((None, NOT_FOUND), ([{"id": "e-1", "labels": ["roadmap"]}], None),
                             ([{"id": "e-1"}], None)):
            with self.subTest(shown=shown):
                self.assertEqual(("technical", None), self.lookup(shown, "e-1", "spec.md", cause)[0])
        self.assertEqual(("technical", None), self.lookup(None, None, self.root / "spec.md")[0])

    def test_unreadable_bead_is_an_error_not_the_spec_kind(self):
        for cause in ("bd not found", "bd timed out after 30s", "bd exited 1: Error: failed to connect to dolt server",
                      "invalid JSON from bd"):
            with self.subTest(cause=cause):
                self.assertEqual(("capability", f"cannot read the kind of epic e-1: {cause}"),
                                 self.lookup(None, "e-1", "spec.md", cause)[0])
        self.assertEqual(("capability", "cannot read the kind of epic e-1: unexpected show output"),
                         self.lookup([{"id": "e-1"}, {"id": "e-2"}], "e-1", "spec.md")[0])

    def test_a_missing_beads_database_is_no_bead_outside_team_mode(self):
        cause = "bd exited 1: Error: no beads database found"
        self.assertEqual(("technical", None), self.lookup(None, "e-1", "spec.md", cause)[0])

    def test_markdown_tasks_tell_an_unknown_id_from_unreadable_files(self):
        self.assertEqual(("technical", None), epic_kind.lookup(self.root, "e-1", "spec.md"))
        write(self.root, ".planning/tasks/e-1/e-1.md", "---\nid: e-1\ntitle: Epic\nlabels: [kind:parity]\n---\n")
        self.assertEqual(("parity", None), epic_kind.lookup(self.root, "e-1", None))
        write(self.root, ".planning/tasks/e-2/e-2.md", "no frontmatter\n")
        kind, error = epic_kind.lookup(self.root, "e-3", "spec.md")
        self.assertEqual(("capability", "cannot read the kind of epic e-3: markdown task query failed"), (kind, error))

    def test_invalid_or_several_kind_labels_are_errors(self):
        self.assertEqual(
            ("capability", "epic e-1: Kind: foo is not one of capability, technical, parity"),
            self.lookup([{"id": "e-1", "labels": ["kind:foo"]}], "e-1", "spec.md")[0])
        self.assertEqual(
            ("capability", "epic e-1 has several kind labels: technical, capability"),
            self.lookup([{"id": "e-1", "labels": ["kind:technical", "roadmap", "kind:capability"]}], "e-1", None)[0])
        self.assertEqual(("technical", None),
                         self.lookup([{"id": "e-1", "labels": ["kind:technical", "kind:technical"]}], "e-1", None)[0])

    def test_agreeing_kinds(self):
        self.assertEqual(("technical", None), self.lookup([{"labels": ["kind:technical"]}], "e-1", "spec.md")[0])

    def test_mismatch_names_both_kinds(self):
        result, _ = self.lookup([{"id": "e-1", "labels": ["kind:capability"]}], "e-1", "spec.md")
        self.assertEqual(("capability", "kind mismatch: epic e-1 is kind:capability, spec spec.md says Kind: technical"),
                         result)

    def test_sdd_change_takes_the_kind_of_its_proposal(self):
        write(self.root, "docs/changes/c-1/01-proposal.md", "# Proposal\n\nEpic: e-1\nKind: parity\n")
        write(self.root, "docs/changes/c-1/02-spec-delta.md", "# Spec Delta\n")
        for path in ("docs/changes/c-1", "docs/changes/c-1/02-spec-delta.md", "docs/changes/c-1/01-proposal.md"):
            with self.subTest(path=path):
                self.assertEqual(("parity", None), self.lookup(None, None, path)[0])
        # The mismatch names the file the Kind: line was read from.
        result, _ = self.lookup([{"labels": ["kind:technical"]}], "e-1", "docs/changes/c-1/02-spec-delta.md")
        self.assertEqual("kind mismatch: epic e-1 is kind:technical, spec docs/changes/c-1/01-proposal.md "
                         "says Kind: parity", result[1])


if __name__ == "__main__":
    unittest.main()

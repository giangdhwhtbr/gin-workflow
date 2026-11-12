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

    def test_label_kind(self):
        self.assertIsNone(epic_kind.label_kind([]))
        self.assertIsNone(epic_kind.label_kind(["roadmap", "team-ready"]))
        self.assertEqual("technical", epic_kind.label_kind(["roadmap", "kind:technical"]))
        self.assertEqual("parity", epic_kind.label_kind(["kind:parity", "kind:technical"]))

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


class TestLookup(unittest.TestCase):
    """epic-kinds R2, R4, R9: the bead's `kind:` label, else the spec's `Kind:` line, else capability."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write(self.root, "spec.md", "# Spec\n\nKind: technical\n")

    def tearDown(self):
        self.tmp.cleanup()

    def lookup(self, shown, workflow_id, spec_path):
        with mock.patch("workflow_core.tasks.query", return_value=shown) as query:
            return epic_kind.lookup(self.root, workflow_id, spec_path), query

    def test_default_without_a_bead_or_a_spec(self):
        result, query = self.lookup(None, None, None)
        self.assertEqual(("capability", None), result)
        query.assert_not_called()
        self.assertEqual(("capability", None), self.lookup(None, "e-1", "missing.md")[0])

    def test_bead_label_in_either_json_shape(self):
        for shown in ([{"id": "e-1", "labels": ["roadmap", "kind:parity"]}], {"id": "e-1", "labels": ["kind:parity"]}):
            with self.subTest(shown=shown):
                result, query = self.lookup(shown, "e-1", None)
                self.assertEqual(("parity", None), result)
                query.assert_called_once_with(self.root, ["show", "e-1"])

    def test_spec_kind_when_the_bead_has_none(self):
        # None: the tracker is unavailable or the workflow id is not a bead.
        for shown in (None, [{"id": "e-1", "labels": ["roadmap"]}], [{"id": "e-1"}]):
            with self.subTest(shown=shown):
                self.assertEqual(("technical", None), self.lookup(shown, "e-1", "spec.md")[0])
        self.assertEqual(("technical", None), self.lookup(None, None, self.root / "spec.md")[0])

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
        result, _ = self.lookup([{"labels": ["kind:technical"]}], "e-1", "docs/changes/c-1/02-spec-delta.md")
        self.assertEqual("kind mismatch: epic e-1 is kind:technical, spec docs/changes/c-1/02-spec-delta.md "
                         "says Kind: parity", result[1])


if __name__ == "__main__":
    unittest.main()

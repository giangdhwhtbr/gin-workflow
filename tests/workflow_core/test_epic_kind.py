"""Unit tests for workflow_core.epic_kind."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

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

    def test_spec_kind_ignores_code_fences(self):
        text = """# Title

```markdown
Kind: technical
```

Kind: parity
"""
        self.assertEqual("parity", epic_kind.spec_kind(text))

        fenced_only = """# Title
```
Kind: technical
```
"""
        self.assertIsNone(epic_kind.spec_kind(fenced_only))

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


if __name__ == "__main__":
    unittest.main()

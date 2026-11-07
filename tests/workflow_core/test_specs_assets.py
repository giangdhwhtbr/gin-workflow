"""`gin specs assets add|confirm` and the asset lint (Confirmed: values, folders frozen on the base)."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specs_fixtures import LAUNCHER, commit_all, git, make_repo, write  # noqa: E402
from workflow_core import specs, specs_assets  # noqa: E402
from workflow_core.specs import SpecsError  # noqa: E402

FOLDER = "docs/specs/orders/assets/2026-11-07"


def run_specs(root: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(LAUNCHER), "specs", *args, "--repository", str(root)],
                          text=True, capture_output=True, check=False, cwd=cwd)


class AssetsCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.root = make_repo(base / "repo")
        self.cfg = specs.sdd_config(specs.load_config(self.root))
        write(self.root, "docs/specs/orders/spec.md", "# Orders\n")
        self.outside = base / "desktop"
        self.outside.mkdir()
        (self.outside / "a.png").write_bytes(b"\x89PNG a")
        (self.outside / "brief.pdf").write_bytes(b"%PDF brief")

    def add(self, *files: Path, **options):
        return specs_assets.add(self.root, self.cfg, options.pop("cap", "orders"), list(files),
                                **{"day": "2026-11-07", **options})

    def description(self, day: str = "2026-11-07", cap: str = "orders") -> str:
        return (self.root / f"docs/specs/{cap}/assets/{day}/description.md").read_text(encoding="utf-8")


class TestAssetsAdd(AssetsCase):
    def test_legacy_screenshots_from_outside_the_repository(self):
        result = self.add(self.outside / "a.png", legacy=True)
        self.assertEqual(b"\x89PNG a", (self.root / FOLDER / "legacy/a.png").read_bytes())
        self.assertTrue((self.outside / "a.png").is_file())
        text = self.description()
        for line in ("# orders: 2026-11-07\n", "Kind: legacy\n", "Previous: none\n", "Confirmed: no\n"):
            self.assertIn(line, text)
        self.assertEqual({"folder": FOLDER, "description": f"{FOLDER}/description.md", "created": True,
                          "files": [f"{FOLDER}/legacy/a.png"]}, result)

    def test_kind_and_previous_follow_earlier_dated_folders(self):
        write(self.root, "docs/specs/orders/assets/mockup/index.html", "<html>")
        self.add(day="2026-01-05")
        self.assertIn("Kind: new\n", self.description("2026-01-05"))
        self.assertIn("Previous: none\n", self.description("2026-01-05"))
        self.add(day="2026-03-01")
        self.assertIn("Kind: change\n", self.description("2026-03-01"))
        self.assertIn("Previous: assets/2026-01-05/\n", self.description("2026-03-01"))
        self.add(day="2026-02-01")
        self.assertIn("Previous: assets/2026-01-05/\n", self.description("2026-02-01"))
        self.assertEqual(["description.md"], sorted(p.name for p in (self.root / "docs/specs/orders/assets/2026-02-01").iterdir()))

    def test_adding_to_an_unconfirmed_folder_keeps_its_description(self):
        self.add(self.outside / "a.png")
        path = self.root / FOLDER / "description.md"
        path.write_text(self.description().replace("Source:\n", "Source: workshop\n"), encoding="utf-8")
        result = self.add(self.outside / "brief.pdf")
        self.assertIn("Source: workshop\n", self.description())
        self.assertEqual({"folder": FOLDER, "description": f"{FOLDER}/description.md", "created": False,
                          "files": [f"{FOLDER}/brief.pdf"]}, result)

    def test_new_capability_needs_the_flag(self):
        self.add(cap="invoices", new_capability=True)
        self.assertIn("Kind: new\n", self.description(cap="invoices"))

    def assertRefused(self, pattern: str, *files: Path, **options) -> None:
        with self.assertRaisesRegex(SpecsError, pattern):
            self.add(*files, **options)
        self.assertFalse((self.root / FOLDER).exists())

    def test_refusals_write_nothing(self):
        other = self.outside / "other"
        other.mkdir()
        (other / "a.png").write_bytes(b"other")
        self.assertRefused(r"--legacy takes only \.png", self.outside / "brief.pdf", legacy=True)
        self.assertRefused("two files named a.png", self.outside / "a.png", other / "a.png")
        self.assertRefused("not a file", self.outside / "a.png", self.outside / "nope.png")
        self.assertRefused("did you mean orders", cap="order")
        self.assertRefused("no capability has a close name", cap="zzz")
        self.assertRefused(r"must match \[a-z\]\[a-z0-9-\]\*", cap="Order")
        self.assertRefused("must be YYYY-MM-DD", day="20261107")
        self.assertRefused("not a calendar date", day="2026-13-01")

    def test_existing_name_and_confirmed_folder_are_refused(self):
        self.add(self.outside / "a.png")
        with self.assertRaisesRegex(SpecsError, f"{FOLDER}/a.png already exists"):
            self.add(self.outside / "a.png")
        path = self.root / FOLDER / "description.md"
        path.write_text(self.description().replace("Confirmed: no", "Confirmed: 2026-11-08"), encoding="utf-8")
        with self.assertRaisesRegex(SpecsError, "was confirmed on 2026-11-08"):
            self.add(self.outside / "brief.pdf")
        self.assertFalse((self.root / FOLDER / "brief.pdf").exists())

    def test_cli_add_prints_folder_and_files(self):
        result = run_specs(self.root, "assets", "add", "orders", str(self.outside / "a.png"), "--legacy",
                           "--date", "2026-11-07")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([FOLDER, f"{FOLDER}/legacy/a.png"], result.stdout.splitlines())
        result = run_specs(self.root, "assets", "add", "orders", "brief.pdf", "--date", "2026-11-08",
                           "--format", "json", cwd=self.outside)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["docs/specs/orders/assets/2026-11-08/brief.pdf"], json.loads(result.stdout)["files"])

    def test_cli_refusals_exit_2(self):
        result = run_specs(self.root, "assets", "add", "order", str(self.outside / "a.png"))
        self.assertEqual(2, result.returncode)
        self.assertIn("specs error:", result.stderr)
        self.assertIn("did you mean orders", result.stderr)
        legacy = make_repo(Path(self._tmp.name) / "legacy", layout="legacy")
        result = run_specs(legacy, "assets", "add", "orders")
        self.assertEqual(2, result.returncode)
        self.assertIn("this command needs 'sdd'", result.stderr)


class TestAssetsConfirm(AssetsCase):
    def confirm(self, day: str = "2026-11-07"):
        return specs_assets.confirm(self.root, self.cfg, "orders", day, today=date(2026, 11, 9))

    def test_confirm_sets_today(self):
        self.add()
        self.assertEqual({"description": f"{FOLDER}/description.md", "confirmed": "2026-11-09"}, self.confirm())
        self.assertIn("Confirmed: 2026-11-09\n", self.description())
        self.assertNotIn("\nConfirmed: no\n", self.description())
        with self.assertRaisesRegex(SpecsError, "already confirmed on 2026-11-09"):
            self.confirm()

    def test_confirm_inserts_a_missing_line(self):
        write(self.root, f"{FOLDER}/description.md", "# orders: 2026-11-07\n\nKind: change\nPrevious: none\n\n## Summary\n")
        self.confirm()
        self.assertIn("Previous: none\nConfirmed: 2026-11-09\n", self.description())
        write(self.root, "docs/specs/orders/assets/2026-11-08/description.md", "# orders: 2026-11-08\n\n## Summary\n")
        self.confirm("2026-11-08")
        self.assertTrue(self.description("2026-11-08").startswith("# orders: 2026-11-08\nConfirmed: 2026-11-09\n"))

    def test_confirm_needs_the_folder(self):
        with self.assertRaisesRegex(SpecsError, "run gin specs assets add first"):
            self.confirm()

    def test_cli_confirm(self):
        self.add()
        result = run_specs(self.root, "assets", "confirm", "orders", "--date", "2026-11-07")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(f"{FOLDER}/description.md: Confirmed: {date.today().isoformat()}\n", result.stdout)
        self.assertEqual(2, run_specs(self.root, "assets", "confirm", "orders").returncode)

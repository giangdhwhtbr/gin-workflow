"""`gin specs assets add|confirm` and the asset lint (Confirmed: values, folders frozen on the base)."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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

    def test_source_named_description_is_reserved(self):
        (self.outside / "description.md").write_text("mine", encoding="utf-8")
        self.assertRefused("description.md is reserved", self.outside / "description.md")

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
        self.assertEqual({"description": f"{FOLDER}/description.md", "confirmed": "2026-11-09",
                          "confirmed_by": "t@example.com", "agreed_with": None}, self.confirm())
        self.assertIn("Confirmed: 2026-11-09\nConfirmed by: t@example.com\n", self.description())
        self.assertNotIn("\nConfirmed: no\n", self.description())
        with self.assertRaisesRegex(SpecsError, "already confirmed on 2026-11-09"):
            self.confirm()

    def test_confirm_records_who_agreed(self):
        self.add()
        result = specs_assets.confirm(self.root, self.cfg, "orders", "2026-11-07",
                                      agreed_with="fe_lead Binh", today=date(2026, 11, 9))
        self.assertIn("Confirmed by: t@example.com\nAgreed with: fe_lead Binh\n", self.description())
        self.assertEqual("fe_lead Binh", result["agreed_with"])

    def test_confirm_whitespace_only_agreed_with_omits_line_and_returns_none(self):
        self.add()
        result = specs_assets.confirm(self.root, self.cfg, "orders", "2026-11-07",
                                      agreed_with="   ", today=date(2026, 11, 9))
        self.assertNotIn("Agreed with:", self.description())
        self.assertIsNone(result["agreed_with"])

    def test_confirm_multiline_agreed_with_collapses_to_single_line(self):
        self.add()
        result = specs_assets.confirm(self.root, self.cfg, "orders", "2026-11-07",
                                      agreed_with="pm An\nfe_lead Binh", today=date(2026, 11, 9))
        self.assertIn("Confirmed by: t@example.com\nAgreed with: pm An fe_lead Binh\n", self.description())
        self.assertEqual("pm An fe_lead Binh", result["agreed_with"])

    def test_confirm_needs_a_git_email(self):
        self.add()
        before = self.description()
        with unittest.mock.patch("workflow_core.specs_assets.git_email", return_value=""):
            with self.assertRaisesRegex(SpecsError, "set git user.email before confirming"):
                self.confirm()
        self.assertEqual(before, self.description())

    def test_confirm_inserts_a_missing_line(self):
        write(self.root, f"{FOLDER}/description.md", "# orders: 2026-11-07\n\nKind: change\nPrevious: none\n\n## Summary\n")
        self.confirm()
        self.assertIn("Previous: none\nConfirmed: 2026-11-09\nConfirmed by: t@example.com\n", self.description())
        write(self.root, "docs/specs/orders/assets/2026-11-08/description.md", "# orders: 2026-11-08\n\n## Summary\n")
        self.confirm("2026-11-08")
        self.assertTrue(self.description("2026-11-08").startswith(
            "# orders: 2026-11-08\nConfirmed: 2026-11-09\nConfirmed by: t@example.com\n"))

    def test_confirm_needs_the_folder(self):
        with self.assertRaisesRegex(SpecsError, "run gin specs assets add first"):
            self.confirm()

    def test_cli_confirm(self):
        self.add()
        result = run_specs(self.root, "assets", "confirm", "orders", "--date", "2026-11-07")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(f"{FOLDER}/description.md: Confirmed: {date.today().isoformat()}\n", result.stdout)
        self.assertEqual(2, run_specs(self.root, "assets", "confirm", "orders").returncode)
        self.add(day="2026-11-08")
        result = run_specs(self.root, "assets", "confirm", "orders", "--date", "2026-11-08",
                           "--agreed-with", "pm An", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("t@example.com", payload["confirmed_by"])
        self.assertEqual("pm An", payload["agreed_with"])


class TestAssetsList(AssetsCase):
    FIRST = "docs/specs/orders/assets/2026-05-11"
    SECOND = "docs/specs/orders/assets/2026-06-01"

    def make_folders(self):
        write(self.root, f"{self.FIRST}/description.md",
              "# orders: 2026-05-11\n\nKind: legacy\nPrevious: none\nConfirmed: no\n\n"
              "## As-is behaviour\n\n### Order list\ntext\n### Order form\ntext\n\n"
              "## Rules\n\n### Not a screen\n")
        specs_assets.confirm(self.root, self.cfg, "orders", "2026-05-11", today=date(2026, 5, 12))
        write(self.root, f"{self.SECOND}/description.md",
              "# orders: 2026-06-01\n\nKind: change\nPrevious: assets/2026-05-11/\nConfirmed: no\n")

    def test_lists_dated_folders_oldest_first_with_kind_confirmed_and_screens(self):
        self.make_folders()
        self.assertEqual([
            {"date": "2026-05-11", "kind": "legacy", "confirmed": "2026-05-12",
             "path": f"{self.FIRST}/description.md", "screens": ["Order list", "Order form"]},
            {"date": "2026-06-01", "kind": "change", "confirmed": None,
             "path": f"{self.SECOND}/description.md", "screens": []},
        ], specs_assets.listing(self.root, self.cfg, "orders"))

    def test_a_folder_without_description_has_empty_values(self):
        (self.root / self.FIRST).mkdir(parents=True)
        self.assertEqual([{"date": "2026-05-11", "kind": None, "confirmed": None,
                           "path": f"{self.FIRST}/description.md", "screens": []}],
                         specs_assets.listing(self.root, self.cfg, "orders"))

    def test_a_capability_without_assets_is_an_empty_list(self):
        result = run_specs(self.root, "assets", "list", "orders", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], json.loads(result.stdout))

    def test_unknown_capability_exits_2(self):
        result = run_specs(self.root, "assets", "list", "order")
        self.assertEqual(2, result.returncode)
        self.assertIn("did you mean orders", result.stderr)

    def test_text_output_one_line_per_folder(self):
        self.make_folders()
        result = run_specs(self.root, "assets", "list", "orders")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([f"2026-05-11 legacy 2026-05-12 {self.FIRST}/description.md",
                          f"2026-06-01 change not confirmed {self.SECOND}/description.md"],
                         result.stdout.splitlines())

    def test_legacy_layout_lists_nothing(self):
        legacy = make_repo(Path(self._tmp.name) / "legacy", layout="legacy")
        result = run_specs(legacy, "assets", "list", "orders", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], json.loads(result.stdout))
        self.assertEqual("", run_specs(legacy, "assets", "list", "orders").stdout)


CONFIRMED = "docs/specs/orders/assets/2026-11-01"


class TestAssetLint(AssetsCase):
    def confirm_on_main(self, confirmed: str = "2026-11-02") -> str:
        write(self.root, f"{CONFIRMED}/description.md",
              f"# orders: 2026-11-01\n\nKind: new\nPrevious: none\nConfirmed: {confirmed}\n")
        write(self.root, f"{CONFIRMED}/brief.md", "v1\n")
        commit_all(self.root, "main")
        git(self.root, "switch", "-q", "-c", "feat/x")
        return git(self.root, "rev-parse", "HEAD").strip()[:12]

    def lint(self, against: str | None = None):
        return specs_assets.lint(self.root, self.cfg, against)

    def test_changes_to_a_folder_confirmed_on_the_base_are_reported(self):
        sha = self.confirm_on_main()
        self.assertEqual(([], []), self.lint())
        write(self.root, f"{CONFIRMED}/brief.md", "v2\n")
        write(self.root, f"{CONFIRMED}/new.png", "png")
        suffix = f"assets/2026-11-01/ was confirmed on 2026-11-02 at merge-base {sha}; add a new dated folder"
        self.assertEqual(([f"{CONFIRMED}/brief.md: {suffix}", f"{CONFIRMED}/new.png: {suffix}"], []), self.lint())
        (self.root / CONFIRMED / "new.png").unlink()
        (self.root / CONFIRMED / "brief.md").unlink()
        self.assertEqual(([f"{CONFIRMED}/brief.md: {suffix}"], []), self.lint())

    def test_non_ascii_paths_are_reported_plainly(self):
        self.confirm_on_main()
        write(self.root, f"{CONFIRMED}/\u00e9.png", "png")
        result = run_specs(self.root, "lint")
        self.assertEqual(1, result.returncode)
        self.assertIn(f"{CONFIRMED}/\u00e9.png: ", result.stdout)
        self.assertNotIn("\\", result.stdout)

    def test_against_names_the_base(self):
        self.confirm_on_main()
        write(self.root, f"{CONFIRMED}/brief.md", "v2\n")
        commit_all(self.root, "edit")
        findings, _ = self.lint("main")
        self.assertEqual([f"{CONFIRMED}/brief.md: assets/2026-11-01/ was confirmed on 2026-11-02 at main; "
                          "add a new dated folder"], findings)
        result = run_specs(self.root, "lint", "--against", "main")
        self.assertEqual(1, result.returncode)
        self.assertIn(findings[0], result.stdout)

    def test_unconfirmed_or_branch_only_confirmed_folders_pass(self):
        self.confirm_on_main(confirmed="no")
        write(self.root, f"{CONFIRMED}/brief.md", "v2\n")
        write(self.root, "docs/specs/orders/assets/2026-11-05/description.md", "# orders: 2026-11-05\n\nConfirmed: 2026-11-05\n")
        commit_all(self.root, "branch")
        write(self.root, "docs/specs/orders/assets/2026-11-05/x.md", "edit\n")
        self.assertEqual(([], []), self.lint())

    def test_without_a_base_the_check_is_skipped_with_a_warning(self):
        self.assertEqual(([], ["frozen asset check skipped: cannot find a merge-base with main or master; "
                               "pass --against"]), self.lint())
        self.assertEqual(([], ["frozen asset check skipped: cannot resolve nope"]), self.lint("nope"))
        result = run_specs(self.root, "lint")
        self.assertEqual(1 if specs.lint_living(self.root, self.cfg) else 0, result.returncode, result.stdout)
        self.assertIn("warning: frozen asset check skipped", result.stderr)

    def test_confirmed_value_must_be_no_or_a_date(self):
        write(self.root, "docs/specs/orders/assets/2026-11-03/description.md",
              "# orders: 2026-11-03\n\nKind: new\nPrevious: none\nConfirmed: yes\n")
        write(self.root, "docs/specs/orders/assets/2026-11-04/description.md", "# orders\n\nConfirmed: 2026-02-30\n")
        write(self.root, "docs/specs/orders/assets/2026-11-05/description.md", "# orders\n\nConfirmed: no\n")
        write(self.root, "docs/specs/orders/assets/2026-11-06/description.md", "# orders\n")
        message = "Confirmed: must be 'no' or a YYYY-MM-DD date"
        findings, _ = self.lint()
        self.assertEqual([f"docs/specs/orders/assets/2026-11-03/description.md:5: {message}",
                          f"docs/specs/orders/assets/2026-11-04/description.md:3: {message}"], findings)
        result = run_specs(self.root, "lint")
        self.assertEqual(1, result.returncode)
        self.assertIn(findings[0], result.stdout)

    def test_lint_accepts_folders_without_sign_off_lines(self):
        self.confirm_on_main()
        findings, _ = self.lint()
        self.assertEqual([], [f for f in findings if "Confirmed:" in f])
        write(self.root, "docs/specs/orders/assets/2026-11-02/description.md",
              "# orders: 2026-11-02\n\nKind: new\nPrevious: none\nConfirmed: 2026-11-02\n"
              "Confirmed by: x@y\nAgreed with: z\n")
        findings, _ = self.lint()
        self.assertEqual([], [f for f in findings if "Confirmed:" in f])

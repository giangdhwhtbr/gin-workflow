# Plan: BA asset intake: CLI commands for dated spec asset folders and a lint-enforced freeze

Epic: gin-workflow-tp83
Spec: .planning/specs/2026-11-07-ba-asset-intake-design.md

## Objective
`gin specs assets add` builds a capability's dated asset folder (validated capability, copied files, generated `description.md`), `gin specs assets confirm` marks it confirmed, `gin specs lint` reports a malformed `Confirmed:` value and any change to a folder confirmed on the base branch, and the capture, mockup, and sdd skills and the BA and SDD guides use the commands instead of building folders by hand.

Architecture: a new module `plugins/gin-workflow/src/scripts/workflow_core/specs_assets.py` holds `add`, `confirm`, `confirmed_date`, and `lint`. `specs_cli.py` gains the nested subcommand `assets add|confirm` (after `require_layout(cfg, "sdd")`) and calls `specs_assets.lint` from the `lint` command in both modes, printing its warnings to stderr. `specs.py` is not changed: the module reuses `_CAP`, `_ISO_DATE`, `specs_dir`, `template_text`, `render`, `shown`, `default_base`, `_git`, and `atomic_write_many`. Skills and docs follow.

Tech stack: Python 3 standard library (`argparse`, `difflib`, `datetime`, `re`, `subprocess` via `specs._git`), Markdown skills and docs, Python `unittest` tests run by `python3 -m pytest -n auto`.

Global Constraints (from the spec):
- One module `scripts/workflow_core/specs_assets.py` and a nested subcommand `gin specs assets add|confirm`, not flat commands and not skill text only.
- The freeze is enforced by the CLI and by lint against a base ref, not by the CLI alone.
- Files are copied, including from outside the repository; originals stay where they are.
- Out of scope: a command that commits BA or tester output (epic `gin-workflow-yasu`); deleting or moving the original files after a copy; the legacy layout (both commands need `artifacts.layout: sdd`); gin-console.
- Usage and validation errors raise `SpecsError` and exit 2 with `specs error: <message>`; lint findings exit 1.
- A missing `Confirmed:` line reads as `no`; existing dated folders stay valid.
- When no base can be found, lint warns on stderr and skips the frozen check; the exit code is unchanged.
- The command output never names a plugin other than gin-workflow (`tests/gin_ba/test_ba_packaging.py`: the core never names gin-ba).
- Budgets: every skill under `plugins/gin-ba/src/skills/` at most 6,000 characters (`tests/gin_ba/test_ba_packaging.py:46`); `plugins/gin-workflow/src/skills/sdd/SKILL.md` at most 6,000 (`tests/workflow_core/test_token_budget.py:163`, 5,818 today).
- Every docs page follows `plugins/gin-workflow/src/references/docs-style.md` (no em or en dashes).

## Route Rubric
- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis
- Problem statement: BAs and agents build dated asset folders by hand; nothing validates the capability name, `Kind:`, or `Previous:`, files outside the repository cannot be added, and a confirmed folder is frozen only in skill text.
- Success criteria: US-1 to US-4 of the spec; the full suite passes.
- Constraints: see Global Constraints.
- Non-goals: the spec's "Out of scope".

## Approach Options
### Option 1: one module, nested `assets add|confirm`, lint in the CLI (chosen in discuss)
- Summary: `specs_assets.py` holds the commands and the asset lint; `specs_cli.py` wires `assets add|confirm` and runs the asset lint in `specs lint`.
- Pros: one tested home for folder rules; `specs.py` stays as is; matches the `new_change` pattern.
- Cons: the first nested subparser in `specs_cli.py`.

### Option 2: flat `specs asset-add` and `specs asset-confirm`
- Summary: the same logic behind two flat subcommands.
- Pros: no nested parser.
- Cons: names diverge from the "assets" group the docs and skills describe.

### Recommended Approach
- Selected option: Option 1.
- Rationale: chosen by the user in discuss on 2026-11-07 (spec "Decisions confirmed with the user").

## Scope
- In scope: R1 to R6 of the spec.
- Out of scope: everything under the spec's "Out of scope".

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 extends the module Track 1 creates (it reuses confirmed_date and the test file), and Track 3 documents the commands and lint of both, so one track at a time avoids conflicts in the same files.
```

## Tasks

### Track 1: `gin specs assets add` and `gin specs assets confirm`
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/specs_assets.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py:14-50` (parser: nested `assets add|confirm`) and `:95-100` (`_run`: dispatch `assets` after `require_layout(cfg, "sdd")`)
  - Test `tests/workflow_core/test_specs_assets.py`
- **Interfaces**:
  - Consumes: `specs._CAP`, `specs._ISO_DATE`, `specs.specs_dir`, `specs.template_text`, `specs.render`, `specs.shown`, `specs.SpecsError`, `atomic.atomic_write_many`.
  - Produces:
    - `IMAGE_SUFFIXES: tuple[str, ...]`
    - `confirmed_date(text: str) -> str | None`
    - `add(root: Path, cfg: Mapping[str, Any], cap: str, files: Sequence[Path], *, day: str | None = None, legacy: bool = False, new_capability: bool = False, today: date | None = None) -> dict[str, Any]` returning `{"folder": str, "description": str, "created": bool, "files": list[str]}` (repository-relative POSIX paths)
    - `confirm(root: Path, cfg: Mapping[str, Any], cap: str, day: str, *, today: date | None = None) -> dict[str, str]` returning `{"description": str, "confirmed": str}`
    - CLI: `gin specs assets add <cap> [files...] [--date D] [--legacy] [--new-capability]`, `gin specs assets confirm <cap> --date D`, both with `--repository` and `--format`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one new module and a small CLI wiring with a clear spec, but many refusal cases and an all-or-nothing write to get right.
- **Acceptance criteria**:
  - Every test in `TestAssetsAdd` and `TestAssetsConfirm` of `tests/workflow_core/test_specs_assets.py` passes.
  - The full suite passes.
- **Estimated complexity**: medium

#### Steps

1. Create `tests/workflow_core/test_specs_assets.py`:

```python
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
        self.assertNotIn("Confirmed: no", self.description())
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
```

2. Run `python3 -m pytest tests/workflow_core/test_specs_assets.py -q`. Expected: collection fails with `ImportError: cannot import name 'specs_assets'`.

3. Create `plugins/gin-workflow/src/scripts/workflow_core/specs_assets.py`:

```python
"""Dated asset folders `<specs>/<cap>/assets/<YYYY-MM-DD>/`: `gin specs assets add|confirm` and their lint."""

from __future__ import annotations

from datetime import date
import difflib
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from . import specs
from .atomic import atomic_write_many

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif")
_CONFIRMED = re.compile(r"^Confirmed:[ \t]*(.*?)[ \t]*$", re.MULTILINE)


def _is_day(value: str) -> bool:
    if not specs._ISO_DATE.match(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def confirmed_date(text: str) -> str | None:
    """The ISO date on the first `Confirmed:` line, or None when the folder is not confirmed."""
    found = _CONFIRMED.search(text)
    return found.group(1) if found and _is_day(found.group(1)) else None


def _day(value: str | None, today: date | None) -> str:
    if value is None:
        return (today or date.today()).isoformat()
    if not specs._ISO_DATE.match(value):
        raise specs.SpecsError(f"date {value!r} must be YYYY-MM-DD")
    if not _is_day(value):
        raise specs.SpecsError(f"date {value!r} is not a calendar date")
    return value


def _capability(root: Path, cfg: Mapping[str, Any], cap: str, new_capability: bool) -> Path:
    if not specs._CAP.match(cap):
        raise specs.SpecsError(f"capability {cap!r} must match [a-z][a-z0-9-]*")
    base = specs.specs_dir(root, cfg)
    if (base / cap).is_dir() or new_capability:
        return base / cap
    existing = sorted(p.name for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
    close = difflib.get_close_matches(cap, existing, n=3)
    hint = f"did you mean {', '.join(close)}?" if close else "no capability has a close name"
    raise specs.SpecsError(f"no capability {cap!r} under {specs.shown(root, base)}: {hint} "
                           "Pass --new-capability to create it.")


def _dated(assets: Path) -> list[str]:
    return sorted(p.name for p in assets.iterdir() if p.is_dir() and specs._ISO_DATE.match(p.name)) \
        if assets.is_dir() else []


def _set_field(text: str, key: str, value: str, after: str) -> str:
    """Replace the first `<key>:` line, or insert it after the `<after>:` line, else after the first line."""
    line = f"{key}: {value}"
    current = re.compile(rf"^{key}:.*$", re.MULTILINE)
    if current.search(text):
        return current.sub(line, text, count=1)
    anchor = re.compile(rf"^{after}:.*$", re.MULTILINE).search(text)
    end = anchor.end() if anchor else text.find("\n") if "\n" in text else len(text)
    return f"{text[:end]}\n{line}{text[end:]}"


def add(root: Path, cfg: Mapping[str, Any], cap: str, files: Sequence[Path], *, day: str | None = None,
        legacy: bool = False, new_capability: bool = False, today: date | None = None) -> dict[str, Any]:
    folder = _capability(root, cfg, cap, new_capability) / "assets" / _day(day, today)
    description = folder / "description.md"
    if description.is_file() and (when := confirmed_date(description.read_text(encoding="utf-8"))):
        raise specs.SpecsError(f"{specs.shown(root, folder)} was confirmed on {when} and is frozen; "
                               "use a new --date")
    target = folder / "legacy" if legacy else folder
    writes: dict[Path, bytes] = {}
    for source in (Path(item).expanduser() for item in files):
        if not source.is_file():
            raise specs.SpecsError(f"not a file: {source}")
        if legacy and source.suffix.lower() not in IMAGE_SUFFIXES:
            raise specs.SpecsError(f"{source.name}: --legacy takes only {', '.join(IMAGE_SUFFIXES)}")
        destination = target / source.name
        if destination in writes:
            raise specs.SpecsError(f"two files named {source.name}")
        if destination.exists():
            raise specs.SpecsError(f"{specs.shown(root, destination)} already exists")
        writes[destination] = source.read_bytes()
    copied = [specs.shown(root, path) for path in writes]
    created = not description.is_file()
    if created:
        earlier = [name for name in _dated(folder.parent) if name < folder.name]
        text = specs.render(specs.template_text(root, "iteration.md"), {"capability": cap, "date": folder.name})
        text = _set_field(text, "Kind", "legacy" if legacy else "change" if earlier else "new", after="Kind")
        text = _set_field(text, "Previous", f"assets/{earlier[-1]}/" if earlier else "none", after="Kind")
        writes[description] = _set_field(text, "Confirmed", "no", after="Previous").encode("utf-8")
    if writes:
        atomic_write_many(writes, mode=0o644)
    return {"folder": specs.shown(root, folder), "description": specs.shown(root, description),
            "created": created, "files": copied}


def confirm(root: Path, cfg: Mapping[str, Any], cap: str, day: str, *, today: date | None = None) -> dict[str, str]:
    if not specs._CAP.match(cap):
        raise specs.SpecsError(f"capability {cap!r} must match [a-z][a-z0-9-]*")
    description = specs.specs_dir(root, cfg) / cap / "assets" / _day(day, None) / "description.md"
    shown = specs.shown(root, description)
    if not description.is_file():
        raise specs.SpecsError(f"no {shown}: run gin specs assets add first")
    text = description.read_text(encoding="utf-8")
    if when := confirmed_date(text):
        raise specs.SpecsError(f"{shown} is already confirmed on {when}")
    stamp = (today or date.today()).isoformat()
    atomic_write_many({description: _set_field(text, "Confirmed", stamp, after="Previous").encode("utf-8")},
                      mode=0o644)
    return {"description": shown, "confirmed": stamp}
```

4. In `specs_cli.py` `_parser`, after the `migrate` parser (line 50), add:

```python
    assets = sub.add_parser("assets").add_subparsers(dest="assets_command", required=True)
    item = assets.add_parser("add", parents=[common])
    item.add_argument("cap")
    item.add_argument("files", nargs="*", type=Path)
    item.add_argument("--date")
    item.add_argument("--legacy", action="store_true")
    item.add_argument("--new-capability", action="store_true")
    item = assets.add_parser("confirm", parents=[common])
    item.add_argument("cap")
    item.add_argument("--date", required=True)
```

   The `assets` parser takes no `common` parent, so `args.repository` and `args.format` come from `add` or `confirm`. In `_run`, right after `specs.require_layout(cfg, "sdd")` (line 95), add:

```python
    if args.command == "assets":
        from .specs_assets import add, confirm

        if args.assets_command == "add":
            result = add(root, cfg, args.cap, args.files, day=args.date, legacy=args.legacy,
                         new_capability=args.new_capability)
            _emit(result, args.format, "\n".join([result["folder"], *result["files"]]))
        else:
            result = confirm(root, cfg, args.cap, args.date)
            _emit(result, args.format, f"{result['description']}: Confirmed: {result['confirmed']}")
        return 0
```

5. Run `python3 -m pytest tests/workflow_core/test_specs_assets.py -q`. Expected: all tests pass.

6. Run `python3 -m pytest -n auto -q`. Expected: all tests pass. Commit: `feat(specs): gin specs assets add and confirm (gin-workflow-tp83)`.

### Track 2: asset lint: `Confirmed:` values and folders frozen on the base
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_assets.py` (new `confirmed_value_errors`, `frozen_findings`, `lint`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py:107-112` (`lint` runs the asset lint and prints its warnings)
  - Test `tests/workflow_core/test_specs_assets.py` (new class `TestAssetLint`)
- **Interfaces**:
  - Consumes: `confirmed_date`, `_is_day` (Track 1), `specs.default_base`, `specs._git`, `specs.specs_dir`, `specs.shown`.
  - Produces:
    - `confirmed_value_errors(root: Path, cfg: Mapping[str, Any]) -> list[str]`
    - `frozen_findings(root: Path, cfg: Mapping[str, Any], base: str, label: str) -> list[str]`
    - `lint(root: Path, cfg: Mapping[str, Any], against: str | None) -> tuple[list[str], list[str]]` (findings, warnings)
    - `gin specs lint [--change C] [--against REF]`: findings added to the output and exit code; each warning printed to stderr as `warning: <text>`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded addition to the Track 1 module, but git edge cases (deleted, untracked, no base, unknown ref) need care.
- **Acceptance criteria**:
  - Every test in `TestAssetLint` passes, and `tests/workflow_core/test_specs.py` still passes unchanged.
  - The full suite passes.
- **Estimated complexity**: medium

#### Steps

1. Add to `tests/workflow_core/test_specs_assets.py`:

```python
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
```

2. Run `python3 -m pytest tests/workflow_core/test_specs_assets.py -q -k TestAssetLint`. Expected: fails with `AttributeError: module 'workflow_core.specs_assets' has no attribute 'lint'`.

3. Add to `specs_assets.py` (needs `PurePosixPath` from `pathlib`):

```python
def confirmed_value_errors(root: Path, cfg: Mapping[str, Any]) -> list[str]:
    """A `Confirmed:` line of a dated folder's description.md that is neither `no` nor an ISO date."""
    errors = []
    for description in sorted(specs.specs_dir(root, cfg).glob("*/assets/*/description.md")):
        if not specs._ISO_DATE.match(description.parent.name):
            continue
        for number, line in enumerate(description.read_text(encoding="utf-8").splitlines(), 1):
            found = _CONFIRMED.match(line)
            if found:
                if found.group(1) != "no" and not _is_day(found.group(1)):
                    errors.append(f"{specs.shown(root, description)}:{number}: "
                                  "Confirmed: must be 'no' or a YYYY-MM-DD date")
                break
    return errors


def frozen_findings(root: Path, cfg: Mapping[str, Any], base: str, label: str) -> list[str]:
    """Every path that differs from `base` under a dated folder confirmed on `base`, untracked files included."""
    prefix = PurePosixPath(cfg["specs"]).as_posix()
    listed = specs._git(root, "ls-tree", "-r", "--name-only", base, "--", prefix)
    if listed.returncode != 0:
        raise specs.SpecsError(f"cannot list {prefix} at {label}: {listed.stderr.strip()}")
    pattern = re.compile(rf"^{re.escape(prefix)}/[^/]+/assets/(\d{{4}}-\d{{2}}-\d{{2}})/description\.md$")
    findings = []
    for path in listed.stdout.splitlines():
        match = pattern.match(path)
        when = confirmed_date(specs._git(root, "show", f"{base}:{path}").stdout) if match else None
        if not when:
            continue
        folder = path.rsplit("/", 1)[0]
        changed = specs._git(root, "diff", "--name-only", base, "--", folder).stdout.splitlines()
        untracked = specs._git(root, "ls-files", "--others", "--exclude-standard", "--", folder).stdout.splitlines()
        findings += [f"{item}: assets/{match.group(1)}/ was confirmed on {when} at {label}; add a new dated folder"
                     for item in sorted(set(changed + untracked))]
    return findings


def lint(root: Path, cfg: Mapping[str, Any], against: str | None) -> tuple[list[str], list[str]]:
    """Asset findings for `gin specs lint`, and warnings for stderr."""
    errors = confirmed_value_errors(root, cfg)
    try:
        base = against or specs.default_base(root)
        resolved = specs._git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
        if resolved.returncode != 0:
            raise specs.SpecsError(f"cannot resolve {base}")
        commit = resolved.stdout.strip()
        return errors + frozen_findings(root, cfg, commit, against or f"merge-base {commit[:12]}"), []
    except specs.SpecsError as error:
        return errors, [f"frozen asset check skipped: {error}"]
```

4. In `specs_cli.py`, replace the `lint` block (lines 107-112) with:

```python
    if args.command == "lint":
        from .specs_assets import lint as lint_assets

        if args.change:
            errors = specs.lint_change(root, cfg, specs.find_change(root, cfg, args.change), against=args.against)
        else:
            errors = specs.lint_living(root, cfg)
        found, warnings = lint_assets(root, cfg, args.against)
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        return _findings(errors + found, args.format, "ok")
```

5. Run `python3 -m pytest tests/workflow_core/test_specs_assets.py tests/workflow_core/test_specs.py -q`. Expected: all tests pass.

6. Run `python3 -m pytest -n auto -q`. Expected: all tests pass. Commit: `feat(specs): lint confirmed asset values and folders frozen on the base (gin-workflow-tp83)`.

### Track 3: skills, template, and docs use the commands
- **Dependencies**: Track 1, Track 2
- **Files**:
  - Modify `plugins/gin-ba/src/skills/capture/SKILL.md:13-17,29-30` (steps 1, 2, 6)
  - Modify `plugins/gin-ba/src/skills/mockup/SKILL.md:13-17,28-33` (steps 1, 2, 7)
  - Modify `plugins/gin-workflow/src/skills/sdd/SKILL.md:13` (discuss step 3, asset sentences)
  - Modify `plugins/gin-workflow/src/templates/iteration.md:3-7` (comment)
  - Modify `docs/guides/ba.md`, `docs/guides/ba.vi.md` (legacy, mockup, and confirm steps)
  - Modify `docs/guides/sdd.md:52-74`, `docs/guides/sdd.vi.md` (section "Images and mockups")
  - Modify `docs/reference/cli.md` (`specs` commands)
  - Modify `docs/reference/skills.md:80`, `docs/reference/skills.vi.md` (capture row, only if its wording says the BA places files)
  - Test `tests/gin_ba/test_ba_packaging.py:57-68` (needles)
- **Interfaces**:
  - Consumes: the commands and lint behaviour of Tracks 1 and 2, exactly as their `Interfaces` state.
  - Produces: skill and docs text only.
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** text edits with the exact content below; budgets and needle tests catch mistakes, so no design judgement is left.
- **Acceptance criteria**:
  - `tests/gin_ba/test_ba_packaging.py`, `tests/workflow_core/test_token_budget.py`, and the docs tests pass.
  - The full suite passes.
- **Estimated complexity**: low

#### Steps

1. In `tests/gin_ba/test_ba_packaging.py`, the shared needle tuple (line 57) replaces `"gin specs template iteration.md"` with `"gin specs assets add"` and `"Confirmed: <today>"` with `"gin specs assets confirm"`; the capture needles (line 66) replace `"never copy from outside the repository"` with `"--legacy"`. Run `python3 -m pytest tests/gin_ba/test_ba_packaging.py -q`. Expected: fails on the new needles.

2. Edit `plugins/gin-ba/src/skills/capture/SKILL.md`:
   - Step 1, last bullet: keep the normalization and the near-match rule; a new name the user confirms is created with `--new-capability`.
   - Step 2 becomes:
     ```
     2. The folder is `<specs>/<cap>/assets/<date>/`, with `<date>` from `--date` or today.
        - Add the screenshots the BA names, from inside or outside the repository: `gin specs assets add <cap> <files...> --legacy --date <date>`. It copies them under `<date>/legacy/`, accepts only `.png`, `.jpg`, `.jpeg`, `.webp`, or `.gif`, and writes `description.md` with `Kind: legacy`, `Previous:`, and `Confirmed: no` when it is missing. On exit 2, report its message and stop; a folder whose `description.md` reads `Confirmed: <YYYY-MM-DD>` is frozen: ask for a new date and never edit it.
        - With no files named and none under `<date>/legacy/`, ask the BA for the screenshot paths.
        - Ask once who gave the screenshots for `Source:`.
     ```
   - Step 6: "When the BA explicitly confirms the description, run `gin specs assets confirm <cap> --date <date>`." The rest of the step stays.
   - Step 7: replace "only the BA's explicit answer sets `Confirmed:`" with "only the BA's explicit answer runs `gin specs assets confirm`". Keep "Do not commit".

3. Edit `plugins/gin-ba/src/skills/mockup/SKILL.md`:
   - Step 1, last bullet: same change as capture.
   - Step 2: the first bullet becomes "Run `gin specs assets add <cap> --date <date>`: it creates the folder and, when missing, `description.md` with `Kind:` (`new` or `change`), `Previous:`, and `Confirmed: no`. On exit 2, report its message and stop. Ask once who gave the inputs for `Source:` (for example `customer workshop`)." Keep the frozen bullet (`Confirmed: <YYYY-MM-DD>`, "frozen", "never edit it"). The last bullet keeps "continue in it and read the mockup already there" and drops the `Confirmed: no` insertion.
   - Step 7: the last bullet becomes "then run `gin specs assets confirm <cap> --date <date>`."
   - Step 8: same change as capture step 7.

4. Edit `plugins/gin-workflow/src/skills/sdd/SKILL.md` discuss step 3. Replace from "`git mv` an asset placed elsewhere" through "never edit an older dated folder." with:
   ```
   Each batch of inputs gets a new dated folder (the day it arrived): `specs assets add <cap> <files...> [--date <YYYY-MM-DD>]` copies the files, from inside or outside the repository, and writes `description.md` (`Kind:`, `Previous:`, `Confirmed: no`); `--legacy` puts screenshots of an existing feature under `legacy/`; delete an original only when the user asks. Never edit an older dated folder: `specs lint` reports a change to a folder confirmed on the base branch.
   ```
   Check `wc -c plugins/gin-workflow/src/skills/sdd/SKILL.md` stays at most 6,000.

5. Edit `plugins/gin-workflow/src/templates/iteration.md` comment: after "never edit an older one." insert "`gin specs assets add` creates the folder and fills Kind and Previous; `gin specs assets confirm` sets Confirmed." Keep every other line of the template.

6. Docs, per `plugins/gin-workflow/src/references/docs-style.md`:
   - `docs/guides/ba.md` and `ba.vi.md`: the legacy step that says to put screenshots under `docs/specs/<capability>/assets/<date>/legacy/` says instead that `/gin-ba:capture` adds the files you name, from anywhere on disk, with `gin specs assets add <capability> <files> --legacy`; the mockup and capture confirm steps say the skill runs `gin specs assets confirm` when you confirm. Keep "the BA reviews and commits" (the commit command is epic `gin-workflow-yasu`).
   - `docs/guides/sdd.md` and `sdd.vi.md`, "Images and mockups": replace "Start every `description.md` from `gin specs template iteration.md`." with the two commands and what each writes; replace the lint sentence with: `specs lint` reports a dated folder without `description.md`, a `Confirmed:` value that is neither `no` nor a date, and any change to a folder confirmed on the base branch (`--against <ref>`, else the merge-base with `main` or `master`; without one it warns and skips that check). Add the limit: a folder confirmed on the current branch is checked only after it reaches the base; `assets add` refuses it before that. Keep "flat files under `assets/` and folders not named by an ISO date stay valid and are not checked".
   - `docs/reference/cli.md`: under the `specs` commands, add `specs assets add <cap> [files...] [--date D] [--legacy] [--new-capability]` and `specs assets confirm <cap> --date D` with one line each on what they do and that they exit 2 on refusal; note that `specs lint` accepts `--against` without `--change` for the frozen asset check.
   - `docs/reference/skills.md:80` and `skills.vi.md`: change only if the capture row says the BA places the files.

7. Run `python3 -m pytest tests/gin_ba tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_check.py tests/workflow_core/test_docs_coverage.py -q`. Expected: all pass. Then `python3 -m pytest -n auto -q`. Expected: all pass. Commit: `docs(specs): skills and guides use gin specs assets add and confirm (gin-workflow-tp83)`.

## Integration
- **Branch**: `feat/ba-asset-intake`
- **Merge strategy**: sequential

## Validation
- [ ] All tests pass: `python3 -m pytest -n auto -q`
- [ ] `gin specs lint --spec .planning/specs/2026-11-07-ba-asset-intake-design.md` prints `ok`
- [ ] Manual: in a scratch SDD repository, `gin specs assets add <cap> ~/some.png --legacy`, then `gin specs assets confirm <cap> --date <today>`, commit on `main`, edit the folder on a branch, and `gin specs lint` exits 1 naming the file.

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog using the route rubric.
- The user may override `Model:` and `Effort:` before plan approval.
- The parent bead `gin-workflow-tp83` stays open until a human-confirmed merge; each track bead closes once its tests and review pass.

"""`gin-qa e2e`: Playwright specs for `Type: e2e` test cases, their runs, and the evidence the runs leave."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import shutil
from typing import Any

from . import cases as tc
from .reqs import Effective, QaError

HEADER = re.compile(r"^// TC: (TC-[A-Z][A-Z0-9-]*-\d{3,})@([0-9a-f]{8})$")
FIXTURE = "evidence.ts"


@dataclass
class Spec:
    path: str
    tc: str | None
    pinned: str | None


def evidence_root(eff: Effective) -> str:
    """The `evidence` folder next to the e2e folder: `qa/evidence` for `qa/e2e`."""
    return (PurePosixPath(eff.e2e_dir).parent / "evidence").as_posix()


def spec_path(eff: Effective, case: tc.Case) -> str:
    return f"{eff.e2e_dir}/{case.cap}/{case.id.lower()}.spec.ts"


def e2e_cases(root: Path, eff: Effective) -> dict[str, tc.Case]:
    cases, _ = tc.load(root, eff.cases_dir)
    return {case.id: case for case in cases if case.fields.get("Type", "").strip().lower() == "e2e"}


def load_specs(root: Path, eff: Effective) -> list[Spec]:
    base = root / eff.e2e_dir
    found: list[Spec] = []
    for path in sorted(base.glob("*/*.spec.ts")) if base.is_dir() else []:
        first = path.read_text(encoding="utf-8").split("\n", 1)[0]
        match = HEADER.match(first)
        found.append(Spec(path.relative_to(root).as_posix(), *(match.groups() if match else (None, None))))
    return found


def plan(root: Path, eff: Effective, capability: str | None) -> dict[str, list[dict[str, Any]]]:
    cases = e2e_cases(root, eff)
    specs = {spec.path: spec for spec in load_specs(root, eff)}
    missing: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    for case in cases.values():
        if capability and case.cap != capability:
            continue
        row = {"tc": case.id, "spec": spec_path(eff, case), "hash8": tc.hash8(case), "case": tc.as_dict(case)}
        spec = specs.get(row["spec"])
        if spec is None:
            missing.append(row)
        elif spec.pinned != row["hash8"]:
            stale.append({**row, "pinned": spec.pinned})
    orphan = [{"spec": spec.path, "tc": spec.tc} for spec in specs.values()
              if (not capability or spec.path.split("/")[-2] == capability)
              and spec.tc is not None and spec.tc not in cases]
    return {"missing": missing, "stale": stale, "orphan": orphan}


def check_specs(root: Path, eff: Effective) -> list[str]:
    errors: list[str] = []
    cases = e2e_cases(root, eff)
    for spec in load_specs(root, eff):
        if spec.tc is None:
            errors.append(f"{spec.path}:1: needs a first line '// TC: <TC-ID>@<hash8>'; "
                          "write it with `gin-qa e2e pin <TC-ID>`")
        elif spec.tc in cases and spec.path != spec_path(eff, cases[spec.tc]):
            errors.append(f"{spec.path}:1: {spec.tc} belongs in {spec_path(eff, cases[spec.tc])}")
    work = plan(root, eff, None)
    errors += [f"{row['case']['file']}:{row['case']['line']}: {row['tc']} has no e2e spec ({row['spec']})"
               for row in work["missing"]]
    errors += [f"{row['spec']}:1: {row['tc']} changed (pinned {row['pinned']}, now {row['hash8']}); update the spec, "
               f"then `gin-qa e2e pin {row['tc']}`" for row in work["stale"]]
    errors += [f"{row['spec']}:1: {row['tc']} is not an e2e test case any more" for row in work["orphan"]]
    return errors


def pin(root: Path, eff: Effective, ids: list[str]) -> list[str]:
    cases = e2e_cases(root, eff)
    errors: list[str] = []
    edits: dict[Path, str] = {}
    for case_id in ids:
        case = cases.get(case_id)
        path = root / spec_path(eff, case) if case else None
        if case is None:
            errors.append(f"{case_id}: no such e2e test case")
        elif not path.is_file():
            errors.append(f"{case_id}: no spec at {spec_path(eff, case)}")
        else:
            edits[path] = f"// TC: {case.id}@{tc.hash8(case)}"
    if errors:
        return errors
    for path, header in edits.items():
        lines = path.read_text(encoding="utf-8").split("\n")
        if HEADER.match(lines[0]):
            lines[0] = header
        else:
            lines.insert(0, header)
        path.write_text("\n".join(lines), encoding="utf-8")
    return []


def _template() -> Path:
    here = Path(__file__).resolve().parent
    for base in (here.parent, here.parent.parent):  # installed launcher, then plugin source
        if (base / "templates" / FIXTURE).is_file():
            return base / "templates" / FIXTURE
    raise QaError(f"the {FIXTURE} template is missing from this gin-qa install; reinstall gin-qa")


def init(root: Path, eff: Effective) -> list[str]:
    """Copies the fixture and ignores the evidence folder; never overwrites. Returns what it did."""
    done: list[str] = []
    target = root / eff.e2e_dir / FIXTURE
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_template(), target)
        done.append(f"wrote {eff.e2e_dir}/{FIXTURE}")
    ignore = root / ".gitignore"
    entry = f"/{evidence_root(eff)}/"
    lines = ignore.read_text(encoding="utf-8").splitlines() if ignore.is_file() else []
    if entry not in lines:
        ignore.write_text("\n".join([*lines, entry]) + "\n", encoding="utf-8")
        done.append(f"added {entry} to .gitignore")
    if _playwright(root) is None:
        done.append("@playwright/test is not installed here: npm install -D @playwright/test && "
                    "npx playwright install chromium")
    return done


def _playwright(root: Path) -> Path | None:
    for base in (root, *root.parents):
        if (base / "node_modules/@playwright/test/package.json").is_file():
            return base
    return None

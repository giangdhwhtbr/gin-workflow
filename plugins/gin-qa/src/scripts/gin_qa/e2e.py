"""`gin-qa e2e`: Playwright specs for `Type: e2e` test cases, their runs, and the evidence the runs leave."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
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


def _selected(root: Path, eff: Effective, targets: list[str]) -> list[str]:
    specs = load_specs(root, eff)
    if not targets:
        return [spec.path for spec in specs]
    cases = e2e_cases(root, eff)
    chosen: list[str] = []
    for target in targets:
        if tc.TC_ID.fullmatch(target):
            if target not in cases or not (root / spec_path(eff, cases[target])).is_file():
                raise QaError(f"{target}: no e2e spec; write one with /gin-qa:e2e {target}")
            chosen.append(spec_path(eff, cases[target]))
        else:
            found = [spec.path for spec in specs if spec.path.split("/")[-2] == target]
            if not found:
                raise QaError(f"{target}: no e2e specs under {eff.e2e_dir}/{target}")
            chosen += found
    return list(dict.fromkeys(chosen))


def run(root: Path, eff: Effective, targets: list[str]) -> tuple[str, int, list[str]]:
    """Runs the selected specs into a new evidence folder. Returns (folder, Playwright exit, check findings)."""
    if not (root / eff.e2e_dir / FIXTURE).is_file():
        raise QaError(f"{eff.e2e_dir}/{FIXTURE} is missing; run `gin-qa e2e init`")
    npx = shutil.which("npx")
    if npx is None:
        raise QaError("npx is not on PATH; install Node.js")
    if _playwright(root) is None:
        raise QaError("@playwright/test is not installed: npm install -D @playwright/test")
    specs = _selected(root, eff, targets)
    if not specs:
        raise QaError(f"no e2e specs under {eff.e2e_dir}; write them with /gin-qa:e2e")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    folder, suffix = f"{evidence_root(eff)}/{stamp}", 2
    (root / evidence_root(eff)).mkdir(parents=True, exist_ok=True)
    while True:
        try:
            (root / folder).mkdir()
            break
        except FileExistsError:  # another run started in the same second
            folder, suffix = f"{evidence_root(eff)}/{stamp}-{suffix}", suffix + 1
    record = {"started": datetime.now(timezone.utc).isoformat(), "specs": specs, "playwright_exit": None}
    (root / folder / "run.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    # Each run gets its own Playwright output folder: the shared default is wiped when a run starts.
    result = subprocess.run([npx, "playwright", "test", *specs, "--output", f"{folder}/playwright"],
                            cwd=root, stdout=sys.stderr,
                            env={**os.environ, "GIN_QA_RUN_DIR": str(root / folder)})
    record["playwright_exit"] = result.returncode
    (root / folder / "run.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return folder, result.returncode, check_run(root, eff, folder)


def _run_folder(root: Path, eff: Effective, folder: str) -> tuple[Path, dict[str, Any]]:
    path = (root / folder).resolve()
    base = (root / evidence_root(eff)).resolve()
    if base not in path.parents:
        raise QaError(f"{folder}: not a run folder under {evidence_root(eff)}")
    if not (path / "run.json").is_file():
        raise QaError(f"{folder}: no run.json; runs are made by `gin-qa e2e run`")
    try:
        record = json.loads((path / "run.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        record = None
    specs = record.get("specs") if isinstance(record, dict) else None
    if not specs or not isinstance(specs, list) or not all(isinstance(spec, str) for spec in specs):
        raise QaError(f"{folder}: run.json is not a gin-qa run record (needs a non-empty specs list)")
    return path, record


def _result(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, "no result.json (the spec did not run, or it does not use the evidence fixture)"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return None, f"result.json is not valid JSON: {error}"
    if not isinstance(data, dict) or data.get("status") not in ("passed", "failed") \
            or not isinstance(data.get("steps"), list):
        return None, "result.json needs a status of passed or failed and a steps list"
    return data, None


def _artifact(folder: Path, name: object) -> Path | None:
    """A non-empty evidence file named relative to its case folder and resolving inside it, else None."""
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        return None
    path = (folder / name).resolve()
    if folder.resolve() not in path.parents or not path.is_file() or path.stat().st_size == 0:
        return None
    return path


def _result_folders(case_dir: Path) -> list[Path]:
    """Where a case's results live: the case folder (unnamed Playwright project) and one subfolder per named project."""
    subfolders = sorted(sub for sub in case_dir.iterdir() if (sub / "result.json").is_file()) if case_dir.is_dir() else []
    return ([case_dir] if (case_dir / "result.json").is_file() else []) + subfolders


def check_run(root: Path, eff: Effective, folder: str) -> list[str]:
    path, record = _run_folder(root, eff, folder)
    shown = path.relative_to(root.resolve()).as_posix()
    cases = e2e_cases(root, eff)
    errors: list[str] = []
    for spec in record.get("specs", []):
        match = HEADER.match((root / spec).read_text(encoding="utf-8").split("\n", 1)[0]) \
            if (root / spec).is_file() else None
        if match is None:
            errors.append(f"{spec}: no '// TC:' header, so its evidence cannot be found")
            continue
        case_id = match.group(1)
        for result_dir in _result_folders(path / case_id.lower()) or [path / case_id.lower()]:
            errors += _check_result(result_dir, f"{shown}/{result_dir.relative_to(path).as_posix()}/result.json",
                                    case_id, cases)
    return errors


def _check_result(folder: Path, where: str, case_id: str, cases: dict[str, tc.Case]) -> list[str]:
    data, problem = _result(folder / "result.json")
    if problem:
        return [f"{where}: {problem}"]
    errors: list[str] = []
    if data.get("tc") != case_id:
        errors.append(f"{where}: tc is {data.get('tc')!r}, expected {case_id}")
    if data["status"] == "passed" and not data["steps"]:
        errors.append(f"{where}: passed without any ev.step; nothing was checked")
    for step in data["steps"]:
        step = step if isinstance(step, dict) else {"n": "?"}
        if _artifact(folder, step.get("screenshot")) is None:
            errors.append(f"{where}: step {step.get('n')} has no screenshot on disk")
        if step.get("snapshot") is not None and _artifact(folder, step["snapshot"]) is None:
            errors.append(f"{where}: step {step.get('n')} has no snapshot on disk")
    if case_id not in cases:
        errors.append(f"{where}: {case_id} is not an e2e test case any more")
    elif data.get("tc_hash8") != tc.hash8(cases[case_id]):
        errors.append(f"{where}: ran {case_id}@{data.get('tc_hash8')}, but the case is now "
                      f"@{tc.hash8(cases[case_id])}")
    return errors


def export(root: Path, eff: Effective, folder: str) -> dict[str, Any]:
    path, record = _run_folder(root, eff, folder)
    shown = path.relative_to(root.resolve()).as_posix()
    rows: list[dict[str, Any]] = []
    for case in e2e_cases(root, eff).values():
        results: list[dict[str, Any]] = []
        for result_dir in _result_folders(path / case.id.lower()):
            data, _ = _result(result_dir / "result.json")
            if data is None:
                continue
            for step in data["steps"]:
                for key in ("screenshot", "snapshot"):
                    if isinstance(step, dict) and step.get(key) is not None:
                        found = _artifact(result_dir, step[key])
                        step[key] = found.relative_to(root.resolve()).as_posix() if found else None
            results.append(data)
        spec = spec_path(eff, case)
        rows.append({**tc.as_dict(case), "spec": spec if (root / spec).is_file() else None, "results": results})
    return {"run": shown, "started": record.get("started"), "playwright_exit": record.get("playwright_exit"),
            "cases": rows}

"""`gin-qa e2e`: Playwright specs for e2e test cases, their runs, and the evidence the runs leave."""

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
from urllib.parse import urlsplit

from . import cases as tc
from .reqs import Effective, QaError

HEADER = re.compile(r"^// TC: (TC-[A-Z][A-Z0-9-]*-\d{3,})@([0-9a-f]{8})$")
FIXTURE = "evidence.ts"
CONFIG = "playwright.config.ts"
CONFIG_NAMES = tuple(f"playwright.config.{ext}" for ext in ("ts", "js", "mjs", "cjs", "mts", "cts"))
DEFAULT_BASE_URL = "http://localhost:3000"


@dataclass
class Spec:
    path: str
    tc: str | None
    pinned: str | None


def evidence_root(eff: Effective) -> str:
    """The `evidence` folder next to the e2e folder: `qa/evidence` for `qa/e2e`."""
    return (PurePosixPath(eff.e2e_dir).parent / "evidence").as_posix()


def new_run_folder(root: Path, eff: Effective, suffix: str = "") -> str:
    """Creates `<evidence root>/<UTC stamp><suffix>`, with `-2`, `-3`, ... when another run took the name."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S") + suffix
    folder, number = f"{evidence_root(eff)}/{stamp}", 2
    (root / evidence_root(eff)).mkdir(parents=True, exist_ok=True)
    while True:
        try:
            (root / folder).mkdir()
            return folder
        except FileExistsError:  # another run started in the same second
            folder, number = f"{evidence_root(eff)}/{stamp}-{number}", number + 1


def spec_path(eff: Effective, case: tc.Case) -> str:
    return f"{eff.e2e_dir}/{case.cap}/{case.id.lower()}.spec.ts"


def e2e_cases(root: Path, eff: Effective) -> dict[str, tc.Case]:
    cases, _ = tc.load(root, eff.cases_dir)
    return {case.id: case for case in cases if case.type == "e2e"}


def load_specs(root: Path, eff: Effective) -> list[Spec]:
    base = root / eff.e2e_dir
    found: list[Spec] = []
    for path in sorted(base.glob("*/*.spec.ts"), key=lambda path: path.parts) if base.is_dir() else []:
        first = path.read_text(encoding="utf-8").split("\n", 1)[0]
        match = HEADER.match(first)
        found.append(Spec(path.relative_to(root).as_posix(), *(match.groups() if match else (None, None))))
    return found


def plan(root: Path, eff: Effective, capability: str | None) -> dict[str, list[dict[str, Any]]]:
    capability = tc.capability_arg(capability)
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
        tc.write_atomic(path, "\n".join(lines))
    return []


def _template(name: str) -> Path:
    here = Path(__file__).resolve().parent
    for base in (here.parent, here.parent.parent):  # installed launcher, then plugin source
        if (base / "templates" / name).is_file():
            return base / "templates" / name
    raise QaError(f"the {name} template is missing from this gin-qa install; reinstall gin-qa")


def check_base_url(value: str) -> str:
    """The URL goes into a TypeScript string literal: only a plain http(s) URL with a host is accepted."""
    try:
        parts = urlsplit(value)
        plain = parts.scheme in ("http", "https") and bool(parts.hostname)
    except ValueError:  # e.g. an unclosed IPv6 bracket
        plain = False
    if not plain or any(char in "'\\`" or ord(char) < 32 or ord(char) == 127 for char in value):
        raise QaError(f"--base-url: expected an http(s) URL, got {value!r}")
    return value


def _has_e2e_script(root: Path) -> bool:
    try:
        scripts = json.loads((root / "package.json").read_text(encoding="utf-8")).get("scripts")
    except (OSError, ValueError, AttributeError):
        return False
    return isinstance(scripts, dict) and "e2e" in scripts


def init(root: Path, eff: Effective, base_url: str | None = None) -> list[str]:
    """Copies the fixture, ignores the evidence folder, and writes the Playwright config; never overwrites.
    Returns what it did."""
    url = check_base_url(DEFAULT_BASE_URL if base_url is None else base_url)
    done: list[str] = []
    target = root / eff.e2e_dir / FIXTURE
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_template(FIXTURE), target)
        done.append(f"wrote {eff.e2e_dir}/{FIXTURE}")
    ignore = root / ".gitignore"
    entry = f"/{evidence_root(eff)}/"
    lines = ignore.read_text(encoding="utf-8").splitlines() if ignore.is_file() else []
    if entry not in lines:
        ignore.write_text("\n".join([*lines, entry]) + "\n", encoding="utf-8")
        done.append(f"added {entry} to .gitignore")
    existing = next((name for name in CONFIG_NAMES if (root / name).exists()), None)
    if existing is None:
        text = _template(CONFIG).read_text(encoding="utf-8")
        (root / CONFIG).write_text(text.replace("__E2E_DIR__", eff.e2e_dir).replace("__BASE_URL__", url),
                                   encoding="utf-8")
        done.append(f"wrote {CONFIG} (baseURL {url})")
    elif base_url is not None:
        done.append(f"{existing} exists; --base-url not applied")
    if _playwright(root) is None:
        done.append("@playwright/test is not installed here: npm install -D @playwright/test && "
                    "npx playwright install chromium")
    if not _has_e2e_script(root):
        done.append('add "e2e": "playwright test" to the package.json scripts')
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


def _outcome(run_dir: Path, case_id: str) -> str:
    """The worst status over the case's result folders: failed, then blocked (no valid result.json), then passed."""
    statuses = [((_result(folder / "result.json")[0] or {}).get("status", "blocked")
                 if _contained(run_dir, folder) else "blocked")
                for folder in _result_folders(run_dir / case_id.lower())]
    return next((worst for worst in ("failed", "blocked") if worst in statuses), "passed" if statuses else "blocked")


def _record(root: Path, eff: Effective, folder: str, specs: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    recorded: list[dict[str, str]] = []
    errors: list[str] = []
    for spec in specs:
        match = HEADER.match((root / spec).read_text(encoding="utf-8").split("\n", 1)[0]) \
            if (root / spec).is_file() else None
        if match is None:
            continue  # check_run reports the missing header
        case_id, status = match.group(1), _outcome(root / folder, match.group(1))
        try:
            tc.record_result(root, eff.cases_dir, case_id, status, run=folder)
        except ValueError as error:
            errors.append(f"{case_id}: result not recorded: {error}")
            continue
        recorded.append({"tc": case_id, "result": status})
    return recorded, errors


def run(root: Path, eff: Effective, targets: list[str]) -> tuple[str, int, list[str], list[dict[str, str]]]:
    """Runs the selected specs into a new evidence folder.

    Returns (folder, Playwright exit, findings, recorded results).
    """
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
    folder = new_run_folder(root, eff)
    record = {"started": datetime.now(timezone.utc).isoformat(), "specs": specs, "playwright_exit": None}
    (root / folder / "run.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    # Each run gets its own Playwright output folder: the shared default is wiped when a run starts.
    result = subprocess.run([npx, "playwright", "test", *specs, "--output", f"{folder}/playwright"],
                            cwd=root, stdout=sys.stderr,
                            env={**os.environ, "GIN_QA_RUN_DIR": str(root / folder)})
    record["playwright_exit"] = result.returncode
    (root / folder / "run.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    findings = check_run(root, eff, folder)
    recorded, problems = _record(root, eff, folder, specs)
    return folder, result.returncode, findings + problems, recorded


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
    """Where a case's results live: the case folder (unnamed Playwright project) and every subfolder (one per named
    project, symlinks included so they are reported). Every one must hold a result.json: the case folder itself
    when it holds any file (evidence of an unnamed project) or nothing else, each subfolder always."""
    entries = sorted(case_dir.iterdir(), key=lambda path: path.parts) if case_dir.is_dir() else []
    subfolders = [entry for entry in entries if entry.is_symlink() or entry.is_dir()]
    own = [case_dir] if len(subfolders) < len(entries) or not subfolders else []
    return own + subfolders


def _contained(run: Path, folder: Path) -> bool:
    """A real folder under the run folder, not a symlink to somewhere else."""
    return not folder.is_symlink() and run.resolve() in folder.resolve().parents


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
        case_dir = path / case_id.lower()
        if case_dir.exists() and not _contained(path, case_dir):
            errors.append(f"{shown}/{case_id.lower()}: not a folder inside the run")
            continue
        for result_dir in _result_folders(case_dir):
            relative = result_dir.relative_to(path).as_posix()
            if not _contained(path, result_dir):
                errors.append(f"{shown}/{relative}: not a folder inside the run")
                continue
            errors += _check_result(result_dir, f"{shown}/{relative}/result.json", case_id, cases)
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
            if not _contained(path, result_dir) or not _contained(path, path / case.id.lower()):
                continue
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

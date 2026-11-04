"""`gin-qa report`: one folder holding an offline HTML report of the test cases and the e2e screenshots it shows."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import shutil
from typing import Any

from . import cases as tc
from . import e2e
from .reqs import Effective, QaError

TEMPLATE = "report.html"
PLACEHOLDER = "/*GIN_QA_DATA*/"
RESULT_KEYS = ("project", "status", "error", "started", "finished")
STEP_KEYS = ("n", "title", "status", "url", "error")

Results = dict[str, list[dict[str, Any]]]


def _run_results(root: Path, eff: Effective, run: str) -> tuple[str, Results] | None:
    """(the run folder as `e2e export` shows it, results per case ID), or None when the folder cannot be read."""
    try:
        payload = e2e.export(root, eff, run)
    except (QaError, OSError, ValueError):
        return None
    return payload["run"], {row["id"]: row["results"] for row in payload["cases"]}


def _tests_run(root: Path, run: str) -> bool:
    """A `gin-qa tests run` folder: its run.json names a test type, and it holds no e2e evidence to show."""
    try:
        return "type" in json.loads((root / run / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False


def _result(data: dict[str, Any], run: str, copies: dict[str, str]) -> dict[str, Any]:
    """One Playwright project's result; each screenshot gets its path inside the report folder, `<run name>/...`."""
    steps = []
    for step in data.get("steps", []):
        if not isinstance(step, dict):
            continue
        shot, target = step.get("screenshot"), None
        if isinstance(shot, str):  # e2e.export keeps only files resolved inside the run folder
            target = (PurePosixPath(PurePosixPath(run).name) / PurePosixPath(shot).relative_to(run)).as_posix()
            copies[shot] = target
        steps.append({**{key: step.get(key) for key in STEP_KEYS}, "screenshot": target})
    return {**{key: data.get(key) for key in RESULT_KEYS}, "steps": steps}


def _target(root: Path, eff: Effective, out: str | None) -> Path:
    """The report folder, not created yet: `out` (missing or empty), else a new `<evidence>/report-<stamp>`."""
    if out is not None:
        path = (root / out).resolve()
        if path.exists() and (not path.is_dir() or any(path.iterdir())):
            raise QaError(f"{out}: exists and is not an empty folder")
        return path
    base = root / e2e.evidence_root(eff)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    path, suffix = base / f"report-{stamp}", 2
    while path.exists():
        path, suffix = base / f"report-{stamp}-{suffix}", suffix + 1
    return path


def build(root: Path, eff: Effective, capability: str | None, out: str | None) -> dict[str, Any]:
    """Writes `index.html` and the screenshots it shows into a new folder; returns what the CLI prints."""
    cases, _ = tc.load(root, eff.cases_dir)  # parse findings are `gin-qa cases check`'s job
    if capability is not None:
        cases = [case for case in cases if case.cap == capability]
    if not cases:
        raise QaError(f"no test cases for capability {capability}" if capability
                      else f"no test cases under {eff.cases_dir}")
    template = e2e._template(TEMPLATE).read_text(encoding="utf-8")
    if template.count(PLACEHOLDER) != 1:
        raise QaError(f"the {TEMPLATE} template must hold {PLACEHOLDER} once; reinstall gin-qa")
    folder = _target(root, eff, out)
    evidence = f"{e2e.evidence_root(eff)}/"
    runs: dict[str, tuple[str, Results] | None] = {}
    copies: dict[str, str] = {}
    rows = []
    for case in cases:
        row = {**tc.as_dict(case), "evidence": "none", "results": []}
        run = row["run"]
        if run.startswith(evidence) and not _tests_run(root, run):  # anything else is shown as text
            if run not in runs:
                runs[run] = _run_results(root, eff, run)
            found = runs[run]
            row["evidence"] = "missing" if found is None else "found"
            if found is not None:
                shown, by_id = found
                row["results"] = [_result(data, shown, copies) for data in by_id.get(case.id, [])]
        rows.append(row)
    created = not folder.exists()  # False only for an empty --out folder
    # simplified: a second report in the same second exits 2 if it loses the mkdir race; no lock needed
    folder.mkdir(parents=True, exist_ok=not created)
    index = folder / "index.html"
    try:
        for source, target in copies.items():
            (folder / target).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / source, folder / target)
        data = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "scope": capability,
                "cases": rows}
        index.write_text(template.replace(PLACEHOLDER, json.dumps(data, sort_keys=True).replace("<", "\\u003c")),
                         encoding="utf-8")
    except OSError:
        shutil.rmtree(folder, ignore_errors=True)  # everything in it is ours: it was new or empty
        if not created:
            folder.mkdir()  # an empty --out folder is left as it was
        raise
    return {"report": index.relative_to(root).as_posix() if root in index.parents else str(index),
            "cases": len(rows), "screenshots": len(copies),
            "missing_evidence": [run for run, found in runs.items() if found is None]}

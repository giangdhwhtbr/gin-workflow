"""`gin-qa cases bug`: file a bug bead for a failed case, linked to the epic the case was written for."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Mapping, Sequence

from . import cases as tc, e2e
from .reqs import Effective, QaError

_EPIC = re.compile(r"^Epic: (\S+)$", re.MULTILINE)
_WORKFLOW = re.compile(r"^Workflow: (\S+)$", re.MULTILINE)
PRIORITY = {"high": "1", "medium": "2", "low": "3"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _gin_workflow(root: Path, *args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    """`gin ...` in the repository: `task` runs bd against the current directory's database."""
    executable = shutil.which("gin")
    if executable is None:
        raise QaError("gin is not on PATH; install gin-workflow first")
    return subprocess.run([executable, *args], cwd=root, input=stdin, capture_output=True, text=True)


def _record(stdout: str) -> dict[str, Any] | None:
    """The first object of a `--json` answer: bd prints a list for show and one object for create."""
    try:
        data = json.loads(stdout)
    except ValueError:
        return None
    row = data[0] if isinstance(data, list) and data else data
    return row if isinstance(row, dict) else None


def _show(root: Path, bead: str) -> tuple[dict[str, Any] | None, str]:
    """(the bead, "") when found; (None, "") when the tracker has no such bead; (None, <stderr>) on any other failure."""
    shown = _gin_workflow(root, "task", "show", bead, "--json")
    if shown.returncode == 0:
        return _record(shown.stdout), ""
    if "no issue" in shown.stderr + shown.stdout:
        return None, ""
    return None, shown.stderr.strip() or f"gin task show exited {shown.returncode}"


def _workflow_epic(root: Path, topic: str) -> str | None:
    """The epic recorded at orchestration-ready for a `Workflow: <topic>` spec (`gin state`)."""
    state = _gin_workflow(root, "state", "--workflow-id", topic, "--repository", str(root), "--format", "json")
    try:
        epic = json.loads(state.stdout).get("epic")
    except (ValueError, AttributeError):
        return None
    return epic if isinstance(epic, str) and epic else None


def epic_of(root: Path, eff: Effective, case: tc.Case) -> list[str]:
    """Legacy: the spec named in `Source:` (its `Epic:` line, else the epic of its `Workflow:`), read from the project
    root, which holds the specs and the tracker (`root` is the QA home's repository), as a list of one or none. SDD:
    every epic of the case's REQs, in REQ order."""
    project = eff.project_root
    source = case.fields.get("Source")
    if source:
        relative = source.split("#", 1)[0].strip()
        path = (project / relative).resolve()
        if project.resolve() not in path.parents:
            raise QaError(f"{case.id}: {relative} is outside the repository")
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise QaError(f"{case.id}: cannot read {relative}: {getattr(error, 'strerror', None) or error}") from error
        if found := _EPIC.search(text):
            return [found.group(1)]
        topic = _WORKFLOW.search(text)
        epic = _workflow_epic(project, topic.group(1)) if topic else None
        return [epic] if epic else []
    return list(dict.fromkeys(eff.reqs[req]["epic"] for req, _ in case.reqs if eff.reqs.get(req, {}).get("epic")))


def _evidence_lines(evidence: list[str], attached: Mapping[str, tuple[str, str]]) -> list[str]:
    """An evidence value that was attached becomes an image line and its local path; any other stays a plain line."""
    lines: list[str] = []
    for item in evidence:
        if item in attached:
            label, sha = attached[item]
            lines += [f"- ![{label}](attachment:{sha})", f"  local: {item}"]
        else:
            lines.append(f"- {item}")
    return lines


def description(case: tc.Case, run: str | None, previous: str | None, actual: str, evidence: list[str],
                attached: Mapping[str, tuple[str, str]] | None = None) -> str:
    head = [f"- Case: {case.path}:{case.line}", *([f"- Run: {run}"] if run else []),
            *([f"- Previous bug: {previous}"] if previous else [])]
    sections = [("Preconditions", [f"- {item}" for item in case.preconditions]),
                ("Test data", [f"- {item}" for item in case.test_data]),
                ("Steps", [f"{number}. {step}" for number, step in enumerate(case.steps, 1)]),
                ("Expected", [f"- {item}" for item in case.expected]),
                ("Actual", [actual]),
                ("Evidence", _evidence_lines(evidence, attached or {}))]
    return "\n\n".join(["\n".join(head), *(f"## {name}\n\n" + "\n".join(lines) for name, lines in sections if lines)])


def rerun_note(run: str | None, actual: str, evidence: list[str], shas: Sequence[str] = ()) -> str:
    """One line with no double quote: a Windows .cmd shim cuts an argument at its first newline and re-parses quotes."""
    evidence = [*evidence, *(f"attachment:{sha}" for sha in shas)]
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    parts = [f"Re-run {day}", *([f"Run: {run}"] if run else []), f"Actual: {actual}",
             *([f"Evidence: {', '.join(evidence)}"] if evidence else [])]
    return "; ".join(parts).replace('"', "'")


def _images(root: Path, eff: Effective, case: tc.Case, run: str | None,
            evidence: list[str]) -> tuple[list[tuple[Path, str, int | None, str]], list[str]]:
    """((file, label, step, local path) of every image to attach, warnings). Images: files named in `evidence` that
    resolve, symlinks followed, inside `root` or the project root with an image suffix; then the screenshot of each
    failed step of the case's results in the e2e run folder `run`, when it names one. `root` holds the evidence."""
    found: dict[Path, tuple[Path, str, int | None, str]] = {}
    warnings: list[str] = []
    base = root.resolve()
    allowed = (base, eff.project_root.resolve())

    def local(path: Path) -> str:
        return path.relative_to(base).as_posix() if base in path.parents else str(path)

    for value in evidence:
        path = (root / value).resolve()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES and any(top in path.parents for top in allowed):
            found.setdefault(path, (path, f"{case.id}: {path.name}", None, value))
    try:
        folder = e2e._run_folder(root, eff, run)[0] if run else None
    except QaError:
        folder = None
    try:
        case_dir = folder / case.id.lower() if folder else None
        if folder and case_dir and e2e._contained(folder, case_dir):
            for result_dir in e2e._result_folders(case_dir):
                data = e2e._result(result_dir / "result.json")[0] if e2e._contained(folder, result_dir) else None
                for step in data["steps"] if data else []:
                    if not isinstance(step, dict) or step.get("status") != "failed":
                        continue
                    shot = e2e._artifact(result_dir, step.get("screenshot"))
                    if shot is None or shot.suffix.lower() not in IMAGE_SUFFIXES:
                        continue
                    number = step.get("n") if isinstance(step.get("n"), int) else None
                    label = f"{case.id} step {number}: {step.get('title')}" if number else f"{case.id}: {shot.name}"
                    found.setdefault(shot, (shot, label, number, local(shot)))
    except (QaError, OSError, ValueError) as error:
        warnings.append(f"{run}: failed step screenshots not read: {error}")
    return list(found.values()), warnings


def _attach(project: Path, bug: str, case_id: str,
            images: list[tuple[Path, str, int | None, str]]) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """`gin attach add` per image: ({local path: (label, sha256)}, warnings). Nothing here raises."""
    attached: dict[str, tuple[str, str]] = {}
    warnings: list[str] = []
    for file, label, step, local in images:
        label = " ".join(label.replace('"', "'").replace("[", "(").replace("]", ")").split())
        argv = ["attach", "add", bug, str(file), "--case", case_id, *(["--step", str(step)] if step else []),
                "--caption", label, "--format", "json"]
        try:
            done = _gin_workflow(project, *argv)
        except (QaError, OSError) as error:
            warnings.append(f"{local}: not attached: {error}")
            continue
        try:
            answer = json.loads(done.stdout) if done.returncode in (0, 1) else None
            sha = answer["entries"][0]["sha256"] if answer and answer["entries"] else None
            refused = [f"{item['name']}: {item['reason']}" for item in answer["refused"]] if answer else []
        except (ValueError, KeyError, TypeError, IndexError):
            answer, sha, refused = None, None, []
        if isinstance(sha, str) and sha:
            attached[local] = (label, sha)
            if answer.get("warning"):
                warnings.append(f"{local}: {answer['warning']}")
        else:
            reason = "; ".join(refused) or done.stderr.strip() or f"gin attach add exited {done.returncode}"
            warnings.append(f"{local}: not attached: {reason}")
    return attached, warnings


def file_bug(root: Path, eff: Effective, case_id: str, actual: str, evidence: list[str], *,
             external_ref: str | None = None, discovered_from: str | None = None,
             run: str | None = None) -> dict[str, Any]:
    """Record `failed` on a case with its open bug, or with a new bug bead filed against the case's epic."""
    for value in (actual, *evidence, *(item for item in (external_ref, discovered_from, run) if item is not None)):
        tc.one_line(value)
    case = tc.find(root, eff.cases_dir, case_id)
    project = eff.project_root  # Beads runs against the project root; the case files live under `root`
    run = run if run is not None else case.fields.get("Run")
    previous = case.fields.get("Bug")
    if previous:
        old, _ = _show(project, previous)  # a value that is not a readable bead counts as no open bug
        if old is not None and old.get("status") not in (None, "closed"):
            images, warnings = _images(root, eff, case, run, evidence)
            attached, failed = _attach(project, previous, case_id, images)
            warnings += failed
            shas = [sha for _, sha in attached.values()]
            added = _gin_workflow(project, "task", "update", previous, "--append-notes",
                                  rerun_note(run, actual, evidence, shas))
            if added.returncode != 0:  # before the case changes, so the tester can run this again
                raise QaError(added.stderr.strip() or f"gin task update exited {added.returncode}")
            row = tc.record_result(root, eff.cases_dir, case_id, "failed", run, previous)
            return {"tc": case_id, "bug": previous, "epic": None, "created": False, "appended": True,
                    "file": row["file"], "attachments": shas, "warnings": warnings}
    if discovered_from:
        epic = discovered_from
    else:
        epics = epic_of(root, eff, case)
        if not epics:
            raise QaError(f"no epic for {case_id}; pass --discovered-from <bead>")
        if len(epics) > 1:
            raise QaError(f"several epics for {case_id}: {', '.join(epics)}; pass --discovered-from <bead>")
        epic = epics[0]
    found, failure = _show(project, epic)
    if failure:
        raise QaError(failure)
    if found is None:
        raise QaError(f"{epic}: no such bead; pass --discovered-from <bead>")
    priority = PRIORITY.get(case.fields.get("Priority", "").strip().lower(), "2")
    # the description goes on stdin: a Windows .cmd shim cuts an argument at its first newline
    argv = ["task", "create", "-t", "bug", "--title", f"{case_id}: {case.title}".replace('"', "'"),
            "--body-file", "-", "--deps", f"discovered-from:{epic}", "-p", priority,
            *(["--external-ref", external_ref] if external_ref else []), "--json"]
    images, scan_warnings = _images(root, eff, case, run, evidence)
    # every image path is listed as plain evidence first, so a failed attach leaves the local path in the bug
    listed = [*evidence, *(local for _, _, _, local in images if local not in evidence)]
    created = _gin_workflow(project, *argv, stdin=description(case, run, previous, actual, listed))
    if created.returncode != 0:
        raise QaError(created.stderr.strip() or f"gin task create exited {created.returncode}")
    bug = (_record(created.stdout) or {}).get("id")
    if not isinstance(bug, str) or not bug:
        raise QaError(f"gin task create printed no bead id: {created.stdout.strip()[:200]!r}")
    try:
        row = tc.record_result(root, eff.cases_dir, case_id, "failed", run, bug)
    except (ValueError, OSError) as error:
        raise QaError(f"filed {bug} but could not record it: {error}; "
                      f"run gin-qa cases result {case_id} failed --bug {bug}") from error
    attached, warnings = _attach(project, bug, case_id, images)
    warnings = [*scan_warnings, *warnings]
    if attached:
        try:
            body = description(case, run, previous, actual, listed, attached)
            rewritten = _gin_workflow(project, "task", "update", bug, "--body-file", "-", stdin=body)
            if rewritten.returncode != 0:
                reason = rewritten.stderr.strip() or f"gin task update exited {rewritten.returncode}"
                warnings.append(f"{bug}: description not updated: {reason}")
        except (QaError, OSError) as error:
            warnings.append(f"{bug}: description not updated: {error}")
    return {"tc": case_id, "bug": bug, "epic": epic, "created": True, "appended": False, "file": row["file"],
            "attachments": [sha for _, sha in attached.values()], "warnings": warnings}

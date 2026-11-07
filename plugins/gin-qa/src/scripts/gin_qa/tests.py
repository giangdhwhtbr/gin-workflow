"""`gin-qa tests`: tests of the automated case types other than e2e, declared in the guidelines, and their runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any
from xml.etree import ElementTree

from . import cases as tc
from .e2e import ignore_evidence, new_run_folder
from .reqs import Effective, QaError

SECTION = "## Automated types"
RESERVED = ("e2e", "manual")
MARKER = re.compile(r"\bTC: (TC-[A-Z][A-Z0-9-]*-\d{3,})@([0-9a-f]{8})\b")
_ITEM = re.compile(r"^- (Tests|Run): (.*)$")
_BACKTICKED = re.compile(r"`([^`]+)`")
SKIP_DIRS = {".git", "node_modules"}


@dataclass
class AutomatedType:
    name: str
    globs: list[str]
    command: str


@dataclass
class Marker:
    tc: str
    pinned: str
    path: str  # repository-relative, '/'-separated
    line: int


def _command_problems(command: str) -> list[str]:
    try:
        argv = shlex.split(command)
    except ValueError as error:
        return [f"Run: {error}"]
    problems = [] if any("{junit}" in token for token in argv) else ["Run needs {junit}"]
    if any("{files}" in token and token != "{files}" for token in argv):
        problems.append("{files} must be a whole argument")
    return problems


def declared(root: Path, eff: Effective) -> tuple[dict[str, AutomatedType], list[str]]:
    """The `## Automated types` section of the guidelines: the valid types by name, and the declaration errors."""
    path = root / eff.guidelines
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    blocks: list[tuple[str, int, dict[str, str]]] = []
    inside = False
    for number, line in enumerate(lines, 1):
        if line.startswith("## "):
            inside = line.rstrip() == SECTION
        elif inside and line.startswith("### "):
            blocks.append((line[4:].strip(), number, {}))
        elif inside and blocks and (item := _ITEM.match(line)):
            blocks[-1][2][item.group(1)] = item.group(2)
    types: dict[str, AutomatedType] = {}
    first: dict[str, int] = {}
    errors: list[str] = []
    for name, number, items in blocks:
        where = f"{eff.guidelines}:{number}: {name}"
        if not tc.TYPE.fullmatch(name):
            errors.append(f"{where}: not a type name (lower-case letters, digits, and '-')")
            continue
        if name in RESERVED:
            errors.append(f"{where}: cannot be declared here; e2e and manual have their own commands")
            continue
        if name in first:
            errors.append(f"{where}: declared twice (first at line {first[name]})")
            continue
        first[name] = number
        problems: list[str] = []
        globs = _BACKTICKED.findall(items.get("Tests", ""))
        if not globs:
            problems.append("needs a '- Tests:' line with one or more backticked globs")
        problems += [f"Tests glob `{g}` must be relative to the repository root, without '..'" for g in globs
                     if PurePosixPath(g).is_absolute() or PureWindowsPath(g).is_absolute() or ".." in g.split("/")]
        commands = _BACKTICKED.findall(items.get("Run", ""))
        if len(commands) != 1:
            problems.append("needs a '- Run:' line with one backticked command")
        else:
            problems += _command_problems(commands[0])
        errors += [f"{where}: {problem}" for problem in problems]
        if not problems:
            types[name] = AutomatedType(name, globs, commands[0])
    return types, errors


def _types(root: Path, eff: Effective, only: str | None = None) -> dict[str, AutomatedType]:
    types, errors = declared(root, eff)
    if errors:
        raise QaError(f"{eff.guidelines} declares automated types with errors; run `gin-qa tests check`")
    if only is not None and only not in types:
        raise QaError(f"--type {only}: not declared under '{SECTION}' in {eff.guidelines}")
    return types


def _files(root: Path, globs: list[str]) -> list[str]:
    """Repository-relative files matching any glob, found by walking each glob's leading folders without wildcards."""
    found: set[str] = set()
    for pattern in globs:
        regex = tc.glob_regex(pattern)
        parts = pattern.split("/")
        fixed = next((index for index, part in enumerate(parts) if "*" in part or "?" in part), len(parts))
        base = root.joinpath(*parts[:fixed])
        candidates = [base] if base.is_file() else []
        # ponytail: skips only .git and node_modules; a glob starting with `**` walks the whole repository
        for folder, dirs, names in os.walk(base):
            dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
            candidates += [Path(folder) / name for name in names]
        found.update(rel for rel in (path.relative_to(root).as_posix() for path in candidates) if regex.match(rel))
    return sorted(found)


def markers(root: Path, files: list[str]) -> list[Marker]:
    found: list[Marker] = []
    for rel in files:
        text = (root / rel).read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.split("\n"), 1):
            found += [Marker(match.group(1), match.group(2), rel, number) for match in MARKER.finditer(line)]
    return found


def _row(case: tc.Case, kind: str) -> dict[str, Any]:
    return {"tc": case.id, "type": kind, "hash8": tc.hash8(case), "case": tc.as_dict(case)}


def plan(root: Path, eff: Effective, capability: str | None = None, only: str | None = None) -> dict[str, Any]:
    capability = tc.capability_arg(capability)
    types = _types(root, eff, only)
    cases, _ = tc.load(root, eff.cases_dir)  # parse findings are `gin-qa cases check`'s job
    by_id = {case.id: case for case in cases}
    files = {name: _files(root, kind.globs) for name, kind in types.items()}
    missing: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    orphan: list[dict[str, Any]] = []
    for name in sorted(types) if only is None else [only]:
        tested: set[str] = set()
        for mark in markers(root, files[name]):
            case = by_id.get(mark.tc)
            if case is not None and case.type != name and mark.path in files.get(case.type, []):
                continue  # a test of another declared type whose globs also cover this file
            if capability and tc.TC_ID.fullmatch(mark.tc).group(1) != capability.upper():
                continue
            where = {"file": mark.path, "line": mark.line}
            if case is None or case.type != name:
                if not any((row["tc"], row["file"], row["line"]) == (mark.tc, mark.path, mark.line) for row in orphan):
                    orphan.append({"tc": mark.tc, "type": name, **where})
                continue
            if mark.pinned != tc.hash8(case):
                stale.append({**_row(case, name), **where, "pinned": mark.pinned})
            tested.add(case.id)
        missing += [_row(case, name) for case in cases
                    if case.type == name and (not capability or case.cap == capability) and case.id not in tested]
    return {"types": {name: {"tests": kind.globs, "run": kind.command} for name, kind in types.items()},
            "missing": missing, "stale": stale, "orphan": orphan}


def check(root: Path, eff: Effective, only: str | None = None) -> list[str]:
    _, errors = declared(root, eff)
    if errors:
        return errors
    work = plan(root, eff, None, only)
    findings = [f"{row['case']['file']}:{row['case']['line']}: {row['tc']} has no test of type {row['type']}; "
                f"write it with `/gin-qa:tests {row['case']['capability']} --type {row['type']}`"
                for row in work["missing"]]
    findings += [f"{row['file']}:{row['line']}: {row['tc']} changed (pinned {row['pinned']}, now {row['hash8']}); "
                 f"update the test, then `gin-qa tests pin {row['tc']}`" for row in work["stale"]]
    findings += [f"{row['file']}:{row['line']}: {row['tc']} is not a test case of type {row['type']}"
                 for row in work["orphan"]]
    return findings


def pin(root: Path, eff: Effective, ids: list[str]) -> list[str]:
    """Rewrites the hash8 of every marker of each case; writes nothing when any ID fails."""
    types = _types(root, eff)
    cases = {case.id: case for case in tc.load(root, eff.cases_dir)[0]}
    errors: list[str] = []
    edits: dict[str, list[tuple[int, str, str]]] = {}
    for case_id in ids:
        case = cases.get(case_id)
        if case is None or case.type not in types:
            errors.append(f"{case_id}: not a test case of a declared automated type")
            continue
        found = [mark for mark in markers(root, _files(root, types[case.type].globs)) if mark.tc == case_id]
        if not found:
            errors.append(f"{case_id}: no 'TC: {case_id}@<hash8>' marker in the {case.type} tests")
        for mark in found:
            edits.setdefault(mark.path, []).append((mark.line, case_id, tc.hash8(case)))
    if errors:
        return errors
    texts: dict[str, str] = {}
    for rel, changes in edits.items():
        try:
            lines = (root / rel).read_text(encoding="utf-8").split("\n")
        except UnicodeDecodeError:
            errors.append(f"{rel}: not UTF-8 text")
            continue
        for number, case_id, value in changes:
            lines[number - 1] = re.sub(rf"\bTC: {re.escape(case_id)}@[0-9a-f]{{8}}\b", f"TC: {case_id}@{value}",
                                       lines[number - 1])
        texts[rel] = "\n".join(lines)
    if errors:
        return errors
    for rel, text in texts.items():
        tc.write_atomic(root / rel, text)
    return []


def _select(cases: dict[str, tc.Case], marked: dict[str, set[str]], kind: str, targets: list[str]) -> list[str]:
    """The case IDs to run: every case of the type with a marker, or those the targets name."""
    ids = sorted(marked)
    if not targets:
        if not ids:
            raise QaError(f"no {kind} tests with a 'TC:' marker; write them with /gin-qa:tests <capability> --type {kind}")
        return ids
    chosen: list[str] = []
    for target in targets:
        if tc.TC_ID.fullmatch(target):
            if target not in marked:
                raise QaError(f"{target}: no {kind} test with its marker")
            chosen.append(target)
        else:
            found = [case_id for case_id in ids if cases[case_id].cap == target]
            if not found:
                raise QaError(f"{target}: no {kind} tests in this capability")
            chosen += found
    return list(dict.fromkeys(chosen))


def _junit(path: Path) -> tuple[list[tuple[str, str]], str | None]:
    """(`classname name` upper-cased with `_` as `-`, status) per testcase, or the problem with the file."""
    if not path.is_file():
        return [], "missing; the Run command must write JUnit XML to {junit}"
    try:
        top = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as error:
        return [], f"not valid XML: {error}"
    except OSError as error:
        return [], f"cannot be read: {error}"
    if top.tag not in ("testsuites", "testsuite"):
        return [], f"the root is <{top.tag}>, not <testsuites> or <testsuite>"
    rows: list[tuple[str, str]] = []
    for test in top.iter("testcase"):
        if test.find("failure") is not None or test.find("error") is not None:
            status = "failed"
        elif test.find("skipped") is not None:
            status = "blocked"
        else:
            status = "passed"
        rows.append((f"{test.get('classname', '')} {test.get('name', '')}".replace("_", "-").upper(), status))
    return rows, None


def _outcome(case_id: str, rows: list[tuple[str, str]]) -> str | None:
    """The worst status of the test cases named after the case, or None when none ran."""
    named = re.compile(rf"(?<![A-Z0-9]){re.escape(case_id)}(?!\d)")
    statuses = [status for name, status in rows if named.search(name)]
    return next((worst for worst in ("failed", "blocked", "passed") if worst in statuses), None)


def run(root: Path, eff: Effective, kind: str, targets: list[str]) -> tuple[str, int, list[str], list[dict[str, str]]]:
    """Runs the declared command of `kind` into a new evidence folder and records each selected case's result.

    Returns (folder, the command's exit, findings, recorded results).
    """
    declared_type = _types(root, eff, kind)[kind]
    cases = {case.id: case for case in tc.load(root, eff.cases_dir)[0] if case.type == kind}
    marked: dict[str, set[str]] = {}
    for mark in markers(root, _files(root, declared_type.globs)):
        if mark.tc in cases:
            marked.setdefault(mark.tc, set()).add(mark.path)
    selected = _select(cases, marked, kind, targets)
    argv = shlex.split(declared_type.command)
    program = shutil.which(str(root / argv[0]) if "/" in argv[0] or "\\" in argv[0] else argv[0])
    if program is None:
        raise QaError(f"{argv[0]}: not found; check the Run command of {kind} in {eff.guidelines}")
    folder = new_run_folder(root, eff, f"-{kind}")
    ignore_evidence(root, eff)
    junit = root / folder / "junit.xml"
    files = sorted({path for case_id in selected for path in marked[case_id]})
    command: list[str] = []
    for token in argv:
        command += files if token == "{files}" else [token.replace("{junit}", str(junit))]
    record: dict[str, Any] = {"type": kind, "started": datetime.now(timezone.utc).isoformat(), "command": command,
                              "cases": selected, "exit": None}
    (root / folder / "run.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    result = subprocess.run([program, *command[1:]], cwd=root, stdout=sys.stderr)
    record["exit"] = result.returncode
    (root / folder / "run.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    rows, problem = _junit(junit)
    findings = [f"{folder}/junit.xml: {problem}"] if problem else []
    recorded: list[dict[str, str]] = []
    for case_id in selected:
        status = "blocked" if problem else _outcome(case_id, rows)
        if status is None:
            findings.append(f"{case_id}: no test named after it ran")
            status = "blocked"
        try:
            tc.record_result(root, eff.cases_dir, case_id, status, run=folder)
        except (ValueError, OSError) as error:
            findings.append(f"{case_id}: result not recorded: {error}")
            continue
        recorded.append({"tc": case_id, "result": status})
    return folder, result.returncode, findings, recorded

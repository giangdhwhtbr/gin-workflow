"""`gin-qa tests`: tests of the automated case types other than e2e, declared in the guidelines, and their runs."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shlex
from typing import Any

from . import cases as tc
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
    for rel, changes in edits.items():
        lines = (root / rel).read_text(encoding="utf-8").split("\n")
        for number, case_id, value in changes:
            lines[number - 1] = re.sub(rf"\bTC: {re.escape(case_id)}@[0-9a-f]{{8}}\b", f"TC: {case_id}@{value}",
                                       lines[number - 1])
        tc.write_atomic(root / rel, "\n".join(lines))
    return []

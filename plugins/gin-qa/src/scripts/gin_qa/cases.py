"""Test case files: `### TC-<CAP>-NNN: <title>` blocks with fields, Preconditions, Steps, and Expected."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import re
import subprocess

TC_ID = re.compile(r"\bTC-([A-Z][A-Z0-9-]*)-(\d{3,})\b")
_HEADING = re.compile(r"^### (TC-([A-Z][A-Z0-9-]*)-(\d{3,})): (\S.*)$")
_FIELD = re.compile(r"^([A-Za-z][A-Za-z0-9 _-]*):\s*(\S.*)$")
_REQ_ITEM = re.compile(r"^(REQ-[A-Z][A-Z0-9-]*-\d{3,})@([0-9a-f]{8})$")
_STEP = re.compile(r"^(\d+)\. (\S.*)$")
SECTIONS = ("Preconditions", "Steps", "Expected")
KNOWN_FIELDS = ("REQ", "Source", "Type", "Priority")


@dataclass
class Case:
    id: str
    cap: str
    title: str
    path: Path
    line: int
    fields: dict[str, str] = field(default_factory=dict)
    field_lines: dict[str, int] = field(default_factory=dict)
    reqs: list[tuple[str, str]] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    expected: list[str] = field(default_factory=list)


def _parse_block(path: Path, lines: list[str], start: int, end: int, errors: list[str]) -> Case | None:
    found = _HEADING.match(lines[start])
    where = f"{path}:{start + 1}"
    if not found:
        errors.append(f"{where}: heading is not a test case '### TC-<CAP>-<NNN>: <title>': {lines[start]!r}")
        return None
    case = Case(found.group(1), found.group(2).lower(), found.group(4), path, start + 1)
    section = ""
    seen: list[str] = []
    for index in range(start + 1, end):
        line, at = lines[index], f"{path}:{index + 1}"
        if not line.strip():
            continue
        name = line.strip()[:-1] if line.strip().endswith(":") else ""
        if name in SECTIONS:
            if name in seen or (seen and SECTIONS.index(name) < SECTIONS.index(seen[-1])):
                errors.append(f"{at}: {case.id}: sections must appear once, in the order "
                              "Preconditions, Steps, Expected")
            seen.append(name)
            section = name
        elif not section:
            match = _FIELD.match(line)
            if not match:
                errors.append(f"{at}: {case.id}: expected 'Key: value' before Preconditions/Steps")
                continue
            key, value = match.group(1).strip(), match.group(2).strip()
            if key in case.fields:
                errors.append(f"{at}: {case.id}: duplicate field {key}")
            case.fields[key], case.field_lines[key] = value, index + 1
        elif section == "Steps":
            match = _STEP.match(line)
            if not match or int(match.group(1)) != len(case.steps) + 1:
                errors.append(f"{at}: {case.id}: steps must be numbered 1., 2., 3., ...")
                continue
            case.steps.append(match.group(2))
        elif line.startswith("- ") and line[2:].strip():
            (case.preconditions if section == "Preconditions" else case.expected).append(line[2:].strip())
        else:
            errors.append(f"{at}: {case.id}: {section} items are '- ' bullets")
    for name in ("Steps", "Expected"):
        if not (case.steps if name == "Steps" else case.expected):
            errors.append(f"{where}: {case.id}: needs at least one {name} item")
    if "REQ" in case.fields:
        for item in (part.strip() for part in case.fields["REQ"].split(",")):
            match = _REQ_ITEM.match(item)
            if match:
                case.reqs.append((match.group(1), match.group(2)))
            else:
                errors.append(f"{path}:{case.field_lines['REQ']}: {case.id}: REQ entries are "
                              f"'REQ-<CAP>-<NNN>@<hash8>' separated by ', ', got {item!r}")
    return case


def parse_file(path: Path, shown: str) -> tuple[list[Case], list[str]]:
    """Every `### ` block up to the next `## `/`### ` heading; findings are `<file>:<line>: <message>`."""
    lines = path.read_text(encoding="utf-8").splitlines()
    starts = [index for index, line in enumerate(lines) if line.startswith("### ")]
    ends = [index for index, line in enumerate(lines) if line.startswith("## ") or line.startswith("### ")]
    cases: list[Case] = []
    errors: list[str] = []
    for start in starts:
        end = next((index for index in ends if index > start), len(lines))
        case = _parse_block(Path(shown), lines, start, end, errors)
        if case is not None:
            cases.append(case)
    return cases, errors


def case_files(root: Path, cases_dir: str) -> dict[str, Path]:
    base = root / cases_dir
    return {path.stem: path for path in sorted(base.glob("*.md"))} if base.is_dir() else {}


def load(root: Path, cases_dir: str) -> tuple[list[Case], list[str]]:
    cases: list[Case] = []
    errors: list[str] = []
    for cap, path in case_files(root, cases_dir).items():
        found, problems = parse_file(path, path.relative_to(root).as_posix())
        errors += problems
        for case in found:
            if case.cap != cap:
                errors.append(f"{case.path}:{case.line}: {case.id} belongs in {cases_dir}/{case.cap}.md, not {cap}.md")
        cases += found
    seen: dict[str, Case] = {}
    for case in cases:
        if case.id in seen:
            errors.append(f"{case.path}:{case.line}: duplicate {case.id} (first at {seen[case.id].path}:"
                          f"{seen[case.id].line})")
        seen.setdefault(case.id, case)
    return cases, errors


def next_id(root: Path, cases_dir: str, cap: str) -> str:
    """One past the highest number in the file now or in its git history, so numbers are never reused."""
    path = root / cases_dir / f"{cap}.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    history = subprocess.run(["git", "log", "--format=", "-p", "--", str(path)], cwd=root,
                             capture_output=True, text=True, check=False)
    if history.returncode == 0:
        text += history.stdout
    upper = cap.upper()
    numbers = [int(match.group(2)) for match in TC_ID.finditer(text) if match.group(1) == upper]
    return f"TC-{upper}-{max(numbers, default=0) + 1:03d}"


def glob_regex(pattern: str) -> re.Pattern[str]:
    out = ""
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            out, index = out + "(?:.*/)?", index + 3
        elif pattern.startswith("**", index):
            out, index = out + ".*", index + 2
        elif pattern[index] == "*":
            out, index = out + "[^/]*", index + 1
        elif pattern[index] == "?":
            out, index = out + "[^/]", index + 1
        else:
            out, index = out + re.escape(pattern[index]), index + 1
    return re.compile(f"^{out}$")


def hash8(case: Case) -> str:
    """What a test implements: title, free fields, and sections. REQ:/Source:, Type, and Priority are left out,
    so re-pinning a requirement does not make the case's e2e spec stale."""
    lines = [case.title, *(f"{key}: {value}" for key, value in case.fields.items() if key not in KNOWN_FIELDS)]
    for name, items in zip(SECTIONS, (case.preconditions, case.steps, case.expected)):
        lines += [f"{name}:", *items]
    return hashlib.sha256("\n".join(line.strip() for line in lines).encode("utf-8")).hexdigest()[:8]


def as_dict(case: Case) -> dict[str, object]:
    return {"id": case.id, "title": case.title, "capability": case.cap, "file": str(case.path), "line": case.line,
            "hash8": hash8(case),
            "reqs": [{"id": req, "hash8": pinned} for req, pinned in case.reqs],
            "source": case.fields.get("Source", ""), "type": case.fields.get("Type", ""),
            "priority": case.fields.get("Priority", ""),
            "fields": {key: value for key, value in case.fields.items() if key not in KNOWN_FIELDS},
            "preconditions": case.preconditions, "steps": case.steps, "expected": case.expected}

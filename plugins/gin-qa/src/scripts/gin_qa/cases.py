"""Test case files: `### TC-<CAP>-NNN: <title>` blocks with fields, Preconditions, Steps, and Expected."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path, PurePosixPath
import re
import subprocess

TC_ID = re.compile(r"\bTC-([A-Z][A-Z0-9-]*?)-(\d{3,})\b")  # lazy: TC-AUTH-005-2024-tax is TC-AUTH-005
_FIELD = re.compile(r"^(?:- )?(\*\*)?([A-Za-z][A-Za-z0-9 _-]*):(?(1)\*\*|(?!\*\*))\s*(\S.*)$")
_SECTION = re.compile(r"^(\*\*)?([A-Za-z][A-Za-z ]*):(?(1)\*\*)$")
_REQ_ITEM = re.compile(r"^(REQ-[A-Z][A-Z0-9-]*-\d{3,})@([0-9a-f]{8})$")
_STEP = re.compile(r"^(\d+)\. (\S.*)$")
_CASE_FILE = re.compile(r"^(TC-[A-Z][A-Z0-9-]*?-\d{3,})(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?\.([a-z][a-z0-9-]*)\.md$")
TYPE = re.compile(r"^[a-z][a-z0-9-]*$")
SECTIONS = ("Preconditions", "Test data", "Steps", "Expected")
RESULTS = ("passed", "failed", "blocked", "not run")
RESULT_FIELDS = ("Result", "Run", "Bug")
KNOWN_FIELDS = ("REQ", "Source", "Type", "Priority", *RESULT_FIELDS)


def _heading(level: str) -> re.Pattern[str]:
    return re.compile(rf"^{level} (TC-([A-Z][A-Z0-9-]*)-(\d{{3,}})): (\S.*)$")


@dataclass
class Case:
    id: str
    cap: str
    title: str
    path: PurePosixPath  # repository-relative, '/'-separated on every platform
    line: int
    fields: dict[str, str] = field(default_factory=dict)
    field_lines: dict[str, int] = field(default_factory=dict)
    reqs: list[tuple[str, str]] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    expected: list[str] = field(default_factory=list)
    test_data: list[str] = field(default_factory=list)
    type: str = ""


def _parse_block(path: PurePosixPath, lines: list[str], start: int, end: int, errors: list[str],
                 level: str = "###") -> Case | None:
    found = _heading(level).match(lines[start])
    where = f"{path}:{start + 1}"
    if not found:
        errors.append(f"{where}: heading is not a test case '{level} TC-<CAP>-<NNN>: <title>': {lines[start]!r}")
        return None
    case = Case(found.group(1), found.group(2).lower(), found.group(4), path, start + 1)
    section = ""
    seen: list[str] = []
    for index in range(start + 1, end):
        line, at = lines[index], f"{path}:{index + 1}"
        if not line.strip():
            continue
        label = _SECTION.match(line.strip())
        name = label.group(2) if label else ""
        if name in SECTIONS:
            if name in seen or (seen and SECTIONS.index(name) < SECTIONS.index(seen[-1])):
                errors.append(f"{at}: {case.id}: sections must appear once, in the order " + ", ".join(SECTIONS))
            seen.append(name)
            section = name
        elif not section:
            match = _FIELD.match(line)
            if not match:
                errors.append(f"{at}: {case.id}: expected 'Key: value' before Preconditions/Steps")
                continue
            key, value = match.group(2).strip(), match.group(3).strip()
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
            {"Preconditions": case.preconditions, "Test data": case.test_data,
             "Expected": case.expected}[section].append(line[2:].strip())
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
    result = case.fields.get("Result")
    if result is not None and result not in RESULTS:
        errors.append(f"{path}:{case.field_lines['Result']}: {case.id}: Result is one of {', '.join(RESULTS)}; "
                      f"got {result!r}")
    for key in ("Run", "Bug"):
        if key in case.fields and result is None:
            errors.append(f"{path}:{case.field_lines[key]}: {case.id}: {key}: needs a Result: line")
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
        case = _parse_block(PurePosixPath(shown), lines, start, end, errors)
        if case is not None:
            case.type = case.fields.get("Type", "").strip().lower()
            cases.append(case)
    return cases, errors


def parse_case_file(path: Path, shown: str) -> tuple[list[Case], list[str]]:
    """A per-case file `<TC-ID>[-<slug>].<type>.md` holding one `# TC-…: <title>` case; the type is the name's."""
    named = _CASE_FILE.match(path.name)
    if not named:
        return [], [f"{shown}: case file name is not '<TC-ID>[-<slug>].<type>.md'"]
    lines = path.read_text(encoding="utf-8").splitlines()
    heads = [index for index, line in enumerate(lines) if line.startswith("#")]
    if len(heads) != 1:
        return [], [f"{shown}: holds {len(heads)} headings; a case file holds one '# TC-<CAP>-<NNN>: <title>'"]
    errors = [f"{shown}:{index + 1}: text before the case heading" for index in range(heads[0])
              if lines[index].strip()][:1]
    case = _parse_block(PurePosixPath(shown), lines, heads[0], len(lines), errors, "#")
    if case is None:
        return [], errors
    case.type = named.group(2)
    if case.id != named.group(1):
        errors.append(f"{shown}:{case.line}: {case.id}: file name says {named.group(1)}")
    if "Type" in case.fields:
        errors.append(f"{shown}:{case.field_lines['Type']}: {case.id}: Type comes from the file name; "
                      "remove the Type: line")
    return [case], errors


def parse_path(root: Path, cases_dir: str, path: Path) -> tuple[list[Case], list[str]]:
    shown = path.relative_to(root).as_posix()
    flat = path.parent == root / cases_dir
    return parse_file(path, shown) if flat else parse_case_file(path, shown)


def case_files(root: Path, cases_dir: str) -> list[Path]:
    """Flat `<cases>/<capability>.md` files and per-case `<cases>/<capability>/*.md` files."""
    base = root / cases_dir
    return sorted([*base.glob("*.md"), *base.glob("*/*.md")]) if base.is_dir() else []


def load(root: Path, cases_dir: str) -> tuple[list[Case], list[str]]:
    cases: list[Case] = []
    errors: list[str] = []
    base = root / cases_dir
    for path in case_files(root, cases_dir):
        flat = path.parent == base
        if flat and (base / path.stem).is_dir():
            errors.append(f"{cases_dir}/{path.stem}.md: capability also has folder {cases_dir}/{path.stem}/; "
                          f"run gin-qa cases split {path.stem}")
        found, problems = parse_path(root, cases_dir, path)
        errors += problems
        folder = path.stem if flat else path.parent.name
        for case in found:
            if case.cap != folder:
                where = f"{cases_dir}/{case.cap}.md, not {folder}.md" if flat else \
                    f"{cases_dir}/{case.cap}/, not {folder}/"
                errors.append(f"{case.path}:{case.line}: {case.id} belongs in {where}")
        cases += found
    seen: dict[str, Case] = {}
    for case in cases:
        if case.id in seen:
            errors.append(f"{case.path}:{case.line}: duplicate {case.id} (first at {seen[case.id].path}:"
                          f"{seen[case.id].line})")
        seen.setdefault(case.id, case)
    return cases, errors


def next_id(root: Path, cases_dir: str, cap: str) -> str:
    """One past the highest number in the flat file, the case file names, or their git history: never reused."""
    path, folder = root / cases_dir / f"{cap}.md", root / cases_dir / cap
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    text += "\n".join(item.name for item in folder.glob("*.md")) if folder.is_dir() else ""
    for args in (["-p", "--", str(path)], ["--name-only", "--", str(folder)]):
        history = subprocess.run(["git", "log", "--format=", *args], cwd=root, capture_output=True, text=True,
                                 check=False)
        if history.returncode == 0:
            text += "\n" + history.stdout
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
    """What a test implements: title, free fields, and sections. REQ:/Source:, Type, Priority, and the result
    fields are left out; an empty Test data section adds nothing, so cases written before it keep their hash."""
    lines = [case.title, *(f"{key}: {value}" for key, value in case.fields.items() if key not in KNOWN_FIELDS)]
    for name, items in zip(SECTIONS, (case.preconditions, case.test_data, case.steps, case.expected)):
        if name != "Test data" or items:
            lines += [f"{name}:", *items]
    return hashlib.sha256("\n".join(line.strip() for line in lines).encode("utf-8")).hexdigest()[:8]


def field_line(like: str, key: str, value: str) -> str:
    """`key: value` in the form of the field line `like`: `- **Key:** value` or `Key: value`."""
    return f"- **{key}:** {value}" if like.lstrip().startswith("- **") else f"{key}: {value}"


def as_dict(case: Case) -> dict[str, object]:
    return {"id": case.id, "title": case.title, "capability": case.cap, "file": str(case.path), "line": case.line,
            "hash8": hash8(case),
            "reqs": [{"id": req, "hash8": pinned} for req, pinned in case.reqs],
            "source": case.fields.get("Source", ""), "type": case.type,
            "priority": case.fields.get("Priority", ""),
            "fields": {key: value for key, value in case.fields.items() if key not in KNOWN_FIELDS},
            "preconditions": case.preconditions, "steps": case.steps, "expected": case.expected,
            "result": case.fields.get("Result", "not run"), "run": case.fields.get("Run", ""),
            "bug": case.fields.get("Bug", ""), "test_data": case.test_data}

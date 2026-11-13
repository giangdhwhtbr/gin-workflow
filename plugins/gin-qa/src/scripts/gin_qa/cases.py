"""Test case files: `### TC-<CAP>-NNN: <title>` blocks with fields, Preconditions, Steps, and Expected."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import time

TC_ID = re.compile(r"\bTC-([A-Z][A-Z0-9-]*?)-(\d{3,})\b")  # lazy: TC-AUTH-005-2024-tax is TC-AUTH-005
_FIELD = re.compile(r"^(?:- )?(\*\*)?([A-Za-z][A-Za-z0-9 _-]*):(?(1)\*\*|(?!\*\*))\s*(\S.*)$")
_SECTION = re.compile(r"^(\*\*)?([A-Za-z][A-Za-z ]*):(?(1)\*\*)$")
_REQ_ITEM = re.compile(r"^(REQ-[A-Z][A-Z0-9-]*-\d{3,})@([0-9a-f]{8})$")
_STEP = re.compile(r"^(\d+)\. (\S.*)$")
_CASE_FILE = re.compile(r"^(TC-[A-Z][A-Z0-9-]*?-\d{3,})(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?\.([a-z][a-z0-9-]*)\.md$")
TYPE = re.compile(r"^[a-z][a-z0-9-]*$")
TYPES_SECTION = "## Types"
_TYPE_ENTRY = re.compile(r"^- `([a-z][a-z0-9-]*)`(?::.*)?$")
SECTIONS = ("Preconditions", "Test data", "Steps", "Expected")
RESULTS = ("passed", "failed", "blocked", "not run")
RESULT_FIELDS = ("Result", "Run", "Bug")
MOVED_FIELD = "Moved from e2e"
_MOVED = re.compile(r"^(\d{4}-\d{2}-\d{2}): (\S.*)$")
LEGACY_FIELD = "Legacy"
KNOWN_FIELDS = ("REQ", "Source", "Type", "Priority", MOVED_FIELD, LEGACY_FIELD, *RESULT_FIELDS)


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
    moved = case.fields.get(MOVED_FIELD)
    if moved is not None and not _MOVED.match(moved):
        errors.append(f"{path}:{case.field_lines[MOVED_FIELD]}: {case.id}: {MOVED_FIELD}: is "
                      f"'<YYYY-MM-DD>: <reason>'; got {moved!r}")
    if LEGACY_FIELD in case.fields:
        at = f"{path}:{case.field_lines[LEGACY_FIELD]}: {case.id}: {LEGACY_FIELD}:"
        refs = legacy_refs(case)
        if not refs:
            errors.append(f"{at} needs at least one reference")
        for item in refs:
            path_part = item.split("#", 1)[0].replace("\\", "/")
            if not path_part:
                errors.append(f"{at} {item} needs a path before #")
                continue
            target = PurePosixPath(path_part)
            if target.is_absolute() or re.match(r"^[A-Za-z]:", target.as_posix()) or ".." in target.parts:
                errors.append(f"{at} {item} must be a relative path inside the repository")
    return case


def legacy_refs(case: Case) -> list[str]:
    return [item for item in (part.strip() for part in case.fields.get(LEGACY_FIELD, "").split(",")) if item]


def _lines(path: Path) -> list[str]:
    """Split on newlines only, as the writers do: splitlines() also breaks on \\x0c, \\x85, \\u2028, ..."""
    return path.read_text(encoding="utf-8").split("\n")


def declared_types(root: Path, guidelines: str) -> tuple[set[str] | None, list[str]]:
    """The types listed under `## Types` in the guidelines, or None without the file or section; and its findings."""
    path = root / guidelines
    if not path.is_file():
        return None, []
    lines = [line.rstrip() for line in _lines(path)]
    start = next((index for index, line in enumerate(lines) if line == TYPES_SECTION), None)
    if start is None:
        return None, []
    types: set[str] = set()
    errors: list[str] = []
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.startswith("## "):
            break
        if not line.startswith("- "):
            continue
        entry = _TYPE_ENTRY.match(line)
        if entry:
            types.add(entry.group(1))
        else:
            errors.append(f"{guidelines}:{index + 1}: '{TYPES_SECTION}' entry is not \"- `<type>`: <description>\"")
    if not types and not errors:
        errors.append(f"{guidelines}:{start + 1}: '{TYPES_SECTION}' lists no types")
    return types, errors


def parse_file(path: Path, shown: str) -> tuple[list[Case], list[str]]:
    """Every `### ` block up to the next `## `/`### ` heading; findings are `<file>:<line>: <message>`."""
    lines = _lines(path)
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
    lines = _lines(path)
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
    return sorted([*base.glob("*.md"), *base.glob("*/*.md")], key=lambda path: path.parts) if base.is_dir() else []


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


def capability_arg(value: str | None) -> str | None:
    """`value`, refused when it is a TC-ID rather than a capability."""
    found = TC_ID.fullmatch(value or "")
    if found:
        raise ValueError(f"{value}: a TC-ID, not a capability; pass its capability, for example `{found.group(1).lower()}`")
    return value


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



@contextmanager
def _lock(folder: Path, timeout: float = 10.0):
    """One gin-qa writer at a time per cases folder; a crashed writer leaves the file, named in the error."""
    path = folder / ".gin-qa.lock"
    deadline = time.monotonic() + timeout
    while True:
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except (FileExistsError, PermissionError):
            if time.monotonic() > deadline:
                raise ValueError(f"{path}: held for {timeout:.0f}s; delete it if no gin-qa is running") from None
            time.sleep(0.02)
    try:
        yield
    finally:
        os.close(handle)
        os.unlink(path)


def write_atomic(path: Path, text: str) -> None:
    """Readers in other processes see the old or the new file, never half of one.

    `text` ends lines with \\n; they are written as the replaced file ends them (CRLF stays CRLF), else \\n.
    """
    newline = "\r\n" if path.is_file() and b"\r\n" in path.read_bytes() else "\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8", newline=newline)
    for attempt in range(40):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:  # ponytail: Windows refuses a replace while a reader has the file open; retry 2s
            if attempt == 39:
                raise
            time.sleep(0.05)


def _with_result(text: str, case: Case, values: list[tuple[str, str | None]]) -> str:
    lines = text.split("\n")
    own = {case.field_lines[key] for key in RESULT_FIELDS if key in case.field_lines}
    others = [number for key, number in case.field_lines.items() if key not in RESULT_FIELDS]
    anchor = max(others) if others else (min(own) - 1 if own else case.line)
    like = lines[max(others) - 1] if others else (lines[min(own) - 1] if own else "")
    new = [field_line(like, key, value) for key, value in values if value is not None]
    anchor -= sum(1 for number in own if number <= anchor)
    kept = [line for number, line in enumerate(lines, 1) if number not in own]
    return "\n".join(kept[:anchor] + new + kept[anchor:])


def one_line(value: str) -> str:
    """A value written into a case file or a bead: one non-empty line of printable characters."""
    if not value.strip() or not value.isprintable():
        raise ValueError(f"{value!r}: values are one non-empty line")
    return value


def find(root: Path, cases_dir: str, case_id: str) -> Case:
    """The case `case_id`; refused when the case files have a finding that names it."""
    cases, findings = load(root, cases_dir)
    located = next((case for case in cases if case.id == case_id), None)
    if located is None:
        raise ValueError(f"{case_id}: no such test case")
    about = [error for error in findings if re.search(rf"\b{re.escape(case_id)}\b", error)]
    if about:
        raise ValueError("; ".join(about))
    return located


def record_result(root: Path, cases_dir: str, case_id: str, status: str, run: str | None = None,
                  bug: str | None = None) -> dict[str, str]:
    """The only writer of Result/Run/Bug: Run is replaced (dropped when None); Bug changes only when given."""
    if status not in RESULTS:
        raise ValueError(f"status is one of {', '.join(RESULTS)}; got {status!r}")
    for value in (run, bug):
        if value is not None:
            one_line(value)
    located = find(root, cases_dir, case_id)
    path = root / located.path
    flat = path.parent == root / cases_dir
    with _lock(root / cases_dir):
        found, errors = parse_path(root, cases_dir, path)
        case = next((item for item in found if item.id == case_id), None)
        # a per-case file holds only this case, so every finding in it is about the case
        problems = [error for error in errors if not flat or re.search(rf"\b{re.escape(case_id)}\b", error)]
        if case is None or problems:
            raise ValueError("; ".join(problems) or f"{case_id}: no longer in {located.path}")
        kept_bug = case.fields.get("Bug") if bug is None else (None if bug == "none" else bug)
        values = [("Result", status), ("Run", run), ("Bug", kept_bug)]
        write_atomic(path, _with_result(path.read_text(encoding="utf-8"), case, values))
    return {"tc": case_id, "result": status, "run": run or "", "bug": kept_bug or "", "file": str(located.path)}


def move_to_manual(root: Path, cases_dir: str, guidelines: str, case_id: str, reason: str) -> Path:
    """Renames an e2e case file to `.manual.md`, records why, and resets its result; returns the new path."""
    one_line(reason)
    located = find(root, cases_dir, case_id)
    path = root / located.path
    flat = path.parent == root / cases_dir
    target = path.with_name(path.name[:-len(".e2e.md")] + ".manual.md")
    with _lock(root / cases_dir):
        found, errors = parse_path(root, cases_dir, path)
        case = next((item for item in found if item.id == case_id), None)
        problems = [error for error in errors if not flat or re.search(rf"\b{re.escape(case_id)}\b", error)]
        if case is None or problems:
            raise ValueError("; ".join(problems) or f"{case_id}: no longer in {located.path}")
        if case.type != "e2e":
            raise ValueError(f"{case_id}: is a {case.type or 'untyped'} case; only an e2e case moves to manual")
        if flat:
            raise ValueError(f"{case.path}: a flat cases file; run `gin-qa cases split {case.cap}` first")
        if MOVED_FIELD in case.fields:
            raise ValueError(f"{case.path}:{case.field_lines[MOVED_FIELD]}: {case_id}: remove the {MOVED_FIELD}: line first")
        types, _ = declared_types(root, guidelines)
        if types is not None and "manual" not in types:
            raise ValueError(f"manual is not listed under '{TYPES_SECTION}' in {guidelines}")
        if target.exists():
            raise ValueError(f"{target.relative_to(root).as_posix()}: already exists")
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        values = [(MOVED_FIELD, f"{day}: {reason}"), ("Result", "not run"), ("Bug", case.fields.get("Bug"))]
        write_atomic(path, _with_result(path.read_text(encoding="utf-8"), case, values))
        path.rename(target)
    return target


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if len(slug) > 40:
        slug = slug[:41].rsplit("-", 1)[0] if "-" in slug[:41] else slug[:40]
    return f"-{slug}" if slug else ""


def new_case(root: Path, cases_dir: str, guidelines: str, cap: str, kind: str, title: str, key: str,
             value: str) -> tuple[str, Path]:
    """Writes `<cases>/<cap>/<TC-ID>-<slug>.<kind>.md` with the next ID; `key`/`value` is its REQ or Source field."""
    one_line(title)
    cap = capability_arg(cap)
    if not TYPE.fullmatch(cap):
        raise ValueError(f"{cap!r}: a capability matches [a-z][a-z0-9-]*")
    types, _ = declared_types(root, guidelines)
    if not TYPE.fullmatch(kind) or (types is not None and kind not in types):
        raise ValueError(f"{kind}: not listed under '{TYPES_SECTION}' in {guidelines}")
    base = root / cases_dir
    base.mkdir(parents=True, exist_ok=True)  # before the lock: the lock file lives in the cases folder
    with _lock(base):
        if (base / f"{cap}.md").is_file():
            raise ValueError(f"{cases_dir}/{cap}.md: a flat cases file; run `gin-qa cases split {cap}` first")
        (base / cap).mkdir(exist_ok=True)
        case_id = next_id(root, cases_dir, cap)
        path = base / cap / f"{case_id}{_slug(title)}.{kind}.md"
        write_atomic(path, f"# {case_id}: {title}\n\n- **{key}:** {value}\n- **Priority:** medium\n\n"
                           "**Preconditions:**\n\n**Test data:**\n\n**Steps:**\n\n**Expected:**\n")
    return case_id, path


def split(root: Path, cases_dir: str, cap: str) -> tuple[list[str], list[str]]:
    """`<cases>/<cap>.md` → one `<cases>/<cap>/<TC-ID>-<slug>.<type>.md` per case; nothing is written on findings."""
    if not TYPE.fullmatch(cap):
        raise ValueError(f"{cap!r}: a capability matches [a-z][a-z0-9-]*")
    base = root / cases_dir
    path = base / f"{cap}.md"
    shown = f"{cases_dir}/{cap}.md"
    if not path.is_file():
        raise ValueError(f"{shown}: no such file")
    found, errors = parse_file(path, shown)
    lines = path.read_text(encoding="utf-8").split("\n")
    first = next((index for index, line in enumerate(lines) if line.startswith("### ")), len(lines))
    head = [line for line in lines[:first] if line.strip()]
    if head[1:] or (head and not head[0].startswith("# ")) or any(line.startswith("## ") for line in lines):
        errors.append(f"{shown}: holds text outside its title and case blocks; move it before splitting")
    if not found:
        errors.append(f"{shown}: holds no test cases")
    targets: dict[str, Path] = {}
    for case in found:
        kind = case.fields.get("Type", "").strip().lower()
        if not TYPE.match(kind):
            errors.append(f"{shown}:{case.line}: {case.id}: needs a Type: matching [a-z][a-z0-9-]* to split")
        if case.cap != cap or case.id in targets:
            errors.append(f"{shown}:{case.line}: {case.id}: not a unique {cap} case")
        target = base / cap / f"{case.id}{_slug(case.title)}.{kind}.md"
        if target.exists():
            errors.append(f"{target.relative_to(root).as_posix()}: already exists")
        targets[case.id] = target
    if errors:
        return [], errors
    starts = [case.line - 1 for case in found] + [len(lines)]
    for case, start, end in zip(found, starts, starts[1:]):
        block = lines[start:end]
        block[0] = "# " + block[0][len("### "):]
        del block[case.field_lines["Type"] - 1 - start]
        targets[case.id].parent.mkdir(parents=True, exist_ok=True)
        targets[case.id].write_text("\n".join(block).rstrip("\n") + "\n", encoding="utf-8")
    path.unlink()
    return [target.relative_to(root).as_posix() for target in targets.values()], []

def moved_from_e2e(case: Case) -> dict[str, str] | None:
    found = _MOVED.match(case.fields.get(MOVED_FIELD, ""))
    return {"date": found.group(1), "reason": found.group(2)} if found else None


def as_dict(case: Case) -> dict[str, object]:
    return {"id": case.id, "title": case.title, "capability": case.cap, "file": str(case.path), "line": case.line,
            "hash8": hash8(case),
            "reqs": [{"id": req, "hash8": pinned} for req, pinned in case.reqs],
            "source": case.fields.get("Source", ""), "type": case.type,
            "priority": case.fields.get("Priority", ""),
            "fields": {key: value for key, value in case.fields.items() if key not in KNOWN_FIELDS},
            "preconditions": case.preconditions, "steps": case.steps, "expected": case.expected,
            "result": case.fields.get("Result", "not run"), "run": case.fields.get("Run", ""),
            "bug": case.fields.get("Bug", ""),
            "moved_from_e2e": moved_from_e2e(case), "test_data": case.test_data,
            "legacy": legacy_refs(case)}

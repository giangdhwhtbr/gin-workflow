"""SDD living specs: requirement blocks, lint, ID allocation, change folders, renumbering."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import subprocess
from typing import Any, Mapping, Sequence

from .atomic import atomic_write_many
from .configuration import resolve_effective_config
from . import epic_kind
from .executables import tool

DEFAULT_TEST_GLOBS = ("**/test_*.py", "**/*_test.py", "**/*.test.*", "**/*.spec.*", "tests/**", "__tests__/**")
SDD_DEFAULTS: dict[str, Any] = {
    "layout": "legacy", "specs": "docs/specs", "changes": "docs/changes", "adr": "docs/adr",
    "codebase": "docs/codebase", "explain": ".agent-workflow/runtime/explain", "spec_review": "chat", "test_globs": list(DEFAULT_TEST_GLOBS),
}
DELTA_SECTIONS = ("ADDED", "MODIFIED", "REMOVED")
# Change-folder files in reading order; the template for each is `<role>.md`.
CHANGE_FILES = {"proposal": "01-proposal.md", "spec-delta": "02-spec-delta.md", "design": "03-design.md",
                "plan": "04-plan.md", "tests": "05-tests.md"}
CHANGE_TEMPLATES = ("proposal", "spec-delta", "design", "tests")
REQ_ID = re.compile(r"\bREQ-([A-Z][A-Z0-9-]*)-(\d{3,})\b")
_FULL_ID = re.compile(r"^REQ-([A-Z][A-Z0-9-]*)-(\d{3,})$")
_HEADING = re.compile(r"^### (REQ-[A-Z][A-Z0-9-]*-\d{3,}): (\S.*)$")
_HEADING_LINE = re.compile(r"^### (REQ-[A-Z][A-Z0-9-]*-\d{3,}):", re.MULTILINE)
_BASE = re.compile(r"^<!-- base: ([0-9a-f]{64}) -->$")
_STATEMENT = re.compile(r"\b(SHALL|MUST)\b")
_CAP = re.compile(r"^[a-z][a-z0-9-]*$")
REQ_TYPES = ("functional", "non-functional", "business-rule")
NFR_CATEGORIES = ("performance", "security", "reliability", "usability", "compatibility", "maintainability",
                  "portability", "constraint")
# The folders of a capability next to its spec.md; the linters below and the SDD check of setup doctor share them.
ASSETS_DIR, DIAGRAMS_DIR, USE_CASES_DIR = "assets", "diagrams", "use-cases"
CAPABILITY_FOLDERS = (ASSETS_DIR, DIAGRAMS_DIR, USE_CASES_DIR)
ACTORS_FILE = "actors.md"
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_EPIC_LINE = re.compile(r"^Epic: (\S+)$", re.MULTILINE)


class SpecsError(ValueError):
    """Usage or configuration error (exit 2)."""


@dataclass(frozen=True)
class Block:
    id: str
    title: str
    section: str
    start: int
    end: int
    text: str

    @property
    def cap(self) -> str:
        return cap_of(self.id)

    @property
    def base(self) -> str | None:
        for line in self.text.splitlines()[1:]:
            found = _BASE.match(line.strip())
            if found:
                return found.group(1)
        return None

    def _field(self, key: str) -> str:
        """A `<key>:` line of the block body before its first `####` section."""
        return line_value(self.text.split("\n#### ", 1)[0], key)

    @property
    def type(self) -> str:
        return self._field("Type") or "functional"

    @property
    def category(self) -> str:
        return self._field("Category")

    @property
    def measure(self) -> str:
        return self._field("Measure")


_STORY_HEADING = re.compile(r"^### (US-\d+):")
_PLACEHOLDER = re.compile(r"\{\{|\bTBD\b|\bTODO\b")


def lint_design_spec(path: Path, root: Path | None = None) -> list[str]:
    """Legacy design spec: user stories with acceptance criteria and no placeholder left outside code."""
    errors, story, state, fenced = [], None, "", False
    stories = 0
    text = path.read_text(encoding="utf-8")
    repo_root = root
    if repo_root is None:
        toplevel = _git(path.parent, "rev-parse", "--show-toplevel")
        repo_root = Path(toplevel.stdout.strip()) if toplevel.returncode == 0 else path.parent
    shown_path = shown(repo_root, path)

    found_kind = epic_kind.spec_kind_line(text)
    spec_k = found_kind[0] if found_kind else None
    if found_kind:
        val, line_no = found_kind
        inv = epic_kind.invalid(val)
        if inv:
            errors.append(f"{shown_path}:{line_no}: {inv}")

    def close() -> None:
        if story and state != "bullet":
            errors.append(f"{path}:{story[1]}: {story[0]} has no acceptance criteria")

    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if _PLACEHOLDER.search(re.sub(r"`[^`]*`", "", line)):
            errors.append(f"{path}:{number}: placeholder left: {line.strip()}")
        if re.match(r"^#{1,3} ", line):
            close()
            match = _STORY_HEADING.match(line)
            story, state = ((match.group(1), number), "") if match else (None, "")
            stories += bool(match)
        elif story and line.strip().strip("*") == "Acceptance criteria:":
            state = "criteria"
        elif story and state == "criteria" and re.match(r"^\s*[-*] \S", line):
            state = "bullet"
    close()
    errors += technical_questions(path)[1]
    if spec_k not in ("technical", "parity") and not stories:
        errors.append(f"{path}:1: no user stories (### US-<n>:)")

    if spec_k == "parity":
        errors += epic_kind.parity_errors(repo_root, text, shown_path)

    return errors


_TQ_SECTION = "## Open Technical Questions"
_TQ = re.compile(r"^- (TQ-\d+): \S")
_DECISION = re.compile(r"^\s+Decision:(.*)$")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_LEGACY_SPECS = ".planning/specs"


@dataclass(frozen=True)
class Question:
    id: str
    line: int
    decision: str


def technical_questions(path: Path, label: str | None = None) -> tuple[list[Question], list[str]]:
    """Questions under `## Open Technical Questions` (an empty decision is open) and the section's format errors."""
    name = label or str(path)
    text = _COMMENT.sub(lambda found: "\n" * found.group().count("\n"), path.read_text(encoding="utf-8"))
    questions: list[Question] = []
    errors: list[str] = []
    inside = fenced = False
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if re.match(r"^#{1,2} ", line):
            inside = line.strip() == _TQ_SECTION
            continue
        if not inside or not line.strip():
            continue
        question, decision = _TQ.match(line), _DECISION.match(line)
        if question:
            if any(item.id == question.group(1) for item in questions):
                errors.append(f"{name}:{number}: {question.group(1)} appears twice")
            questions.append(Question(question.group(1), number, ""))
        elif decision and questions and questions[-1].line == number - 1:
            answer = decision.group(1).strip()
            if not answer:
                errors.append(f"{name}:{number}: {questions[-1].id} has an empty Decision:")
            questions[-1] = replace(questions[-1], decision=answer)
        elif decision:
            errors.append(f"{name}:{number}: Decision: without a question on the line above")
        else:
            errors.append(f"{name}:{number}: not a question (- TQ-<n>: <question>) or its Decision: line")
    return questions, errors


def design_doc(root: Path, cfg: Mapping[str, Any], workflow_id: str) -> Path | None:
    """The workflow's design doc: the SDD change's design file, or the one legacy spec naming the workflow."""
    root = Path(root)
    if cfg["layout"] == "sdd":
        try:
            design = change_file(find_change(root, cfg, workflow_id), "design")
        except SpecsError as error:
            if "ambiguous" in str(error):
                raise
            return None
        return design if design.is_file() else None
    named = re.compile(rf"^(?:Epic|Workflow): {re.escape(workflow_id)}$", re.MULTILINE)
    folder = root / _LEGACY_SPECS
    found = [path for path in sorted(folder.glob("*.md"))
             if named.search(path.read_text(encoding="utf-8", errors="replace"))] if folder.is_dir() else []
    if len(found) > 1:
        raise SpecsError(f"several specs name {workflow_id}: {', '.join(shown(root, path) for path in found)}")
    return found[0] if found else None


def cap_of(req_id: str) -> str:
    found = _FULL_ID.match(req_id)
    if not found:
        raise SpecsError(f"not a requirement id: {req_id!r}")
    return found.group(1).lower()


def sdd_config(config: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = config.get("artifacts") if isinstance(config.get("artifacts"), Mapping) else {}
    return {key: artifacts.get(key, default) for key, default in SDD_DEFAULTS.items()}


def load_config(repository: Path) -> Mapping[str, Any]:
    if not (Path(repository) / ".agent-workflow/config.yaml").is_file():
        raise SpecsError("gin setup is required; run /setup once")
    return resolve_effective_config(Path(repository), write=False).config.to_dict()


def require_layout(cfg: Mapping[str, Any], layout: str) -> None:
    if cfg["layout"] != layout:
        raise SpecsError(f"artifacts.layout is {cfg['layout']!r}; this command needs {layout!r}")


def plugin_templates_dir() -> Path:
    """Launcher layout ships `templates/` beside `workflow_core/`; plugin trees have it two levels up."""
    here = Path(__file__).resolve().parent
    for candidate in (here.parent / "templates", here.parent.parent / "templates"):
        if candidate.is_dir():
            return candidate
    raise SpecsError("plugin templates directory not found next to workflow_core")


def template_text(repository: Path, name: str) -> str:
    """Project override `.agent-workflow/templates/<name>` wins over the plugin template."""
    for base in (Path(repository) / ".agent-workflow/templates", plugin_templates_dir()):
        path = base / name
        if path.is_file():
            return path.read_text(encoding="utf-8")
    raise SpecsError(f"unknown template: {name}")


def render(text: str, values: Mapping[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def parse_blocks(text: str) -> tuple[list[Block], list[tuple[int, str]]]:
    """Requirement blocks (`### REQ-…` up to the next `##`/`###` heading) and malformed headings."""
    lines = text.splitlines()
    blocks: list[Block] = []
    errors: list[tuple[int, str]] = []
    section = ""
    current: tuple[str, str, int] | None = None

    def close(end: int) -> None:
        if current is not None:
            req_id, title, start = current
            body = "\n".join(lines[start:end]).rstrip()
            blocks.append(Block(req_id, title, section, start, end, body))

    for index, line in enumerate(lines):
        if line.startswith("## ") or line.startswith("### "):
            close(index)
            current = None
        if line.startswith("## "):
            section = line[3:].strip()
        elif line.startswith("### "):
            found = _HEADING.match(line)
            if found:
                current = (found.group(1), found.group(2), index)
            else:
                errors.append((index + 1, f"heading is not a requirement '### REQ-<CAP>-<NNN>: <title>': {line!r}"))
    close(len(lines))
    return blocks, errors


def block_hash(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines() if not _BASE.match(line.strip())]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def type_of(block: Block) -> str:
    """The block's type, or functional when its `Type:` is not a known one (lint reports that)."""
    return block.type if block.type in REQ_TYPES else "functional"


def statement(block: Block) -> str:
    """The first SHALL or MUST line of the block body, outside scenarios and bullets."""
    head = block.text.split("\n#### ", 1)[0].splitlines()[1:]
    return next((line.strip() for line in head if not line.startswith(("#", "- ")) and _STATEMENT.search(line)), "")


def lint_block(block: Block) -> list[str]:
    """Statement and scenario rules for an ADDED, MODIFIED, or living block."""
    errors: list[str] = []
    body = block.text.splitlines()[1:]
    prose = [line for line in body if line.strip() and not line.startswith("#") and not line.startswith("- ")]
    if not any(_STATEMENT.search(line) for line in prose):
        errors.append(f"{block.id}: needs a SHALL or MUST statement")
    head = _COMMENT.sub("", block.text.split("\n#### ", 1)[0])
    if block.type not in REQ_TYPES:
        errors.append(f"{block.id}: Type must be one of {', '.join(REQ_TYPES)}")
    non_functional = block.type == "non-functional"
    if non_functional and block.category not in NFR_CATEGORIES:
        errors.append(f"{block.id}: Category must be one of {', '.join(NFR_CATEGORIES)}")
    if not non_functional and re.search(r"^(Category|Measure):", head, re.MULTILINE):
        errors.append(f"{block.id}: Category and Measure are only for Type: non-functional")
    scenarios: list[list[str]] = []
    for line in body:
        if line.startswith("#### Scenario:"):
            scenarios.append([])
        elif line.startswith("#### "):
            errors.append(f"{block.id}: only '#### Scenario:' sub-headings are allowed")
        elif scenarios and line.startswith("- "):
            scenarios[-1].append(line[2:].split(" ", 1)[0])
    if not scenarios and non_functional and not block.measure:
        errors.append(f"{block.id}: needs at least one '#### Scenario:' or a 'Measure:' line")
    elif not scenarios and not non_functional:
        errors.append(f"{block.id}: needs at least one '#### Scenario:'")
    for number, steps in enumerate(scenarios, start=1):
        missing = [step for step in ("GIVEN", "WHEN", "THEN") if step not in steps]
        if missing:
            errors.append(f"{block.id}: scenario {number} lacks {', '.join(missing)}")
    return errors


def specs_dir(root: Path, cfg: Mapping[str, Any]) -> Path:
    return Path(root) / cfg["specs"]


def changes_dir(root: Path, cfg: Mapping[str, Any]) -> Path:
    return Path(root) / cfg["changes"]


def living_files(root: Path, cfg: Mapping[str, Any]) -> dict[str, Path]:
    base = specs_dir(root, cfg)
    return {path.parent.name: path for path in sorted(base.glob("*/spec.md"))} if base.is_dir() else {}


def living_blocks(root: Path, cfg: Mapping[str, Any]) -> dict[str, tuple[Path, Block]]:
    found: dict[str, tuple[Path, Block]] = {}
    for path in living_files(root, cfg).values():
        for block in parse_blocks(path.read_text(encoding="utf-8"))[0]:
            found.setdefault(block.id, (path, block))
    return found


def find_change(root: Path, cfg: Mapping[str, Any], change_id: str) -> Path:
    base = changes_dir(root, cfg)
    exact = base / change_id
    if exact.is_dir() and change_id != "archive":
        return exact
    matches = [p for p in sorted(base.glob(f"{change_id}-*")) if p.is_dir()] if base.is_dir() else []
    if len(matches) == 1:
        return matches[0]
    raise SpecsError(f"unknown change {change_id!r} under {cfg['changes']}" if not matches
                     else f"change {change_id!r} is ambiguous: {', '.join(p.name for p in matches)}")


def change_file(change: Path, role: str) -> Path:
    """The numbered file; a change folder written before numbering keeps its `<role>.md`."""
    numbered, legacy = change / CHANGE_FILES[role], change / f"{role}.md"
    return legacy if legacy.is_file() and not numbered.is_file() else numbered


def change_epic(change: Path) -> str:
    proposal = change_file(change, "proposal")
    found = _EPIC_LINE.search(proposal.read_text(encoding="utf-8")) if proposal.is_file() else None
    if not found:
        raise SpecsError(f"{proposal}: missing 'Epic: <id>' line")
    return found.group(1)


def change_kind(change: Path) -> str:
    """The declared kind from proposal.md, or default ('capability')."""
    proposal = change_file(change, "proposal")
    if proposal.is_file():
        kind_val = epic_kind.spec_kind(proposal.read_text(encoding="utf-8"))
        if kind_val:
            return kind_val
    return epic_kind.DEFAULT


def shown(root: Path, path: Path) -> str:
    """Repository-relative path for findings."""
    try:
        return Path(path).relative_to(root).as_posix()
    except ValueError:
        return str(path)


def delta_blocks(root: Path, change: Path) -> tuple[list[Block], list[str]]:
    path = change_file(change, "spec-delta")
    if not path.is_file():
        if change_kind(change) == "technical":
            return [], []
        return [], [f"{shown(root, path)}: missing {path.name}"]
    blocks, malformed = parse_blocks(path.read_text(encoding="utf-8"))
    errors = [f"{shown(root, path)}:{line}: {message}" for line, message in malformed]
    for block in blocks:
        if block.section not in DELTA_SECTIONS:
            errors.append(f"{shown(root, path)}:{block.start + 1}: {block.id} is outside ## ADDED/MODIFIED/REMOVED")
    return blocks, errors


_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATED_CHANGE = re.compile(r"^\d{4}-\d{2}-\d{2}-")


def lint_iterations(root: Path, cfg: Mapping[str, Any]) -> list[str]:
    """Every dated asset folder `<specs>/<cap>/assets/<YYYY-MM-DD>/` has a `description.md`."""
    return [f"{shown(root, folder)}: missing description.md (gin specs template iteration.md)"
            for folder in sorted(specs_dir(root, cfg).glob(f"*/{ASSETS_DIR}/*"))
            if folder.is_dir() and _ISO_DATE.match(folder.name) and not (folder / "description.md").is_file()]


_MERMAID = re.compile(r"^```mermaid[ \t]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
_DIAGRAM_KINDS = {"-activity.md": ("flowchart", "graph"), "-state.md": ("stateDiagram",)}


def _mermaid_types(text: str) -> list[str]:
    """The first word of each ```mermaid block, skipping blank lines and `%%` comments."""
    types: list[str] = []
    for body in _MERMAID.findall(text):
        first = next((line.strip() for line in body.splitlines()
                      if line.strip() and not line.strip().startswith("%%")), "")
        types.append(first.split()[0] if first else "")
    return types


def lint_diagrams(root: Path, cfg: Mapping[str, Any]) -> list[str]:
    """Every `<specs>/<cap>/diagrams/*-activity.md` / `*-state.md` holds a mermaid block of its kind."""
    errors: list[str] = []
    for path in sorted(specs_dir(root, cfg).glob(f"*/{DIAGRAMS_DIR}/*.md")):
        kinds = next((types for suffix, types in _DIAGRAM_KINDS.items() if path.name.endswith(suffix)), None)
        if kinds and not any(kind.startswith(kinds) for kind in _mermaid_types(path.read_text(encoding="utf-8"))):
            errors.append(f"{shown(root, path)}: no mermaid block starting with {' or '.join(kinds)}")
    return errors


_DECISION_NODE = re.compile(r"\b([A-Za-z_][\w-]*)\{(?!\{)")
_EDGE = re.compile(r"^\s*(?P<src>[A-Za-z_][\w-]*)(?:\s*(?:\{[^}]*\}|\[[^\]]*\]|\([^)]*\)+))?\s*"
                   r"(?:(?P<arrow>-->|-\.->|==>)\s*(?P<pipe>\|)?|(?:--|-\.|==)\s+[^\s>-][^\n]*?(?:-->|\.->|==>))")


def unlabelled_decision_edges(text: str) -> list[tuple[int, str]]:
    """(line number, node id) of each edge leaving a `{…}` decision without a label, in ```mermaid blocks.

    One edge per line: on a chained line only the first edge is read. `%%` comment lines are skipped."""
    body: list[tuple[int, str]] = []
    inside = False
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            inside = not inside and stripped.startswith("```mermaid")
        elif inside and not stripped.startswith("%%"):
            body.append((number, line))
    decisions = {found.group(1) for _, line in body for found in _DECISION_NODE.finditer(line)}
    return [(number, edge.group("src")) for number, line in body
            if (edge := _EDGE.match(line)) and edge.group("src") in decisions
            and edge.group("arrow") and not edge.group("pipe")]


_USE_CASE_REQS = re.compile(r"^Requirements:[ \t]*(.*)$", re.MULTILINE)
_MAIN_FLOW = re.compile(r"^## Main flow[ \t]*\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)


def line_value(text: str, key: str) -> str:
    """The value of the first `<key>:` line outside `<!-- -->` comments, stripped; '' when absent."""
    found = re.search(rf"^{re.escape(key)}:[ \t]*(.*)$", _COMMENT.sub("", text), re.MULTILINE)
    return found.group(1).strip() if found else ""


def line_values(text: str, key: str) -> list[str]:
    """The comma-separated values of the first `<key>:` line, each stripped, empty ones dropped."""
    return [value.strip() for value in line_value(text, key).split(",") if value.strip()]


_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


def actor_key(name: str) -> str:
    """An actor name without regard to case or repeated spaces: the key use case diagrams and catalogues share."""
    return " ".join(name.split()).casefold()


def use_case_ref(cap: str, value: str) -> tuple[str, str] | None:
    """The (capability, slug) a use case reference names: `slug` in `cap`, or `other/slug`."""
    parts = value.split("/")
    if len(parts) == 1 and parts[0]:
        return cap, parts[0]
    if len(parts) == 2 and all(parts) and parts[0] not in (".", ".."):
        return parts[0], parts[1]
    return None


def generalization_cycles(parents: Mapping[str, list[str]]) -> list[list[str]]:
    """Each cycle of a child -> parents graph once, as its sorted members."""
    cycles: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()

    def visit(node: str, path: list[str]) -> None:
        if node in path:
            cycle = sorted(path[path.index(node):])
            if tuple(cycle) not in seen:
                seen.add(tuple(cycle))
                cycles.append(cycle)
            return
        for parent in parents.get(node, ()):
            visit(parent, [*path, node])

    for node in sorted(parents):
        visit(node, [])
    return cycles


_CELL_SPLIT = re.compile(r"(?<!\\)\|")


def read_text_or_none(path: Path) -> str | None:
    """The UTF-8 text of `path`, or None when it cannot be read (the caller skips it, as `trace` does)."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _cells(line: str) -> list[str]:
    return [cell.strip().replace("\\|", "|") for cell in _CELL_SPLIT.split(line.strip().strip("|"))]


def table_rows(text: str) -> tuple[list[str], list[tuple[int, dict[str, str]]]] | None:
    """The first Markdown table of `text` outside `<!-- -->` comments: its header cells and each row as
    (line number, {header: cell}); `\\|` in a cell is a pipe, a short row is padded with ''."""
    lines = _COMMENT.sub(lambda found: "\n" * found.group(0).count("\n"), text).split("\n")
    for index, line in enumerate(lines[:-1]):
        if line.lstrip().startswith("|") and _TABLE_RULE.match(lines[index + 1]):
            header = _cells(line)
            rows = []
            for number in range(index + 2, len(lines)):
                if not lines[number].lstrip().startswith("|"):
                    break
                cells = _cells(lines[number])
                rows.append((number + 1, dict(zip(header, cells + [""] * (len(header) - len(cells))))))
            return header, rows
    return None


def actor_parents(root: Path, cfg: Mapping[str, Any]) -> dict[str, str]:
    """`actor_key(child)` -> parent label from the `Is a` column of `<specs>/actors.md`."""
    table = table_rows(read_text_or_none(specs_dir(root, cfg) / ACTORS_FILE) or "")
    return {actor_key(row["Actor"]): " ".join(row["Is a"].split())
            for _, row in (table[1] if table else []) if row.get("Actor") and row.get("Is a")}


def lint_actors(root: Path, cfg: Mapping[str, Any]) -> list[str]:
    """`<specs>/actors.md`, when present, is a table with Actor and Description columns naming only actors of use cases."""
    base = specs_dir(root, cfg)
    path = base / ACTORS_FILE
    if not path.is_file():
        return []
    content = read_text_or_none(path)
    if content is None:
        return [f"{shown(root, path)}: cannot be read as UTF-8 text"]
    table = table_rows(content)
    if table is None or not {"Actor", "Description"} <= set(table[0]):
        return [f"{shown(root, path)}: needs a table with Actor and Description columns"]
    named = set()
    for case in base.glob(f"*/{USE_CASES_DIR}/*.md"):
        text = read_text_or_none(case)
        if text is None:
            continue
        named |= {actor_key(name) for name in [line_value(text, "Actor"), *line_values(text, "Secondary actors")] if name}
    errors = [f"{shown(root, path)}:{number}: actor '{row['Actor']}' is in no use case"
              for number, row in table[1] if row["Actor"] and actor_key(row["Actor"]) not in named]
    if "Is a" in table[0]:
        rows = [row for _, row in table[1] if row["Actor"]]
        known = named | {actor_key(row["Actor"]) for row in rows}
        errors += [f"{shown(root, path)}:{number}: actor '{row['Actor']}' is a '{row['Is a']}', which is no actor"
                   for number, row in table[1] if row["Actor"] and row["Is a"] and actor_key(row["Is a"]) not in known]
        labels = {actor_key(row[column]): row[column] for row in rows for column in ("Is a", "Actor") if row[column]}
        parents = {actor_key(row["Actor"]): [actor_key(row["Is a"])] for row in rows if row["Is a"]}
        errors += [f"{shown(root, path)}: actor generalization cycle: {', '.join(labels[key] for key in cycle)}"
                   for cycle in generalization_cycles(parents)]
    return errors


def lint_references(root: Path, cfg: Mapping[str, Any]) -> list[str]:
    """`Includes:`/`Extends:`/`Specializes:` of a use case name a use case (`slug`, or `cap/slug` of another capability);
    `Use case:` of an activity diagram names one of the same capability."""
    base = specs_dir(root, cfg)
    errors: list[str] = []
    for cap in sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []:
        cases = sorted((cap / USE_CASES_DIR).glob("*.md"))
        slugs = {path.stem for path in cases}
        for path in cases:
            text = path.read_text(encoding="utf-8")
            for key in ("Includes", "Extends", "Specializes"):
                for value in line_values(text, key):
                    target = use_case_ref(cap.name, value)
                    if target == (cap.name, path.stem):
                        errors.append(f"{shown(root, path)}: {key} names the use case itself")
                    elif target is None or not (base / target[0] / USE_CASES_DIR / f"{target[1]}.md").is_file():
                        errors.append(f"{shown(root, path)}: {key} names unknown use case '{value}'")
        for path in sorted((cap / DIAGRAMS_DIR).glob("*-activity.md")):
            errors += [f"{shown(root, path)}: Use case names unknown use case '{slug}'"
                       for slug in line_values(path.read_text(encoding="utf-8"), "Use case") if slug not in slugs]
    return errors


def open_changes(root: Path, cfg: Mapping[str, Any]) -> list[Path]:
    """Change folders that are not archived and have a spec delta, sorted by name."""
    base = changes_dir(root, cfg)
    return [change for change in (sorted(base.iterdir()) if base.is_dir() else [])
            if change.is_dir() and change.name != "archive" and change_file(change, "spec-delta").is_file()]


def in_flight_blocks(root: Path, cfg: Mapping[str, Any], *,
                     exclude: Path | None = None) -> dict[str, list[tuple[Path, Block]]]:
    """ADDED blocks of open changes (other than `exclude`) whose REQ-ID is not in a living spec yet."""
    living = living_blocks(root, cfg)
    found: dict[str, list[tuple[Path, Block]]] = {}
    for change in open_changes(root, cfg):
        if exclude is not None and change.resolve() == Path(exclude).resolve():
            continue
        for block in delta_blocks(root, change)[0]:
            if block.section == "ADDED" and block.id not in living:
                found.setdefault(block.id, []).append((change, block))
    return found


def _known_req_ids(root: Path, cfg: Mapping[str, Any]) -> set[str]:
    """REQ-IDs in a living spec, or ADDED or MODIFIED in an open change folder."""
    known = set(living_blocks(root, cfg))
    for change in open_changes(root, cfg):
        known |= {b.id for b in delta_blocks(root, change)[0] if b.section in ("ADDED", "MODIFIED")}
    return known


def lint_use_cases(root: Path, cfg: Mapping[str, Any]) -> list[str]:
    """Every `<specs>/<cap>/use-cases/*.md` has a title, an actor, known REQ-IDs, and a numbered main flow."""
    paths = sorted(specs_dir(root, cfg).glob(f"*/{USE_CASES_DIR}/*.md"))
    known = _known_req_ids(root, cfg) if paths else set()
    raw = {path: path.read_text(encoding="utf-8") for path in paths}
    included = {ref for path, text in raw.items()
                for ref in (use_case_ref(path.parent.parent.name, value) for value in line_values(text, "Includes")) if ref}
    parents = {}
    for path, text in raw.items():
        cap = path.parent.parent.name
        parents[f"{cap}/{path.stem}"] = [f"{ref[0]}/{ref[1]}" for ref in
                                        (use_case_ref(cap, value) for value in line_values(text, "Specializes")) if ref]
    errors: list[str] = []
    for cycle in generalization_cycles(parents):
        first = specs_dir(root, cfg) / cycle[0].split("/")[0] / USE_CASES_DIR / f"{cycle[0].split('/')[1]}.md"
        errors.append(f"{shown(root, first)}: use case generalization cycle: {', '.join(cycle)}")
    for path in paths:
        text, name = _COMMENT.sub("", raw[path]), shown(root, path)
        if not re.search(r"^# \S", text, re.MULTILINE):
            errors.append(f"{name}: missing '# <use case name>' title")
        if not re.search(r"^Actor:[ \t]*\S", text, re.MULTILINE) and (path.parent.parent.name, path.stem) not in included:
            errors.append(f"{name}: missing 'Actor: <primary actor>' line")
        line = _USE_CASE_REQS.search(text)
        ids = [found.group(0) for found in REQ_ID.finditer(line.group(1))] if line else []
        if line is None:
            errors.append(f"{name}: missing 'Requirements: REQ-…' line")
        elif not ids:
            errors.append(f"{name}: no REQ-ID on its Requirements line")
        flow = _MAIN_FLOW.search(text)
        if not (flow and re.search(r"^\d+\.\s+\S", flow.group(1), re.MULTILINE)):
            errors.append(f"{name}: missing '## Main flow' with a numbered list")
        errors += [f"{name}: {req} is not in a living spec or an open change" for req in ids if req not in known]
    return errors


def lint_living(root: Path, cfg: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}
    for cap, path in living_files(root, cfg).items():
        name = shown(root, path)
        if not _CAP.match(cap):
            errors.append(f"{name}: capability folder must match [a-z][a-z0-9-]*")
        blocks, malformed = parse_blocks(path.read_text(encoding="utf-8"))
        errors += [f"{name}:{line}: {message}" for line, message in malformed]
        for block in blocks:
            where = f"{name}:{block.start + 1}"
            if block.cap != cap:
                errors.append(f"{where}: {block.id} belongs in {block.cap}/spec.md")
            if block.id in seen:
                errors.append(f"{where}: {block.id} duplicates {seen[block.id]}")
            seen.setdefault(block.id, name)
            errors += [f"{where}: {message}" for message in lint_block(block)]
    return errors + lint_iterations(root, cfg) + lint_diagrams(root, cfg) + lint_use_cases(root, cfg) + lint_references(root, cfg) + lint_actors(root, cfg)


_FLOW_SECTION = re.compile(r"^## (?:Alternative|Exception) flows[ \t]*\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)


def has_branch_flows(text: str) -> bool:
    """A use case with a `### ` flow under `## Alternative flows` or `## Exception flows`."""
    return any(re.search(r"^### \S", body, re.MULTILINE) for body in _FLOW_SECTION.findall(_COMMENT.sub("", text)))


def _feature_diagram_findings(root: Path, cfg: Mapping[str, Any], blocks: list[Block],
                              against: str | None) -> list[str]:
    """Activity diagrams a change owes: one per capability it adds to, one per changed use case with branch flows,
    labelled decisions in changed diagrams. Without `against`, the per-capability rule of old."""
    base = specs_dir(root, cfg)
    blocks = [block for block in blocks if block.type != "non-functional"]
    if not against:
        caps = sorted({block.cap for block in blocks if block.section in ("ADDED", "MODIFIED")})
        return [f"{cap}: no activity diagram in {shown(root, base / cap / DIAGRAMS_DIR)}/ "
                "(gin specs template activity.md)"
                for cap in caps if not any((base / cap / DIAGRAMS_DIR).glob("*-activity.md"))]
    caps = sorted({block.cap for block in blocks if block.section == "ADDED"})
    changed = changed_since(root, against, base)
    errors = [f"{cap}: no activity diagram added or changed in {shown(root, base / cap / DIAGRAMS_DIR)}/ "
              f"since {against} (gin specs template activity.md)"
              for cap in caps
              if not any(shown(root, p) in changed for p in (base / cap / DIAGRAMS_DIR).glob("*-activity.md"))]
    for path in sorted(base.glob(f"*/{USE_CASES_DIR}/*.md")):
        if shown(root, path) not in changed or not has_branch_flows(path.read_text(encoding="utf-8")):
            continue
        drawn = {slug for diagram in (path.parent.parent / DIAGRAMS_DIR).glob("*-activity.md")
                 for slug in line_values(diagram.read_text(encoding="utf-8"), "Use case")}
        if path.stem not in drawn:
            errors.append(f"{shown(root, path)}: no activity diagram with 'Use case: {path.stem}'")
    for path in sorted(base.glob(f"*/{DIAGRAMS_DIR}/*-activity.md")):
        if shown(root, path) in changed:
            errors += [f"{shown(root, path)}:{number}: edge from decision '{node}' has no label"
                       for number, node in unlabelled_decision_edges(path.read_text(encoding="utf-8"))]
    return errors


def _lint_kind(root: Path, change: Path) -> tuple[str, list[str]]:
    """The change's kind for lint: the epic's `kind:` label, else `Kind:` of 01-proposal.md, and a mismatch finding.

    When the task tracker cannot answer, the `Kind:` line decides without a finding, so lint works without Beads."""
    proposal = change_file(change, "proposal")
    found = _EPIC_LINE.search(proposal.read_text(encoding="utf-8")) if proposal.is_file() else None
    kind, error = epic_kind.lookup(root, found.group(1) if found else None, shown(root, change))
    if error is None:
        return kind, []
    if error.startswith("kind mismatch"):
        return kind, [f"{shown(root, proposal)}: {error}"]
    return change_kind(change), []


def _epic_kinds(root: Path) -> dict[str, str] | None:
    """The `kind:` label of each issue that has exactly one, in one tracker query; None when the tracker cannot answer."""
    from . import tasks

    rows, cause = tasks.query_result(root, ["list", "--all", "--limit", "0"])
    if cause or not isinstance(rows, list):
        return None
    kinds: dict[str, str] = {}
    for row in rows:
        found = epic_kind.label_kinds(list(row.get("labels") or ())) if isinstance(row, Mapping) else []
        if len(found) == 1 and "id" in row:
            kinds[row["id"]] = found[0]
    return kinds


def _cited_diagrams(root: Path, change: Path, specs_root: Path) -> set[str]:
    """Activity diagrams under the specs folder that a change folder cites in backticks, as repository paths."""
    top = Path(root).resolve()
    found: set[str] = set()
    for doc in sorted(change.rglob("*.md")):
        for token in _CITED.findall(read_text_or_none(doc) or ""):
            path = Path(root) / posixpath.normpath(_LINE_SUFFIX.sub("", token.split("#", 1)[0]))
            if not (path.name.endswith("-activity.md") and path.parent.name == DIAGRAMS_DIR
                    and os.path.isfile(path)):
                continue
            resolved = path.resolve()
            if resolved.is_relative_to(specs_root) and resolved.is_relative_to(top):
                found.add(resolved.relative_to(top).as_posix())
    return found


def _added_with(root: Path, rel: str, names: set[str]) -> bool:
    """Whether the commit that added `rel` also touched a change folder with one of these names.

    A root commit, like the boundary of a shallow clone, seems to add every file, so it proves nothing: False."""
    added = _git(root, "log", "--diff-filter=A", "--format=%H %P", "-1", "--", rel)
    commit, *parents = added.stdout.split() or [""]
    if added.returncode != 0 or not commit or not parents:
        return False
    touched = _git(root, "show", "--name-only", "--format=", commit).stdout.splitlines()
    return any(part in names for path in touched for part in Path(path).parts)


def technical_diagram_warnings(root: Path, cfg: Mapping[str, Any]) -> list[str]:
    """Activity diagrams added with an archived technical change and cited by no other change.

    Before 3.1.2 a technical change was made to write activity diagrams; none is required now. A diagram is reported
    only when the commit that added it also touched that change folder, no non-technical change cites it, and its
    `Use case:` names no use case of the capability. The epic's `kind:` label decides a change's kind; without one, or
    when the tracker cannot answer, its `Kind:` line does (proposals before 3.1.2 say capability for every epic)."""
    base, specs_root = changes_dir(root, cfg), specs_dir(root, cfg).resolve()
    archive = base / "archive"
    if not archive.is_dir():
        return []
    open_folders = [p for p in sorted(base.iterdir()) if p.is_dir() and p.name != "archive"]
    archived = [p for p in sorted(archive.iterdir()) if p.is_dir()]
    cited = {change: _cited_diagrams(root, change, specs_root) for change in open_folders + archived}
    if not any(cited[change] for change in archived):
        return []
    if _git(root, "rev-parse", "--is-shallow-repository").stdout.strip() != "false":
        return []  # a shallow clone hides who added a diagram; a git error leaves it unknown too
    kinds = _epic_kinds(root)

    def technical(change: Path) -> bool:
        epic = _EPIC_LINE.search(read_text_or_none(change_file(change, "proposal")) or "")
        label = (kinds or {}).get(epic.group(1)) if epic else None
        return (label or change_kind(change)) == "technical"

    candidates: dict[str, list[str]] = {}
    other: set[str] = set()
    for change, diagrams in cited.items():
        if not diagrams:
            continue
        if not technical(change):
            other |= diagrams
        elif change in archived:
            for rel in diagrams:
                candidates.setdefault(rel, []).append(change.name)
    warnings = []
    for rel, changes in sorted(candidates.items()):
        diagram = Path(root) / rel
        use_cases = diagram.parent.parent / USE_CASES_DIR
        drawn_for = line_values(read_text_or_none(diagram) or "", "Use case")
        if rel in other or any((use_cases / f"{slug}.md").is_file() for slug in drawn_for):
            continue
        names = {name for change in changes for name in (change, _DATED_CHANGE.sub("", change))}
        if _added_with(root, rel, names):
            warnings.append(f"{rel} was added with technical change {', '.join(changes)} and no feature change cites "
                            "it; delete it and its link in spec.md ## Diagrams unless a feature needs it")
    return warnings


def lint_change(root: Path, cfg: Mapping[str, Any], change: Path, *, against: str | None = None) -> list[str]:
    blocks, errors = delta_blocks(root, change)
    path = shown(root, change_file(change, "spec-delta"))
    living = living_blocks(root, cfg)
    in_flight = in_flight_blocks(root, cfg, exclude=change)
    seen: set[str] = set()
    for block in blocks:
        where = f"{path}:{block.start + 1}"
        if block.id in seen:
            errors.append(f"{where}: {block.id} appears twice in the delta")
        seen.add(block.id)
        if not _CAP.match(block.cap):
            errors.append(f"{where}: capability {block.cap!r} must match [a-z][a-z0-9-]*")
        if block.section == "ADDED":
            if block.id in living:
                errors.append(f"{where}: {block.id} already exists in {shown(root, living[block.id][0])}")
            errors += [f"{where}: {message}" for message in lint_block(block)]
        elif block.section in ("MODIFIED", "REMOVED"):
            if block.id not in living:
                added = in_flight.get(block.id, [])
                if not added:
                    errors.append(f"{where}: {block.id} is not in the living spec or an open change")
                elif len(added) > 1:
                    errors.append(f"{where}: {block.id} is added by {' and '.join(c.name for c, _ in added)}; renumber one")
            if block.base is None:
                errors.append(f"{where}: {block.id} needs '<!-- base: <hash> -->' (gin specs hash {block.id})")
            if block.section == "MODIFIED":
                errors += [f"{where}: {message}" for message in lint_block(block)]
            elif not re.search(r"^Reason: \S", block.text, re.MULTILINE):
                errors.append(f"{where}: {block.id} needs a 'Reason: <why>' line")
    if against:
        own = Path(cfg["changes"]) / change.name
        taken = ids_at_ref(root, cfg, against, exclude=own)
        for block in blocks:
            if block.section == "ADDED" and block.id in taken:
                errors.append(f"{path}:{block.start + 1}: {block.id} is already used on {against}")
    kind, kind_errors = _lint_kind(root, change)
    errors += kind_errors
    if kind != "technical":
        errors += _feature_diagram_findings(root, cfg, blocks, against)
    design = change_file(change, "design")
    questions = technical_questions(design, shown(root, design))[1] if design.is_file() else []

    proposal = change_file(change, "proposal")
    if proposal.is_file():
        p_text = proposal.read_text(encoding="utf-8")
        shown_prop = shown(root, proposal)
        found_p_kind = epic_kind.spec_kind_line(p_text)
        p_kind = found_p_kind[0] if found_p_kind else None
        if found_p_kind:
            val, line_no = found_p_kind
            inv = epic_kind.invalid(val)
            if inv:
                errors.append(f"{shown_prop}:{line_no}: {inv}")
        if p_kind == "parity":
            errors += epic_kind.parity_errors(root, p_text, shown_prop)

    return errors + questions + _untracked_citations(root, change) + lint_iterations(root, cfg) + lint_diagrams(root, cfg) + lint_use_cases(root, cfg) + lint_references(root, cfg) + lint_actors(root, cfg)


_CITED = re.compile(r"`([^`\s]+)`")
_LINE_SUFFIX = re.compile(r":\d+(?:-\d+)?$")


def _untracked_citations(root: Path, change: Path) -> list[str]:
    """Repository paths cited in backticks that exist on disk but git does not track, so a clone loses them.

    Missing paths (planned files), paths outside the repository, and the change folder itself are skipped."""
    listed = _git(root, "ls-files", "-z", "--others", "--exclude-standard")
    if listed.returncode != 0:
        return [f"{shown(root, change)}: could not list untracked files: {listed.stderr.strip()}"]
    own = shown(root, change) + "/"
    untracked = [p for p in listed.stdout.split("\0") if p and not p.startswith(own)]
    errors = []
    for doc in sorted(change.rglob("*.md")):
        for number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            for cited in _CITED.findall(line):
                rel = posixpath.normpath(_LINE_SUFFIX.sub("", cited))
                # os.path.exists, not Path.exists: a token too long for a file name is simply not a path.
                if rel == "." or rel.startswith(("/", "..")) or not os.path.exists(root / rel):
                    continue
                if any(p == rel or p.startswith(rel + "/") for p in untracked):
                    errors.append(f"{shown(root, doc)}:{number}: `{cited}` is not tracked by git; commit it")
    return errors


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)


def changed_since(root: Path, ref: str, folder: Path) -> set[str]:
    """Paths under `folder`, relative to `root`, added, modified, or renamed since `ref`, untracked files included."""
    if _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode != 0:
        raise SpecsError(f"cannot resolve {ref}")
    where = shown(root, folder)
    diff = _git(root, "-c", "core.quotepath=off", "diff", "--name-only", "--relative", "--diff-filter=AMR", ref, "--", where)
    untracked = _git(root, "-c", "core.quotepath=off", "ls-files", "--others", "--exclude-standard", "--", where)
    return set(diff.stdout.splitlines() + untracked.stdout.splitlines())


def _ids_in(text: str) -> set[str]:
    return set(_HEADING_LINE.findall(text))


def _local_ids(tree: Path, cfg: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    patterns = (("*/spec.md", cfg["specs"]), ("**/spec-delta.md", cfg["changes"]),
                (f"**/{CHANGE_FILES['spec-delta']}", cfg["changes"]))
    for pattern, base in patterns:
        directory = Path(tree) / base
        if directory.is_dir():
            for path in directory.glob(pattern):
                ids |= _ids_in(path.read_text(encoding="utf-8"))
    return ids


def ids_at_ref(root: Path, cfg: Mapping[str, Any], ref: str, *, exclude: Path | None = None) -> set[str]:
    """Requirement ids in living specs and deltas at a git ref, optionally skipping one change folder."""
    result = _git(root, "grep", "-I", "-E", "^### REQ-", ref, "--", cfg["specs"], cfg["changes"])
    ids: set[str] = set()
    skip = f"{exclude.as_posix()}/" if exclude else None
    for line in result.stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) == 3 and not (skip and parts[1].startswith(skip)):
            ids |= _ids_in(parts[2])
    return ids


def scan_ids(root: Path, cfg: Mapping[str, Any]) -> tuple[set[str], list[str]]:
    """Ids in this tree, every local worktree, and every remote-tracking branch."""
    ids = _local_ids(root, cfg)
    warnings: list[str] = []
    listed = _git(root, "worktree", "list", "--porcelain")
    if listed.returncode != 0:
        return ids, ["not a git repository; scanned this tree only"]
    for line in listed.stdout.splitlines():
        if line.startswith("worktree "):
            ids |= _local_ids(Path(line[len("worktree "):]), cfg)
    if not _git(root, "remote").stdout.strip():
        warnings.append("no git remote; scanned local worktrees only")
        return ids, warnings
    if _git(root, "fetch", "--quiet").returncode != 0:
        warnings.append("git fetch failed; remote branches may be stale")
    refs = _git(root, "for-each-ref", "--format=%(refname)", "refs/remotes").stdout.split()
    for ref in refs:
        if not ref.endswith("/HEAD"):
            ids |= ids_at_ref(root, cfg, ref)
    return ids, warnings


def next_id(root: Path, cfg: Mapping[str, Any], cap: str) -> tuple[str, list[str]]:
    if not _CAP.match(cap):
        raise SpecsError(f"capability {cap!r} must match [a-z][a-z0-9-]*")
    ids, warnings = scan_ids(root, cfg)
    numbers = [int(_FULL_ID.match(item).group(2)) for item in ids if cap_of(item) == cap]
    return f"REQ-{cap.upper()}-{max(numbers, default=0) + 1:03d}", warnings


def new_change(root: Path, cfg: Mapping[str, Any], slug: str, epic: str, title: str = "",
               today: date | None = None, kind: str | None = None) -> Path:
    if not _SLUG.match(slug):
        raise SpecsError(f"slug {slug!r} must match [a-z0-9][a-z0-9-]*")
    change = changes_dir(root, cfg) / f"{epic}-{slug}"
    if change.exists():
        raise SpecsError(f"change folder already exists: {change}")
    values = {"epic": epic, "slug": slug, "title": title or slug.replace("-", " ").capitalize(),
              "date": (today or date.today()).isoformat()}
    if kind is None:
        kind = epic_kind.lookup(root, epic, None)[0]
    texts = {role: render(template_text(root, f"{role}.md"), values) for role in CHANGE_TEMPLATES}
    texts["proposal"] = re.sub(r"^Kind: \S+$", f"Kind: {kind}", texts["proposal"], count=1, flags=re.MULTILINE)
    atomic_write_many({change / CHANGE_FILES[role]: text.encode("utf-8") for role, text in texts.items()}, mode=0o644)
    return change


def requirement_hash(root: Path, cfg: Mapping[str, Any], req_id: str) -> tuple[Block, str, Path | None]:
    """The block, its hash, and the open change that adds it (None for a living block)."""
    living = living_blocks(root, cfg)
    if req_id in living:
        block = living[req_id][1]
        return block, block_hash(block.text), None
    added = in_flight_blocks(root, cfg).get(req_id, [])
    if not added:
        raise SpecsError(f"{req_id} is not in the living spec or an open change")
    if len(added) > 1:
        raise SpecsError(f"{req_id} is added by {' and '.join(c.name for c, _ in added)}; renumber one")
    change, block = added[0]
    return block, block_hash(block.text), change


def _bd(root: Path, argv: Sequence[str]) -> Any:
    from . import task_markdown
    from .configuration import ConfigValidationError
    from .tasks import backend

    try:
        name = backend(root)
    except ConfigValidationError as error:
        raise SpecsError(str(error)) from error
    if name == "markdown":
        value = task_markdown.query(root, argv)
        if value is None:
            raise SpecsError(f"task {' '.join(argv)} failed")
        return value
    executable = tool("bd", root)
    if executable is None:
        raise SpecsError("bd is not installed")
    completed = subprocess.run([executable, *argv], cwd=root, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise SpecsError(f"bd {' '.join(argv)} failed: {completed.stderr.strip()}")
    return json.loads(completed.stdout) if "--json" in argv else completed.stdout


def default_base(root: Path) -> str:
    for branch in ("main", "master"):
        found = _git(root, "merge-base", "HEAD", branch)
        if found.returncode == 0:
            return found.stdout.strip()
    raise SpecsError("cannot find a merge-base with main or master; pass --against")


def test_files(root: Path, cfg: Mapping[str, Any], candidates: Sequence[str]) -> list[str]:
    from .rules import _glob_regex

    patterns = [_glob_regex(pattern) for pattern in cfg["test_globs"]]
    return [path for path in candidates if any(pattern.match(path) for pattern in patterns)]


def renumber(root: Path, cfg: Mapping[str, Any], change: Path, old: str, new: str,
             *, against: str | None = None) -> dict[str, Any]:
    cap_of(old)
    cap_of(new)
    taken, _ = scan_ids(root, cfg)
    if new in taken:
        raise SpecsError(f"{new} is already used")
    base = against or default_base(root)
    changed = _git(root, "diff", "--name-only", f"{base}...HEAD").stdout.split()
    targets = sorted(change.rglob("*.md")) + [Path(root) / path for path in test_files(root, cfg, changed)]
    pattern = re.compile(rf"\b{re.escape(old)}\b")
    writes: dict[Path, bytes] = {}
    for path in targets:
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if pattern.search(text):
                writes[path] = pattern.sub(new, text).encode("utf-8")
    beads = _bd(root, ["list", "--parent", change_epic(change), "--label", f"req:{old}",
                       "--all", "--limit", "0", "--json"])
    atomic_write_many(writes, mode=0o644)
    relabeled = []
    for bead in beads:
        _bd(root, ["update", bead["id"], "--remove-label", f"req:{old}", "--add-label", f"req:{new}"])
        relabeled.append(bead["id"])
    return {"old": old, "new": new, "files": sorted(p.relative_to(root).as_posix() for p in writes), "beads": relabeled}

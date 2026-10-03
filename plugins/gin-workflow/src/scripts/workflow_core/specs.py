"""SDD living specs: requirement blocks, lint, ID allocation, change folders, renumbering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Mapping, Sequence

from .atomic import atomic_write_many
from .configuration import resolve_effective_config

DEFAULT_TEST_GLOBS = ("**/test_*.py", "**/*_test.py", "**/*.test.*", "**/*.spec.*", "tests/**", "__tests__/**")
SDD_DEFAULTS: dict[str, Any] = {
    "layout": "legacy", "specs": "docs/specs", "changes": "docs/changes", "adr": "docs/adr",
    "codebase": "docs/codebase", "spec_review": "chat", "test_globs": list(DEFAULT_TEST_GLOBS),
}
DELTA_SECTIONS = ("ADDED", "MODIFIED", "REMOVED")
CHANGE_TEMPLATES = ("proposal.md", "spec-delta.md", "design.md", "tests.md")
REQ_ID = re.compile(r"\bREQ-([A-Z][A-Z0-9-]*)-(\d{3,})\b")
_FULL_ID = re.compile(r"^REQ-([A-Z][A-Z0-9-]*)-(\d{3,})$")
_HEADING = re.compile(r"^### (REQ-[A-Z][A-Z0-9-]*-\d{3,}): (\S.*)$")
_HEADING_LINE = re.compile(r"^### (REQ-[A-Z][A-Z0-9-]*-\d{3,}):", re.MULTILINE)
_BASE = re.compile(r"^<!-- base: ([0-9a-f]{64}) -->$")
_STATEMENT = re.compile(r"\b(SHALL|MUST)\b")
_CAP = re.compile(r"^[a-z][a-z0-9-]*$")
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
        raise SpecsError("gin-workflow setup is required; run /setup once")
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


def lint_block(block: Block) -> list[str]:
    """Statement and scenario rules for an ADDED, MODIFIED, or living block."""
    errors: list[str] = []
    body = block.text.splitlines()[1:]
    prose = [line for line in body if line.strip() and not line.startswith("#") and not line.startswith("- ")]
    if not any(_STATEMENT.search(line) for line in prose):
        errors.append(f"{block.id}: needs a SHALL or MUST statement")
    scenarios: list[list[str]] = []
    for line in body:
        if line.startswith("#### Scenario:"):
            scenarios.append([])
        elif line.startswith("#### "):
            errors.append(f"{block.id}: only '#### Scenario:' sub-headings are allowed")
        elif scenarios and line.startswith("- "):
            scenarios[-1].append(line[2:].split(" ", 1)[0])
    if not scenarios:
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


def change_epic(change: Path) -> str:
    proposal = change / "proposal.md"
    found = _EPIC_LINE.search(proposal.read_text(encoding="utf-8")) if proposal.is_file() else None
    if not found:
        raise SpecsError(f"{proposal}: missing 'Epic: <id>' line")
    return found.group(1)


def shown(root: Path, path: Path) -> str:
    """Repository-relative path for findings."""
    try:
        return Path(path).relative_to(root).as_posix()
    except ValueError:
        return str(path)


def delta_blocks(root: Path, change: Path) -> tuple[list[Block], list[str]]:
    path = change / "spec-delta.md"
    if not path.is_file():
        return [], [f"{shown(root, path)}: missing spec-delta.md"]
    blocks, malformed = parse_blocks(path.read_text(encoding="utf-8"))
    errors = [f"{shown(root, path)}:{line}: {message}" for line, message in malformed]
    for block in blocks:
        if block.section not in DELTA_SECTIONS:
            errors.append(f"{shown(root, path)}:{block.start + 1}: {block.id} is outside ## ADDED/MODIFIED/REMOVED")
    return blocks, errors


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
    return errors


def lint_change(root: Path, cfg: Mapping[str, Any], change: Path, *, against: str | None = None) -> list[str]:
    blocks, errors = delta_blocks(root, change)
    path = shown(root, change / "spec-delta.md")
    living = living_blocks(root, cfg)
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
                errors.append(f"{where}: {block.id} is not in the living spec")
            if block.base is None:
                errors.append(f"{where}: {block.id} needs '<!-- base: <hash> -->' (gin-workflow specs hash {block.id})")
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
    return errors


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)


def _ids_in(text: str) -> set[str]:
    return set(_HEADING_LINE.findall(text))


def _local_ids(tree: Path, cfg: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    for pattern, base in (("*/spec.md", cfg["specs"]), ("**/spec-delta.md", cfg["changes"])):
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
               today: date | None = None) -> Path:
    if not _SLUG.match(slug):
        raise SpecsError(f"slug {slug!r} must match [a-z0-9][a-z0-9-]*")
    change = changes_dir(root, cfg) / f"{epic}-{slug}"
    if change.exists():
        raise SpecsError(f"change folder already exists: {change}")
    values = {"epic": epic, "slug": slug, "title": title or slug.replace("-", " ").capitalize(),
              "date": (today or date.today()).isoformat()}
    atomic_write_many({change / name: render(template_text(root, name), values).encode("utf-8")
                       for name in CHANGE_TEMPLATES}, mode=0o644)
    return change


def requirement_hash(root: Path, cfg: Mapping[str, Any], req_id: str) -> tuple[Block, str]:
    living = living_blocks(root, cfg)
    if req_id not in living:
        raise SpecsError(f"{req_id} is not in the living spec")
    block = living[req_id][1]
    return block, block_hash(block.text)


def _bd(root: Path, argv: Sequence[str]) -> Any:
    executable = shutil.which("bd")
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
    return {"old": old, "new": new, "files": sorted(str(p.relative_to(root)) for p in writes), "beads": relabeled}

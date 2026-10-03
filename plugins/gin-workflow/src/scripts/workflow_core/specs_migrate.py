"""Move a legacy `.planning` layout into the SDD `docs/` layout; setup and doctor SDD checks."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping

from .atomic import atomic_write_many
from .specs import specs_dir, template_text
from .specs_archive import move

_DESIGN = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)-design\.md$")
_PLAN = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$")
LEGACY_SPECS = ".planning/specs"
LEGACY_CODEBASE = ".planning/codebase"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)


def plan_moves(root: Path, config: Mapping[str, Any], cfg: Mapping[str, Any]) -> dict[str, Any]:
    """Pair `<date>-<slug>-design.md` with `<date>-<slug>.md` by slug; everything else moves alone or is skipped."""
    plans_dir = str((config.get("artifacts") or {}).get("plans", ".planning/plans"))
    archive = Path(cfg["changes"]) / "archive"
    designs: dict[str, list[tuple[str, Path]]] = defaultdict(list)
    plans: dict[str, list[tuple[str, Path]]] = defaultdict(list)
    skipped: list[str] = []
    for kind, directory in (("design", LEGACY_SPECS), ("plan", plans_dir)):
        for path in sorted((Path(root) / directory).glob("*.md")):
            relative = path.relative_to(root)
            design = _DESIGN.match(path.name)
            plan = _PLAN.match(path.name)
            if kind == "design" and design:
                designs[design.group(2)].append((design.group(1), relative))
            elif kind == "plan" and plan and not design:
                plans[plan.group(2)].append((plan.group(1), relative))
            else:
                skipped.append(relative.as_posix())
    moves: list[dict[str, str]] = []
    for slug in sorted(set(designs) | set(plans)):
        if len(designs[slug]) == 1 and len(plans[slug]) == 1:
            day = designs[slug][0][0]
            pairs = [(designs[slug][0][1], "design.md", day), (plans[slug][0][1], "plan.md", day)]
        else:
            pairs = [(path, "design.md", day) for day, path in designs[slug]]
            pairs += [(path, "plan.md", day) for day, path in plans[slug]]
        for source, name, day in pairs:
            moves.append({"from": source.as_posix(), "to": (archive / f"{day}-{slug}" / name).as_posix()})
    if (Path(root) / LEGACY_CODEBASE).is_dir():
        moves.append({"from": LEGACY_CODEBASE, "to": str(cfg["codebase"])})
    return {"moves": moves, "skipped": skipped}


def in_flight_workflows(root: Path) -> list[str]:
    from .events import WorkflowEventStore
    from .lifecycle_cli import _delivery_gate_state, _process_gate_state

    path = Path(root) / ".agent-workflow/runtime/events.jsonl"
    if not path.is_file():
        return []
    store = WorkflowEventStore(path)
    ids = sorted({event.workflow_id for event in store.read_all()})
    return [workflow for workflow in ids
            if _process_gate_state(store, workflow)["plan_approved"]
            and not _delivery_gate_state(Path(root), store, workflow)["shipped"]]


def open_worktrees(root: Path, config: Mapping[str, Any]) -> list[str]:
    base = (Path(root) / str((config.get("artifacts") or {}).get("worktrees", ".planning/worktrees"))).resolve()
    listed = _git(root, "worktree", "list", "--porcelain").stdout.splitlines()
    paths = [Path(line[len("worktree "):]).resolve() for line in listed if line.startswith("worktree ")]
    return [path.as_posix() for path in paths if path.is_relative_to(base)]


def refusals(root: Path, config: Mapping[str, Any], *, force: bool) -> list[str]:
    found: list[str] = []
    if _git(root, "status", "--porcelain").stdout.strip():
        found.append("uncommitted changes; commit or set them aside first")
    if not force:
        found += [f"workflow {item} is approved but not shipped (use --force to migrate anyway)"
                  for item in in_flight_workflows(root)]
        found += [f"worktree open at {item} (use --force to migrate anyway)" for item in open_worktrees(root, config)]
    return found


def migrate(root: Path, config: Mapping[str, Any], cfg: Mapping[str, Any], *, dry_run: bool,
            force: bool) -> dict[str, Any]:
    plan = plan_moves(root, config, cfg)
    blocked = refusals(root, config, force=force)
    readme = specs_dir(root, cfg) / "README.md"
    result = {**plan, "refusals": blocked, "readme": readme.relative_to(root).as_posix(),
              "status": "planned" if dry_run else ("refused" if blocked else "migrated")}
    if dry_run or blocked:
        return result
    for item in plan["moves"]:
        move(root, Path(root) / item["from"], Path(root) / item["to"])
    if not readme.is_file():
        atomic_write_many({readme: template_text(root, "specs-README.md").encode("utf-8")}, mode=0o644)
    from .setup_service import configure

    configure(root, assignments=['artifacts.layout="sdd"'], approve=True)
    return result


def _foreign(directory: Path) -> list[str]:
    """Files that do not belong to an SDD specs folder (README.md and <cap>/spec.md)."""
    if not directory.is_dir():
        return []
    return sorted(path.relative_to(directory).as_posix() for path in directory.rglob("*")
                  if path.is_file() and path.name != "README.md"
                  and not (path.name == "spec.md" and path.parent.parent == directory))


def sdd_report(root: Path, config: Mapping[str, Any], cfg: Mapping[str, Any], *, proposed: bool = False) -> dict[str, Any]:
    """Read-only SDD checks for `setup preset` (proposed layout) and `setup doctor`."""
    report: dict[str, Any] = {"layout": "sdd" if proposed else cfg["layout"]}
    foreign = _foreign(specs_dir(root, cfg))
    if report["layout"] == "sdd" and foreign:
        report["conflict"] = {"path": str(cfg["specs"]), "files": foreign[:10],
                              "suggestion": "set artifacts.specs to another folder, e.g. docs/requirements"}
    plans_dir = str((config.get("artifacts") or {}).get("plans", ".planning/plans"))
    if report["layout"] == "legacy" and any(any((Path(root) / d).glob("*.md")) for d in (LEGACY_SPECS, plans_dir)):
        report["suggestion"] = "run /gin-workflow:migrate-specs to move .planning specs and plans into the SDD layout"
    return report

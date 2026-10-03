"""Requirement blocks as data (`gin-workflow specs reqs`) for tools that build on the specs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .specs import (Block, SpecsError, block_hash, changes_dir, delta_blocks, living_files, parse_blocks, shown)

_STEPS = ("GIVEN", "WHEN", "THEN")


def scenarios(block: Block) -> list[dict[str, Any]]:
    """`#### Scenario:` sections; an `AND` bullet continues the step before it."""
    found: list[dict[str, Any]] = []
    step = ""
    for line in block.text.splitlines()[1:]:
        if line.startswith("#### Scenario:"):
            found.append({"title": line[len("#### Scenario:"):].strip(), "given": [], "when": [], "then": []})
            step = ""
        elif found and line.startswith("- "):
            word, _, rest = line[2:].partition(" ")
            if word in _STEPS:
                step = word.lower()
            if step and (word in _STEPS or word == "AND"):
                found[-1][step].append(rest.strip())
    return found


def _row(root: Path, path: Path, block: Block, change: str | None) -> dict[str, Any]:
    return {"id": block.id, "title": block.title, "capability": block.cap,
            "section": "LIVING" if change is None else block.section, "change": change,
            "hash": block_hash(block.text), "source": f"{shown(root, path)}:{block.start + 1}",
            "scenarios": scenarios(block)}


def open_changes(root: Path, cfg: Mapping[str, Any]) -> list[Path]:
    base = changes_dir(root, cfg)
    if not base.is_dir():
        return []
    return [path for path in sorted(base.iterdir())
            if path.is_dir() and path.name != "archive" and (path / "spec-delta.md").is_file()]


def _delta_rows(root: Path, change: Path) -> list[dict[str, Any]]:
    blocks, errors = delta_blocks(root, change)
    if errors:
        raise SpecsError("; ".join(errors))
    return [_row(root, change / "spec-delta.md", block, change.name) for block in blocks]


def requirements(root: Path, config: Mapping[str, Any], cfg: Mapping[str, Any],
                 change: Path | None = None) -> dict[str, Any]:
    """Living blocks then every open change's delta blocks, or one change's delta blocks only."""
    rows: list[dict[str, Any]] = []
    if cfg["layout"] == "sdd":
        if change is not None:
            rows = _delta_rows(root, change)
        else:
            for path in living_files(root, cfg).values():
                rows += [_row(root, path, block, None) for block in parse_blocks(path.read_text(encoding="utf-8"))[0]]
            for item in open_changes(root, cfg):
                rows += _delta_rows(root, item)
    qa = config.get("qa") if isinstance(config.get("qa"), Mapping) else {}
    return {"layout": cfg["layout"], "qa": dict(qa), "test_globs": list(cfg["test_globs"]), "requirements": rows}

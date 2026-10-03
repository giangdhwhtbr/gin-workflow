"""Merge a change's spec delta into the living spec, then archive the change folder."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import shutil
import subprocess
from typing import Any, Mapping

from .atomic import atomic_write_many
from .specs import (Block, SpecsError, block_hash, delta_blocks, lint_change, living_blocks, parse_blocks,
                    render, specs_dir, template_text, _BASE)


class ArchiveConflict(ValueError):
    """The delta cannot be applied; nothing was written (exit 1)."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _clean(block: Block) -> list[str]:
    return [line for line in block.text.splitlines() if not _BASE.match(line.strip())]


def _apply(lines: list[str], edits: Mapping[str, Block | None]) -> list[str]:
    """Replace (Block) or drop (None) living blocks by id, bottom-up so indexes stay valid."""
    blocks = sorted(parse_blocks("\n".join(lines))[0], key=lambda block: block.start, reverse=True)
    for block in blocks:
        if block.id in edits:
            replacement = edits[block.id]
            lines[block.start:block.end] = [] if replacement is None else [*_clean(replacement), ""]
    return lines


def _append(lines: list[str], added: list[Block]) -> list[str]:
    while lines and not lines[-1].strip():
        lines.pop()
    for block in added:
        lines += ["", *_clean(block)]
    return lines


def move(root: Path, source: Path, target: Path) -> None:
    """`git mv` keeps history; untracked sources fall back to a plain move."""
    target.parent.mkdir(parents=True, exist_ok=True)
    moved = subprocess.run(["git", "mv", str(source), str(target)], cwd=root, capture_output=True, check=False)
    if moved.returncode != 0:
        shutil.move(str(source), str(target))


def archive(root: Path, cfg: Mapping[str, Any], change: Path, *, today: date | None = None) -> dict[str, Any]:
    errors = lint_change(root, cfg, change)
    blocks, _ = delta_blocks(root, change)
    living = living_blocks(root, cfg)
    for block in blocks:
        if block.section in ("MODIFIED", "REMOVED") and block.id in living:
            current = block_hash(living[block.id][1].text)
            if block.base != current:
                errors.append(f"{block.id}: living block changed since the delta was written "
                              f"(base {str(block.base)[:12]}, now {current[:12]}); update the delta")
    if errors:
        raise ArchiveConflict(errors)
    target = Path(cfg["changes"]) / "archive" / f"{(today or date.today()).isoformat()}-{change.name}"
    if (Path(root) / target).exists():
        raise SpecsError(f"archive folder already exists: {target}")

    base = specs_dir(root, cfg)
    texts: dict[str, list[str]] = {}
    new_caps: list[str] = []
    for block in blocks:
        path = base / block.cap / "spec.md"
        if block.cap not in texts:
            if path.is_file():
                texts[block.cap] = path.read_text(encoding="utf-8").splitlines()
            else:
                title = block.cap.replace("-", " ").capitalize()
                texts[block.cap] = render(template_text(root, "spec.md"), {"capability": title}).splitlines()
                new_caps.append(block.cap)
    for cap, lines in texts.items():
        mine = [block for block in blocks if block.cap == cap]
        edits = {b.id: (b if b.section == "MODIFIED" else None) for b in mine if b.section != "ADDED"}
        texts[cap] = _append(_apply(lines, edits), [b for b in mine if b.section == "ADDED"])
    writes = {base / cap / "spec.md": ("\n".join(lines).rstrip() + "\n").encode("utf-8") for cap, lines in texts.items()}
    if new_caps:
        readme = base / "README.md"
        text = readme.read_text(encoding="utf-8") if readme.is_file() else template_text(root, "specs-README.md")
        lines = text.rstrip().splitlines() + [f"- [{cap}]({cap}/spec.md)" for cap in new_caps]
        writes[readme] = ("\n".join(lines) + "\n").encode("utf-8")
    atomic_write_many(writes, mode=0o644)
    move(root, change, Path(root) / target)
    return {"change": change.name, "archived_to": target.as_posix(),
            "specs": sorted(str(path.relative_to(root)) for path in writes),
            "added": [b.id for b in blocks if b.section == "ADDED"],
            "modified": [b.id for b in blocks if b.section == "MODIFIED"],
            "removed": [b.id for b in blocks if b.section == "REMOVED"]}

"""Measure instruction size loaded per lifecycle stage (chars; ~4 chars ≈ 1 token)."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

STAGES = ("discuss", "plan", "orchestrate", "execute", "verify", "ship", "review", "workflow", "progress", "quick")

_REFERENCE = re.compile(r"(?<![\w.-])((?:\.\./)*references/[\w./-]+\.md)")
_LINK = re.compile(r"\]\((?:file://)?([^)\s#]+\.md)\)")
_NAMED_SKILL = re.compile(r"`([\w-]+)`")
_DELEGATION_LINE = re.compile(r"methodolog")
_COMMAND_DELEGATION_LINE = re.compile(r"methodolog|\bskill\b")
_DESCRIPTION = re.compile(r"^description:\s*(.*)$", re.MULTILINE)
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def _linked(src: Path, owner: Path) -> list[Path]:
    text = owner.read_text(encoding="utf-8")
    found = []
    for relative in [*_REFERENCE.findall(text), *_LINK.findall(text)]:
        for base in (owner.parent, src):
            candidate = (base / relative).resolve()
            if candidate.is_file() and candidate.is_relative_to(src.resolve()):
                found.append(candidate)
                break
    return found


def _named_skills(src: Path, owner: Path) -> list[Path]:
    delegation = _COMMAND_DELEGATION_LINE if owner.parent.name == "commands" else _DELEGATION_LINE
    lines = owner.read_text(encoding="utf-8").splitlines()
    names = [name for line in lines if delegation.search(line) for name in _NAMED_SKILL.findall(line)]
    return [p.resolve() for p in (src / f"skills/{name}/SKILL.md" for name in names) if p.is_file()]


def stage_chain(src: Path, stage: str) -> list[Path]:
    """Command + stage skill, their links, and the skills they delegate to (plus those skills' links).

    A command delegates on any line naming a skill; a stage skill delegates only on a methodology line.

    Skills that are only named for conditional use (debugging on failure, review as a separate step)
    load on demand and are budgeted on their own.
    """
    src = Path(src)
    roots = [p.resolve() for p in (src / f"commands/{stage}.md", src / f"skills/{stage}/SKILL.md") if p.is_file()]
    chain: dict[Path, None] = dict.fromkeys(roots)
    delegated: list[Path] = []
    for owner in roots:
        for linked in _linked(src, owner):
            chain.setdefault(linked, None)
        for skill in _named_skills(src, owner):
            if skill not in chain:
                chain[skill] = None
                delegated.append(skill)
    for owner in delegated:
        for linked in _linked(src, owner):
            chain.setdefault(linked, None)
    return list(chain)


def stage_chars(src: Path, stage: str) -> int:
    return sum(len(p.read_text(encoding="utf-8")) for p in stage_chain(src, stage))


def description_chars(src: Path) -> int:
    src = Path(src)
    files = [*src.glob("skills/*/SKILL.md"), *src.glob("agents/*.md"), *src.glob("commands/*.md")]
    total = 0
    for path in files:
        header = _FRONTMATTER.match(path.read_text(encoding="utf-8"))
        match = _DESCRIPTION.search(header.group(1)) if header else None
        total += len(match.group(1).strip()) if match else 0
    return total


def report(src: Path) -> str:
    lines = ["| Stage | Chars |", "|---|---|"]
    lines += [f"| {stage} | {stage_chars(src, stage):,} |" for stage in STAGES]
    lines.append(f"| descriptions | {description_chars(src):,} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="workflow_core.budget")
    parser.add_argument("--report", action="store_true", required=True)
    parser.add_argument("--src", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    print(report(args.src))
    return 0


if __name__ == "__main__":
    sys.exit(main())

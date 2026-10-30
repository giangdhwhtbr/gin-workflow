"""`gin-workflow docs check`: mechanical rules for Markdown pages. Exit 0 ok, 1 findings, 2 usage error."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Iterator, Sequence

from . import specs

STYLE_RULES = (("dash", re.compile("[–—]")),
               ("bold-label item", re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\*\*")),
               ("emoji", re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⭕️]")),
               ("numbered heading", re.compile(r"^#{1,6}\s+\d")))
PLACEHOLDER = re.compile(r"\{\{[^}]*\}\}|\b(?:TBD|TODO)\b")
INLINE_CODE = re.compile(r"`[^`]*`")
LINK = re.compile(r"\]\(([^)\s]+)\)")


def _prose(text: str) -> Iterator[tuple[int, str]]:
    """Numbered lines outside fenced code blocks."""
    fenced = False
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            yield number, line


def style_violations(text: str) -> list[str]:
    """Mechanical docs-pack rules outside fenced code blocks, as '<line>: <rule>'."""
    return [f"{number}: {name}" for number, line in _prose(text) for name, pattern in STYLE_RULES
            if pattern.search(line)]


def required_sections(repository: Path, template: str) -> list[str]:
    """Literal '## ' headings of a template; a heading with a placeholder varies per page and is skipped."""
    return [line.rstrip() for line in specs.template_text(repository, template).splitlines()
            if line.startswith("## ") and "{{" not in line]


def page_findings(page: Path, text: str, required: Sequence[str] = ()) -> list[str]:
    """Every rule for one page, ordered by line; missing sections last."""
    found = []
    for number, line in _prose(text):
        prose = INLINE_CODE.sub("", line)
        found += [f"{page}:{number}: {name}" for name, pattern in STYLE_RULES if pattern.search(line)]
        if PLACEHOLDER.search(prose):
            found.append(f"{page}:{number}: placeholder")
        for target in LINK.findall(prose):
            path = target.split("#", 1)[0]
            if path and not re.match(r"[a-z]+:", path) and not (page.parent / path).exists():
                found.append(f"{page}:{number}: dead link")
    lines = {line.rstrip() for line in text.splitlines()}
    return found + [f"{page}: missing section: {heading}" for heading in required if heading not in lines]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gin-workflow docs")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("files", nargs="+", type=Path)
    check.add_argument("--template")
    check.add_argument("--repository", type=Path, default=Path.cwd())
    check.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(arguments)
    missing = [str(path) for path in args.files if not path.is_file()]
    if missing:
        print(f"no such file: {', '.join(missing)}", file=sys.stderr)
        return 2
    try:
        required = required_sections(args.repository.resolve(), args.template) if args.template else []
    except specs.SpecsError as error:
        print(error, file=sys.stderr)
        return 2
    found = [item for path in args.files
             for item in page_findings(path, path.read_text(encoding="utf-8"), required)]
    if args.format == "json":
        print(json.dumps({"status": "findings" if found else "ok", "findings": found}, indent=2, sort_keys=True))
    else:
        print("\n".join(found) if found else "ok")
    return 1 if found else 0

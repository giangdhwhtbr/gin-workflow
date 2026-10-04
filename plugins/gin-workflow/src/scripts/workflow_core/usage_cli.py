"""`gin-workflow usage` command line: exit 0 ok, 2 usage or a real error (`--best-effort` turns errors into warnings)."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from . import usage


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from error


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repository", type=Path, default=Path.cwd())
    common.add_argument("--format", choices=("text", "json"), default="text")
    parser = argparse.ArgumentParser(prog="gin-workflow usage")
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("collect", parents=[common])
    item.add_argument("--bead", required=True)
    item.add_argument("--best-effort", action="store_true")
    item = sub.add_parser("report", parents=[common])
    scope = item.add_mutually_exclusive_group()
    scope.add_argument("--bead")
    scope.add_argument("--epic")
    scope.add_argument("--since", type=_date)
    return parser


def _money(value: Any) -> str:
    return "-" if value is None else f"{value:g}"


def _report_text(out: dict[str, Any]) -> str:
    lines = [f"{entry['bead']}  {_money(entry.get('cost'))}  {entry.get('title', '')}" for entry in out["beads"]]
    lines.append(f"total: {_money(out['totals']['cost'])}")
    for name, values in sorted(out["totals"]["models"].items()):
        tokens = " ".join(f"{key}={values[key]}" for key in ("input", "output", "cache_read", "cache_write"))
        lines.append(f"model {name}: {tokens} cost={_money(values['cost'])}")
    for name, values in sorted(out["totals"]["stages"].items()):
        lines.append(f"stage {name}: tokens={values['tokens']} cost={_money(values['cost'])}")
    if out["unpriced"]:
        lines.append(f"unpriced: {', '.join(out['unpriced'])}")
    if out["unattributed"]["tokens"]:
        lines.append(f"unattributed: tokens={out['unattributed']['tokens']} "
                     f"cost={_money(out['unattributed']['cost'])}")
    if out["not_collected"]:
        lines.append(f"not collected: {', '.join(out['not_collected'])}")
    return "\n".join(lines)


def main(arguments: Sequence[str]) -> int:
    args = _parser().parse_args(list(arguments))
    root = args.repository.resolve()
    try:
        if args.command == "collect":
            out = usage.collect(root, args.bead)
            text = f"{args.bead}: cost {_money(out['cost'])}; sources " + \
                ", ".join(f"{name} {status}" for name, status in sorted(out["sources"].items()))
        else:
            out = usage.report(root, bead=args.bead, epic=args.epic, since=args.since)
            text = _report_text(out)
    except usage.UsageError as error:
        if args.command == "collect" and args.best_effort:
            print(f"warning: usage not collected for {args.bead}: {error}", file=sys.stderr)
            return 0
        print(f"error: {error}", file=sys.stderr)
        return 2
    except Exception as error:  # never block closing a bead
        if args.command == "collect" and args.best_effort:
            print(f"warning: usage not collected for {args.bead}: {error}", file=sys.stderr)
            return 0
        raise
    print(json.dumps(out, indent=2, sort_keys=True) if args.format == "json" else text)
    return 0

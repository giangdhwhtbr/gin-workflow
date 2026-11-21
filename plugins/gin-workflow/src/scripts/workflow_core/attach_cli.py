"""`gin attach`: images on beads. Exit 0 ok, 1 a file refused, 2 usage, bead, tracker, configuration or store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from . import attachments, workspace
from .attach_store import StoreError
from .models import DependencyUnavailableError


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repository", type=Path, default=None)
    parser = argparse.ArgumentParser(prog="gin attach")
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("add", parents=[common])
    item.add_argument("bead")
    item.add_argument("files", nargs="+", type=Path, metavar="file")
    item.add_argument("--caption")
    item.add_argument("--case")
    item.add_argument("--step", type=int)
    item.add_argument("--format", choices=("text", "json"), default="text")
    item = sub.add_parser("list", parents=[common])
    item.add_argument("bead")
    item.add_argument("--format", choices=("text", "json"), default="text")
    item = sub.add_parser("fetch", parents=[common])
    item.add_argument("--bead")
    item.add_argument("--out", type=Path)
    sub.add_parser("push", parents=[common])
    return parser


def _emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _run(args: argparse.Namespace) -> int:
    repo = args.repository
    if args.command == "add":
        added = attachments.add(repo, args.bead, args.files, caption=args.caption, case=args.case, step=args.step)
        if args.format == "json":
            _emit({"bead": args.bead, "entries": added.entries, "refused": added.refused, "warning": added.warning})
        else:
            for entry in added.entries:
                print(attachments.reference(entry))
        for item in added.refused:
            print(f"refused {item['name']}: {item['reason']}", file=sys.stderr)
        if added.warning:
            print(f"warning: {added.warning}", file=sys.stderr)
        return 1 if added.refused else 0
    if args.command == "list":
        found = attachments.list_entries(repo, args.bead)
        if args.format == "json":
            _emit({"bead": args.bead, "entries": found})
        else:
            for entry in found:
                note = " (pruned)" if entry.get("pruned_at") else ""
                print(f"{entry['sha256']}  {entry['mime']}  {entry['bytes']}  {entry['name']}{note}")
        return 0
    if args.command == "fetch":
        if bool(args.bead) != bool(args.out):
            print("error: --bead and --out go together", file=sys.stderr)
            return 2
        for path in attachments.fetch(repo, bead=args.bead, out=args.out):
            print(path)
        return 0
    warning = attachments.push(repo)
    if warning:
        print(f"error: {warning}", file=sys.stderr)
        return 2
    return 0


def main(argv: Sequence[str]) -> int:
    try:
        args = _parser().parse_args(list(argv))
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    args.repository = workspace.repository_root(args.repository)
    try:
        return _run(args)
    except (attachments.AttachmentError, StoreError, DependencyUnavailableError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

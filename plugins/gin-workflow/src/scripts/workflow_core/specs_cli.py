"""`gin-workflow specs` command line: exit 0 ok, 1 content findings, 2 usage or configuration error."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from . import specs


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repository", type=Path, default=Path.cwd())
    common.add_argument("--format", choices=("text", "json"), default="text")
    parser = argparse.ArgumentParser(prog="gin-workflow specs")
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("new", parents=[common])
    item.add_argument("slug")
    item.add_argument("--epic", required=True)
    item.add_argument("--title", default="")
    sub.add_parser("next-id", parents=[common]).add_argument("cap")
    item = sub.add_parser("lint", parents=[common])
    item.add_argument("--change")
    item.add_argument("--against")
    sub.add_parser("hash", parents=[common]).add_argument("req_id")
    sub.add_parser("template", parents=[common]).add_argument("name")
    item = sub.add_parser("renumber", parents=[common])
    item.add_argument("old")
    item.add_argument("new")
    item.add_argument("--change", required=True)
    item.add_argument("--against")
    sub.add_parser("archive", parents=[common]).add_argument("--change", required=True)
    sub.add_parser("trace", parents=[common]).add_argument("--change", required=True)
    sub.add_parser("status", parents=[common]).add_argument("--change", required=True)
    item = sub.add_parser("migrate", parents=[common])
    item.add_argument("--dry-run", action="store_true")
    item.add_argument("--force", action="store_true")
    return parser


def _emit(payload: dict[str, Any], output_format: str, text: str) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True) if output_format == "json" else text)


def _findings(errors: list[str], output_format: str, ok: str) -> int:
    _emit({"status": "findings" if errors else "ok", "findings": errors}, output_format,
          "\n".join(errors) if errors else ok)
    return 1 if errors else 0


def _run(args: argparse.Namespace) -> int:
    root = args.repository.resolve()
    if args.command == "template":
        text = specs.template_text(root, args.name)
        _emit({"name": args.name, "text": text}, args.format, text.rstrip("\n"))
        return 0
    config = specs.load_config(root)
    cfg = specs.sdd_config(config)
    if args.command == "migrate":
        from .specs_migrate import migrate

        specs.require_layout(cfg, "legacy")
        result = migrate(root, config, cfg, dry_run=args.dry_run, force=args.force)
        lines = [f"{m['from']} -> {m['to']}" for m in result["moves"]]
        lines += [f"skipped: {item}" for item in result["skipped"]] + [f"refused: {r}" for r in result["refusals"]]
        _emit(result, args.format, "\n".join([f"status: {result['status']}", *lines]))
        return 1 if result["status"] == "refused" else 0
    specs.require_layout(cfg, "sdd")
    if args.command == "new":
        change = specs.new_change(root, cfg, args.slug, args.epic, args.title)
        relative = change.relative_to(root).as_posix()
        _emit({"change": change.name, "path": relative}, args.format, relative)
        return 0
    if args.command == "next-id":
        req_id, warnings = specs.next_id(root, cfg, args.cap)
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        _emit({"id": req_id, "warnings": warnings}, args.format, req_id)
        return 0
    if args.command == "lint":
        if args.change:
            errors = specs.lint_change(root, cfg, specs.find_change(root, cfg, args.change), against=args.against)
        else:
            errors = specs.lint_living(root, cfg)
        return _findings(errors, args.format, "ok")
    if args.command == "hash":
        block, digest = specs.requirement_hash(root, cfg, args.req_id)
        _emit({"id": block.id, "hash": digest}, args.format, f"<!-- base: {digest} -->")
        return 0
    change = specs.find_change(root, cfg, args.change)
    if args.command == "renumber":
        result = specs.renumber(root, cfg, change, args.old, args.new, against=args.against)
        _emit(result, args.format, "\n".join([f"{args.old} -> {args.new}", *result["files"], *result["beads"]]))
        return 0
    if args.command == "archive":
        from .specs_archive import ArchiveConflict, archive

        try:
            result = archive(root, cfg, change)
        except ArchiveConflict as conflict:
            return _findings(conflict.errors, args.format, "ok")
        _emit(result, args.format, f"archived to {result['archived_to']}; updated {', '.join(result['specs'])}")
        return 0
    from .specs_trace import status, trace

    if args.command == "trace":
        result = trace(root, cfg, change)
        lines = [f"{row['id']}: {row['status']} {' '.join(row['sources'])}".rstrip() for row in result["requirements"]]
        _emit(result, args.format, "\n".join(lines))
        return 1 if result["missing"] else 0
    result = status(root, change)
    _emit(result, args.format, " ".join(str(result.get(key, "")) for key in ("status", "url", "merge_commit")).strip())
    return 0


def main(arguments: Sequence[str]) -> int:
    try:
        args = _parser().parse_args(list(arguments))
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    try:
        return _run(args)
    except (specs.SpecsError, ValueError) as error:
        print(f"specs error: {error}", file=sys.stderr)
        return 2

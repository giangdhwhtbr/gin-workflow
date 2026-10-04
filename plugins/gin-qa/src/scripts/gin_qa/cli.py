"""`gin-qa cases` and `gin-qa e2e`: exit 0 ok, 1 findings, 2 usage or environment error."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from . import cases as tc
from . import e2e
from .reqs import Effective, QaError, resolve, specs_reqs

VERSION = "0.1"


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repository", type=Path, default=Path.cwd())
    common.add_argument("--format", choices=("text", "json"), default="text")
    parser = argparse.ArgumentParser(prog="gin-qa cases")
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("plan", parents=[common])
    scope = item.add_mutually_exclusive_group(required=True)
    scope.add_argument("capability", nargs="?")
    scope.add_argument("--change")
    sub.add_parser("next-id", parents=[common]).add_argument("capability")
    sub.add_parser("pin", parents=[common]).add_argument("ids", nargs="+")
    sub.add_parser("check", parents=[common]).add_argument("--change")
    sub.add_parser("export", parents=[common])
    return parser


def _e2e_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repository", type=Path, default=Path.cwd())
    common.add_argument("--format", choices=("text", "json"), default="text")
    parser = argparse.ArgumentParser(prog="gin-qa e2e")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", parents=[common])
    sub.add_parser("plan", parents=[common]).add_argument("capability", nargs="?")
    sub.add_parser("pin", parents=[common]).add_argument("ids", nargs="+")
    sub.add_parser("check", parents=[common])
    return parser


def _emit(payload: dict[str, Any], output_format: str, text: str) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True) if output_format == "json" else text)


def _scope(root: Path, eff: Effective, capability: str | None, change: str | None) -> tuple[set[str], set[str]]:
    """REQ-IDs to cover and REQ-IDs removed, for a capability, a change, or everything."""
    if change:
        rows = specs_reqs(root, change)["requirements"]
        return ({row["id"] for row in rows if row["section"] != "REMOVED"},
                {row["id"] for row in rows if row["section"] == "REMOVED"})
    if capability:
        return ({req for req, row in eff.reqs.items() if row["capability"] == capability},
                {req for req in eff.removed if req.split("-")[1:-1] == capability.upper().split("-")})
    return set(eff.reqs), set(eff.removed)


def _work(root: Path, eff: Effective, cases: list[tc.Case], capability: str | None,
          change: str | None) -> dict[str, list[dict[str, Any]]]:
    wanted, removed = _scope(root, eff, capability, change)
    covered = {req for case in cases for req, _ in case.reqs}
    missing = [{"req": req, "title": row["title"], "capability": row["capability"], "hash8": row["hash"][:8],
                "source": row["source"], "scenarios": row["scenarios"]}
               for req, row in eff.reqs.items() if req in wanted and req not in covered]
    stale: list[dict[str, Any]] = []
    obsolete: list[dict[str, Any]] = []
    for case in cases:
        for req, pinned in case.reqs:
            everything = not capability and not change
            if not (everything or req in wanted or req in removed or (capability and case.cap == capability)):
                continue
            where = {"tc": case.id, "file": str(case.path), "line": case.line, "req": req}
            if req in eff.reqs:
                current = eff.reqs[req]["hash"][:8]
                if pinned != current:
                    stale.append({**where, "pinned": pinned, "current": current, "source": eff.reqs[req]["source"]})
            else:
                reason = f"removed by {eff.removed[req]}" if req in eff.removed else "does not exist"
                obsolete.append({**where, "reason": reason})
    return {"missing": missing, "stale": stale, "obsolete": obsolete}


def _check(root: Path, eff: Effective, change: str | None) -> list[str]:
    cases, errors = tc.load(root, eff.cases_dir)
    probe = f"{eff.cases_dir.rstrip('/')}/probe.md"
    errors += [f"{eff.cases_dir}: matches artifacts.test_globs pattern {pattern!r}; test cases would count as "
               "executed tests in specs trace" for pattern in eff.test_globs if tc.glob_regex(pattern).match(probe)]
    needed = "REQ" if eff.layout == "sdd" else "Source"
    errors += [f"{case.path}:{case.line}: {case.id}: needs a {needed}: field" for case in cases
               if needed not in case.fields]
    if eff.layout != "sdd":
        return errors
    errors += eff.conflicts
    work = _work(root, eff, cases, None, change)
    errors += [f"{row['source']}: {row['req']} has no test case" for row in work["missing"]]
    errors += [f"{row['file']}:{row['line']}: {row['tc']}: {row['req']} changed (pinned {row['pinned']}, now "
               f"{row['current']}); update the case, then `gin-qa cases pin {row['tc']}`" for row in work["stale"]]
    errors += [f"{row['file']}:{row['line']}: {row['tc']}: {row['req']} {row['reason']}" for row in work["obsolete"]]
    return errors


def _pin(root: Path, eff: Effective, ids: list[str]) -> list[str]:
    cases, _ = tc.load(root, eff.cases_dir)
    by_id = {case.id: case for case in cases}
    errors: list[str] = []
    edits: dict[Path, dict[int, str]] = {}
    for case_id in ids:
        case = by_id.get(case_id)
        if case is None:
            errors.append(f"{case_id}: no such test case")
            continue
        if not case.reqs:
            errors.append(f"{case.path}:{case.line}: {case_id}: has no valid REQ entries")
            continue
        unknown = [req for req, _ in case.reqs if req not in eff.reqs]
        if unknown:
            errors.append(f"{case.path}:{case.line}: {case_id}: {', '.join(unknown)} not found; delete or fix the case")
            continue
        line = "REQ: " + ", ".join(f"{req}@{eff.reqs[req]['hash'][:8]}" for req, _ in case.reqs)
        edits.setdefault(root / case.path, {})[case.field_lines["REQ"]] = line
    if errors:
        return errors
    for path, lines in edits.items():
        text = path.read_text(encoding="utf-8").split("\n")
        for number, line in lines.items():
            text[number - 1] = line
        path.write_text("\n".join(text), encoding="utf-8")
    return []


def _findings(errors: list[str], output_format: str, ok: str) -> int:
    _emit({"status": "findings" if errors else "ok", "findings": errors}, output_format,
          "\n".join(errors) if errors else ok)
    return 1 if errors else 0


def _run(args: argparse.Namespace) -> int:
    root = args.repository.resolve()
    eff = resolve(specs_reqs(root))
    if args.command == "next-id":
        found = tc.next_id(root, eff.cases_dir, args.capability)
        _emit({"id": found}, args.format, found)
        return 0
    if args.command == "check":
        return _findings(_check(root, eff, args.change), args.format, "ok")
    if args.command == "pin":
        return _findings(_pin(root, eff, args.ids), args.format, f"pinned {' '.join(args.ids)}")
    cases, _ = tc.load(root, eff.cases_dir)
    if args.command == "export":
        rows = [tc.as_dict(case) for case in cases]
        _emit({"cases": rows}, args.format, "\n".join(f"{row['id']} {row['title']}" for row in rows))
        return 0
    work = (_work(root, eff, cases, args.capability, args.change) if eff.layout == "sdd"
            else {"missing": [], "stale": [], "obsolete": []})
    payload = {"layout": eff.layout, "cases": eff.cases_dir, "guidelines": eff.guidelines, **work}
    lines = [f"missing {row['req']} {row['title']}" for row in work["missing"]]
    lines += [f"stale {row['tc']} ({row['req']})" for row in work["stale"]]
    lines += [f"obsolete {row['tc']} ({row['req']} {row['reason']})" for row in work["obsolete"]]
    _emit(payload, args.format, "\n".join(lines) or "nothing to do")
    return 0


def _run_e2e(args: argparse.Namespace) -> int:
    root = args.repository.resolve()
    eff = resolve(specs_reqs(root))
    if args.command == "init":
        done = e2e.init(root, eff)
        _emit({"done": done}, args.format, "\n".join(done) or "already initialized")
        return 0
    if args.command == "plan":
        work = e2e.plan(root, eff, args.capability)
        lines = [f"{kind} {row['tc']} {row['spec']}" for kind in ("missing", "stale", "orphan") for row in work[kind]]
        _emit({"e2e": eff.e2e_dir, "guidelines": eff.guidelines, **work}, args.format,
              "\n".join(lines) or "nothing to do")
        return 0
    if args.command == "pin":
        return _findings(e2e.pin(root, eff, args.ids), args.format, f"pinned {' '.join(args.ids)}")
    return _findings(e2e.check_specs(root, eff), args.format, "ok")


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--version"]:
        print(f"gin-qa {VERSION}")
        return 0
    if argv[:1] not in (["cases"], ["e2e"]):
        print("usage: gin-qa cases {plan,next-id,pin,check,export} ...\n"
              "       gin-qa e2e {init,plan,pin,check} ...", file=sys.stderr)
        return 2
    try:
        args = (_parser() if argv[0] == "cases" else _e2e_parser()).parse_args(argv[1:])
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    try:
        return _run(args) if argv[0] == "cases" else _run_e2e(args)
    except (QaError, ValueError, OSError) as error:
        print(f"gin-qa error: {error}", file=sys.stderr)
        return 2

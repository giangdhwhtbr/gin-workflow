"""`gin-qa cases`, `gin-qa e2e`, `gin-qa tests`, and `gin-qa report`: exit 0 ok, 1 findings, 2 usage or environment error."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from . import cases as tc
from . import bugs, e2e, report, tests
from .reqs import Effective, QaError, resolve, specs_reqs

VERSION = "0.9"


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
    item = sub.add_parser("result", parents=[common])
    item.add_argument("id")
    item.add_argument("status")
    item.add_argument("--run")
    item.add_argument("--bug")
    item = sub.add_parser("bug", parents=[common])
    item.add_argument("id")
    item.add_argument("--actual", required=True)
    item.add_argument("--evidence", action="append", default=[])
    item.add_argument("--external-ref")
    item.add_argument("--discovered-from")
    item.add_argument("--run")
    sub.add_parser("split", parents=[common]).add_argument("capability")
    sub.add_parser("check", parents=[common]).add_argument("--change")
    sub.add_parser("export", parents=[common])
    return parser


def _e2e_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repository", type=Path, default=Path.cwd())
    common.add_argument("--format", choices=("text", "json"), default="text")
    parser = argparse.ArgumentParser(prog="gin-qa e2e")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", parents=[common]).add_argument("--base-url")
    sub.add_parser("plan", parents=[common]).add_argument("capability", nargs="?")
    sub.add_parser("pin", parents=[common]).add_argument("ids", nargs="+")
    sub.add_parser("run", parents=[common]).add_argument("targets", nargs="*", metavar="TC-ID|capability")
    sub.add_parser("check", parents=[common]).add_argument("--run", dest="folder")
    sub.add_parser("export", parents=[common]).add_argument("--run", dest="folder", required=True)
    return parser


def _tests_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repository", type=Path, default=Path.cwd())
    common.add_argument("--format", choices=("text", "json"), default="text")
    parser = argparse.ArgumentParser(prog="gin-qa tests")
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("plan", parents=[common])
    item.add_argument("capability", nargs="?")
    item.add_argument("--type", dest="kind")
    sub.add_parser("pin", parents=[common]).add_argument("ids", nargs="+")
    sub.add_parser("check", parents=[common]).add_argument("--type", dest="kind")
    item = sub.add_parser("run", parents=[common])
    item.add_argument("--type", dest="kind", required=True)
    item.add_argument("targets", nargs="*", metavar="TC-ID|capability")
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
    types, problems = tc.declared_types(root, eff.guidelines)
    errors += problems
    if types is not None:
        errors += [f"{case.path}:{case.line}: {case.id}: type '{case.type}' is not listed under "
                   f"'{tc.TYPES_SECTION}' in {eff.guidelines}" for case in cases if case.type and case.type not in types]
    files = [f"{eff.cases_dir}/probe.md", *(path.relative_to(root).as_posix()
                                            for path in tc.case_files(root, eff.cases_dir))]
    for pattern in eff.test_globs:
        hit = next((path for path in files if tc.glob_regex(pattern).match(path)), None)
        if hit is not None:
            shown = eff.cases_dir if hit == files[0] else hit
            errors.append(f"{shown}: matches artifacts.test_globs pattern {pattern!r}; test cases would count as "
                          "executed tests in specs trace")
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
        value = ", ".join(f"{req}@{eff.reqs[req]['hash'][:8]}" for req, _ in case.reqs)
        edits.setdefault(root / case.path, {})[case.field_lines["REQ"]] = value
    if errors:
        return errors
    for path, values in edits.items():
        text = path.read_text(encoding="utf-8").split("\n")
        for number, value in values.items():
            text[number - 1] = tc.field_line(text[number - 1], "REQ", value)
        tc.write_atomic(path, "\n".join(text))
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
    if args.command == "result":
        row = tc.record_result(root, eff.cases_dir, args.id, args.status, args.run, args.bug)
        _emit(row, args.format, f"{row['tc']} {row['result']}")
        return 0
    if args.command == "bug":
        row = bugs.file_bug(root, eff, args.id, args.actual, args.evidence, external_ref=args.external_ref,
                            discovered_from=args.discovered_from, run=args.run)
        _emit(row, args.format, f"{row['tc']} failed {row['bug']}")
        return 0
    if args.command == "split":
        written, errors = tc.split(root, eff.cases_dir, args.capability)
        if errors:
            return _findings(errors, args.format, "")
        _emit({"written": written}, args.format, "\n".join(written))
        return 0
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
        done = e2e.init(root, eff, args.base_url)
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
    if args.command == "check":
        errors = e2e.check_run(root, eff, args.folder) if args.folder else e2e.check_specs(root, eff)
        return _findings(errors, args.format, "ok")
    if args.command == "export":
        payload = e2e.export(root, eff, args.folder)
        _emit(payload, args.format, "\n".join(
            f"{row['id']} {' '.join(result['status'] for result in row['results']) or 'not run'}"
            for row in payload["cases"]))
        return 0
    folder, code, errors, recorded = e2e.run(root, eff, args.targets)
    _emit({"run": folder, "playwright_exit": code, "findings": errors, "recorded": recorded}, args.format,
          "\n".join([*errors, *(f"{row['tc']} {row['result']}" for row in recorded), f"run: {folder}"]))
    return code or (1 if errors else 0)


def _run_tests(args: argparse.Namespace) -> int:
    root = args.repository.resolve()
    eff = resolve(specs_reqs(root))
    if args.command == "plan":
        work = tests.plan(root, eff, args.capability, args.kind)
        lines = [f"{kind} {row['tc']} {row['type']}" + (f" {row['file']}:{row['line']}" if "file" in row else "")
                 for kind in ("missing", "stale", "orphan") for row in work[kind]]
        _emit({"guidelines": eff.guidelines, **work}, args.format, "\n".join(lines) or "nothing to do")
        return 0
    if args.command == "pin":
        return _findings(tests.pin(root, eff, args.ids), args.format, f"pinned {' '.join(args.ids)}")
    if args.command == "check":
        return _findings(tests.check(root, eff, args.kind), args.format, "ok")
    folder, code, errors, recorded = tests.run(root, eff, args.kind, args.targets)
    _emit({"run": folder, "exit": code, "findings": errors, "recorded": recorded}, args.format,
          "\n".join([*errors, *(f"{row['tc']} {row['result']}" for row in recorded), f"run: {folder}"]))
    return code or (1 if errors else 0)


def _report_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gin-qa report")
    parser.add_argument("capability", nargs="?")
    parser.add_argument("--out", help="report folder, relative to the repository; must be missing or empty")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def _run_report(args: argparse.Namespace) -> int:
    root = args.repository.resolve()
    payload = report.build(root, resolve(specs_reqs(root)), args.capability, args.out)
    for run in payload["missing_evidence"]:
        print(f"gin-qa: evidence not found: {run}", file=sys.stderr)
    _emit(payload, args.format, payload["report"])
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--version"]:
        print(f"gin-qa {VERSION}")
        return 0
    groups = {"cases": (_parser, _run), "e2e": (_e2e_parser, _run_e2e), "tests": (_tests_parser, _run_tests),
              "report": (_report_parser, _run_report)}
    if not argv or argv[0] not in groups:
        print("usage: gin-qa cases {plan,next-id,pin,result,bug,split,check,export} ...\n"
              "       gin-qa e2e {init,plan,pin,run,check,export} ...\n"
              "       gin-qa tests {plan,pin,check,run} ...\n"
              "       gin-qa report [capability] [--out DIR]", file=sys.stderr)
        return 2
    make, run = groups[argv[0]]
    try:
        args = make().parse_args(argv[1:])
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    try:
        return run(args)
    except (QaError, ValueError, OSError) as error:
        print(f"gin-qa error: {error}", file=sys.stderr)
        return 2

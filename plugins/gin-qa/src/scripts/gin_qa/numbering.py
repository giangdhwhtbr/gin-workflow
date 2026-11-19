"""TC-ID numbering: the IDs that keep a number from a new case, and `gin-qa cases renumber`."""

from __future__ import annotations

from collections import Counter
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Any

from . import cases as tc
from . import e2e, tests
from .reqs import Effective, QaError


def cap_of(tc_id: str) -> str | None:
    found = tc.TC_ID.fullmatch(tc_id or "")
    return found.group(1).lower() if found else None


def test_files(root: Path, eff: Effective) -> list[str]:
    """Files matched by the `Tests:` globs of the valid automated types; a declaration error drops only its type."""
    types, _ = tests.declared(root, eff)
    return tests._files(root, [glob for kind in types.values() for glob in kind.globs])


def _specs(root: Path, eff: Effective, cap: str) -> list[tuple[str, str | None, str]]:
    """(path, header TC-ID, TC-ID of the file name) of each spec in `<e2e>/<cap>/`."""
    return [(spec.path, spec.tc, PurePosixPath(spec.path).name.removesuffix(".spec.ts").upper())
            for spec in e2e.load_specs(root, eff) if spec.path.split("/")[-2] == cap]


def held(root: Path, eff: Effective, cap: str) -> set[str]:
    ids = {item for _, header, named in _specs(root, eff, cap) for item in (header, named) if item}
    ids |= {marker.tc for marker in tests.markers(root, test_files(root, eff))}
    return {item for item in ids if cap_of(item) == cap}


UNTOUCHED = ["bug bead titles", "gin-qa tests run folders", "exported reports"]


def _pattern(mapping: dict[str, str]) -> tuple[re.Pattern[str], dict[str, str]]:
    """One regex over the four written forms of every old ID (TC-AUTH-005, tc-auth-005, tc_auth_005,
    TC_AUTH_005), and the same form of its new ID."""
    forms: dict[str, str] = {}
    for old, new in mapping.items():
        for shape in (str.upper, str.lower):
            for sep in ("-", "_"):
                forms[shape(old).replace("-", sep)] = shape(new).replace("-", sep)
    alternatives = "|".join(sorted(map(re.escape, forms), key=len, reverse=True))
    return re.compile(rf"(?<![A-Za-z0-9])(?:{alternatives})(?!\d)"), forms


def _uncommitted(root: Path, paths: list[str]) -> list[str]:
    """The paths git reports modified, staged, or untracked; none outside a git repository."""
    if not paths:
        return []
    done = subprocess.run(["git", "-c", "core.quotePath=false", "status", "--porcelain", "--untracked-files=all",
                           "--", *paths], cwd=root, capture_output=True, text=True, check=False,
                          env={**os.environ, "LC_ALL": "C"})  # the stderr check below reads git's English text
    if done.returncode == 0:
        return [line[3:] for line in done.stdout.splitlines() if line.strip()]
    if "not a git repository" in done.stderr:
        return []
    raise QaError(f"git status failed: {done.stderr.strip()}")


def _move(moves: list[tuple[Path, Path]]) -> None:
    """Renames through temporary names first, so `003 -> 002` never lands on `002` before it moved on."""
    staged = []
    for index, (source, target) in enumerate(moves):
        temporary = source.with_name(f".renumber-{index}-{source.name}")
        source.rename(temporary)
        staged.append((temporary, target))
    for temporary, target in staged:
        temporary.rename(target)


def renumber(root: Path, eff: Effective, cap: str, dry_run: bool) -> tuple[dict[str, Any], list[str]]:
    """`<cap>`'s cases to 001..N in their order, with their case files, e2e specs, test markers and names,
    and the e2e evidence their `Run:` names; nothing is written when there is a finding."""
    if not tc.TYPE.fullmatch(cap):
        raise ValueError(f"{cap!r}: a capability matches [a-z][a-z0-9-]*")
    base = root / eff.cases_dir
    if (base / f"{cap}.md").is_file():
        return {}, [f"{eff.cases_dir}/{cap}.md: a flat cases file; run `gin-qa cases split {cap}` first"]
    done = {"mapping": {}, "files": [], "untouched": UNTOUCHED, "dry_run": dry_run}
    if not (base / cap).is_dir():
        return done, []
    with tc._lock(base):
        loaded, errors = tc.load(root, eff.cases_dir)
        mine = [case for case in loaded if case.cap == cap]
        counts = Counter(case.id for case in mine)
        findings = [error for error in errors if error.startswith(f"{eff.cases_dir}/{cap}/")]
        specs = _specs(root, eff, cap)
        findings += [f"{path}: orphan e2e spec ({header or named} has no case); delete it or restore the case"
                     for path, header, named in specs if named not in counts or (header and header not in counts)]
        files = test_files(root, eff)
        findings += [f"{marker.path}:{marker.line}: orphan marker {marker.tc} (no case); delete it or restore "
                     "the case" for marker in tests.markers(root, files)
                     if cap_of(marker.tc) == cap and marker.tc not in counts]
        if findings:
            return {}, findings
        upper = cap.upper()
        ordered = sorted(counts, key=lambda item: int(tc.TC_ID.fullmatch(item).group(2)))
        mapping = {old: f"TC-{upper}-{index:03d}" for index, old in enumerate(ordered, 1)
                   if old != f"TC-{upper}-{index:03d}"}
        if not mapping:
            return done, []
        pattern, forms = _pattern(mapping)
        edits: dict[Path, str] = {}
        moves: list[tuple[Path, Path]] = []
        tracked = [*(root / case.path for case in mine), *(root / path for path, _, _ in specs),
                   *(root / path for path in files)]
        evidence: list[Path] = []
        runs: dict[Path, dict[str, str]] = {}
        evidence_base = (root / e2e.evidence_root(eff)).resolve()
        for case in mine:
            if case.id not in mapping:
                continue
            path = root / case.path
            moves.append((path, path.with_name(mapping[case.id] + path.name[len(case.id):])))
            run = case.fields.get("Run", "").strip()
            old_dir = root / run / case.id.lower()
            if run and evidence_base in (root / run).resolve().parents and (root / run / "run.json").is_file() \
                    and old_dir.is_dir():
                runs.setdefault(root / run / "run.json", {})[case.id] = mapping[case.id]
                evidence += old_dir.rglob("result.json")
                moves.append((old_dir, old_dir.with_name(mapping[case.id].lower())))
        for path, _, named in specs:
            if named in mapping:
                moves.append((root / path, (root / path).with_name(mapping[named].lower() + ".spec.ts")))
        wanted = {path: mapping for path in [*tracked, *evidence]}
        wanted.update(runs)  # a run record only changes for the cases whose evidence folder moves in that run
        for path, part in wanted.items():
            found, spelled = (pattern, forms) if part is mapping else _pattern(part)
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                if any(form.encode("ascii") in path.read_bytes() for form in spelled):
                    findings.append(f"{path.relative_to(root).as_posix()}: not UTF-8; rewrite its TC-IDs by hand "
                                    "or exclude it from the Tests: globs")
                continue
            new = found.sub(lambda match: spelled[match.group(0)], text)
            if new != text:
                edits[path] = new
        sources = {source for source, _ in moves}
        findings += [f"{target.relative_to(root).as_posix()}: already exists; delete it if it belongs to a "
                     "deleted case" for _, target in moves if target.exists() and target not in sources]
        changed = sorted({path.relative_to(root).as_posix() for path in [*edits, *sources] if path in tracked})
        findings += [f"{path}: not committed; commit or discard it first" for path in _uncommitted(root, changed)]
        if findings:
            return {}, findings

        def after(path: Path) -> str:
            """Where `path` is once the moves ran; a file inside a moved evidence folder moves with it."""
            for source, target in moves:
                if path == source or source in path.parents:
                    return (target / path.relative_to(source)).relative_to(root).as_posix()
            return path.relative_to(root).as_posix()

        shown = sorted({after(path) for path in [*edits, *sources]})
        if not dry_run:
            try:
                for path, text in edits.items():
                    tc.write_atomic(path, text)
                _move(moves)
            except OSError as error:
                raise QaError(f"renumber stopped after writing some files: {error}; `git status` lists "
                              "the files written; restore them with `git restore` and `git clean`, and rename any "
                              "`.renumber-*` files or evidence folders back") from error
        return {**done, "mapping": mapping, "files": shown}, []

"""Weekly check of the Claude Code changelog and the Beads releases against the surfaces gin uses.

Run from the main checkout: `python3 scripts/upstream_watch.py [--dry-run]`. One run files at most one
`upstream` bead listing the new lines that name a surface of `scripts/upstream_surfaces.json`, and one bead
per source it cannot read. The last versions read live in `.agent-workflow/runtime/upstream-watch.json`.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, TextIO
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SURFACES = ROOT / "scripts/upstream_surfaces.json"
CHANGELOG_URL = "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md"
RELEASES_URL = "https://api.github.com/repos/gastownhall/beads/releases?per_page=30"
STATE = Path(".agent-workflow/runtime/upstream-watch.json")
_HEADING = re.compile(r"^## +(\d+(?:\.\d+)+)\s*$", re.MULTILINE)
_BD_NAMES = r"(?:bd|bd_bin|executable)"
_BD_CALL = re.compile(r'(?:_bd|_bd_json|_beads_json)\s*\([^\[\n]*\[\s*"([a-z][a-z-]*)"'
                      r'|\[\s*(?:"bd"|' + _BD_NAMES + r')\s*,\s*"([a-z][a-z-]*)"')
# `[executable, "<word>"` also starts a call of another tool: `cases` runs the specs tool
# (specs_trace_all.py:62), `auth` and `api` run tea or gh (hosts/gitea.py:55, :194, :198), and
# `("bd", "gh")` in executables.py names two tools.
_NOT_BD = {"gh", "cases", "auth", "api"}
_VERSION = re.compile(r"\d+(?:\.\d+)*")


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def _lines(body: str) -> list[str]:
    """Release-note lines without list markers; blank lines and headings dropped."""
    return [line.strip().lstrip("-* ").strip() for line in body.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def claude_entries(text: str, last: str | None) -> list[tuple[str, list[str]]]:
    """(version, lines) of each changelog section newer than `last`, newest first."""
    headings = list(_HEADING.finditer(text))
    sections = [(match.group(1), text[match.end():headings[index + 1].start() if index + 1 < len(headings) else len(text)])
                for index, match in enumerate(headings)]
    if not sections:
        raise ValueError("no `## <version>` heading found")
    return [(version, _lines(body)) for version, body in sections
            if last is None or _version(version) > _version(last)]


def beads_entries(releases: list[dict[str, Any]], last: str | None) -> list[tuple[str, list[str]]]:
    """(label, lines) of each release published after `last`, newest first; a prerelease is marked."""
    rows = sorted(releases, key=lambda release: str(release.get("published_at") or ""), reverse=True)
    return [(f"{row['tag_name']} (release candidate)" if row.get("prerelease") else str(row["tag_name"]),
             _lines(str(row.get("body") or "")))
            for row in rows if last is None or str(row.get("published_at") or "") > last]


def matching(lines: list[str], groups: Mapping[str, list[str]]) -> list[tuple[str, list[str]]]:
    """(line, group names) of each line holding a keyword; a keyword needs no letter or digit right before it."""
    found = []
    for line in lines:
        names = [name for name, keywords in groups.items()
                 if any(re.search(r"(?<![A-Za-z0-9])" + re.escape(keyword), line, re.IGNORECASE)
                        for keyword in keywords)]
        if names:
            found.append((line, names))
    return found


def bd_subcommands(source_dir: Path) -> set[str]:
    """The bd subcommands that gin's Python code names at a call site with a literal subcommand."""
    called: set[str] = set()
    for path in Path(source_dir).rglob("*.py"):
        for match in _BD_CALL.finditer(path.read_text(encoding="utf-8")):
            called.add(match.group(1) or match.group(2))
    return called - _NOT_BD


def _span(entries: list[tuple[str, list[str]]]) -> str:
    versions = [version.split(" ")[0] for version, _ in entries]
    return versions[0] if len(versions) == 1 else f"{versions[-1]} to {versions[0]}"


def _digest(sources: list[tuple[str, list[tuple[str, list[str]]], Mapping[str, list[str]]]]) -> tuple[str, str] | None:
    """The title and description of the bead for the matching lines, or None when no line matches."""
    spans, parts = [], []
    for name, entries, groups in sources:
        if not entries:
            continue
        spans.append(f"{name} {_span(entries)}")
        for version, lines in entries:
            hits = matching(lines, groups)
            if hits:
                parts.append(f"{name} {version}:\n" + "\n".join(f"- {line} ({', '.join(names)})" for line, names in hits))
    if not parts:
        return None
    text = ("Lines of the upstream release notes that name a surface gin uses "
            "(scripts/upstream_surfaces.json). Close the bead when none needs work; split a line that does.\n\n"
            + "\n\n".join(parts))
    return f"Upstream changes: {'; '.join(spans)}", text


def _read_state(path: Path) -> tuple[dict[str, str], str | None]:
    """(state, None) from the state file; ({}, cause) when it is unreadable or invalid; ({}, None) when absent."""
    if not path.is_file():
        return {}, None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return {}, f"{error}"
    if not isinstance(state, dict) or not all(isinstance(value, str) for value in state.values()):
        return {}, "it is not a JSON object of strings"
    if "claude-code" in state and not _VERSION.fullmatch(state["claude-code"]):
        return {}, f"claude-code is not a dotted version: {state['claude-code']!r}"
    return state, None


def run(state_path: Path, *, fetch: Callable[[str], str], file_bead: Callable[[str, str], None],
        surfaces: Mapping[str, Mapping[str, list[str]]], dry_run: bool = False, out: TextIO = sys.stdout) -> int:
    """0 when every source was read, 1 when a source or the state file failed (its bead filed), 2 when a bead could not be filed."""
    state, bad_state = _read_state(state_path)
    newest, sources, failures = dict(state), [], []  # a failed source never reaches `newest[key] =`, so its old value stays
    if bad_state:
        failures.append(("Upstream check could not read its state file",
                         f"{state_path} is invalid: {bad_state}. Each source records a new baseline."))
    readers = (("claude-code", "Claude Code", "Claude Code changelog", CHANGELOG_URL,
                lambda text, last: claude_entries(text, last),
                lambda text: _HEADING.search(text).group(1)),
               ("beads", "Beads", "Beads releases", RELEASES_URL,
                lambda text, last: beads_entries(json.loads(text), last),
                lambda text: max(str(row.get("published_at") or "") for row in json.loads(text)) or _no_date()))
    baselines = []
    for key, name, label, url, entries_of, newest_of in readers:
        try:
            text = fetch(url)
            entries = entries_of(text, state.get(key))
            newest[key] = newest_of(text)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            failures.append((f"Upstream check could not read {label}",
                             f"{url} failed: {error}. The next run reads the same range again."))
            continue
        if key in state:
            sources.append((name, entries, surfaces[key]))
        else:
            baselines.append(name)
    beads = failures + ([] if (digest := _digest(sources)) is None else [digest])
    for title, text in beads:
        print(title, file=out)
        if dry_run:
            print(text, file=out)
            continue
        try:
            file_bead(title, text)
        except (OSError, RuntimeError) as error:
            print(f"could not file the bead: {error}", file=sys.stderr)
            return 2
    if not dry_run:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(newest, indent=2) + "\n", encoding="utf-8")
    for name in baselines:
        print(f"baseline recorded for {name}; the next run reports what changes after it", file=out)
    return 1 if failures else 0


def _no_date() -> str:
    raise ValueError("no release has a published_at date")


def _fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "gin-upstream-watch",
                                                   "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _main_checkout() -> Path:
    common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=ROOT,
                            text=True, capture_output=True, check=True).stdout.strip()
    return Path(common).parent


def _file_bead(root: Path) -> Callable[[str, str], None]:
    def file_bead(title: str, text: str) -> None:
        done = subprocess.run(["gin", "task", "create", "--type", "task", "-l", "upstream", "-d", text, title],
                              cwd=root, text=True, capture_output=True)
        if done.returncode:
            raise RuntimeError((done.stderr or done.stdout).strip() or f"gin task create exited {done.returncode}")
    return file_bead


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="upstream_watch", description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print what would be filed; file and write nothing")
    args = parser.parse_args(argv)
    root = _main_checkout()
    surfaces = json.loads(SURFACES.read_text(encoding="utf-8"))
    return run(root / STATE, fetch=_fetch, file_bead=_file_bead(root), surfaces=surfaces, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())

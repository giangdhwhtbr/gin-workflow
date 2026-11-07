"""Dated asset folders `<specs>/<cap>/assets/<YYYY-MM-DD>/`: `gin specs assets add|confirm` and their lint."""

from __future__ import annotations

from datetime import date
import difflib
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping, Sequence

from . import specs
from .atomic import atomic_write_many

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif")
_CONFIRMED = re.compile(r"^Confirmed:[ \t]*(.*?)[ \t]*$", re.MULTILINE)


def _is_day(value: str) -> bool:
    if not specs._ISO_DATE.match(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def confirmed_date(text: str) -> str | None:
    """The ISO date on the first `Confirmed:` line, or None when the folder is not confirmed."""
    found = _CONFIRMED.search(text)
    return found.group(1) if found and _is_day(found.group(1)) else None


def _day(value: str | None, today: date | None) -> str:
    if value is None:
        return (today or date.today()).isoformat()
    if not specs._ISO_DATE.match(value):
        raise specs.SpecsError(f"date {value!r} must be YYYY-MM-DD")
    if not _is_day(value):
        raise specs.SpecsError(f"date {value!r} is not a calendar date")
    return value


def _capability(root: Path, cfg: Mapping[str, Any], cap: str, new_capability: bool) -> Path:
    if not specs._CAP.match(cap):
        raise specs.SpecsError(f"capability {cap!r} must match [a-z][a-z0-9-]*")
    base = specs.specs_dir(root, cfg)
    if (base / cap).is_dir() or new_capability:
        return base / cap
    existing = sorted(p.name for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
    close = difflib.get_close_matches(cap, existing, n=3)
    hint = f"did you mean {', '.join(close)}?" if close else "no capability has a close name"
    raise specs.SpecsError(f"no capability {cap!r} under {specs.shown(root, base)}: {hint} "
                           "Pass --new-capability to create it.")


def _dated(assets: Path) -> list[str]:
    return sorted(p.name for p in assets.iterdir() if p.is_dir() and specs._ISO_DATE.match(p.name)) \
        if assets.is_dir() else []


def _set_field(text: str, key: str, value: str, after: str) -> str:
    """Replace the first `<key>:` line, or insert it after the `<after>:` line, else after the first line."""
    line = f"{key}: {value}"
    current = re.compile(rf"^{key}:.*$", re.MULTILINE)
    if current.search(text):
        return current.sub(line, text, count=1)
    anchor = re.compile(rf"^{after}:.*$", re.MULTILINE).search(text)
    end = anchor.end() if anchor else text.find("\n") if "\n" in text else len(text)
    return f"{text[:end]}\n{line}{text[end:]}"


def add(root: Path, cfg: Mapping[str, Any], cap: str, files: Sequence[Path], *, day: str | None = None,
        legacy: bool = False, new_capability: bool = False, today: date | None = None) -> dict[str, Any]:
    folder = _capability(root, cfg, cap, new_capability) / "assets" / _day(day, today)
    description = folder / "description.md"
    if description.is_file() and (when := confirmed_date(description.read_text(encoding="utf-8"))):
        raise specs.SpecsError(f"{specs.shown(root, folder)} was confirmed on {when} and is frozen; "
                               "use a new --date")
    target = folder / "legacy" if legacy else folder
    writes: dict[Path, bytes] = {}
    for source in (Path(item).expanduser() for item in files):
        if not source.is_file():
            raise specs.SpecsError(f"not a file: {source}")
        if legacy and source.suffix.lower() not in IMAGE_SUFFIXES:
            raise specs.SpecsError(f"{source.name}: --legacy takes only {', '.join(IMAGE_SUFFIXES)}")
        destination = target / source.name
        if destination == description:
            raise specs.SpecsError("description.md is reserved for the folder description")
        if destination in writes:
            raise specs.SpecsError(f"two files named {source.name}")
        if destination.exists():
            raise specs.SpecsError(f"{specs.shown(root, destination)} already exists")
        writes[destination] = source.read_bytes()
    copied = [specs.shown(root, path) for path in writes]
    created = not description.is_file()
    if created:
        earlier = [name for name in _dated(folder.parent) if name < folder.name]
        text = specs.render(specs.template_text(root, "iteration.md"), {"capability": cap, "date": folder.name})
        text = _set_field(text, "Kind", "legacy" if legacy else "change" if earlier else "new", after="Kind")
        text = _set_field(text, "Previous", f"assets/{earlier[-1]}/" if earlier else "none", after="Kind")
        writes[description] = _set_field(text, "Confirmed", "no", after="Previous").encode("utf-8")
    if writes:
        atomic_write_many(writes, mode=0o644)
    return {"folder": specs.shown(root, folder), "description": specs.shown(root, description),
            "created": created, "files": copied}


def confirm(root: Path, cfg: Mapping[str, Any], cap: str, day: str, *, today: date | None = None) -> dict[str, str]:
    if not specs._CAP.match(cap):
        raise specs.SpecsError(f"capability {cap!r} must match [a-z][a-z0-9-]*")
    description = specs.specs_dir(root, cfg) / cap / "assets" / _day(day, None) / "description.md"
    shown = specs.shown(root, description)
    if not description.is_file():
        raise specs.SpecsError(f"no {shown}: run gin specs assets add first")
    text = description.read_text(encoding="utf-8")
    if when := confirmed_date(text):
        raise specs.SpecsError(f"{shown} is already confirmed on {when}")
    stamp = (today or date.today()).isoformat()
    atomic_write_many({description: _set_field(text, "Confirmed", stamp, after="Previous").encode("utf-8")},
                      mode=0o644)
    return {"description": shown, "confirmed": stamp}


def confirmed_value_errors(root: Path, cfg: Mapping[str, Any]) -> list[str]:
    """A `Confirmed:` line of a dated folder's description.md that is neither `no` nor an ISO date."""
    errors = []
    for description in sorted(specs.specs_dir(root, cfg).glob("*/assets/*/description.md")):
        if not specs._ISO_DATE.match(description.parent.name):
            continue
        for number, line in enumerate(description.read_text(encoding="utf-8").splitlines(), 1):
            found = _CONFIRMED.match(line)
            if found:
                if found.group(1) != "no" and not _is_day(found.group(1)):
                    errors.append(f"{specs.shown(root, description)}:{number}: "
                                  "Confirmed: must be 'no' or a YYYY-MM-DD date")
                break
    return errors


def frozen_findings(root: Path, cfg: Mapping[str, Any], base: str, label: str) -> list[str]:
    """Every path that differs from `base` under a dated folder confirmed on `base`, untracked files included."""
    prefix = PurePosixPath(cfg["specs"]).as_posix()
    listed = specs._git(root, "ls-tree", "-r", "--name-only", base, "--", prefix)
    if listed.returncode != 0:
        raise specs.SpecsError(f"cannot list {prefix} at {label}: {listed.stderr.strip()}")
    pattern = re.compile(rf"^{re.escape(prefix)}/[^/]+/assets/(\d{{4}}-\d{{2}}-\d{{2}})/description\.md$")
    findings = []
    for path in listed.stdout.splitlines():
        match = pattern.match(path)
        when = confirmed_date(specs._git(root, "show", f"{base}:{path}").stdout) if match else None
        if not when:
            continue
        folder = path.rsplit("/", 1)[0]
        changed = specs._git(root, "diff", "--name-only", base, "--", folder).stdout.splitlines()
        untracked = specs._git(root, "ls-files", "--others", "--exclude-standard", "--", folder).stdout.splitlines()
        findings += [f"{item}: assets/{match.group(1)}/ was confirmed on {when} at {label}; add a new dated folder"
                     for item in sorted(set(changed + untracked))]
    return findings


def lint(root: Path, cfg: Mapping[str, Any], against: str | None) -> tuple[list[str], list[str]]:
    """Asset findings for `gin specs lint`, and warnings for stderr."""
    errors = confirmed_value_errors(root, cfg)
    try:
        base = against or specs.default_base(root)
        resolved = specs._git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
        if resolved.returncode != 0:
            raise specs.SpecsError(f"cannot resolve {base}")
        commit = resolved.stdout.strip()
        return errors + frozen_findings(root, cfg, commit, against or f"merge-base {commit[:12]}"), []
    except specs.SpecsError as error:
        return errors, [f"frozen asset check skipped: {error}"]

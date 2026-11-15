"""`.ginrc`: the minimum gin version a project needs, and the verdict for the installed one.

Read before any configuration, so this module imports neither YAML nor another workflow_core module."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess

FILE = ".ginrc"
QA = "gin-qa"  # the one core module that names the QA extension: it reports the extension's version
GUIDE = "https://giangdhwhtbr.github.io/gin-workflow/guides/upgrading/"
_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")


class PinError(ValueError):
    """The text is not one version X.Y.Z."""


@dataclass(frozen=True)
class Verdict:
    status: str  # none, compatible, older, newer_major, invalid
    required: str | None = None
    path: Path | None = None
    reason: str | None = None  # the OS error when the file cannot be read


def parse(text: str) -> tuple[int, int, int]:
    stripped = text.strip()
    if not _VERSION.fullmatch(stripped):
        raise PinError(f"not a version X.Y.Z: {stripped!r}")
    major, minor, patch = (int(part) for part in stripped.split("."))
    return major, minor, patch


def find(start: Path) -> Path | None:
    """The nearest .ginrc from `start` upwards. Inside the home directory, the search stops below it."""
    here = Path(start).resolve()
    try:
        home = Path.home().resolve()
    except RuntimeError:  # no home directory can be determined
        home = None
    inside_home = home is not None and (here == home or home in here.parents)
    for directory in (here, *here.parents):
        if inside_home and (directory == home or directory in home.parents):
            return None
        candidate = directory / FILE
        if candidate.exists():
            return candidate
    return None


def verdict(installed: str, start: Path) -> Verdict:
    path = find(start)
    if path is None:
        return Verdict("none")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as error:
        return Verdict("invalid", path=path, reason=str(error))
    except UnicodeDecodeError:
        return Verdict("invalid", path=path)
    try:
        required = parse(text)
    except PinError:
        return Verdict("invalid", path=path)
    have = parse(installed)
    if have[0] > required[0]:
        status = "newer_major"
    elif have < required:
        status = "older"
    else:
        status = "compatible"
    return Verdict(status, text.strip(), path)


def message(found: Verdict, installed: str) -> str:
    if found.status == "older":
        return (f"gin {installed} is older than this project needs ({found.required}, {found.path}); "
                f"update gin: {GUIDE}")
    if found.status == "newer_major":
        return (f"gin {installed} is a newer major version than this project uses ({found.required}, {found.path}); "
                f"upgrade the project with gin setup update --approve: {GUIDE}")
    if found.status == "invalid":
        return f"{found.path} must hold one version X.Y.Z" + (f" ({found.reason})" if found.reason else "")
    return ""


def _output(argv: list[str]) -> str | None:
    executable = shutil.which(argv[0])
    if executable is None:
        return None
    try:
        done = subprocess.run([executable, *argv[1:]], capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    return done.stdout if done.returncode == 0 else None


def qa_version() -> str | None:
    """The version the QA extension's `--version` prints, or None when it is missing or fails."""
    out = _output([QA, "--version"])
    parts = out.split() if out else []
    return parts[1] if len(parts) == 2 and parts[0] == QA else None

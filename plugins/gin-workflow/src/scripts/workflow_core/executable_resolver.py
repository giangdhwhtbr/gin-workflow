"""Safe harness executable discovery preserving package manager symlinks."""

from __future__ import annotations

import os
from pathlib import Path
import shutil


PROVIDER_EXE_ALIASES: dict[str, tuple[str, ...]] = {
    "antigravity": ("agy",),
}

COMMON_INSTALL_DIRS: tuple[Path, ...] = (
    Path.home() / ".npm-global/bin",
    Path.home() / ".local/bin",
    Path.home() / ".local/share/pnpm",
    Path("/usr/local/bin"),
    Path("/home/linuxbrew/.linuxbrew/bin"),
)


def resolve_harness_executable(configured: str | None, provider: str | None = None) -> str | None:
    """Resolve a configured harness executable to an absolute executable path.

    Preserves symlinks (avoids Path.resolve() which can break versioned npm shims).
    """
    if configured is None or not str(configured).strip():
        return None

    raw = str(configured).strip()
    candidate = Path(raw)

    # 1. Check absolute path
    if candidate.is_absolute():
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return os.path.abspath(raw)
        return None

    # 2. If it contains path separators, reject or require explicit anchor
    if "/" in raw or "\\" in raw:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return os.path.abspath(raw)
        return None

    # 3. Check standard PATH via shutil.which
    found = shutil.which(raw)
    if found:
        return os.path.abspath(found)

    # 4. Check exact provider aliases (e.g. literal 'antigravity' -> 'agy')
    alias_matches: list[str] = []
    if provider and provider in PROVIDER_EXE_ALIASES:
        if raw == provider:
            alias_matches.extend(PROVIDER_EXE_ALIASES[provider])

    for alias in alias_matches:
        found_alias = shutil.which(alias)
        if found_alias:
            return os.path.abspath(found_alias)

    # 5. Search common installation directories
    candidates_to_probe = [raw, *alias_matches]
    for directory in COMMON_INSTALL_DIRS:
        for name in candidates_to_probe:
            probe = directory / name
            if probe.is_file() and os.access(probe, os.X_OK):
                return os.path.abspath(str(probe))

    return None

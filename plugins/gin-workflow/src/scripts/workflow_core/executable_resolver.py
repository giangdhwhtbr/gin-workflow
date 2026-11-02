"""Safe harness executable discovery preserving package manager symlinks."""

from __future__ import annotations

import os
from pathlib import Path
import shutil


PROVIDER_EXE_ALIASES: dict[str, tuple[str, ...]] = {
    "antigravity": ("agy",),
}

def common_install_dirs(os_name: str = os.name) -> tuple[Path, ...]:
    try:
        home = Path.home()
    except RuntimeError:  # no HOME or USERPROFILE, as in a stripped child environment on Windows
        home = None
    dirs = [] if home is None else [home / ".npm-global/bin", home / ".local/bin", home / ".opencode/bin",
                                    home / ".local/share/pnpm"]
    dirs += [Path("/usr/local/bin"), Path("/home/linuxbrew/.linuxbrew/bin")]
    if os_name == "nt" and os.environ.get("APPDATA"):
        dirs.append(Path(os.environ["APPDATA"]) / "npm")
    return tuple(dirs)


COMMON_INSTALL_DIRS: tuple[Path, ...] = common_install_dirs()


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
    extensions = [""]
    if os.name == "nt":
        extensions = []
        # PATHEXT is always ;-separated; lowercase too, as Windows matches case-insensitively and the probe does not.
        extensions += [e for ext in os.environ.get("PATHEXT", "").split(";") if ext for e in (ext.lower(), ext)]
        extensions.append("")  # bare name last: on Windows it is usually the extensionless npm shell script
    for directory in COMMON_INSTALL_DIRS:
        for name in candidates_to_probe:
            for ext in extensions:
                probe = os.path.join(directory, f"{name}{ext}")
                if os.path.isfile(probe) and os.access(probe, os.X_OK):
                    return os.path.abspath(probe)

    return None

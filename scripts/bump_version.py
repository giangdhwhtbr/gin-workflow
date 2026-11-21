"""Write one release version to every location that carries it.

Usage: python3 scripts/bump_version.py X.Y.Z
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

VERSION_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
PLUGINS = ("gin-workflow", "gin-qa", "gin-ba")
JSON_VERSION = re.compile(r'^\s*"version":\s*"([^"]+)"', re.MULTILINE)


def locations(root: Path) -> list[tuple[Path, re.Pattern]]:
    """Every file that carries the release version, with the pattern whose group 1 is that version."""
    root = Path(root)
    found: list[tuple[Path, re.Pattern]] = []
    for plugin in PLUGINS:
        base = root / "plugins" / plugin
        found.append((base / "plugin.meta.json", JSON_VERSION))
        found.append((base / "src/.claude-plugin/plugin.json", JSON_VERSION))
        found.append((base / "src/.codex-plugin/plugin.json", JSON_VERSION))
    found += [
        (root / "plugins/gin-workflow/src/scripts/workflow_core/cli.py", re.compile(r'^CLI_VERSION = "([^"]+)"', re.MULTILINE)),
        (root / "plugins/gin-qa/src/scripts/gin_qa/cli.py", re.compile(r'^VERSION = "([^"]+)"', re.MULTILINE)),
    ]
    for name in ("LAUNCHER_VERSION", "QA_LAUNCHER_VERSION"):
        found.append((root / "install.sh", re.compile(rf'^{name}="([^"]+)"', re.MULTILINE)))
    for name in ("LauncherVersion", "QaLauncherVersion"):
        found.append((root / "install.ps1", re.compile(rf"^\${name} = '([^']+)'", re.MULTILINE)))
    return found


def bump(root: Path, version: str) -> list[Path]:
    """Write `version` to every location and return the files that changed."""
    if not VERSION_RE.fullmatch(version):
        raise ValueError(f"version must be X.Y.Z (three numbers), got {version!r}")
    texts: dict[Path, str] = {}
    original: dict[Path, str] = {}
    for path, pattern in locations(root):
        if path not in texts:
            texts[path] = original[path] = path.read_bytes().decode("utf-8")
        match = pattern.search(texts[path])
        if match is None:
            raise ValueError(f"{path}: no version found for pattern {pattern.pattern!r}")
        texts[path] = texts[path][: match.start(1)] + version + texts[path][match.end(1):]
    changed = [path for path, text in texts.items() if text != original[path]]
    for path in changed:
        path.write_bytes(texts[path].encode("utf-8"))
    return changed


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("error: usage: bump_version.py X.Y.Z", file=sys.stderr)
        return 2
    root = Path(__file__).resolve().parents[1]
    try:
        changed = bump(root, argv[0])
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    for path in changed:
        print(path.relative_to(root))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

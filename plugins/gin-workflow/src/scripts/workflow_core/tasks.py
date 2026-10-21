"""`gin-workflow task`: one task-tracking entry point, routed to Beads (`bd`) or the Markdown store."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Mapping, Sequence

from . import task_markdown
from .checkout import main_checkout
from .configuration import ConfigValidationError


def backend(root: Path) -> str:
    """The configured `providers.task_tracking` name; `beads` when setup has not run.

    An effective config that exists but is invalid raises ConfigValidationError instead of
    falling back, so a markdown repository never silently writes to Beads.
    """
    from .configuration import load_effective_config

    root = Path(root)
    if not (main_checkout(root.resolve()) / ".agent-workflow/generated/effective-config.yaml").is_file():
        return "beads"
    try:
        return backend_name(load_effective_config(root))
    except OSError as error:
        raise ConfigValidationError(f"cannot read the effective config: {error}") from error


def backend_name(config: Mapping[str, Any]) -> str:
    """`providers.task_tracking` in an already-loaded config; `beads` when unset."""
    providers = config.get("providers", {})
    raw = providers.get("task_tracking", "beads") if isinstance(providers, Mapping) else "beads"
    name = raw.get("name", raw.get("type")) if isinstance(raw, Mapping) else raw
    return str(name or "beads")


def _bd_json(executable: str, argv: Sequence[str], cwd: Path, env: Mapping[str, str] | None = None) -> Any:
    """The first JSON value bd prints (it may append a tip line); None when bd fails."""
    try:
        completed = subprocess.run([executable, *argv, "--json"], cwd=cwd, env=env, text=True,
                                   capture_output=True, check=False, timeout=30)
        return json.JSONDecoder().raw_decode(completed.stdout.lstrip())[0] if completed.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def _shipped(root: Path, executable: str, ref: str) -> bool:
    """True when `external:<project>:<capability>` has a closed `provides:<capability>` bead in that project."""
    _, project, capability = (ref.split(":", 2) + ["", ""])[:3]
    try:
        location = subprocess.run([executable, "config", "get", f"external_projects.{project}"], cwd=root,
                                  text=True, capture_output=True, check=False, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False
    if not project or not capability or not Path(location).is_dir():
        return False
    found = _bd_json(executable, ["list", "--status", "closed", "--label", f"provides:{capability}"], root,
                     env={**os.environ, "BEADS_DIR": location})
    return bool(found)


def held_by_external(root: Path, executable: str) -> dict[str, list[str]]:
    """Ready beads with an unshipped external dependency, which bd 1.0.5 reports as resolved."""
    explained = _bd_json(executable, ["ready", "--explain", "-n", "0"], root)
    held: dict[str, list[str]] = {}
    for issue in explained.get("ready", []) if isinstance(explained, dict) else []:
        refs = [ref for ref in issue.get("resolved_blockers") or [] if str(ref).startswith("external:")]
        missing = [ref for ref in refs if not _shipped(root, executable, ref)]
        if missing:
            held[issue["id"]] = missing
    return held


def _ready(executable: str, argv: Sequence[str]) -> int:
    root = Path.cwd()
    held = held_by_external(root, executable)
    if not held:
        return subprocess.run([executable, *argv], check=False).returncode
    completed = subprocess.run([executable, *argv], text=True, capture_output=True, check=False)
    sys.stderr.write(completed.stderr)
    if completed.returncode != 0:
        sys.stdout.write(completed.stdout)
        return completed.returncode
    if "--json" in argv:
        issues = json.JSONDecoder().raw_decode(completed.stdout.lstrip())[0]
        print(json.dumps([issue for issue in issues if issue.get("id") not in held], indent=2))
        return 0
    # ponytail: drops the text lines naming a held id; a held parent's indented children stay listed
    pattern = re.compile(r"(?<![\w.-])(" + "|".join(map(re.escape, held)) + r")(?![\w.-])")
    sys.stdout.write("".join(line for line in completed.stdout.splitlines(keepends=True)
                             if not pattern.search(line)))
    print("\nHeld by unshipped external dependencies:")
    for bead, refs in sorted(held.items()):
        print(f"  {bead}: {', '.join(refs)}")
    return 0


def query(root: Path, argv: Sequence[str]) -> Any:
    """Run one read-only query and return its JSON; None when the backend is unavailable or fails."""
    try:
        name = backend(root)
    except ConfigValidationError:
        return None
    if name == "markdown":
        return task_markdown.query(root, argv)
    executable = shutil.which("bd")
    if executable is None:
        return None
    try:
        completed = subprocess.run(
            [executable, *argv, "--json"], cwd=root, text=True, capture_output=True, check=False, timeout=30
        )
        result = json.loads(completed.stdout) if completed.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None
    if argv[:1] == ["ready"] and isinstance(result, list):
        held = held_by_external(root, executable)
        result = [issue for issue in result if issue.get("id") not in held]
    return result


def main(argv: Sequence[str]) -> int:
    root = Path.cwd()
    try:
        name = backend(root)
    except ConfigValidationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if name == "markdown":
        return task_markdown.main(root, argv)
    executable = shutil.which("bd")
    if executable is None:
        print("error: bd is not installed; install Beads or set providers.task_tracking: markdown "
              "(gin-workflow setup configure --set providers.task_tracking=markdown)", file=sys.stderr)
        return 127
    if argv[:1] == ["ready"]:
        return _ready(executable, argv)
    return subprocess.run([executable, *argv], check=False).returncode

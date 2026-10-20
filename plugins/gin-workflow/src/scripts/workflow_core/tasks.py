"""`gin-workflow task`: one task-tracking entry point, routed to Beads (`bd`) or the Markdown store."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Mapping, Sequence

from . import task_markdown


def backend(root: Path) -> str:
    """The configured `providers.task_tracking` name; `beads` when unset or setup has not run."""
    from .configuration import ConfigValidationError, load_effective_config

    try:
        return backend_name(load_effective_config(Path(root)))
    except (ConfigValidationError, OSError):
        return "beads"


def backend_name(config: Mapping[str, Any]) -> str:
    """`providers.task_tracking` in an already-loaded config; `beads` when unset."""
    providers = config.get("providers", {})
    raw = providers.get("task_tracking", "beads") if isinstance(providers, Mapping) else "beads"
    name = raw.get("name", raw.get("type")) if isinstance(raw, Mapping) else raw
    return str(name or "beads")


def query(root: Path, argv: Sequence[str]) -> Any:
    """Run one read-only query and return its JSON; None when the backend is unavailable or fails."""
    if backend(root) == "markdown":
        return task_markdown.query(root, argv)
    executable = shutil.which("bd")
    if executable is None:
        return None
    try:
        completed = subprocess.run(
            [executable, *argv, "--json"], cwd=root, text=True, capture_output=True, check=False, timeout=30
        )
        return json.loads(completed.stdout) if completed.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def main(argv: Sequence[str]) -> int:
    root = Path.cwd()
    if backend(root) == "markdown":
        return task_markdown.main(root, argv)
    executable = shutil.which("bd")
    if executable is None:
        print("error: bd is not installed; install Beads or set providers.task_tracking: markdown "
              "(gin-workflow setup configure --set providers.task_tracking=markdown)", file=sys.stderr)
        return 127
    return subprocess.run([executable, *argv], check=False).returncode

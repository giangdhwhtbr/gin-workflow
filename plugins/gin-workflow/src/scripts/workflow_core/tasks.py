"""`gin-workflow task`: one task-tracking entry point, routed to Beads (`bd`) or the Markdown store."""

from __future__ import annotations

import json
from pathlib import Path
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
        return json.loads(completed.stdout) if completed.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


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
    return subprocess.run([executable, *argv], check=False).returncode

"""`gin task`: one task-tracking entry point, routed to Beads (`bd`) or the Markdown store."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping, Sequence

from . import task_markdown, workspace
from .checkout import main_checkout
from .configuration import ConfigValidationError
from .executables import tool


def backend(root: Path) -> str:
    """The configured `providers.task_tracking` name; `markdown` when setup has not run.

    An effective config that exists but is invalid raises ConfigValidationError instead of
    falling back, so a markdown repository never silently writes to Beads.
    """
    from .configuration import load_effective_config

    root = Path(root)
    if not (main_checkout(root.resolve()) / ".agent-workflow/generated/effective-config.yaml").is_file():
        return "markdown"
    try:
        return backend_name(load_effective_config(root))
    except OSError as error:
        raise ConfigValidationError(f"cannot read the effective config: {error}") from error


def backend_name(config: Mapping[str, Any]) -> str:
    """`providers.task_tracking` in an already-loaded config; `beads` when unset and team configured, else `markdown`."""
    default = "beads" if "team" in config else "markdown"
    providers = config.get("providers", {})
    raw = providers.get("task_tracking", default) if isinstance(providers, Mapping) else default
    name = raw.get("name", raw.get("type")) if isinstance(raw, Mapping) else raw
    return str(name or default)


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
    parts = ref.split(":")
    if len(parts) != 3 or not all(parts):
        return False
    _, project, capability = parts
    try:
        location = subprocess.run([executable, "config", "get", f"external_projects.{project}"], cwd=root,
                                  text=True, capture_output=True, check=False, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False
    directory = main_checkout(Path(root)) / Path(location).expanduser()
    if not location or not directory.is_dir():
        return False
    found = _bd_json(executable, ["list", "--status", "closed", "--label", f"provides:{capability}"], root,
                     env={**os.environ, "BEADS_DIR": str(directory)})
    return bool(found)


def held_in(root: Path, executable: str, result: Any) -> dict[str, list[str]]:
    """Ready beads in a bd ready result (a list, or the `--explain` dict) with an unshipped external dependency.

    bd 1.0.5 reports those as resolved. A list carries each bead's `dependencies`; the explain dict its
    `resolved_blockers`. Each distinct ref is looked up once.
    """
    shipped: dict[str, bool] = {}
    held: dict[str, list[str]] = {}
    for issue in (result.get("ready") if isinstance(result, dict) else result) or []:
        if "resolved_blockers" in issue:
            refs = list(issue["resolved_blockers"] or [])
        else:
            refs = [dependency.get("depends_on_id") for dependency in issue.get("dependencies") or []]
        refs = [ref for ref in refs if str(ref).startswith("external:")]
        for ref in refs:
            if ref not in shipped:
                shipped[ref] = _shipped(root, executable, ref)
        missing = [ref for ref in refs if not shipped[ref]]
        if missing:
            held[issue["id"]] = missing
    return held


def held_by_external(root: Path, executable: str) -> dict[str, list[str]] | None:
    """`held_in` for bd's `--explain` ready list; None when bd cannot explain it.

    Callers then fail instead of releasing held beads.
    """
    explained = _bd_json(executable, ["ready", "--explain", "-n", "0"], root)
    return held_in(root, executable, explained) if isinstance(explained, dict) else None


def without_held(result: Any, held: Mapping[str, Any]) -> Any:
    """A bd ready result (a list, or the `--explain` dict) minus the held beads."""
    if isinstance(result, list):
        return [issue for issue in result if not (isinstance(issue, dict) and issue.get("id") in held)]
    if isinstance(result, dict) and isinstance(result.get("ready"), list):
        return {**result, "ready": without_held(result["ready"], held)}
    return result


def _ready(executable: str, argv: Sequence[str], root: Path) -> int:
    json_output = "--json" in argv
    held = {} if json_output else held_by_external(root, executable)
    if held is None:
        print("error: bd ready --explain failed, so external dependencies cannot be checked", file=sys.stderr)
        return 1
    if not json_output and not held:
        return subprocess.run([executable, *argv], cwd=root, check=False).returncode
    completed = subprocess.run([executable, *argv], cwd=root, text=True, capture_output=True, check=False)
    sys.stderr.write(completed.stderr)
    if completed.returncode != 0:
        sys.stdout.write(completed.stdout)
        return completed.returncode
    if json_output:
        try:
            issues = json.JSONDecoder().raw_decode(completed.stdout.lstrip())[0]
        except json.JSONDecodeError:
            print("error: bd ready printed no JSON, so external dependencies cannot be applied", file=sys.stderr)
            return 1
        held = held_in(root, executable, issues)
        if held:
            print(json.dumps(without_held(issues, held), indent=2))
        else:
            sys.stdout.write(completed.stdout)
        return 0
    # ponytail: drops the text lines naming a held id; a held parent's indented children stay listed
    pattern = re.compile(r"(?<![\w.-])(" + "|".join(map(re.escape, held)) + r")(?![\w.-])")
    sys.stdout.write("".join(line for line in completed.stdout.splitlines(keepends=True)
                             if not pattern.search(line)))
    print("\nHeld by unshipped external dependencies:")
    for bead, refs in sorted(held.items()):
        print(f"  {bead}: {', '.join(refs)}")
    return 0


def query_result(root: Path, argv: Sequence[str]) -> tuple[Any, str | None]:
    """Run one read-only query: (JSON, None), or (None, cause) when the backend is unavailable or fails."""
    try:
        name = backend(root)
    except ConfigValidationError:
        return None, "invalid backend config"
    if name == "markdown":
        result = task_markdown.query(root, argv)
        return (None, "markdown task query failed") if result is None else (result, None)
    executable = tool("bd", root)
    if executable is None:
        return None, "bd not found"
    if argv[:1] == ["ready"]:
        argv = [*argv, "--exclude-type", "milestone"]
    try:
        completed = subprocess.run(
            [executable, *argv, "--json"], cwd=root, text=True, capture_output=True, check=False, timeout=30
        )
    except subprocess.TimeoutExpired:
        return None, "bd timed out after 30s"
    except (OSError, subprocess.SubprocessError) as error:
        return None, f"bd failed: {error}"
    if completed.returncode != 0:
        first = next((line.strip() for line in (completed.stderr or "").splitlines() if line.strip()), "")
        return None, f"bd exited {completed.returncode}" + (f": {first}" if first else "")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None, "invalid JSON from bd"
    if argv[:1] == ["ready"]:
        result = without_held(result, held_in(root, executable, result))
    return result, None


def query(root: Path, argv: Sequence[str]) -> Any:
    """Run one read-only query and return its JSON; None when the backend is unavailable or fails."""
    return query_result(root, argv)[0]


def _bd_env(root: Path, argv: Sequence[str]) -> dict[str, str] | None:
    """In team mode bd acts as the member's email, as `team claim` does, unless an actor is already given."""
    if "BD_ACTOR" in os.environ or any(arg == "--actor" or arg.startswith("--actor=") for arg in argv):
        return None
    from .team import current_member, team_for_repo

    team = team_for_repo(root)
    member = current_member(root, team) if team is not None else None
    return None if member is None else {**os.environ, "BD_ACTOR": member.email}


def main(argv: Sequence[str]) -> int:
    root = workspace.project_root(Path.cwd())
    try:
        name = backend(root)
    except ConfigValidationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if argv[:1] == ["close"]:
        from .close_guard import check

        argv, error = check(root, argv)
        if error:
            print(f"error: {error}", file=sys.stderr)
            return 2
    if name == "markdown":
        return task_markdown.main(root, argv)
    executable = tool("bd", root)
    if executable is None:
        print("error: bd is not installed; install Beads or set providers.task_tracking: markdown "
              "(gin setup configure --set providers.task_tracking=markdown)", file=sys.stderr)
        return 127
    if argv[:1] == ["ready"]:
        return _ready(executable, [*argv, "--exclude-type", "milestone"], root)
    return subprocess.run([executable, *argv], cwd=root, check=False, env=_bd_env(root, argv)).returncode

"""Markdown task store: one file per task under `.planning/tasks/`, driven by a `bd`-compatible CLI subset."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any, Sequence

import yaml

from .atomic import atomic_write_text
from .checkout import main_checkout
from .events import _file_lock

STATUSES = ("open", "in_progress", "blocked", "deferred", "closed")
_FIELDS = ("id", "title", "issue_type", "status", "parent", "deps", "labels", "priority", "assignee",
           "spec_id", "acceptance_criteria", "close_reason", "created_at", "updated_at")
_NOTES = "\n## Notes\n"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*")


class _Loader(yaml.SafeLoader):
    """SafeLoader that keeps timestamps as strings, so a hand-edited date stays JSON-serializable."""


_Loader.yaml_implicit_resolvers = {
    key: [resolver for resolver in resolvers if resolver[0] != "tag:yaml.org,2002:timestamp"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()}


class TaskFileError(ValueError):
    """A task file or request that cannot be honored; the message names the file or task."""


def tasks_root(root: Path) -> Path:
    return main_checkout(Path(root).resolve()) / ".planning" / "tasks"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise TaskFileError(f"{path}: unreadable: {error}") from error


def _parse(path: Path) -> dict[str, Any]:
    text = _read(path)
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise TaskFileError(f"{path}: missing YAML frontmatter")
    head, body = text[4:].split("\n---\n", 1)
    try:
        task = yaml.load(head, Loader=_Loader)
    except yaml.YAMLError as error:
        raise TaskFileError(f"{path}: invalid frontmatter: {error}") from error
    if not isinstance(task, dict) or not task.get("id") or not task.get("title"):
        raise TaskFileError(f"{path}: frontmatter needs id and title")
    if not all(isinstance(task[key], (str, int)) for key in ("id", "title")):
        raise TaskFileError(f"{path}: id and title must be strings")
    for key in ("labels", "acceptance_criteria"):
        if not isinstance(task.get(key) or [], list) or not all(isinstance(item, str) for item in task.get(key) or []):
            raise TaskFileError(f"{path}: {key} must be a list of strings")
    deps = task.get("deps") or []
    if not isinstance(deps, list) or not all(isinstance(dep, dict) and isinstance(dep.get("id"), str) for dep in deps):
        raise TaskFileError(f"{path}: deps must be a list of mappings with an id")
    if not all(isinstance(value, (str, int, type(None))) for key, value in task.items()
               if key not in ("deps", "labels", "acceptance_criteria")):
        raise TaskFileError(f"{path}: scalar fields must be strings or numbers")
    task["id"], task["title"] = str(task["id"]), str(task["title"])
    if task.get("status", "open") not in STATUSES:
        raise TaskFileError(f"{path}: unsupported status {task.get('status')!r}")
    description, notes = (re.split(r"^## Notes$", body.strip("\n"), maxsplit=1, flags=re.M) + [""])[:2]
    task.update(description=description.strip(), notes=notes.strip())
    task.setdefault("status", "open")
    task.setdefault("issue_type", "task")
    for key in ("deps", "labels", "acceptance_criteria"):
        task[key] = list(task.get(key) or [])
    return task


def _render(task: dict[str, Any]) -> str:
    head = {key: task[key] for key in _FIELDS if task.get(key) not in (None, "", [])}
    text = "---\n" + yaml.safe_dump(head, sort_keys=False, allow_unicode=True) + "---\n"
    if task.get("description"):
        text += "\n" + task["description"].strip() + "\n"
    if task.get("notes"):
        text += _NOTES + "\n" + task["notes"].strip() + "\n"
    return text


def load_all(root: Path) -> dict[str, dict[str, Any]]:
    tasks: dict[str, dict[str, Any]] = {}
    base = tasks_root(root)
    for path in sorted(base.glob("*/*.md")) if base.is_dir() else ():
        task = _parse(path)
        task["_path"] = path
        if task["id"] in tasks:
            raise TaskFileError(f"duplicate task id {task['id']}: {tasks[task['id']]['_path']} and {path}")
        tasks[task["id"]] = task
    return tasks


def _get(tasks: dict[str, dict[str, Any]], task_id: str) -> dict[str, Any]:
    if task_id not in tasks:
        raise TaskFileError(f"no such task: {task_id}")
    return tasks[task_id]


def _ignore(root: Path) -> None:
    """Keep task files out of git: this store is local, like the Beads database."""
    ignore = tasks_root(root) / ".gitignore"
    if not ignore.is_file():
        ignore.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(ignore, "*\n", mode=0o644)


def _save(root: Path, task: dict[str, Any]) -> None:
    task["description"] = re.sub(r"\r\n?", "\n", task.get("description") or "")
    if re.search(r"^## Notes$", task["description"], flags=re.M):
        raise TaskFileError("description cannot contain a '## Notes' line; use --notes")
    task["updated_at"] = _now()
    path = task.pop("_path")
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, _render(task), mode=0o644)
    task["_path"] = path


def _next_id(tasks: dict[str, dict[str, Any]], prefix: str) -> str:
    pattern = re.compile(re.escape(prefix) + r"(\d+)$")
    numbers = [int(match.group(1)) for task_id in tasks if (match := pattern.match(task_id))]
    return f"{prefix}{max(numbers, default=0) + 1}"


def prefix(root: Path) -> str:
    return main_checkout(Path(root).resolve()).name


def _blockers(tasks: dict[str, dict[str, Any]], task: dict[str, Any]) -> list[str]:
    return [dep["id"] for dep in task["deps"] if dep.get("type", "blocks") == "blocks"
            and tasks.get(dep["id"], {}).get("status") != "closed"]


def _cycle(tasks: dict[str, dict[str, Any]], start: str, target: str) -> list[str] | None:
    """Path target -> ... -> start through blocking deps, if adding start->target would close a cycle."""
    stack = [(target, [start, target])]
    seen = set()
    while stack:
        current, path = stack.pop()
        if current == start:
            return path
        if current in seen or current not in tasks:
            continue
        seen.add(current)
        for dep in tasks[current]["deps"]:
            if dep.get("type", "blocks") == "blocks":
                stack.append((dep["id"], [*path, dep["id"]]))
    return None


def as_json(task: dict[str, Any]) -> dict[str, Any]:
    record = {key: value for key, value in task.items()
              if not key.startswith("_") and key != "deps" and value is not None}
    record["dependencies"] = [{"depends_on_id": dep["id"], "type": dep.get("type", "blocks")}
                              for dep in task["deps"]]
    if task.get("parent"):
        record["dependencies"].append({"depends_on_id": task["parent"], "type": "parent-child"})
    return record


def _csv(values: Sequence[str] | None) -> list[str]:
    return [part.strip() for value in values or () for part in value.split(",") if part.strip()]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gin-workflow task", exit_on_error=False)
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)

    def command(name: str) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, exit_on_error=False)
        sub.add_argument("--json", action="store_true", dest="json_flag")
        return sub

    create = command("create")
    create.add_argument("title_arg", nargs="?")
    create.add_argument("--title")
    create.add_argument("--id")
    create.add_argument("--type", default="task")
    create.add_argument("--parent")
    create.add_argument("--labels", "-l", action="append")
    create.add_argument("--description", "-d", default="")
    create.add_argument("--spec-id")
    create.add_argument("--acceptance", "--acceptance-criteria", default="")
    create.add_argument("--status", default="open", choices=STATUSES)
    create.add_argument("--notes", default="")
    create.add_argument("--priority", "-p")
    create.add_argument("--assignee", "-a")

    show = command("show")
    show.add_argument("ids", nargs="+")

    update = command("update")
    update.add_argument("id")
    update.add_argument("--title")
    update.add_argument("--description", "-d")
    update.add_argument("--status", "-s", choices=STATUSES)
    update.add_argument("--notes")
    update.add_argument("--append-notes")
    update.add_argument("--acceptance", "--acceptance-criteria")
    update.add_argument("--add-label", action="append")
    update.add_argument("--remove-label", action="append")
    update.add_argument("--priority", "-p")
    update.add_argument("--assignee", "-a")

    close = command("close")
    close.add_argument("ids", nargs="+")
    close.add_argument("--reason", "-r", default="")

    reopen = command("reopen")
    reopen.add_argument("ids", nargs="+")

    listing = command("list")
    listing.add_argument("--status", "-s", action="append")
    listing.add_argument("--label", "-l", action="append")
    listing.add_argument("--parent")
    listing.add_argument("--type", "-t")
    listing.add_argument("--all", action="store_true")
    listing.add_argument("--limit", "-n", type=int, default=0)

    command("ready")
    command("blocked")

    dep = command("dep")
    dep_commands = dep.add_subparsers(dest="dep_command", required=True)
    for name in ("add", "remove"):
        sub = dep_commands.add_parser(name, exit_on_error=False)
        sub.add_argument("id")
        sub.add_argument("depends_on")
        sub.add_argument("--type", "-t", default="blocks")
        sub.add_argument("--json", action="store_true", dest="json_flag")
    dep_list = dep_commands.add_parser("list", exit_on_error=False)
    dep_list.add_argument("id")
    dep_list.add_argument("--json", action="store_true", dest="json_flag")

    config = command("config")
    config.add_argument("action", choices=("get",))
    config.add_argument("key", choices=("issue_prefix",))

    remember = command("remember")
    remember.add_argument("fact")
    memories = command("memories")
    memories.add_argument("keyword", nargs="?", default="")
    return parser


def _execute(root: Path, args: argparse.Namespace) -> Any:
    command = args.command
    _ignore(root)
    if command == "config":
        return {"key": "issue_prefix", "value": prefix(root)}
    readers = ("show", "list", "ready", "blocked", "memories")
    with _file_lock(tasks_root(root) / ".lock", exclusive=command not in readers):
        if command in ("remember", "memories"):
            memory = tasks_root(root) / "memory.md"
            lines = _read(memory).splitlines() if memory.is_file() else []
            if command == "memories":
                return [line[2:] for line in lines if line.startswith("- ") and args.keyword.lower() in line.lower()]
            atomic_write_text(memory, "\n".join(lines or ["# Project memory", ""]) + f"\n- {args.fact}\n", mode=0o644)
            return {"remembered": args.fact}
        tasks = load_all(root)
        if command == "show":
            return [as_json(_get(tasks, task_id)) for task_id in args.ids]
        if command == "list":
            statuses = _csv(args.status)
            labels = _csv(args.label)
            found = [task for task in tasks.values()
                     if (args.all or statuses or task["status"] != "closed")
                     and (not statuses or task["status"] in statuses)
                     and all(label in task["labels"] for label in labels)
                     and (not args.parent or task.get("parent") == args.parent)
                     and (not args.type or task["issue_type"] == args.type)]
            return [as_json(task) for task in found[: args.limit or None]]
        if command == "ready":
            return [as_json(task) for task in tasks.values()
                    if task["status"] == "open" and not _blockers(tasks, task)]
        if command == "blocked":
            return [{**as_json(task), "blocked_by": _blockers(tasks, task)} for task in tasks.values()
                    if task["status"] != "closed" and _blockers(tasks, task)]
        if command == "create":
            title = args.title or args.title_arg
            if not title or not title.strip():
                raise TaskFileError("create needs a title")
            if args.parent:
                parent = _get(tasks, args.parent)
                task_id = args.id or _next_id(tasks, f"{args.parent}.")
                directory = parent["_path"].parent
            else:
                task_id = args.id or _next_id(tasks, f"{prefix(root)}-")
                directory = tasks_root(root) / task_id
            if not _ID.fullmatch(task_id) or ".." in task_id:
                raise TaskFileError(f"invalid task id: {task_id!r}")
            if task_id in tasks:
                raise TaskFileError(f"task already exists: {task_id}")
            task = {"id": task_id, "title": title.strip(), "issue_type": args.type, "status": args.status,
                    "parent": args.parent, "deps": [], "labels": _csv(args.labels), "priority": args.priority,
                    "assignee": args.assignee, "spec_id": args.spec_id,
                    "acceptance_criteria": [line for line in args.acceptance.splitlines() if line.strip()],
                    "created_at": _now(), "description": args.description, "notes": args.notes,
                    "_path": directory / f"{task_id}.md"}
            _save(root, task)
            return as_json(task)
        if command == "update":
            task = _get(tasks, args.id)
            for key in ("title", "description", "status", "notes", "priority", "assignee"):
                if getattr(args, key) is not None:
                    task[key] = getattr(args, key)
            if args.append_notes:
                task["notes"] = "\n".join(filter(None, (task["notes"], args.append_notes)))
            if args.acceptance is not None:
                task["acceptance_criteria"] = [line for line in args.acceptance.splitlines() if line.strip()]
            removed = set(_csv(args.remove_label))
            task["labels"] = [label for label in task["labels"] if label not in removed]
            task["labels"] += [label for label in _csv(args.add_label) if label not in task["labels"]]
            _save(root, task)
            return [as_json(task)]
        if command in ("close", "reopen"):
            changed = []
            for task_id in args.ids:
                task = _get(tasks, task_id)
                task["status"] = "closed" if command == "close" else "open"
                task["close_reason"] = args.reason if command == "close" else ""
                _save(root, task)
                changed.append(as_json(task))
            return changed
        if command == "dep":
            task = _get(tasks, args.id)
            if args.dep_command == "list":
                return [as_json(_get(tasks, dep["id"])) for dep in task["deps"]]
            if args.dep_command == "add":
                _get(tasks, args.depends_on)
                if args.id == args.depends_on:
                    raise TaskFileError(f"{args.id} cannot depend on itself")
                if args.type == "blocks" and (cycle := _cycle(tasks, args.id, args.depends_on)):
                    raise TaskFileError("dependency cycle: " + " -> ".join(cycle))
                if not any(dep["id"] == args.depends_on for dep in task["deps"]):
                    task["deps"].append({"id": args.depends_on, "type": args.type})
            else:
                task["deps"] = [dep for dep in task["deps"] if dep["id"] != args.depends_on]
            _save(root, task)
            status = {"add": "added", "remove": "removed"}[args.dep_command]
            return {"status": status, "issue_id": args.id, "depends_on_id": args.depends_on}
    raise TaskFileError(f"unsupported command: {command}")


def _text(value: Any) -> str:
    rows = value if isinstance(value, list) else [value]
    lines = []
    for row in rows:
        if isinstance(row, dict) and "id" in row:
            lines.append(f"{row['id']} [{row['status']}] {row['title']}")
        elif isinstance(row, dict) and "value" in row:
            lines.append(str(row["value"]))
        else:
            lines.append(str(row) if not isinstance(row, dict) else json.dumps(row))
    return "\n".join(lines)


def _run(root: Path, argv: Sequence[str]) -> tuple[argparse.Namespace, Any]:
    try:
        args = _parser().parse_args(list(argv))
    except SystemExit as error:  # argparse reports usage errors by exiting
        raise TaskFileError(f"invalid arguments: {' '.join(argv)}") from error
    return args, _execute(root, args)


def main(root: Path, argv: Sequence[str]) -> int:
    try:
        args, result = _run(root, argv)
    except (argparse.ArgumentError, TaskFileError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2) if args.json or getattr(args, "json_flag", False) else _text(result))
    return 0


def query(root: Path, argv: Sequence[str]) -> Any:
    """Run one command in process and return its JSON-shaped result; None when it fails."""
    try:
        return _run(root, [arg for arg in argv if arg != "--json"])[1]
    except (argparse.ArgumentError, TaskFileError):
        return None

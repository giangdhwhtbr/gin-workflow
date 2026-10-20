# Plan: Markdown task tracking (gin-workflow without Beads)

Spec: `.planning/specs/2026-10-16-markdown-task-tracking-design.md`
Workflow id: `markdown-task-tracking`

## Objective
With `providers.task_tracking: markdown`, the whole lifecycle runs without `bd`: skills call `gin-workflow task …`, tasks are git-ignored Markdown files under `.planning/tasks/` in the main checkout, and `implementation_complete`/`shipped` derive from them. With `beads` (the default) `gin-workflow task` runs `bd` with the arguments unchanged, and every existing behavior stays as it is.

**Goal (from spec):** Some environments cannot install Beads (`bd`). gin-workflow must still run the full lifecycle there, with tasks stored as local Markdown files inside the repository directory. Beads stays the default and must keep working exactly as it does today.

**Architecture:** one store module `workflow_core/task_markdown.py` that parses a `bd`-compatible argv subset and returns `bd`-shaped JSON. One dispatcher `workflow_core/tasks.py` (`backend`, `query`, `main`) that every caller goes through: `gin-workflow task`, the lifecycle gate query (`lifecycle_cli._beads_json`), `specs._bd`, and `usage._bd`. A thin `MarkdownTaskTrackingProvider` reuses the store through its own argv and the beads provider's `_task` normalizer.

**Tech stack:** Python 3 + PyYAML (already required), `unittest`, bash.

**Global Constraints (verbatim from spec):**
- With `task_tracking: beads` (the default), every existing lifecycle behavior, gate result, and test outcome is unchanged. `gin-workflow task <args>` under `beads` runs `bd <args>` with the arguments unchanged and returns its exit code and output. The existing test suites pass unmodified, except contract tests that assert skill text containing a literal `bd` command, which follow the R8 rewrite.
- The store writes `.planning/tasks/.gitignore` containing `*` on its first write, so task files are never committed and never make a checkout dirty. Nothing in this mode commits task files.
- Paths always resolve to the main checkout (the parent of `git-common-dir`), so every worktree reads and writes the same files.
- Writes take an exclusive lock on `.planning/tasks/.lock` in the main checkout (git-ignored with the rest), reusing `_file_lock` from `workflow_core/events.py`, and write files with `workflow_core/atomic.py`.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `implement`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: none needed; every file below was prototyped and the full suite passed with it (983 tests, 3 skipped).

## Requirement Analysis
- Problem statement: `bd` is a hard dependency; skills, gates, `specs`, and `usage` call it directly, so environments that cannot install it cannot use gin-workflow.
- Success criteria: spec US-1..US-4 acceptance criteria pass as tests; the existing suite stays green.
- Constraints: Global Constraints above.
- Non-goals: tracking task files in git or sharing them (follow-up epic: `gin-tasks` branch + team mode on markdown); team mode and `usage` on markdown; migration between backends; Windows locking.

## Approach Options
### Option 1: `bd`-compatible CLI subset behind one dispatcher (selected)
- Summary: `gin-workflow task` accepts the same arguments as `bd`; skills change `bd ` to `gin-workflow task ` and nothing else. Under beads it is a pure pass-through.
- Pros: beads behavior is unchanged by construction; skill edits are mechanical; Python callers keep their `bd`-shaped JSON parsing.
- Cons: the markdown side must mimic `bd`'s flag names and JSON keys for the subset in use.

### Option 2: new neutral verbs and JSON, adapters for both backends
- Pros: cleaner interface.
- Cons: rewrites every skill instruction and every Python caller, and re-implements beads behavior, which puts non-regression at risk.

### Recommended Approach
- Selected option: Option 1. Reasoning: it is the smallest change and the only one where beads stays byte-for-byte identical.

## Scope
- In scope: the files listed per track.
- Out of scope: everything in Non-goals; `review_ledger/cleanup.py` (with no `bd`, it already falls back to review-ledger and git-merge state); `team_beads.py`.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Four small tracks; T2 and T3 depend on T1 and T4 depends on T2, so one agent in sequence is cheapest.
```

## Tasks

Every track follows TDD: add the track's tests, run them and see them fail, add the code, run them and see them pass, then commit on the track branch. All code below is the prototyped, passing version: copy it exactly.

### Track 1: Markdown store and bd-compatible CLI
- **Dependencies**: none
- **Provider role**: `backend`
- **Reasoning**: `high` (concurrency and file-format edge cases (locking, cycle detection, fail-closed parsing).)
- **Estimated complexity**: high
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/workflow_core/task_markdown.py`
  - Create: `tests/workflow_core/test_task_markdown.py`
- **Interfaces (produced)**:
  - `tasks_root(root: Path) -> Path` — `<main checkout>/.planning/tasks`
  - `class TaskFileError(ValueError)`
  - `main(root: Path, argv: Sequence[str]) -> int` — prints JSON with `--json`, else one `<id> [<status>] <title>` line per row; exit 1 on `TaskFileError` or bad arguments
  - `query(root: Path, argv: Sequence[str]) -> Any` — the same result in process (any `--json` in argv is ignored); `None` on failure
  - `prefix(root: Path) -> str`, `as_json(task) -> dict`, `STATUSES`
- **Interfaces (consumed)**:
  - `atomic.atomic_write_text(path, text, mode=)`, `checkout.main_checkout(repo)`, `events._file_lock(path, exclusive=)`
- **Acceptance criteria**:
  - `create` of an epic, a child (`<epic>.<n>`), and `--id` gives bd-shaped ids and files at the spec paths
  - `ready`/`blocked`/`list --all`/`--status a,b`/`--label`/`--parent` filter as `bd` does
  - cycles, self and dangling dependencies, duplicate `--id`, and malformed files are rejected with exit 1 naming the file or task
  - a worktree writes to the main checkout; 12 concurrent creates get distinct ids; `git status` stays clean
- **Steps**:
  1. Add the test changes below. Run `python3 -m unittest tests.workflow_core.test_task_markdown`: expect failures or import errors.
  2. Add the code changes below. Run the same command: expect `OK`.
  3. Commit on the track branch.

`plugins/gin-workflow/src/scripts/workflow_core/task_markdown.py` (new):

````python
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


class TaskFileError(ValueError):
    """A task file or request that cannot be honored; the message names the file or task."""


def tasks_root(root: Path) -> Path:
    return main_checkout(Path(root).resolve()) / ".planning" / "tasks"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise TaskFileError(f"{path}: missing YAML frontmatter")
    head, body = text[4:].split("\n---\n", 1)
    try:
        task = yaml.safe_load(head)
    except yaml.YAMLError as error:
        raise TaskFileError(f"{path}: invalid frontmatter: {error}") from error
    if not isinstance(task, dict) or not task.get("id") or not task.get("title"):
        raise TaskFileError(f"{path}: frontmatter needs id and title")
    if task.get("status", "open") not in STATUSES:
        raise TaskFileError(f"{path}: unsupported status {task.get('status')!r}")
    description, _, notes = body.strip("\n").partition(_NOTES.strip("\n"))
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
        tasks[str(task["id"])] = task
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
    if command in ("remember", "memories"):
        memory = tasks_root(root) / "memory.md"
        lines = memory.read_text(encoding="utf-8").splitlines() if memory.is_file() else []
        if command == "memories":
            return [line[2:] for line in lines if line.startswith("- ") and args.keyword.lower() in line.lower()]
        atomic_write_text(memory, "\n".join(lines or ["# Project memory", ""]) + f"\n- {args.fact}\n", mode=0o644)
        return {"remembered": args.fact}

    with _file_lock(tasks_root(root) / ".lock", exclusive=command not in ("show", "list", "ready", "blocked")):
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
            return {"status": args.dep_command + "ed", "issue_id": args.id, "depends_on_id": args.depends_on}
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
````

`tests/workflow_core/test_task_markdown.py` (new):

````python
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core import task_markdown  # noqa: E402


class TaskMarkdownTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name) / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

    def tearDown(self):
        self._directory.cleanup()

    def run_task(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = task_markdown.main(self.root, argv)
        return code, out.getvalue(), err.getvalue()

    def q(self, *argv):
        return task_markdown.query(self.root, argv)

    def test_create_epic_and_children_with_bd_shaped_ids_and_files(self):
        epic = self.q("create", "--type", "epic", "Epic")
        child = self.q("create", "Track", "--parent", epic["id"], "-d", "desc", "--acceptance", "a\nb")
        self.assertEqual("repo-1", epic["id"])
        self.assertEqual("repo-1.1", child["id"])
        path = self.root / ".planning/tasks/repo-1/repo-1.1.md"
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nid: repo-1.1\n"))
        self.assertIn("\ndesc\n", text)
        shown = self.q("show", "repo-1.1")[0]
        self.assertEqual(["a", "b"], shown["acceptance_criteria"])
        self.assertIn({"depends_on_id": "repo-1", "type": "parent-child"}, shown["dependencies"])

    def test_explicit_id_labels_and_label_filters(self):
        self.q("create", "--id", "repo-rm-auth", "--type", "epic", "--labels", "roadmap", "Auth")
        self.q("update", "repo-rm-auth", "--add-label", "sprint:s1")
        self.assertEqual(["repo-rm-auth"], [r["id"] for r in self.q("list", "--label", "sprint:s1", "--all")])
        self.q("update", "repo-rm-auth", "--remove-label", "sprint:s1")
        self.assertEqual([], self.q("list", "--label", "sprint:s1", "--all"))
        code, _, err = self.run_task("create", "--id", "repo-rm-auth", "Again")
        self.assertEqual(1, code)
        self.assertIn("already exists", err)

    def test_ready_blocked_close_reopen_and_list_all(self):
        epic = self.q("create", "--type", "epic", "E")["id"]
        a = self.q("create", "A", "--parent", epic)["id"]
        b = self.q("create", "B", "--parent", epic)["id"]
        self.q("dep", "add", b, a)
        self.assertEqual({epic, a}, {r["id"] for r in self.q("ready")})
        self.assertEqual([(b, [a])], [(r["id"], r["blocked_by"]) for r in self.q("blocked")])
        self.q("close", a, "--reason", "tests green")
        self.assertEqual({epic, b}, {r["id"] for r in self.q("ready")})
        self.assertEqual([b], [r["id"] for r in self.q("list", "--parent", epic)])
        self.assertEqual({a, b}, {r["id"] for r in self.q("list", "--parent", epic, "--all", "--limit", "0")})
        self.assertEqual("tests green", self.q("show", a)[0]["close_reason"])
        self.q("reopen", a)
        self.assertEqual("open", self.q("show", a)[0]["status"])
        self.assertEqual({a, b}, {r["id"] for r in self.q("list", "--status", "open,in_progress", "--parent", epic)})

    def test_update_fields_and_notes(self):
        task = self.q("create", "T", "--notes", "first")["id"]
        self.q("update", task, "--status", "in_progress", "--title", "T2", "--append-notes", "second")
        shown = self.q("show", task)[0]
        self.assertEqual(("in_progress", "T2", "first\nsecond"), (shown["status"], shown["title"], shown["notes"]))

    def test_dependency_cycle_self_and_dangling_are_rejected(self):
        a = self.q("create", "A")["id"]
        b = self.q("create", "B")["id"]
        self.q("dep", "add", b, a)
        code, _, err = self.run_task("dep", "add", a, b)
        self.assertEqual(1, code)
        self.assertIn(f"dependency cycle: {a} -> {b} -> {a}", err)
        self.assertEqual(1, self.run_task("dep", "add", a, a)[0])
        self.assertEqual(1, self.run_task("dep", "add", a, "repo-99")[0])
        self.assertEqual([a], [r["id"] for r in self.q("dep", "list", b)])
        self.q("dep", "remove", b, a)
        self.assertEqual([], self.q("dep", "list", b))

    def test_malformed_file_fails_closed_naming_the_file(self):
        self.q("create", "--type", "epic", "E")
        bad = self.root / ".planning/tasks/repo-1/broken.md"
        bad.write_text("no frontmatter\n", encoding="utf-8")
        code, _, err = self.run_task("list")
        self.assertEqual(1, code)
        self.assertIn(str(bad), err)
        self.assertIsNone(self.q("list", "--all"))
        bad.write_text("---\nid: repo-9\ntitle: x\nstatus: done\n---\n", encoding="utf-8")
        self.assertIn("unsupported status", self.run_task("list")[2])

    def test_hand_edit_is_picked_up(self):
        task = self.q("create", "T")["id"]
        path = self.root / f".planning/tasks/{task}/{task}.md"
        path.write_text(path.read_text(encoding="utf-8").replace("status: open", "status: closed"), encoding="utf-8")
        self.assertEqual("closed", self.q("show", task)[0]["status"])

    def test_worktree_reads_and_writes_the_main_checkout(self):
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=self.root, check=True,
                       env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                            "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin"})
        worktree = Path(self._directory.name) / "wt"
        subprocess.run(["git", "worktree", "add", "-q", str(worktree), "-b", "wt"], cwd=self.root, check=True)
        created = task_markdown.query(worktree, ["create", "From worktree"])
        self.assertTrue((self.root / f".planning/tasks/{created['id']}/{created['id']}.md").is_file())
        self.assertFalse((worktree / ".planning/tasks").exists())

    def test_concurrent_creates_get_distinct_ids(self):
        epic = self.q("create", "--type", "epic", "E")["id"]
        code = f"import sys; sys.path.insert(0, {str(SCRIPTS)!r}); from pathlib import Path; " \
               f"from workflow_core.task_markdown import main; sys.exit(main(Path('.'), sys.argv[1:]))"
        workers = [subprocess.Popen([sys.executable, "-c", code, "create", f"T{n}", "--parent", epic],
                                    cwd=self.root, stdout=subprocess.DEVNULL) for n in range(12)]
        self.assertEqual([0] * 12, [worker.wait() for worker in workers])
        self.assertEqual(12, len(self.q("list", "--parent", epic)))

    def test_task_files_are_git_ignored(self):
        self.q("create", "--type", "epic", "E")
        self.q("remember", "a fact")
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.root, text=True, capture_output=True)
        self.assertEqual("", status.stdout)
        self.assertEqual("*\n", (self.root / ".planning/tasks/.gitignore").read_text(encoding="utf-8"))

    def test_memory_and_prefix(self):
        self.q("remember", "use uv for python")
        self.q("remember", "never edit .beads")
        self.assertEqual(["use uv for python"], self.q("memories", "uv"))
        self.assertEqual("repo", self.q("config", "get", "issue_prefix")["value"])
        self.assertEqual((0, "repo\n", ""), self.run_task("config", "get", "issue_prefix"))

    def test_text_output_and_unknown_command(self):
        task = self.q("create", "T")["id"]
        self.assertEqual((0, f"{task} [open] T\n", ""), self.run_task("list"))
        self.assertNotEqual(0, self.run_task("frobnicate")[0])


if __name__ == "__main__":
    unittest.main()
````


### Track 2: Dispatcher, gates, and config
- **Dependencies**: Track 1
- **Provider role**: `backend`
- **Reasoning**: `medium` (bounded wiring with clear seams; the beads path is a pass-through.)
- **Estimated complexity**: medium
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/workflow_core/tasks.py`
  - Create: `tests/workflow_core/test_tasks.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/cli.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/specs.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/usage.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/configuration.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py`
- **Interfaces (produced)**:
  - `tasks.backend(root: Path) -> str` — `providers.task_tracking` from the effective config; `beads` when unset or setup has not run
  - `tasks.query(root: Path, argv: list[str]) -> Any` — beads: the exact former `_beads_json` subprocess call; markdown: `task_markdown.query`
  - `tasks.main(argv: Sequence[str]) -> int` — beads: `subprocess.run([bd, *argv], check=False).returncode`, 127 with a hint when `bd` is missing; markdown: `task_markdown.main(Path.cwd(), argv)`
  - `gin-workflow task …` routed in `cli.main`
  - `setup detect` JSON gains `beads_installed: bool`
- **Interfaces (consumed)**:
  - Track 1 `task_markdown.query`, `task_markdown.main`; `configuration.load_effective_config`
- **Acceptance criteria**:
  - `lifecycle_cli._beads_json` keeps its name and signature (existing tests patch it) and delegates to `tasks.query`
  - under beads, `gin-workflow task <args>` calls `bd <args>` unchanged and the gate query calls `bd … --json` exactly as before
  - with markdown configured, the real CLI moves `implementation_complete` and `shipped` from unmet to satisfied as tasks close
  - a `team` block with `markdown` fails validation with "team mode requires Beads"; `usage` under markdown raises "AI usage tracking requires Beads"
- **Steps**:
  1. Add the test changes below. Run `python3 -m unittest tests.workflow_core.test_tasks`: expect failures or import errors.
  2. Add the code changes below. Run the same command: expect `OK`.
  3. Commit on the track branch.

`plugins/gin-workflow/src/scripts/workflow_core/tasks.py` (new):

````python
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
        providers = load_effective_config(Path(root)).get("providers", {})
    except (ConfigValidationError, OSError):
        return "beads"
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
````

`tests/workflow_core/test_tasks.py` (new):

````python
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core import tasks  # noqa: E402
from workflow_core.configuration import ConfigValidationError, validate_portable_config  # noqa: E402

CLI = SCRIPTS / "gin-workflow"
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@t"}


def gw(cwd, *argv):
    return subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=ENV, text=True, capture_output=True)


class TaskDispatchTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name) / "repo"
        (self.root / ".claude").mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=self.root, env=ENV, check=True)

    def tearDown(self):
        self._directory.cleanup()

    def init(self, *assignments):
        sets = [arg for value in assignments for arg in ("--set", value)]
        done = gw(self.root, "setup", "init", "--harness", "claude", "--non-interactive", "--approve", *sets)
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)

    def test_backend_defaults_to_beads_without_setup_or_setting(self):
        self.assertEqual("beads", tasks.backend(self.root))
        self.init()
        self.assertEqual("beads", tasks.backend(self.root))

    def test_beads_passes_argv_through_to_bd_unchanged(self):
        argv = ["update", "x-1", "--status", "in_progress", "--json"]
        with mock.patch("workflow_core.tasks.backend", return_value="beads"), \
                mock.patch("workflow_core.tasks.shutil.which", return_value="/opt/bd"), \
                mock.patch("workflow_core.tasks.subprocess.run",
                           return_value=subprocess.CompletedProcess([], 7)) as run:
            self.assertEqual(7, tasks.main(argv))
        run.assert_called_once_with(["/opt/bd", *argv], check=False)

    def test_beads_query_matches_the_previous_bd_call(self):
        done = subprocess.CompletedProcess([], 0, stdout='[{"id": "x-1", "status": "closed"}]')
        with mock.patch("workflow_core.tasks.backend", return_value="beads"), \
                mock.patch("workflow_core.tasks.shutil.which", return_value="/opt/bd"), \
                mock.patch("workflow_core.tasks.subprocess.run", return_value=done) as run:
            self.assertEqual([{"id": "x-1", "status": "closed"}], tasks.query(self.root, ["show", "x-1"]))
        run.assert_called_once_with(["/opt/bd", "show", "x-1", "--json"], cwd=self.root, text=True,
                                    capture_output=True, check=False, timeout=30)

    def test_beads_missing_bd_explains_the_markdown_option(self):
        with mock.patch("workflow_core.tasks.backend", return_value="beads"), \
                mock.patch("workflow_core.tasks.shutil.which", return_value=None):
            self.assertIsNone(tasks.query(self.root, ["show", "x"]))
            with mock.patch("sys.stderr") as stderr:
                self.assertEqual(127, tasks.main(["ready"]))
        self.assertIn("providers.task_tracking=markdown", "".join(c.args[0] for c in stderr.write.call_args_list))

    def test_markdown_lifecycle_gates_end_to_end(self):
        self.init("providers.task_tracking=markdown")
        self.assertEqual("markdown", tasks.backend(self.root))
        epic = json.loads(gw(self.root, "task", "create", "--type", "epic", "E", "--json").stdout)["id"]
        child = json.loads(gw(self.root, "task", "create", "T", "--parent", epic, "--json").stdout)["id"]
        gw(self.root, "record", "orchestration-ready", "--workflow-id", "w", "--epic", epic, "--evidence", "x",
           "--actor", "me")

        def gates():
            state = json.loads(gw(self.root, "state", "--workflow-id", "w", "--format", "json").stdout)
            return state["gates"]["implementation_complete"], state["gates"]["shipped"]

        self.assertEqual(("unmet", "unmet"), gates())
        self.assertEqual(0, gw(self.root, "task", "close", child, "--reason", "ok").returncode)
        self.assertEqual(("satisfied", "unmet"), gates())
        gw(self.root, "task", "close", epic, "--reason", "merged")
        self.assertEqual(("satisfied", "satisfied"), gates())

    def test_detect_reports_whether_bd_is_installed(self):
        from workflow_core import setup_service

        for found, expected in (("/opt/bd", True), (None, False)):
            with mock.patch("workflow_core.setup_service.shutil.which", return_value=found):
                self.assertIs(expected, setup_service.detect(self.root)["beads_installed"])

    def test_team_mode_rejects_markdown_task_tracking(self):
        config = {"schema_version": "2.7", "providers": {"task_tracking": "markdown"},
                  "team": {"host": "github", "members": {}}}
        with self.assertRaisesRegex(ConfigValidationError, "team mode requires Beads"):
            validate_portable_config(config)


if __name__ == "__main__":
    unittest.main()
````

`plugins/gin-workflow/src/scripts/workflow_core/cli.py`:

````diff
diff --git a/plugins/gin-workflow/src/scripts/workflow_core/cli.py b/plugins/gin-workflow/src/scripts/workflow_core/cli.py
index 6b654d6..4f6912a 100644
--- a/plugins/gin-workflow/src/scripts/workflow_core/cli.py
+++ b/plugins/gin-workflow/src/scripts/workflow_core/cli.py
@@ -67,10 +67,13 @@ def main(arguments: Sequence[str] | None = None) -> int:
         print(f"gin-workflow {CLI_VERSION}")
         return 0
     if not argv or argv[0] not in ("setup", "state", "unblock", "record", "quick-check", "rules", "specs", "team",
-                                   "usage", "reviewer", "hooks"):
+                                   "usage", "reviewer", "hooks", "task"):
         print("usage: gin-workflow {setup,state,unblock,record,quick-check,rules,specs,team,usage,reviewer,hooks} <command>",
               file=sys.stderr)
         return 2
+    if argv[0] == "task":
+        from .tasks import main as tasks_main
+        return tasks_main(argv[1:])
     if argv[0] == "hooks":
         from .hooks import main as hooks_main
         return hooks_main(argv[1:])
````

`plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py`:

````diff
diff --git a/plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py b/plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py
index 6b592e4..dd404e4 100644
--- a/plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py
+++ b/plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py
@@ -81,17 +81,10 @@ def _process_gate_state(
 
 
 def _beads_json(repo_path: Path, argv: list[str]) -> Any:
-    """Run one read-only Beads query; None when Beads is unavailable or fails."""
-    executable = shutil.which("bd")
-    if executable is None:
-        return None
-    try:
-        completed = subprocess.run(
-            [executable, *argv, "--json"], cwd=repo_path, text=True, capture_output=True, check=False, timeout=30
-        )
-        return json.loads(completed.stdout) if completed.returncode == 0 else None
-    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
-        return None
+    """Run one read-only task query on the configured backend; None when it is unavailable or fails."""
+    from .tasks import query
+
+    return query(repo_path, argv)
 
 
 def _recorded_epic(event_store: WorkflowEventStore, workflow_id: str) -> str:
````

`plugins/gin-workflow/src/scripts/workflow_core/specs.py`:

````diff
diff --git a/plugins/gin-workflow/src/scripts/workflow_core/specs.py b/plugins/gin-workflow/src/scripts/workflow_core/specs.py
index 9039038..0293e6c 100644
--- a/plugins/gin-workflow/src/scripts/workflow_core/specs.py
+++ b/plugins/gin-workflow/src/scripts/workflow_core/specs.py
@@ -367,6 +367,14 @@ def requirement_hash(root: Path, cfg: Mapping[str, Any], req_id: str) -> tuple[B
 
 
 def _bd(root: Path, argv: Sequence[str]) -> Any:
+    from . import task_markdown
+    from .tasks import backend
+
+    if backend(root) == "markdown":
+        value = task_markdown.query(root, argv)
+        if value is None:
+            raise SpecsError(f"task {' '.join(argv)} failed")
+        return value
     executable = shutil.which("bd")
     if executable is None:
         raise SpecsError("bd is not installed")
````

`plugins/gin-workflow/src/scripts/workflow_core/usage.py`:

````diff
diff --git a/plugins/gin-workflow/src/scripts/workflow_core/usage.py b/plugins/gin-workflow/src/scripts/workflow_core/usage.py
index 0305e2b..7fc8f16 100644
--- a/plugins/gin-workflow/src/scripts/workflow_core/usage.py
+++ b/plugins/gin-workflow/src/scripts/workflow_core/usage.py
@@ -67,6 +67,10 @@ def cost(totals: Mapping[str, int], price: Price | None) -> float | None:
 
 
 def _bd(repo: Path, argv: list[str]) -> Any:
+    from .tasks import backend
+
+    if backend(repo) == "markdown":
+        raise UsageError("AI usage tracking requires Beads (providers.task_tracking: beads)")
     executable = shutil.which("bd")
     if executable is None:
         raise UsageError("bd is not installed")
````

`plugins/gin-workflow/src/scripts/workflow_core/configuration.py`:

````diff
diff --git a/plugins/gin-workflow/src/scripts/workflow_core/configuration.py b/plugins/gin-workflow/src/scripts/workflow_core/configuration.py
index 8c70812..c2e9631 100644
--- a/plugins/gin-workflow/src/scripts/workflow_core/configuration.py
+++ b/plugins/gin-workflow/src/scripts/workflow_core/configuration.py
@@ -179,6 +179,12 @@ def _validate_portable(value: object, path: tuple[str, ...] = ()) -> None:
 
 
 def validate_portable_config(config: Mapping[str, Any]) -> None:
+    providers = config.get("providers", {})
+    task_tracking = providers.get("task_tracking") if isinstance(providers, Mapping) else None
+    if "team" in config and (
+        task_tracking.get("name") if isinstance(task_tracking, Mapping) else task_tracking
+    ) == "markdown":
+        raise ConfigValidationError("team mode requires Beads; providers.task_tracking: markdown is not supported")
     try:
         validate_config_schema(config)
     except DependencyUnavailableError:
````

`plugins/gin-workflow/src/scripts/workflow_core/setup_service.py`:

````diff
diff --git a/plugins/gin-workflow/src/scripts/workflow_core/setup_service.py b/plugins/gin-workflow/src/scripts/workflow_core/setup_service.py
index cfa9acd..7f401d5 100644
--- a/plugins/gin-workflow/src/scripts/workflow_core/setup_service.py
+++ b/plugins/gin-workflow/src/scripts/workflow_core/setup_service.py
@@ -4,6 +4,7 @@ from __future__ import annotations
 
 import difflib
 from pathlib import Path
+import shutil
 from typing import Any, Iterable, Mapping
 
 from .atomic import atomic_write_many
@@ -110,6 +111,7 @@ def detect(repository: Path, *, harness: str | None = None, **_: Any) -> dict[st
         "detected_harnesses": detected,
         "harness": selected,
         "project": detect_project(root),
+        "beads_installed": shutil.which("bd") is not None,
         "actions": [],
     }
````


### Track 3: Markdown provider
- **Dependencies**: Track 1
- **Provider role**: `backend`
- **Reasoning**: `medium` (adapter over a tested store; mirrors the fake provider's contract.)
- **Estimated complexity**: medium
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/workflow_providers/task_tracking_markdown.py`
  - Create: `tests/workflow_providers/test_task_tracking_markdown.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_providers/registry.py`
- **Interfaces (produced)**:
  - `MarkdownTaskTrackingProvider(repository_root: Path)` implementing `TaskTrackingProvider`; `metadata.name == "markdown"`; `sync` returns unavailable
  - `ProviderRegistry.from_effective_config` selects it for `providers.task_tracking: markdown`
- **Interfaces (consumed)**:
  - Track 1 `task_markdown.query`; `task_tracking.BeadsTaskTrackingProvider._task`, `task_tracking._closure_note`; `contracts.*`
- **Acceptance criteria**:
  - the fake provider's contract scenario passes against markdown
  - closure provenance survives a new provider instance; a mismatched re-close is invalid
  - the registry returns a `MarkdownTaskTrackingProvider` for `markdown`
- **Steps**:
  1. Add the test changes below. Run `python3 -m unittest tests.workflow_providers.test_task_tracking_markdown`: expect failures or import errors.
  2. Add the code changes below. Run the same command: expect `OK`.
  3. Commit on the track branch.

`plugins/gin-workflow/src/scripts/workflow_providers/task_tracking_markdown.py` (new):

````python
"""Task tracking over the Markdown store (`workflow_core.task_markdown`), for repositories without Beads."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from workflow_core import task_markdown

from .contracts import (
    ProviderBase,
    ProviderResult,
    TaskClosureRequest,
    TaskCreateRequest,
    TaskDependencyRecord,
    TaskPreflight,
    TaskReadiness,
    TaskRecord,
    TaskSyncRequest,
    TaskSyncResult,
    normalize_task_changes,
    validate_task_attributes,
    validate_task_status,
)
from .task_tracking import BeadsTaskTrackingProvider, _closure_note


class MarkdownTaskTrackingProvider(ProviderBase):
    provider_name = "markdown"
    provider_type = "task_tracking"
    capabilities = frozenset(
        {"task.create", "task.read", "task.update", "task.close", "task.dependency", "task.readiness",
         "task.preflight"}
    )

    def __init__(self, repository_root: Path) -> None:
        super().__init__()
        self.repository_root = Path(repository_root).resolve()

    def _run(self, *argv: str) -> ProviderResult[Any]:
        value = task_markdown.query(self.repository_root, argv)
        return ProviderResult.invalid(f"markdown task {argv[0]} failed") if value is None else ProviderResult.success(value)

    def _record(self, *argv: str) -> ProviderResult[TaskRecord]:
        ran = self._run(*argv)
        return ran if ran.value is None else BeadsTaskTrackingProvider._task(ran.value)

    def create_task(self, request: TaskCreateRequest, *, idempotency_key: str) -> ProviderResult[TaskRecord]:
        if not request.title.strip() or not idempotency_key:
            return ProviderResult.invalid("title and idempotency_key are required")
        if error := validate_task_status(request.status) or validate_task_attributes(request.attributes):
            return ProviderResult.invalid(error)
        if replay := self._replay("create_task", idempotency_key, request):
            return replay
        argv = ["create", request.title, "--status", request.status, "--description", request.description]
        if request.notes:
            argv += ["--notes", "\n".join(request.notes)]
        if request.acceptance_criteria:
            argv += ["--acceptance", "\n".join(request.acceptance_criteria)]
        for key, value in sorted(request.attributes.items()):
            argv += [f"--{key}", str(value)]
        return self._remember("create_task", idempotency_key, request, self._record(*argv))

    def read_task(self, task_id: str) -> ProviderResult[TaskRecord]:
        return self._record("show", task_id) if task_id.strip() else ProviderResult.invalid("task_id is required")

    def update_task(
        self, task_id: str, changes: Mapping[str, Any], *, idempotency_key: str
    ) -> ProviderResult[TaskRecord]:
        if not task_id.strip() or not changes or not idempotency_key:
            return ProviderResult.invalid("task_id, changes, and idempotency_key are required")
        normalized, error = normalize_task_changes(changes)
        if error:
            return ProviderResult.invalid(error)
        if replay := self._replay("update_task", idempotency_key, (task_id, changes)):
            return replay
        argv = ["update", task_id]
        for key, value in normalized.items():
            flag = "acceptance" if key == "acceptance_criteria" else key
            argv += [f"--{flag}", "\n".join(value) if isinstance(value, tuple) else str(value)]
        return self._remember("update_task", idempotency_key, (task_id, changes), self._record(*argv))

    def close_task(self, request: TaskClosureRequest, *, idempotency_key: str) -> ProviderResult[TaskRecord]:
        if not request.task_id.strip() or not request.closure_reason.strip() or not request.acceptance_evidence \
                or not idempotency_key:
            return ProviderResult.invalid(
                "task_id, closure_reason, acceptance_evidence, and idempotency_key are required"
            )
        if replay := self._replay("close_task", idempotency_key, request):
            return replay
        current = self.read_task(request.task_id)
        if current.value is None:
            return current
        matches = (current.value.acceptance_evidence, current.value.closure_reason) == (
            request.acceptance_evidence, request.closure_reason)
        if current.value.status == "closed":
            if matches:
                return ProviderResult.success(current.value, idempotent=True)
            return ProviderResult.invalid("closed task provenance does not match closure request")
        if not matches:
            noted = self._run("update", request.task_id, "--append-notes", _closure_note(request))
            if noted.value is None:
                return noted
        closed = self._run("close", request.task_id, "--reason", request.closure_reason)
        if closed.value is None:
            return closed
        return self._remember("close_task", idempotency_key, request, self.read_task(request.task_id))

    def add_dependency(
        self, dependency: TaskDependencyRecord, *, idempotency_key: str
    ) -> ProviderResult[TaskDependencyRecord]:
        if not idempotency_key or dependency.dependency_type != "blocks":
            return ProviderResult.invalid("valid blocking dependency and idempotency_key are required")
        if replay := self._replay("add_dependency", idempotency_key, dependency):
            return replay
        added = self._run("dep", "add", dependency.task_id, dependency.depends_on_task_id)
        result = added if added.value is None else ProviderResult.success(dependency)
        return self._remember("add_dependency", idempotency_key, dependency, result)

    def readiness(self, task_id: str) -> ProviderResult[TaskReadiness]:
        shown = self.read_task(task_id)
        if shown.value is None:
            return shown
        blocked = self._run("blocked")
        if blocked.value is None:
            return blocked
        blockers = next((tuple(row["blocked_by"]) for row in blocked.value if row["id"] == task_id), ())
        return ProviderResult.success(TaskReadiness(task_id, shown.value.status == "open" and not blockers, blockers))

    def preflight(self) -> ProviderResult[TaskPreflight]:
        return ProviderResult.success(TaskPreflight("markdown", "1", self.capabilities, True))

    def sync(self, request: TaskSyncRequest, *, idempotency_key: str, **_: Any) -> ProviderResult[TaskSyncResult]:
        return ProviderResult.unavailable("markdown task tracking has no sync; the files are in git")
````

`tests/workflow_providers/test_task_tracking_markdown.py` (new):

````python
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.models import EffectiveConfig  # noqa: E402
from workflow_providers.contracts import (  # noqa: E402
    OperationStatus,
    TaskClosureRequest,
    TaskCreateRequest,
    TaskDependencyRecord,
    TaskSyncRequest,
)
from workflow_providers.registry import ProviderRegistry  # noqa: E402
from workflow_providers.task_tracking_markdown import MarkdownTaskTrackingProvider  # noqa: E402


class MarkdownTaskTrackingProviderTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        self.provider = MarkdownTaskTrackingProvider(self.root)

    def tearDown(self):
        self._directory.cleanup()

    def test_same_contract_scenario_as_the_fake_provider(self):
        provider = self.provider
        dependency = provider.create_task(TaskCreateRequest("dependency"), idempotency_key="dep")
        created = provider.create_task(
            TaskCreateRequest("Task", notes=("implementation note",), acceptance_criteria=("tests pass",)),
            idempotency_key="create",
        )
        edge = TaskDependencyRecord(created.value.task_id, dependency.value.task_id)
        provider.add_dependency(edge, idempotency_key="edge")
        replayed_edge = provider.add_dependency(edge, idempotency_key="edge")
        blocked = provider.readiness(created.value.task_id)
        provider.close_task(
            TaskClosureRequest(dependency.value.task_id, "done", ("unit tests",)), idempotency_key="close-dependency"
        )
        ready = provider.readiness(created.value.task_id)
        closed = provider.close_task(
            TaskClosureRequest(created.value.task_id, "accepted", ("tests:0", "review:approved")),
            idempotency_key="close-task",
        )

        self.assertEqual(("implementation note",), created.value.notes)
        self.assertEqual(("tests pass",), created.value.acceptance_criteria)
        self.assertTrue(replayed_edge.idempotent)
        self.assertEqual((dependency.value.task_id,), blocked.value.blockers)
        self.assertTrue(ready.value.ready)
        self.assertEqual("closed", closed.value.status)
        self.assertEqual(("tests:0", "review:approved"), closed.value.acceptance_evidence)
        self.assertEqual("accepted", closed.value.closure_reason)

    def test_closed_provenance_survives_a_new_provider_and_mismatch_is_invalid(self):
        task = self.provider.create_task(TaskCreateRequest("T"), idempotency_key="c").value.task_id
        request = TaskClosureRequest(task, "accepted", ("tests:0",))
        self.provider.close_task(request, idempotency_key="close")
        fresh = MarkdownTaskTrackingProvider(self.root)
        self.assertTrue(fresh.close_task(request, idempotency_key="other").idempotent)
        mismatch = fresh.close_task(TaskClosureRequest(task, "other", ("x",)), idempotency_key="m")
        self.assertEqual(OperationStatus.INVALID, mismatch.status)

    def test_update_attributes_unknown_task_and_sync(self):
        task = self.provider.create_task(TaskCreateRequest("T"), idempotency_key="c").value.task_id
        updated = self.provider.update_task(task, {"assignee": "dev", "status": "in_progress"}, idempotency_key="u")
        self.assertEqual(("dev", "in_progress"), (updated.value.attributes["assignee"], updated.value.status))
        self.assertIsNone(self.provider.read_task("nope-1").value)
        self.assertEqual(OperationStatus.UNAVAILABLE,
                         self.provider.sync(TaskSyncRequest("flush"), idempotency_key="s").status)
        self.assertTrue(self.provider.preflight().value.healthy)

    def test_registry_selects_markdown(self):
        config = EffectiveConfig({"providers": {"task_tracking": "markdown"}}, self.root)
        registry = ProviderRegistry.from_effective_config(config)
        self.assertIsInstance(registry.task_tracking, MarkdownTaskTrackingProvider)
        self.assertEqual("markdown", registry.task_tracking.metadata.name)


if __name__ == "__main__":
    unittest.main()
````

`plugins/gin-workflow/src/scripts/workflow_providers/registry.py`:

````diff
diff --git a/plugins/gin-workflow/src/scripts/workflow_providers/registry.py b/plugins/gin-workflow/src/scripts/workflow_providers/registry.py
index f9d0ad9..deff5f1 100644
--- a/plugins/gin-workflow/src/scripts/workflow_providers/registry.py
+++ b/plugins/gin-workflow/src/scripts/workflow_providers/registry.py
@@ -43,6 +43,7 @@ from .knowledge import ObsidianKnowledgeProvider, RepositoryKnowledgeProvider
 from .notifications import TelegramNotificationProvider
 from .review import ReviewLedgerProvider
 from .task_tracking import BeadsTaskTrackingProvider
+from .task_tracking_markdown import MarkdownTaskTrackingProvider
 from .workspace import WorktreeWorkspaceProvider
 from .antigravity_worker import (
     AntigravityWorkerAdapter,
@@ -137,6 +138,8 @@ class ProviderRegistry:
                 )
             except ValueError as error:
                 raise RegistryError(str(error)) from error
+        elif task_name == "markdown":
+            task_tracking = MarkdownTaskTrackingProvider(root)
         elif task_name == "fake":
             task_tracking = FakeTaskTrackingProvider()
         else:
````


### Track 4: Skills, agents, safety hook, setup skill, docs
- **Dependencies**: Track 2
- **Provider role**: `backend`
- **Reasoning**: `low` (mechanical text edits and one bash fallback, each guarded by a test.)
- **Estimated complexity**: low
- **Files**:
  - Create: `tests/test_no_direct_bd.py`
  - Modify: `plugins/gin-workflow/src/scripts/safety-check.sh`
  - Modify: `tests/test_safety_check.py`
  - Modify: `tests/workflow_core/test_assignments.py`
  - Modify: `plugins/gin-workflow/src/agents/bead-worker.md`
  - Modify: `plugins/gin-workflow/src/agents/developer.md`
  - Modify: `plugins/gin-workflow/src/skills/discuss/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/execute/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/gin-knowledge/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/gin-parallel-agents/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/orchestrate/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/progress/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/report/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/roadmap/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/setup/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/ship/SKILL.md`
  - Modify: `README.md`
  - Modify: `docs/reference/cli.md`
  - Modify: `docs/reference/config.md`
  - Modify: `docs/concepts/providers.md`
- **Interfaces (produced)**:
  - skills and agents call `gin-workflow task …` instead of `bd …` (allowlist: `beads-migration`, `team-setup`, `gin-team`)
  - `/setup` step 6 offers `markdown` only when `beads_installed` is false
- **Interfaces (consumed)**:
  - Track 2 `gin-workflow task` and `detect.beads_installed`
- **Acceptance criteria**:
  - `tests/test_no_direct_bd.py` finds no `` `bd `` in skills/agents outside the allowlist
  - the hook parses the payload with `python3` when `jq` is not on `PATH` and still blocks `--no-verify` (the new test fails on the old script)
  - docs describe `gin-workflow task` and `providers.task_tracking`
- **Steps**:
  1. Add the test changes below. Run `python3 -m unittest tests.test_no_direct_bd tests.test_safety_check tests.workflow_core.test_assignments`: expect failures or import errors.
  2. Add the code changes below. Run the same command: expect `OK`.
  3. Commit on the track branch.

`tests/test_no_direct_bd.py` (new):

````python
"""Skills and agents reach task tracking through `gin-workflow task`, so the markdown backend works without `bd`."""

from pathlib import Path
import re
import unittest

SRC = Path(__file__).resolve().parents[1] / "plugins/gin-workflow/src"
BEADS_ONLY = {"beads-migration", "team-setup", "gin-team"}


class TestNoDirectBd(unittest.TestCase):
    def test_skills_and_agents_do_not_call_bd_directly(self):
        offenders = []
        for path in sorted([*SRC.glob("skills/*/*.md"), *SRC.glob("agents/*.md")]):
            if path.parent.name in BEADS_ONLY:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if re.search(r"`bd\b", line):
                    offenders.append(f"{path.relative_to(SRC)}:{number}")
        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
````

`plugins/gin-workflow/src/scripts/safety-check.sh`:

````diff
diff --git a/plugins/gin-workflow/src/scripts/safety-check.sh b/plugins/gin-workflow/src/scripts/safety-check.sh
index 377ef96..b0df358 100755
--- a/plugins/gin-workflow/src/scripts/safety-check.sh
+++ b/plugins/gin-workflow/src/scripts/safety-check.sh
@@ -16,8 +16,14 @@ if [ ! -t 0 ]; then
         exit 2
       }
       CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty' 2>/dev/null) || CWD=""
+    elif command -v python3 >/dev/null 2>&1; then
+      COMMAND=$(printf '%s' "$INPUT" | python3 -c 'import json, sys; print((json.load(sys.stdin).get("tool_input") or {}).get("command") or "")' 2>/dev/null) || {
+        echo "Error: failed to parse PreToolUse hook payload as JSON." >&2
+        exit 2
+      }
+      CWD=$(printf '%s' "$INPUT" | python3 -c 'import json, sys; print(json.load(sys.stdin).get("cwd") or "")' 2>/dev/null) || CWD=""
     else
-      echo "Error: jq is required to parse PreToolUse hook payload but is missing." >&2
+      echo "Error: jq or python3 is required to parse PreToolUse hook payload but neither is installed." >&2
       exit 2
     fi
   else
````

`tests/test_safety_check.py`:

````diff
diff --git a/tests/test_safety_check.py b/tests/test_safety_check.py
index c748f2c..6f1f49a 100644
--- a/tests/test_safety_check.py
+++ b/tests/test_safety_check.py
@@ -1,7 +1,10 @@
 """safety-check.sh blocks `--no-verify` so the gin-workflow git hooks cannot be skipped."""
 
+import json
 from pathlib import Path
+import shutil
 import subprocess
+import tempfile
 import unittest
 
 SCRIPT = Path(__file__).resolve().parents[1] / "plugins/gin-workflow/src/scripts/safety-check.sh"
@@ -22,5 +25,17 @@ class TestNoVerifyBlocked(unittest.TestCase):
             self.assertEqual(0, exit_code(command), command)
 
 
+class TestPayloadWithoutJq(unittest.TestCase):
+    def test_python3_parses_the_payload_when_jq_is_missing(self):
+        with tempfile.TemporaryDirectory() as directory:
+            for tool in ("bash", "cat", "git", "realpath", "python3"):
+                Path(directory, tool).symlink_to(shutil.which(tool))
+            for command, expected in (("git commit --no-verify -m x", 2), ("git status", 0)):
+                payload = json.dumps({"tool_input": {"command": command}, "cwd": directory})
+                done = subprocess.run([str(Path(directory, "bash")), str(SCRIPT)], input=payload.encode(),
+                                      env={"PATH": directory}, capture_output=True)
+                self.assertEqual(expected, done.returncode, (command, done.stderr))
+
+
 if __name__ == "__main__":
     unittest.main()
````

`tests/workflow_core/test_assignments.py`:

````diff
diff --git a/tests/workflow_core/test_assignments.py b/tests/workflow_core/test_assignments.py
index 11a25d0..1697f27 100644
--- a/tests/workflow_core/test_assignments.py
+++ b/tests/workflow_core/test_assignments.py
@@ -69,7 +69,7 @@ class AssignmentTests(unittest.TestCase):
         self.assertIn("every track has a configured role and low/medium/high reasoning", planning)
         self.assertLess(
             orchestrate.index("resolve_all_assignments"),
-            orchestrate.index("bd create"),
+            orchestrate.index("gin-workflow task create"),
         )
 
     def test_parent_deliverable_vs_track_bead_and_handoff_contracts(self):
````

`plugins/gin-workflow/src/agents/bead-worker.md`:

````diff
diff --git a/plugins/gin-workflow/src/agents/bead-worker.md b/plugins/gin-workflow/src/agents/bead-worker.md
index ace2b6c..74d9201 100644
--- a/plugins/gin-workflow/src/agents/bead-worker.md
+++ b/plugins/gin-workflow/src/agents/bead-worker.md
@@ -10,12 +10,12 @@ model: standard_impl
 You execute, validate, and report on one assigned bead (task track). Follow the `execute` skill.
 
 ## Inputs
-1. `bd show <track-id> --json`: status, dependencies, description, acceptance criteria.
+1. `gin-workflow task show <track-id> --json`: status, dependencies, description, acceptance criteria.
 2. In-scope files from the matching track in `.planning/plans/` (its `Files:` list), or derived from the bead description and acceptance criteria for a standalone unit.
 3. The relevant source and test files, to learn current conventions.
 
 ## Guidelines
-1. Edit only the in-scope files. If changes outside them are needed, record the blocker in the bead (`bd update <id> --notes`), send a `work_blocked` notification when `telegram-notify` is configured, and stop.
+1. Edit only the in-scope files. If changes outside them are needed, record the blocker in the bead (`gin-workflow task update <id> --notes`), send a `work_blocked` notification when `telegram-notify` is configured, and stop.
 2. Record notable discoveries, workarounds, or decisions per the `gin-knowledge` skill.
 3. Run the relevant tests or checks against the acceptance criteria. On failure, follow `gin-debugging` and fix locally.
````

`plugins/gin-workflow/src/agents/developer.md`:

````diff
diff --git a/plugins/gin-workflow/src/agents/developer.md b/plugins/gin-workflow/src/agents/developer.md
index 489f9b7..996ee1e 100644
--- a/plugins/gin-workflow/src/agents/developer.md
+++ b/plugins/gin-workflow/src/agents/developer.md
@@ -14,7 +14,7 @@ You do not redefine architecture, expand scope, or change ownership boundaries s
 ## Inputs
 Before editing:
 
-1. Read the assignment: `bd show <id>` (dependencies, notes, acceptance criteria) and the plan track, whose file list is the write boundary.
+1. Read the assignment: `gin-workflow task show <id>` (dependencies, notes, acceptance criteria) and the plan track, whose file list is the write boundary.
 2. Read `gin-workflow state --format json`: `project.shape`, `project.rigor`, and `project.verify_commands`.
 3. Load **one** shape appendix from the plugin references: `references/shape-frontend.md` for `frontend`, `references/shape-backend.md` for `backend`; for `fullstack` or `library`, the one matching the task's files, and both only when the task spans both.
 4. Look up related code on demand: `codegraph explore "<symbols>"` when `.codegraph/` exists, else grep and read.
````

`plugins/gin-workflow/src/skills/discuss/SKILL.md`:

````diff
diff --git a/plugins/gin-workflow/src/skills/discuss/SKILL.md b/plugins/gin-workflow/src/skills/discuss/SKILL.md
index 128f476..329390f 100644
--- a/plugins/gin-workflow/src/skills/discuss/SKILL.md
+++ b/plugins/gin-workflow/src/skills/discuss/SKILL.md
@@ -9,9 +9,9 @@ description: Clarify a requirement into a confirmed design spec before any plann
 
 # Discuss
 
-Turn a requirement into a confirmed design. The user starts with an idea, not a Beads task; never ask them to run `bd` during discovery.
+Turn a requirement into a confirmed design. The user starts with an idea, not a Beads task; never ask them to run `gin-workflow task` during discovery.
 
-**Roadmap epic:** `/discuss <epic-id>` starts from `bd show <id> --json` and its roadmap entry. Stop if the id is missing, not an epic, or closed; warn if its dependencies are still open. Pass `--workflow-id <epic-id>` to every `state` and `record` call and never create another epic.
+**Roadmap epic:** `/discuss <epic-id>` starts from `gin-workflow task show <id> --json` and its roadmap entry. Stop if the id is missing, not an epic, or closed; warn if its dependencies are still open. Pass `--workflow-id <epic-id>` to every `state` and `record` call and never create another epic.
 
 **Hard gate:** no code, scaffolding, implementation skill, plan, or Beads task until the user explicitly confirms the design. This applies to every request, however simple; a simple design can be a few sentences, but it is still presented and confirmed.
````

`plugins/gin-workflow/src/skills/execute/SKILL.md`:

````diff
diff --git a/plugins/gin-workflow/src/skills/execute/SKILL.md b/plugins/gin-workflow/src/skills/execute/SKILL.md
index ecc3dc1..d44df7b 100644
--- a/plugins/gin-workflow/src/skills/execute/SKILL.md
+++ b/plugins/gin-workflow/src/skills/execute/SKILL.md
@@ -13,7 +13,7 @@ Implement one ready work unit inside its approved scope and record evidence.
 
 ## 1. Select and review
 1. Require `orchestration_ready`. For a standalone or pre-existing bead, record it as its own epic instead of a plan cycle: `gin-workflow record orchestration-ready --workflow-id <bead> --epic <bead> --evidence <bead> --actor <id>`, and pass `--workflow-id <bead>` to every later `state`/`record` call for it. An epic labelled `roadmap` with no confirmed spec: refuse and recommend `/discuss <epic-id>`; never record it as its own epic.
-2. Pick one unit from `bd ready`; read it with `bd show <id> --json`; claim it with `bd update <id> --status in_progress`.
+2. Pick one unit from `gin-workflow task ready`; read it with `gin-workflow task show <id> --json`; claim it with `gin-workflow task update <id> --status in_progress`.
    With `project.team.enabled`, pick with `gin-workflow team ready` and claim with `gin-workflow team claim <id>` (the `gin-team` skill).
 3. Resolve file scope and validation intent from the plan track, or from the task description and acceptance criteria for a standalone unit. Review critically and raise concerns before starting.
 4. Work in the isolated worktree. Never implement on main/master without explicit consent.
@@ -25,7 +25,7 @@ Implement one ready work unit inside its approved scope and record evidence.
 - Run `gin-workflow rules --files <scope files>` and give its output to the `developer` agent (or follow it when executing directly). Rules never widen the scope.
 - On a `greenfield` project, a task that sets up lint, typecheck, or test starts from the `suggest` snippets of the missing checks in `checks_details.rules.tool_checks` of `gin-workflow setup doctor --format json`.
 - Validate immediately and keep the command output as evidence. Do not proceed while tests fail or acceptance criteria are unmet.
-- **Stop and ask** on a blocker, a plan gap, an unclear instruction, or repeated validation failure. Leave the bead in progress with a `bd update <id> --notes` entry; do not guess. Failures route to the `gin-debugging` skill.
+- **Stop and ask** on a blocker, a plan gap, an unclear instruction, or repeated validation failure. Leave the bead in progress with a `gin-workflow task update <id> --notes` entry; do not guess. Failures route to the `gin-debugging` skill.
 - Scope or execution-strategy changes and production-impacting parallel work need explicit approval first.
 - Record notable decisions or risks per `gin-knowledge`.
 
@@ -39,7 +39,7 @@ Execute directly for sequential work, a single agent, three or fewer tasks, or n
 
 ## 4. Complete
 1. Request review through the `review` skill and wait for a terminal review state.
-2. Once tests and review pass, run `gin-workflow usage collect --bead <id> --best-effort`, then close the track bead (`bd close <id> --reason "<evidence>"`); this unblocks dependents and needs no PR or merge.
+2. Once tests and review pass, run `gin-workflow usage collect --bead <id> --best-effort`, then close the track bead (`gin-workflow task close <id> --reason "<evidence>"`); this unblocks dependents and needs no PR or merge.
 3. Commit and push the feature branch. Never report "waiting for PR merge" without a real PR link. Stop at handoff and offer two options:
    1. Xin lệnh tạo PR từ nhánh feature đã push.
    2. Giữ nhánh feature đã push và tiếp tục chuyển sang track tiếp theo sử dụng artifact vừa sinh.
````

`plugins/gin-workflow/src/skills/gin-knowledge/SKILL.md`:

````diff
diff --git a/plugins/gin-workflow/src/skills/gin-knowledge/SKILL.md b/plugins/gin-workflow/src/skills/gin-knowledge/SKILL.md
index d659b3c..596dca8 100644
--- a/plugins/gin-workflow/src/skills/gin-knowledge/SKILL.md
+++ b/plugins/gin-workflow/src/skills/gin-knowledge/SKILL.md
@@ -5,13 +5,13 @@ description: Use to capture durable decisions, constraints, and lessons during w
 
 # Knowledge
 
-Knowledge lives in `.planning/knowledge/` (the configured `artifacts.knowledge`) as small Markdown records. Short facts that every session needs go in `bd remember "<fact>"`. Knowledge is looked up on demand and never copied wholesale into a stage's context.
+Knowledge lives in `.planning/knowledge/` (the configured `artifacts.knowledge`) as small Markdown records. Short facts that every session needs go in `gin-workflow task remember "<fact>"`. Knowledge is looked up on demand and never copied wholesale into a stage's context.
 
 ## Capture (during execute)
 1. Capture only reusable knowledge: compatibility constraints, environment limits, architectural decisions, counterintuitive APIs, and debugging lessons that will recur. Do not capture routine steps, transient worker state, private reasoning, or self-assessment.
-2. Search first (`grep -ril "<topic>" .planning/knowledge`, `bd memories <keyword>`) and update an existing record instead of duplicating it.
+2. Search first (`grep -ril "<topic>" .planning/knowledge`, `gin-workflow task memories <keyword>`) and update an existing record instead of duplicating it.
 3. Write `.planning/knowledge/<topic>.md` with **Context**, **Decision/Solution**, **Consequences**, **References** (paths, beads), and **Scope**.
-4. Mention the record in the bead notes (`bd update <id> --notes`). If the knowledge location is unavailable, say so in the handoff; never work around it.
+4. Mention the record in the bead notes (`gin-workflow task update <id> --notes`). If the knowledge location is unavailable, say so in the handoff; never work around it.
 
 ## Reconcile (during ship, after verification and before closing beads)
 1. Find the records related to the task.
````

`plugins/gin-workflow/src/skills/gin-parallel-agents/SKILL.md`:

````diff
diff --git a/plugins/gin-workflow/src/skills/gin-parallel-agents/SKILL.md b/plugins/gin-workflow/src/skills/gin-parallel-agents/SKILL.md
index b659a61..8bf5f0e 100644
--- a/plugins/gin-workflow/src/skills/gin-parallel-agents/SKILL.md
+++ b/plugins/gin-workflow/src/skills/gin-parallel-agents/SKILL.md
@@ -15,7 +15,7 @@ Dispatch one agent per independent problem domain and let them work concurrently
 Do not use it for related failures (fixing one may fix the others), exploratory debugging, work that needs whole-system understanding, or agents that would edit the same files. Production-impacting parallel work or an execution-strategy change needs explicit user approval, recorded first.
 
 ## Pattern
-1. **Group** the work by what it affects, and confirm each group is dependency-ready in Beads (`bd ready`).
+1. **Group** the work by what it affects, and confirm each group is dependency-ready in Beads (`gin-workflow task ready`).
 2. **Brief each agent** with:
    - one focused goal (one test file, subsystem, or bead);
    - its dependencies;
@@ -25,7 +25,7 @@ Do not use it for related failures (fixing one may fix the others), exploratory
    - the expected return (root cause, changes, evidence).
    Include the exact error messages and test names. Never pass your transcript, secrets, or concrete model names.
 3. **Dispatch** through the harness's worker or subagent mechanism within the configured concurrency, giving each agent its own worktree (`gin-worktrees`) and one bead claim.
-4. **Integrate**: read each summary, record the outcome in the bead (`bd update <id> --notes`), check for edits outside the approved scopes or conflicting changes, run the full suite, and spot-check, since agents make systematic errors.
+4. **Integrate**: read each summary, record the outcome in the bead (`gin-workflow task update <id> --notes`), check for edits outside the approved scopes or conflicting changes, run the full suite, and spot-check, since agents make systematic errors.
 
 ## Example brief
 ```
````

`plugins/gin-workflow/src/skills/gin-sdd/SKILL.md`:

````diff
diff --git a/plugins/gin-workflow/src/skills/gin-sdd/SKILL.md b/plugins/gin-workflow/src/skills/gin-sdd/SKILL.md
index 3e6dc89..7690f51 100644
--- a/plugins/gin-workflow/src/skills/gin-sdd/SKILL.md
+++ b/plugins/gin-workflow/src/skills/gin-sdd/SKILL.md
@@ -8,7 +8,7 @@ description: Use in a lifecycle stage when `project.layout` is `sdd` — change
 Applies only when `gin-workflow state --format json` reports `project.layout: sdd`. Paths come from `artifacts.specs` (default `docs/specs`) and `artifacts.changes` (default `docs/changes`). Every `state`/`record` call for a change passes `--workflow-id <epic>`. All commands are `gin-workflow specs <command>`; exit 1 means findings to fix, exit 2 means wrong usage or layout.
 
 ## discuss
-1. After the user confirms the design: `bd create --type epic --title "<title>"` (a roadmap epic is reused as is) → `specs new <slug> --epic <epic>` creates `<changes>/<epic>-<slug>/`.
+1. After the user confirms the design: `gin-workflow task create --type epic --title "<title>"` (a roadmap epic is reused as is) → `specs new <slug> --epic <epic>` creates `<changes>/<epic>-<slug>/`.
 2. Write `proposal.md`, `spec-delta.md`, and `design.md` in that folder. `proposal.md` lists `## User Stories` from `specs template user-story.md`, each with `REQ:`. Each new requirement gets its ID from `specs next-id <cap>`; a `MODIFIED` or `REMOVED` block puts the output of `specs hash <REQ-ID>` on the line after its heading, and a `REMOVED` block adds `Reason: <why>`. An architecture decision also gets `docs/adr/NNNN-<slug>.md` from `specs template adr.md`.
 3. `specs lint --change <epic>` must exit 0.
 4. `project.spec_review`:
@@ -19,7 +19,7 @@ Applies only when `gin-workflow state --format json` reports `project.layout: sd
 Write `<change>/plan.md`. Each track's Metadata adds `Requirements: REQ-…`; every `ADDED`/`MODIFIED` REQ in the delta belongs to at least one track. Record `plan-approved --workflow-id <epic>`.
 
 ## orchestrate
-Reuse the epic as parent. Each track bead: `bd create --parent <epic> --spec-id <epic>-<slug> --labels req:<REQ-ID>,…` from its `Requirements:`.
+Reuse the epic as parent. Each track bead: `gin-workflow task create --parent <epic> --spec-id <epic>-<slug> --labels req:<REQ-ID>,…` from its `Requirements:`.
 
 ## execute and review
 New or changed tests carry the REQ-ID in the test name or a comment (`# REQ-AUTH-003`). The reviewer checks that each scenario of the track's REQs has a test.
````

`plugins/gin-workflow/src/skills/orchestrate/SKILL.md`:

````diff
diff --git a/plugins/gin-workflow/src/skills/orchestrate/SKILL.md b/plugins/gin-workflow/src/skills/orchestrate/SKILL.md
index 26a8e0c..16818ec 100644
--- a/plugins/gin-workflow/src/skills/orchestrate/SKILL.md
+++ b/plugins/gin-workflow/src/skills/orchestrate/SKILL.md
@@ -19,8 +19,8 @@ Turn an approved plan into durable Beads state. Beads is the only source of stat
 3. Resolve routes for the whole batch before any durable write: build an `AssignmentRequest(task_id, provider_role, reasoning, main_harness, workflow_id)` per track and call `workflow_core.assignments.resolve_all_assignments(requests, config, local)` (`PYTHONPATH=<plugin>/scripts`; `config` is the generated effective config and `local` comes from `workflow_core.provider_config.load_provider_local_config(repo)`). If anything is unresolved, report all diagnostics and stop. Otherwise persist each preview with `write_assignment_manifest`. Concrete provider/model names never enter Beads or the plan.
 4. Distinguish Parent Bead (Deliverable) vs Track Beads (Work Units):
    - **Parent Bead (Deliverable / Epic)**: the overall deliverable. Merge holds such as "remain open until human-confirmed merge" belong only here.
-   - **Track Beads (Work Units)**: one per plan track (`bd create --parent <epic>`). Acceptance criteria are strictly technical (in-scope code, tests, review approval). Never copy parent merge holds into tracks.
-5. Mirror dependencies with `bd dep add <blocked> <blocker>` and check `bd ready` / `bd show`. Each track closes after tests and review pass, which unblocks its dependents.
+   - **Track Beads (Work Units)**: one per plan track (`gin-workflow task create --parent <epic>`). Acceptance criteria are strictly technical (in-scope code, tests, review approval). Never copy parent merge holds into tracks.
+5. Mirror dependencies with `gin-workflow task dep add <blocked> <blocker>` and check `gin-workflow task ready` / `gin-workflow task show`. Each track closes after tests and review pass, which unblocks its dependents.
 6. Isolate by default: create a worktree per the `gin-worktrees` skill under `.planning/worktrees/`. Disabling isolation or running on the current branch needs explicit approval, recorded first.
 7. Production-impacting parallel work or an execution-strategy change needs explicit approval.
 8. `gin-workflow record orchestration-ready --epic <parent-bead> --evidence "<bead-ids>; <worktree>; <branch>" --actor <id>`. The epic lets `gin-workflow state` derive `implementation_complete` once every track is closed.
````

`plugins/gin-workflow/src/skills/progress/SKILL.md`:

````diff
diff --git a/plugins/gin-workflow/src/skills/progress/SKILL.md b/plugins/gin-workflow/src/skills/progress/SKILL.md
index f6f4cb3..ad52f2f 100644
--- a/plugins/gin-workflow/src/skills/progress/SKILL.md
+++ b/plugins/gin-workflow/src/skills/progress/SKILL.md
@@ -11,9 +11,9 @@ description: Report Beads task status, blockers, open waivers, and next ready wo
 
 Read-only status report.
 
-1. Query Beads: `bd list --status open,in_progress`, `bd ready`, `bd blocked`, and `bd show <id>` for requested tasks. For a sprint: `bd list --label sprint:<name> --all --json` gives the epics; `bd list --parent <epic> --all --json` gives each one's tracks.
+1. Query Beads: `gin-workflow task list --status open,in_progress`, `gin-workflow task ready`, `gin-workflow task blocked`, and `gin-workflow task show <id>` for requested tasks. For a sprint: `gin-workflow task list --label sprint:<name> --all --json` gives the epics; `gin-workflow task list --parent <epic> --all --json` gives each one's tracks.
 2. Group as Pending, Active, Complete, and Failed. Recommend active dependencies first, then ready work by priority, then root blockers.
 3. Add review status (`python3 review-ledger.py status --bead-id <id>`) and gate state (`gin-workflow state --format json`) when relevant, and recent `/quick` runs (`recent_quick` in `gin-workflow state`).
-4. Report open gate waivers (gates shown as `waived(<reason>)` by `gin-workflow state`) and check their follow-up tasks with `bd show`, so waivers do not become a habit.
+4. Report open gate waivers (gates shown as `waived(<reason>)` by `gin-workflow state`) and check their follow-up tasks with `gin-workflow task show`, so waivers do not become a habit.
 5. Label worker and worktree details as derived runtime metadata, never authoritative state.
 6. Return the report. Never mutate state or chain into another stage.
````

`plugins/gin-workflow/src/skills/report/SKILL.md`:

````diff
diff --git a/plugins/gin-workflow/src/skills/report/SKILL.md b/plugins/gin-workflow/src/skills/report/SKILL.md
index 47bb890..cdc0414 100644
--- a/plugins/gin-workflow/src/skills/report/SKILL.md
+++ b/plugins/gin-workflow/src/skills/report/SKILL.md
@@ -12,7 +12,7 @@ description: Report AI usage per bead or epic — tokens and estimated cost per
 Read-only usage report. Summaries are written into each bead's metadata (`ai_usage`) when the bead closes (`execute`) or the epic ships (`ship`); this skill only reads them.
 
 1. Scope from the request: one bead (`--bead <id>`), an epic and its tracks (`--epic <id>`), a sprint's epics and their tracks (`--sprint <name>`, epics labelled `sprint:<name>`), beads closed since a date (`--since YYYY-MM-DD`), or every collected bead (no flag).
-2. Run `gin-workflow usage report <scope> --format json`. Exit 2 means `bd` is missing or failed: show the error and stop.
+2. Run `gin-workflow usage report <scope> --format json`. Exit 2 means the task backend is missing or failed (usage reports need Beads): show the error and stop.
 3. Present:
    - Each bead: cost, title, and its quality signals.
    - Totals per model (input, output, cache read, cache write, cost) and per stage (`discuss`, `plan`, `orchestrate`, `execute`, `review`, `verify`, `ship`, `quick`).
````

`plugins/gin-workflow/src/skills/roadmap/SKILL.md`:

````diff
diff --git a/plugins/gin-workflow/src/skills/roadmap/SKILL.md b/plugins/gin-workflow/src/skills/roadmap/SKILL.md
index 1af8fda..4c7c2b3 100644
--- a/plugins/gin-workflow/src/skills/roadmap/SKILL.md
+++ b/plugins/gin-workflow/src/skills/roadmap/SKILL.md
@@ -13,18 +13,18 @@ On `/roadmap` only. Outside the lifecycle: it records no gate. One question per
 3. `brownfield` or `legacy` needs the tech-doc folder (`.planning/codebase/`, or `artifacts.codebase`, default `docs/codebase/`, with the SDD layout); if it is missing, stop and recommend `/tech-doc`. `greenfield` needs a product brief: ask for a path or the text.
 
 ## Steps
-1. **Read** every file of the tech-doc folder, subsystem subfolders included, yourself (no subagent summaries: epic dependencies come from reading across files), or the product brief; then living specs (or `.planning/specs/`), the roadmap file if it exists, and `bd list --label roadmap --all --json`. With `.codegraph/`, check load-bearing claims with `codegraph explore`.
+1. **Read** every file of the tech-doc folder, subsystem subfolders included, yourself (no subagent summaries: epic dependencies come from reading across files), or the product brief; then living specs (or `.planning/specs/`), the roadmap file if it exists, and `gin-workflow task list --label roadmap --all --json`. With `.codegraph/`, check load-bearing claims with `codegraph explore`.
 2. **Clarify** with the PM (at most `project.max_questions` questions (`gin-workflow state --format json`, default 8); at the cap, say the scope is too large or unclear and propose splitting it into smaller epics, or list the rest as assumptions): business goals, milestones, team capacity, operating constraints (downtime, data migration), exclusions. Do not number questions against the cap (no `2/8`): it is a ceiling, not a target; ask only what changes the roadmap.
 3. **Propose 2–3 ways to split the work** (for example by bounded context, by risk, by business value) with trade-offs; lead with your recommendation.
-4. **Present the roadmap**. Each epic: title, `Epic: <id>`, `Goal:`, `Scope:`, `Out of scope:`, `Depends on:` (epic ids), `Evidence:` (tech-doc file and section, or the brief), `Risks:`. A new id is `<prefix>-rm-<slug>` (`bd config get issue_prefix`; slug of lowercase letters, digits, and hyphens) and never changes once written. Check that dependencies are acyclic. On a re-run, present only what differs from the file and Beads. Revise until the PM explicitly confirms.
+4. **Present the roadmap**. Each epic: title, `Epic: <id>`, `Goal:`, `Scope:`, `Out of scope:`, `Depends on:` (epic ids), `Evidence:` (tech-doc file and section, or the brief), `Risks:`. A new id is `<prefix>-rm-<slug>` (`gin-workflow task config get issue_prefix`; slug of lowercase letters, digits, and hyphens) and never changes once written. Check that dependencies are acyclic. On a re-run, present only what differs from the file and Beads. Revise until the PM explicitly confirms.
 5. **Write** the file from `gin-workflow specs template roadmap.md` on branch `roadmap/<topic>` and commit. When `team.approvals.roadmap` in `.agent-workflow/config.yaml` lists roles: push, ask approval, open the pull request, and return `awaiting_roadmap_review`. On the next run, take the PR URL from the PM or `gh pr list --head roadmap/<topic>`, then `gin-workflow team check <pr-url> --gate roadmap`: exit 0 continues with the merged file on the base branch; exit 1 shows the reasons and stops. Never work around a rejection.
-6. **Sync Beads** for each epic in the file, after `bd show <id> --json` (only an explicit not-found result means missing; any other failure stops the sync):
-   - missing: `bd create --id <id> --type epic --labels roadmap -d "<description>" "<title>"`;
-   - existing: `bd update <id> --title "<title>" -d "<description>"`. Never `bd create --id` an existing id: it replaces the bead and erases its description;
+6. **Sync Beads** for each epic in the file, after `gin-workflow task show <id> --json` (only an explicit not-found result means missing; any other failure stops the sync):
+   - missing: `gin-workflow task create --id <id> --type epic --labels roadmap -d "<description>" "<title>"`;
+   - existing: `gin-workflow task update <id> --title "<title>" -d "<description>"`. Never `gin-workflow task create --id` an existing id: it replaces the bead and erases its description;
    - the description comes from `gin-workflow specs template epic.md`;
-   - dependencies: `bd dep add <epic> <dependency>` for each `Depends on:` id; `bd dep remove <epic> <dependency>` for a dependency on a `roadmap`-labelled epic that the file no longer lists (`bd dep list <epic> --json`);
+   - dependencies: `gin-workflow task dep add <epic> <dependency>` for each `Depends on:` id; `gin-workflow task dep remove <epic> <dependency>` for a dependency on a `roadmap`-labelled epic that the file no longer lists (`gin-workflow task dep list <epic> --json`);
    - an epic that is `in_progress` or closed: warn and leave its title, description, and dependencies unchanged;
    - an epic labelled `roadmap` that the file no longer lists: report it and ask; never close or delete an epic;
-   - a failing `bd` call: stop and report which epics were synced; a re-run continues from there.
-7. **Sprint** (when asked): `bd update <epic> --add-label sprint:<name>` for each chosen epic.
-8. **Report**: the roadmap path, epics created and updated, dependency changes, `bd ready` epics, the next step `/discuss <epic-id>`, and `gin-workflow setup refresh` to update the links in `AGENTS.md`.
+   - a failing `gin-workflow task` call: stop and report which epics were synced; a re-run continues from there.
+7. **Sprint** (when asked): `gin-workflow task update <epic> --add-label sprint:<name>` for each chosen epic.
+8. **Report**: the roadmap path, epics created and updated, dependency changes, `gin-workflow task ready` epics, the next step `/discuss <epic-id>`, and `gin-workflow setup refresh` to update the links in `AGENTS.md`.
````

`plugins/gin-workflow/src/skills/setup/SKILL.md`:

````diff
diff --git a/plugins/gin-workflow/src/skills/setup/SKILL.md b/plugins/gin-workflow/src/skills/setup/SKILL.md
index 34c9b61..5b2449f 100644
--- a/plugins/gin-workflow/src/skills/setup/SKILL.md
+++ b/plugins/gin-workflow/src/skills/setup/SKILL.md
@@ -16,6 +16,7 @@ Ask exactly one question at a time and wait for its answer. Do not infer require
 3. **Provider mode** — `single` (the current harness does everything; default) or `multi` (continue with Advanced setup groups 2–9).
 4. **Verify commands** — Confirm the detected lint, typecheck, test, build, and e2e commands; the user may edit any. On greenfield, ask for `stack_intent` instead.
 5. **Code index** — Brownfield or legacy only. When `codegraph.installed` is true and it is not `indexed`: offer `codegraph init`, and run it only on approval. When `codegraph.installed` is false: print one line suggesting CodeGraph with https://github.com/giangdhwhtbr/gin-workflow/blob/master/docs/guides/recommended-tools.md; do not ask, install, or wait.
+6. **Task tracking** — Only when `detect` reports `beads_installed: false`: offer local Markdown tasks (`--set providers.task_tracking=markdown`; one git-ignored file per task under `.planning/tasks/`, no team mode or usage reports) or installing Beads first. Add the assignment only on approval. When Beads is installed, do not ask.
 
 Optional: a model per tier for the current harness from `gin-workflow setup models --provider <harness> --format json`. Suggest fast/cheap models for `low` and frontier models for `high`; an `agy` id suffix (`-low`/`-medium`/`-high`) matches its tier. Always allow manual entry; an empty list means manual entry. Model choices become `--provider-set` assignments. When skipped in single mode, setup defaults the harness mapping from built-in harness defaults.
````

`plugins/gin-workflow/src/skills/ship/SKILL.md`:

````diff
diff --git a/plugins/gin-workflow/src/skills/ship/SKILL.md b/plugins/gin-workflow/src/skills/ship/SKILL.md
index 4a0ce4a..8fd5fae 100644
--- a/plugins/gin-workflow/src/skills/ship/SKILL.md
+++ b/plugins/gin-workflow/src/skills/ship/SKILL.md
@@ -14,7 +14,7 @@ Check → detect workspace → present options → execute the choice → clean
 ## Steps
 
 1. Require `implementation_complete` and a terminal review state. Do not run tests: the `pre-commit`/`pre-push` git hooks and CI own that (run `gin-workflow hooks install` if `gin-workflow setup doctor` reports a hook missing). Run only these plain steps and stop on the first failure, reporting it to the user without retrying:
-   - With `project.review_ledger` on, for each closed track bead of the epic: `python3 review-ledger.py validate --bead-id <id> --in-history` and `render --bead-id <id> --check`. Then `git log -m --name-only <newest approved commit>..HEAD` may touch only `.planning/specs/`, `.planning/reviews/`, and the SDD spec dirs; any other change after approval needs the last approved track reopened (`bd reopen`) and reviewed again.
+   - With `project.review_ledger` on, for each closed track bead of the epic: `python3 review-ledger.py validate --bead-id <id> --in-history` and `render --bead-id <id> --check`. Then `git log -m --name-only <newest approved commit>..HEAD` may touch only `.planning/specs/`, `.planning/reviews/`, and the SDD spec dirs; any other change after approval needs the last approved track reopened (`gin-workflow task reopen`) and reviewed again.
    - With `project.layout: sdd`, lint, trace, and archive the change into the living spec, per the `gin-sdd` skill.
    With `project.team.enabled`, merging follows the host rules, Beads are synced, and a `team.approvals.ship` policy limits the options (the `gin-team` skill).
 2. Detect the workspace before changing directory and save the results:
@@ -33,9 +33,9 @@ Check → detect workspace → present options → execute the choice → clean
    - **Keep:** report the branch and worktree path. Keep the worktree.
    - **Discard:** list what will be deleted and require the typed word `discard`. Then `git reset --hard HEAD && git clean -fd`; for a named branch, clean up (step 6), then `cd "$MAIN_ROOT" && git checkout <base> && git branch -D "$FEATURE_BRANCH"`. A detached workspace is only reset; the harness owns its removal.
 6. Cleanup (merge/discard only, when `IS_WORKTREE=yes`): from `MAIN_ROOT`, run `scripts/worktree-cleanup.sh <track-id>` (never from inside the worktree), before deleting the branch, then `git worktree prune`. Never use wildcards or unresolved paths; never remove harness-owned worktrees.
-7. Close out: run `gin-workflow usage collect --bead <epic> --best-effort` before closing the parent bead and before any ledger cleanup; close the remaining beads with evidence (`bd close`); the parent bead closes only after a human-confirmed merge, and closing it is what marks `shipped`. A standalone bead (its own epic) is already closed: after the merge, `gin-workflow record shipped --workflow-id <bead> --evidence <merge commit> --actor <id>`. Once a bead is closed and merged, run `python3 review-ledger.py cleanup --bead-id <bead-id>` (or `--all-closed`). Reconcile knowledge per `gin-knowledge`. Branch or worktree cleanup never proves completion.
+7. Close out: run `gin-workflow usage collect --bead <epic> --best-effort` before closing the parent bead and before any ledger cleanup; close the remaining beads with evidence (`gin-workflow task close`); the parent bead closes only after a human-confirmed merge, and closing it is what marks `shipped`. A standalone bead (its own epic) is already closed: after the merge, `gin-workflow record shipped --workflow-id <bead> --evidence <merge commit> --actor <id>`. Once a bead is closed and merged, run `python3 review-ledger.py cleanup --bead-id <bead-id>` (or `--all-closed`). Reconcile knowledge per `gin-knowledge`. Branch or worktree cleanup never proves completion.
 8. If this repository is itself a plugin/marketplace source installed elsewhere on this host (as `gin-workflow` is), refresh each platform's installed snapshot (see `docs/reference/troubleshooting.md`); harness caches do not pick up new commits.
-9. Handoff: list `bd ready` tasks grouped by dependency readiness and non-overlapping file scope, mark which can run in parallel, and end with `Next commands:` (for example `/gin-workflow:execute <id-1> <id-2>`).
+9. Handoff: list `gin-workflow task ready` tasks grouped by dependency readiness and non-overlapping file scope, mark which can run in parallel, and end with `Next commands:` (for example `/gin-workflow:execute <id-1> <id-2>`).
 
 ## Exit
````

`README.md`:

````diff
diff --git a/README.md b/README.md
index 3000adb..018c96b 100644
--- a/README.md
+++ b/README.md
@@ -26,7 +26,7 @@ A workflow plugin for **Claude Code**, **Codex CLI**, **Antigravity CLI**, and *
 | git | branches, worktrees, review checkpoints | your package manager |
 | jq | the safety hook, which blocks every shell command when `jq` is missing | `brew install jq`, `apt install jq`, or `winget install jqlang.jq` |
 | Git Bash (Windows only) | the `.sh` hook scripts | [Git for Windows](https://gitforwindows.org/) or `winget install Git.Git` |
-| [Beads](https://github.com/gastownhall/beads) (`bd`) | task tracking | `brew install beads`, `npm install -g @beads/bd`, or `curl -fsSL https://raw.githubusercontent.com/gastownhall/beads/main/scripts/install.sh \| bash` |
+| [Beads](https://github.com/gastownhall/beads) (`bd`) | task tracking; optional: without it, `/setup` offers local Markdown tasks (`providers.task_tracking: markdown`) | `brew install beads`, `npm install -g @beads/bd`, or `curl -fsSL https://raw.githubusercontent.com/gastownhall/beads/main/scripts/install.sh \| bash` |
 | A harness | running the skills | Claude Code, Codex CLI, Antigravity CLI (`agy`), or OpenCode |
 
 Optional, per feature: [CodeGraph](docs/guides/recommended-tools.md#codegraph) for faster code lookup by agents; `codex`, `agy`, or `opencode` next to your main harness for multi-provider routing; `gh` or `glab` for [team mode](docs/guides/team.md); Node with `@playwright/test` 1.49 or later for [QA end-to-end specs](docs/guides/qa.md). Install and configuration: [recommended tools](docs/guides/recommended-tools.md).
````

`docs/reference/cli.md`:

````diff
diff --git a/docs/reference/cli.md b/docs/reference/cli.md
index 8afd9cb..2722d39 100644
--- a/docs/reference/cli.md
+++ b/docs/reference/cli.md
@@ -184,6 +184,16 @@ Called by the `review` skill to pick the reviewer; you do not need to run it. Pr
 
 Exit codes: 0 routes printed; 2 bad `--base`, no route for the tier, or no independent route.
 
+## `gin-workflow task`
+
+```
+gin-workflow task <bd arguments>
+```
+
+The task-tracking entry point skills and agents use. With `providers.task_tracking: beads` (the default) it runs `bd` with the arguments unchanged. With `markdown` it serves the same subset in process from `.planning/tasks/` (git-ignored, local to this machine): `create`, `show`, `update`, `close`, `reopen`, `list`, `ready`, `blocked`, `dep add|remove|list`, `config get issue_prefix`, `remember`, `memories`, with `bd`-shaped `--json` output.
+
+Exit codes: 0 ok; 1 invalid request or malformed task file (the message names the file); 127 `beads` is configured but `bd` is not installed.
+
 ## `gin-workflow usage`
 
 ```
````

`docs/reference/config.md`:

````diff
diff --git a/docs/reference/config.md b/docs/reference/config.md
index 73a5f1e..13fdd0b 100644
--- a/docs/reference/config.md
+++ b/docs/reference/config.md
@@ -122,6 +122,10 @@ Maps lifecycle phases (`brainstorm`, `design`, `plan`, `implement`, `review`, `d
 
 `core` and `lean` are always enabled unless disabled. Project packs live in `.agent-workflow/rules/`. Inspect the result with `gin-workflow rules --list`. See [Rule packs](../guides/rules.md).
 
+### `providers`
+
+`task_tracking`: `beads` (default) or `markdown`. `markdown` keeps one Markdown file per task under `.planning/tasks/` in the main checkout, git-ignored and local to this machine; it needs no `bd`. Team mode and `gin-workflow usage` require `beads`.
+
 ### `team`
 
 Present only in team mode ([guide](../guides/team.md)): `host` (`github` or `gitlab`), `commit_convention`, `members` (email → `roles`, `login`), `areas` (name → `paths`, `lead`, `roles`), `approvals` (per gate: a role list or `area_lead`; `roadmap` takes a role list and gates the `/roadmap` pull request), and `beads_sync.remote`.
````

`docs/concepts/providers.md`:

````diff
diff --git a/docs/concepts/providers.md b/docs/concepts/providers.md
index c239bd4..a377138 100644
--- a/docs/concepts/providers.md
+++ b/docs/concepts/providers.md
@@ -8,7 +8,7 @@ Skills work through provider-neutral capabilities, each with health and capabili
 
 | Capability | Covers |
 |---|---|
-| Task tracking | task identity, dependencies, readiness, claims, blockers, closure: Beads through `bd` (or `br`) commands, never by editing `.beads/` directly |
+| Task tracking | task identity, dependencies, readiness, claims, blockers, closure: through `gin-workflow task`, which runs Beads (`bd`) or, with `providers.task_tracking: markdown`, local Markdown files under `.planning/tasks/`; never by editing `.beads/` directly |
 | Workspace | isolation (worktrees) and cleanup metadata |
 | Worker dispatch | resolve role and reasoning, recheck health, circuit and capacity, dispatch, cancel, report status, collect normalized results |
 | Review | request review, terminal review state, findings |
````

## Integration
- **Branch**: `feat/markdown-task-tracking`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m unittest tests.test_all tests.test_safety_check tests.test_no_direct_bd` passes (prototype: 983 tests, OK, 3 skipped)
- [ ] Manual: in a scratch repo, `gin-workflow setup init --harness claude --non-interactive --approve --set providers.task_tracking=markdown`, then `gin-workflow task create --type epic E`, `gin-workflow task create T --parent <repo>-1`, `gin-workflow task ready`, and confirm `git status --porcelain` is empty
- [ ] Manual (beads non-regression): in this repository, `gin-workflow task ready --json` prints the same output as `bd ready --json`

## Notes
- The spec's "parameterize the existing compatibility tests" became new test modules instead, so the existing beads suites stay untouched (stricter non-regression).
- Follow-up epic (not this plan): `gin-tasks` branch sync and team mode on markdown, built on `task_markdown`.
- Model guidance is planning metadata, not Beads state.

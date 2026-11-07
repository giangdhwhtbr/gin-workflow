# Plan: Multi-repo workspace: parent holds docs, specs, config and beads; child repos cloned from a manifest; tracks worktree one child repo

Epic: gin-workflow-workspace
Spec: .planning/specs/2026-11-07-workspace-design.md

## Objective
A small parent repository (the workspace) lists its child repositories in `workspace.repos`. Every `gin` command run inside a child, or inside a child's track worktree, resolves the parent as the project root; `gin workspace clone|status` manage the clones; hooks and `/quick` run a child's own checks; plan tracks name their `Repo:` and orchestrate creates the worktree of that child only; ship merges per repository. The docs describe the layout and the workflow by role, and a bead in the qwikfone Beads database drives the validation on a real repository.

Architecture: a new module `workflow_core/workspace.py` owns the manifest (`Repo`, `Workspace`), the resolution (`locate`, `project_root`, `repository_root`), the state summary, and the doctor findings. Every CLI entry point that today defaults `--repository` to the current directory calls `workspace.repository_root(args.repository)` once after parsing. `hooks.py`, `lifecycle_cli._quick_check_command`, `worktrees.py`, and `team.py` ask `workspace.locate()` for the current repository entry where they need the child instead of the workspace root. A new `workflow_core/workspace_cli.py` holds `gin workspace clone|status`. The schema gains a `workspace` block; `setup` gains `--workspace`; `setup doctor` gains a `workspace` block. The skills `setup`, `plan` (and `plan-schema.md`), `orchestrate`, `execute`, `worktrees`, `ship`, and `quick` carry the behaviour under their character budgets. The docs set gains `docs/guides/workspace.md` and a rewritten brownfield setup.

Tech stack: Python 3 standard library plus PyYAML and jsonschema (already required), Markdown skills and docs, `unittest` tests run by `python3 -m pytest -n auto`.

Global Constraints (from the spec):
- Git submodules or subtrees are not the mechanism; the manifest replaces both. No lock file.
- `project.packages` inside a child repository is not supported; `project.monorepo` and `project.packages` keep their single-repository meaning.
- No change to gin-qa or gin-ba skills; gin-console reads one new, additive `workspace` key in `gin state --format json` and nothing else changes shape.
- A track changes one repository; a change spanning two repositories is two tracks.
- A config without `workspace` behaves exactly as today; no migration, no schema version bump (the top-level schema allows additional keys, `schemas.py:262`).
- An explicit `--repository` is taken as given; only the default (the current directory) is resolved to the workspace root (R3).
- `bd` always runs with the workspace root as its working directory (R5); skill and agent text never names `bd` (`tests/test_no_direct_bd.py`), only `gin task`.
- A frozen entry and the `beads` entry never get hooks, tracks, or worktrees; at most one `beads` entry, at path `.beads`.
- Track worktrees live under the parent's `.planning/worktrees/<track-id>` and are worktrees of the child repository (R10).
- `Files:` in a plan stay workspace-relative; the developer receives repo-relative paths (R11).
- Budgets (`tests/workflow_core/test_token_budget.py`): stage chains at most 12,000 characters (today plan 11,322, execute 11,660, orchestrate 6,860, ship 9,283), `quick` chain at most 8,000 (5,439), shared skill `worktrees` at most 6,000 (2,727), agents at most 4,000 (`developer.md` 3,636), `references/` holds exactly the four files `tests/gin_orchestrator/test_harness_packaging.py:309-313` lists (no new reference file).
- Every new `gin` subcommand needs a `## \`gin <command>\`` heading in `docs/reference/cli.md` (`tests/workflow_core/test_docs_coverage.py:42-47`); every docs page is linked from `README.md` and listed in `mkdocs.yml` nav; docs follow `references/docs-style.md` (no em or en dashes, no bold-label list items, no placeholder words).
- The validation bead changes the real `~/qwikfone` working copy only in a qwikfone session, under that session's approvals; this repository's tests never touch it.

## Route Rubric
- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis
- Problem statement: gin-workflow drives exactly one git repository (`cli.py:29`, `configuration.py:393`, `worktrees.py:22-41`, `hooks.py:43-59`); a brownfield modernization made of many repositories gets either a worktree of everything per track (run from a parent) or no config, specs and beads at all (run from a child).
- Success criteria: US-1 to US-6 of the spec; the full suite passes; the qwikfone bead run finds no gap left unfixed or unfiled.
- Constraints: see Global Constraints.
- Non-goals: the spec's "Out of scope".

## Approach Options
### Option 1: one resolver, called at every entry point (chosen in discuss)
- Summary: `workspace.locate()` walks up from the current repository's main checkout to a parent whose `workspace.repos` lists it; each CLI `main` replaces the default `--repository` with the resolved root; hooks, quick-check, worktrees and the plan check ask for the entry when they need the child.
- Pros: no change to `main_checkout` (its callers handle linked worktrees); an explicit `--repository` keeps today's meaning; tests that pass `--repository` to a temp repo are unaffected.
- Cons: about fifteen one-line edits at the argparse sites; `gin task` has no flag and uses `Path.cwd()` (`tasks.py:189`), so it gets the resolver directly.

### Option 2: resolve once in `cli.main` and inject `--repository`
- Summary: `cli.main` computes the root and appends `--repository <root>` to `argv` before dispatch.
- Pros: one edit.
- Cons: `tasks.py` ignores the flag; hooks and worktrees need the child, not the root, so they would have to undo the injection; argv rewriting hides the behaviour from each module's tests.

### Recommended Approach
- Selected option: Option 1.
- Rationale: chosen in discuss on 2026-11-07; it keeps `main_checkout` untouched and makes the resolution visible in each module.

## Scope
- In scope: R1 to R16 of the spec.
- Out of scope: everything under the spec's "Out of scope".

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks 2 to 6 all import the module Track 1 creates and three of them edit lifecycle_cli.py, hooks.py and team.py in overlapping regions; Track 7 and Track 8 describe the behaviour of Tracks 2 to 6; Track 9 needs the installed result of all of them. One track at a time on the feature branch keeps each review small and avoids merge conflicts in lifecycle_cli.py.
```

## Tasks

### Track 1: `workspace.py`: manifest, validation, resolution, summary
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/workspace.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/schemas.py:13` (`_SHAPES` stays; new `_WORKSPACE` block after `_TEAM`) and `:255-262` (register `"workspace": _WORKSPACE` in `CONFIG_SCHEMA["properties"]`)
  - Test `tests/workflow_core/test_workspace.py`
- **Interfaces**:
  - Consumes: `checkout.main_checkout(repo: Path) -> Path`; `configuration.require_yaml()`; `schemas._CHECKS`.
  - Produces: `workspace.SHAPES = ("frontend", "backend", "library", "qa", "beads")`; `Repo(path, url, shape, frozen, default_branch, checks)` with `Repo.workable -> bool`; `Workspace(root, repos)` with `repo(path) -> Repo | None`, `checkout(repo) -> Path`, `present(repo) -> bool`, `repo_of(file: str) -> Repo | None`; `Located(root, repo, workspace, entry)`; `repos_from(config: Mapping) -> tuple[Repo, ...]` (raises `WorkspaceError`); `load(root: Path) -> Workspace | None`; `locate(repository: Path) -> Located`; `project_root(repository: Path) -> Path`; `repository_root(value: Path | None) -> Path`; `summary(located: Located) -> dict | None`; `branch(path: Path) -> str | None`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one new module with a clear data model and validation rules spelled out in R1 and R3; the edge cases (nesting, reserved paths, linked worktree of a child) are listed and each gets a test.
- **Acceptance criteria**:
  - Every test in `tests/workflow_core/test_workspace.py` passes.
  - `python3 -m pytest tests/workflow_core/test_configuration.py tests/workflow_core/test_schema_2_5.py` passes (schema still loads older configs).
- **Estimated complexity**: medium

#### Steps

1. Create `tests/workflow_core/test_workspace.py`:

```python
"""workspace.py: manifest validation and workspace root resolution."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"))

from workflow_core import workspace  # noqa: E402
from workflow_core.schemas import validate_config_schema  # noqa: E402


def git(root, *argv):
    return subprocess.run(["git", *argv], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def init_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    (root / "f.txt").write_text("x", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init", "--no-verify")
    return root


MANIFEST = """schema_version: '2.9'
workspace:
  repos:
    - path: services/api
      url: git@example.com:acme/api.git
      shape: backend
      verify: {checks: {test: "echo api-test"}}
    - path: apps/web
      url: git@example.com:acme/web.git
      shape: frontend
      default_branch: master
    - path: legacy/portal
      url: git@example.com:acme/portal.git
      frozen: true
    - path: .beads
      url: git@example.com:acme/beads.git
      shape: beads
"""


def make_workspace(base: Path) -> Path:
    """A parent with the manifest above and `services/api` cloned (a plain repo at the path)."""
    root = init_repo(base / "ws")
    (root / ".agent-workflow").mkdir()
    (root / ".agent-workflow/config.yaml").write_text(MANIFEST, encoding="utf-8")
    init_repo(root / "services/api")
    return root


class ManifestTests(unittest.TestCase):
    def test_repos_from_parses_defaults(self):
        repos = workspace.repos_from({"workspace": {"repos": [
            {"path": "services/api", "url": "u", "shape": "backend"},
            {"path": "legacy/x", "url": "u2", "frozen": True},
            {"path": ".beads", "url": "u3", "shape": "beads"}]}})
        self.assertEqual(("services/api", "backend", False, "main", {}), (repos[0].path, repos[0].shape,
                                                                            repos[0].frozen, repos[0].default_branch,
                                                                            dict(repos[0].checks)))
        self.assertEqual([True, False, False], [r.workable for r in repos])

    def test_repos_from_rejects_bad_manifests(self):
        bad = [
            ([{"path": "a", "url": "u", "shape": "backend"}, {"path": "a", "url": "u", "shape": "backend"}], "duplicate"),
            ([{"path": "a", "url": "u", "shape": "backend"}, {"path": "a/b", "url": "u", "shape": "backend"}], "nests"),
            ([{"path": ".planning", "url": "u", "shape": "backend"}], "reserved"),
            ([{"path": "/abs", "url": "u", "shape": "backend"}], "relative"),
            ([{"path": "a", "url": "u"}], "shape"),
            ([{"path": "a", "url": "u", "shape": "beads"}], ".beads"),
            ([{"path": ".beads", "url": "u", "shape": "beads"}, {"path": "b", "url": "u", "shape": "beads"}], "one"),
        ]
        for repos, word in bad:
            with self.subTest(word=word), self.assertRaises(workspace.WorkspaceError) as caught:
                workspace.repos_from({"workspace": {"repos": repos}})
            self.assertIn(word, str(caught.exception))

    def test_schema_accepts_manifest_and_rejects_unknown_keys(self):
        import yaml
        validate_config_schema(yaml.safe_load(MANIFEST))
        with self.assertRaises(ValueError):
            validate_config_schema({"schema_version": "2.9", "workspace": {"repos": [
                {"path": "a", "url": "u", "shape": "backend", "branch": "x"}]}})
        with self.assertRaises(ValueError):
            validate_config_schema({"schema_version": "2.9", "workspace": {"repos": [
                {"path": "a", "url": "u", "shape": "fullstack"}]}})

    def test_repo_of_uses_the_longest_prefix(self):
        ws = workspace.Workspace(Path("/ws"), workspace.repos_from(
            {"workspace": {"repos": [{"path": "services/api", "url": "u", "shape": "backend"},
                                     {"path": "apps/web", "url": "u", "shape": "frontend"}]}}))
        self.assertEqual("services/api", ws.repo_of("services/api/src/Main.java").path)
        self.assertIsNone(ws.repo_of("docs/x.md"))
        self.assertIsNone(ws.repo_of("services/apix/a"))


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name).resolve()
        self.root = make_workspace(self.base)
        self.child = self.root / "services/api"

    def test_load_returns_none_without_manifest(self):
        plain = init_repo(self.base / "plain")
        (plain / ".agent-workflow").mkdir()
        (plain / ".agent-workflow/config.yaml").write_text("schema_version: '2.9'\n", encoding="utf-8")
        self.assertIsNone(workspace.load(plain))
        self.assertIsNone(workspace.load(self.base))

    def test_locate_from_parent_child_and_child_worktree(self):
        parent = workspace.locate(self.root)
        self.assertEqual((self.root, self.root, None), (parent.root, parent.repo, parent.entry))
        self.assertIsNotNone(parent.workspace)
        child = workspace.locate(self.child)
        self.assertEqual((self.root, self.child, "services/api"), (child.root, child.repo, child.entry.path))
        nested = workspace.locate(self.child / "src")
        self.assertEqual(self.root, nested.root)
        wt = self.root / ".planning/worktrees/t1"
        wt.parent.mkdir(parents=True)
        git(self.child, "worktree", "add", "-b", "feat/x-t1", str(wt), "main")
        linked = workspace.locate(wt)
        self.assertEqual((self.root, self.child, "services/api"), (linked.root, linked.repo, linked.entry.path))

    def test_locate_outside_a_workspace_keeps_the_repository(self):
        plain = init_repo(self.base / "plain")
        located = workspace.locate(plain)
        self.assertEqual((plain, plain, None, None), (located.root, located.repo, located.workspace, located.entry))
        stray = init_repo(self.base / "elsewhere/api")  # a child cloned outside its manifest path
        self.assertEqual(stray, workspace.locate(stray).root)

    def test_repository_root_resolves_only_the_default(self):
        self.assertEqual(self.child, workspace.repository_root(self.child))
        self.assertEqual(self.root, workspace.project_root(self.child))

    def test_summary(self):
        child = workspace.summary(workspace.locate(self.child))
        self.assertEqual(str(self.root), child["root"])
        self.assertEqual("services/api", child["current_repo"])
        by_path = {r["path"]: r for r in child["repos"]}
        self.assertEqual({"path": "services/api", "shape": "backend", "frozen": False, "present": True,
                          "branch": "main"}, by_path["services/api"])
        self.assertEqual({"path": "apps/web", "shape": "frontend", "frozen": False, "present": False,
                          "branch": None}, by_path["apps/web"])
        self.assertIsNone(workspace.summary(workspace.locate(init_repo(self.base / "plain"))))
        self.assertIsNone(workspace.summary(workspace.locate(self.root))["current_repo"])


if __name__ == "__main__":
    unittest.main()
```

Run `python3 -m pytest tests/workflow_core/test_workspace.py -q`; it fails with `ImportError` on `workflow_core.workspace`.

2. Create `plugins/gin-workflow/src/scripts/workflow_core/workspace.py`:

```python
"""A workspace: a parent repository whose `.agent-workflow/config.yaml` lists child repositories in `workspace.repos`.

Child repositories are plain git clones at their manifest path under the parent, gitignored there. Every `gin`
command run inside a child (or inside a child's track worktree) resolves the parent as its project root.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any, Mapping

from .checkout import main_checkout
from .configuration import require_yaml

SHAPES = ("frontend", "backend", "library", "qa", "beads")
CHECK_NAMES = ("lint", "typecheck", "test", "build", "e2e")
RESERVED = (".planning", ".agent-workflow")
BEADS_PATH = ".beads"


class WorkspaceError(ValueError):
    """An invalid `workspace.repos` manifest."""


@dataclass(frozen=True)
class Repo:
    path: str
    url: str
    shape: str = ""
    frozen: bool = False
    default_branch: str = "main"
    checks: Mapping[str, str] = field(default_factory=dict)

    @property
    def workable(self) -> bool:
        """Takes hooks, plan tracks and worktrees: neither frozen nor the Beads repository."""
        return not self.frozen and self.shape != "beads"


@dataclass(frozen=True)
class Workspace:
    root: Path
    repos: tuple[Repo, ...]

    def repo(self, path: str) -> Repo | None:
        return next((repo for repo in self.repos if repo.path == path), None)

    def checkout(self, repo: Repo) -> Path:
        return self.root / repo.path

    def present(self, repo: Repo) -> bool:
        return (self.checkout(repo) / ".git").exists()

    def repo_of(self, file: str) -> Repo | None:
        """The entry whose path contains `file` (workspace-relative), or None."""
        posix = PurePosixPath(file)
        matches = [repo for repo in self.repos if PurePosixPath(repo.path) in posix.parents]
        return max(matches, key=lambda repo: len(repo.path)) if matches else None


@dataclass(frozen=True)
class Located:
    root: Path                 # the project root: the workspace root, or the repository itself
    repo: Path                 # the main checkout of the repository that was given
    workspace: Workspace | None
    entry: Repo | None         # the manifest entry of `repo` when it is a child


def _entry(raw: Mapping[str, Any]) -> Repo:
    path = str(raw.get("path", "")).strip()
    if not path or path.startswith("/") or ".." in PurePosixPath(path).parts:
        raise WorkspaceError(f"workspace.repos: path must be relative and inside the workspace: {path!r}")
    if path in RESERVED:
        raise WorkspaceError(f"workspace.repos: {path} is reserved")
    url = str(raw.get("url", "")).strip()
    if not url:
        raise WorkspaceError(f"workspace.repos: {path}: url is required")
    frozen = bool(raw.get("frozen", False))
    shape = str(raw.get("shape", "")).strip()
    if shape not in SHAPES and not (frozen and shape == ""):
        raise WorkspaceError(f"workspace.repos: {path}: shape must be one of {', '.join(SHAPES)}")
    if shape == "beads" and path != BEADS_PATH:
        raise WorkspaceError(f"workspace.repos: the beads repository must be at {BEADS_PATH}, not {path}")
    checks = {k: str(v) for k, v in ((raw.get("verify") or {}).get("checks") or {}).items()
              if k in CHECK_NAMES and str(v).strip()}
    return Repo(path, url, shape, frozen, str(raw.get("default_branch", "main")), checks)


def repos_from(config: Mapping[str, Any]) -> tuple[Repo, ...]:
    """Parse and validate `workspace.repos`; an empty tuple when the key is absent."""
    block = config.get("workspace") if isinstance(config, Mapping) else None
    if not isinstance(block, Mapping) or not isinstance(block.get("repos"), list):
        return ()
    repos = tuple(_entry(raw) for raw in block["repos"] if isinstance(raw, Mapping))
    paths = [repo.path for repo in repos]
    for index, path in enumerate(paths):
        if path in paths[:index]:
            raise WorkspaceError(f"workspace.repos: duplicate path {path}")
        for other in paths:
            if other != path and PurePosixPath(path) in PurePosixPath(other).parents:
                raise WorkspaceError(f"workspace.repos: {other} nests inside {path}")
    if sum(repo.shape == "beads" for repo in repos) > 1:
        raise WorkspaceError("workspace.repos: at most one beads repository")
    return repos


def load(root: Path) -> Workspace | None:
    """The workspace rooted at `root`, or None when its config has no `workspace.repos`."""
    config_path = Path(root) / ".agent-workflow/config.yaml"
    if not config_path.is_file():
        return None
    yaml = require_yaml()
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as error:
        raise WorkspaceError(f"{config_path}: {error}") from error
    repos = repos_from(config)
    return Workspace(Path(root).resolve(), repos) if repos else None


def locate(repository: Path) -> Located:
    """Resolve `repository` (any directory inside a repository or one of its linked worktrees) to its project root."""
    given = Path(repository).resolve()
    checkout = main_checkout(given)
    for parent in checkout.parents:
        workspace = load(parent)
        if workspace is None:
            continue
        for repo in workspace.repos:
            if workspace.checkout(repo).resolve() == checkout:
                return Located(workspace.root, checkout, workspace, repo)
    own = load(checkout)
    return Located(own.root if own else given, checkout, own, None)


def project_root(repository: Path) -> Path:
    return locate(repository).root


def repository_root(value: Path | None) -> Path:
    """`--repository` as given; without it, the current directory resolved to its workspace root."""
    return Path(value).resolve() if value is not None else project_root(Path.cwd())


def branch(path: Path) -> str | None:
    done = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path, text=True,
                          capture_output=True, check=False)
    return done.stdout.strip() if done.returncode == 0 else None


def summary(located: Located) -> dict[str, Any] | None:
    """The `workspace` object of `gin state --format json`; None outside a workspace."""
    if located.workspace is None:
        return None
    workspace = located.workspace
    return {
        "root": str(workspace.root),
        "current_repo": located.entry.path if located.entry else None,
        "repos": [{"path": repo.path, "shape": repo.shape, "frozen": repo.frozen,
                   "present": workspace.present(repo),
                   "branch": branch(workspace.checkout(repo)) if workspace.present(repo) else None}
                  for repo in workspace.repos],
    }
```

Note on `locate`: `main_checkout` turns a child's linked worktree (anywhere on disk) into the child checkout, and `checkout.parents` includes the workspace root for a nested path such as `services/api/src`, because `main_checkout` of a plain directory returns the directory itself only when it is not inside a git repository; inside one, git's common dir names the checkout. The last line keeps today's behaviour outside a workspace: `root` is the directory that was given.

3. In `schemas.py`, after `_TEAM` (before `CONFIG_SCHEMA`), add:

```python
_WORKSPACE = {
    "type": "object",
    "required": ["repos"],
    "properties": {
        "repos": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["path", "url"],
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "url": {"type": "string", "minLength": 1},
                    "shape": {"enum": ["frontend", "backend", "library", "qa", "beads"]},
                    "frozen": {"type": "boolean"},
                    "default_branch": {"type": "string", "minLength": 1},
                    "verify": {"type": "object", "properties": {"checks": _CHECKS}, "additionalProperties": False},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}
```

and register it in `CONFIG_SCHEMA["properties"]` next to `"team": _TEAM` as `"workspace": _WORKSPACE`.

4. Run `python3 -m pytest tests/workflow_core/test_workspace.py tests/workflow_core/test_configuration.py tests/workflow_core/test_schema_2_5.py -q`; all pass. Commit: `feat(workspace): manifest, validation and workspace root resolution (gin-workflow-workspace)`.

### Track 2: every CLI entry point resolves the workspace root; `gin state` reports `workspace`
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:609-614` (`--repository` default `None`, resolve once, keep `args.start`) and `:461-463` (`"workspace"` key in the state payload)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/cli.py:29` (setup `--repository` default `None`) and `:125-128` (resolve before `COMMANDS[action]`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/tasks.py:104-106` (`_ready(executable, argv, root)`), `:189` (`root = workspace.project_root(Path.cwd())`), `:209-211` (`cwd=root` on both subprocess calls)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/routes.py:349,356,360`, `milestone_cli.py:33,269`, `team_cli.py:16`, `specs_cli.py:16`, `usage_cli.py:24`, `verification.py:85`, `docs_check.py:68`, `goal.py:53`, `reviewer.py:154`, `rules.py:258` (each: `default=None`, then `args.repository = workspace.repository_root(args.repository)` right after `parse_args`)
  - Test `tests/workflow_core/test_workspace_cli_resolution.py`
- **Interfaces**:
  - Consumes: `workspace.repository_root`, `workspace.project_root`, `workspace.locate`, `workspace.summary`.
  - Produces: `gin state --format json` key `workspace: {root, current_repo, repos: [...]} | null`; `args.start: Path` on the lifecycle namespace (the directory the command started from, before resolution).
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** a cross-module change touching fifteen entry points and the `bd` working directory; each edit is small, but a missed site or a wrong `cwd` silently breaks a command only in a workspace, so the strongest model checks every site against the test matrix.
- **Acceptance criteria**:
  - `tests/workflow_core/test_workspace_cli_resolution.py` passes: `gin state --format json` from the parent, from `services/api`, and from a track worktree of `services/api` print the same `gates` and `epic`, and `workspace.current_repo` is `null`, `services/api`, `services/api`; `gin task list --json` from the child runs `bd` with `cwd` equal to the workspace root (asserted through a fake `bd` on `PATH` that records its cwd, `tests/workflow_core/team_fixtures.py` `fake_cli`); a plain repository keeps `workspace: null`.
  - The full suite passes.
- **Estimated complexity**: medium

#### Steps

1. Create `tests/workflow_core/test_workspace_cli_resolution.py` (reuse `make_workspace`, `git`, `init_repo` from `tests/workflow_core/test_workspace.py` by import):

```python
"""Every gin entry point resolves the workspace root from inside a child repository."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "plugins/gin-workflow/src/scripts/gin"
sys.path.insert(0, str(ROOT / "plugins/gin-workflow/src/scripts"))

from tests.workflow_core.team_fixtures import path_with  # noqa: E402
from tests.workflow_core.test_workspace import git, make_workspace  # noqa: E402


def run(cwd: Path, *args: str, env=None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(LAUNCHER), *args], cwd=cwd, text=True, capture_output=True,
                          env={**os.environ, **(env or {})}, check=False)


class ResolutionFromChildTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name).resolve()
        self.root = make_workspace(self.base)
        self.child = self.root / "services/api"
        (self.root / ".agent-workflow/config.yaml").write_text(
            (self.root / ".agent-workflow/config.yaml").read_text() + "providers:\n  task_tracking: beads\n")
        self.assertEqual(0, run(self.root, "setup", "init", "--harness", "claude", "--approve",
                                "--format", "json").returncode)

    def state(self, cwd: Path) -> dict:
        done = run(cwd, "state", "--format", "json")
        self.assertIn(done.returncode, (0, 1), done.stderr)
        return json.loads(done.stdout)

    def test_state_is_the_same_from_parent_child_and_track_worktree(self):
        wt = self.root / ".planning/worktrees/t1"
        wt.parent.mkdir(parents=True)
        git(self.child, "worktree", "add", "-b", "feat/x-t1", str(wt), "main")
        parent, child, linked = self.state(self.root), self.state(self.child), self.state(wt)
        self.assertEqual(parent["gates"], child["gates"])
        self.assertEqual(parent["gates"], linked["gates"])
        self.assertEqual([None, "services/api", "services/api"],
                         [s["workspace"]["current_repo"] for s in (parent, child, linked)])
        self.assertEqual(str(self.root), child["workspace"]["root"])

    def test_explicit_repository_is_taken_as_given(self):
        done = run(self.base, "state", "--repository", str(self.child), "--format", "json")
        self.assertEqual(2, done.returncode)  # the child has no .agent-workflow: today's error, unchanged

    def test_plain_repository_reports_null_workspace(self):
        plain = self.base / "plain"
        plain.mkdir()
        (plain / ".agent-workflow").mkdir()
        (plain / ".agent-workflow/config.yaml").write_text("schema_version: '2.9'\n")
        run(plain, "setup", "init", "--harness", "claude", "--approve", "--format", "json")
        self.assertIsNone(self.state(plain)["workspace"])

    def test_task_runs_bd_at_the_workspace_root(self):
        with tempfile.TemporaryDirectory() as bin_dir:
            script = Path(bin_dir) / "bd"
            script.write_text('#!/bin/sh\npwd > "$BD_CWD_FILE"\necho "[]"\n', encoding="utf-8")
            script.chmod(0o755)
            marker = Path(bin_dir) / "cwd.txt"
            done = run(self.child, "task", "list", "--json",
                       env={**path_with(Path(bin_dir)), "BD_CWD_FILE": str(marker)})
            self.assertEqual(0, done.returncode, done.stderr)
            self.assertEqual(str(self.root), marker.read_text().strip())


if __name__ == "__main__":
    unittest.main()
```

`path_with(bin_dir)` (`tests/workflow_core/team_fixtures.py:152`) returns the `PATH` mapping with `bin_dir` first. Run the file; the resolution tests fail (`workspace` key missing, state from the child exits 2).

2. In `lifecycle_cli.py` `main`, replace lines 609-614 with:

```python
    parser = argparse.ArgumentParser(prog=f"gin {command}")
    parser.add_argument("--repository", type=Path, default=None)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--workflow-id", default="default-workflow")
    parser.add_argument("--scope-hash")
```

and, right after each `args = parser.parse_args(...)` in that function (the `state` branch and the shared branch for the other commands), add:

```python
        args.start = Path(args.repository) if args.repository is not None else Path.cwd()
        args.repository = workspace.repository_root(args.repository)
```

with `from . import workspace` among the imports. Every later `Path(args.repository).resolve()` then already names the root.

3. In `_state_command`, after the `"extensions"` entry (line 463), add:

```python
        "workspace": workspace.summary(workspace.locate(getattr(args, "start", repo_path))),
```

4. `cli.py`: line 29 becomes `parser.add_argument("--repository", type=Path, default=None)`; after `options = vars(parsed)` (line 126) add `options["repository"] = workspace.repository_root(options["repository"])` with `from . import workspace` at the top of `main` (lazy import like the others).

5. `tasks.py`: `_ready(executable: str, argv: Sequence[str], root: Path) -> int` drops its `root = Path.cwd()` line and passes `cwd=root` to both `subprocess.run` calls inside it; `main` line 189 becomes `root = workspace.project_root(Path.cwd())`; line 209 becomes `return _ready(executable, [*argv, "--exclude-type", "milestone"], root)`; line 211 adds `cwd=root`.

6. For each of `routes.py`, `milestone_cli.py`, `team_cli.py`, `specs_cli.py`, `usage_cli.py`, `verification.py`, `docs_check.py`, `goal.py`, `reviewer.py`, `rules.py`: change the `--repository` default from `Path.cwd()` to `None` and add `args.repository = workspace.repository_root(args.repository)` on the line after `parse_args` (import `from . import workspace`). `routes.py` has two parsers (lines 349 and 356): change both. `hooks.py` and `worktrees.py` are left to Tracks 4 and 5.

7. Run the new test file, then `python3 -m pytest tests/workflow_core -q -n auto`. Fix any test that asserted `Path.cwd()` as a default. Commit: `feat(workspace): resolve the workspace root at every entry point; state reports workspace (gin-workflow-workspace)`.

### Track 3: `gin workspace clone|status`, setup `--workspace`, doctor findings
- **Dependencies**: Track 1
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/workspace_cli.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/workspace.py` (append `doctor(root, workspace) -> dict` and `ensure_gitignore(root, lines) -> list[str]`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/cli.py:20-21` (`"workspace"` in `TOP_COMMANDS`), `:45-47` (`--workspace` flag), `:85-87` (dispatch `workspace` to `workspace_cli.main`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py:820-835` (`preset(... workspace: bool = False ...)` adds `workspace.repos=[]`), the `init` command (gitignore block when `workspace=True`), `:559-561` (doctor block after `team`)
  - Modify `docs/reference/cli.md:316` (new `## \`gin workspace\`` section before `## \`gin worktree\``) and `:14-43` (`--workspace` in the setup flags list)
  - Test `tests/workflow_core/test_workspace_cli.py`
- **Interfaces**:
  - Consumes: `workspace.load`, `Workspace`, `Repo`, `configuration.require_yaml`, `setup_service.preset_assignments` output.
  - Produces: `gin workspace clone [PATH ...] [--all] [--json] [--repository DIR]` and `gin workspace status [--json] [--repository DIR]`; `workspace.doctor(root: Path, ws: Workspace) -> {"repos": {path: {"present", "checks", "ignored", "submodule"}}, "actions": [str]}`; `workspace.ensure_gitignore(root: Path, lines: Sequence[str]) -> list[str]` (the lines it appended); `gin setup preset --workspace` emits the assignment `workspace.repos=[]`; `gin setup init --workspace` appends to the root `.gitignore` the block `# workspace repos (gin workspace clone adds one line per repository)`, `/.beads`, `.planning/worktrees/`; `setup doctor` payload `checks_details.workspace` and `actions` entries prefixed `workspace:` without changing health.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded commands with a clear spec (R2, R6) and a fixture of local bare repositories; no cross-module logic beyond the doctor block that follows the `team` block's shape.
- **Acceptance criteria**:
  - `tests/workflow_core/test_workspace_cli.py` passes: `clone --all` on a fresh parent clones every entry at its path, the frozen one shallow (`git rev-parse --is-shallow-repository` is `true`), appends one `/<path>` line each to `.gitignore`, and a second run clones nothing; `clone services/api` clones one; `status` text and `--json` report present, branch, dirty, frozen; both commands exit 1 with `not in a workspace: <dir>` outside one.
  - `gin setup preset --workspace` includes `workspace.repos=[]`; `gin setup doctor` on the fixture reports `workspace: clone apps/web: gin workspace clone apps/web` and `workspace: apps/web has no verify.checks`, with `status` still `healthy` when everything else is.
  - `tests/workflow_core/test_docs_coverage.py` passes (the `gin workspace` heading exists).
- **Estimated complexity**: medium

#### Steps

1. Create `tests/workflow_core/test_workspace_cli.py` with a fixture that makes bare repositories for `services/api`, `apps/web`, `legacy/portal` and `.beads` (each `git init --bare` plus one commit pushed from a scratch clone), writes the parent config with their `file://` urls (`default_branch: main`), then:

```python
    def test_clone_all_then_status(self):
        done = run(self.root, "workspace", "clone", "--all", "--json")
        self.assertEqual(0, done.returncode, done.stderr)
        cloned = {item["path"]: item for item in json.loads(done.stdout)["repos"]}
        self.assertEqual({"services/api", "apps/web", "legacy/portal", ".beads"}, set(cloned))
        self.assertTrue(all(item["status"] == "cloned" for item in cloned.values()))
        self.assertEqual("true", git(self.root / "legacy/portal", "rev-parse", "--is-shallow-repository"))
        ignore = (self.root / ".gitignore").read_text()
        for path in cloned:
            self.assertIn(f"\n/{path}\n", ignore)
        again = json.loads(run(self.root, "workspace", "clone", "--all", "--json").stdout)
        self.assertTrue(all(item["status"] == "present" for item in again["repos"]))
        status = json.loads(run(self.root / "services/api", "workspace", "status", "--json").stdout)
        api = next(item for item in status["repos"] if item["path"] == "services/api")
        self.assertEqual({"path": "services/api", "present": True, "branch": "main", "dirty": False,
                          "frozen": False}, api)
        text = run(self.root, "workspace", "status").stdout
        self.assertIn("legacy/portal  present  main  clean  frozen", text)

    def test_clone_one_and_outside_workspace(self):
        done = run(self.root, "workspace", "clone", "services/api")
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertTrue((self.root / "services/api/.git").exists())
        self.assertFalse((self.root / "apps/web").exists())
        plain = self.base / "plain"
        plain.mkdir()
        done = run(plain, "workspace", "status")
        self.assertEqual(1, done.returncode)
        self.assertIn(f"not in a workspace: {plain}", done.stderr)
        done = run(self.root, "workspace", "clone", "nope")
        self.assertEqual(1, done.returncode)
        self.assertIn("not in workspace.repos: nope", done.stderr)

    def test_setup_workspace_flag_and_doctor(self):
        preset = json.loads(run(self.root, "setup", "preset", "--project-stage", "brownfield", "--project-shape",
                                "backend", "--rigor", "standard", "--task-tracking", "markdown", "--workspace",
                                "--format", "json").stdout)
        self.assertIn("workspace.repos=[]", preset["assignments"])
        run(self.root, "workspace", "clone", "services/api")
        run(self.root, "setup", "init", "--harness", "claude", "--approve", "--format", "json")
        doctor = json.loads(run(self.root, "setup", "doctor", "--format", "json").stdout)
        self.assertEqual("healthy", doctor["status"])
        self.assertIn("workspace: clone apps/web: gin workspace clone apps/web", doctor["actions"])
        self.assertIn("workspace: apps/web has no verify.checks", doctor["actions"])
        self.assertFalse(doctor["checks_details"]["workspace"]["repos"]["apps/web"]["present"])
```

Use the `run` helper from Track 2's test (`cwd` is the first argument). Note that the fixture config gives `services/api` a `verify.checks.test` and leaves `apps/web` without checks. Run the file; every test fails on the unknown command.

2. Create `workspace_cli.py`:

```python
"""`gin workspace`: clone the manifest's repositories and show their state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence

from . import workspace as ws


def _run_git(argv: Sequence[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *argv], cwd=cwd, text=True, capture_output=True, check=False)


def clone(space: ws.Workspace, paths: Sequence[str], all_repos: bool) -> list[dict[str, Any]]:
    chosen = list(space.repos) if all_repos else [space.repo(path) for path in paths]
    if any(repo is None for repo in chosen):
        missing = [path for path, repo in zip(paths, chosen) if repo is None]
        raise ws.WorkspaceError(f"not in workspace.repos: {', '.join(missing)}")
    if not chosen:
        raise ws.WorkspaceError("name a repository path or pass --all")
    results = []
    for repo in chosen:
        target = space.checkout(repo)
        if space.present(repo):
            results.append({"path": repo.path, "status": "present"})
            continue
        argv = ["clone", "--branch", repo.default_branch, *(["--depth", "1"] if repo.frozen else []),
                repo.url, str(target)]
        done = _run_git(argv)
        if done.returncode:
            raise ws.WorkspaceError(f"{repo.path}: {done.stderr.strip() or 'git clone failed'}")
        results.append({"path": repo.path, "status": "cloned"})
    ws.ensure_gitignore(space.root, [f"/{repo.path}" for repo in chosen])
    return results


def status(space: ws.Workspace) -> list[dict[str, Any]]:
    rows = []
    for repo in space.repos:
        present = space.present(repo)
        dirty = None
        if present:
            porcelain = _run_git(["status", "--porcelain"], space.checkout(repo))
            dirty = bool(porcelain.stdout.strip()) if porcelain.returncode == 0 else None
        rows.append({"path": repo.path, "present": present,
                     "branch": ws.branch(space.checkout(repo)) if present else None,
                     "dirty": dirty, "frozen": repo.frozen})
    return rows


def _text(rows: list[dict[str, Any]]) -> str:
    width = max(len(row["path"]) for row in rows)
    lines = []
    for row in rows:
        state = "present" if row["present"] else "missing"
        tree = "" if row["dirty"] is None else ("dirty" if row["dirty"] else "clean")
        lines.append("  ".join(part for part in (row["path"].ljust(width), state, row["branch"] or "", tree,
                                                 "frozen" if row["frozen"] else "") if part))
    return "\n".join(lines)


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="gin workspace")
    commands = parser.add_subparsers(dest="command", required=True)
    clone_parser = commands.add_parser("clone")
    clone_parser.add_argument("paths", nargs="*")
    clone_parser.add_argument("--all", dest="all_repos", action="store_true")
    status_parser = commands.add_parser("status")
    for sub in (clone_parser, status_parser):
        sub.add_argument("--repository", type=Path, default=None)
        sub.add_argument("--json", dest="as_json", action="store_true")
    args = parser.parse_args(list(argv))
    start = args.repository if args.repository is not None else Path.cwd()
    try:
        located = ws.locate(start)
        if located.workspace is None:
            raise ws.WorkspaceError(f"not in a workspace: {Path(start).resolve()}")
        if args.command == "clone":
            rows = clone(located.workspace, args.paths, args.all_repos)
            print(json.dumps({"repos": rows}) if args.as_json else
                  "\n".join(f"{row['path']}: {row['status']}" for row in rows))
        else:
            rows = status(located.workspace)
            print(json.dumps({"repos": rows}) if args.as_json else _text(rows))
    except (ws.WorkspaceError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0
```

3. Append to `workspace.py`:

```python
GITIGNORE_HEADER = "# workspace repos (gin workspace clone adds one line per repository)"


def ensure_gitignore(root: Path, lines: Sequence[str]) -> list[str]:
    """Append each missing line to `<root>/.gitignore` under the workspace header; returns what was added."""
    path = Path(root) / ".gitignore"
    existing = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    added = [line for line in lines if line not in existing]
    if not added:
        return []
    block = ([] if GITIGNORE_HEADER in existing else [GITIGNORE_HEADER]) + added
    text = ("\n".join(existing).rstrip("\n") + "\n\n" if existing else "") + "\n".join(block) + "\n"
    path.write_text(text, encoding="utf-8")
    return added


def doctor(root: Path, space: Workspace) -> dict[str, Any]:
    """Findings for `gin setup doctor`; they never flip health."""
    ignore_path = Path(root) / ".gitignore"
    ignored = set(ignore_path.read_text(encoding="utf-8").splitlines()) if ignore_path.is_file() else set()
    modules_path = Path(root) / ".gitmodules"
    modules = modules_path.read_text(encoding="utf-8") if modules_path.is_file() else ""
    repos: dict[str, dict[str, Any]] = {}
    actions: list[str] = []
    for repo in space.repos:
        present = space.present(repo)
        submodule = f"path = {repo.path}" in modules
        repos[repo.path] = {"present": present, "checks": sorted(repo.checks), "ignored": f"/{repo.path}" in ignored,
                            "submodule": submodule}
        if not present:
            actions.append(f"clone {repo.path}: gin workspace clone {repo.path}")
        if repo.workable and not repo.checks:
            actions.append(f"{repo.path} has no verify.checks")
        if f"/{repo.path}" not in ignored:
            actions.append(f"{repo.path} is not in .gitignore; gin workspace clone adds it")
        if submodule:
            actions.append(f"{repo.path} is still a submodule in .gitmodules; remove it "
                           f"(git submodule deinit -f {repo.path}; git rm -f {repo.path})")
    return {"repos": repos, "actions": actions}
```

(`Sequence` joins the `typing` import.)

4. `cli.py`: add `"workspace"` to `TOP_COMMANDS` after `"worktree"`; add `parser.add_argument("--workspace", action="store_true")` after `--monorepo`; add the dispatch block `if argv[0] == "workspace": from .workspace_cli import main as workspace_main; return workspace_main(argv[1:])` next to `worktree`.

5. `setup_service.py`: `preset(...)` gains `workspace: bool = False` and, before returning, `if workspace: assignments.append("workspace.repos=[]")` (match how `preset_assignments` values are rendered; the test asserts the literal `workspace.repos=[]`). The `init` command gains `workspace: bool = False` and, after writing the config (not on dry-run), calls `workspace_mod.ensure_gitignore(root, ["/.beads", ".planning/worktrees/"])` with the header (import `from . import workspace as workspace_mod`). In `doctor`, after the `team` block (line 561), add:

```python
        space = workspace_mod.load(root)
        if space is not None:
            detail = workspace_mod.doctor(root, space)
            checks_details["workspace"] = detail
            actions.extend(f"workspace: {action}" for action in detail["actions"])
```

6. `docs/reference/cli.md`: before `## \`gin worktree\`` insert:

````markdown
## `gin workspace`

```
gin workspace clone [--repository DIR] [--json] [--all | PATH ...]
gin workspace status [--repository DIR] [--json]
```

A workspace is a parent repository whose `workspace.repos` lists child repositories ([configuration](config.md#workspace)). `clone` clones the named entries, or every entry with `--all`, at their manifest paths from their `url` and `default_branch`; a `frozen` entry is cloned with `--depth 1`; an entry already present is reported as `present`; each path gets a `/<path>` line in the parent `.gitignore`. `status` prints one line per entry: path, `present` or `missing`, branch, `clean` or `dirty`, and `frozen`. Both commands run from anywhere inside the workspace, including a child repository.

Exit codes: 0 done; 1 outside a workspace, an unknown path, or a git failure (message on stderr); 2 invalid arguments.
````

and add `--workspace` to the setup flag list with "writes an empty `workspace.repos` list and the parent `.gitignore` entries".

7. Run `python3 -m pytest tests/workflow_core/test_workspace_cli.py tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_setup_cli.py -q`; all pass. Commit: `feat(workspace): gin workspace clone/status, setup --workspace, doctor findings (gin-workflow-workspace)`.

### Track 4: hooks and quick-check per child repository
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/hooks.py:89-98` (`status_report`), `:143-179` (`verify`), `:182-200` (`main`: `--all-repos`, repository default)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/verification.py:37-45` (`record` and `check` take `events_root`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:570-576` (`_quick_check_command` uses the child's checks)
  - Test `tests/workflow_core/test_hooks.py` (new class `WorkspaceHookTests`)
  - Test `tests/workflow_core/test_lifecycle_cli.py` (new test `test_quick_check_in_a_child_uses_its_checks`)
- **Interfaces**:
  - Consumes: `workspace.locate`, `Located.entry.checks`, `Repo.workable`.
  - Produces: `hooks._scoped(root: Path, hook: str) -> tuple[list[tuple[Path, list[tuple[str, str]]]], Path, str]` (scoped commands, events root, rigor); `verification.record(root, hook, tree, commands, *, events_root: Path | None = None)`; `verification.check(root, commit=None, *, events_root: Path | None = None)`; `gin hooks install --all-repos`; `gin quick-check` `verify_commands` from the child entry when run inside one.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** bounded to two modules with a clear spec, but the pre-push record (tree hash of the child, events in the workspace) and the `status_report`/`verify` duplication have several edge cases (no checks, frozen entry, root run, `--all-repos` with missing clones), so effort is raised.
- **Acceptance criteria**:
  - `WorkspaceHookTests` passes: `gin hooks run pre-commit` inside `services/api` runs that entry's `lint` only (asserted by a command that writes a marker file) and nothing from the parent `verify.checks`; `gin hooks status` inside the child lists `services/api:lint`; a passing pre-push inside the child appends an event to `<workspace>/.agent-workflow/runtime/events.jsonl` and the second run prints `already passed on this tree`; `gin hooks install --all-repos` from the parent installs into `services/api` only (the frozen and `beads` entries and a missing clone are skipped and listed); `gin hooks run` inside a repository with no entry checks prints `no verify commands configured`.
  - `test_quick_check_in_a_child_uses_its_checks` passes: `gin quick-check --changed-files 1 --modules 1 --format json` from `services/api` returns `verify_commands` equal to the entry's checks filtered by rigor.
  - The full suite passes.
- **Estimated complexity**: medium

#### Steps

1. In `tests/workflow_core/test_hooks.py` add a class that builds the workspace with `make_workspace` (import from `test_workspace`), gives the parent `verify.checks.lint: "touch parent-lint"` and the `services/api` entry `verify: {checks: {lint: "touch child-lint", test: "true"}}`, then asserts the acceptance criteria above by calling `hooks.main([...,"--repository", str(child)])` in-process and checking the marker files and the printed JSON. For `--all-repos`, call `hooks.main(["install", "--all-repos", "--repository", str(root)])` and assert `(child / ".git/hooks/pre-commit").is_file()` and that the output names `legacy/portal: skipped (frozen)`, `.beads: skipped (beads)`, `apps/web: skipped (not cloned)`. Run; they fail.

2. `hooks.py`: factor the collection into one helper used by `verify` and `status_report`:

```python
def _scoped(root: Path, hook: str | None) -> tuple[list[tuple[Path, list[tuple[str, str]]]], Path, str]:
    """(cwd, [(name, command)]) groups for `hook` (all names when None), the events root, and the rigor."""
    located = workspace.locate(root)
    settings = project_settings(resolve_effective_config(located.root, write=False).config.to_dict())
    if hook is None:
        names: tuple[str, ...] = ("lint", "typecheck", "test", "build", "e2e")
    else:
        names = _PRE_PUSH.get(settings.rigor, _PRE_PUSH["standard"]) if hook == "pre-push" else _PRE_COMMIT
    if located.entry is not None:
        checks = located.entry.checks
        return ([(located.repo, [(f"{located.entry.path}:{name}", checks[name]) for name in names if checks.get(name)])],
                located.root, settings.rigor)
    scoped = [(root, [(name, settings.verify_commands[name]) for name in names if settings.verify_commands.get(name)])]
    for package in settings.packages:
        checks = (package.get("verify") or {}).get("checks") or {}
        scoped.append((root / package["path"],
                       [(f"{package['path']}:{name}", checks[name]) for name in names if checks.get(name)]))
    return scoped, root, settings.rigor
```

`verify` becomes: `scoped, events_root, _ = _scoped(root, hook)`; the "no verify commands" check unchanged; `verification.check(root, "HEAD", events_root=events_root)` and `verification.record(events_root=events_root, ...)` with `root` still the child for `clean_tree`. `status_report` becomes `scoped, _, _ = _scoped(root, None)` and `names = sorted(name for _, commands in scoped for name, _ in commands)`.

3. `verification.py`: `record(root, hook, tree, commands, *, events_root=None)` uses `_events_path(events_root or root)`; `check(root, commit=None, *, events_root=None)` likewise (the tree is still computed in `root`).

4. `hooks.main`: `--repository` default `None` then `root = args.repository.resolve() if args.repository else Path.cwd().resolve()` (hooks keep the repository they fire in; `_scoped` resolves the workspace); add `parser.add_argument("--all-repos", action="store_true")`; in the `install` branch, when `args.all_repos`: `located = workspace.locate(root)`; if `located.workspace is None`: print `error: not in a workspace` to stderr, return 1; for each `repo` in `located.workspace.repos`: print `<path>: skipped (frozen)` / `(beads)` / `(not cloned)` or run `install(located.workspace.checkout(repo))` and print `<path>: <hook>: <state>` lines; return 0.

5. `lifecycle_cli._quick_check_command`: after `settings = ...` add:

```python
    located = workspace.locate(getattr(args, "start", repo_path))
    verify_commands = dict(located.entry.checks) if located.entry is not None else settings.verify_commands
    commands = {k: v for k, v in verify_commands.items() if k in _QUICK_COMMANDS[settings.rigor]}
```

and in `tests/workflow_core/test_lifecycle_cli.py` add a test that writes the workspace fixture, runs `cli_main(["quick-check", "--changed-files", "1", "--modules", "1", "--format", "json"])` with `os.chdir(child)` inside a `contextlib.chdir`-style helper (restore the cwd in `addCleanup`), and asserts `verify_commands == {"test": "true", "lint": "touch child-lint"}` filtered by `standard` rigor (so `lint` and `test`).

6. Run `python3 -m pytest tests/workflow_core/test_hooks.py tests/workflow_core/test_lifecycle_cli.py tests/workflow_core/test_verification*.py -q`; pass. Commit: `feat(workspace): hooks and quick-check run a child repository's own checks (gin-workflow-workspace)`.

### Track 5: `gin worktree` creates a child repository's worktree under the workspace
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/worktrees.py:22-50` (`_target`, `create`, `cleanup` take `root`) and `:53-77` (`main` resolves the workspace)
  - Test `tests/workflow_core/test_worktrees.py` (new class `WorkspaceWorktreeTests`)
- **Interfaces**:
  - Consumes: `workspace.locate`.
  - Produces: `worktrees._target(repo, track_id, root: Path | None = None)`, `create(repo, track_id, branch, base_ref=None, root=None)`, `cleanup(repo, track_id, root=None)`; `gin worktree create --repository <child> TRACK BRANCH [BASE]` places the worktree at `<workspace>/.planning/worktrees/<track-id>` and `cleanup --repository <child> TRACK` removes it.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one module, one new optional parameter, behaviour fixed by R10; the containment guard already exists.
- **Acceptance criteria**:
  - `WorkspaceWorktreeTests` passes: `worktrees.main(["create", "--repository", str(child), "t1", "feat/x-t1", "main"])` creates `<root>/.planning/worktrees/t1` whose `git rev-parse --git-common-dir` is `<child>/.git` and whose branch is `feat/x-t1`; `cleanup --repository <child> t1` removes it; a plain repository keeps today's path; a path escaping `.planning/worktrees` is refused.
  - The full suite passes.
- **Estimated complexity**: low

#### Steps

1. Add the test class (fixture from `test_workspace.make_workspace`), then run it; it fails because the worktree lands under `services/api/.planning/worktrees`.

2. `worktrees.py`:

```python
def _target(repo: Path, track_id: str, root: Path | None = None) -> Path:
    if not _TRACK_ID.fullmatch(track_id):
        raise ValueError(f"invalid track-id '{track_id}'")
    top = root if root is not None else Path(_git(repo, "rev-parse", "--show-toplevel"))
    worktrees = (Path(top) / ".planning/worktrees").resolve()
    target = (worktrees / track_id).resolve()
    if target.parent != worktrees:
        raise ValueError("resolved path escapes worktree root")
    return target
```

`create(repo, track_id, branch, base_ref=None, root=None)` and `cleanup(repo, track_id, root=None)` pass `root` through. In `main`, after `repo = Path(args.repository)`: `located = workspace.locate(repo)`; `root = located.root if located.entry is not None else None`; pass `root=root` to both calls; the `create` message stays. Update the module docstring: "under `.planning/worktrees` of the repository, or of the workspace for a child repository".

3. Run `python3 -m pytest tests/workflow_core/test_worktrees.py -q`; pass. Commit: `feat(workspace): worktree of a child repository under the workspace .planning/worktrees (gin-workflow-workspace)`.

### Track 6: `Repo:` on plan tracks, plan-approved check, team check-plan, route manifest
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py:188-193` (`Track.repo`), `:197` (`_META`), `:224` and `:238` (parser), after `:297` (new `check_plan_repos`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:291-301` (plan-approved workspace check; `_plan_path` helper)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py:89-90` (`check-plan` adds the workspace findings)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/routes.py:155-162` (carry `repo` into each entry) and `assignments.py:206-211` (`tracks_map` keeps `repo`)
  - Test `tests/workflow_core/test_team_gates.py` (`test_plan_tracks_reads_repo`, `test_check_plan_repos_findings`)
  - Test `tests/workflow_core/test_specs_technical_questions.py` (new class `PlanApprovedWorkspaceTests`)
  - Test `tests/workflow_core/test_routes_cli.py` (`test_repo_is_kept_in_the_manifest`)
- **Interfaces**:
  - Consumes: `workspace.Workspace.repo`, `repo_of`, `Repo.workable`, `plan_tracks`.
  - Produces: `Track(number, title, area, owner, files, repo: str = "")`; `team.check_plan_repos(space: Workspace, path: Path) -> list[str]` with messages `Track N: missing Repo:`, `Track N: Repo: X is not in workspace.repos`, `Track N: Repo: X is frozen` / `is the beads repository`, ``Track N: `file` is outside repo X``; `lifecycle_cli._plan_path(root: Path, value: str | None) -> Path | None`; `gin record plan-approved` rejection `plan-approved refused: workspace tracks\n<errors>` (exit 1) and `plan-approved refused: a workspace needs the plan file as --plan or --evidence` (exit 1); `gin team check-plan` appends the same findings; `gin routes resolve` entries and `tracks` keep a `repo` key when the input track has one.
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** a lifecycle gate across four modules (`team.py`, `lifecycle_cli.py`, `team_cli.py`, `routes.py`/`assignments.py`) with ordering constraints (the check runs after open questions and before the team authorization) and many refusal cases; the strongest model keeps the messages and exit codes consistent with the existing refusals.
- **Acceptance criteria**:
  - `test_plan_tracks_reads_repo` passes: a track with `- **Repo**: \`services/api\`` and one with `- Repo: apps/web` both parse; existing tests in the file still pass (`repo` is the last field).
  - `test_check_plan_repos_findings` passes on a plan with four tracks: missing `Repo:`, unknown repo, frozen repo, a file outside its repo; the expected list is exact and ordered by track.
  - `PlanApprovedWorkspaceTests` passes: in a workspace, `record plan-approved --evidence <plan>` with a valid plan records (gate `satisfied`); with the bad plan it exits 1 with `plan-approved refused: workspace tracks`; with `--evidence "pr-123"` (no file) it exits 1 with the `needs the plan file` message; outside a workspace the same commands behave as today (`test_workflow_without_design_doc_records_as_today` still passes).
  - `test_repo_is_kept_in_the_manifest` passes: a tracks JSON with `"repo": "services/api"` yields `assignments[0]["repo"]` and `tracks["t1"]["repo"]` equal to it, and an entry without `repo` has no key.
  - The full suite passes.
- **Estimated complexity**: medium

#### Steps

1. Tests first (the three files), run, fail.

2. `team.py`: `Track` gains `repo: str = ""` as its last field; `_META` becomes `^-\s*(?:\*\*)?(Area|Owner|Repo)(?:\*\*)?:\s*`?([^`\s]+)`?\s*$`; the seed dict at line 238 gains `"repo": ""`; `close()` passes `current["repo"]` after the files tuple. Add after `check_plan`:

```python
def check_plan_repos(space: "Workspace", path: Path) -> list[str]:
    """Workspace rules for a plan: every track names one workable `Repo:` and lists files inside it."""
    errors: list[str] = []
    for track in plan_tracks(path):
        label = f"Track {track.number}"
        if not track.repo:
            errors.append(f"{label}: missing Repo:")
            continue
        repo = space.repo(track.repo)
        if repo is None:
            errors.append(f"{label}: Repo: {track.repo} is not in workspace.repos")
            continue
        if repo.frozen:
            errors.append(f"{label}: Repo: {track.repo} is frozen")
        elif repo.shape == "beads":
            errors.append(f"{label}: Repo: {track.repo} is the beads repository")
        errors += [f"{label}: `{item}` is outside repo {track.repo}" for item in track.files
                   if space.repo_of(item) != repo]
    return errors
```

with `from .workspace import Workspace` (a real import, not a string annotation; `workspace.py` does not import `team.py`, so there is no cycle).

3. `lifecycle_cli.py`: add

```python
def _plan_path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    candidate = Path(value)
    candidate = candidate if candidate.is_absolute() else root / candidate
    return candidate if candidate.is_file() else None
```

and, in `_record_command` after the open-questions block (line 300) and before `store = ...`:

```python
        located = workspace.locate(Path(args.repository).resolve())
        if located.workspace is not None:
            plan = _plan_path(located.root, args.plan) or _plan_path(located.root, args.evidence)
            if plan is None:
                return {"status": "rejected",
                        "message": "plan-approved refused: a workspace needs the plan file as --plan or --evidence"}, 1
            from .team import check_plan_repos

            errors = check_plan_repos(located.workspace, plan)
            if errors:
                return {"status": "rejected",
                        "message": "plan-approved refused: workspace tracks\n" + "\n".join(errors)}, 1
```

4. `team_cli.py` `check-plan`: `findings = team_core.check_plan(team, args.plan)`; `located = workspace.locate(args.repository)`; `if located.workspace is not None: findings += team_core.check_plan_repos(located.workspace, args.plan)`; then `_findings(findings, ...)`.

5. `routes.py`: in the loop that appends `AssignmentManifest(...).to_dict()` (around line 160), build `entry = ...to_dict()`, then `if isinstance(track, Mapping) and track.get("repo"): entry["repo"] = str(track["repo"])`, then `entries.append(entry)`. `assignments.write_assignments`: in `tracks_map[task_id]` add `**({"repo": entry["repo"]} if entry.get("repo") else {})`.

6. Run `python3 -m pytest tests/workflow_core/test_team_gates.py tests/workflow_core/test_specs_technical_questions.py tests/workflow_core/test_routes_cli.py tests/workflow_core/test_lifecycle_cli.py -q`; pass. Commit: `feat(workspace): Repo: on plan tracks, plan-approved and check-plan refuse bad tracks, manifest keeps repo (gin-workflow-workspace)`.

### Track 7: skills: setup, plan and plan-schema, orchestrate, execute and worktrees, ship, quick
- **Dependencies**: Track 3, Track 4, Track 5, Track 6
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/setup/SKILL.md:20-23` (question 6 and `[--workspace]`)
  - Modify `plugins/gin-workflow/src/skills/plan/SKILL.md:20` (one `Repo:` sentence) and `plugins/gin-workflow/src/skills/plan/plan-schema.md:60` (`- **Repo**` line)
  - Modify `plugins/gin-workflow/src/skills/orchestrate/SKILL.md:22,24` (`repo` in the tracks JSON; child `feat/<topic>` and `gin worktree create --repository`)
  - Modify `plugins/gin-workflow/src/skills/execute/SKILL.md:19` (one sentence pointing at the `worktrees` skill)
  - Modify `plugins/gin-workflow/src/skills/worktrees/SKILL.md` (new section `## 3. Workspace`)
  - Modify `plugins/gin-workflow/src/skills/ship/SKILL.md:26,31,35,37` (per-repository items, cleanup `--repository`, `record shipped` evidence)
  - Modify `plugins/gin-workflow/src/skills/quick/SKILL.md:14` (run from the repository you change)
  - Test `tests/workflow_core/test_token_budget.py` (existing; must still pass), `tests/test_no_direct_bd.py`
- **Interfaces**:
  - Consumes: the CLI behaviour of Tracks 2 to 6.
  - Produces: instruction text only; no new skill directory, no new reference file.
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** instruction text under tight budgets (execute chain has 340 characters left, plan chain 678), so the wording needs judgement, but there is no logic.
- **Acceptance criteria**:
  - `python3 -m pytest tests/workflow_core/test_token_budget.py tests/test_no_direct_bd.py tests/workflow_core/test_role_aware_skills.py -q` passes.
  - Each edited skill contains the exact sentences below (a reviewer greps for `Repo:` in plan, `--repository <repo>` in orchestrate and ship, `## 3. Workspace` in worktrees, `--workspace` in setup).
- **Estimated complexity**: low

#### Steps

1. `setup/SKILL.md`: after question 5 add

```
6. **Workspace** — Ask whether this repository is the parent of several repositories (services, apps, a frozen legacy, shared Beads). On yes pass `--workspace` to `preset` and `init`; it writes an empty `workspace.repos` and the parent `.gitignore` lines. The lead then fills one entry per repository (`path`, `url`, `shape`, `frozen`, `default_branch`, `verify.checks`) and runs `gin workspace clone --all` and `gin hooks install --all-repos`.
```

and change the preset line to `... [--monorepo] [--workspace] [--stack-intent TEXT] --format json`.

2. `plan/SKILL.md` line 20: append the sentence `In a workspace (\`gin state --format json\` has a non-null \`workspace\`), every track adds \`Repo: <path>\` naming one workable \`workspace.repos\` entry and lists only \`Files:\` inside it; a change across two repositories is two tracks.` `plan-schema.md`: after the `- **Dependencies**` line add `- **Repo**: workspace only: the \`workspace.repos\` path this track changes`.

3. `orchestrate/SKILL.md`: step 4 JSON becomes `{"task_id", "provider_role", "model", "effort", "repo"}` with `"repo"` noted as "workspace only: the track's `Repo:`"; step 6 gains: `Workspace: for each distinct \`Repo:\`, when the child lacks \`feat/<topic>\`, run \`git -C <repo> fetch origin && git -C <repo> branch feat/<topic> origin/<default_branch>\`; a missing clone stops with \`gin workspace clone <repo>\`. Then \`gin worktree create --repository <repo> <track-id> feat/<topic>-t<N> feat/<topic>\` puts the child's worktree under the parent's \`.planning/worktrees/\`. Put \`Repo: <path>\` in each track bead's description.`

4. `execute/SKILL.md` line 19: append ` In a workspace the worktree is the track's \`Repo:\` (the \`worktrees\` skill, Workspace).` `worktrees/SKILL.md`: append

```
## 3. Workspace
When `gin state --format json` reports `workspace.current_repo`, the worktree is one child repository and the project root is the parent:
- Strip the `<repo>/` prefix from the plan's `Files:`; paths in the worktree are repo-relative.
- Read `references/shape-<shape>.md` for the entry's `shape` (`backend`, `frontend`); `library` and `qa` have none.
- Commit and push in this worktree only; the spec and plan live in the parent and are read, never edited, by a track.
- `gin` commands from inside the worktree resolve the parent: `gin task`, `gin state`, `gin review` need no `--repository`.
- Cleanup from the parent: `gin worktree cleanup --repository <repo> <track-id>`.
```

5. `ship/SKILL.md`: step 3 gains `Workspace: one integration item per \`Repo:\` with tracks, then the parent (spec, plan, docs).` Step 5 Merge gains `Workspace: \`MAIN_ROOT\` is the child checkout \`<parent>/<repo>\`; merge its track branches into the child's \`feat/<topic>\`, then \`feat/<topic>\` into \`<default_branch>\`, one repository at a time; the parent last.` Step 6 gains `In a workspace: \`gin worktree cleanup --repository <repo> <track-id>\` from the parent.` Step 7: `record shipped ... --evidence "<repo>:<merge commit>; ...; parent:<merge commit>"` for a workspace. Keep the chain under 12,000 (2,717 characters of headroom).

6. `quick/SKILL.md` step 2 gains: `In a workspace, run \`/gin:quick\` from the repository you change; \`quick-check\` returns that repository's checks.`

7. Run the budget tests; trim wording until they pass. Commit: `docs(skills): workspace behaviour in setup, plan, orchestrate, execute, worktrees, ship and quick (gin-workflow-workspace)`.

### Track 8: documentation: brownfield starter, workspace guide, reference and concept pages
- **Dependencies**: Track 7
- **Files**:
  - Create `docs/guides/workspace.md` and `docs/guides/workspace.vi.md`
  - Modify `docs/starters/brownfield.md:7-16` (scenario table), `:77-108` (Repository and workspace setup), `:109-404` (a `**Where:**` line under each stage's `**Who:**`), and the same sections of `docs/starters/brownfield.vi.md`
  - Modify `docs/reference/config.md:61` (`monorepo`, `packages` row points to the workspace section) and after `:171` (new `### \`workspace\`` section)
  - Modify `docs/concepts/state-model.md:47-66` (tree and ownership sentence), `docs/concepts/lifecycle.md:7-22` and `:60-65` (orchestrate and ship per repository), `docs/guides/claude-workflow.md:53-66` (session worktree of the parent), `docs/roles.md:16-24` (Files column mentions the repository per role)
  - Modify `README.md:16` (Guides row adds `[workspace](docs/guides/workspace.md)`), `mkdocs.yml:113-124` (nav entry `- Workspace: guides/workspace.md`) and `:63-66` (`Workspace: Không gian làm việc`)
  - Test `tests/workflow_core/test_docs_coverage.py` (existing)
- **Interfaces**:
  - Consumes: the behaviour and command names of Tracks 2 to 7.
  - Produces: documentation only.
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** nine pages of prose with a fixed outline (the spec's "Workflow by role"), the style rules, and link and nav checks; judgement on wording, no logic.
- **Acceptance criteria**:
  - `python3 -m pytest tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_docs_check.py -q` passes and `mkdocs build --strict` succeeds.
  - `docs/guides/workspace.md` has the sections: Layout, Setup once (tech lead), Onboarding (every engineer), PM and BA, Tech lead, Backend and frontend engineers, QA, Commands, Limits; each role section names the directory to open and the commands per stage.
  - The brownfield starter's "Repository and workspace setup" shows the manifest with the six repositories (`legacy/shop-portal` frozen, `services/order-api`, `services/catalog-api`, `apps/web-shop`, `apps/web-admin`, `qa`), `gin workspace clone --all`, `gin hooks install --all-repos`, and keeps the one-repository subtree variant as a short alternative; every stage section has a `**Where:**` line.
- **Estimated complexity**: low

#### Steps

1. Write `docs/guides/workspace.md` from the spec's "Workflow by role" section, with a `## Layout` first:

```yaml
workspace:
  repos:
    - {path: legacy/shop-portal, url: git@github.com:acme/shop-portal.git, frozen: true}
    - path: services/order-api
      url: git@github.com:acme/order-api.git
      shape: backend
      verify: {checks: {test: mvn -q test, build: mvn -q package}}
    - {path: apps/web-shop, url: git@github.com:acme/web-shop.git, shape: frontend,
       verify: {checks: {lint: npm run lint, test: npm test, build: npm run build}}}
    - {path: qa, url: git@github.com:acme/qa.git, shape: qa}
    - {path: .beads, url: git@github.com:acme/beads.git, shape: beads}
```

then `## Setup once`, `## Onboarding`, `## PM and BA`, `## Tech lead`, `## Backend and frontend engineers`, `## QA`, `## Commands` (`gin workspace clone|status`, `gin hooks install --all-repos`, `gin worktree create --repository`, what `gin state` reports), `## Limits` (one repository per track, no packages inside a child, no version pinning, a child cloned elsewhere is standalone). Translate it to `workspace.vi.md` following `docs/guides/team.vi.md`'s conventions (prose Vietnamese, code and identifiers unchanged).

2. Rewrite `docs/starters/brownfield.md` lines 7-16 and 77-108 per the acceptance criteria; the areas in the `team:` block become `legacy: {paths: ["legacy/shop-portal/**"], ...}`, `api: {paths: ["services/**"], ...}`, `web: {paths: ["apps/**"], ...}`, `qa: {paths: ["qa/**"], ...}`. Add `**Where:**` lines: Setup and team setup, Survey, Roadmap, Milestone planning, Discuss, Plan and orchestrate, Ship, Milestone review: `the parent`; Test cases, E2E: `the \`qa\` repository`; Execute: `the track worktree \`<parent>/.planning/worktrees/<track-id>\` (one service or one app)`. Mirror in `brownfield.vi.md`.

3. `config.md`: new section

```markdown
### `workspace`

Present when the repository is the parent of several repositories ([guide](../guides/workspace.md)). `repos` lists them: `path` (relative, gitignored in the parent), `url`, `shape` (`frontend`, `backend`, `library`, `qa`, `beads`), `frozen` (read only: no hooks, tracks, or worktrees; cloned shallow), `default_branch` (default `main`), and `verify.checks` with the same keys as the root block. The `beads` entry sits at `.beads` and holds the shared Beads database. `project.packages` keeps its meaning inside one repository and is ignored for workspace entries.
```

4. `state-model.md`: in the tree, under `.planning/` add `worktrees/    git-fallback worktrees, one per track; in a workspace, worktrees of the child repositories`, and after the tree: "In a workspace the parent owns config, specs, plans, runtime, and beads; each child owns its hooks, branches, and worktrees." `lifecycle.md`: under Stages and gates add one sentence after orchestrate's mention: "In a workspace, each plan track names its `Repo:` and orchestrate creates the worktree of that child repository under the parent's `.planning/worktrees/`"; under Ship: "In a workspace ship integrates one repository at a time, the parent last, and `record shipped` carries one merge commit per repository." `claude-workflow.md:53-66`: add "In a workspace the session worktree is a worktree of the parent, where specs and plans live." `roles.md`: Developer row Files column adds "in a workspace, the child repository of the track".

5. `README.md` Guides row and `mkdocs.yml` nav and `nav_translations`. Run the docs tests and `mkdocs build --strict` (skip the build if mkdocs is not installed and say so in the handoff). Commit: `docs(workspace): guide, brownfield starter, configuration and concept pages (gin-workflow-workspace)`.

### Track 9: the qwikfone validation bead
- **Dependencies**: Track 8
- **Files**:
  - Modify none in this repository; the bead description below is written to a temporary file outside the repository and passed to `--body-file`
- **Interfaces**:
  - Consumes: the qwikfone Beads database at `~/qwikfone/.beads` (`bd -C ~/qwikfone`).
  - Produces: one task bead in qwikfone titled `Set up the gin workspace: submodules to workspace.repos`, whose description is the text in step 1; its id is noted on `gin-workflow-workspace`.
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** a single instruction document with the steps fixed by R15 and the repository facts gathered in discuss; no logic.
- **Human gate**: after `./install.sh --platform claude` from this branch, the user runs the bead in a `~/qwikfone` session (commits, pushes, and the removal of the pointer CI happen there under that session's approvals) and attaches the outputs to the bead; gaps come back to this epic before ship.
- **Acceptance criteria**:
  - `bd -C ~/qwikfone show <id>` prints the bead with the description sections: Preconditions, Manifest, Git steps, Workspace commands, What stays in the parent, What to retire, Teammate steps for `Readme.md`, Checks to attach.
  - After the run: no `.gitmodules` in `~/qwikfone`; each of the seven paths is gitignored and a standalone clone; `gin setup doctor` has no `workspace:` action; `gin state --format json` from `~/qwikfone` and `~/qwikfone/backend` print the same `gates`; `gin hooks run pre-commit` inside `backend` runs `backend:lint` only; an orchestrate dry run of a two-track plan creates `.planning/worktrees/<t1>` (common dir `backend/.git`) and `<t2>` (common dir `frontend/.git`).
- **Estimated complexity**: low

#### Steps

1. Write this text to a temporary file (for example `/tmp/qwikfone-workspace-bead.md`):

```markdown
# Set up the gin workspace: submodules to workspace.repos

Run this in a Claude Code session started in `~/qwikfone`. The parent becomes a gin workspace; every submodule becomes a plain clone listed in `workspace.repos`.

## Preconditions
- `gin --help` lists `workspace`; otherwise run `./install.sh --platform claude` in `~/gin-fam/gin-workflow` on `feat/workspace` first.
- Every submodule is committed and pushed: `git submodule foreach 'git status --porcelain && git log --oneline @{u}..'` prints nothing.
- No active parent worktree: `git worktree list` shows only the main checkout (finish or remove the others).

## Manifest
Add to `.agent-workflow/config.yaml`:
```yaml
workspace:
  repos:
    - {path: backend, url: git@github.com:Qwikfoneoffice/QwikFone_Office_Backend.git, shape: backend,
       default_branch: main, verify: {checks: {lint: pnpm lint:ci, test: pnpm test:ci}}}
    - {path: frontend, url: git@github.com:Qwikfoneoffice/QwikFone_Office_Frontend.git, shape: frontend,
       default_branch: main, verify: {checks: {lint: pnpm lint, test: pnpm test:ci}}}
    - {path: qfo-vision, url: git@github.com:Qwikfoneoffice/qfo-vision.git, shape: backend, default_branch: main,
       verify: {checks: {test: uv run pytest}}}
    - {path: qwikfone-metabase, url: git@github.com:Qwikfoneoffice/qwikfone-metabase.git, shape: backend,
       default_branch: master, verify: {checks: {test: pytest}}}
    - {path: QFO-AT, url: git@github.com:Qwikfoneoffice/QFO-AT.git, shape: qa, default_branch: main,
       verify: {checks: {lint: pnpm lint, test: pnpm test:unit}}}
    - {path: QFO_Document, url: git@github.com:Qwikfoneoffice/QFO_Document.git, shape: library, default_branch: main}
    - {path: .beads, url: git@github.com:Qwikfoneoffice/qfo-bd.git, shape: beads, default_branch: main}
```
Confirm each `default_branch` with `git -C <path> symbolic-ref refs/remotes/origin/HEAD`.

## Git steps
For each path above: `git submodule deinit -f <path>`, `git rm -f <path>`, `rm -rf .git/modules/<name>` (`<name>` as in `.gitmodules`). Then `git rm -f .gitmodules`. Keep `postgres-mcp/`, `scripts/`, `docker-compose*.yml`, `nginx.conf`, `at-proxy.conf`, `docs/`, `.planning/` as they are.

## Workspace commands
`gin workspace clone --all` (clones the seven paths and adds `/<path>` lines to `.gitignore`), `gin hooks install --all-repos`, `gin setup doctor` (no `workspace:` action left), `gin workspace status`.

## What to retire
Delete `.github/workflows/submodule-pointers.yml`, `scripts/check-submodule-pointers.sh`, `docs/submodule-pointers.md`; fix `qwikfone.code-workspace` (`qwikfone_metabase` to `qwikfone-metabase`).

## Teammate steps for Readme.md
After `git pull`: `git submodule deinit --all -f`, `rm -rf .git/modules`, `gin workspace clone --all`, then `gin hooks install` inside each repository they work on. Open the IDE on the repository, not the parent.

## Checks to attach
Attach the output of: `gin workspace status`; `gin state --format json` from `~/qwikfone` and from `~/qwikfone/backend` (same `gates`); `gin hooks run pre-commit --repository ~/qwikfone/backend` (runs `backend:lint` only); `/gin:orchestrate` dry run of a plan with `Repo: backend` and `Repo: frontend` tracks, then `git -C .planning/worktrees/<t1> rev-parse --git-common-dir` and the same for `<t2>`. Commit the parent and push only with the user's approval.
```

2. Create the bead: `bd -C /home/gin/qwikfone create "Set up the gin workspace: submodules to workspace.repos" -t task -p 2 --body-file /tmp/qwikfone-workspace-bead.md` and record its id in this epic's bead notes: `gin task update gin-workflow-workspace --notes "qwikfone validation bead: <id>"`. Nothing to commit in this repository. Stop at the human gate.

## Integration
- **Branch**: `feat/workspace`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes (the pre-push hook runs it once at ship).
- [ ] `python3 -m pytest tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_coverage.py tests/test_no_direct_bd.py tests/gin_orchestrator/test_harness_packaging.py -q` passes after Tracks 7 and 8.
- [ ] Manual: the Track 9 bead run in qwikfone meets its acceptance criteria; every gap is fixed in this epic or filed as a gin-workflow bead with a reason before ship.

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog (`haiku`, `sonnet`, `opus`; efforts `low` to `max`) using the route rubric.
- Provider roles: `backend` for Python changes, `docs` for skills, docs, and the bead text.
- `install.sh` rebuilds `plugins/*/dist/` (untracked); run it after the merge, and before the Track 9 run from this branch.
- Deliverable merge-holds apply only to the Parent Bead `gin-workflow-workspace`; each track bead closes when its tests and review pass.

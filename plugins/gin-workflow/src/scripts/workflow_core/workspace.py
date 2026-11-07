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

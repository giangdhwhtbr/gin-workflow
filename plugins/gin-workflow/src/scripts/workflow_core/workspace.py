"""A workspace: a parent repository whose `.agent-workflow/config.yaml` lists child repositories in `workspace.repos`.

Child repositories are plain git clones at their manifest path under the parent, gitignored there. Every `gin`
command run inside a child (or inside a child's track worktree) resolves the parent as its project root.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any, Mapping, Sequence

from .checkout import main_checkout
from .configuration import require_yaml

SHAPES = ("frontend", "backend", "library", "qa", "beads")
CHECK_NAMES = ("lint", "typecheck", "test", "build", "e2e")
CHECKED_SHAPES = ("frontend", "backend", "qa")  # entries whose hooks are expected to run something
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
    given = str(raw.get("path", "")).strip()
    pure = PurePosixPath(given)
    if not given or pure.is_absolute() or ".." in pure.parts or pure.as_posix() == ".":
        raise WorkspaceError(f"workspace.repos: path must be relative and inside the workspace: {given!r}")
    path = pure.as_posix()
    if pure.parts[0] in RESERVED:
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
    checks = {}
    for name, command in ((raw.get("verify") or {}).get("checks") or {}).items():
        if name not in CHECK_NAMES:
            raise WorkspaceError(f"workspace.repos: {path}: unknown check {name}")
        if str(command).strip():
            checks[name] = str(command)
    return Repo(path, url, shape, frozen, str(raw.get("default_branch", "main")), checks)


def repos_from(config: Mapping[str, Any]) -> tuple[Repo, ...]:
    """Parse and validate `workspace.repos`; an empty tuple when the key is absent."""
    if not isinstance(config, Mapping) or "workspace" not in config:
        return ()
    block = config["workspace"]
    if not isinstance(block, Mapping):
        raise WorkspaceError("workspace must be a mapping")
    raws = block.get("repos")
    if not isinstance(raws, list):
        raise WorkspaceError("workspace.repos must be a list")
    for number, raw in enumerate(raws, 1):
        if not isinstance(raw, Mapping):
            raise WorkspaceError(f"workspace.repos entry {number} must be a mapping")
    repos = tuple(_entry(raw) for raw in raws)
    paths = [repo.path for repo in repos]
    for index, path in enumerate(paths):
        if path in paths[:index]:
            raise WorkspaceError(f"workspace.repos: duplicate path {path}")
        for other in paths:
            if other != path and PurePosixPath(path) in PurePosixPath(other).parents:
                raise WorkspaceError(f"workspace.repos: {other} nests inside {path}")
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
    return Located(given, checkout, own, None)


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
    from .hooks import findings as hook_findings  # hooks imports this module

    ignore_path = Path(root) / ".gitignore"
    ignored = set(ignore_path.read_text(encoding="utf-8").splitlines()) if ignore_path.is_file() else set()
    modules_path = Path(root) / ".gitmodules"
    modules = modules_path.read_text(encoding="utf-8") if modules_path.is_file() else ""
    submodule_paths = {value.strip() for key, _, value in (line.partition("=") for line in modules.splitlines()
                                                           if "=" in line) if key.strip() == "path"}
    repos: dict[str, dict[str, Any]] = {}
    actions: list[str] = []
    for repo in space.repos:
        present = space.present(repo)
        submodule = repo.path in submodule_paths
        repos[repo.path] = {"present": present, "checks": sorted(repo.checks), "ignored": f"/{repo.path}" in ignored,
                            "submodule": submodule}
        if not present:
            actions.append(f"clone {repo.path}: gin workspace clone {repo.path}")
        if repo.workable and repo.shape in CHECKED_SHAPES and not repo.checks:
            actions.append(f"{repo.path} has no verify.checks")
        if present and repo.workable and repo.checks:
            repos[repo.path]["hooks"], found = hook_findings(space.checkout(repo), install="gin hooks install --all-repos")
            actions.extend(f"{repo.path}: {action}" for action in found)
        if f"/{repo.path}" not in ignored:
            actions.append(f"{repo.path} is not in .gitignore; gin workspace clone adds it")
        if submodule:
            actions.append(f"{repo.path} is still a submodule in .gitmodules; remove it "
                           f"(git submodule deinit -f {repo.path}; git rm -f {repo.path})")
    return {"repos": repos, "actions": actions}

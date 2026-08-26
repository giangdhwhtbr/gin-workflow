"""Git-worktree workspace adapter using the repository's safety scripts."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
from typing import Callable, Sequence

from .contracts import ProviderBase, ProviderResult, WorkspaceRecord, WorkspaceRequest


Runner = Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]]
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def _default_runner(argv: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)


def _git(argv: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str] | None:
    """Read-only git query, tolerant of a missing git binary or non-git directory."""
    try:
        return subprocess.run(
            ["git", *argv], cwd=cwd, text=True, capture_output=True, check=False, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return None


class WorktreeWorkspaceProvider(ProviderBase):
    provider_name = "git-worktrees"
    provider_type = "workspace"
    capabilities = frozenset({"workspace.create", "workspace.isolate", "workspace.cleanup"})

    def __init__(
        self,
        repository_root: Path,
        *,
        worktree_root: Path | None = None,
        create_script: Path | None = None,
        cleanup_script: Path | None = None,
        runner: Runner | None = None,
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        scripts = Path(__file__).resolve().parent.parent
        self.worktree_root = Path(worktree_root or self.repository_root / ".planning/worktrees").resolve()
        supported_root = (self.repository_root / ".planning/worktrees").resolve()
        self._configuration_error = (
            "non-default worktree root is unsupported by worktree safety scripts"
            if self.worktree_root != supported_root
            else ""
        )
        self.create_script = Path(create_script or scripts / "worktree-create.sh")
        self.cleanup_script = Path(cleanup_script or scripts / "worktree-cleanup.sh")
        self._runner = runner or _default_runner
        available = runner is not None or (self.create_script.is_file() and self.cleanup_script.is_file())
        super().__init__(available=available, health_detail="worktree safety scripts were not found" if not available else "")
        self._workspaces: dict[str, WorkspaceRecord] = {}

    def _path(self, workspace_id: str) -> Path | None:
        candidate = (self.worktree_root / workspace_id).resolve()
        try:
            candidate.relative_to(self.worktree_root)
        except ValueError:
            return None
        return candidate

    def _discover_branch(self, path: Path) -> str:
        completed = _git(["rev-parse", "--abbrev-ref", "HEAD"], path)
        if completed is None or completed.returncode:
            return ""
        branch = completed.stdout.strip()
        return "" if branch in ("", "HEAD") else branch  # "HEAD" means a detached checkout

    def _resolve_commit(self, cwd: Path, ref: str) -> str:
        completed = _git(["rev-parse", ref], cwd)
        if completed is None or completed.returncode:
            return ""
        return completed.stdout.strip()

    def _registered_worktree_paths(self) -> set[Path]:
        completed = _git(["worktree", "list", "--porcelain"], self.repository_root)
        if completed is None or completed.returncode:
            return set()
        paths: set[Path] = set()
        for line in completed.stdout.splitlines():
            if line.startswith("worktree "):
                paths.add(Path(line[len("worktree "):]).resolve())
        return paths

    def _adopt_existing_worktree(
        self, path: Path, request: WorkspaceRequest
    ) -> WorkspaceRecord | None:
        """Idempotently adopt an existing, verified worktree instead of rejecting it."""
        if not path.is_dir() or not (path / ".git").exists():
            return None
        if path.resolve() not in self._registered_worktree_paths():
            return None
        actual_branch = self._discover_branch(path)
        if not actual_branch or actual_branch != request.branch:
            return None
        head = self._resolve_commit(path, "HEAD")
        base = self._resolve_commit(self.repository_root, request.base_ref)
        if not head or not base:
            return None
        ancestor_check = _git(["merge-base", "--is-ancestor", base, head], self.repository_root)
        if ancestor_check is None or ancestor_check.returncode:
            return None
        return WorkspaceRecord(request.workspace_id, actual_branch, path)

    def _invoke(self, argv: Sequence[str]) -> ProviderResult[bool]:
        try:
            completed = self._runner(argv, self.repository_root)
        except (OSError, subprocess.SubprocessError) as error:
            return ProviderResult.unavailable(f"worktree integration unavailable: {error}")
        if completed.returncode:
            detail = completed.stderr.strip() or completed.stdout.strip() or "unknown worktree error"
            return ProviderResult.unavailable(f"worktree integration unavailable: {detail}")
        return ProviderResult.success(True)

    def create(self, request: WorkspaceRequest, *, idempotency_key: str) -> ProviderResult[WorkspaceRecord]:
        if self._configuration_error:
            return ProviderResult.invalid(self._configuration_error)
        if guarded := self._guard():
            return guarded
        if replay := self._replay("create", idempotency_key, request):
            return replay
        if not _SAFE_ID.fullmatch(request.workspace_id) or not request.branch.strip() or not idempotency_key:
            return ProviderResult.invalid("safe workspace_id, branch, and idempotency_key are required")
        path = self._path(request.workspace_id)
        if path is None:
            return ProviderResult.invalid("workspace path escapes configured worktree root")
        if path.exists():
            adopted = self._adopt_existing_worktree(path, request)
            if adopted is None:
                return ProviderResult.invalid(f"workspace already exists: {request.workspace_id}")
            self._workspaces[request.workspace_id] = adopted
            return self._remember("create", idempotency_key, request, ProviderResult.success(adopted))
        invoked = self._invoke(
            [str(self.create_script), request.workspace_id, request.branch, request.base_ref]
        )
        if invoked.value is None:
            return ProviderResult(invoked.status, message=invoked.message)
        record = WorkspaceRecord(request.workspace_id, request.branch, path)
        self._workspaces[request.workspace_id] = record
        return self._remember("create", idempotency_key, request, ProviderResult.success(record))

    def isolate(self, workspace_id: str) -> ProviderResult[WorkspaceRecord]:
        if self._configuration_error:
            return ProviderResult.invalid(self._configuration_error)
        if guarded := self._guard():
            return guarded
        if not _SAFE_ID.fullmatch(workspace_id):
            return ProviderResult.invalid("safe workspace_id is required")
        path = self._path(workspace_id)
        if path is None or not path.is_dir():
            return ProviderResult.invalid(f"unknown workspace: {workspace_id}")
        record = self._workspaces.get(workspace_id)
        if record is None:
            record = WorkspaceRecord(workspace_id, self._discover_branch(path), path)
            self._workspaces[workspace_id] = record
        return ProviderResult.success(record)

    def bootstrap(self, workspace_id: str) -> ProviderResult[bool]:
        """Initialize submodules and install dependencies before a worker runs here.

        Best-effort and evidence-driven: submodule init (git) and a JS dependency
        install (npm) are the concrete gaps the worker incident hit -- a worker was
        dispatched into a fresh worktree with no node_modules and its type-check
        failed mid-task instead of being caught before dispatch.
        """
        if self._configuration_error:
            return ProviderResult.invalid(self._configuration_error)
        if guarded := self._guard():
            return guarded
        if not _SAFE_ID.fullmatch(workspace_id):
            return ProviderResult.invalid("safe workspace_id is required")
        path = self._path(workspace_id)
        if path is None or not path.is_dir():
            return ProviderResult.invalid(f"unknown workspace: {workspace_id}")
        if (path / ".gitmodules").is_file():
            submodules = _git(["submodule", "update", "--init", "--recursive"], path)
            if submodules is None or submodules.returncode:
                detail = (submodules.stderr.strip() if submodules else "git unavailable") or "unknown error"
                return ProviderResult.unavailable(f"submodule bootstrap failed: {detail}")
        if (path / "package.json").is_file() and not (path / "node_modules").is_dir():
            install_argv = ["ci"] if (path / "package-lock.json").is_file() else ["install"]
            try:
                completed = subprocess.run(
                    ["npm", *install_argv],
                    cwd=path,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=600,
                )
            except (OSError, subprocess.SubprocessError) as error:
                return ProviderResult.unavailable(f"dependency bootstrap failed: {error}")
            if completed.returncode:
                detail = completed.stderr.strip() or completed.stdout.strip() or "npm install failed"
                return ProviderResult.unavailable(f"dependency bootstrap failed: {detail}")
        return ProviderResult.success(True)

    def cleanup(self, workspace_id: str, *, idempotency_key: str) -> ProviderResult[bool]:
        if self._configuration_error:
            return ProviderResult.invalid(self._configuration_error)
        if guarded := self._guard():
            return guarded
        if replay := self._replay("cleanup", idempotency_key, workspace_id):
            return replay
        if not _SAFE_ID.fullmatch(workspace_id) or not idempotency_key:
            return ProviderResult.invalid("safe workspace_id and idempotency_key are required")
        path = self._path(workspace_id)
        if path is None:
            return ProviderResult.invalid("workspace path escapes configured worktree root")
        if not path.exists():
            return self._remember("cleanup", idempotency_key, workspace_id, ProviderResult.success(True, idempotent=True))
        invoked = self._invoke([str(self.cleanup_script), workspace_id])
        if invoked.value is None:
            return invoked
        self._workspaces.pop(workspace_id, None)
        return self._remember("cleanup", idempotency_key, workspace_id, ProviderResult.success(True))

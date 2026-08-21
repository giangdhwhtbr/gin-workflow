"""Non-invasive Git checkpoint creation for review source snapshots."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Dict, List, Mapping, Tuple

from review_ledger.source_identity import (
    canonicalize_scope,
    compute_source_scope_hash,
    compute_tree_hash_for_commit,
    find_nested_repositories,
    get_git_files,
    get_nested_repository_paths,
    is_excluded_path,
    is_generated_path,
    is_path_in_scope,
)


class GitAdapterError(RuntimeError):
    """Raised for Git checkpoint integrity failures."""


@dataclass(frozen=True)
class SourceCheckpoint:
    repository_id: str
    checkpoint_sha: str
    checkpoint_ref: str
    source_scope_hash: str
    source_tree_hash: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "repository_id": self.repository_id,
            "checkpoint_sha": self.checkpoint_sha,
            "checkpoint_ref": self.checkpoint_ref,
            "source_scope_hash": self.source_scope_hash,
            "source_tree_hash": self.source_tree_hash,
        }


def _run_git(
    repo_path: str,
    *args: str,
    env: Mapping[str, str] | None = None,
    input_bytes: bytes | None = None,
) -> bytes:
    process = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        env=None if env is None else dict(env),
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    if process.returncode:
        detail = process.stderr.decode("utf-8", "replace").strip()
        raise GitAdapterError(f"git {' '.join(args)} failed: {detail}")
    return process.stdout


def _repository_root(repo_path: str) -> Path:
    supplied = Path(repo_path).resolve()
    root = Path(
        _run_git(str(supplied), "rev-parse", "--show-toplevel")
        .decode("utf-8", "surrogateescape")
        .strip()
    ).resolve()
    if root != supplied:
        raise GitAdapterError(
            "repository path must identify its own Git root; declare nested repositories separately"
        )
    return root


def get_git_status_files(repo_path: str) -> List[Tuple[str, str]]:
    raw = _run_git(
        repo_path,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--ignore-submodules=none",
    )
    fields = raw.split(b"\0")
    result: List[Tuple[str, str]] = []
    index = 0
    while index < len(fields):
        field = fields[index]
        index += 1
        if not field:
            continue
        status = field[:2].decode("ascii", "replace")
        path = field[3:].decode("utf-8", "surrogateescape")
        result.append((status, path))
        if "R" in status or "C" in status:
            if index < len(fields) and fields[index]:
                original_path = fields[index].decode("utf-8", "surrogateescape")
                result.append((status, original_path))
            index += 1
    return result


def _tracked_gitlinks(repo_path: str) -> set[str]:
    return {
        item["path"]
        for item in get_git_files(repo_path)
        if item["mode"] == "160000"
    }


def _validate_nested_repositories(repo_path: str, scope: Mapping[str, Any]) -> None:
    declared = set(get_nested_repository_paths(scope))
    gitlinks = _tracked_gitlinks(repo_path)
    ambiguous = [
        path
        for path in find_nested_repositories(repo_path, scope)
        if path not in declared and path not in gitlinks
    ]
    if ambiguous:
        raise GitAdapterError(
            "undeclared nested repository overlaps review scope:\n"
            + "\n".join(f"- {path}" for path in ambiguous)
        )


def validate_working_tree_cleanliness(repo_path: str, scope: Mapping[str, Any]) -> None:
    _repository_root(repo_path)
    canonicalize_scope(scope)
    _validate_nested_repositories(repo_path, scope)
    unrelated: List[str] = []
    for _status, path in get_git_status_files(repo_path):
        if path == ".planning" or path.startswith(".planning/"):
            continue
        if is_path_in_scope(path, scope):
            continue
        if (
            is_excluded_path(path, scope)
            or is_generated_path(path, scope)
            or any(
                path == nested or path.startswith(nested + "/")
                for nested in get_nested_repository_paths(scope)
            )
        ):
            continue
        unrelated.append(path)
    if unrelated:
        raise GitAdapterError(
            "Unrelated working-tree changes detected outside review scope:\n"
            + "\n".join(f"- {path}" for path in sorted(set(unrelated)))
        )


def get_current_branch(repo_path: str) -> str:
    return _run_git(repo_path, "branch", "--show-current").decode().strip()


def _validate_review_ref(repo_path: str, review_ref: str) -> None:
    if not review_ref.startswith("refs/gin/review/"):
        raise GitAdapterError("review_ref must use dedicated namespace refs/gin/review/")
    process = subprocess.run(
        ["git", "check-ref-format", review_ref],
        cwd=repo_path,
        capture_output=True,
        check=False,
    )
    if process.returncode:
        raise GitAdapterError("review_ref is not a valid Git ref")
    symbolic = subprocess.run(
        ["git", "symbolic-ref", "-q", review_ref],
        cwd=repo_path,
        capture_output=True,
        check=False,
    )
    if symbolic.returncode == 0:
        raise GitAdapterError("review_ref must not be symbolic")


def _update_review_ref(repo_path: str, review_ref: str, checkpoint_sha: str) -> None:
    current = subprocess.run(
        ["git", "rev-parse", "--verify", review_ref],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    expected = current.stdout.strip() if current.returncode == 0 else "0" * 40
    _run_git(repo_path, "update-ref", "--no-deref", review_ref, checkpoint_sha, expected)


def _remove_filtered_entries(
    repo_path: str,
    scope: Mapping[str, Any],
    *,
    index_file: str,
    env: Mapping[str, str],
) -> None:
    nested = get_nested_repository_paths(scope)
    filtered = sorted(
        {
            item["path"]
            for item in get_git_files(repo_path, index_file=index_file)
            if is_excluded_path(item["path"], scope)
            or is_generated_path(item["path"], scope)
            or any(
                item["path"] == root or item["path"].startswith(root + "/")
                for root in nested
            )
        }
    )
    if filtered:
        _run_git(
            repo_path,
            "update-index",
            "--force-remove",
            "--",
            *filtered,
            env=env,
        )


def _resolve_commit(repo_path: str, ref: str) -> str:
    return _run_git(repo_path, "rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()


def create_source_checkpoint(
    repo_path: str,
    scope: Mapping[str, Any],
    task_id: str,
    base_ref: str = "HEAD",
    review_ref: str | None = None,
    *,
    repository_id: str = "primary",
    commit_msg: str | None = None,
) -> SourceCheckpoint:
    """Create a dedicated review commit without changing HEAD, branch, or real index."""
    root = str(_repository_root(repo_path))
    canonical_scope = canonicalize_scope(scope)
    validate_working_tree_cleanliness(root, canonical_scope)
    base_sha = _resolve_commit(root, base_ref)
    target_ref = review_ref or f"refs/gin/review/{task_id}"
    _validate_review_ref(root, target_ref)

    before_head = _run_git(root, "rev-parse", "HEAD")
    before_branch = _run_git(root, "branch", "--show-current")
    before_status = _run_git(
        root, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=none"
    )
    before_cached = _run_git(root, "diff", "--cached", "--binary")

    fd, temporary_index = tempfile.mkstemp(prefix="gin-review-index-")
    os.close(fd)
    os.unlink(temporary_index)
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = temporary_index
    try:
        current_head_sha = _resolve_commit(root, "HEAD")
        _run_git(root, "read-tree", current_head_sha, env=env)
        _remove_filtered_entries(
            root,
            canonical_scope,
            index_file=temporary_index,
            env=env,
        )
        checkpoint_paths = sorted(
            {
                path
                for _status, path in get_git_status_files(root)
                if is_path_in_scope(path, canonical_scope)
            }
        )
        if checkpoint_paths:
            _run_git(root, "add", "-A", "--", *checkpoint_paths, env=env)
        tree_sha = _run_git(root, "write-tree", env=env).decode().strip()
        message = (commit_msg or f"gin review checkpoint for {task_id}") + "\n"
        checkpoint_sha = _run_git(
            root,
            "commit-tree",
            tree_sha,
            "-p",
            base_sha,
            env=env,
            input_bytes=message.encode("utf-8"),
        ).decode().strip()
    finally:
        try:
            os.unlink(temporary_index)
        except FileNotFoundError:
            pass

    after_head = _run_git(root, "rev-parse", "HEAD")
    after_branch = _run_git(root, "branch", "--show-current")
    after_status = _run_git(
        root, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=none"
    )
    after_cached = _run_git(root, "diff", "--cached", "--binary")
    if (before_head, before_branch, before_status, before_cached) != (
        after_head,
        after_branch,
        after_status,
        after_cached,
    ):
        raise GitAdapterError("checkpoint mutated HEAD, branch, index, or working-tree status")

    _update_review_ref(root, target_ref, checkpoint_sha)

    return SourceCheckpoint(
        repository_id=repository_id,
        checkpoint_sha=checkpoint_sha,
        checkpoint_ref=target_ref,
        source_scope_hash=compute_source_scope_hash(canonical_scope),
        source_tree_hash=compute_tree_hash_for_commit(
            repository_id, root, canonical_scope, checkpoint_sha
        ),
    )


def push_review_ref(repo_path: str, remote_name: str, task_id: str) -> None:
    review_ref = f"refs/gin/review/{task_id}"
    _run_git(repo_path, "push", remote_name, f"{review_ref}:{review_ref}")


def fetch_review_ref(repo_path: str, remote_name: str, task_id: str) -> str:
    review_ref = f"refs/gin/review/{task_id}"
    _run_git(repo_path, "fetch", remote_name, f"{review_ref}:{review_ref}")
    return _run_git(repo_path, "rev-parse", review_ref).decode().strip()

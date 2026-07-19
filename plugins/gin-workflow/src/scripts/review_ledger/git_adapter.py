import subprocess
import os
import re
from typing import Dict, Any, List, Tuple
from review_ledger.source_identity import is_path_in_scope, validate_untracked_files

class GitAdapterError(RuntimeError):
    """Raised for any Git adapter failures."""
    pass

def get_git_status_files(repo_path: str) -> List[Tuple[str, str]]:
    """
    Runs `git status --porcelain` and returns list of (status_code, relative_path).
    Status codes are like 'M', 'A', 'D', 'R', '??'.
    """
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        raise GitAdapterError(f"Failed to get git status: {e.stderr}")

    files = []
    for line in res.stdout.splitlines():
        if not line.strip():
            continue
        # Format: XY path or XY path1 -> path2
        status_part = line[:2]
        path_part = line[3:].strip()
        
        # Handle rename format "path1 -> path2"
        if " -> " in path_part:
            # We want the destination path for scope checking and staging
            _, path_part = path_part.split(" -> ", 1)
        
        # Strip quotes if git quoted the path
        if path_part.startswith('"') and path_part.endswith('"'):
            path_part = path_part[1:-1]
            
        files.append((status_part, path_part))
    return files

def validate_working_tree_cleanliness(repo_path: str, scope: Dict[str, Any]) -> None:
    """
    Checks that no modified or untracked changes exist outside the allowed scope.
    Also checks for prohibited untracked files within the scope.
    Raises GitAdapterError if unrelated or prohibited files exist.
    """
    status_files = get_git_status_files(repo_path)
    
    out_of_scope_changes = []
    for status, path in status_files:
        # Ignore review ledger/planning files as they are review artifacts, not source code
        if path.startswith(".planning/") or path == ".planning":
            continue
        if not is_path_in_scope(path, scope):
            out_of_scope_changes.append(path)

    if out_of_scope_changes:
        raise GitAdapterError(
            f"Unrelated working-tree changes detected outside review scope:\n" +
            "\n".join(f"- {p}" for p in out_of_scope_changes)
        )

    # Check for prohibited untracked files in-scope
    prohibited = validate_untracked_files(repo_path, scope)
    if prohibited:
        raise GitAdapterError(
            f"Prohibited untracked files detected within review scope:\n" +
            "\n".join(f"- {p}" for p in prohibited)
        )

def get_current_branch(repo_path: str) -> str:
    """Returns the name of the current checked out branch."""
    try:
        res = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitAdapterError(f"Failed to get current branch: {e.stderr}")

def create_source_checkpoint(
    repo_path: str,
    scope: Dict[str, Any],
    bead_id: str,
    commit_msg: str
) -> str:
    """
    1. Validates working tree cleanliness.
    2. Switches/checks out the review branch `bead/<bead-id>`.
    3. Stages only in-scope changes.
    4. Commits the checkpoint.
    5. Returns the new commit SHA.
    """
    validate_working_tree_cleanliness(repo_path, scope)

    branch_name = f"bead/{bead_id}"
    current_branch = get_current_branch(repo_path)
    
    if current_branch != branch_name:
        # Check if branch exists
        exists_res = subprocess.run(
            ["git", "show-ref", "--verify", f"refs/heads/{branch_name}"],
            cwd=repo_path,
            capture_output=True
        )
        if exists_res.returncode == 0:
            # Checkout existing
            checkout_cmd = ["git", "checkout", branch_name]
        else:
            # Create new
            checkout_cmd = ["git", "checkout", "-b", branch_name]
            
        try:
            subprocess.run(checkout_cmd, cwd=repo_path, capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            raise GitAdapterError(f"Failed to checkout branch {branch_name}: {e.stderr}")

    # Stage files that are in scope and dirty
    status_files = get_git_status_files(repo_path)
    staged_any = False
    
    for status, path in status_files:
        if is_path_in_scope(path, scope):
            # Run git add on path (works for modification, addition, deletion, untracked)
            try:
                subprocess.run(["git", "add", path], cwd=repo_path, capture_output=True, check=True)
                staged_any = True
            except subprocess.CalledProcessError as e:
                raise GitAdapterError(f"Failed to stage file {path}: {e.stderr}")

    if not staged_any:
        # No changes to commit, return current HEAD SHA
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return res.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise GitAdapterError(f"Failed to get current HEAD SHA: {e.stderr}")

    # Commit
    try:
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=repo_path,
            capture_output=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        raise GitAdapterError(f"Failed to commit checkpoint: {e.stderr}")

    # Get new commit SHA
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitAdapterError(f"Failed to parse new HEAD: {e.stderr}")

def push_review_ref(repo_path: str, remote_name: str, bead_id: str) -> None:
    """Pushes the review branch to the remote. Never uses force push."""
    branch_name = f"bead/{bead_id}"
    try:
        subprocess.run(
            ["git", "push", remote_name, branch_name],
            cwd=repo_path,
            capture_output=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        raise GitAdapterError(f"Failed to push branch {branch_name} to {remote_name}: {e.stderr}")

def fetch_review_ref(repo_path: str, remote_name: str, bead_id: str) -> str:
    """Fetches the review branch from remote and returns its SHA."""
    branch_name = f"bead/{bead_id}"
    try:
        # First fetch the branch
        subprocess.run(
            ["git", "fetch", remote_name, f"{branch_name}:{branch_name}"],
            cwd=repo_path,
            capture_output=True
        )
        # Parse fetched SHA
        res = subprocess.run(
            ["git", "rev-parse", f"refs/heads/{branch_name}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitAdapterError(f"Failed to fetch review ref {branch_name} from {remote_name}: {e.stderr}")

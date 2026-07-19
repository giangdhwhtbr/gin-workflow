import subprocess
import os
import hashlib
from typing import Dict, Any, List, Optional
from review_ledger import jcs

def get_git_files(repo_path: str) -> List[Dict[str, str]]:
    """
    Runs `git ls-files --stage` to retrieve all tracked Git files
    with their modes, object SHAs, and paths.
    """
    try:
        res = subprocess.run(
            ["git", "ls-files", "--stage"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to execute git ls-files: {e.stderr}")

    files = []
    for line in res.stdout.splitlines():
        if not line.strip():
            continue
        # Format: <mode> <sha> <stage>\t<path>
        metadata, path = line.split("\t", 1)
        mode, sha, stage = metadata.split(" ")
        
        # Determine object type from git mode
        # 160000 = gitlink (submodule commit), others are blobs
        obj_type = "commit" if mode == "160000" else "blob"
        
        files.append({
            "mode": mode,
            "sha": sha,
            "path": path,
            "type": obj_type
        })
    return files

def is_path_in_scope(path: str, scope: Dict[str, Any]) -> bool:
    """Checks if a relative path falls within the included and not excluded scope."""
    included = scope.get("included_paths", [])
    excluded = scope.get("excluded_artifact_paths", [])

    in_included = False
    if not included:
        in_included = True
    else:
        for p in included:
            p_clean = p.rstrip('/')
            if path == p or path.startswith(p_clean + '/'):
                in_included = True
                break

    if not in_included:
        return False

    for p in excluded:
        p_clean = p.rstrip('/')
        if path == p or path.startswith(p_clean + '/'):
            return False

    return True

def compute_source_tree_hash(repo_id: str, repo_path: str, scope: Dict[str, Any]) -> str:
    """
    Computes a deterministic source tree hash for the repository matching the scope,
    as specified in spec §7.4.
    """
    files = get_git_files(repo_path)
    
    encoded_lines = []
    for f in files:
        path = f["path"]
        if is_path_in_scope(path, scope):
            # Format: repo_id + NUL + path + NUL + mode + NUL + type + NUL + sha
            line_str = f"{repo_id}\0{path}\0{f['mode']}\0{f['type']}\0{f['sha']}"
            encoded_lines.append(line_str.encode("utf-8"))

    # Cryptographically hash the sorted list of file records
    encoded_lines.sort()
    hasher = hashlib.sha256()
    for line in encoded_lines:
        hasher.update(line)
    return hasher.hexdigest()

def compute_source_scope_hash(scope: Dict[str, Any]) -> str:
    """Computes a deterministic hash of the scope configuration using JCS canonicalization."""
    canonical_scope = jcs.serialize(scope)
    return hashlib.sha256(canonical_scope.encode("utf-8")).hexdigest()

def validate_untracked_files(repo_path: str, scope: Dict[str, Any]) -> List[str]:
    """
    Finds untracked files inside the repository scope and returns a list of any 
    untracked files that are not allowed by 'allowed_generated_paths'.
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
        raise RuntimeError(f"Failed to execute git status: {e.stderr}")

    allowed_gen = scope.get("allowed_generated_paths", [])
    prohibited = []

    for line in res.stdout.splitlines():
        if line.startswith("?? "):
            path = line[3:].strip()
            # If path is in scope, verify if it matches allowed generated paths
            if is_path_in_scope(path, scope):
                allowed = False
                for gen_p in allowed_gen:
                    gen_clean = gen_p.rstrip('/')
                    if path == gen_p or path.startswith(gen_clean + '/'):
                        allowed = True
                        break
                if not allowed:
                    prohibited.append(path)

    return prohibited

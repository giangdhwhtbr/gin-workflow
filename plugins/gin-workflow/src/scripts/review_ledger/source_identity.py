"""Canonical source-scope and Git object identity helpers."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any, Dict, List, Mapping

from review_ledger import jcs


def _git(repo_path: str, *args: str, env: Mapping[str, str] | None = None) -> bytes:
    process = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        env=None if env is None else dict(env),
        capture_output=True,
        check=False,
    )
    if process.returncode:
        message = process.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {message}")
    return process.stdout


def canonical_scope_path(path: str) -> str:
    value = str(path).replace("\\", "/").strip()
    while value.endswith("/"):
        value = value[:-1]
    parsed = PurePosixPath(value)
    if not value or value == "." or parsed.is_absolute() or re.match(r"^[A-Za-z]:/", value) or ".." in parsed.parts:
        raise ValueError(f"scope path must be repository-relative: {path!r}")
    return parsed.as_posix()


def canonicalize_scope(scope: Mapping[str, Any]) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    for key in (
        "included_paths",
        "excluded_artifact_paths",
        "allowed_generated_paths",
        "nested_repository_paths",
    ):
        result[key] = sorted({canonical_scope_path(item) for item in scope.get(key, [])})
    return result


def _matches(path: str, roots: List[str]) -> bool:
    normalized = canonical_scope_path(path)
    return any(normalized == root or normalized.startswith(root + "/") for root in roots)


def is_included_path(path: str, scope: Mapping[str, Any]) -> bool:
    included = canonicalize_scope(scope)["included_paths"]
    return not included or _matches(path, included)


def is_excluded_path(path: str, scope: Mapping[str, Any]) -> bool:
    return _matches(path, canonicalize_scope(scope)["excluded_artifact_paths"])


def is_generated_path(path: str, scope: Mapping[str, Any]) -> bool:
    return _matches(path, canonicalize_scope(scope)["allowed_generated_paths"])


def get_nested_repository_paths(scope: Mapping[str, Any]) -> List[str]:
    return canonicalize_scope(scope)["nested_repository_paths"]


def is_path_in_scope(path: str, scope: Mapping[str, Any]) -> bool:
    canonical = canonical_scope_path(path)
    return (
        is_included_path(canonical, scope)
        and not is_excluded_path(canonical, scope)
        and not is_generated_path(canonical, scope)
        and not _matches(canonical, get_nested_repository_paths(scope))
    )


def _parse_index_records(raw: bytes) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        metadata, path_bytes = entry.split(b"\t", 1)
        mode, sha, stage = metadata.decode("ascii").split()
        path = path_bytes.decode("utf-8", "surrogateescape")
        records.append(
            {
                "mode": mode,
                "sha": sha,
                "stage": stage,
                "path": path,
                "type": "commit" if mode == "160000" else "blob",
            }
        )
    return records


def get_git_files(repo_path: str, *, index_file: str | None = None) -> List[Dict[str, str]]:
    env = os.environ.copy()
    if index_file is not None:
        env["GIT_INDEX_FILE"] = index_file
    return _parse_index_records(_git(repo_path, "ls-files", "--stage", "-z", env=env))


def get_tree_files(repo_path: str, treeish: str) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    for entry in _git(repo_path, "ls-tree", "-r", "-z", treeish).split(b"\0"):
        if not entry:
            continue
        metadata, path_bytes = entry.split(b"\t", 1)
        mode, obj_type, sha = metadata.decode("ascii").split()
        records.append(
            {
                "mode": mode,
                "sha": sha,
                "stage": "0",
                "path": path_bytes.decode("utf-8", "surrogateescape"),
                "type": obj_type,
            }
        )
    return records


def _hash_records(repo_id: str, files: List[Dict[str, str]], scope: Mapping[str, Any]) -> str:
    encoded = []
    for item in files:
        if is_path_in_scope(item["path"], scope):
            encoded.append(
                f"{repo_id}\0{item['path']}\0{item['mode']}\0{item['type']}\0{item['sha']}".encode(
                    "utf-8", "surrogateescape"
                )
            )
    digest = hashlib.sha256()
    for line in sorted(encoded):
        digest.update(line)
    return digest.hexdigest()


def compute_source_tree_hash(repo_id: str, repo_path: str, scope: Mapping[str, Any]) -> str:
    return _hash_records(repo_id, get_git_files(repo_path), scope)


def compute_tree_hash_for_commit(
    repo_id: str, repo_path: str, scope: Mapping[str, Any], treeish: str
) -> str:
    return _hash_records(repo_id, get_tree_files(repo_path, treeish), scope)


def compute_source_scope_hash(scope: Mapping[str, Any]) -> str:
    canonical = canonicalize_scope(scope)
    return hashlib.sha256(jcs.serialize(canonical).encode("utf-8")).hexdigest()


def _status_paths(repo_path: str) -> List[str]:
    raw = _git(
        repo_path,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--ignore-submodules=none",
    )
    fields = raw.split(b"\0")
    paths: List[str] = []
    index = 0
    while index < len(fields):
        field = fields[index]
        index += 1
        if not field:
            continue
        status = field[:2].decode("ascii", "replace")
        path = field[3:].decode("utf-8", "surrogateescape")
        paths.append(path)
        if "R" in status or "C" in status:
            index += 1
    return paths


def validate_untracked_files(repo_path: str, scope: Mapping[str, Any]) -> List[str]:
    """Return only untracked paths that are neither source nor declared artifacts.

    Ordinary in-scope source additions are valid checkpoint inputs. Generated and
    excluded artifact paths are intentionally ignored.
    """
    raw = _git(repo_path, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    prohibited: List[str] = []
    for field in raw.split(b"\0"):
        if not field or field[:2] != b"??":
            continue
        path = field[3:].decode("utf-8", "surrogateescape")
        if (
            not is_path_in_scope(path, scope)
            and not is_generated_path(path, scope)
            and not is_excluded_path(path, scope)
            and not path.startswith(".planning/")
        ):
            prohibited.append(path)
    return sorted(prohibited)


def find_nested_repositories(repo_path: str, scope: Mapping[str, Any]) -> List[str]:
    root = Path(repo_path).resolve()
    found: List[str] = []
    for current, directories, _files in os.walk(root):
        current_path = Path(current)
        if current_path == root:
            if ".git" in directories:
                directories.remove(".git")
        elif ".git" in directories or (current_path / ".git").is_file():
            relative = current_path.relative_to(root).as_posix()
            if is_included_path(relative, scope):
                found.append(relative)
            directories[:] = []
            continue
        directories[:] = [
            item
            for item in directories
            if item not in {".git", "__pycache__"}
            and not is_excluded_path((current_path / item).relative_to(root).as_posix(), scope)
            and not is_generated_path((current_path / item).relative_to(root).as_posix(), scope)
        ]
    return sorted(found)

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Optional


PROTECTED_PLANNING_DIRS = frozenset({
    "plans",
    "specs",
    "codebase",
    "knowledge",
    "worktrees",
    "reviews",
    "research",
    "archive",
    "logs",
    "tasks",
    "templates",
    "temp",
    "cache",
})

_BEAD_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")
_REVIEW_REF_PREFIX = "refs/gin/review/"


def _find_bd_executable() -> Optional[str]:
    candidate = shutil.which("bd")
    if candidate:
        return candidate
    common_paths = [
        "/home/linuxbrew/.linuxbrew/bin/bd",
        "/usr/local/bin/bd",
        str(Path.home() / ".cargo" / "bin" / "bd"),
    ]
    for p in common_paths:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def _load_issues_cache(repo_root: Path) -> dict[str, str]:
    cache: dict[str, str] = {}
    issues_file = repo_root / ".beads" / "issues.jsonl"
    if issues_file.is_file():
        try:
            for line in issues_file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                item = json.loads(line)
                task_id = item.get("id") or item.get("task_id")
                status = item.get("status")
                if task_id and status:
                    cache[str(task_id)] = str(status)
        except Exception:
            pass
    return cache


def _query_beads_status(
    bead_id: str,
    repo_root: Path,
    issues_cache: Optional[dict[str, str]] = None,
) -> tuple[Optional[str], str]:
    bd_bin = _find_bd_executable()
    if bd_bin:
        try:
            res = subprocess.run(
                [bd_bin, "show", bead_id, "--json"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                if isinstance(data, list) and len(data) == 1:
                    data = data[0]
                if isinstance(data, dict) and "issue" in data and isinstance(data["issue"], dict):
                    data = data["issue"]
                if isinstance(data, dict) and "status" in data:
                    status = str(data["status"])
                    return status, f"bead status is {status}"
        except Exception:
            pass

    # Fallback to issues_cache or reading .beads/issues.jsonl
    if issues_cache is not None:
        if bead_id in issues_cache:
            status = issues_cache[bead_id]
            return status, f"bead status is {status}"
    else:
        issues_file = repo_root / ".beads" / "issues.jsonl"
        if issues_file.is_file():
            try:
                for line in issues_file.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    if item.get("id") == bead_id or item.get("task_id") == bead_id:
                        status = item.get("status")
                        if status:
                            return str(status), f"bead status is {status}"
            except Exception:
                pass

    return None, "bead not found in beads task tracking"


def _is_commit_merged_to_base(sha: str, repo_root: Path) -> bool:
    for base_ref in ("master", "main", "HEAD"):
        res = subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, base_ref],
            cwd=repo_root,
            capture_output=True,
        )
        if res.returncode == 0:
            return True
    return False


def _is_review_dir(path: Path) -> bool:
    return path.is_dir() and (
        (path / "review.json").exists() or (path / ".review.lock").exists()
    )


def is_bead_closed(
    bead_id: str,
    repo_root: Path,
    dir_path: Optional[Path] = None,
    issues_cache: Optional[dict[str, str]] = None,
) -> tuple[bool, str]:
    """Determine if a bead is eligible for review ledger cleanup."""
    status, reason = _query_beads_status(bead_id, repo_root, issues_cache=issues_cache)
    if status is not None:
        if status.lower() in ("closed", "deferred", "cancelled", "superseded"):
            return True, reason
        return False, reason

    # Fallback: check review ledger state and git merge status
    if dir_path is None:
        scoped = repo_root / ".planning" / "reviews" / bead_id
        legacy = repo_root / ".planning" / bead_id
        dir_path = scoped if scoped.exists() else legacy

    review_json = dir_path / "review.json"
    if review_json.is_file():
        try:
            data = json.loads(review_json.read_text(encoding="utf-8"))
            review_state = data.get("review_state")
            if review_state == "review-approved":
                repos = data.get("repositories", [])
                if not repos:
                    return False, "review ledger has no repositories declared"
                all_merged = True
                for repo in repos:
                    sha = repo.get("checkpoint_sha") or repo.get("reviewed_source_sha")
                    ref = repo.get("checkpoint_ref") or repo.get("review_ref")
                    repo_merged = False
                    if sha and _is_commit_merged_to_base(sha, repo_root):
                        repo_merged = True
                    elif ref:
                        res = subprocess.run(
                            ["git", "rev-parse", "--verify", ref],
                            cwd=repo_root,
                            capture_output=True,
                            text=True,
                        )
                        if res.returncode == 0:
                            ref_sha = res.stdout.strip()
                            if _is_commit_merged_to_base(ref_sha, repo_root):
                                repo_merged = True
                    if not repo_merged:
                        all_merged = False
                        break
                if all_merged:
                    return True, "review is approved and all checkpoints are merged into base branch"
        except Exception:
            pass

    return False, "bead is not closed in task tracking and not merged in git"


def _existing_review_refs(repo_root: Path) -> set[str]:
    res = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname)", _REVIEW_REF_PREFIX],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    return set(res.stdout.split()) if res.returncode == 0 else set()


def _ledger_refs(bead_id: str, dir_path: Optional[Path], existing: set[str]) -> list[str]:
    """The checkpoint refs a ledger created: its default ref plus any its review.json names."""
    refs = {f"{_REVIEW_REF_PREFIX}{bead_id}"}
    if dir_path is not None:
        try:
            data = json.loads((dir_path / "review.json").read_text(encoding="utf-8"))
            for repo in data.get("repositories", []):
                for key in ("checkpoint_ref", "review_ref"):
                    ref = repo.get(key)
                    if isinstance(ref, str) and ref.startswith(_REVIEW_REF_PREFIX):
                        refs.add(ref)
        except (OSError, ValueError, AttributeError):
            pass
    return sorted(refs & existing)


def cleanup_review_ledgers(
    repo_root: Path,
    *,
    bead_id: Optional[str] = None,
    all_closed: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Safely cleans up stale review ledgers for closed or merged beads."""
    if not bead_id and not all_closed:
        raise ValueError("Either bead_id or all_closed must be specified.")
    if bead_id and all_closed:
        raise ValueError("--bead-id and --all-closed are mutually exclusive.")

    candidates: list[tuple[str, Optional[Path]]] = []
    existing_refs = _existing_review_refs(repo_root)

    if bead_id:
        if not _BEAD_ID_PATTERN.match(bead_id) or bead_id in (".", ".."):
            raise ValueError(f"Invalid bead_id: '{bead_id}'. Must be a valid identifier without path traversal.")
        if bead_id in PROTECTED_PLANNING_DIRS:
            return {
                "cleaned": [],
                "skipped": [{"bead_id": bead_id, "path": "", "reason": f"'{bead_id}' is a protected directory"}],
                "dry_run": dry_run,
            }

        scoped = repo_root / ".planning" / "reviews" / bead_id
        legacy = repo_root / ".planning" / bead_id
        if _is_review_dir(scoped):
            candidates.append((bead_id, scoped))
        if _is_review_dir(legacy) and bead_id not in PROTECTED_PLANNING_DIRS:
            candidates.append((bead_id, legacy))
        if not candidates and f"{_REVIEW_REF_PREFIX}{bead_id}" in existing_refs:
            candidates.append((bead_id, None))
        if not candidates:
            return {
                "cleaned": [],
                "skipped": [{"bead_id": bead_id, "path": "", "reason": "No review directory found"}],
                "dry_run": dry_run,
            }
    else:
        issues_cache = _load_issues_cache(repo_root)

        reviews_dir = repo_root / ".planning" / "reviews"
        if reviews_dir.is_dir():
            for child in sorted(reviews_dir.iterdir()):
                if _is_review_dir(child) and not child.name.startswith("."):
                    candidates.append((child.name, child))

        planning_dir = repo_root / ".planning"
        if planning_dir.is_dir():
            for child in sorted(planning_dir.iterdir()):
                if (
                    _is_review_dir(child)
                    and not child.name.startswith(".")
                    and child.name not in PROTECTED_PLANNING_DIRS
                ):
                    candidates.append((child.name, child))

        # Refs whose ledger directory is already gone.
        with_ledger = {b_id for b_id, _ in candidates}
        for ref in sorted(existing_refs):
            b_id = ref[len(_REVIEW_REF_PREFIX):]
            if b_id not in with_ledger and _BEAD_ID_PATTERN.match(b_id):
                candidates.append((b_id, None))

    cleaned: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    issues_cache_ref = issues_cache if not bead_id else None

    for b_id, dir_path in candidates:
        eligible, reason = is_bead_closed(b_id, repo_root, dir_path, issues_cache=issues_cache_ref)
        path = str(dir_path) if dir_path is not None else ""
        if eligible:
            # Several directories of one bead share its refs; the first one deletes them.
            refs = _ledger_refs(b_id, dir_path, existing_refs)
            if not dry_run:
                if dir_path is not None:
                    shutil.rmtree(dir_path)
                for ref in refs:
                    subprocess.run(["git", "update-ref", "-d", ref], cwd=repo_root, check=True, capture_output=True)
            existing_refs.difference_update(refs)
            cleaned.append({
                "bead_id": b_id,
                "path": path,
                "reason": reason,
                "refs": refs,
            })
        else:
            skipped.append({
                "bead_id": b_id,
                "path": path,
                "reason": reason,
            })

    return {
        "cleaned": cleaned,
        "skipped": skipped,
        "dry_run": dry_run,
    }

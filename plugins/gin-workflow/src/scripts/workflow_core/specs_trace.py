"""Requirement traceability (REQ -> tests) and spec-review PR status."""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any, Callable, Iterable, Mapping

from .checkout import main_checkout
from .specs import REQ_ID, SpecsError, change_file, delta_blocks, retired_blocks, test_files
from .workspace import Repo, Workspace, load


def _tracked(root: Path) -> list[str]:
    listed = subprocess.run(["git", "ls-files"], cwd=root, text=True, capture_output=True, check=False)
    if listed.returncode == 0:
        return listed.stdout.splitlines()
    return [path.relative_to(root).as_posix() for path in Path(root).rglob("*") if path.is_file()]


def _child_tracked(checkout: Path) -> list[str] | None:
    listed = subprocess.run(["git", "ls-files"], cwd=checkout, text=True, capture_output=True, check=False)
    return listed.stdout.splitlines() if listed.returncode == 0 else None


def _ref_tracked(checkout: Path, ref: str) -> list[str] | None:
    listed = subprocess.run(["git", "ls-tree", "-r", "--name-only", ref], cwd=checkout, text=True,
                            capture_output=True, check=False)
    return listed.stdout.splitlines() if listed.returncode == 0 else None


def _from_disk(path: Path) -> Callable[[], str]:
    return lambda: path.read_text(encoding="utf-8")


def _from_ref(checkout: Path, ref: str, path: str) -> Callable[[], str]:
    def read() -> str:
        done = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=checkout, capture_output=True, check=False)
        if done.returncode != 0:
            raise OSError(path)
        return done.stdout.decode("utf-8")
    return read


def _child_checkout(space: Workspace, repo: Repo) -> Path | None:
    """The child's clone under the gin root, else, from a linked worktree of the parent, under its main checkout."""
    if space.present(repo):
        return space.checkout(repo)
    main = main_checkout(space.root)
    other = main / repo.path
    return other if main != space.root and (other / ".git").exists() else None


def _tests_md_rows(path: Path) -> list[tuple[str, set[str], str]]:
    rows = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and line.lstrip().startswith("|"):
            ids = {match.group(0) for match in REQ_ID.finditer(cells[1])}
            if ids:
                rows.append((cells[0], ids, cells[3]))
    return rows


def req_sources(root: Path, cfg: Mapping[str, Any], req_ids: Iterable[str],
                refs: Mapping[str, str] | None = None) -> tuple[dict[str, list[str]], list[str]]:
    """Test files citing each REQ-ID (sorted repository paths), and the workspace children that could not be listed.

    `refs` maps a child path to a git ref whose files are read instead of its checkout."""
    wanted = set(req_ids)
    refs = refs or {}
    sources: dict[str, list[str]] = {req: [] for req in wanted}
    candidates = [(relative, _from_disk(Path(root) / relative)) for relative in test_files(root, cfg, _tracked(root))]
    skipped: list[str] = []
    space = load(root)
    repos = [repo for repo in (space.repos if space else []) if repo.workable]
    for name in refs:
        if name not in {repo.path for repo in repos}:
            raise SpecsError(f"--ref {name}={refs[name]}: {name} is not a workable workspace repository")
    for repo in repos:
        checkout = _child_checkout(space, repo)
        ref = refs.get(repo.path)
        if ref is not None and checkout is None:
            raise SpecsError(f"--ref {repo.path}={ref}: {repo.path} is not cloned; run gin workspace clone {repo.path}")
        if ref is not None:
            tracked = _ref_tracked(checkout, ref)
            if tracked is None:
                raise SpecsError(f"--ref {repo.path}={ref}: cannot resolve {ref} in {repo.path}")
        else:
            tracked = _child_tracked(checkout) if checkout is not None else None
        if tracked is None:
            skipped.append(repo.path)
            continue
        for path in test_files(root, cfg, tracked):
            reader = _from_ref(checkout, ref, path) if ref is not None else _from_disk(checkout / path)
            candidates.append((f"{repo.path}/{path}", reader))
    for relative, read in candidates:
        try:
            text = read()
        except (OSError, UnicodeDecodeError):
            continue
        for req in {match.group(0) for match in REQ_ID.finditer(text)} & wanted:
            sources[req].append(relative)
    return {req: sorted(paths) for req, paths in sources.items()}, skipped


def trace(root: Path, cfg: Mapping[str, Any], change: Path, refs: Mapping[str, str] | None = None) -> dict[str, Any]:
    blocks, errors = delta_blocks(root, change)
    if errors:
        raise SpecsError("; ".join(errors))
    wanted = [block.id for block in blocks if block.section in ("ADDED", "MODIFIED")]
    gone = sorted((set(retired_blocks(root, cfg)) | {block.id for block in blocks
                                                     if block.section in ("REMOVED", "RETIRED")}) - set(wanted))
    sources, skipped = req_sources(root, cfg, wanted + gone, refs)
    tests_md = change_file(change, "tests")
    for case, ids, evidence in _tests_md_rows(tests_md):
        if evidence and evidence != "-":
            for req in ids & set(wanted):
                sources[req].append(f"{tests_md.relative_to(root).as_posix()}#{case}")
    requirements = [{"id": req, "status": "covered" if sources[req] else "missing", "sources": sorted(sources[req])}
                    for req in wanted]
    return {"change": change.name, "requirements": requirements,
            "missing": [row["id"] for row in requirements if row["status"] == "missing"],
            "retired": [{"id": req, "sources": sorted(sources[req])} for req in gone if sources[req]],
            "skipped": skipped}


def status(root: Path, change: Path) -> dict[str, Any]:
    """The newest spec-review PR of `spec/<change>` on the configured host (GitHub without team mode)."""
    from .hosts import adapter
    from .team import TeamConfig, team_for_repo
    from .team_host import HostCliMissing, HostUnavailable, pr_for_branch

    branch = f"spec/{change.name}"
    record = "gin record requirement-confirmed --workflow-id <epic> --evidence <pr-url> --actor <id>"
    host = (team_for_repo(root) or TeamConfig()).host
    try:
        pr = pr_for_branch(host, branch, root)
    except HostCliMissing:
        name = adapter(host).executable
        return {"change": change.name, "branch": branch, "status": f"{name}_unavailable",
                "message": f"{name} unavailable; check the PR for {branch} by hand, then: {record}"}
    except HostUnavailable as error:
        raise SpecsError(str(error)) from error
    if pr is None:
        return {"change": change.name, "branch": branch, "status": "none"}
    payload = {"change": change.name, "branch": branch, "status": pr.state, "url": pr.url}
    if pr.state == "merged":
        payload["merge_commit"] = pr.merge_commit
    return payload

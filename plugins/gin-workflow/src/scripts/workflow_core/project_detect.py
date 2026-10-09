"""Deterministic, read-only project detection for setup (no LLM, no writes)."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Callable

from .executable_resolver import PROVIDER_EXE_ALIASES

FRONTEND_JS = {"react", "vue", "svelte", "next", "nuxt", "@angular/core", "solid-js", "preact", "astro"}
BACKEND_JS = {"express", "@nestjs/core", "fastify", "koa", "hono"}
BACKEND_PY = {"fastapi", "django", "flask"}
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".go", ".rs", ".java", ".rb"}
SKIP_DIRS = {".git", "node_modules", ".agent-workflow", ".planning", ".venv", "dist", "build"}
NPM_DEFAULT_TEST = "no test specified"
EXEC_PREFIX = {"npm": "npx", "pnpm": "pnpm exec", "yarn": "yarn", "bun": "bunx"}
RUN_PREFIX = {"uv": "uv run ", "poetry": "poetry run ", "pip": ""}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _js_pm(root: Path) -> str:
    for lock, pm in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"), ("bun.lock", "bun")):
        if (root / lock).exists():
            return pm
    return "npm"


def _py_pm(root: Path) -> str:
    return "uv" if (root / "uv.lock").exists() else "poetry" if (root / "poetry.lock").exists() else "pip"


def _empty_commands() -> dict[str, str]:
    return {"lint": "", "typecheck": "", "test": "", "build": "", "e2e": ""}


def _js_package(directory: Path, pm: str) -> tuple[str | None, dict[str, str], list[str]]:
    manifest = _read_json(directory / "package.json")
    deps = {**manifest.get("dependencies", {}), **manifest.get("devDependencies", {})}
    front, back = bool(FRONTEND_JS & set(deps)), bool(BACKEND_JS & set(deps))
    shape = "fullstack" if front and back else "frontend" if front else "backend" if back else (
        "library" if ("main" in manifest or "exports" in manifest or "bin" in manifest) and not manifest.get("private") else None)
    scripts = manifest.get("scripts", {}) if isinstance(manifest.get("scripts"), dict) else {}
    commands = _empty_commands()
    run = lambda name: f"{pm} run {name}"  # noqa: E731
    if "lint" in scripts:
        commands["lint"] = run("lint")
    typecheck = next((s for s in ("typecheck", "type-check") if s in scripts), None)
    if typecheck:
        commands["typecheck"] = run(typecheck)
    elif (directory / "tsconfig.json").exists() and "typescript" in deps:
        commands["typecheck"] = f"{EXEC_PREFIX[pm]} tsc --noEmit"
    if "test" in scripts and NPM_DEFAULT_TEST not in str(scripts["test"]):
        commands["test"] = run("test")
    if "build" in scripts:
        commands["build"] = run("build")
    e2e = next((s for s in ("test:e2e", "e2e") if s in scripts), None)
    if e2e:
        commands["e2e"] = run(e2e)
    stack = sorted(name for name in deps if name in FRONTEND_JS | BACKEND_JS | {"typescript", "vite"})
    return shape, commands, stack


def _mentions(text: str, name: str) -> bool:
    """`name` as a whole package token: `ruff` matches `[tool.ruff]`, not `trufflehog` or `ruff-lsp`."""
    return re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text) is not None


def _py_package(root: Path, pm: str) -> tuple[str | None, dict[str, str], list[str]]:
    text = ""
    for name in ("pyproject.toml", "requirements.txt"):
        if (root / name).is_file():
            text += (root / name).read_text(encoding="utf-8", errors="replace").lower()
    if not text:
        return None, _empty_commands(), []
    found = sorted(dep for dep in BACKEND_PY if _mentions(text, dep))
    shape = "backend" if found else ("library" if "[project]" in text else None)
    prefix = RUN_PREFIX[pm]
    commands = _empty_commands()
    if _mentions(text, "ruff"):
        commands["lint"] = f"{prefix}ruff check ."
    if _mentions(text, "mypy"):
        commands["typecheck"] = f"{prefix}mypy ."
    if _mentions(text, "pytest"):
        commands["test"] = f"{prefix}pytest"
    return shape, commands, found


def _workspace_globs(root: Path) -> list[str]:
    globs: list[str] = []
    workspace = root / "pnpm-workspace.yaml"
    if workspace.is_file():
        globs += re.findall(r"-\s*['\"]?([^'\"\n]+)['\"]?", workspace.read_text(encoding="utf-8"))
    workspaces = _read_json(root / "package.json").get("workspaces")
    if isinstance(workspaces, dict):
        workspaces = workspaces.get("packages")
    if isinstance(workspaces, list):
        globs += [str(item) for item in workspaces]
    return globs


def _workspace_dirs(root: Path, globs: list[str]) -> list[Path]:
    """Workspace package directories: `!` patterns exclude, dependency/VCS dirs never count."""
    def matches(pattern: str) -> set[Path]:
        try:
            return {path for path in root.glob(pattern.rstrip("/")) if path.is_dir()}
        except ValueError:
            return set()

    included: set[Path] = set()
    excluded: set[Path] = set()
    for pattern in globs:
        if pattern.startswith("!"):
            excluded |= matches(pattern[1:])
        else:
            included |= matches(pattern)
    return sorted(
        path for path in included
        if (path / "package.json").is_file()
        and not any(part in SKIP_DIRS for part in path.relative_to(root).parts)
        and not any(path == ex or ex in path.parents for ex in excluded)
    )


def _combine(shapes: list[str]) -> str:
    kinds = set(shapes)
    if {"frontend", "backend"} <= kinds or "fullstack" in kinds:
        return "fullstack"
    return next(iter(kinds)) if len(kinds) == 1 else "fullstack"


def _source_count(root: Path, limit: int = 5) -> int:
    count = 0
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file() and path.suffix in SOURCE_SUFFIXES:
            count += 1
            if count >= limit:
                break
    return count


def _codegraph(root: Path, which: Callable[[str], str | None]) -> dict[str, bool]:
    index = root / ".codegraph"
    indexed = index.is_dir()
    stale = False
    if indexed:
        newest = max((p.stat().st_mtime for p in index.rglob("*") if p.is_file()), default=0.0)
        try:
            head = subprocess.run(["git", "log", "-1", "--format=%ct"], cwd=root, capture_output=True, text=True,
                                  check=False)
        except OSError:
            head = None
        stale = (head is not None and head.returncode == 0 and head.stdout.strip().isdigit()
                 and newest < int(head.stdout.strip()))
    return {"installed": which("codegraph") is not None, "indexed": indexed, "stale": stale}


def detect_project(root: Path, *, which: Callable[[str], str | None] = shutil.which) -> dict[str, Any]:
    root = Path(root).resolve()
    manifests = [n for n in ("package.json", "pyproject.toml", "requirements.txt", "go.mod", "Cargo.toml") if (root / n).is_file()]
    shape: str | None = None
    commands, stack, pm, packages = _empty_commands(), [], "", []
    if (root / "package.json").is_file():
        pm = _js_pm(root)
        shape, commands, stack = _js_package(root, pm)
    elif (root / "pyproject.toml").is_file() or (root / "requirements.txt").is_file():
        pm = _py_pm(root)
        shape, commands, stack = _py_package(root, pm)
    elif (root / "go.mod").is_file():
        pm, shape, commands = "go", "backend", {**_empty_commands(), "test": "go test ./...", "build": "go build ./..."}
    elif (root / "Cargo.toml").is_file():
        cargo = (root / "Cargo.toml").read_text(encoding="utf-8")
        pm = "cargo"
        shape = "library" if "[lib]" in cargo and not (root / "src/main.rs").exists() else "backend"
        commands = {**_empty_commands(), "lint": "cargo clippy", "test": "cargo test", "build": "cargo build"}
    globs = _workspace_globs(root)
    monorepo = bool(globs) or (root / "turbo.json").is_file() or (root / "nx.json").is_file()
    if monorepo and pm in EXEC_PREFIX:
        for directory in _workspace_dirs(root, globs):
            package_shape, package_commands, _ = _js_package(directory, pm)
            packages.append({"path": directory.relative_to(root).as_posix(),
                             "shape": package_shape or "library",
                             "verify": {"checks": package_commands}})
        if packages:
            shape = _combine([p["shape"] for p in packages])
    stage = "greenfield" if not manifests and _source_count(root) < 5 else "brownfield"
    providers = {provider: which(PROVIDER_EXE_ALIASES.get(provider, (provider,))[0])
                 for provider in ("claude", "codex", "antigravity", "opencode")}
    return {
        "stage": stage,
        "shape": shape or "fullstack",
        "monorepo": monorepo,
        "package_manager": pm,
        "stack": stack,
        "packages": packages,
        "verify_commands": commands,
        "suggested_rigor": "easy" if stage == "greenfield" else "standard",
        "providers": providers,
        "codegraph": _codegraph(root, which),
    }

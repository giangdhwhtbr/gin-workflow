"""Deterministic project detection fixtures."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from workflow_core.project_detect import detect_project


def _repo(files: dict[str, str]) -> Path:
    root = Path(tempfile.mkdtemp())
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _pkg(deps=(), dev=(), scripts=None, **extra) -> str:
    return json.dumps({"dependencies": {d: "1" for d in deps}, "devDependencies": {d: "1" for d in dev},
                       "scripts": scripts or {}, **extra})


NO_TOOLS = lambda name: None  # noqa: E731


class TestDetectProject(unittest.TestCase):
    def test_empty_repo_is_greenfield(self):
        result = detect_project(_repo({"README.md": "# x"}), which=NO_TOOLS)
        self.assertEqual(("greenfield", "easy"), (result["stage"], result["suggested_rigor"]))

    def test_react_vite_is_frontend_with_pnpm_scripts(self):
        root = _repo({"package.json": _pkg(["react", "react-dom"], ["vite", "typescript"],
                                           {"lint": "eslint .", "test": "vitest", "build": "vite build"}),
                      "pnpm-lock.yaml": "", "tsconfig.json": "{}", "src/main.tsx": ""})
        result = detect_project(root, which=NO_TOOLS)
        self.assertEqual(("brownfield", "frontend", "pnpm"), (result["stage"], result["shape"], result["package_manager"]))
        self.assertEqual({"lint": "pnpm run lint", "typecheck": "pnpm exec tsc --noEmit", "test": "pnpm run test",
                          "build": "pnpm run build", "e2e": ""}, result["verify_commands"])

    def test_fastapi_is_backend_with_uv_tools(self):
        root = _repo({"pyproject.toml": '[project]\ndependencies=["fastapi"]\n[tool.ruff]\n[tool.mypy]\n[tool.pytest.ini_options]\n',
                      "uv.lock": "", "app/main.py": ""})
        result = detect_project(root, which=NO_TOOLS)
        self.assertEqual(("backend", "uv"), (result["shape"], result["package_manager"]))
        self.assertEqual("uv run ruff check .", result["verify_commands"]["lint"])
        self.assertEqual("uv run mypy .", result["verify_commands"]["typecheck"])
        self.assertEqual("uv run pytest", result["verify_commands"]["test"])

    def test_next_plus_express_is_fullstack(self):
        root = _repo({"package.json": _pkg(["next", "react", "express"]), "package-lock.json": "{}"})
        self.assertEqual("fullstack", detect_project(root, which=NO_TOOLS)["shape"])

    def test_pnpm_workspace_is_monorepo_with_per_package_shapes(self):
        root = _repo({"package.json": _pkg(), "pnpm-workspace.yaml": "packages:\n  - 'apps/*'\n",
                      "pnpm-lock.yaml": "",
                      "apps/web/package.json": _pkg(["react"], scripts={"test": "vitest"}),
                      "apps/api/package.json": _pkg(["fastify"])})
        result = detect_project(root, which=NO_TOOLS)
        self.assertTrue(result["monorepo"])
        self.assertEqual("fullstack", result["shape"])
        shapes = {p["path"]: p["shape"] for p in result["packages"]}
        self.assertEqual({"apps/api": "backend", "apps/web": "frontend"}, shapes)

    def test_library_and_default_npm_test_script_ignored(self):
        root = _repo({"package.json": _pkg(main="index.js", scripts={"test": 'echo "Error: no test specified" && exit 1'}),
                      "package-lock.json": "{}", "index.js": ""})
        result = detect_project(root, which=NO_TOOLS)
        self.assertEqual("library", result["shape"])
        self.assertEqual("", result["verify_commands"]["test"])

    def test_legacy_is_never_auto_assigned_and_providers_use_agy(self):
        found = {"claude": "/bin/claude", "agy": "/usr/local/bin/agy", "codegraph": "/bin/codegraph"}
        result = detect_project(_repo({"package.json": _pkg(["express"]), "package-lock.json": "{}"}),
                                which=lambda name: found.get(name))
        self.assertNotEqual("legacy", result["stage"])
        self.assertEqual({"claude": True, "codex": False, "antigravity": True},
                         {k: bool(v) for k, v in result["providers"].items()})
        self.assertEqual({"installed": True, "indexed": False, "stale": False}, result["codegraph"])

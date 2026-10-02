"""Pack proposals for setup, read-only tool checks, and CLAUDE.md/AGENTS.md conflict warnings."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins/gin-workflow/src/scripts"))

from workflow_core.rules import load_plugin_packs  # noqa: E402
from workflow_core.rules_checks import (  # noqa: E402
    check_tool, conflict_warnings, propose_packs, rules_doctor, tool_check_report)

PLUGIN = load_plugin_packs(ROOT / "plugins/gin-workflow/src/rules")


def _repo(files: dict[str, str]) -> Path:
    root = Path(tempfile.mkdtemp())
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _pkg(*deps: str) -> str:
    return json.dumps({"dependencies": {d: "1" for d in deps}})


class TestPropose(unittest.TestCase):
    def test_react_vite(self):
        root = _repo({"package.json": json.dumps({"dependencies": {"react": "1"},
                                                  "devDependencies": {"vite": "1", "typescript": "1"}}),
                      "tsconfig.json": "{}"})
        self.assertEqual(["core", "typescript", "react"], propose_packs(root, PLUGIN))

    def test_fastapi(self):
        root = _repo({"pyproject.toml": '[project]\ndependencies=["fastapi"]\n'})
        self.assertEqual(["core", "python", "fastapi"], propose_packs(root, PLUGIN))

    def test_nextjs(self):
        root = _repo({"package.json": _pkg("next", "react")})
        self.assertEqual(["core", "typescript", "nextjs", "react"], propose_packs(root, PLUGIN))

    def test_workspace_packages_count(self):
        root = _repo({"package.json": json.dumps({"workspaces": ["apps/*"]}),
                      "apps/api/package.json": _pkg("express")})
        self.assertIn("node-api", propose_packs(root, PLUGIN))

    def test_greenfield_uses_stack_intent(self):
        root = _repo({"README.md": "# new"})
        self.assertEqual(["core", "python", "fastapi"], propose_packs(root, PLUGIN, stack_intent="FastAPI service"))
        self.assertEqual(["core", "typescript", "nextjs", "react"],
                         propose_packs(root, PLUGIN, stack_intent="Next.js app"))
        self.assertEqual(["core"], propose_packs(root, PLUGIN))


class TestToolChecks(unittest.TestCase):
    def test_tsconfig_strict(self):
        self.assertEqual("missing", check_tool(_repo({}), {"tsconfig_option": {"strict": True}}))
        self.assertEqual("missing", check_tool(_repo({"tsconfig.json": '{"compilerOptions": {}}'}),
                                               {"tsconfig_option": {"strict": True}}))
        jsonc = '{\n  // comment\n  "$schema": "https://x/y",\n  "compilerOptions": {"strict": true,},\n}\n'
        self.assertEqual("present", check_tool(_repo({"tsconfig.json": jsonc}), {"tsconfig_option": {"strict": True}}))
        self.assertEqual("unknown", check_tool(_repo({"tsconfig.json": "{oops"}), {"tsconfig_option": {"strict": True}}))
        self.assertEqual("unknown", check_tool(_repo({"tsconfig.json": '{"extends": "./base.json"}'}),
                                               {"tsconfig_option": {"strict": True}}))

    def test_pyproject_tool(self):
        self.assertEqual("missing", check_tool(_repo({"pyproject.toml": "[project]\n"}), {"pyproject_tool": "tool.ruff"}))
        self.assertEqual("present", check_tool(_repo({"pyproject.toml": "[tool.ruff]\n"}), {"pyproject_tool": "tool.ruff"}))
        self.assertEqual("unknown", check_tool(_repo({"pyproject.toml": "[tool.ruff\n"}), {"pyproject_tool": "tool.ruff"}))

    def test_eslint_rule(self):
        check = {"eslint_rule": "react-hooks/rules-of-hooks"}
        self.assertEqual("missing", check_tool(_repo({}), check))
        self.assertEqual("missing", check_tool(_repo({"eslint.config.js": "export default [];"}), check))
        self.assertEqual("present", check_tool(
            _repo({"eslint.config.js": 'import reactHooks from "eslint-plugin-react-hooks";'}), check))

    def test_file_exists_and_report_shape(self):
        self.assertEqual("present", check_tool(_repo({"a.txt": ""}), {"file_exists": "a.txt"}))
        report = tool_check_report(_repo({}), [PLUGIN["python"]])
        self.assertEqual([("python", "ruff", "missing"), ("python", "mypy", "missing")],
                         [(r["pack"], r["id"], r["status"]) for r in report])
        self.assertTrue(all(r["suggest"] for r in report))


class TestConflictsAndDoctor(unittest.TestCase):
    def test_conflict_keyword_in_claude_md(self):
        root = _repo({"CLAUDE.md": "Components use a Default Export.\n"})
        [warning] = conflict_warnings(root, [PLUGIN["react"]])
        self.assertEqual(("react", "default export", "CLAUDE.md"),
                         (warning["pack"], warning["project_conflict"], warning["file"]))

    def test_rules_doctor_uses_config(self):
        root = _repo({})
        result = rules_doctor(root, {"rules": {"packs": ["python"], "disabled": []}})
        self.assertEqual(["core", "python"], result["packs"])
        self.assertEqual({"ruff", "mypy"}, {r["id"] for r in result["tool_checks"]})
        self.assertEqual([], result["conflicts"])


if __name__ == "__main__":
    unittest.main()

"""Rule pack parsing, selection by file scope, precedence, and budget trimming."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.rules import (  # noqa: E402
    RulesError, build_rules, load_plugin_packs, load_project_rules, parse_pack, select_packs)


def _pack(directory: Path, name: str, front: str, body: str) -> Path:
    path = directory / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{front}\n---\n{body}", encoding="utf-8")
    return path


def _plugin_dir(root: Path) -> Path:
    packs = root / "rules"
    _pack(packs, "core", "id: core\ntier: core\napplies_to: ['**/*']",
          "- [critical] `scope`: Stay in scope.\n- `naming`: Name by domain.\n")
    _pack(packs, "typescript", "id: typescript\ntier: language\napplies_to: ['**/*.ts', '**/*.tsx']",
          "- [high] `no-any`: Avoid any.\n")
    _pack(packs, "python", "id: python\ntier: language\napplies_to: ['**/*.py']",
          "- [high] `typed`: Type public functions.\n")
    _pack(packs, "react", "id: react\ntier: framework\nrequires: [typescript]\napplies_to: ['**/*.tsx']",
          "- [critical] `state-location`: Server state in the data layer.\n\n## Why\n- `state-location`: WHY-TEXT.\n")
    _pack(packs, "nextjs", "id: nextjs\ntier: framework\nrequires: [react]\napplies_to: ['app/**']",
          "- [high] `server-default`: Prefer server components.\n")
    _pack(packs, "fastapi", "id: fastapi\ntier: framework\nrequires: [python]\napplies_to: ['**/*.py']",
          "- [high] `thin-routes`: Keep routes thin.\n")
    (packs / "README.md").write_text("policy, not a pack\n", encoding="utf-8")
    return packs


class TestParse(unittest.TestCase):
    def test_bullets_impacts_and_why_are_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = load_plugin_packs(_plugin_dir(Path(tmp)))["react"]
            self.assertEqual([("state-location", "critical")], [(b.anchor, b.impact) for b in pack.bullets])
            self.assertEqual({"state-location": "WHY-TEXT."}, dict(pack.why))
            self.assertNotIn("WHY", "\n".join(b.line for b in pack.bullets))

    def test_missing_impact_defaults_to_medium_and_readme_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs = load_plugin_packs(_plugin_dir(Path(tmp)))
            self.assertNotIn("README", packs)
            self.assertEqual("medium", packs["core"].bullets[1].impact)

    def test_malformed_packs_are_rejected(self):
        cases = {
            "prose": ("id: x\ntier: core\napplies_to: ['**/*']", "Some prose line.\n"),
            "dup": ("id: x\ntier: core\napplies_to: ['**/*']", "- `a`: one.\n- `a`: two.\n"),
            "impact": ("id: x\ntier: core\napplies_to: ['**/*']", "- [low] `a`: one.\n"),
            "tier": ("id: x\ntier: lib\napplies_to: ['**/*']", "- `a`: one.\n"),
            "applies": ("id: x\ntier: core", "- `a`: one.\n"),
            "why-unknown": ("id: x\ntier: core\napplies_to: ['**/*']", "- `a`: one.\n\n## Why\n- `b`: no.\n"),
            "why-twice": ("id: x\ntier: core\napplies_to: ['**/*']", "- `a`: one.\n\n## Why\n- `a`: 1.\n- `a`: 2.\n"),
        }
        for name, (front, body) in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(RulesError):
                    parse_pack(_pack(Path(tmp), "x", front, body), source="plugin")

    def test_project_rule_needs_only_applies_to(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _pack(repo / ".agent-workflow/rules", "api-style", "applies_to: ['src/**']", "- `codes`: Use codes.\n")
            [rule] = load_project_rules(repo)
            self.assertEqual(("api-style", "project", "project"), (rule.id, rule.tier, rule.source))


class TestSelect(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plugin = load_plugin_packs(_plugin_dir(self.root))

    def tearDown(self):
        self.tmp.cleanup()

    def _ids(self, config, files, project=()):
        packs, _ = select_packs(self.plugin, list(project), config, files)
        return [p.id for p in packs]

    def test_missing_rules_block_means_core_only(self):
        self.assertEqual(["core"], self._ids({}, ["app/page.tsx"]))

    def test_python_scope_never_gets_react(self):
        config = {"rules": {"packs": ["core", "python", "fastapi", "typescript", "react"]}}
        self.assertEqual(["fastapi", "python", "core"], self._ids(config, ["api/main.py"]))

    def test_requires_are_co_loaded_and_ordered_after_dependents(self):
        config = {"rules": {"packs": ["nextjs"]}}
        self.assertEqual(["nextjs", "react", "typescript", "core"], self._ids(config, ["app/page.tsx"]))

    def test_disabled_wins_over_packs_and_requires(self):
        config = {"rules": {"packs": ["react"], "disabled": ["typescript", "core"]}}
        self.assertEqual(["react"], self._ids(config, ["src/a.tsx"]))

    def test_project_rules_come_first(self):
        repo = self.root / "repo"
        _pack(repo / ".agent-workflow/rules", "ui", "applies_to: ['**/*.tsx']", "- `x`: Project rule.\n")
        ids = self._ids({"rules": {"packs": ["react"]}}, ["src/a.tsx"], load_project_rules(repo))
        self.assertEqual(["ui", "react", "typescript", "core"], ids)

    def test_unknown_pack_is_warned_not_fatal(self):
        _, warnings = select_packs(self.plugin, [], {"rules": {"packs": ["vue"]}}, ["a.vue"])
        self.assertEqual(["unknown rule pack 'vue' ignored"], warnings)


class TestBudget(unittest.TestCase):
    def _packs(self, root: Path):
        line = "x" * 120
        _pack(root / "rules", "core", "id: core\ntier: core\napplies_to: ['**/*']",
              "".join(f"- `c-med-{i}`: {line}\n" for i in range(4)) + f"- [critical] `c-crit`: {line}\n")
        _pack(root / "rules", "python", "id: python\ntier: language\napplies_to: ['**/*.py']",
              "".join(f"- [high] `p-high-{i}`: {line}\n" for i in range(4)) + f"- `p-med`: {line}\n")
        plugin = load_plugin_packs(root / "rules")
        _pack(root / "repo/.agent-workflow/rules", "proj", "applies_to: ['**/*.py']", f"- `proj-med`: {line}\n")
        packs, _ = select_packs(plugin, load_project_rules(root / "repo"), {"rules": {"packs": ["python"]}}, ["a.py"])
        return packs

    def test_within_budget_returns_everything(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_rules(self._packs(Path(tmp)))
            self.assertEqual([], result["trimmed"])
            self.assertEqual(result["chars"], len(result["text"]))
            self.assertIn("## proj (project)", result["text"])

    def test_medium_trimmed_first_from_lowest_precedence_project_last(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_rules(self._packs(Path(tmp)), budget=1_000)
            self.assertEqual(["core#c-med-3", "core#c-med-2", "core#c-med-1", "core#c-med-0", "python#p-med"],
                             result["trimmed"][:5])
            self.assertLessEqual(result["chars"], 1_000)
            self.assertIn("c-crit", result["text"])

    def test_high_trimmed_after_all_medium_and_critical_never(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_rules(self._packs(Path(tmp)), budget=100)
            self.assertIn("proj#proj-med", result["trimmed"])
            self.assertIn("python#p-high-0", result["trimmed"])
            self.assertIn("c-crit", result["text"])
            self.assertTrue(any("critical rules exceed budget" in w for w in result["warnings"]))
            self.assertGreater(result["chars"], 100)

    def test_why_never_rendered(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs, _ = select_packs(load_plugin_packs(_plugin_dir(Path(tmp))), [],
                                    {"rules": {"packs": ["react"]}}, ["a.tsx"])
            result = build_rules(packs)
            self.assertNotIn("WHY-TEXT", result["text"])
            self.assertNotIn("WHY-TEXT", json.dumps(result))


class TestCli(unittest.TestCase):
    def _run(self, repo: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPTS / "gin-workflow"), "rules", "--repository", str(repo), *args],
                              cwd=ROOT, env={"PYTHONPATH": str(SCRIPTS), "PATH": "/usr/bin:/bin"},
                              capture_output=True, text=True, check=False)

    def test_files_uses_packaged_packs_and_core_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(Path(tmp), "--files", "src/a.py", "--format", "json")
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(["core"], [p["id"] for p in payload["packs"]])

    def test_list_reports_sizes_and_impact_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(Path(tmp), "--list", "--format", "json")
            self.assertEqual(0, result.returncode, result.stderr)
            [core] = json.loads(result.stdout)["packs"]
            self.assertEqual(("core", "plugin"), (core["id"], core["source"]))
            self.assertEqual({"critical", "high", "medium"}, set(core["impacts"]))

    def test_malformed_project_rule_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _pack(repo / ".agent-workflow/rules", "bad", "applies_to: ['**/*']", "prose\n")
            result = self._run(repo, "--files", "a.py")
            self.assertEqual(2, result.returncode)
            self.assertIn("rules error", result.stderr)


if __name__ == "__main__":
    unittest.main()

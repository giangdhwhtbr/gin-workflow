"""gin-orchestrator packaging: manifests, skill budget and links, marketplace, and the installed script lookup."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.gin_orchestrator import paths

from workflow_core.budget import description_chars  # noqa: E402

ROOT = paths.ROOT
ORCH = ROOT / "plugins/gin-orchestrator"


class TestPackaging(unittest.TestCase):
    def test_manifests_agree(self):
        meta = json.loads((ORCH / "plugin.meta.json").read_text())
        for relative in ("src/.claude-plugin/plugin.json", "src/.codex-plugin/plugin.json"):
            manifest = json.loads((ORCH / relative).read_text())
            with self.subTest(manifest=relative):
                for key in ("name", "version", "description", "author", "repository"):
                    self.assertEqual(meta[key], manifest[key])
        self.assertEqual("gin-orchestrator", meta["name"])
        self.assertEqual("0.0.0", meta["version"])
        self.assertEqual("./skills/", json.loads((ORCH / "src/.codex-plugin/plugin.json").read_text())["skills"])
        self.assertNotIn("hooks", json.loads((ORCH / "src/.codex-plugin/plugin.json").read_text()))

    def test_marketplace_lists_three_plugins(self):
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual({"gin-workflow": "plugins/gin-workflow/src", "gin-qa": "plugins/gin-qa/src",
                          "gin-orchestrator": "plugins/gin-orchestrator/src"},
                         {p["name"]: p["source"]["path"] for p in marketplace["plugins"]})

    def test_skill_budget_and_links(self):
        self.assertEqual(["providers"], sorted(p.name for p in (ORCH / "src/skills").iterdir()))
        self.assertLessEqual(description_chars(ORCH / "src"), 1_000)
        skill = ORCH / "src/skills/providers/SKILL.md"
        text = skill.read_text(encoding="utf-8")
        self.assertLessEqual(len(text), 6_000)
        for link in re.findall(r"\]\(([^)]+)\)", text):
            with self.subTest(link=link):
                self.assertTrue((skill.parent / link).resolve().is_file())

    def test_find_script_resolves_beside_the_installed_package(self):
        """The installer copies the shell scripts next to the package; `find_script` must find them there."""
        with tempfile.TemporaryDirectory() as directory:
            install = Path(directory) / ".local/lib/gin-orchestrator/0.1"
            shutil.copytree(paths.ORCH_SCRIPTS / "gin_orchestrator", install / "gin_orchestrator",
                            ignore=shutil.ignore_patterns("__pycache__"))
            (install / "worktree-create.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            done = subprocess.run(
                [sys.executable, "-c",
                 "from gin_orchestrator.workspace import find_script; print(find_script('worktree-create.sh'))"],
                env={**os.environ, "PYTHONPATH": os.pathsep.join((str(install), str(paths.CORE_SCRIPTS)))},
                capture_output=True, text=True, check=False)

            self.assertEqual(0, done.returncode, done.stderr)
            self.assertEqual(str((install / "worktree-create.sh").resolve()), done.stdout.strip())


if __name__ == "__main__":
    unittest.main()

"""The `gin-orchestrator` launcher: it finds gin-workflow's facade through `gin-workflow paths`."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.gin_orchestrator import paths

LAUNCHER = paths.ORCH_SCRIPTS / "gin-orchestrator"


def run(path: str) -> subprocess.CompletedProcess[str]:
    """Run `version --json` with `path` as PATH and no PYTHONPATH, so only the launcher finds the libraries."""
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    env["PATH"] = path
    return subprocess.run([sys.executable, str(LAUNCHER), "version", "--json"], env=env, capture_output=True,
                          text=True, check=False)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.bin = Path(self.directory.name) / "bin"
        self.bin.mkdir()

    def test_launcher_runs_with_gin_workflow_on_path(self):
        (self.bin / "gin-workflow").symlink_to(paths.CORE_SCRIPTS / "gin-workflow")

        result = run(f"{self.bin}{os.pathsep}{os.environ['PATH']}")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, json.loads(result.stdout)["contract"])

    def test_launcher_without_gin_workflow_exits_1(self):
        result = run(str(self.bin))

        self.assertEqual(1, result.returncode)
        self.assertEqual("error: gin-workflow is not on PATH; install it with ./install.sh --plugin gin-orchestrator\n",
                         result.stderr)

    def test_launcher_rejects_an_unsupported_ext_version(self):
        lib = Path(self.directory.name) / "lib"
        (lib / "workflow_core").mkdir(parents=True)
        (lib / "workflow_core/__init__.py").write_text("", encoding="utf-8")
        (lib / "workflow_core/ext.py").write_text("EXT_VERSION = 99\n", encoding="utf-8")
        fake = self.bin / "gin-workflow"
        fake.write_text(f"#!/bin/sh\necho '{json.dumps({'lib_dir': str(lib)})}'\n", encoding="utf-8")
        fake.chmod(0o755)

        result = run(f"{self.bin}{os.pathsep}{os.environ['PATH']}")

        self.assertEqual(1, result.returncode)
        self.assertEqual("error: gin-workflow facade EXT_VERSION 99; this gin-orchestrator supports 1\n", result.stderr)


if __name__ == "__main__":
    unittest.main()

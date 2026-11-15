""".ginrc pins the version a project needs; gin refuses when incompatible; gin version (gin-workflow-b7ip)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "plugins/gin-workflow/src/scripts/gin"
sys.path.insert(0, str(ROOT / "plugins/gin-workflow/src/scripts"))

from workflow_core import version_pin  # noqa: E402
from workflow_core.cli import CLI_VERSION  # noqa: E402
from tests.workflow_core.orchestrator_fakes import fake_orchestrator  # noqa: E402
from tests.workflow_core.test_workspace import git, init_repo  # noqa: E402

MAJOR, MINOR, PATCH = (int(part) for part in CLI_VERSION.split("."))
HIGHER = f"{MAJOR}.{MINOR}.{PATCH + 1}"
LOWER = f"{MAJOR}.0.0"
OLDER_MAJOR = f"{MAJOR - 1}.9.9"
HOOK_TAIL = "Tell the user before any other work."
ROWS = {  # .ginrc content -> exit code of gin state
    None: 0,
    CLI_VERSION: 0,
    LOWER: 0,
    HIGHER: 2,
    OLDER_MAJOR: 2,
    "3.1": 2,
}


def run(cwd: Path, *argv: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(LAUNCHER), *argv], cwd=cwd, text=True, capture_output=True,
                          check=False, env=env)


def pin(root: Path, content: str | None) -> None:
    path = root / ".ginrc"
    if content is None:
        path.unlink(missing_ok=True)
    else:
        path.write_text(content + "\n", encoding="utf-8")


class ParseTests(unittest.TestCase):
    def test_parse_accepts_one_ascii_version_with_surrounding_whitespace(self):
        self.assertEqual((3, 1, 0), version_pin.parse("3.1.0\n"))
        self.assertEqual((10, 20, 30), version_pin.parse("  10.20.30  "))

    def test_parse_rejects_anything_else(self):
        for text in ("3.1", "3.1.0.1", "v3.1.0", "3.1.0 beta", "3.1.0\nx", "", "3.1.x",
                     "٣.١.٠", "３.１.０"):
            with self.subTest(text=text), self.assertRaises(version_pin.PinError):
                version_pin.parse(text)
        self.assertTrue(issubclass(version_pin.PinError, ValueError))


class RefusalTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name).resolve()
        self.root = init_repo(self.base / "project")

    def test_state_follows_each_row_of_the_comparison(self):
        for content, code in ROWS.items():
            with self.subTest(pin=content):
                pin(self.root, content)
                result = run(self.root, "state", "--format", "json")
                self.assertEqual(code, result.returncode, result.stderr)
                if code == 0:
                    self.assertNotIn(".ginrc", result.stderr)
                    json.loads(result.stdout)
                else:
                    self.assertEqual("", result.stdout)
                    self.assertEqual(1, len(result.stderr.splitlines()), result.stderr)
                    self.assertTrue(result.stderr.startswith("error: "), result.stderr)

    def test_older_gin_names_both_versions_and_the_guide(self):
        pin(self.root, HIGHER)
        error = run(self.root, "state").stderr
        self.assertIn(f"gin {CLI_VERSION} is older than this project needs ({HIGHER}, {self.root / '.ginrc'})", error)
        self.assertIn("update gin", error)
        self.assertIn(version_pin.GUIDE, error)

    def test_newer_major_names_both_versions_and_the_project_upgrade(self):
        pin(self.root, OLDER_MAJOR)
        error = run(self.root, "state").stderr
        self.assertIn(f"gin {CLI_VERSION} is a newer major version than this project uses ({OLDER_MAJOR}", error)
        self.assertIn("gin setup update --approve", error)
        self.assertIn(version_pin.GUIDE, error)

    def test_invalid_pin_says_what_the_file_must_hold(self):
        pin(self.root, "３.１.０")
        result = run(self.root, "state")
        self.assertEqual(2, result.returncode)
        self.assertIn(f"{self.root / '.ginrc'} must hold one version X.Y.Z", result.stderr)

    def test_a_pin_that_is_not_utf8_is_invalid(self):
        (self.root / ".ginrc").write_bytes(b"\xff\xfe\n")
        result = run(self.root, "state")
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertEqual(f"error: {self.root / '.ginrc'} must hold one version X.Y.Z\n", result.stderr)

    def test_a_pin_with_a_utf8_byte_order_mark_is_read(self):
        (self.root / ".ginrc").write_bytes(b"\xef\xbb\xbf" + CLI_VERSION.encode() + b"\r\n")
        result = run(self.root, "state", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)

    def test_version_paths_and_version_command_run_in_every_case(self):
        for content in ROWS:
            with self.subTest(pin=content):
                pin(self.root, content)
                self.assertEqual(f"gin {CLI_VERSION}\n", run(self.root, "--version").stdout)
                paths = run(self.root, "paths")
                self.assertEqual(0, paths.returncode, paths.stderr)
                self.assertIn("lib_dir", json.loads(paths.stdout))
                version = run(self.root, "version")
                self.assertIn(version.returncode, (0, 1), version.stderr)
                self.assertTrue(version.stdout.startswith(f"gin {CLI_VERSION}\n"), version.stdout)

    def test_setup_runs_under_a_newer_major_version_and_state_does_not(self):
        pin(self.root, OLDER_MAJOR)
        doctor = run(self.root, "setup", "doctor", "--format", "json")
        self.assertEqual(0, doctor.returncode, doctor.stderr)
        self.assertEqual(OLDER_MAJOR, json.loads(doctor.stdout)["checks_details"]["version"]["required"])
        self.assertEqual(2, run(self.root, "state").returncode)

    def test_setup_is_refused_for_an_older_gin(self):
        pin(self.root, HIGHER)
        self.assertEqual(2, run(self.root, "setup", "doctor").returncode)

    def test_lookup_from_a_subdirectory(self):
        pin(self.root, HIGHER)
        sub = self.root / "src/deep"
        sub.mkdir(parents=True)
        self.assertEqual(2, run(sub, "state").returncode)

    def test_lookup_from_a_linked_worktree(self):
        pin(self.root, HIGHER)
        git(self.root, "add", ".ginrc")
        git(self.root, "commit", "-qm", "pin", "--no-verify")
        worktree = self.base / "linked"
        git(self.root, "worktree", "add", "-q", str(worktree), "-b", "feature")
        result = run(worktree, "state")
        self.assertEqual(2, result.returncode)
        self.assertIn(str(worktree / ".ginrc"), result.stderr)

    def test_lookup_follows_the_repository_option(self):
        pin(self.root, HIGHER)
        elsewhere = init_repo(self.base / "elsewhere")
        self.assertEqual(0, run(elsewhere, "state").returncode)
        self.assertEqual(2, run(elsewhere, "state", "--repository", str(self.root)).returncode)
        self.assertEqual(2, run(elsewhere, "state", f"--repository={self.root}").returncode)
        for option in (["--repo", str(self.root)], [f"--repo={self.root}"], ["--rep", str(self.root)]):
            with self.subTest(option=option):
                result = run(elsewhere, "setup", "doctor", *option)
                self.assertEqual(2, result.returncode, result.stdout)
                self.assertIn("is older than this project needs", result.stderr)
        for option in (["--re", str(self.root)], [f"--re={self.root}"]):
            with self.subTest(option=option):
                result = run(elsewhere, "state", *option)
                self.assertEqual(2, result.returncode, result.stdout)
                self.assertIn("is older than this project needs", result.stderr)
        self.assertEqual(2, run(elsewhere, "setup", "doctor", "--repository", str(self.root)).returncode)


class VersionCommandTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name).resolve()
        self.root = self.base / "project"
        self.root.mkdir()
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.env = {**os.environ, "PATH": str(self.bin)}

    def test_text_output_and_exit_codes(self):
        result = run(self.root, "version", env=self.env)
        self.assertEqual((0, f"gin {CLI_VERSION}\n"), (result.returncode, result.stdout))

        pin(self.root, LOWER)
        result = run(self.root, "version", env=self.env)
        self.assertEqual(0, result.returncode)
        self.assertEqual([f"gin {CLI_VERSION}", f"project: {LOWER} ({self.root / '.ginrc'})", "compatible: yes"],
                         result.stdout.splitlines())

        pin(self.root, HIGHER)
        result = run(self.root, "version", env=self.env)
        self.assertEqual(1, result.returncode)
        self.assertEqual([f"gin {CLI_VERSION}", f"project: {HIGHER} ({self.root / '.ginrc'})", "compatible: no"],
                         result.stdout.splitlines())

    def test_json_output_and_exit_codes(self):
        result = run(self.root, "version", "--format", "json", env=self.env)
        self.assertEqual(0, result.returncode)
        self.assertEqual({"installed": CLI_VERSION, "required": None, "path": None, "status": "none",
                          "compatible": True, "companions": {}}, json.loads(result.stdout))

        pin(self.root, CLI_VERSION)
        result = run(self.root, "version", "--format", "json", env=self.env)
        self.assertEqual(0, result.returncode)
        self.assertEqual({"installed": CLI_VERSION, "required": CLI_VERSION, "path": str(self.root / ".ginrc"),
                          "status": "compatible", "compatible": True, "companions": {}}, json.loads(result.stdout))

        pin(self.root, HIGHER)
        result = run(self.root, "version", "--format", "json", env=self.env)
        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual(("older", False, HIGHER), (payload["status"], payload["compatible"], payload["required"]))

    def test_repository_option(self):
        pin(self.root, HIGHER)
        result = run(self.base, "version", "--repository", str(self.root), "--format", "json", env=self.env)
        self.assertEqual(1, result.returncode)
        self.assertEqual(str(self.root / ".ginrc"), json.loads(result.stdout)["path"])

    def test_companions_found_on_path(self):
        qa = self.bin / "gin-qa"
        qa.write_text("#!/bin/sh\necho 'gin-qa 9.9.9'\n", encoding="utf-8")
        qa.chmod(0o755)
        fake_orchestrator(self.bin)
        env = {**self.env, "PATH": f"{self.bin}{os.pathsep}{Path(sys.executable).parent}"}  # the fake runs python3
        text = run(self.root, "version", env=env).stdout.splitlines()
        self.assertEqual([f"gin {CLI_VERSION}", "gin-qa 9.9.9", "gin-orchestrator 0.1.0"], text)
        payload = json.loads(run(self.root, "version", "--format", "json", env=env).stdout)
        self.assertEqual({"gin-qa": "9.9.9", "gin-orchestrator": "0.1.0"}, payload["companions"])

        qa.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        payload = json.loads(run(self.root, "version", "--format", "json", env=env).stdout)
        self.assertEqual({"gin-orchestrator": "0.1.0"}, payload["companions"])

    def test_hook_is_silent_without_pin_and_when_compatible(self):
        for content in (None, CLI_VERSION, LOWER):
            with self.subTest(pin=content):
                pin(self.root, content)
                result = run(self.root, "version", "--hook", env=self.env)
                self.assertEqual((0, "", ""), (result.returncode, result.stdout, result.stderr))

    def test_hook_prints_one_line_when_older_or_invalid(self):
        for content, needle in ((HIGHER, f"is older than this project needs ({HIGHER}"),
                                ("3.1", "must hold one version X.Y.Z")):
            with self.subTest(pin=content):
                pin(self.root, content)
                result = run(self.root, "version", "--hook", env=self.env)
                self.assertEqual(0, result.returncode)
                self.assertEqual(1, len(result.stdout.splitlines()), result.stdout)
                self.assertIn(needle, result.stdout)
                self.assertTrue(result.stdout.rstrip("\n").endswith(" " + HOOK_TAIL), result.stdout)

    def test_hook_reports_a_pin_that_is_not_utf8(self):
        (self.root / ".ginrc").write_bytes(b"\xff\xfe\n")
        result = run(self.root, "version", "--hook", env=self.env)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(f"{self.root / '.ginrc'} must hold one version X.Y.Z {HOOK_TAIL}\n", result.stdout)

    def test_the_home_directory_and_above_are_not_searched_from_inside_it(self):
        home = self.base / "home"
        inside = home / "work/project"
        inside.mkdir(parents=True)
        outside = self.base / "elsewhere/project"
        outside.mkdir(parents=True)
        pin(home, HIGHER)
        pin(self.base, HIGHER)
        env = {**self.env, "HOME": str(home)}
        found = json.loads(run(inside, "version", "--format", "json", env=env).stdout)
        self.assertEqual(("none", None), (found["status"], found["path"]))
        found = json.loads(run(outside, "version", "--format", "json", env=env).stdout)
        self.assertEqual(("older", str(self.base / ".ginrc")), (found["status"], found["path"]))

    def test_orchestrator_is_found_through_executables_local_yaml(self):
        hidden = self.base / "hidden"
        fake_orchestrator(hidden)
        (self.root / ".agent-workflow").mkdir()
        (self.root / ".agent-workflow/executables.local.yaml").write_text(
            f'schema_version: "2.10"\nexecutables:\n  gin-orchestrator: {hidden / "gin-orchestrator"}\n',
            encoding="utf-8")
        env = {**self.env, "PATH": f"{self.bin}{os.pathsep}{Path(sys.executable).parent}"}  # the fake runs python3
        payload = json.loads(run(self.root, "version", "--format", "json", env=env).stdout)
        self.assertEqual({"gin-orchestrator": "0.1.0"}, payload["companions"])

    def test_hook_exits_zero_when_the_pin_cannot_be_read(self):
        (self.root / ".ginrc").mkdir()
        result = run(self.root, "version", "--hook", env=self.env)
        self.assertEqual((0, ""), (result.returncode, result.stdout))
        self.assertEqual(2, run(self.root, "state", env=self.env).returncode)


if __name__ == "__main__":
    unittest.main()

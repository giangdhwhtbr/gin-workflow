from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.executable_resolver import resolve_harness_executable  # noqa: E402


class ExecutableResolverTests(unittest.TestCase):
    def test_returns_none_for_empty_or_whitespace(self):
        self.assertIsNone(resolve_harness_executable(""))
        self.assertIsNone(resolve_harness_executable("   "))
        self.assertIsNone(resolve_harness_executable(None))

    def test_resolves_existing_absolute_executable_path(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "my-cli"
            binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            binary.chmod(0o755)

            resolved = resolve_harness_executable(str(binary))
            self.assertEqual(os.path.abspath(str(binary)), resolved)

    def test_returns_none_for_non_executable_or_missing_absolute_path(self):
        with tempfile.TemporaryDirectory() as directory:
            non_exec = Path(directory) / "not-executable"
            non_exec.write_text("plain text", encoding="utf-8")
            non_exec.chmod(0o644)

            self.assertIsNone(resolve_harness_executable(str(non_exec)))
            self.assertIsNone(resolve_harness_executable(str(Path(directory) / "missing")))

    def test_resolves_binary_from_standard_path(self):
        # python3 is guaranteed to exist on PATH
        resolved = resolve_harness_executable("python3")
        self.assertIsNotNone(resolved)
        self.assertTrue(os.access(resolved, os.X_OK))

    def test_resolves_antigravity_literal_alias_to_agy(self):
        with tempfile.TemporaryDirectory() as directory:
            dummy_agy = Path(directory) / "agy"
            dummy_agy.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            dummy_agy.chmod(0o755)

            old_path = os.environ.get("PATH", "")
            try:
                os.environ["PATH"] = f"{directory}:{old_path}"
                resolved = resolve_harness_executable("antigravity", provider="antigravity")
                self.assertEqual(str(dummy_agy), resolved)
            finally:
                os.environ["PATH"] = old_path

    def test_finds_opencode_in_its_default_install_dir(self):
        from workflow_core import executable_resolver as module

        self.assertIn(Path.home() / ".opencode/bin", module.COMMON_INSTALL_DIRS)
        with tempfile.TemporaryDirectory() as directory:
            exe = Path(directory) / "opencode"
            exe.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            exe.chmod(0o755)
            with mock.patch.object(module, "COMMON_INSTALL_DIRS", (Path(directory),)), \
                    mock.patch("shutil.which", return_value=None):
                self.assertEqual(str(exe), module.resolve_harness_executable("opencode", provider="opencode"))

    def test_preserves_symlink_without_resolving_to_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "real-binary-v1.0"
            target.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            target.chmod(0o755)

            symlink = root / "cli-symlink"
            symlink.symlink_to(target)

            resolved = resolve_harness_executable(str(symlink))
            self.assertEqual(os.path.abspath(str(symlink)), resolved)
            self.assertTrue(os.path.islink(resolved))

    def test_does_not_alias_custom_wrapper_for_antigravity(self):
        # A custom wrapper named 'my-agy' should not be silently replaced by 'agy'
        self.assertIsNone(resolve_harness_executable("my-agy-wrapper-nonexistent", provider="antigravity"))

    def test_us5_finds_cmd_shim_in_common_dir_with_pathext(self):
        from workflow_core import executable_resolver as module
        with tempfile.TemporaryDirectory() as directory:
            shim = Path(directory) / "claude.cmd"
            shim.write_text("@echo off\r\n", encoding="utf-8")
            shim.chmod(0o755)
            with mock.patch.object(module, "COMMON_INSTALL_DIRS", (Path(directory),)), \
                    mock.patch.dict(os.environ, {"PATH": "", "PATHEXT": ".COM;.EXE;.BAT;.CMD"}), \
                    mock.patch.object(module.os, "name", "nt"):
                self.assertEqual(str(shim), module.resolve_harness_executable("claude", provider="claude"))

    def _probe_dir_with_bare_and_cmd(self, os_name):
        from workflow_core import executable_resolver as module
        with tempfile.TemporaryDirectory() as directory:
            for name in ("claude", "claude.cmd"):
                (Path(directory) / name).write_text("x", encoding="utf-8")
                (Path(directory) / name).chmod(0o755)
            with mock.patch.object(module, "COMMON_INSTALL_DIRS", (Path(directory),)), \
                    mock.patch.dict(os.environ, {"PATH": "", "PATHEXT": ".COM;.EXE;.BAT;.CMD"}):
                if os_name == "nt":
                    with mock.patch.object(module.os, "name", "nt"):
                        resolved = module.resolve_harness_executable("claude")
                else:
                    resolved = module.resolve_harness_executable("claude")
            return Path(resolved).name

    def test_nt_prefers_pathext_shim_over_bare_name(self):
        self.assertEqual("claude.cmd", self._probe_dir_with_bare_and_cmd("nt"))

    def test_posix_prefers_bare_name(self):
        self.assertEqual("claude", self._probe_dir_with_bare_and_cmd("posix"))

    def test_us5_appdata_npm_is_probed_on_windows(self):
        from workflow_core import executable_resolver as module
        with mock.patch.dict(os.environ, {"APPDATA": r"C:\Users\x\AppData\Roaming"}):
            self.assertIn(Path(r"C:\Users\x\AppData\Roaming") / "npm", module.common_install_dirs("nt"))
            self.assertFalse(any(path.name == "npm" for path in module.common_install_dirs("posix")))


if __name__ == "__main__":
    unittest.main()

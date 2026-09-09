from pathlib import Path
import os
import sys
import tempfile
import unittest


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


if __name__ == "__main__":
    unittest.main()

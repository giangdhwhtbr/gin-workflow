from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core import atomic  # noqa: E402


class AtomicWriteTests(unittest.TestCase):
    def test_second_replace_failure_rolls_back_first_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.yaml"
            second = root / "second.yaml"
            first.write_bytes(b"old-first")
            second.write_bytes(b"old-second")
            real_replace = atomic.os.replace
            failed = False

            def fail_second(source, destination):
                nonlocal failed
                if Path(destination) == second and not failed:
                    failed = True
                    raise OSError("second replace failed")
                return real_replace(source, destination)

            with mock.patch.object(atomic.os, "replace", side_effect=fail_second):
                with self.assertRaisesRegex(OSError, "second replace failed"):
                    atomic.atomic_write_many(
                        {first: b"new-first", second: b"new-second"}
                    )

            self.assertEqual(b"old-first", first.read_bytes())
            self.assertEqual(b"old-second", second.read_bytes())

    def test_incomplete_rollback_retains_original_backup_for_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.yaml"
            second = root / "second.yaml"
            first.write_bytes(b"old-first")
            second.write_bytes(b"old-second")
            real_replace = atomic.os.replace

            def fail_forward_and_rollback(source, destination):
                source_path = Path(source)
                destination_path = Path(destination)
                if destination_path == second and source_path.suffix == ".tmp":
                    raise OSError("forward failed")
                if destination_path == first and source_path.suffix == ".rollback":
                    raise OSError("rollback failed")
                return real_replace(source, destination)

            with mock.patch.object(
                atomic.os, "replace", side_effect=fail_forward_and_rollback
            ):
                with self.assertRaisesRegex(RuntimeError, "rollback was incomplete"):
                    atomic.atomic_write_many(
                        {first: b"new-first", second: b"new-second"}
                    )

            backups = tuple(root.glob(".first.yaml.*.rollback"))
            self.assertEqual(1, len(backups))
            self.assertEqual(b"old-first", backups[0].read_bytes())

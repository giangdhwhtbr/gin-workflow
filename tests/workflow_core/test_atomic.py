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

    def test_fsync_directory_is_noop_on_windows(self):
        with mock.patch.object(atomic.os, "name", "nt"):
            with mock.patch.object(atomic.os, "open") as mock_open:
                atomic._fsync_directory(Path("/dummy/dir"))
                mock_open.assert_not_called()

    def test_atomic_write_many_succeeds_without_fchmod(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "file.txt"
            original_fchmod = getattr(atomic.os, "fchmod", None)
            if hasattr(atomic.os, "fchmod"):
                delattr(atomic.os, "fchmod")
            try:
                atomic.atomic_write_many({target: b"hello"})
                self.assertEqual(b"hello", target.read_bytes())
            finally:
                if original_fchmod is not None:
                    atomic.os.fchmod = original_fchmod

    def test_replace_atomic_retries_on_windows_permission_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            dest = root / "dest.txt"
            source.write_bytes(b"content")

            attempts = 0
            real_replace = atomic.os.replace

            def flaky_replace(src, dst):
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise PermissionError(13, "Permission denied")
                return real_replace(src, dst)

            with mock.patch.object(atomic.os, "name", "nt"):
                with mock.patch.object(atomic.os, "replace", side_effect=flaky_replace):
                    with mock.patch.object(atomic.time, "sleep"):
                        atomic._replace_atomic(source, dest)
            self.assertEqual(3, attempts)
            self.assertEqual(b"content", dest.read_bytes())

    def test_replace_atomic_raises_after_max_retries_on_windows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            dest = root / "dest.txt"
            source.write_bytes(b"content")

            with mock.patch.object(atomic.os, "name", "nt"):
                with mock.patch.object(
                    atomic.os, "replace", side_effect=PermissionError(13, "Access denied")
                ):
                    with mock.patch.object(atomic.time, "sleep"):
                        with self.assertRaises(PermissionError):
                            atomic._replace_atomic(source, dest)

    def test_unlink_file_retries_on_windows_permission_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "file.txt"
            target.write_bytes(b"to delete")

            attempts = 0
            real_unlink = Path.unlink

            def flaky_unlink(self, missing_ok=False):
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise PermissionError(13, "File in use")
                return real_unlink(self, missing_ok=missing_ok)

            with mock.patch.object(atomic.os, "name", "nt"):
                with mock.patch.object(Path, "unlink", flaky_unlink):
                    with mock.patch.object(atomic.time, "sleep"):
                        atomic._unlink_file(target)
            self.assertEqual(3, attempts)
            self.assertFalse(target.exists())




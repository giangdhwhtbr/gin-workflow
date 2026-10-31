import errno
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins/gin-workflow/src/scripts"))

from workflow_core import locking  # noqa: E402
from workflow_core.locking import file_lock  # noqa: E402


class FakeMsvcrt:
    LK_UNLCK = 0
    LK_NBLCK = 2

    def __init__(self, failures=()):
        self.failures = list(failures)
        self.calls = []

    def locking(self, fd, mode, nbytes):
        self.calls.append(mode)
        if mode == self.LK_NBLCK and self.failures:
            raise self.failures.pop(0)


def busy():
    return OSError(errno.EACCES, "Permission denied")


class WindowsLockTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "sub" / ".lock"

    def windows(self, fake):
        return mock.patch.dict(sys.modules, {"fcntl": None, "msvcrt": fake})

    def test_retries_on_contention_then_locks_and_unlocks(self):
        fake = FakeMsvcrt([busy(), busy()])
        with self.windows(fake), file_lock(self.path, exclusive=False):
            pass
        self.assertEqual([2, 2, 2, 0], fake.calls)
        self.assertEqual(1, self.path.stat().st_size)

    def test_non_contention_error_raises_without_retry(self):
        fake = FakeMsvcrt([OSError(errno.EBADF, "Bad file descriptor")])
        with self.windows(fake), self.assertRaises(OSError) as raised:
            with file_lock(self.path):
                self.fail("lock must not be acquired")
        self.assertEqual(errno.EBADF, raised.exception.errno)
        self.assertEqual([2], fake.calls)

    def test_gives_up_after_the_timeout(self):
        fake = FakeMsvcrt([busy() for _ in range(10_000)])
        with self.windows(fake), mock.patch.object(locking, "LOCK_TIMEOUT", 0.1):
            with self.assertRaisesRegex(TimeoutError, re.escape(str(self.path))):
                with file_lock(self.path):
                    self.fail("lock must not be acquired")

    def test_body_errors_propagate_and_still_unlock(self):
        fake = FakeMsvcrt()
        with self.windows(fake), self.assertRaisesRegex(OSError, "from the body"):
            with file_lock(self.path):
                raise OSError("from the body")
        self.assertEqual([2, 0], fake.calls)

    def test_no_locking_module_raises(self):
        with mock.patch.dict(sys.modules, {"fcntl": None, "msvcrt": None}):
            with self.assertRaisesRegex(OSError, "advisory file locking"):
                with file_lock(self.path):
                    self.fail("lock must not be acquired")


@unittest.skipIf(sys.platform == "win32", "POSIX flock")
class PosixLockTests(unittest.TestCase):
    def test_second_holder_waits_for_the_first(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".lock"
            order, held = [], threading.Event()

            def first():
                with file_lock(path):
                    held.set()
                    time.sleep(0.2)
                    order.append("first released")

            thread = threading.Thread(target=first)
            thread.start()
            held.wait(5)
            with file_lock(path):
                order.append("second acquired")
            thread.join()
            self.assertEqual(["first released", "second acquired"], order)

    def test_shared_locks_do_not_block_each_other(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".lock"
            with file_lock(path, exclusive=False), file_lock(path, exclusive=False):
                pass

    def test_us3_waiter_times_out_while_the_lock_is_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.lock"
            held, release = threading.Event(), threading.Event()

            def holder():
                with file_lock(path):
                    held.set()
                    release.wait(5)

            thread = threading.Thread(target=holder)
            thread.start()
            held.wait(5)
            try:
                started = time.monotonic()
                with mock.patch.object(locking, "LOCK_TIMEOUT", 0.2), self.assertRaises(TimeoutError):
                    with file_lock(path):
                        pass
                self.assertLess(time.monotonic() - started, 2)
            finally:
                release.set()
                thread.join()


class SingleImplementationTests(unittest.TestCase):
    def test_only_locking_imports_fcntl_or_msvcrt(self):
        pattern = re.compile(r"^\s*(import (fcntl|msvcrt)\b|from (fcntl|msvcrt) import)", re.M)
        offenders = [str(path.relative_to(ROOT)) for path in sorted(ROOT.glob("plugins/*/src/scripts/**/*.py"))
                     if path.name != "locking.py" and pattern.search(path.read_text(encoding="utf-8"))]
        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()

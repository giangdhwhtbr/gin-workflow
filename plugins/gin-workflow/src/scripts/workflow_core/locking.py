"""Cross-process advisory file locks: `fcntl.flock` on POSIX, `msvcrt.locking` on Windows."""

from __future__ import annotations

from contextlib import contextmanager
import errno
from pathlib import Path
import time
from typing import Iterator

LOCK_TIMEOUT = 60.0
_CONTENTION = {errno.EACCES, errno.EAGAIN, getattr(errno, "EWOULDBLOCK", errno.EAGAIN),
               getattr(errno, "EDEADLOCK", errno.EDEADLK)}


@contextmanager
def file_lock(path: Path, *, exclusive: bool = True) -> Iterator[None]:
    """Hold a lock on `path` (created if missing) for the body of the `with`.

    Waits at most `LOCK_TIMEOUT` seconds, then raises `TimeoutError`."""
    try:
        import fcntl
    except ImportError:
        fcntl = None
    msvcrt = None
    if fcntl is None:
        try:
            import msvcrt
        except ImportError as error:
            raise OSError("file locking requires POSIX or Windows advisory file locking") from error
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if fcntl is not None:
            mode = (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB

            def acquire() -> None:
                fcntl.flock(stream.fileno(), mode)

            def release() -> None:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        else:
            # simplified: Windows has no shared lock, so readers take the exclusive one; use LockFileEx for shared locks if reader contention matters.
            stream.seek(0)
            if not stream.read(1):
                stream.write(b"\0")
                stream.flush()

            def acquire() -> None:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)

            def release() -> None:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        timeout = LOCK_TIMEOUT
        deadline = time.monotonic() + timeout
        while True:
            try:
                acquire()
                break
            except OSError as error:
                if error.errno not in _CONTENTION:
                    raise
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"timed out after {timeout:g}s waiting for lock {path}") from error
                time.sleep(0.05)
        try:
            yield
        finally:
            release()

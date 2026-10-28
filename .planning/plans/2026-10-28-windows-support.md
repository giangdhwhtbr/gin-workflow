# Plan: Windows support — one file lock, Python worktree commands

Epic: gin-workflow-eq77
Spec: `.planning/specs/2026-10-28-windows-support-design.md`
Branch: `fix/windows-support` (builds on 8b50069, which already holds the `events.py` msvcrt fallback and the `atomic.py` `nt` guards)

## Goal

On Windows without WSL, every gin-workflow command that takes a file lock or creates a worktree runs. One lock implementation, `workflow_core.locking.file_lock`, replaces the four copies. `gin-workflow worktree create|cleanup` in Python replaces `worktree-create.sh` and `worktree-cleanup.sh` for skills and for gin-orchestrator.

## Architecture

- `workflow_core/locking.py`: `file_lock(path, *, exclusive=True)`. POSIX `fcntl.flock`; Windows `msvcrt.locking(LK_NBLCK)` on byte 0, retrying only on contention, bounded by `WINDOWS_LOCK_TIMEOUT = 60.0` seconds. `fcntl`/`msvcrt` are imported inside the function so tests can swap them through `sys.modules`.
- Callers: `events._file_lock` (wraps lock-acquire `OSError` into `EventPersistenceError`), `assignments.write_assignments`, `review_ledger.cli.ledger_lock`, `gin_orchestrator.evidence.FilesystemEvidenceIndex._file_lock` (through `workflow_core.ext.file_lock`).
- `workflow_core/worktrees.py`: `create`, `cleanup`, `main`. `cli.py` dispatches `gin-workflow worktree`. `ext.py` re-exports `create_worktree`, `cleanup_worktree`.
- `gin_orchestrator/workspace.py` calls `create_worktree`/`cleanup_worktree` directly; the script lookup, the runner, and the installer copy steps go away.

## Tech Stack

Python 3 stdlib (`fcntl`, `msvcrt`, `errno`, `argparse`, `subprocess`, `contextlib`), unittest, bash/PowerShell install scripts and smoke tests.

## Global Constraints

Copied from the spec:

- POSIX behavior of every lock is unchanged: blocking, shared locks still shared.
- The new `TimeoutError` on Windows is an `OSError`; `events.py` maps it to `EventPersistenceError` like other lock failures.
- Removing the `.sh` scripts changes the skill text and the gin-orchestrator install layout. Both ship in the same release, so no compatibility shim is kept. Projects that call the scripts directly from their own docs must switch to `gin-workflow worktree`.
- `ext.py` only gains names; gin-orchestrator built against the old facade still imports. `EXT_VERSION` stays 1.
- Out of scope: items 5, 6, 7 of the epic; renaming either `stage` key; a `doctor` version-skew check; the `safety-check.sh`/`post-edit.sh` hooks; `merge-integration.sh`.
- R2 (`atomic.py`) is already done on the branch (8b50069) and needs no track.

Repository constraints:

- Commit on `fix/windows-support` only; never on `master`. No PR, merge, or force-push without explicit approval.
- Full suite: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all`.
- Remove imports that a change leaves unused; do not touch unrelated code.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `brainstorm`: `high_reasoning`
  - `design`: `high_reasoning`
  - `plan`: `standard_impl`
  - `implement`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: Use `high_reasoning` for planning only when execution boundaries, dependency sequencing, or major tradeoffs are still unresolved.

## Requirement Analysis
- Problem statement: gin-workflow and gin-orchestrator import `fcntl` in four places and ship bash-only worktree scripts, so on Windows without WSL gates cannot be recorded, routes cannot resolve, gin-orchestrator cannot import, and worktrees cannot be created.
- Success criteria: US-1..US-3 of the spec; `grep -rn "import fcntl\|import msvcrt" plugins/*/src` matches only `locking.py`; full suite and install smoke tests pass.
- Constraints: see Global Constraints.
- Non-goals: Windows CI; shared locks on Windows; any change to hook scripts.

## Approach Options
### Option 1: one `file_lock` in `workflow_core`, worktree logic in Python behind the CLI and `ext`
- Summary: the spec's design.
- Pros: one place to fix locking; no bash dependency; gin-orchestrator drops script discovery and the installer copy step.
- Cons: touches two plugins and both installers in one change.

### Option 2: patch each lock in place and keep the `.sh` scripts, documenting `git worktree add`
- Summary: smallest diff per file.
- Pros: fewer files.
- Cons: four lock copies stay and drift (the retry bug exists in two already); gin-orchestrator still fails without bash.

### Recommended Approach
- Selected option: Option 1.
- Reasoning: confirmed in the spec; it removes the duplication that caused item 2.

## Scope
- In scope: R1 (shared lock and its four callers), R3 (worktree module, CLI, ext, orchestrator, installers, skills, docs).
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Three tracks; Track 1 and Track 2 both edit ext.py and test_ext.py, and Track 3 consumes Track 2's ext exports, so they run in order in one session.
```

## Tasks

### Track 1: Shared `file_lock` and its four callers
- **Dependencies**: none
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Model guidance**: `standard_impl`
- **Estimated complexity**: medium
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/locking.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/events.py` (imports lines 3–16; `_file_lock` lines 166–206)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/assignments.py` (imports lines 5–11; `_manifest_lock` lines 165–175; its use at line 193)
  - Modify `plugins/gin-workflow/src/scripts/review_ledger/cli.py` (imports lines 1–24; fcntl/msvcrt block and `_lock_stream`/`_unlock_stream` lines 26–55; `ledger_lock` lines 87–98)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/ext.py` (import and `__all__`)
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/evidence.py` (line 9 `import fcntl`; `workflow_core.ext` import lines 29–34; `_file_lock` lines 371–381)
  - Test: create `tests/workflow_core/test_locking.py`; modify `tests/workflow_core/test_events.py`, `tests/workflow_core/test_ext.py`
- **Interfaces produced**:
  - `workflow_core.locking.WINDOWS_LOCK_TIMEOUT: float = 60.0`
  - `workflow_core.locking.file_lock(path: Path, *, exclusive: bool = True) -> ContextManager[None]` — raises `OSError` when no locking module exists, `TimeoutError` on Windows after `WINDOWS_LOCK_TIMEOUT`, and re-raises any non-contention `OSError` from `msvcrt.locking`.
  - `workflow_core.ext.file_lock` (re-export)
- **Interfaces consumed**: none
- **Steps**:
  1. Write `tests/workflow_core/test_locking.py`:
     ```python
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
             with self.windows(fake), mock.patch.object(locking, "WINDOWS_LOCK_TIMEOUT", 0.1):
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


     class SingleImplementationTests(unittest.TestCase):
         def test_only_locking_imports_fcntl_or_msvcrt(self):
             pattern = re.compile(r"^\s*(import (fcntl|msvcrt)\b|from (fcntl|msvcrt) import)", re.M)
             offenders = [str(path.relative_to(ROOT)) for path in sorted(ROOT.glob("plugins/*/src/scripts/**/*.py"))
                          if path.name != "locking.py" and pattern.search(path.read_text(encoding="utf-8"))]
             self.assertEqual([], offenders)


     if __name__ == "__main__":
         unittest.main()
     ```
  2. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_locking` → fails with `ImportError` (no `workflow_core.locking`).
  3. Create `plugins/gin-workflow/src/scripts/workflow_core/locking.py`:
     ```python
     """Cross-process advisory file locks: `fcntl.flock` on POSIX, `msvcrt.locking` on Windows."""

     from __future__ import annotations

     from contextlib import contextmanager
     import errno
     from pathlib import Path
     import time
     from typing import Iterator

     WINDOWS_LOCK_TIMEOUT = 60.0
     _CONTENTION = {errno.EACCES, getattr(errno, "EDEADLOCK", errno.EDEADLK)}


     @contextmanager
     def file_lock(path: Path, *, exclusive: bool = True) -> Iterator[None]:
         """Hold a lock on `path` (created if missing) for the body of the `with`."""
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
                 fcntl.flock(stream.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
                 try:
                     yield
                 finally:
                     fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                 return
             # ponytail: Windows has no shared lock, so readers take the exclusive one.
             stream.seek(0)
             if not stream.read(1):
                 stream.write(b"\0")
                 stream.flush()
             deadline = time.monotonic() + WINDOWS_LOCK_TIMEOUT
             while True:
                 stream.seek(0)
                 try:
                     msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                     break
                 except OSError as error:
                     if error.errno not in _CONTENTION:
                         raise
                     if time.monotonic() >= deadline:
                         raise TimeoutError(
                             f"timed out after {WINDOWS_LOCK_TIMEOUT:g}s waiting for lock {path}"
                         ) from error
                     time.sleep(0.05)
             try:
                 yield
             finally:
                 stream.seek(0)
                 msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
     ```
  4. Run the step-2 command → passes except `test_only_locking_imports_fcntl_or_msvcrt` (lists `events.py`, `assignments.py`, `review_ledger/cli.py`, `evidence.py`).
  5. `events.py`: change `from contextlib import contextmanager` to `from contextlib import ExitStack, contextmanager`; delete `import time`; add `from .locking import file_lock` after `from .atomic import atomic_write_bytes`; replace the whole `_file_lock` body:
     ```python
     @contextmanager
     def _file_lock(path: Path, *, exclusive: bool) -> Iterator[None]:
         with ExitStack() as stack:
             try:
                 stack.enter_context(file_lock(path, exclusive=exclusive))
             except OSError as error:
                 raise EventPersistenceError(f"cannot lock {path}: {error}") from error
             yield
     ```
     `task_markdown.py` keeps importing `_file_lock` from `events`; do not change it.
  6. `assignments.py`: delete `_manifest_lock` (lines 165–175) and `from contextlib import contextmanager`; drop `Iterator` from the `typing` import; add `from .locking import file_lock`; replace `with _manifest_lock(lock_path):` with `with file_lock(lock_path):`.
  7. `review_ledger/cli.py`: delete the `try: import fcntl ... except ImportError: ... import msvcrt` block, `_lock_stream`, `_unlock_stream`, and `import time` (its only use was the retry sleep); add `from workflow_core.locking import file_lock` after `from workflow_core.atomic import atomic_write_many`; replace `ledger_lock`:
     ```python
     @contextmanager
     def ledger_lock(bead_id: str, base_dir: Optional[str] = None):
         json_path, _ = get_ledger_paths(bead_id, base_dir)
         with file_lock(Path(os.path.dirname(json_path)) / ".review.lock"):
             yield
     ```
  8. `ext.py`: add `from .locking import file_lock` (after `from .identity import ...`) and `"file_lock"` to `__all__` between `"default_provider_model_config"` and `"freeze"`. Add `"file_lock"` at the same place in `EXPECTED` in `tests/workflow_core/test_ext.py`.
  9. `evidence.py`: delete `import fcntl`; add `file_lock` to the `from workflow_core.ext import (...)` list; replace the `_file_lock` method body:
     ```python
     @contextmanager
     def _file_lock(self, *, exclusive: bool):
         with file_lock(self.index_path.with_name(f".{self.index_path.name}.lock"), exclusive=exclusive):
             yield
     ```
  10. Append to `WorkflowEventTests` in `tests/workflow_core/test_events.py`:
      ```python
      def test_lock_timeout_becomes_event_persistence_error(self):
          @contextmanager
          def timed_out(path, *, exclusive):
              raise TimeoutError("timed out after 60s waiting for lock x")
              yield

          with mock.patch("workflow_core.events.file_lock", timed_out):
              with tempfile.TemporaryDirectory() as directory:
                  store = WorkflowEventStore(Path(directory) / "events.jsonl")
                  event = WorkflowEvent.create(event_type="worker.completed", workflow_id="wf-1",
                                               task_id="worker-1", payload={"status": "success"})
                  with self.assertRaisesRegex(EventPersistenceError, "timed out"):
                      store.append(event)
      ```
      and add `from contextlib import contextmanager` to its imports. The two existing `test_file_lock_*` tests stay as they are and must still pass.
  11. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_locking tests.workflow_core.test_events tests.workflow_core.test_ext tests.workflow_core.test_assignments tests.workflow_core.test_task_markdown` → all pass.
  12. Run the full suite → passes. Run `grep -rn "import fcntl\|import msvcrt" plugins/*/src` → only `workflow_core/locking.py` lines.
  13. Commit: `fix(locking): one cross-platform file lock for events, assignments, review ledger, evidence`.
- **Acceptance criteria**: `test_locking.py` passes (contention retry, non-contention raise, timeout, body error, missing module, POSIX contention, single implementation); existing events/assignments/review-ledger/evidence tests pass unchanged except the added cases; the grep in step 12 matches only `locking.py`.

### Track 2: `gin-workflow worktree create|cleanup` in Python
- **Dependencies**: Track 1
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Model guidance**: `standard_impl`
- **Estimated complexity**: medium
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/worktrees.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/cli.py` (`main`, lines 66–70 command tuple and usage string; dispatch after the `goal` branch, lines 82–84)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/ext.py` (import and `__all__`)
  - Modify `plugins/gin-workflow/src/skills/gin-worktrees/SKILL.md` (lines 22 and 34), `plugins/gin-workflow/src/skills/ship/SKILL.md` (line 35)
  - Modify `docs/reference/cli.md` (new `## \`gin-workflow worktree\`` section before `## \`gin-workflow task\``)
  - Test: create `tests/workflow_core/test_worktrees.py`; modify `tests/workflow_core/test_ext.py`
- **Interfaces produced**:
  - `workflow_core.worktrees.create(repo: Path, track_id: str, branch: str, base_ref: str | None = None) -> Path`
  - `workflow_core.worktrees.cleanup(repo: Path, track_id: str) -> Path | None`
  - `workflow_core.worktrees.main(argv: Sequence[str]) -> int`
  - `workflow_core.ext.create_worktree`, `workflow_core.ext.cleanup_worktree` (re-exports)
  - CLI: `gin-workflow worktree create [--repository DIR] TRACK_ID BRANCH [BASE_REF]`, `gin-workflow worktree cleanup [--repository DIR] TRACK_ID`
  - Errors: `ValueError` (invalid id, path escape, existing target, empty branch), `RuntimeError` (git failed; message is git's stderr), `OSError` (git missing).
- **Interfaces consumed**: none
- **Steps**:
  1. Write `tests/workflow_core/test_worktrees.py`:
     ```python
     import contextlib
     import io
     from pathlib import Path
     import subprocess
     import sys
     import tempfile
     import unittest

     sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"))

     from workflow_core import worktrees  # noqa: E402


     def git(root, *argv):
         return subprocess.run(["git", *argv], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


     class WorktreeTests(unittest.TestCase):
         def setUp(self):
             directory = tempfile.TemporaryDirectory()
             self.addCleanup(directory.cleanup)
             self.root = Path(directory.name).resolve()
             git(self.root, "init", "-q")
             git(self.root, "config", "user.email", "t@example.com")
             git(self.root, "config", "user.name", "Test")
             (self.root / "file.txt").write_text("base", encoding="utf-8")
             git(self.root, "add", ".")
             git(self.root, "commit", "-q", "-m", "base")
             self.base = git(self.root, "rev-parse", "--abbrev-ref", "HEAD")
             self.worktrees = self.root / ".planning/worktrees"

         def test_create_from_current_branch_then_cleanup_twice(self):
             path = worktrees.create(self.root, "t1", "bead/t1")
             self.assertEqual(self.worktrees / "t1", path)
             self.assertEqual("bead/t1", git(path, "rev-parse", "--abbrev-ref", "HEAD"))
             self.assertEqual(git(self.root, "rev-parse", self.base), git(path, "rev-parse", "HEAD"))
             self.assertEqual(path, worktrees.cleanup(self.root, "t1"))
             self.assertFalse(path.exists())
             self.assertIsNone(worktrees.cleanup(self.root, "t1"))

         def test_create_from_explicit_base_ref(self):
             git(self.root, "branch", "other")
             path = worktrees.create(self.root, "t2", "bead/t2", "other")
             self.assertEqual(git(self.root, "rev-parse", "other"), git(path, "rev-parse", "HEAD"))

         def test_rejects_unsafe_ids_without_side_effects(self):
             for track_id in ("../x", "a/b", "", ".", "..", "x y"):
                 with self.subTest(track_id=track_id), self.assertRaises(ValueError):
                     worktrees.create(self.root, track_id, "bead/x")
             self.assertFalse(self.worktrees.exists())
             self.assertEqual("", git(self.root, "branch", "--list", "bead/x"))

         def test_rejects_existing_target_and_empty_branch(self):
             (self.worktrees / "t3").mkdir(parents=True)
             with self.assertRaisesRegex(ValueError, "already exists"):
                 worktrees.create(self.root, "t3", "bead/t3")
             with self.assertRaisesRegex(ValueError, "branch"):
                 worktrees.create(self.root, "t4", " ")
             self.assertEqual("", git(self.root, "branch", "--list", "bead/t3"))

         def test_git_failure_is_a_runtime_error(self):
             with self.assertRaises(RuntimeError):
                 worktrees.create(self.root, "t5", "bead/t5", "no-such-ref")

         def test_cli_create_cleanup_and_error(self):
             out, err = io.StringIO(), io.StringIO()
             with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                 self.assertEqual(0, worktrees.main(["create", "--repository", str(self.root), "t6", "bead/t6"]))
                 self.assertEqual(1, worktrees.main(["create", "--repository", str(self.root), "../x", "b"]))
                 self.assertEqual(0, worktrees.main(["cleanup", "--repository", str(self.root), "t6"]))
                 self.assertEqual(0, worktrees.main(["cleanup", "--repository", str(self.root), "t6"]))
             self.assertIn(str(self.worktrees / "t6"), out.getvalue())
             self.assertIn("error: invalid track-id '../x'", err.getvalue())


     if __name__ == "__main__":
         unittest.main()
     ```
  2. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_worktrees` → fails with `ImportError`.
  3. Create `plugins/gin-workflow/src/scripts/workflow_core/worktrees.py`:
     ```python
     """`gin-workflow worktree`: create and remove track worktrees under `.planning/worktrees`."""

     from __future__ import annotations

     import argparse
     from pathlib import Path
     import re
     import subprocess
     import sys
     from typing import Sequence

     _TRACK_ID = re.compile(r"[A-Za-z0-9._-]+")


     def _git(repo: Path, *argv: str) -> str:
         completed = subprocess.run(["git", *argv], cwd=repo, text=True, capture_output=True, check=False)
         if completed.returncode:
             raise RuntimeError(completed.stderr.strip() or f"git {argv[0]} failed")
         return completed.stdout.strip()


     def _target(repo: Path, track_id: str) -> Path:
         if not _TRACK_ID.fullmatch(track_id):
             raise ValueError(f"invalid track-id '{track_id}'")
         root = (Path(_git(repo, "rev-parse", "--show-toplevel")) / ".planning/worktrees").resolve()
         target = (root / track_id).resolve()
         if target.parent != root:
             raise ValueError("resolved path escapes worktree root")
         return target


     def create(repo: Path, track_id: str, branch: str, base_ref: str | None = None) -> Path:
         """New branch `branch` checked out at `.planning/worktrees/<track_id>`, from `base_ref` or the current branch."""
         target = _target(repo, track_id)
         if target.exists():
             raise ValueError(f"directory {target} already exists")
         if not branch.strip():
             raise ValueError("branch is required")
         base = base_ref or _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
         _git(repo, "worktree", "add", "-b", branch, str(target), base)
         return target


     def cleanup(repo: Path, track_id: str) -> Path | None:
         """Remove the track's worktree; None when it does not exist."""
         target = _target(repo, track_id)
         if not target.exists():
             return None
         _git(repo, "worktree", "remove", str(target))
         return target


     def main(argv: Sequence[str]) -> int:
         parser = argparse.ArgumentParser(prog="gin-workflow worktree")
         commands = parser.add_subparsers(dest="command", required=True)
         create_parser = commands.add_parser("create")
         create_parser.add_argument("--repository", default=".")
         create_parser.add_argument("track_id")
         create_parser.add_argument("branch")
         create_parser.add_argument("base_ref", nargs="?")
         cleanup_parser = commands.add_parser("cleanup")
         cleanup_parser.add_argument("--repository", default=".")
         cleanup_parser.add_argument("track_id")
         args = parser.parse_args(list(argv))
         repo = Path(args.repository)
         try:
             if args.command == "create":
                 path = create(repo, args.track_id, args.branch, args.base_ref)
                 print(f"Worktree created at: {path} on branch {args.branch}")
             elif (removed := cleanup(repo, args.track_id)) is None:
                 print(f"No worktree for {args.track_id}; nothing to remove.")
             else:
                 print(f"Worktree {removed} removed.")
         except (ValueError, RuntimeError, OSError) as error:
             print(f"error: {error}", file=sys.stderr)
             return 1
         return 0
     ```
  4. Run the step-2 command → passes.
  5. `cli.py` `main`: add `"worktree"` to the command tuple (after `"goal"`) and to the usage string (after `goal`, i.e. `...,paths,goal,worktree}`); add the dispatch after the `goal` branch:
     ```python
     if argv[0] == "worktree":
         from .worktrees import main as worktrees_main
         return worktrees_main(argv[1:])
     ```
  6. `ext.py`: add `from .worktrees import cleanup as cleanup_worktree, create as create_worktree` (last import) and `"cleanup_worktree"` (between `"authorize_protected_action"` and `"create_context_manifest"`) and `"create_worktree"` (after `"create_context_manifest"`) to `__all__`. Add both names at the same places in `EXPECTED` in `tests/workflow_core/test_ext.py`.
  7. `docs/reference/cli.md`: insert before `## \`gin-workflow task\``:
     ````markdown
     ## `gin-workflow worktree`

     ```
     gin-workflow worktree create [--repository DIR] TRACK_ID BRANCH [BASE_REF]
     gin-workflow worktree cleanup [--repository DIR] TRACK_ID
     ```

     Creates or removes the git worktree for one track at `.planning/worktrees/<track-id>` in the repository's top level. `TRACK_ID` must match `[A-Za-z0-9._-]+` and resolve inside `.planning/worktrees`. `create` makes the new branch `BRANCH` from `BASE_REF` (default: the current branch, or `HEAD` when detached) and refuses an existing directory. `cleanup` runs `git worktree remove` and succeeds without doing anything when the directory does not exist. Runs on every platform; it replaces `worktree-create.sh` and `worktree-cleanup.sh`.

     Exit codes: 0 created, removed, or nothing to remove; 1 invalid track id, existing directory, or git failure (message on stderr); 2 invalid arguments.
     ````
  8. `gin-worktrees/SKILL.md` line 22: replace `` `scripts/worktree-create.sh <track-id> <branch> [base-ref]` (the script validates the id and path containment, and always creates the branch) `` with `` `gin-workflow worktree create <track-id> <branch> [base-ref]` (it validates the id and path containment, and always creates the branch) ``. Line 34: replace `` run `scripts/worktree-cleanup.sh <track-id>` `` with `` run `gin-workflow worktree cleanup <track-id>` ``. `ship/SKILL.md` line 35: same replacement as line 34.
  9. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_worktrees tests.workflow_core.test_ext tests.workflow_core.test_docs_coverage` → pass. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.cli worktree --help` from the repo root → exit 0, lists `create` and `cleanup`.
  10. Run the full suite → passes.
  11. Commit: `feat(worktree): gin-workflow worktree create|cleanup in Python`.
- **Acceptance criteria**: `test_worktrees.py` passes; `cli.md` documents the command (docs coverage test passes); the two skills name `gin-workflow worktree` and no longer name the `.sh` scripts.

### Track 3: gin-orchestrator uses the Python worktree functions; remove the shell scripts
- **Dependencies**: Track 2
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Model guidance**: `standard_impl`
- **Estimated complexity**: medium
- **Files**:
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/workspace.py` (module docstring line 1; imports lines 5–13; `find_script` lines 17–23; `_default_runner` lines 26–27; `__init__` lines 45–67; `_invoke` lines 120–128; `create` lines 148–152; `cleanup` lines 227–229)
  - Modify `plugins/gin-orchestrator/src/README.md` (line 21)
  - Modify `install.sh` (lines 540–545), `install.ps1` (lines 424–430)
  - Delete `plugins/gin-workflow/src/scripts/worktree-create.sh`, `plugins/gin-workflow/src/scripts/worktree-cleanup.sh`
  - Test: modify `tests/gin_orchestrator/test_contracts.py` (lines 407–471), `tests/gin_orchestrator/test_orchestrator_packaging.py` (lines 52–66), `tests/install_smoke_test.sh` (lines 370–374), `tests/install_smoke_test.ps1` (lines 132–134)
- **Interfaces consumed**: `workflow_core.ext.create_worktree`, `workflow_core.ext.cleanup_worktree` (Track 2)
- **Interfaces produced**: `WorktreeWorkspaceProvider(repository_root: Path, *, worktree_root: Path | None = None)` — the `create_script`, `cleanup_script`, and `runner` parameters are removed; `find_script` is removed.
- **Steps**:
  1. In `tests/gin_orchestrator/test_contracts.py`, replace `test_worktree_adapter_normalizes_script_results_and_replay` with:
     ```python
     def test_worktree_adapter_creates_cleans_and_replays(self):
         with tempfile.TemporaryDirectory() as directory:
             root = Path(directory).resolve()
             self._init_repo_with_commit(root)
             workspaces = WorktreeWorkspaceProvider(root)
             self.assertIs(
                 OperationStatus.INVALID,
                 workspaces.create(WorkspaceRequest("../escape", "branch"), idempotency_key="bad").status,
             )
             created = workspaces.create(
                 WorkspaceRequest("track-1", "bead/track-1"), idempotency_key="create"
             )
             replayed = workspaces.create(
                 WorkspaceRequest("track-1", "bead/track-1"), idempotency_key="create"
             )
             self.assertTrue(created.value.path.is_dir())
             self.assertTrue(replayed.idempotent)
             cleaned = workspaces.cleanup("track-1", idempotency_key="create")
             self.assertTrue(cleaned.value)
             self.assertFalse(created.value.path.exists())

     def test_worktree_adapter_reports_git_failure_as_unavailable(self):
         with tempfile.TemporaryDirectory() as directory:
             offline = WorktreeWorkspaceProvider(Path(directory))
             self.assertIs(
                 OperationStatus.UNAVAILABLE,
                 offline.create(WorkspaceRequest("track-2", "branch"), idempotency_key="fail").status,
             )
     ```
     In `test_worktree_adapter_rejects_nondefault_root_before_runner_or_side_effect`, rename it to `test_worktree_adapter_rejects_nondefault_root_without_side_effect`, delete `calls` and `runner`, construct `WorktreeWorkspaceProvider(root, worktree_root=root / ".custom/worktrees")`, and drop `self.assertEqual([], calls)`; keep the `INVALID` and the two `assertFalse(...exists())` assertions. These are the only three `runner=` uses for `WorktreeWorkspaceProvider` (lines 419, 437, 457).
  2. Delete `test_find_script_resolves_beside_the_installed_package` from `tests/gin_orchestrator/test_orchestrator_packaging.py`, and any import it alone used.
  3. Run `PYTHONPATH=plugins/gin-workflow/src/scripts:plugins/gin-orchestrator/src/scripts python3 -m unittest tests.gin_orchestrator.test_contracts` → the new tests fail (`TypeError` or wrong status, because the provider still looks for scripts).
  4. `workspace.py`:
     - Docstring: `"""Git-worktree workspace adapter over gin-workflow's worktree commands."""`
     - Imports: drop `Callable` (keep `Sequence`, used by `_git`); add `from workflow_core.ext import cleanup_worktree, create_worktree`. Delete `Runner`, `find_script`, `_default_runner`, `_invoke`.
     - `__init__`: signature `(self, repository_root: Path, *, worktree_root: Path | None = None) -> None`; delete the `create_script`, `cleanup_script`, `_runner`, and `available` lines; call `super().__init__()`.
     - `create`, replacing the `invoked = self._invoke(...)` block:
       ```python
       try:
           create_worktree(self.repository_root, request.workspace_id, request.branch, request.base_ref or None)
       except (OSError, RuntimeError, ValueError) as error:
           return ProviderResult.unavailable(f"worktree integration unavailable: {error}")
       ```
     - `cleanup`, replacing `invoked = self._invoke(...)` and its `if`:
       ```python
       try:
           cleanup_worktree(self.repository_root, workspace_id)
       except (OSError, RuntimeError, ValueError) as error:
           return ProviderResult.unavailable(f"worktree integration unavailable: {error}")
       ```
  5. Run the step-3 command → passes.
  6. `git rm plugins/gin-workflow/src/scripts/worktree-create.sh plugins/gin-workflow/src/scripts/worktree-cleanup.sh`.
  7. `install.sh`: delete the `if [ "$name" = gin-orchestrator ]; then ... fi` block (comment, loop, `cp -f`). `install.ps1`: delete the `if ($Name -eq 'gin-orchestrator') { ... }` block that copies the two scripts.
  8. `tests/install_smoke_test.sh`: replace the comment and the `for script in worktree-create.sh ...; done` loop with `assert_not_exists "$MOCK_HOME/.local/lib/gin-orchestrator/0.1/worktree-create.sh"`. `tests/install_smoke_test.ps1`: replace the `foreach ($scriptName ...) { ... }` block with `Assert-True (-not (Test-Path -LiteralPath (Join-Path $TestHome '.local/lib/gin-orchestrator/0.1/worktree-create.sh'))) 'gin-orchestrator copied worktree scripts'`.
  9. `plugins/gin-orchestrator/src/README.md` line 21: replace the paragraph with `The worker library creates and removes worktrees through \`workflow_core.ext.create_worktree\` and \`cleanup_worktree\`, the same code as \`gin-workflow worktree\`.`
  10. Run `grep -rn "worktree-create\|worktree-cleanup\|find_script" plugins/*/src docs README.md install.sh install.ps1 tests --include='*.py' --include='*.md' --include='*.sh' --include='*.ps1'` → matches only the two `assert_not_exists`/`Test-Path` lines and the `cli.md` sentence that says the command replaces the scripts.
  11. Run the full suite → passes. Run `bash tests/install_smoke_test.sh` → passes.
  12. Commit: `refactor(orchestrator): create worktrees through workflow_core, drop the shell scripts`.
- **Acceptance criteria**: gin-orchestrator contract tests create and remove a real worktree with no script installed; installs no longer copy `.sh` files (smoke test asserts it); the grep in step 10 shows no stale references.

## Integration
- **Branch**: `fix/windows-support`
- **Merge strategy**: sequential

## Validation
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all` passes
- [ ] `bash tests/install_smoke_test.sh` passes
- [ ] `grep -rn "import fcntl\|import msvcrt" plugins/*/src` matches only `workflow_core/locking.py`
- [ ] Manual, Windows 11 with no WSL (user): after `install.ps1`, run `gin-workflow state --format json`, `gin-workflow record requirement-confirmed --evidence <spec> --actor <id> --workflow-id <id>` from two shells at once, `gin-workflow routes resolve --workflow-id <id> --tracks <file> --json`, `python -c "import gin_orchestrator"` with the installed `PYTHONPATH`, and `gin-workflow worktree create t1 bead/t1` / `cleanup t1` twice — all exit 0 with no `fcntl` error; `gin-workflow worktree create ../x b` exits 1

## Notes
- Model guidance is planning metadata, not Beads state.
- Concrete providers and models are resolved during orchestration; they never belong in this plan.
- The Parent Bead `gin-workflow-eq77` stays open until the human-confirmed merge; track beads close when their tests and review pass. Items 5–7 of the epic are not delivered here: before closing the epic, split them into their own beads.

# Windows support: one file lock, Python worktree commands

Epic: gin-workflow-eq77
Status: confirmed by the user on 2026-10-28.

## Goal and scope

On Windows without WSL, every gin-workflow command that takes a file lock or creates a worktree must run. This spec covers items 1–4 of epic `gin-workflow-eq77`. It builds on branch `fix/windows-support` (8b50069), which already adds a `msvcrt` fallback to `events.py` and the `os.name == "nt"` guards in `atomic.py`.

In scope:
- Item 1: the Windows lock in `events.py` (retry loop correctness).
- Item 2: one shared file-lock implementation for every lock in the repo.
- Item 3: the `atomic.py` Windows guards (already on the branch; kept as is).
- Item 4: worktree create/cleanup without bash.

Out of scope (each gets its own bead or `/quick` after this spec):
- Item 5 (`task close` actor in team mode) and item 6 (`team check-plan` false positive).
- Item 7: the two `stage` keys stay as they are, because they sit at different levels (`stage` and `project.stage`) and gin-console reads the top-level `stage` (`gin-console/backend/src/gin_console/projects/collect.py:116`). The `record` failure message and the `orchestrate` routes wording go to a separate bead.
- Item 3, version skew: the two "2.8" copies came from installs made at different commits without a version bump. Reinstalling fixes it; a `doctor` check comparing the copies can be a later bead.
- Hook scripts `safety-check.sh` and `post-edit.sh`: on Windows, Claude Code runs hooks through Git Bash.
- `merge-integration.sh` is referenced nowhere; left untouched.

## Requirements

### R1. Shared file lock

New module `plugins/gin-workflow/src/scripts/workflow_core/locking.py` with one context manager:

```python
@contextmanager
def file_lock(path: Path, *, exclusive: bool = True) -> Iterator[None]
```

- Creates the parent directory, opens `path` in `a+b`.
- POSIX: `fcntl.flock` with `LOCK_EX` or `LOCK_SH`, blocking, then `LOCK_UN`.
- Windows (no `fcntl`): ensures the file has at least one byte, then `msvcrt.locking(fd, LK_NBLCK, 1)` on byte 0. Windows has no shared lock, so `exclusive=False` takes the exclusive lock.
  - Retries only on lock contention (`OSError` with `errno` `EACCES` or `EDEADLOCK`), sleeping 0.05 s between tries.
  - Gives up after 60 s with `TimeoutError` naming the lock file.
  - Any other `OSError` is raised at once.
  - Unlocks byte 0 with `LK_UNLCK` on exit.
- Neither `fcntl` nor `msvcrt` available: raise `OSError` saying file locking is unsupported on this platform.

Every lock in the repo uses it, and no other module imports `fcntl` or `msvcrt`:

| Caller | Today | After |
|---|---|---|
| `workflow_core/events.py::_file_lock` | own fcntl/msvcrt code | `file_lock`; still raises `EventPersistenceError` when locking is unavailable |
| `workflow_core/assignments.py::_manifest_lock` | fcntl only | `file_lock(path)` |
| `review_ledger/cli.py::_lock_stream/_unlock_stream` | own fcntl/msvcrt code | `file_lock` on the same lock path |
| `gin_orchestrator/evidence.py::_file_lock` | top-level `import fcntl` | `file_lock` imported through `workflow_core.ext` |

`workflow_core/ext.py` exports `file_lock`. Adding a name does not change `EXT_VERSION`.

### R2. Atomic writes on Windows

`workflow_core/atomic.py` keeps the branch changes: `_fsync_directory` returns early on `nt`, `fchmod` is guarded with `hasattr`, and replace/unlink retry up to 10 times on `PermissionError`. No further change.

### R3. Worktree create and cleanup in Python

New module `plugins/gin-workflow/src/scripts/workflow_core/worktrees.py`:

- `create(repo: Path, track_id: str, branch: str, base_ref: str | None = None) -> Path`
- `cleanup(repo: Path, track_id: str) -> Path | None`

Both keep the checks of the shell scripts they replace:
- `track_id` must match `^[A-Za-z0-9._-]+$`.
- The target `<repo-toplevel>/.planning/worktrees/<track_id>` must resolve inside `.planning/worktrees`.
- `create` refuses an existing target directory. Without `base_ref` it uses the current branch, or `HEAD` when detached. It runs `git worktree add -b <branch> <target> <base_ref>`.
- `cleanup` returns `None` with no error when the target does not exist; otherwise it runs `git worktree remove <target>`.
- Errors raise `ValueError` (bad input) or `RuntimeError` (git failed, with git's stderr).

Surfaces:
- CLI: `gin-workflow worktree create <track-id> <branch> [base-ref]` and `gin-workflow worktree cleanup <track-id>`. Exit 0 on success with the path printed; exit 1 with `error: <message>` on stderr otherwise.
- `workflow_core/ext.py` exports `create_worktree` and `cleanup_worktree`.
- `gin_orchestrator/workspace.py::WorktreeWorkspaceProvider` calls them directly instead of running scripts. `find_script` and the `create_script`/`cleanup_script` parameters are removed; failures keep mapping to `ProviderResult.unavailable("worktree integration unavailable: ...")`.
- Skills `gin-worktrees` and `ship` name the new commands.
- Removed: `plugins/gin-workflow/src/scripts/worktree-create.sh`, `worktree-cleanup.sh`, the copy steps in `install.sh` and `install.ps1`, their checks in `tests/install_smoke_test.sh` and `.ps1`, and the `find_script` note in `plugins/gin-orchestrator/src/README.md`.

## User Stories

### US-1: Record gates on Windows
As a developer on Windows without WSL, I want `state`, `record`, `unblock`, `task`, and `team` to run, so that I can move an epic through the lifecycle.

Acceptance criteria:
- `gin-workflow state --format json` and `gin-workflow record requirement-confirmed ...` complete on Windows with no `fcntl` error.
- Two processes recording at once both succeed, one after the other.
- A lock held longer than 60 s makes the waiting command fail with a message naming the lock file, instead of hanging.

### US-2: Resolve routes on Windows
As a developer on Windows, I want `gin-workflow routes resolve` and the review ledger to run, so that `orchestrate` and `review` work.

Acceptance criteria:
- `gin-workflow routes resolve --workflow-id <id> --tracks <file> --json` completes on Windows.
- `gin_orchestrator` imports on Windows (no top-level `fcntl`).
- `grep -rn "import fcntl\|import msvcrt" plugins/*/src` matches only `workflow_core/locking.py`.

### US-3: Create worktrees without bash
As a developer on Windows with no working `bash`, I want one command to create and remove a track worktree, so that isolated execution works the same as on Linux.

Acceptance criteria:
- `gin-workflow worktree create <track-id> <branch>` creates `.planning/worktrees/<track-id>` on a new branch.
- A track id like `../x` or `a/b` is refused with exit 1 and nothing is created.
- `gin-workflow worktree cleanup <track-id>` removes it; a second run exits 0.
- gin-orchestrator creates and removes worker worktrees with no shell script installed.

## Errors and compatibility

- POSIX behavior of every lock is unchanged: blocking, shared locks still shared.
- The new `TimeoutError` on Windows is an `OSError`; `events.py` maps it to `EventPersistenceError` like other lock failures.
- Removing the `.sh` scripts changes the skill text and the gin-orchestrator install layout. Both ship in the same release, so no compatibility shim is kept. Projects that call the scripts directly from their own docs must switch to `gin-workflow worktree`.
- `ext.py` only gains names; gin-orchestrator built against the old facade still imports.

## Testing

- `tests/workflow_core/test_locking.py`, with a stub `msvcrt` module and `fcntl` hidden:
  - contention twice, then success;
  - a non-contention `OSError` raises at once;
  - the timeout raises `TimeoutError` (patched clock);
  - the POSIX path, with two processes contending on a real lock.
- `tests/workflow_core/test_worktrees.py` on a temporary git repo: create, cleanup, cleanup again, invalid id, an existing target, the default base ref.
- Existing tests for `events`, `assignments`, the review ledger, the orchestrator `evidence` and `workspace` modules, and the install smoke tests are updated and pass: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all`.
- There is no Windows CI. The Windows proof is the user running the US-1 to US-3 acceptance commands on a Windows 11 machine with no WSL.

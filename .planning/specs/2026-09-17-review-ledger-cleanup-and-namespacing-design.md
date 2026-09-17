# Review Ledger Scoping and Stale Directory Cleanup Design

- **Date:** 2026-09-17
- **Status:** Draft (Requirement Confirmed Pending User Final Spec Review)
- **Topic:** Review Ledger Namespacing, Lifecycle Scoping, and Stale Directory Cleanup

## 1. Problem Statement

Repositories running `gin-workflow` (such as `qwikfone` and `gin-workflow`) currently accumulate dozens of stale directories named `<bead-id>` directly under `.planning/` (e.g., `qwikfone-28q/`, `qwikfone-38r/`, `gin-workflow-0qh/`).

### Root Causes
1. **Unscoped Ledger Storage:** `review_ledger/cli.py` defines ledger paths via `os.path.join(base_dir, ".planning", bead_id)`. Every review cycle creates a top-level directory directly in `.planning/` containing `review.json`, `review.md`, and `.review.lock`.
2. **Missing Post-Merge Cleanup Lifecycle:** Once a bead completes independent code review, passes verification, merges into the base branch, and closes in Beads (`bd close`), its review files remain on disk indefinitely.
3. **Leftover Lock and Empty Files:** `.review.lock` remains present in each folder even when inactive.

## 2. Goals & Non-Goals

### Goals
- **Scoped Namespace:** Move active review ledgers into `.planning/reviews/<bead-id>/`, keeping the root of `.planning/` clean (only canonical top-level directories: `plans/`, `specs/`, `codebase/`, `knowledge/`, `worktrees/`, and `reviews/`).
- **Backward Compatibility:** Seamlessly read existing review ledgers at `.planning/<bead-id>/` if present, ensuring active in-flight reviews are not disrupted.
- **Automated Lifecycle Cleanup:** Provide a reliable cleanup mechanism that purges review directories for closed/merged beads.
- **Lifecycle Integration:** Wire the cleanup into the branch delivery workflow (`finishing-a-development-branch` / `ship`) and diagnostic routines (`doctor`).
- **Repo Hygiene Command:** Provide a CLI subcommand (e.g. `review-ledger.py cleanup` or `gin-workflow cleanup`) to purge legacy stale folders across repositories (such as `~/qwikfone/.planning/` and `~/gin-workflow/.planning/`).

### Non-Goals
- Altering the review ledger event-sourced state machine (`bead_fsm`, `finding_fsm`, or `transitions`).
- Changing how durable workflow audit events (`events.jsonl`) or git commits are recorded.

## 3. Architecture & Detailed Design

### 3.1 Namespace & Ledger Path Resolution
In `plugins/gin-workflow/src/scripts/review_ledger/cli.py`:
- Update `get_ledger_paths(bead_id: str, base_dir: Optional[str] = None) -> Tuple[str, str]`:
  ```python
  if not base_dir:
      base_dir = os.getcwd()
  scoped_dir = os.path.join(base_dir, ".planning", "reviews", bead_id)
  legacy_dir = os.path.join(base_dir, ".planning", bead_id)

  # If legacy directory exists with review.json and scoped directory does not, fall back to legacy
  if not os.path.exists(scoped_dir) and os.path.exists(os.path.join(legacy_dir, "review.json")):
      target_dir = legacy_dir
  else:
      target_dir = scoped_dir

  return (
      os.path.join(target_dir, "review.json"),
      os.path.join(target_dir, "review.md")
  )
  ```
- In `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py`:
  - Update `_resolve_scope_hash(repo_path: Path)` to inspect both `planning_dir.glob("reviews/*/review.json")` and legacy `planning_dir.glob("*/review.json")`.

### 3.2 Cleanup Subcommand & Engine
Add a cleanup handler to `review_ledger` (callable as `review-ledger.py cleanup`):
- **Parameters:**
  - `--repository`: Repository root path (default: current working directory).
  - `--bead-id`: (Optional) Clean up a single specific bead directory.
  - `--all-closed`: (Optional) Scan all bead directories under `.planning/` and `.planning/reviews/` and delete those corresponding to closed beads.
  - `--dry-run`: Preview what directories will be removed without deleting.
- **Verification of Closed Status:**
  - Query Beads task tracking via task tracking provider or `bd show <bead_id> --json`.
  - A directory is eligible for removal if:
    1. Bead status in Beads is `closed` (or superseded/deferred), OR
    2. The review ledger state is `review-approved` and the associated branch has been merged into HEAD/master.
- **Cleanup Actions:**
  - Safely remove the directory (`shutil.rmtree`) including `review.json`, `review.md`, and `.review.lock`.
  - Remove empty parent `.planning/reviews/` if empty (or leave clean directory).
  - If a legacy directory `.planning/<bead-id>` is removed, report it explicitly.

### 3.3 Integration into Workflow Lifecycle Skills
1. **`finishing-a-development-branch` / `ship`**:
   - In step 5 / post-merge verification: Once the branch is merged into master and the bead is closed (`bd close <bead-id>`), execute `python3 review-ledger.py cleanup --bead-id <bead-id>` to purge its transient review folder.
2. **`setup` / `doctor`**:
   - Add a check in doctor diagnostics to identify stale or orphaned review ledger directories and suggest or execute cleanup.

## 4. Verification & Testing Strategy
1. **Unit Tests:**
   - Path resolution tests: Test that `get_ledger_paths` returns `.planning/reviews/<bead_id>/` by default.
   - Fallback test: Test that existing `.planning/<bead_id>/review.json` is preserved when already present.
   - Cleanup tests:
     - Test cleanup on an open bead fails / skips.
     - Test cleanup on a closed bead deletes `.planning/reviews/<bead_id>/` and `.planning/<bead_id>/`.
     - Test dry-run outputs actions without filesystem mutations.
2. **Integration & Packaging Tests:**
   - Run full test discovery: `python3 -m unittest discover -s tests`.
   - Run `python3 tests/test_harness_packaging.py`.
3. **End-to-End Verification on Real Repos:**
   - Dry-run cleanup on `gin-workflow` to inspect candidate legacy folders.
   - Verify that active/open beads are untouched.

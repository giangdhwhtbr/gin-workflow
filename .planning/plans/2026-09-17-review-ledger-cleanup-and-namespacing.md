# Review Ledger Scoping and Stale Directory Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SKILL: Use `executing-plans` to implement this plan. Authoritative task state is tracked via task-tracking capability (Beads); checkboxes (`- [ ]`) provide visual step breakdown.

**Goal:** Scope review ledgers under `.planning/reviews/<bead-id>/` to keep the `.planning/` root clean, maintain backward-compatible fallback for legacy in-flight review directories, and provide automated and CLI-driven cleanup of closed/merged bead review directories.

**Architecture:** Update `get_ledger_paths` in `review_ledger/cli.py` to resolve scoped paths under `.planning/reviews/<bead-id>/` with fallback to legacy `.planning/<bead-id>/`. Implement a cleanup engine with `--bead-id`, `--all-closed`, and `--dry-run` options, validating Beads task closure before deleting. Integrate cleanup into `finishing-a-development-branch` and `setup doctor` diagnostics.

**Tech Stack:** Python 3 (stdlib `os`, `shutil`, `pathlib`, `json`, `argparse`, `unittest`), Beads CLI / Task Tracking Provider.

## Global Constraints

- Never break reading of existing in-flight review ledgers located at `.planning/<bead-id>/review.json`.
- Only delete review directories for beads that are confirmed `closed` in task tracking or approved and merged in Git.
- Clean up `.review.lock` along with `review.json` and `review.md` to leave no dangling lock files.
- Do not commit or push without explicit user authorization.
- Follow TDD: write failing unit tests before implementing each change.

---

## Tasks / Tracks

### Track 1: Review Ledger Namespacing & Backward-Compatible Path Resolution

**Metadata:**
- Task ID: `gin-workflow-rl1`
- Provider role: `backend`
- Reasoning: `high`
- Model guidance: `high_reasoning`
- Dependencies: []

**Files:**
- Modify: `plugins/gin-workflow/src/scripts/review_ledger/cli.py:70-95`
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:31-48`
- Test: `tests/review_ledger/test_cli.py`
- Test: `tests/review_ledger/test_acceptance_identity.py`
- Test: `tests/review_ledger/test_integration.py`
- Test: `tests/workflow_providers/test_review_initialize.py`

**Interfaces:**
- Produces: `get_ledger_paths(bead_id: str, base_dir: Optional[str] = None) -> Tuple[str, str]` resolving to `.planning/reviews/<bead_id>/review.json` by default and falling back to `.planning/<bead_id>/review.json` when legacy ledger exists.
- Produces: `ledger_lock(bead_id: str, base_dir: Optional[str] = None)` placing `.review.lock` inside the resolved directory.

- [x] **Step 1: Write tests for scoped ledger paths and legacy fallback**

Add test cases in `tests/review_ledger/test_cli.py`:
```python
def test_get_ledger_paths_defaults_to_reviews_subfolder(self):
    from review_ledger.cli import get_ledger_paths
    json_path, md_path = get_ledger_paths("test-bead-123", self.test_dir)
    expected_json = os.path.join(self.test_dir, ".planning", "reviews", "test-bead-123", "review.json")
    expected_md = os.path.join(self.test_dir, ".planning", "reviews", "test-bead-123", "review.md")
    self.assertEqual(json_path, expected_json)
    self.assertEqual(md_path, expected_md)

def test_get_ledger_paths_falls_back_to_legacy_when_present(self):
    from review_ledger.cli import get_ledger_paths
    legacy_dir = os.path.join(self.test_dir, ".planning", "legacy-bead")
    os.makedirs(legacy_dir, exist_ok=True)
    with open(os.path.join(legacy_dir, "review.json"), "w") as f:
        f.write("{}")
    json_path, md_path = get_ledger_paths("legacy-bead", self.test_dir)
    self.assertEqual(json_path, os.path.join(legacy_dir, "review.json"))
    self.assertEqual(md_path, os.path.join(legacy_dir, "review.md"))
```

- [x] **Step 2: Run tests to verify failure**

Run: `python3 -m unittest tests/review_ledger/test_cli.py`
Expected: FAIL due to paths still resolving directly under `.planning/test-bead-123`.

- [x] **Step 3: Update `get_ledger_paths` and `ledger_lock`**

In `plugins/gin-workflow/src/scripts/review_ledger/cli.py`:
```python
def get_ledger_paths(bead_id: str, base_dir: Optional[str] = None) -> Tuple[str, str]:
    """Returns the paths to the review.json and review.md files."""
    if not base_dir:
        base_dir = os.getcwd()
    scoped_dir = os.path.join(base_dir, ".planning", "reviews", bead_id)
    legacy_dir = os.path.join(base_dir, ".planning", bead_id)
    if not os.path.exists(scoped_dir) and os.path.exists(os.path.join(legacy_dir, "review.json")):
        dir_path = legacy_dir
    else:
        dir_path = scoped_dir
    return (
        os.path.join(dir_path, "review.json"),
        os.path.join(dir_path, "review.md")
    )
```

In `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py`:
Update `_resolve_scope_hash` to search both `planning_dir.glob("reviews/*/review.json")` and `planning_dir.glob("*/review.json")`.

- [x] **Step 4: Update test fixtures expecting hardcoded path**

Update `tests/review_ledger/test_acceptance_identity.py`, `tests/review_ledger/test_cli.py`, `tests/review_ledger/test_integration.py`, and `tests/workflow_providers/test_review_initialize.py` to use `get_ledger_paths` or look under `.planning/reviews/`.

- [x] **Step 5: Run tests to verify all pass**

Run: `python3 -m unittest discover -s tests`
Expected: PASS.

---

### Track 2: Stale Review Ledger Cleanup Engine & Subcommand

**Metadata:**
- Task ID: `gin-workflow-rl2`
- Provider role: `backend`
- Reasoning: `high`
- Model guidance: `high_reasoning`
- Dependencies: [`gin-workflow-rl1`]

**Files:**
- Create: `plugins/gin-workflow/src/scripts/review_ledger/cleanup.py`
- Modify: `plugins/gin-workflow/src/scripts/review_ledger/cli.py`
- Modify: `plugins/gin-workflow/src/scripts/review-ledger.py`
- Test: `tests/review_ledger/test_cleanup.py`

**Interfaces:**
- Produces: `cleanup_review_ledgers(repo_root: Path, *, bead_id: Optional[str] = None, all_closed: bool = False, dry_run: bool = False) -> Dict[str, Any]`
- Produces: CLI subcommand `python3 review-ledger.py cleanup [--repository <path>] [--bead-id <id>] [--all-closed] [--dry-run]`

- [x] **Step 1: Write unit tests for cleanup engine**

Create `tests/review_ledger/test_cleanup.py`:
- Test cleaning up a specific closed bead: verifies directory removal (including `.review.lock`, `review.json`, `review.md`).
- Test cleaning up an open bead: verifies refusal/skip.
- Test `--dry-run`: verifies directory is not deleted and reported list matches.
- Test cleaning up legacy `.planning/<bead-id>` when closed.
- Test cleaning up `--all-closed`: iterates through all `.planning/reviews/*` and `.planning/*` candidate folders.

- [x] **Step 2: Run test to verify failure**

Run: `python3 -m unittest tests/review_ledger/test_cleanup.py`
Expected: FAIL (`cleanup` module not found).

- [x] **Step 3: Implement `cleanup.py` and register subcommand in `review-ledger.py`**

Create `plugins/gin-workflow/src/scripts/review_ledger/cleanup.py`:
- Function `is_bead_closed(bead_id: str, repo_root: Path) -> bool`:
  - First queries `bd show <bead_id> --json` (or inspects `.beads/issues.jsonl` if executable not in PATH).
  - Checks if `status == 'closed'` or review ledger shows `review-approved` and branch is merged into HEAD.
- Function `cleanup_review_ledgers(...)`:
  - Collect candidate directories from `.planning/reviews/` and legacy `.planning/<bead-id>/` (filtering out canonical directories: `plans`, `specs`, `codebase`, `knowledge`, `worktrees`, `reviews`, `research`).
  - For each eligible directory: delete directory safely with `shutil.rmtree` if not `dry_run`.
  - Return JSON summary of cleaned directories.

Register in `plugins/gin-workflow/src/scripts/review-ledger.py` and `review_ledger/cli.py`.

- [x] **Step 4: Run unit tests to verify pass**

Run: `python3 -m unittest tests/review_ledger/test_cleanup.py`
Expected: PASS.

---

### Track 3: Lifecycle Integration, Doctor Diagnostics & Documentation

**Metadata:**
- Task ID: `gin-workflow-rl3`
- Provider role: `general`
- Reasoning: `medium`
- Model guidance: `standard_impl`
- Dependencies: [`gin-workflow-rl2`]

**Files:**
- Modify: `plugins/gin-workflow/src/skills/cross-agent-code-review/SKILL.md`
- Modify: `plugins/gin-workflow/src/skills/finishing-a-development-branch/SKILL.md`
- Modify: `plugins/gin-workflow/src/commands/ship.md`
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py` (doctor orphan review check)
- Test: `tests/test_harness_packaging.py`

**Interfaces:**
- Consumes: `review-ledger.py cleanup` from Track 2.
- Produces: Automatic post-merge review ledger cleanup in `finishing-a-development-branch` / `ship`.
- Produces: Doctor diagnostics warning about stale review ledgers.

- [x] **Step 1: Write doctor diagnostic test for orphan review directories**

Add test in `tests/workflow_core/test_setup_service.py`:
- Verify that `doctor` flags stale/orphan closed bead directories in `.planning/`.

- [x] **Step 2: Update `setup_service.py` doctor check**

Add check in doctor command to scan `.planning/` and `.planning/reviews/` for stale closed bead review directories, suggesting running `python3 review-ledger.py cleanup --all-closed`.

- [x] **Step 3: Update skill documentation and execution scripts**

- In `finishing-a-development-branch/SKILL.md` and `ship.md`:
  Add post-close cleanup step:
  `python3 review-ledger.py cleanup --bead-id <bead-id>`
- In `cross-agent-code-review/SKILL.md`:
  Document that active review ledgers reside in `.planning/reviews/<bead-id>/`.

- [x] **Step 4: Run packaging and full test suite**

Run: `python3 tests/test_harness_packaging.py`
Run: `python3 -m unittest discover -s tests`
Expected: PASS.

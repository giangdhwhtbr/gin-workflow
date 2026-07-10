# Testing Patterns

**Analysis Date:** 2026-07-10
**Scope:** Full repository (`/home/gin/gin-workflow`)
**Evidence:** 
- [tests/install_smoke_test.sh](file:///home/gin/gin-workflow/tests/install_smoke_test.sh)
**Index Use:** Direct inspection was used (no repository index present).

## Test Framework

**Runner:** Custom Bash asserting harness with inline Python 3 verification helper script.
**Assertion Library:** Custom functions (`assert_exists`, `assert_not_exists`, `assert_contains`, `assert_not_contains`).

**Run Commands:**
```bash
# Run the installation smoke test suite
./tests/install_smoke_test.sh
```

## Test File Organization

**Location:** Located under the dedicated `tests/` directory at the project root.
**Naming:** `<purpose>_test.sh` format (e.g. `install_smoke_test.sh`).
**Structure:** Flat file structure containing assertion definitions and test sequences.

## Test Structure

**Suite Organization:**
```bash
# Example from tests/install_smoke_test.sh
./install.sh --platform claude --dry-run >"$output_file"

assert_contains "$output_file" "Processing plugin: gin-workflow"
assert_not_contains "$output_file" "gin-workflow-advanced"

assert_exists "plugins/gin-workflow/dist/claude-code/commands/tech-doc.md"
```

**Patterns:**
- Setup: Clears out target directories (`plugins/gin-workflow/dist/`) and initializes temporary output logging paths using `mktemp`.
- Teardown: Cleans up temporary files on exit using bash `trap 'rm -f "$output_file"' EXIT`.
- Assertion: Verifies file existence and text presence.

## Mocking

**Framework:** None.

**Patterns:**
Mocking is achieved by writing temporary environment manifests and testing their parsing correctness using inline python templates:
```python
# Example of mock hook config validation
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    data = json.load(f)
...
```

**What to Mock:** Not applicable.
**What NOT to Mock:** Run integration/smoke steps directly on target directory builds.

## Fixtures and Factories

**Test Data:** No mock factories are used. Dry-run mode outputs from `install.sh` serve as live data.

**Location:** Inline inside assertion scripts.

## Coverage

**Requirements:** None enforced.
**View Coverage:** Not applicable.

## Test Types

**Unit Tests:** None.
**Integration Tests:** Smoke testing of installation configuration mapping, plugin manifest templating, and path existence.
**E2E Tests:** None.

## Common Patterns

**Async Testing:**
- None.

**Error Testing:**
- Validation errors are triggered by passing invalid configuration arguments (e.g. `--plugin invalid`) and verifying the script returns a non-zero exit code.

---

*Testing analysis: 2026-07-10*

# Review findings — gin-workflow-t68.3

Reviewer: `reviewer:codex`
Reviewed diff: `git diff f6c0339 0b5d807` (the ledger checkpoint has the same tree as `0b5d807`).

## F-001 — IMPORTANT — Do not close a placeholder without a usable merge commit

Location: `plugins/gin-workflow/src/scripts/workflow_core/team_beads.py:134` (metadata write followed by unconditional close at line 137).
Rules: `core#validate-boundaries`, `core#errors-explicit`.

`deps()` accepts an empty `found.merge_commit`, records `merge_commit=""`, and closes the placeholder with exit 0. The new `deps_for()` then rejects it forever: the suggested `team deps` retry scans only open placeholders, so it cannot populate the missing SHA even when the host later supplies it. This concerns newly refreshed placeholders, not migration of pre-change data.

The GitLab list adapter can produce this input: `merged_with_text()` only reads `merge_commit_sha`, whereas the existing `_gitlab()` adapter also handles `squash_commit_sha`. The host boundary also explicitly permits missing commit fields. GitLab documents both SHA fields and fast-forward/squash merge methods: https://docs.gitlab.com/api/merge_requests/ and https://docs.gitlab.com/user/project/merge_requests/methods/.

Reproduced with a temporary GitLab team repository, real bd, and the existing fake glab fixture. A merged MR row supplied `merge_commit_sha: null` and `squash_commit_sha: <HEAD>`; its body named the placeholder's plan and track. Output:

```text
refresh: 0 closed t-0m5 (https://gitlab.corp.com/group/app/-/merge_requests/9)
placeholder: closed {'merge_commit': ''}
check: 1 missing t-0m5: no merge commit recorded; run team deps
retry with SHA now supplied: 0 no external placeholders
check after retry: 1 missing t-0m5: no merge commit recorded; run team deps
```

Suggested fix: resolve the integrated SHA in the host adapter (reuse its existing squash fallback), and leave the placeholder open with an explicit diagnostic if the SHA is unavailable. Store a nonempty SHA before closing. Add a regression case for missing host SHA followed by a successful retry, plus the GitLab squash response.

## Validation

- `PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest tests.workflow_core.test_team_beads tests.workflow_core.test_team_gates tests.workflow_core.test_team_init </dev/null`: 45 tests, OK, 77.033s.
- Additional in-memory checks passed: metadata-write failure prevents close; closed dependencies with absent or unknown SHA are rejected.
- The reproduction above confirms a newly closed placeholder cannot recover through the advertised refresh command.
- No implementation or test files modified. Full suite not rerun; implementer's 878-test result was not independently verified.

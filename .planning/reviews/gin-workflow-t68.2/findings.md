# Independent review: gin-workflow-t68.2

Actor: `reviewer:codex`. Reviewed diff: `2523fbd..28989d8`.
Scope: Requirement 2 and Track 2. Implementation and test files were not modified.

## R1-history — IMPORTANT

Location: `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:138`.
Rules: `core#scope`, `core#test-behavior`.

The endpoint diff does not prove that every intervening commit changed only spec artifacts. In a temporary repository, verify A, commit `src/code.py`, then `git revert --no-edit HEAD`: the gate becomes `satisfied`, although both subsequent commits changed code and Requirement 2 requires `unmet`. Check changed paths for every commit in `head..tip`, including merge changes, and cover code followed by revert with a regression test.

## R2-diff-error — IMPORTANT

Location: `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:111` and `:138`.
Rules: `core#errors-explicit`, `core#validate-boundaries`.

`_git` converts command failures to an empty string, which makes the spec-only check evaluate `all([])` as true. Reproduced: verify A, commit `src/code.py`, then `git config diff.renames invalid`. The diff exits 128 with `fatal: bad boolean config value 'invalid' for 'diff.renames'`, but the gate is `satisfied`. Preserve the exit status and reject/report failures instead of accepting them as an empty successful diff; add a failure-path regression test.

## R3-reverification — IMPORTANT

Location: `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:243`.
Rule: `core#test-behavior`.

Global event deduplication suppresses re-verification after returning to an earlier verified commit. Reproduced: verify A, commit code B, verify B, `git reset --hard A`, then verify A with the same evidence. The command exits 0, but only two verification events exist; the latest remains B and the gate stays `unmet`. Deduplicate only an identical latest verification, or give each new verification run a distinct identity. Add an A/B/A regression test.

## Validation

- `PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest tests.workflow_core.test_lifecycle_cli tests.workflow_core.test_team_gates </dev/null`: 55 tests, OK.
- `PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest tests.workflow_core.test_end_to_end </dev/null`: 7 tests, OK.
- All three findings reproduced using existing test helpers in temporary repositories; no production repository commits or configuration were changed.
- The full 870-test suite was not rerun.
- The declared empty-commit and post-ship deviations were reviewed; neither is a separate finding.

Disposition: `changes-requested`; all three findings remain open. No approval issued.

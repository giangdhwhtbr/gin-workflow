---
name: verify
description: Verify completed work against requirement, plan, and review evidence with fresh command output.
---

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`; linked worktrees have none), stop: tell the user to run `/setup` once and do nothing else. (`capabilities: {}` is a valid config.)
2. Read [references/stage-contract.md](../../references/stage-contract.md) now: it defines the gate CLI, valid evidence, approval, and git rules this stage relies on.

# Verify

**Iron law: no completion claim without fresh verification evidence.** If you have not run the command in this action, you cannot claim it passes.

Gate for every claim: identify the command that proves it → run it fully and fresh → read the whole output and exit code → state the actual result with the evidence.

## Steps

1. Require `implementation_complete`.
2. **Review approval** for each track bead:
   - `python3 review-ledger.py validate --bead-id <bead-id>` — an active, non-invalidated approval exists and every finding is terminal.
   - Source tree hashes still match the approval snapshot. Several tracks on one branch: the last track validates at HEAD; each earlier one uses `python3 review-ledger.py validate --bead-id <bead-id> --in-history`, which names the approved commit, and every later change on the branch must belong to a later approved track.
   - `python3 review-ledger.py render --bead-id <bead-id> --check` — no drift in `review.md`.
3. **Quality gates**: run `project.verify_commands` from `gin-workflow state --format json` per rigor (easy: lint, typecheck, tests; standard: + build; strict: + e2e/a11y when configured), then any manual/UI checks the plan specifies.
4. **Requirements**: re-read the confirmed spec and approved plan, make a line-by-line checklist, and verify each item against the code — not only the diff. With `project.layout: sdd`, also run `specs lint` and `specs trace` per the `gin-sdd` skill.
   With `project.team.enabled`, `verification_passed` may need a PR approval (the `gin-team` skill).
5. Record every run, failure, skipped check (say so explicitly), risk, and unavailable provider. Failures route to the `gin-debugging` skill; do not patch blindly here.

| Claim | Requires | Not sufficient |
|---|---|---|
| Tests pass | Test output with 0 failures | Earlier run, "should pass" |
| Build succeeds | Build exit 0 | Lint passing |
| Bug fixed | Original symptom test passes; red-green verified | Code changed |
| Agent completed | VCS diff checked | Agent says "success" |
| Requirements met | Checklist verified | Tests passing |
| Waiting for PR merge | Pushed branch with a real PR link | Uncommitted code |
| Track complete | Criteria, tests, and review pass | Parent merge pending |

**Stop** on "should", "probably", "seems to", satisfaction before evidence, trusting agent reports, partial checks, or a verified track left open waiting for the parent merge.

## Exit

Only when every gate has evidence: `gin-workflow record verification-passed --evidence "<commands and results>" --actor <id>`, then return `verification_passed`. Do not ship.

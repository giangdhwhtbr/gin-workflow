---
name: verify
description: Validate the implementation against the approved requirement, plan, and acceptance criteria.
---

# Verify Skill

This is the primary user-facing verification skill for `gin-workflow`.

Use it after implementation to confirm that the result satisfies the original requirement, the approved plan, and the acceptance criteria.

## Delegation

- Use `verification-before-completion` as the underlying verification contract.
- Treat `/verify` as an optional command alias only on hosts that surface plugin commands.

## Usage Standard

1. Run the relevant tests, checks, or manual validation steps.
2. Verify the result against the original requirement, not just the code diff.
3. Record failures honestly and fix them before claiming completion.
4. Identify any issues, gaps, or residual risks.
5. After verification passes, transition to `ship`.

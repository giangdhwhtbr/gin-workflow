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
2. Verify the result against the original requirement, not just the code diff. If any contradiction between the codebase and Obsidian story/decision documentation is identified, fail verification, mark the task as blocked in Beads, and send a Telegram notification.
3. Record failures honestly and fix them before claiming completion.
4. Identify any issues, gaps, or residual risks. Use the `knowledge-capture` skill to log any long-term bugs, workarounds, or risks in the Obsidian vault.
5. After running quality gates, use `telegram-notify` to send a `verification_result` notification with the pass/fail summary.
6. After verification passes, transition to `ship`.

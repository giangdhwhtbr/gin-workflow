---
name: verification-before-completion
description: Extends superpowers:verification-before-completion with the canonical bundled verification-and-handoff workflow checklist.
---

# Verification Before Completion Skill

This skill extends `superpowers:verification-before-completion` for the `gin-workflow` plugin.

## Base Skill

When `superpowers:verification-before-completion` is available, use it first as the base contract. Then apply the Gin Workflow overlay below.

If `superpowers:verification-before-completion` is unavailable, continue with this skill's self-contained rules and say that the Superpowers base skill could not be loaded.

## Gin Workflow Overlay

Gin Workflow keeps the Superpowers standards, with these plugin-specific overrides:

1. Follow [verification-and-handoff-workflow.md](file://../../references/verification-and-handoff-workflow.md) as the canonical close-out checklist.
2. **Review Approval Verification**:
   - Replay the ledger: `python3 review-ledger.py validate --bead-id <bead-id>`.
   - Verify that the active approval event exists and has not been invalidated.
   - Confirm all findings are in terminal statuses.
   - Re-compute the source tree hashes and confirm they match the snapshot recorded in the approval event.
   - Run `python3 review-ledger.py render --bead-id <bead-id> --check` to ensure no manual modifications or drift exists in `review.md`.
3. **Compilation/Build**: Confirm the application builds without errors when a build is relevant.
4. **Type Checking**: Run static type checks when they apply.
5. **Unit Tests**: Run relevant unit/integration tests to ensure no regressions.
6. **Manual Verification**: Run manual checks or UI testing instructions specified in the plan when applicable.
7. If validation is intentionally not run, record that explicitly in the handoff instead of implying success.

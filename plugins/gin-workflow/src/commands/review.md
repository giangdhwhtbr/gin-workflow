---
name: review
description: Run code review checks for an implementation checkpoint on a Bead task, using the review-ledger CLI and cross-agent-code-review skill.
---

# /gin-workflow:review Command

Use this command to execute a decoupled review pass for a bead.

## Instructions

1. Identify the bead ID to review: `python3 review-ledger.py status --bead-id <bead-id>`.
2. Verify that the bead is in `review-requested` state.
3. Use the `cross-agent-code-review` skill to acquire the lease, evaluate plan alignment, code quality, and test coverage.
4. Record findings and approval/rejection outcomes directly into the review ledger using the CLI:
   - Run: `python3 review-ledger.py start-review` to acquire the lease.
   - Run: `python3 review-ledger.py add-finding` to record issues.
   - Run: `python3 review-ledger.py approve` to record approval.
5. Re-render the review markdown: `python3 review-ledger.py render --bead-id <bead-id>`.

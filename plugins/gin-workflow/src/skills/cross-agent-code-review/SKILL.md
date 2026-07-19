---
name: cross-agent-code-review
description: Handles the reviewer execution logic for a single assigned bead, using the Git review ledger and lease system.
---

# Cross-Agent Code Review Skill

This skill guides the reviewing agent to execute code reviews.

## Reviewer Core Flow

1. **Acquire Lease**:
   - Fetch the remote review branch: `git fetch origin bead/<bead-id>`.
   - Acquire the lease: `python3 review-ledger.py start-review --bead-id <bead-id> --actor-id <reviewer-id>`.
2. **Context Gathering**:
   - Read the plan, acceptance criteria, and declared file scope from `.planning/plans/`.
   - Read the changes: `git diff origin/master...bead/<bead-id>`.
   - Validate the ledger's event log: `python3 review-ledger.py validate --bead-id <bead-id>`.
3. **Evaluation**:
   - Inspect files in scope for correctness, edge cases, error handling, security, and performance.
   - Run verification tests in an isolated environment.
4. **Record Findings**:
   - For each finding, append it to the ledger:
     `python3 review-ledger.py add-finding --bead-id <bead-id> --finding-id <finding-id> --severity <severity> --actor-id <reviewer-id> --lease-id <lease-id>`.
5. **Approve or Request Changes**:
   - If there are unresolved findings: release the lease or transition the status to changes-requested.
   - If all findings are terminal: approve the review:
     `python3 review-ledger.py approve --bead-id <bead-id> --actor-id <reviewer-id> --lease-id <lease-id>`.
   - Render and commit `review.json` and `review.md`.

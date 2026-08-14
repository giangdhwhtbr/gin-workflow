---
name: cross-agent-code-review
description: Handles the reviewer execution logic for a single assigned bead, using the Git review ledger and lease system.
---

# Cross-Agent Code Review Skill

This skill guides the reviewing agent to execute code reviews.

## Reviewer Core Flow

Before starting, enforce the configured review route. When independent review is required, the reviewer provider must differ from the implementation provider. Self-review is allowed only through the explicit `allow_self_review_fallback` policy; route exhaustion otherwise requires human decision.

1. **Acquire Lease**:
   - Fetch the remote review branch: `git fetch origin bead/<bead-id>`.
   - Acquire the lease: `python3 review-ledger.py start-review --bead-id <bead-id> --actor-id <reviewer-id>`.
2. **Context Gathering**:
   - Use only the approved scope, reviewed diff, acceptance criteria, test results, and implementation evidence supplied in the fresh review context.
   - Do not consume the implementer's private reasoning, self-assessment, parent transcript, unrelated history, or secrets.
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

Each unresolved revision gets a new stable revision identity and a fresh review cycle. Stop after the configured maximum review cycles and produce `human_decision_required`; never continue an unbounded reviewer/implementer loop.

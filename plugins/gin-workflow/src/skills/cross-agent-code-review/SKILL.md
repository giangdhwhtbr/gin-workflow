---
name: cross-agent-code-review
description: Handles the reviewer execution logic for a single assigned bead, using the Git review ledger and lease system.
---

# Cross-Agent Code Review Skill

This skill guides the reviewing agent to execute code reviews.

## Reviewer Core Flow

Before starting, enforce the configured review route. When independent review is required, the reviewer provider must differ from the implementation provider. Self-review is allowed only through the explicit `allow_self_review_fallback` policy; route exhaustion otherwise requires human decision.
Active review ledgers reside scoped under `.planning/reviews/<bead-id>/` (`review.json`, `review.md`, `.review.lock`), with backward-compatible fallback for legacy `.planning/<bead-id>/`.

1. **Acquire Lease**:
   - Fetch the remote review branch: `git fetch origin bead/<bead-id>`.
   - Acquire the lease: `python3 review-ledger.py start-review --bead-id <bead-id> --actor-id <reviewer-id>`.
   - To acquire a lease held by a different actor when authorized, pass `--force-takeover --reason "<explanation>"`.
   - If writing to the ledger fails due to lease revision staleness, the lease holder can re-sync the recorded revision using `python3 review-ledger.py resync-lease --bead-id <bead-id> --actor-id <reviewer-id> --lease-id <lease-id>`.

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
5. **Re-Review of a Claimed Fix**:
   - Verify each claimed fix against the tree before accepting it: `python3 review-ledger.py verify-finding --bead-id <bead-id> --finding-id <finding-id> --actor-id <reviewer-id> --lease-id <lease-id>`.
   - If source code was changed during the fix cycle, re-run `checkpoint` before approval to update the reviewed source tree hash: `python3 review-ledger.py checkpoint --bead-id <bead-id> --repo-id <repo-id> --commit-msg "<msg>"`.
   - If the fix is absent, incomplete, or wrong, reopen it rather than verifying it:
     `python3 review-ledger.py reopen-finding --bead-id <bead-id> --finding-id <finding-id> --reason "<why the claimed fix was rejected>" --actor-id <reviewer-id> --lease-id <lease-id>`.
   - Reopening is reviewer-only and preserves the finding's id, severity and evidence, so the ledger shows one finding that went open → fixed → open. Never verify a fix you could not confirm: `verified` is terminal, and a false one is the only way an unfixed defect reaches approval.

6. **Approve or Request Changes**:
   - If there are unresolved findings: release the lease or transition the status to changes-requested.
   - If all findings are terminal: approve the review:
     `python3 review-ledger.py approve --bead-id <bead-id> --actor-id <reviewer-id> --lease-id <lease-id>`.
   - Render and commit `review.json` and `review.md`.

Each unresolved revision gets a new stable revision identity and a fresh review cycle. Stop after the configured maximum review cycles and produce `human_decision_required`; never continue an unbounded reviewer/implementer loop.

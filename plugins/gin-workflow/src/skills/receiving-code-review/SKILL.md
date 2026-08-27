---
name: receiving-code-review
description: Extends superpowers:receiving-code-review with disposition tracking (Apply, Refute, Defer) and no-silent-dismissal rules.
---

# Receiving Code Review Skill

This skill extends `superpowers:receiving-code-review` for the `gin-workflow` plugin.

## Base Skill

When `superpowers:receiving-code-review` is available, use it first as the base contract. Then apply the Gin Workflow overlay below.

If `superpowers:receiving-code-review` is unavailable, continue with this skill's self-contained rules and say that the Superpowers base skill could not be loaded.

## Gin Workflow Overlay

Gin Workflow keeps the Superpowers standards, with these plugin-specific overrides:

1. **Triage Each Finding**:
   Load unresolved findings using `python3 review-ledger.py status --bead-id <bead-id>`. Walk each finding in severity order and choose a disposition:
   - **Apply (Fix)** — If valid and in scope, make changes in the working tree, then mark fixed: `python3 review-ledger.py fix-finding --bead-id <bead-id> --finding-id <finding-id> --actor-id <actor-id>`.
   - **Refute (Dispute)** — If wrong, run: `python3 review-ledger.py dispute-finding --bead-id <bead-id> --finding-id <finding-id> --reason "<reason>" --actor-id <actor-id>`.
   - **Defer** — If valid but out of scope, link a follow-up bead: `python3 review-ledger.py propose-deferral --bead-id <bead-id> --finding-id <finding-id> --reason "<reason>" --follow-up-bead-id <f-bead-id> --follow-up-bead-title "<title>" --actor-id <actor-id>`.
   - **Clarify** — If clarification is requested, run: `python3 review-ledger.py provide-clarification --bead-id <bead-id> --finding-id <finding-id> --clarification "<text>" --actor-id <actor-id>`.

   Mark a finding fixed **only once the change is actually in the tree**. `fix-finding` moves it to `fixed-awaiting-verification`, which is not terminal, and only a reviewer can move it back out. Marking fixed and then reverting leaves the ledger asserting something false and blocks approval until a reviewer reopens it.
2. **When the remediation falls outside the review scope**:
   `checkpoint` refuses any working-tree change outside the ledger's `included_paths` ("Unrelated working-tree changes detected outside review scope"). If a valid finding can only be fixed by touching such a file, do not revert the fix and do not re-run `init` — amend the scope instead:
   `python3 review-ledger.py change-scope --bead-id <bead-id> --reason "<why>" --add-include <path> --actor-id <actor-id>`.
   Widening scope invalidates any active approval by design: the added paths have never been reviewed, so a fresh review round is required. Prefer `change-scope` over deferring when the fix genuinely belongs to this change.
3. **No Silent Dismissal**:
   Every finding must receive an explicit status transaction in the review ledger. If undecided, default to **Apply** for critical issues and **Defer** for suggestions.
4. **Re-Verify and Checkpoint**:
   - Route the revision to the original provider/model route while it remains healthy.
   - If that route is open or unavailable, use only a same-role, same-reasoning fallback; never lower the approved reasoning tier silently.
   - Re-run local quality gates.
   - Stage and commit fixes: `python3 review-ledger.py checkpoint --bead-id <bead-id> --repo-id <repo-id> --commit-msg "feat: fix findings" --actor-id <actor-id>`.
   - Push branch and request re-review.
5. **Completing the Cycle**:
   The review cycle continues until all findings have terminal statuses (`verified`, `withdrawn`, `accepted-as-is`, `deferred-verified`, `human-waived`) and reviewer approves.
   The implementation bead must not close until review is approved, every finding is terminal, and acceptance evidence is complete. When the configured maximum cycle count is reached with unresolved findings, require a human decision.

---
name: review-response
description: Use when receiving review findings, to verify each technically and then fix, dispute, defer, or clarify it.
---

# Review Response

Verify before implementing, ask before assuming; technical correctness over social comfort. Per finding: read it fully, restate it (or ask), check it against the codebase, decide whether it is right for this codebase, respond, and implement one item at a time with a test each.

## Triage
Walk the findings in severity order; each gets an explicit answer and there is no silent dismissal. When undecided, apply critical findings and defer suggestions. Without the ledger, answer each in your report to the reviewer: fixed (where), disputed (why), deferred (follow-up bead), or a clarification.

With `project.review_ledger: true` (the `review` skill), load the open findings with `python3 review-ledger.py status --bead-id <bead-id>`; every finding gets a ledger transaction. All commands take `--bead-id <bead-id> --actor-id <id>`.
- **Fix** (valid, in scope): change the tree first, then `fix-finding --finding-id <id>`. This moves the finding to `fixed-awaiting-verification`, and only the reviewer can make it terminal. Never mark a fix you then revert.
- **Dispute** (wrong): `dispute-finding --finding-id <id> --reason "<technical reason>"`.
- **Defer** (valid, out of scope): `propose-deferral --finding-id <id> --reason "<why>" --follow-up-bead-id <id> --follow-up-bead-title "<title>"`.
  When the reviewer declines the deferral, run `withdraw-deferral --finding-id <id> --reason "<why>"` and fix the finding. An IMPORTANT deferral needs the reviewer's `require-human-decision`, then the human's `waive-finding` (accept) or `record-human-decision`; after a human decision that declines it, run `fix-finding` directly (no `withdraw-deferral`).
- **Clarify**: `provide-clarification --finding-id <id> --clarification "<text>"`.
- **Scope widening**: if a valid fix must touch a file outside the ledger's included paths, `checkpoint` refuses it ("Unrelated working-tree changes detected outside review scope"). Do not revert the fix or re-run `init`; run `change-scope --reason "<why>" --add-include <path>`. This invalidates the active approval, so a fresh review round follows. Prefer it over deferring when the fix belongs to this change.

## Judgment
- If any item is unclear, stop and ask about all unclear items before implementing any, since items may be related.
- Feedback from the user: implement once you understand it, and still ask when the scope is unclear.
- External reviewer: check whether it is correct for this stack, breaks existing behavior, ignores a reason for the current design, or fails on some platform or version, and whether the reviewer has the full context. If you cannot verify it, say what you would need. If it conflicts with the user's prior decisions, discuss it with the user first.
- YAGNI: for "implement this properly", grep for real usage; if the code is unused, propose removing it instead.
- Order: clarify first, then blocking issues (breakage, security), then simple fixes, then complex ones. Test each fix and check for regressions.
- Push back with technical reasoning, tests, or code, not defensiveness. Involve the user on architectural questions.

## Tone
No performative agreement ("You're absolutely right!", "Great point!") and no thanks. State the fix: "Fixed: <what changed> in <location>." If your pushback was wrong: "Verified: you were right because <reason>. Fixing." Then move on.

## Re-verify and checkpoint
- Route the revision to the same route as the implementation while it is healthy; otherwise use only a same-role fallback at that model and effort or higher, never a lower route.
- Re-run the tests of what changed and commit the fix (with the ledger: `checkpoint --repo-id <id> --commit-msg "fix: review findings"`, which commits on the feature branch), then request re-review.

## Completion
The cycle ends when the reviewer approves; with the ledger, every finding is also terminal (`verified`, `withdrawn`, `accepted-as-is`, `deferred-verified`, `human-waived`). The implementation bead must not close before that and before acceptance evidence is complete. After `project.max_cycles` cycles without approval, ask the user instead of retrying; with the ledger, `start-review` is refused until `record-human-decision` is written.

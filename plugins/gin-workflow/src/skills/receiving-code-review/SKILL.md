---
name: receiving-code-review
description: Evaluate code review findings with technical rigor, disposition tracking (Apply/Refute/Defer), and no-silent-dismissal rules.
---

# Receiving Code Review

## Overview

Code review requires technical evaluation, not emotional performance.

**Core principle:** Verify before implementing. Ask before assuming. Technical correctness over social comfort.

## The Response Pattern

```
WHEN receiving code review feedback:

1. READ: Complete feedback without reacting
2. UNDERSTAND: Restate requirement in own words (or ask)
3. VERIFY: Check against codebase reality
4. EVALUATE: Technically sound for THIS codebase?
5. RESPOND: Technical acknowledgment or reasoned pushback
6. IMPLEMENT: One item at a time, test each
```

## Triage Each Finding (Review Ledger)

Load unresolved findings using `python3 review-ledger.py status --bead-id <bead-id>`. Walk each finding in severity order and choose a disposition:

- **Apply (Fix)** — If valid and in scope, make changes in the working tree, then mark fixed: `python3 review-ledger.py fix-finding --bead-id <bead-id> --finding-id <finding-id> --actor-id <actor-id>`.
  *Important*: Mark a finding fixed **only once the change is actually in the tree**. `fix-finding` moves it to `fixed-awaiting-verification` (which is not terminal; only a reviewer can move it). Marking fixed and then reverting leaves the ledger asserting something false and blocks approval.
- **Refute (Dispute)** — If wrong, run: `python3 review-ledger.py dispute-finding --bead-id <bead-id> --finding-id <finding-id> --reason "<reason>" --actor-id <actor-id>`.
- **Defer** — If valid but out of scope, link a follow-up bead: `python3 review-ledger.py propose-deferral --bead-id <bead-id> --finding-id <finding-id> --reason "<reason>" --follow-up-bead-id <f-bead-id> --follow-up-bead-title "<title>" --actor-id <actor-id>`.
- **Clarify** — If clarification is requested, run: `python3 review-ledger.py provide-clarification --bead-id <bead-id> --finding-id <finding-id> --clarification "<text>" --actor-id <actor-id>`.

## Forbidden Responses

**NEVER:**
- "You're absolutely right!" (explicit instruction-file violation)
- "Great point!" / "Excellent feedback!" (performative)
- "Let me implement that now" (before verification)

**INSTEAD:**
- Restate the technical requirement
- Ask clarifying questions
- Push back with technical reasoning if wrong
- Just start working (actions > words)

## Scope Widening

When the remediation falls outside the review scope, `checkpoint` refuses any working-tree change outside the ledger's `included_paths` ("Unrelated working-tree changes detected outside review scope"). 
If a valid finding can only be fixed by touching such a file, do not revert the fix and do not re-run `init` — amend the scope instead:
`python3 review-ledger.py change-scope --bead-id <bead-id> --reason "<why>" --add-include <path> --actor-id <actor-id>`.
Widening scope invalidates any active approval by design: the added paths have never been reviewed, so a fresh review round is required. Prefer `change-scope` over deferring when the fix genuinely belongs to this change.

## No Silent Dismissal

Every finding must receive an explicit status transaction in the review ledger. If undecided, default to **Apply** for critical issues and **Defer** for suggestions.

## Handling Unclear Feedback

```
IF any item is unclear:
  STOP - do not implement anything yet
  ASK for clarification on unclear items

WHY: Items may be related. Partial understanding = wrong implementation.
```

**Example:**
```
The requester: "Fix 1-6"
You understand 1,2,3,6. Unclear on 4,5.

❌ WRONG: Implement 1,2,3,6 now, ask about 4,5 later
✅ RIGHT: "I understand items 1,2,3,6. Need clarification on 4 and 5 before proceeding."
```

## Source-Specific Handling

### From the requester
- **Trusted** - implement after understanding
- **Still ask** if scope unclear
- **No performative agreement**
- **Skip to action** or technical acknowledgment

### From External Reviewers
```
BEFORE implementing:
  1. Check: Technically correct for THIS codebase?
  2. Check: Breaks existing functionality?
  3. Check: Reason for current implementation?
  4. Check: Works on all platforms/versions?
  5. Check: Does reviewer understand full context?

IF suggestion seems wrong:
  Push back with technical reasoning

IF can't easily verify:
  Say so: "I can't verify this without [X]. Should I [investigate/ask/proceed]?"

IF conflicts with the requester's prior decisions:
  Stop and discuss with the requester first
```

**Requester's rule:** "External feedback - be skeptical, but check carefully"

## YAGNI Check for "Professional" Features

```
IF reviewer suggests "implementing properly":
  grep codebase for actual usage

  IF unused: "This endpoint isn't called. Remove it (YAGNI)?"
  IF used: Then implement properly
```

**Requester's rule:** "You and reviewer both report to me. If we don't need this feature, don't add it."

## Implementation Order

```
FOR multi-item feedback:
  1. Clarify anything unclear FIRST
  2. Then implement in this order:
     - Blocking issues (breaks, security)
     - Simple fixes (typos, imports)
     - Complex fixes (refactoring, logic)
  3. Test each fix individually
  4. Verify no regressions
```

## When To Push Back

Push back when:
- Suggestion breaks existing functionality
- Reviewer lacks full context
- Violates YAGNI (unused feature)
- Technically incorrect for this stack
- Legacy/compatibility reasons exist
- Conflicts with the requester's architectural decisions

**How to push back:**
- Use technical reasoning, not defensiveness
- Ask specific questions
- Reference working tests/code
- Involve the requester if architectural

**If you're uncomfortable pushing back out loud:** Name that tension, then tell the requester about the issue you've seen. They'll appreciate your honesty.

## Acknowledging Correct Feedback

When feedback IS correct:
```
✅ "Fixed. [Brief description of what changed]"
✅ "Good catch - [specific issue]. Fixed in [location]."
✅ [Just fix it and show in the code]

❌ "You're absolutely right!"
❌ "Great point!"
❌ "Thanks for catching that!"
❌ "Thanks for [anything]"
❌ ANY gratitude expression
```

**Why no thanks:** Actions speak. Just fix it. The code itself shows you heard the feedback.

**If you catch yourself about to write "Thanks":** DELETE IT. State the fix instead.

## Gracefully Correcting Your Pushback

If you pushed back and were wrong:
```
✅ "You were right - I checked [X] and it does [Y]. Implementing now."
✅ "Verified this and you're correct. My initial understanding was wrong because [reason]. Fixing."

❌ Long apology
❌ Defending why you pushed back
❌ Over-explaining
```

State the correction factually and move on.

## Re-Verify and Checkpoint

- Route the revision to the original provider/model route while it remains healthy.
- If that route is open or unavailable, use only a same-role, same-reasoning fallback; never lower the approved reasoning tier silently.
- Re-run local quality gates.
- Stage and commit fixes: `python3 review-ledger.py checkpoint --bead-id <bead-id> --repo-id <repo-id> --commit-msg "feat: fix findings" --actor-id <actor-id>`.
- Push branch and request re-review.

## Completing the Cycle

The review cycle continues until all findings have terminal statuses (`verified`, `withdrawn`, `accepted-as-is`, `deferred-verified`, `human-waived`) and reviewer approves.
The implementation bead must not close until review is approved, every finding is terminal, and acceptance evidence is complete. When the configured maximum cycle count is reached with unresolved findings, require a human decision.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Performative agreement | State requirement or just act |
| Blind implementation | Verify against codebase first |
| Batch without testing | One at a time, test each |
| Assuming reviewer is right | Check if breaks things |
| Avoiding pushback | Technical correctness > comfort |
| Partial implementation | Clarify all items first |
| Can't verify, proceed anyway | State limitation, ask for direction |

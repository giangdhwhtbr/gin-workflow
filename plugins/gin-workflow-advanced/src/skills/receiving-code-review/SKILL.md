---
name: receiving-code-review
description: Use this skill when receiving review feedback (from a subagent reviewer, an external PR reviewer, or a teammate) to evaluate the feedback technically before implementing it. Verify before changing; ask before assuming; push back with reasoning when the feedback is wrong.
---

# Receiving code review

Review feedback is a set of suggestions to evaluate, not orders to execute. The discipline is technical: read the feedback, restate the requirement to confirm you understood it, check the claim against the actual codebase, and only then decide whether to change the code.

Performative agreement ("you're absolutely right!", "great catch!", "thanks for the feedback!") is forbidden. It costs nothing to write, says nothing about the code, and trains the reviewer that praise is automatic regardless of whether their feedback was useful. Replace it with action: state what's actually being changed, or push back with reasoning.

## The response sequence

When review feedback arrives:

1. **Read** — read the entire feedback before reacting. Don't start drafting a response after the first item.
2. **Understand** — for each item, restate the technical requirement in your own words. If you can't, ask before continuing.
3. **Verify** — check each claim against the codebase. Does the file actually behave the way the reviewer thinks it does?
4. **Evaluate** — is the suggestion technically correct *for this codebase, this stack, this constraint set*? A pattern that's right elsewhere may be wrong here.
5. **Respond** — either state the technical fix or push back with reasoning. No emotional content.
6. **Implement** — one item at a time, test each fix individually before moving to the next.

## Forbidden phrasings

| Avoid | Use instead |
|-------|-------------|
| "You're absolutely right!" | State the fix: "Fixed: split the validation into two functions at auth.ts:42." |
| "Great point!" / "Excellent feedback!" | Just act on it. |
| "Thanks for catching that!" | Just describe what you changed. |
| "Let me implement that immediately" | Verify first; then implement. |

If you catch yourself about to write any of these, delete the line and replace it with the actual fix or the actual question.

The reason for the rule isn't politeness; it's signal. When everything gets the same response, the reviewer can't tell which feedback landed and which didn't.

## Handling unclear feedback

If any feedback item is unclear, **stop and ask before implementing anything**. Even the items you understand may depend on the items you don't.

```
Reviewer: "Fix items 1 through 6."
You understand 1, 2, 3, 6. Items 4 and 5 are unclear.

Wrong: implement 1, 2, 3, 6 now and ask about 4, 5 later.
Right: "I understand 1, 2, 3, and 6. Need clarification on 4 and 5 before
       proceeding — they may interact with the others."
```

Partial understanding usually leads to a partial implementation that has to be redone.

## Source-specific handling

### Internal reviewers (your teammate, your dispatched subagent)

Trusted. Implement after you've verified your understanding. Still ask if scope is unclear. No performative agreement; jump to action or technical acknowledgment.

### External reviewers (PR reviewers, automated tools, third parties)

Be skeptical, then verify. Run through this checklist before acting:

- Is the suggestion technically correct *for this codebase*? (Patterns differ across stacks.)
- Would the change break something currently working?
- Is there a documented or implicit reason the current implementation is the way it is?
- Will the change still work on all platforms / Python versions / Node versions / runtimes the project supports?
- Does the reviewer have full context, or are they suggesting a fix based on a partial view?

If the suggestion seems wrong, push back with technical reasoning (see "How to push back" below).

If you can't easily verify the claim ("does this work on Windows?", "does this affect customers on the legacy plan?"), say so explicitly: "I can't verify this without [environment / data / access]. Should I [investigate / ask the team / proceed with documented assumption]?"

If the suggestion conflicts with a previously locked decision (an ADR, a CONTEXT.md entry, a prior team decision), stop and surface the conflict to the user rather than overriding the prior decision unilaterally.

## YAGNI check on "implement properly" suggestions

When a reviewer suggests "implementing this properly" with database persistence, date filters, CSV export, retries, and so on:

```
Step 1: grep the codebase for actual callers of this code path.

If there are no callers:
  Reply with: "Grepped — nothing currently calls this endpoint. Remove it (YAGNI)?
  Or is there usage I'm missing?"

If there are callers and the missing functionality matters:
  Implement properly.

If there are callers but the suggested features aren't required:
  Push back: "There are callers, but they don't use [feature X]. Adding it would
  be speculative. Want me to leave it minimal?"
```

The reviewer doesn't always know what's used. You do — or you can find out in a minute.

## Implementation order for multi-item feedback

```
1. Clarify any unclear items first.
2. Then implement in this order:
   a. Blocking issues (broken functionality, security)
   b. Simple fixes (typos, missing imports, obvious refactors)
   c. Complex fixes (architectural changes, broader refactors)
3. Test each fix individually before moving to the next.
4. After all fixes, re-run the relevant verification (see :verification-before-completion).
```

Doing simple fixes first builds momentum and reduces the risk that a complex fix interacts with a typo you would have caught later.

## When to push back

Push back when:

- The suggestion would break existing tests or behavior.
- The reviewer is missing context (a constraint, a prior decision, an external requirement).
- The change violates YAGNI (the feature isn't actually needed).
- The suggestion is technically incorrect for this stack or this version.
- A legacy or compatibility constraint makes the current code intentional.
- The change would conflict with an architectural decision that's already in an ADR or CONTEXT.md.

How to push back, in this order:

1. **Restate** the reviewer's concern to confirm you understood it.
2. **Show evidence** — file/line, test output, doc reference, grep result.
3. **Propose alternative or clarify** — either what you'll do instead or a question that resolves the disagreement.

Tone is technical, not defensive. If the reviewer is right after all, you'll discover it during step 2.

## Acknowledging correct feedback

When the feedback was correct, acknowledge it factually and move on:

| Right | Wrong |
|-------|-------|
| "Fixed: split into two functions, see auth.ts:42." | "You're absolutely right!" |
| "Good catch — race condition in flush(). Now wrapped with the existing mutex." | "Excellent feedback!" |
| Just push the fix and reference the diff. | "Thanks for catching that!" |

The code itself shows you heard the feedback. Words add nothing.

## When you pushed back and were wrong

If you argued against the feedback and discover the reviewer was right after all:

```
Right: "You were right — I checked X.cfg and it does Y. Implementing now."
Right: "Verified, you're correct. My initial reading missed [specific reason]. Fixing."
Wrong: long apology
Wrong: defensive explanation of why you pushed back
Wrong: over-explaining
```

State the correction factually. Move on.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Performative agreement | State the fix or just act |
| Implementing without verifying | Check the codebase first |
| Batching multiple changes without testing | One at a time, test each |
| Trusting the reviewer reflexively | Verify against the actual code |
| Avoiding pushback to keep things smooth | Technical correctness beats social comfort |
| Implementing partial understanding | Clarify all items first |
| Proceeding when you can't verify | Say so; ask for direction |

## GitHub thread replies

When responding to inline review comments on GitHub PRs, reply *in the comment thread*, not as a top-level PR comment. The thread carries context for the next reviewer:

```bash
gh api repos/{owner}/{repo}/pulls/{pr}/comments/{id}/replies \
  -f body="<your reply>"
```

Top-level PR comments scatter the discussion and lose the thread of which file/line each reply addresses.

## Where this skill sits

| Aspect | Detail |
|--------|--------|
| Direct skill call | `:receiving-code-review` |
| Used by | external PR review feedback, `:subagent-driven-development` (when the internal reviewer surfaces issues) |
| Hands off to | the relevant fix skill (`:test-driven-development` for behavior changes, `:systematic-debugging` if the feedback reveals a bug, etc.) |
| Then | `:verification-before-completion` to confirm the fix landed |

---
name: receiving-code-review
description: How to triage code-review findings into apply / refute / defer dispositions, re-verify after fixing, and never silently dismiss a finding.
---

# Receiving Code Review Skill

This skill defines how to handle the structured findings returned by a code review (see requesting-code-review). Every finding must receive an explicit disposition — none may be silently dropped.

## Triage Each Finding

Walk the returned findings in severity order (most-severe first). For each finding, choose exactly one disposition:

1. **Apply** — The finding is valid and the fix is in scope. Make the change in the working tree now. Record what you changed so it can be re-verified.
2. **Refute** — The finding is wrong. You must state the reason: cite the behavior the code actually has, a constraint the reviewer missed, or a failure scenario that does not reproduce. A bare "won't fix" or "not an issue" is not a valid refutation. The reason must be specific enough that another reviewer could agree or disagree with it.
3. **Defer** — The finding is valid but out of scope for this track, or the fix is risky enough to warrant its own piece of work. File a follow-up bead (see the bead-worker skill) capturing the finding, its failure scenario, and the suggested fix. Deferring is not the same as dismissing — the finding is recorded as work, not lost.

## No Silent Dismissal

Each finding gets one of the three dispositions above and a recorded reason. There is no fourth "ignore" option. If you cannot decide, default to **Apply** for high-severity findings (fix now) and **Defer** for low-severity ones (file the bead). Never leave a finding without a disposition — an undispositioned finding is a silent dismissal.

## Re-Verify After Applying Fixes

After applying any fixes:

1. Re-run the verification-before-completion checks (build, type checks, unit tests) to confirm the fixes did not introduce a regression.
2. If the change is substantial, request another code-review pass focused on the fixes (requesting-code-review). A single follow-up review of just the diff of fixes is enough — do not re-review the entire change.
3. Re-verify findings you refuted only if a fix touched the same code; otherwise the refutation stands.

## Completing the Review Cycle

Once every finding has a disposition and all **Apply** fixes have been re-verified, the review cycle is complete. Record the disposition table (finding → disposition → reason / bead id) in the track summary so the orchestrator can audit it. Then proceed to finishing-a-development-branch.

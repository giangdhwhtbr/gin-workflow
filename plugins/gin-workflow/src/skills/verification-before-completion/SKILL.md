---
name: verification-before-completion
description: Use this skill before claiming a piece of work is done, fixed, or passing — and before committing, opening a PR, or handing off to the next step. Requires running the relevant verification command in this conversation and reading the actual output before any success language is used.
---

# Verification before completion

Claiming work is complete without re-running the relevant verification is not efficiency — it's an unverifiable assertion that costs the team trust the moment it turns out to be wrong. This skill enforces a small, disciplined gate: before any "it passes / it works / it's done" statement, run the proof and read the output.

## The core rule

**No completion claim without fresh verification evidence in this conversation.**

If the verification command hasn't run since your last code change, you don't know whether the claim is true. "It passed when I ran it ten minutes ago" is a guess about the present.

This skill verifies the *scope of the change* — the tests, type checks, and lint commands relevant to the files modified. The full-suite check before shipping is `:finishing-a-development-branch` Step 1's job. Don't blur the two; running the entire suite for every small change is expensive and discourages the discipline. Running the relevant subset every time is sustainable and catches the same regressions earlier.

## The gate

Before any statement that work is complete, fixed, passing, or ready:

1. **Identify** what command would prove the claim. (Usually: the test for the changed code; the linter for the touched files; the build for the affected package.)
2. **Run it fresh** — execute the full command in the current state of the working directory. Don't paraphrase. Don't summarize. Don't reuse output from earlier in the session.
3. **Read the output** — entire output, not just the last line. Note exit code, count of failures, any warnings.
4. **Compare to the claim** — does the output actually back what you're about to say?
   - If no: state the actual status with evidence ("3 of 18 tests still fail; here's the output").
   - If yes: state the claim with the supporting line from the output.
5. **Then make the claim.**

Skipping any step in that sequence isn't faster — it's just a guess phrased confidently.

## Common claims and what verifies them

| Claim | What proves it | What does NOT prove it |
|-------|----------------|------------------------|
| Tests pass | Test runner output: 0 failures | "Should pass", "they passed earlier" |
| Linter is clean | Linter output: 0 errors | "I only changed three lines" |
| Build succeeds | Build command: exit code 0 | Linter passing, types checking |
| Bug is fixed | Reproduce the original symptom — gone | "Code looks right now" |
| Regression test works | Confirmed red→green: revert fix → fails, restore fix → passes | The test ran once and passed |
| Subagent finished | Read the diff, run the verification | Subagent's report saying "DONE" |
| Requirements met | Walk the spec line by line, mark each as covered | Tests passing |

The right-hand column captures the most common slips. Linter passing doesn't prove the code compiles. A clean test run from before your last edit doesn't prove the test is still clean. A subagent's "DONE" is a claim, not evidence — confirm it by reading the diff and running the verification yourself.

## Warning signs to stop on

Anything that suggests success without freshly running the proof:

- Hedging language: "should", "probably", "seems to be", "I think it's".
- Celebration language without evidence: "Great!", "Perfect!", "All done!"
- About to commit, push, or open a PR with no verification in the recent history.
- Trusting a subagent's status field instead of looking at the actual diff.
- Relying on a partial check (a single test instead of the suite for the touched files).
- Thinking "it's tiny, just this once" — the rule has no exemptions.
- Anything that *implies* success without showing the proof.

When you catch one of these, run the verification before continuing.

## Common rationalizations

| Excuse | Reality |
|--------|---------|
| "It should work now" | Run the command. The verification takes seconds. |
| "I'm pretty confident" | Confidence is not evidence. Evidence is evidence. |
| "Just this once" | "Just this once" is the source of every silent regression. |
| "The linter passed" | The linter doesn't run the tests, the build, or the type checker. |
| "The agent reported DONE" | Verify independently. The agent didn't see the result; you can. |
| "A partial check is enough" | A partial check is a partial guess. The other half is whatever you skipped. |
| "Different wording, the rule shouldn't apply" | The rule applies to any communication that suggests completion. |

## Patterns by claim type

### Test results

Right:

```
$ pytest tests/auth/
...
====== 14 passed in 0.42s ======
```

Then, in the message, "All 14 tests in `tests/auth/` pass."

Wrong: "Tests should be passing now" — without the run.

### Regression tests for fixed bugs

Right: write the test, run it, see it fail (red); apply the fix; run again, see it pass (green); revert the fix temporarily, run again, confirm it fails (red); restore the fix, confirm green.

The red→green→red→green dance proves the test actually catches the regression. A test that has only ever passed proves nothing about whether it would catch the bug coming back.

Wrong: "I added a regression test" — without confirming the red side of the cycle.

### Build / type-check

Right:

```
$ npm run build
... vite build complete ...
$ echo $?
0
```

Then: "Build passes."

Wrong: "Linter passed, build should be fine" — the linter and build are different commands and one passing tells you nothing about the other.

### Requirement coverage

Right: open the spec or plan, walk each requirement, write down which task or file covers it, and identify gaps. State coverage with evidence.

Wrong: "All tests pass, so the requirements are met" — tests passing means *the tests pass*, not that all requirements have tests.

### Subagent handoff

Right: subagent reports DONE → orchestrator reads the diff → orchestrator runs the verifications mentioned in the task → orchestrator reports actual state with evidence.

Wrong: trust the subagent's status string and move on.

## Where this fits in the workflow

| Caller | When to run this |
|--------|------------------|
| `:executing-plans` | After each task, before marking it `completed` |
| `:subagent-driven-development` | Per task, before spec review (verifies the implementer's claim) |
| `:test-driven-development` | After GREEN, before declaring the cycle complete |
| `:systematic-debugging` | At the end of Phase 5, before Phase 6 cleanup |
| `:receiving-code-review` | After applying review feedback, before pushing |
| `:finishing-a-development-branch` | Step 1 (full-suite verify) wraps this for the whole branch |

This skill is small on purpose. Its single job is to make the gap between "looks right" and "verified" visible and consistent.

## Where this skill sits

| Aspect | Detail |
|--------|--------|
| Command entry | `/verify` |
| Direct skill call | `:verification-before-completion` |
| Reads | the change at hand (diff, touched files), the relevant test/build/lint commands |
| Writes | nothing on disk — produces evidence as part of the conversation |
| Hands off to | the calling skill, which uses the evidence to decide what to do next |
| Scope | the change at hand; not a full-project sanity check (that's `:finishing-a-development-branch` Step 1) |

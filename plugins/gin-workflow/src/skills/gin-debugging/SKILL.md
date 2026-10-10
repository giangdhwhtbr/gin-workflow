---
name: gin-debugging
description: Use for any bug, test failure, build failure, or unexpected behavior — find the root cause before fixing.
---

# Debugging

**Iron law: no fix without root-cause investigation first.** Applies to every issue, especially under time pressure or when a fix "seems obvious". Investigate read-first: observe logs, traces, and source before mutating anything; defer destructive actions until the cause is confirmed.

## 1. Root cause
1. Read the error, warnings, and full stack trace: line numbers, paths, codes.
2. Reproduce reliably with exact steps. If you cannot, gather more data; do not guess.
3. Check recent changes: `git diff`, recent commits, dependencies, config, environment.
4. Multi-component systems (CI → build → deploy, API → service → DB): instrument each boundary (data in, data out, config propagation), run once, and locate where it breaks before investigating that component.
5. Trace backward when the error is deep in the stack: find the immediate cause, ask "what called this with that value?", and keep going up to the original trigger. Fix at the source, then consider validation at the layers the bad value passed through. If manual tracing stalls, log the inputs plus a stack trace (`new Error().stack`, `traceback.print_stack()`) just before the failing operation.
6. Test pollution (a file or state appears and you don't know which test creates it): `find-polluter.sh <path-to-check> '<test-glob>'` in this skill's directory bisects the test files.

## 2. Pattern
Find similar working code and read any reference implementation completely. List every difference between working and broken, however small, plus the dependencies, config, and assumptions involved.

## 3. Hypothesis
State one hypothesis: "X is the root cause because Y". Test it with the smallest change, one variable at a time. If it is wrong, form a new hypothesis; do not stack fixes. If you don't understand something, say so and research or ask.

## 4. Fix
1. Write a failing test that reproduces the bug (a one-off script if there is no framework).
2. Make one minimal fix at the root cause. No "while I'm here" changes or bundled refactors.
3. Never swallow errors, skip or comment out failing tests, or turn the failing path into a log-only no-op to hide the symptom.
4. If the fix needs changes outside the bead or plan scope, stop and report instead of expanding scope.
5. Re-run the new test and the affected checks: the new test passes, nothing else broke, and the original symptom is gone.
6. After a failed fix, go back to step 1 with the new information. **After 3 failed fixes, stop**: new symptoms appearing in different places point at the architecture. Discuss it with the user before attempting fix #4.

**Stop and return to step 1** if you catch yourself thinking "quick fix for now", "just try X", "it's probably X", or "skip the test", if you are proposing fixes before tracing the data flow, or if you are making several changes at once. The user saying "stop guessing", "is that not happening?", or "we're stuck?" means the same.

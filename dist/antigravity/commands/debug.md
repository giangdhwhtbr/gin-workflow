---
name: debug
description: Systematically debug a reported bug or symptom by reproducing, isolating, and fixing the root cause.
---

# /debug Command

Systematically debug a reported bug or symptom. Accepts a description of the bug or symptom as args.

## Instructions

1. Use the `systematic-debugging` skill to guide the investigation: reproduce → isolate → hypothesize root cause → minimal fix → verify.
2. Pass the bug/symptom description from args into the skill as the starting point.
3. Do not mask the root cause — fix it at the source rather than hiding the symptom.
4. After applying a fix, run the `verification-before-completion` skill to confirm the fix resolves the issue without regressions.

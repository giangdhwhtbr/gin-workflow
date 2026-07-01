---
name: verification-before-completion
description: Steps and checks required to verify implementation correctness before resolving a plan.
---

# Verification Before Completion Skill

This skill ensures that all changes are thoroughly verified and verified against target behaviors before completion.

## Verification Checklist

1. **Compilation/Build**: Confirm the application builds without errors.
2. **Type Checking**: Run any static type checks (e.g. `npm run typecheck` or equivalent).
3. **Unit Tests**: Run all relevant unit/integration tests to ensure no regressions.
4. **Manual Verification**: Run manual checks or UI testing instructions specified in the plan.

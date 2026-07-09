---
name: verification-before-completion
description: Steps and checks required to verify implementation correctness before resolving a plan.
---

# Verification Before Completion Skill

This skill ensures that all changes are thoroughly verified and verified against target behaviors before completion.

## Verification Checklist

1. Follow [docs/verification-and-handoff-workflow.md](file://../../../../docs/verification-and-handoff-workflow.md) as the canonical close-out checklist.
2. **Compilation/Build**: Confirm the application builds without errors when a build is relevant.
3. **Type Checking**: Run static type checks when they apply.
4. **Unit Tests**: Run relevant unit/integration tests to ensure no regressions.
5. **Manual Verification**: Run manual checks or UI testing instructions specified in the plan when applicable.
6. If validation is intentionally not run, record that explicitly in the handoff instead of implying success.

---
name: verification-before-completion
description: Extends superpowers:verification-before-completion with the canonical bundled verification-and-handoff workflow checklist.
---

# Verification Before Completion Skill

This skill extends `superpowers:verification-before-completion` for the `gin-workflow` plugin.

## Base Skill

When `superpowers:verification-before-completion` is available, use it first as the base contract. Then apply the Gin Workflow overlay below.

If `superpowers:verification-before-completion` is unavailable, continue with this skill's self-contained rules and say that the Superpowers base skill could not be loaded.

## Gin Workflow Overlay

Gin Workflow keeps the Superpowers standards, with these plugin-specific overrides:

1. Follow [verification-and-handoff-workflow.md](file://../../references/verification-and-handoff-workflow.md) as the canonical close-out checklist.
2. **Compilation/Build**: Confirm the application builds without errors when a build is relevant.
3. **Type Checking**: Run static type checks when they apply.
4. **Unit Tests**: Run relevant unit/integration tests to ensure no regressions.
5. **Manual Verification**: Run manual checks or UI testing instructions specified in the plan when applicable.
6. If validation is intentionally not run, record that explicitly in the handoff instead of implying success.

---
name: systematic-debugging
description: Extends superpowers:systematic-debugging with local error isolation, no-masking safety rules, and validation integration.
---

# Systematic Debugging Skill

This skill extends `superpowers:systematic-debugging` for the `gin-workflow` plugin.

## Base Skill

When `superpowers:systematic-debugging` is available, use it first as the base contract. Then apply the Gin Workflow overlay below.

If `superpowers:systematic-debugging` is unavailable, continue with this skill's self-contained rules and say that the Superpowers base skill could not be loaded.

## Gin Workflow Overlay

Gin Workflow keeps the Superpowers standards, with these plugin-specific overrides:

1. **Safety Guardrail Mindset**:
   - **Read-first**: investigate and reproduce using observation (logs, trace, reading source) before mutating.
   - **Validate before mutating**: state the hypothesis and the intended minimal change before applying it.
   - **Defer destructive actions**: prefer logging and inspecting over writing, restarting, or deleting until the root cause is confirmed.
2. **Minimal Fix Rules**:
   - Apply the smallest change that addresses the root cause at its source, not the symptom.
   - Do not swallow or discard errors to hide the failure.
   - Do not comment out or skip failing tests to make a suite pass.
   - Do not suppress, log-only, or no-op a failing path to make the symptom disappear.
3. **Integration and Scope**:
   - Post-fix verification is delegated to the `verification-before-completion` skill — do not declare the bug fixed until its checklist passes.
   - If the fix would require changes beyond the declared scope of a bead/plan, stop and notify the orchestrator rather than expanding scope silently.

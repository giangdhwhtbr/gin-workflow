---
name: systematic-debugging
description: Reproduce, isolate, hypothesize root cause, apply a minimal fix, and verify — without ever masking the underlying failure.
---

# Systematic Debugging Skill

This skill guides a disciplined debugging flow: reproduce the failure, isolate the cause, hypothesize a root cause, apply a minimal fix, and verify the result. It never masks symptoms.

## Core Flow

1. **Reproduce**:
   - Establish a reliable, minimal reproduction of the bug or symptom from the description provided.
   - If reproduction fails, say so explicitly — a non-reproducible bug cannot be reliably fixed. Capture the environment/state differences and ask the user for more context rather than guessing.
2. **Isolate**:
   - Narrow the failure to the smallest scope: the failing component, function, or code path.
   - Use read-first tools (logs, inspect, trace, read source) to localize the problem before changing anything. This matches the `safety-check` guardrail mindset: read and validate before mutating.
3. **Hypothesize Root Cause**:
   - Form an explicit, testable hypothesis about why the failure occurs. State the hypothesis in the output before acting on it.
   - Prefer a single root cause over multiple speculative fixes.
4. **Minimal Fix**:
   - Apply the smallest change that addresses the root cause at its source, not the symptom.
   - Never mask root causes. Explicit rules:
     - Do not swallow or discard errors to hide the failure (no broad `try/catch` that discards the exception, no silent error return).
     - Do not comment out or skip failing tests to make a suite pass.
     - Do not suppress, log-only, or no-op a failing path to make the symptom disappear.
   - If the root cause is in code outside the current scope, stop and surface it rather than papering over it locally.
5. **Verify**:
   - Re-run the reproduction from step 1 to confirm the fix resolves it.
   - Run the `verification-before-completion` skill checklist (build, type checks, relevant tests) to confirm no regressions were introduced.
   - If verification fails, return to step 3 and revise the hypothesis — do not add a second fix on top of an unverified one.

## Safety Guardrail Mindset

- **Read-first**: investigate and confirm before mutating. Reproduce and isolate using observation, not edits.
- **Validate before mutating**: state the hypothesis and the intended minimal change before applying it. If unsure, confirm with the user.
- **Defer destructive actions**: prefer logging, inspecting, and reading over writing, restarting, or deleting until the root cause is confirmed.

## Integration

- Post-fix verification is delegated to the `verification-before-completion` skill — do not declare the bug fixed until its checklist passes.
- If the fix would require changes beyond the declared scope of a bead/plan, stop and notify the orchestrator rather than expanding scope silently.

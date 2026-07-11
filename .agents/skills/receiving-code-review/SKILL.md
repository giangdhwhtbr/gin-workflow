---
name: receiving-code-review
description: Extends superpowers:receiving-code-review with disposition tracking (Apply, Refute, Defer) and no-silent-dismissal rules.
---

# Receiving Code Review Skill

This skill extends `superpowers:receiving-code-review` for the `gin-workflow` plugin.

## Base Skill

When `superpowers:receiving-code-review` is available, use it first as the base contract. Then apply the Gin Workflow overlay below.

If `superpowers:receiving-code-review` is unavailable, continue with this skill's self-contained rules and say that the Superpowers base skill could not be loaded.

## Gin Workflow Overlay

Gin Workflow keeps the Superpowers standards, with these plugin-specific overrides:

1. **Triage Each Finding**:
   Walk the returned findings in severity order (most-severe first). For each finding, choose exactly one disposition:
   - **Apply** — The finding is valid and the fix is in scope. Make the change in the working tree now. Record what you changed so it can be re-verified.
   - **Refute** — The finding is wrong. State the specific reason citing codebase behavior or constraints. A bare "won't fix" is invalid.
   - **Defer** — The finding is valid but out of scope or risky. File a follow-up bead capturing the finding, its failure scenario, and the suggested fix.
2. **No Silent Dismissal**:
   Every finding must have an explicit disposition and reason. If undecided, default to **Apply** for high-severity issues and **Defer** for low-severity issues. Never silently dismiss.
3. **Re-Verify After Applying Fixes**:
   - Re-run `verification-before-completion` checks.
   - For substantial changes, request another code-review pass focused strictly on the diff of fixes.
4. **Completing the Review Cycle**:
   Record the disposition table (finding → disposition → reason / bead id) in the track summary/outcome notes.

---
name: requesting-code-review
description: Extends superpowers:requesting-code-review with code-reviewer subagent integration, expected structured findings, and completion rules.
---

# Requesting Code Review Skill

This skill extends `superpowers:requesting-code-review` for the `gin-workflow` plugin.

## Base Skill

When `superpowers:requesting-code-review` is available, use it first as the base contract. Then apply the Gin Workflow overlay below.

If `superpowers:requesting-code-review` is unavailable, continue with this skill's self-contained rules and say that the Superpowers base skill could not be loaded.

## Gin Workflow Overlay

Gin Workflow keeps the Superpowers standards, with these plugin-specific overrides:

1. **When to Request a Review**:
   Request a review after completing implementation passes or when substantial changes are ready.
2. **Initialization and Checkpoint**:
   - Initialize the review ledger: `python3 review-ledger.py init --bead-id <bead-id> --repo-id <repo-id> --review-ref bead/<bead-id> --base-sha <base-sha> --reviewed-sha <head-sha> --actor-id <actor-id>`.
   - Create a Git checkpoint and commit in-scope changes: `python3 review-ledger.py checkpoint --bead-id <bead-id> --repo-id <repo-id> --commit-msg "checkpoint: ready for review" --actor-id <actor-id>`.
3. **Execution and Push**:
   - Push the review branch: `git push origin bead/<bead-id>`.
   - Update Bead status to `review-requested` by submitting the transaction to the ledger and updating Beads:
     `python3 review-ledger.py transition-requested --bead-id <bead-id> --to review-requested` / `bd update <bead-id> --status open` (or appropriate state).
4. **Post-Review Process**:
   - When reviewer finishes, route findings via the `receiving-code-review` skill.

---
name: ship
description: Prepare the verified implementation for delivery and complete the final workflow steps.
---

# Ship Skill

This is the primary user-facing delivery skill for `gin-workflow`.

Use it only after implementation and verification are complete.

## Delegation

- Use `finishing-a-development-branch` as the underlying delivery contract.
- Treat `/ship` as an optional command alias only on hosts that surface plugin commands.

## Usage Standard

1. Follow the repository verification and handoff workflow before treating the work as complete.
2. Ensure the implementation is complete, tested, and ready for delivery.
3. Perform any required Beads close-out internally as part of the final delivery workflow.
4. Do not commit or push unless explicitly authorized by the active instructions or the user.

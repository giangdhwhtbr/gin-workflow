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
3. Before final delivery, use `telegram-notify` to send a `ship_ready` notification (two-way). If the user replies "ship", proceed. If "hold: reason", pause. On timeout, save state and exit gracefully.
4. Run the `knowledge-reconciliation` skill to update Obsidian user story status and MOC indexes before performing any required Beads close-out internally.
5. Do not commit or push unless explicitly authorized by the active instructions or the user.

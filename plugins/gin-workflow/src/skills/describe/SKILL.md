---
name: describe
description: Write a self-contained HTML page for a bead or epic — its graph of children, blockers, and discovered bugs beside full details, metadata, and comments — without mutating anything.
---

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the repository, stop: tell the user to run `/setup` once and do nothing else. (`capabilities: {}` is a valid config.)
2. Read [references/stage-contract.md](../../references/stage-contract.md) now: it defines the gate CLI, valid evidence, approval, and git rules this stage relies on.

# Describe

Read-only visualization of a bead or epic.

1. Scope: Identify the bead or epic ID to describe from the request. If missing, ask the user for the ID before proceeding.
2. Run `gin-workflow describe <id> [--out <path>] --format json`.
   - Exit 2: `bd` failure or unknown bead ID. Report the error and stop.
   - Exit 3: Graph exceeds the maximum node limit (300). Advise the user to describe a child bead instead and stop.
3. On success (Exit 0):
   - Report the generated HTML file path and node/edge counts.
   - Inform the user that the HTML file is self-contained, works completely offline, and can be opened in any web browser.
4. Never open a browser automatically, never modify beads or state, and never chain into another lifecycle stage.

---
name: gin-knowledge
description: Use to capture durable decisions, constraints, and lessons during work, and to reconcile project knowledge at ship.
---

# Knowledge

Knowledge lives in `.planning/knowledge/` (the configured `artifacts.knowledge`) as small Markdown records. Short facts that every session needs go in `bd remember "<fact>"`. Knowledge is looked up on demand and never copied wholesale into a stage's context.

## Capture (during execute)
1. Capture only reusable knowledge: compatibility constraints, environment limits, architectural decisions, counterintuitive APIs, and debugging lessons that will recur. Do not capture routine steps, transient worker state, private reasoning, or self-assessment.
2. Search first (`grep -ril "<topic>" .planning/knowledge`, `bd memories <keyword>`) and update an existing record instead of duplicating it.
3. Write `.planning/knowledge/<topic>.md` with **Context**, **Decision/Solution**, **Consequences**, **References** (paths, beads), and **Scope**.
4. Mention the record in the bead notes (`bd update <id> --notes`). If the knowledge location is unavailable, say so in the handoff; never work around it.

## Reconcile (during ship, after verification and before closing beads)
1. Find the records related to the task.
2. Update their status with a short evidence-backed summary and references.
3. Correct contradictions or stale statements in related decisions and indexes.
4. Close beads only after the updates are written, or after any skipped or declined update is stated in the handoff. A notification never counts as reconciliation.

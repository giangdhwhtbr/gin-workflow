# Delegation Policy

Each plan track delegates implementation through `gin-workflow routes dispatch --workflow-id <w> --task-id <id> --json`. The dispatcher yields the assigned provider, model, and effort from the assignment manifest.

Each worker receives a bounded context: track text, file scope, rules output (`gin-workflow rules --files <scope>`), worktree path, validation commands, task ID, workflow ID, and retry identity. Model names, parent conversation context, and secrets are not worker inputs.

A `gin-workflow:developer` subagent reports one status: `done`, `needs_clarification`, `failed`, or `blocked`. One task claim and one isolated worktree per worker. A requested route is never lowered; escalation only moves up.

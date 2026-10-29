# Delegation Policy

Each plan track delegates implementation through `gin-workflow routes dispatch --workflow-id <w> --task-id <id> --json`. The dispatcher yields the assigned provider, model, and effort from the assignment manifest.

Each worker receives a bounded context: track text, file scope, rules output (`gin-workflow rules --files <scope>`), worktree path, validation commands, task ID, workflow ID, and retry identity. Model names, parent conversation context, and secrets are not worker inputs.

The worker reports one status: `done`, `needs_clarification`, `failed`, or `blocked`.

Native Claude, Codex, and Antigravity adapters detect harness support through the injected native dispatch boundary. They normalize the provider-neutral request and result. The call delegates methodology to `subagent-driven-development`; the adapter must not embed TDD steps, debugging procedures, implementation recipes, planning instructions, or review instructions.

If native support is unavailable, emit `worker.unavailable` and activate the configured sequential adapter. Absence of a fallback is a normalized failure. Adapters must not import cloud SDKs, contact provider APIs directly, or launch daemon processes.

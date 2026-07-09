# Project Instructions for AI Agents

Run `bd prime` when workflow context is missing or stale.

This file is intentionally short. Use it as a pointer layer, not as a second workflow manual.

## Canonical References

- `AGENTS.md`: repo operating policy and command safety defaults
- `docs/agent-task-lifecycle.md`: canonical agent lifecycle
- `docs/orchestration-state-model.md`: canonical state ownership model
- `docs/verification-and-handoff-workflow.md`: canonical verification and handoff checklist
- `plugins/gin-workflow/src/commands/*.md` and `plugins/gin-workflow/src/skills/**/*.md`: actionable workflow behavior

## Required Defaults

- Use `bd` for durable task tracking.
- Use `bd remember` for durable project memory when needed.
- Do not commit or push unless explicitly authorized.
- Follow the verification and handoff workflow before claiming completion.

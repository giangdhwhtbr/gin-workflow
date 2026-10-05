# Project Instructions for AI Agents

Run `bd prime` when workflow context is missing or stale.

This file is intentionally short. Use it as a pointer layer, not as a second workflow manual.

## Canonical References

- `AGENTS.md`: repo operating policy and command safety defaults
- `docs/concepts/architecture.md`: components and flow diagrams
- `docs/concepts/lifecycle.md`: canonical agent lifecycle, verification, and handoff checklist
- `docs/concepts/state-model.md`: canonical state ownership model
- `docs/concepts/providers.md`: provider routing, worker context, and evidence policy
- `docs/reference/cli.md`, `docs/reference/config.md`: commands and configuration
- `plugins/gin-workflow/src/skills/**/*.md`: actionable workflow behavior (each skill is also its `/gin-workflow:<name>` slash command)

## Response Language

- Reply to the user in Vietnamese, including when they write in English. The
  language of their message is not a request to switch; only an explicit
  instruction is.
- Do not translate the things that have to stay verbatim: code, identifiers,
  file paths, commands, log and test output, commit messages, and the content
  written into tracked files. Those stay as they are, and the prose around them
  is Vietnamese.

## Required Defaults

- Use `bd` for durable task tracking.
- Use `bd remember` for durable project memory when needed.
- Commit and push freely on feature/worktree branches; never commit directly to `main`/`master`. Creating a PR, merging into the base branch, or force-pushing requires explicit user approval.
- Follow the verification and handoff workflow before claiming completion.

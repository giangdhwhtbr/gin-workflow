# Agent Instructions

Run `bd prime` at session start when Beads context is missing or stale.

This repository separates responsibilities intentionally:

- `README.md` is human-facing product and workflow documentation.
- `AGENTS.md` and `CLAUDE.md` define only repo operating policy and entry-point pointers.
- `docs/agent-task-lifecycle.md` is the canonical lifecycle spec.
- `docs/orchestration-state-model.md` is the canonical orchestration-state ownership model.
- `docs/verification-and-handoff-workflow.md` is the canonical close-out checklist.
- Plugin command and skill files under `plugins/gin-workflow/src/` contain the actionable execution rules.

## Required Defaults

- Use Beads via `bd` for durable task tracking.
- Do not create markdown TODO lists or ad hoc memory files.
- Use `bd remember` for durable project memory when needed.
- Do not commit or push unless the user or active instructions explicitly authorize it.
- Before ending work, follow `docs/verification-and-handoff-workflow.md`.

## Quick Reference

```bash
bd prime
bd ready
bd show <id>
bd update <id> --claim
bd close <id>
```

## Non-Interactive Shell Commands

Use non-interactive flags for commands that may prompt:

```bash
cp -f source dest
mv -f source dest
rm -f file
rm -rf directory
cp -rf source dest
scp -o BatchMode=yes ...
ssh -o BatchMode=yes ...
apt-get -y ...
HOMEBREW_NO_AUTO_UPDATE=1 brew ...
```

# Agent Instructions

Run `bd prime` at session start when Beads context is missing or stale.

This repository separates responsibilities intentionally:

- `README.md` is human-facing product and workflow documentation.
- `AGENTS.md` and `CLAUDE.md` define only repo operating policy and entry-point pointers.
- `docs/agent-task-lifecycle.md` is the canonical lifecycle spec.
- `docs/orchestration-state-model.md` is the canonical orchestration-state ownership model.
- `docs/setup-system.md` is the canonical setup, versioning, and migration policy.
- `docs/capability-provider-contracts.md` defines lifecycle capability boundaries.
- `docs/context-and-evidence-policy.md` defines worker context, result, review, and evidence policy.
- `docs/verification-and-handoff-workflow.md` is the canonical close-out checklist.
- Plugin command and skill files under `plugins/gin-workflow/src/` contain the actionable execution rules.

## Response Language

- Reply to the user in Vietnamese, including when they write in English. The
  language of their message is not a request to switch; only an explicit
  instruction is.
- Do not translate the things that have to stay verbatim: code, identifiers,
  file paths, commands, log and test output, commit messages, and the content
  written into tracked files. Those stay as they are, and the prose around them
  is Vietnamese.

## Required Defaults

- Use the task-tracking capability for durable task tracking; Beads remains its durable state owner in this repository.
- Do not create markdown TODO lists or ad hoc memory files.
- Use `bd remember` for durable project memory when needed.
- Do not commit or push unless the user or active instructions explicitly authorize it.
- Before ending work, follow `docs/verification-and-handoff-workflow.md`.

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

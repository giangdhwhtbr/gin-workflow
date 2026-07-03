---
name: setup
description: Use this once when starting a new project with the claude-draft plugin. Creates the `.planning/` artifact directory, seeds `STATE.md`, and optionally adds `.planning/` to `.gitignore`. Idempotent — re-running on an initialized project leaves existing files alone and only fills in what's missing.
---

# Setup — initialize `.planning/`

The plugin keeps every artifact (specs, plans, research output, codebase maps) under a single `.planning/` directory at the project root. This skill creates that directory layout and seeds `STATE.md` so the rest of the plugin has a known starting point.

Run this once when a project first picks up the plugin. After that, the directory persists across sessions and there's nothing to redo unless someone deletes it.

**Announce at start:** "Using `:setup` to initialize `.planning/`."

This skill is invoked by the `/new-project` command. Calling `:setup` directly works too.

## What it does

```
.planning/
├── STATE.md             ← seeded with step="ready", no current topic
├── specs/               ← :brainstorming output goes here
├── plans/               ← :writing-plans output goes here
├── research/            ← agent-researcher output goes here
└── codebase/            ← codebase-mapper output goes here
```

It also offers to add `.planning/` to `.gitignore`. By default `.planning/` is gitignored — teams that want to commit specs and plans can opt in by removing the entry later.

## The process

### 1. Pre-flight check

```bash
# Are we in a git repo?
git rev-parse --git-dir > /dev/null 2>&1 || {
  echo "Not in a git repo. Run 'git init' first or pass a project name."
  exit 1
}

# Has setup already run?
[ -d .planning ] && [ -f .planning/STATE.md ] && already_initialized=true
```

If `.planning/` already exists with a populated `STATE.md`, treat the run as a no-op and tell the user. Don't overwrite `STATE.md` — that would erase the current step pointer.

If `.planning/` exists but `STATE.md` is missing, fill in just `STATE.md` (idempotent recovery).

### 2. Create the directory layout

```bash
mkdir -p .planning/specs .planning/plans .planning/research .planning/codebase
```

`mkdir -p` is safe to run repeatedly — it does nothing if the directories already exist.

### 3. Seed `STATE.md`

Write this content only if `STATE.md` doesn't already exist:

```
step: ready
current_topic:
current_spec:
current_plan:
last_updated: <today's date in YYYY-MM-DDTHH:MM:SSZ>
```

`step: ready` means "no work in progress". Subsequent commands (`/discuss`, `/plan`, `/execute`, `/ship`) update the fields as they progress.

### 4. Offer to gitignore `.planning/`

```bash
# Check if .planning/ is already ignored
git check-ignore -q .planning/ 2>/dev/null
```

If it's not ignored, ask the user:

> By default the plugin gitignores `.planning/` (specs, plans, and research outputs stay local). Add it to `.gitignore`? (yes / no)

- **Yes** — append `.planning/` to `.gitignore` and commit the change with a small message.
- **No** — proceed without changes. Teams that want to commit `.planning/` for review purposes pick this.

If `.gitignore` doesn't exist yet, create it with just the `.planning/` entry.

### 5. Report

```
.planning/ ready.
  specs/    — :brainstorming will write here
  plans/    — :writing-plans will write here
  research/ — agent-researcher will write here
  codebase/ — codebase-mapper will write here

STATE.md: step=ready, no current topic.

Next: /discuss <topic>
```

## STATE.md schema

The single source of truth for "where are we in the workflow":

```
step: ready | discuss | research | plan | execute | ship | done
current_topic: <kebab-case slug, or empty>
current_spec: <path to .planning/specs/... file, or empty>
current_plan: <path to .planning/plans/... file, or empty>
last_updated: <ISO 8601 timestamp>
```

Commands read `STATE.md` to decide whether they can run, and update it after their work completes. For example:

- `/discuss` runs only when `step` is `ready` or `discuss` (otherwise warn the user that work is in progress).
- `/plan` runs only when `step` is `discuss` or `research` (a spec exists).
- `/execute` runs only when `step` is `plan` or `execute`.

Skills don't read or write `STATE.md` directly — that's the command's responsibility, per the plugin's architectural rule (skills hold content, commands manage state).

## Idempotency

Re-running `:setup` is safe:

- Existing directories are left alone (`mkdir -p`).
- Existing `STATE.md` is preserved (the current step would be lost otherwise).
- The `.gitignore` offer is repeated only if `.planning/` isn't already ignored.

The whole skill is a no-op when everything is already in place, and a partial-fill when only some pieces are missing. There's no destructive path.

## What this skill does NOT do

- It does not configure an external issue tracker. The plugin is local-first; specs and plans live in `.planning/`, not in GitHub Issues, GitLab, Linear, or Jira. (External tracker integration is deferred — see the architecture ADR.)
- It does not write `CONTEXT.md` or ADRs. Those are project-specific and authored by the team as needed.
- It does not configure triage labels. Triage workflow is not part of v0.1.0 (deferred to v0.2.0).
- It does not modify `CLAUDE.md` or `AGENTS.md`. Those files are owned by the user; if the plugin needs to register an entry, it asks before editing.

## Where this skill sits

| Aspect | Detail |
|--------|--------|
| Command entry | `/new-project [name]` |
| Direct skill call | `:setup` |
| Reads | `git` config, existing `.planning/`, `.gitignore` |
| Writes | `.planning/{specs,plans,research,codebase}/`, `.planning/STATE.md`, optionally `.gitignore` |
| Required upstream | A git repository (`git init` if needed) |
| Hands off to | the calling command, which then prompts the user to start work (`/discuss`) |
| Frequency | Once per project (idempotent if re-run) |

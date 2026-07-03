---
name: using-claude-draft
description: Use this at the start of any conversation in a project that has the claude-draft plugin installed. Enumerates the plugin's skills, commands, agents, and `.planning/` artifact contract so future invocations resolve to the right skill instead of improvising.
---

# Using the claude-draft plugin

This is the orientation skill. It tells you what's in the plugin and how the pieces connect, so when a task arrives you can pick the right skill or command without re-reading every file.

If a skill applies to the current task — even with low confidence — invoke it. Skills exist to prevent predictable failure modes; reasoning your way around them gives up that protection.

## Core principle

User instructions take priority over plugin skills. Plugin skills take priority over default behavior. If the user's `CLAUDE.md`, `AGENTS.md`, or direct instruction contradicts a skill, follow the user. The plugin is a default; the user is the source of truth.

## How to invoke a skill

In Claude Code, use the `Skill` tool. Loading the skill brings its full content into context — read it and follow it. Don't read SKILL.md files with `Read`; use the proper Skill invocation so the plugin tracks state correctly.

If a relevant skill exists, invoke it **before** any other action — including reading files, running commands, or asking clarifying questions. The skill itself often tells you how to gather information and what to ask.

## Plugin map

### Commands (10) — thin orchestrators

```
/new-project    Initialize .planning/ in a fresh repo
/discuss        Brainstorm a design for new work
/plan           Turn an approved design into a task-by-task plan
/execute        Run the plan with subagents (or inline)
/ship           Merge / open PR / clean up after the work is done
/verify         Run the verification commands relevant to a change
/debug          Systematic-debug a failing test or production bug
/quick          Bypass for trivial fixes (≤2 files, ≤30 minutes)
/progress       Read .planning/STATE.md and suggest the next step
/map-codebase   Map an existing codebase into .planning/codebase/
```

Each command is 5–15 lines of frontmatter plus 20–50 lines of orchestration. Commands read `.planning/STATE.md`, dispatch to a skill or agent, and update state. They never carry workflow content; that lives in skills.

### Skills (15) — full content

| Skill | When to invoke |
|-------|----------------|
| `:brainstorming` | Before writing any code; turns ideas into a design spec |
| `:writing-plans` | After a spec exists; turns it into bite-sized tasks |
| `:executing-plans` | Inline plan execution (no subagents) |
| `:subagent-driven-development` | Plan execution with one fresh subagent per task and two-stage review (preferred when subagents are available) |
| `:test-driven-development` | Any feature, bug fix, or behavior change — write the test first |
| `:systematic-debugging` | Any bug, failing test, or unexpected behavior — six-phase loop |
| `:verification-before-completion` | Before any "this is done" claim — run the proof |
| `:requesting-code-review` | After a task or before merge |
| `:receiving-code-review` | When review feedback arrives — verify before implementing |
| `:dispatching-parallel-agents` | Two or more independent problems that can run in parallel |
| `:using-git-worktrees` | Before executing implementation work — set up an isolated workspace |
| `:finishing-a-development-branch` | After implementation; verify suite, present merge / PR / keep / discard |
| `:writing-skills` | Authoring or editing a skill — TDD for documentation |
| `:setup` | Initialize the `.planning/` directory in a fresh project |
| `:using-claude-draft` | This skill — invoke first in any conversation |

### Agents (3) — subagent specialists

| Agent | Role |
|-------|------|
| `agent-researcher` | Researches stack, libraries, patterns, pitfalls for a topic. Spawned by `/plan` after a spec exists. Produces `.planning/research/<topic>-RESEARCH.md`. |
| `code-reviewer` | Reviews completed work against its plan and quality standards. Auto-dispatched per task by `:subagent-driven-development`. |
| `codebase-mapper` | Maps an existing codebase into `.planning/codebase/{STACK,ARCHITECTURE,...}.md`. Dispatched by `/map-codebase`, typically four mappers in parallel. |

### `.planning/` directory — single artifact home

```
.planning/
├── STATE.md                            # current step + topic pointer
├── specs/YYYY-MM-DD-<topic>-design.md  # output of :brainstorming
├── plans/YYYY-MM-DD-<feature>.md       # output of :writing-plans
├── research/<topic>-RESEARCH.md        # output of agent-researcher
└── codebase/{STACK,ARCHITECTURE,...}.md  # output of codebase-mapper
```

`.gitignore` covers `.planning/` by default. Teams who want to commit specs and plans can opt in by removing the entry.

## Skill priority when multiple apply

When more than one skill seems relevant, this is the priority order:

1. **Process skills first** — `:brainstorming` (for new work) or `:systematic-debugging` (for bugs). These determine *how* to approach the task.
2. **Implementation skills second** — `:writing-plans`, `:test-driven-development`, etc. These guide execution.

Examples:

- "Let's build feature X" → `:brainstorming` first, then on through `:writing-plans` → `:executing-plans` or `:subagent-driven-development`.
- "This test is failing" → `:systematic-debugging` first, which itself hands off to `:test-driven-development` for the regression test.
- "Implement task 3 from the plan" → directly to `:test-driven-development` or `:executing-plans` (the plan already passed through brainstorming).

## Skill flexibility

Some skills are **rigid** — TDD discipline, verification gates, the debugging six-phase loop. Follow these to the letter. Adapting them away is the failure mode they exist to prevent.

Others are **flexible** — patterns and techniques that adapt to context. The skill itself tells you which kind it is. Default to rigid for anything labeled "discipline" or that references an explicit "core rule".

## Red flags — these thoughts mean you're rationalizing

| Thought | Reality |
|---------|---------|
| "This is just a quick question" | Questions are tasks. Check skills first. |
| "I need more context before invoking a skill" | The skill check comes *before* clarifying questions. |
| "Let me explore the codebase first" | Skills tell you how to explore. Check first. |
| "I can check git/files quickly" | Files lack the conversation context. Check skills first. |
| "This doesn't need a formal skill" | If a skill exists for this, use it. |
| "I remember this skill" | Skills change. Read the current version. |
| "The skill is overkill for this case" | Simple cases become complex. The skill's overhead is small. |
| "Let me just do this one thing first" | Check before acting, every time. |
| "This feels productive" | Activity isn't progress. Skills prevent the productive-feeling waste. |
| "I know what TDD/debug/etc means" | Knowing the concept isn't using the skill. Invoke it. |

When you catch any of these, stop and invoke the relevant skill.

## Common workflow chains

**New feature, end to end:**

```
/discuss → :brainstorming → :writing-plans → :using-git-worktrees
        → :subagent-driven-development → :finishing-a-development-branch
                                       (per task: :test-driven-development +
                                        :verification-before-completion +
                                        :requesting-code-review)
```

**Bug fix:**

```
/debug → :systematic-debugging (six phases)
       → Phase 5 hands to :test-driven-development for the regression test
       → :verification-before-completion → :finishing-a-development-branch
```

**External PR feedback:**

```
:receiving-code-review → fix → :test-driven-development (if behavior changed)
                              → :verification-before-completion → push
```

**Codebase orientation in an unfamiliar repo:**

```
/map-codebase → codebase-mapper agents (parallel) → .planning/codebase/*.md
```

## Where this skill sits

This is the entry point. It has no upstream — it's invoked first in a session. Its downstream is "every other skill in the plugin", chosen based on the task. Its job is to make sure the right skill *is* chosen, instead of the agent improvising.

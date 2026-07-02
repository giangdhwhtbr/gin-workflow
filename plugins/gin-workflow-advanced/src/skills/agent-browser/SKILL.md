---
name: agent-browser
description: How to browse available agents and tools and select the right specialist for a task.
---

# Agent Browser Skill

This skill teaches how to discover the agents and tools available in the current session and decide whether to handle a task in the general loop or delegate it to a specialist.

## Browsing Available Agents

The set of available agents is declared in the plugin's installed `agents/` directory. Each agent is a Markdown file with frontmatter (`name`, `description`, `tools`) and a short guidelines body. To browse them:

1. List the plugin's `agents/` directory to see the registered specialists.
2. Read each agent's frontmatter `description` for a one-line summary of its purpose and scope.
3. Read the `tools` frontmatter field to understand which capabilities the agent is granted (e.g. `search_web`, `run_command`, `view_file`, `grep_search`, `list_dir`).

Three specialist agents are defined by this plugin:

- **agent-researcher** — Read-only investigation: requirements, patterns, references, implementation options. Tools: `view_file`, `grep_search`, `list_dir`, `search_web`. Use for fan-out research where the conclusion matters more than the file dumps.
- **code-reviewer** — Reviews code changes for correctness, quality, security, and risk. Tools: `view_file`, `grep_search`, `run_command`. Use after a change is written, before declaring it done.
- **codebase-mapper** — Analyzes project structure, modules, dependencies, and identifies the files relevant to a given task. Tools: `view_file`, `grep_search`, `list_dir`. Use at the start of a task to scope which files matter.

## Selecting the Right Specialist

Match the task shape to the agent:

- Need to investigate requirements, find patterns, or look up references without modifying anything? → **agent-researcher**.
- Need to confirm a finished change is correct, safe, and meets acceptance criteria? → **code-reviewer**.
- Need to understand a new codebase or locate which files a task touches? → **codebase-mapper**.
- Task is a focused, single-track implementation with a clear plan and known files? → general loop (no specialist needed).

## Specialist vs. General Loop

Prefer the general loop (the main conversation) when:

- The task is small and you already hold enough context to act.
- The task requires writing files, since the research/mapper agents are read-only and the reviewer is post-change.
- The task spans multiple phases (research → implement → review) and would otherwise require stitching several specialist outputs together.

Prefer a specialist when:

- The task is read-only and broad (research, mapping) and you only need the conclusion.
- The task is a well-bounded review of an existing diff.
- Parallelizing helps: a specialist can run in the background while the general loop continues other work. See [dispatching-parallel-agents](file://../dispatching-parallel-agents/SKILL.md) for coordination guidance.

## Browsing Tools

Beyond agents, this plugin ships skills (in the plugin's installed `skills/` directory) and commands. To discover what is available:

1. List the plugin's `skills/` directory for the skill catalog; each subdirectory's `SKILL.md` frontmatter `description` summarizes the skill.
2. Cross-reference sibling skills rather than duplicating their guidance — e.g. when planning, point at the `writing-plans` skill (from the `gin-workflow` core plugin) instead of restating its schema.

## Selection Rules

1. Browse agents and skills before assuming none fit — a specialist often shortens the loop.
2. Prefer read-only specialists for read-only work; reserve the general loop for writes.
3. When delegating, pass the precise question and the file paths/symbols already known so the specialist does not re-discover them.
4. When in doubt, run the general loop; escalate to a specialist only when the task shape clearly matches one.

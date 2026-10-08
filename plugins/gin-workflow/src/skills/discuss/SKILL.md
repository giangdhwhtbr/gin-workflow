---
name: discuss
description: Clarify a requirement into a confirmed design spec before any planning, tasks, or code.
---

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`; linked worktrees have none), stop: tell the user to run `/setup` once and do nothing else. (`capabilities: {}` is a valid config.)
2. Read [references/stage-contract.md](../../references/stage-contract.md) now: it defines the gate CLI, valid evidence, approval, and git rules this stage relies on.

# Discuss

Turn a requirement into a confirmed design. The user starts with an idea, not a Beads task; never ask them to run `bd` during discovery.

**Roadmap epic:** `/discuss <epic-id>` starts from `bd show <id> --json` and its roadmap entry. Stop if the id is missing, not an epic, or closed; warn if its dependencies are still open. Pass `--workflow-id <epic-id>` to every `state` and `record` call and never create another epic.

**Hard gate:** no code, scaffolding, implementation skill, plan, or Beads task until the user explicitly confirms the design. This applies to every request, however simple; a simple design can be a few sentences, but it is still presented and confirmed.

## Steps

1. **Explore context** — relevant files, docs, recent commits. If the request spans several independent subsystems, say so first and help decompose into sub-projects (each gets its own spec → plan → implementation); then discuss only the first.
2. **Clarify** — one question per message, multiple choice when possible. Cover purpose, constraints, success criteria, edge cases, risks, dependencies, and assumptions.
3. **Propose 2–3 approaches** — trade-offs, lead with your recommendation and why. Challenge assumptions that create risk. YAGNI.
4. **Present the design** in sections scaled to complexity (a few sentences up to ~300 words); confirm each section before moving on. Cover architecture, components, data flow, error handling, testing. Prefer small units with one purpose and clear interfaces; in existing code follow existing patterns and include only targeted improvements that serve the goal.
5. **Write the spec** to `.planning/specs/YYYY-MM-DD-<topic>-design.md` from `gin-workflow specs template design-spec.md` (`Epic: <id>` for a roadmap epic), with user stories from `specs template user-story.md`. Commit it on a feature branch, never on `main`/`master`.
   With `project.layout: sdd` (`gin-workflow state --format json`), steps 5–8 follow the `gin-sdd` skill instead: change folder, REQ-IDs, and `chat` or `pr` spec review.
   With `project.team.enabled`, spec review and the `requirement-confirmed` evidence follow the `gin-team` skill.
6. **Self-review the spec** and fix inline: placeholders (TBD/TODO), contradictions, scope too large for one plan, requirements readable two ways. Every user story has acceptance criteria and, with REQ-IDs, at least one `REQ:`; every new REQ has a story or a stated technical reason.
7. **User review** — "Spec written to `<path>`. Please review it and tell me about any changes before we write the implementation plan." Apply changes and repeat step 6 until the user explicitly confirms.
8. **Record** — `gin-workflow record requirement-confirmed --evidence <spec-path> --actor <user-id>`.

## Exit

Done only when the user has explicitly confirmed the summarized understanding and the gate is recorded. Return `requirement_confirmed`; the next stage is `plan`. Do not invoke it.

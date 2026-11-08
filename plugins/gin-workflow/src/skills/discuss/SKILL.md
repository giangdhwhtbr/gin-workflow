---
name: discuss
description: Clarify a requirement into a confirmed design spec before any planning, tasks, or code.
---

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`; linked worktrees have none), stop: tell the user to run `/setup` once and do nothing else. (`capabilities: {}` is a valid config.)
2. Read [references/stage-contract.md](../../references/stage-contract.md) now: it defines the gate CLI, valid evidence, approval, and git rules this stage relies on.

# Discuss

Turn a requirement into a confirmed design. The user starts with an idea, not a Beads task; never ask them to run `gin task` during discovery.

**Roadmap epic:** `/discuss <epic-id>` starts from `gin task show <id> --json`, `gin task comments <id> --json`, and its roadmap entry. Stop if the id is missing, not an epic, or closed; warn if its dependencies are still open. With comments, before any clarifying question: read the description, then each comment in `created_at` order (`author`, `created_at`, `text`); summarise the current understanding (goal, scope, what the comments changed, dependencies that shipped or changed); ask the user to confirm or correct that summary. This confirmation does not count against `project.max_questions`. Never ask which comments to keep, and never write a comment. With the markdown task backend there are no comments: say so in one sentence and continue. Pass `--workflow-id <epic-id>` to every `state` and `record` call and never create another epic.

**Hard gate:** no code, scaffolding, implementation skill, plan, or Beads task until the user explicitly confirms the design. This applies to every request, however simple; a simple design can be a few sentences, but it is still presented and confirmed.

## Steps

1. **Explore context** — send code lookups and behavior checks to `gin:agent-researcher` (locating code: weakest model at `low`; cross-module checks: middle model at `medium`; spawn natively when supported, else run `gin-orchestrator dispatch --workflow-id <topic> --task-id <topic>-scout --stage discuss --role research --model <model> --workspace . --objective "<brief>" --agent agent-researcher --json`), returning `file:line` evidence. The main session reads only the lines needed to confirm claims before writing them. If the request spans several independent subsystems, say so first and help decompose into sub-projects (each gets its own spec → plan → implementation); then discuss only the first.
2. **Clarify** — with `project.team.enabled`, read the `team` skill first: it decides which questions you ask. One question per message, multiple choice when possible. `project.max_questions` (`gin state --format json`, default 8) caps your clarifying questions in total; put a question with a sensible default into the spec as an assumption instead of asking it. At the cap, stop, say the scope is too large or unclear, and propose splitting it into smaller epics or list the remaining answers as assumptions for one review. Do not number questions against the cap (no `2/8`): it is a ceiling, not a target; ask only what changes the design.
   Cover purpose, constraints, success criteria, edge cases, risks, dependencies, and assumptions.
3. **Propose 2–3 approaches** — trade-offs, lead with your recommendation and why. Challenge assumptions that create risk. YAGNI.
4. **Present the design** in sections scaled to complexity (a few sentences up to ~300 words); confirm each section before moving on. Cover architecture, components, data flow, error handling, testing. Prefer small units with one purpose and clear interfaces; in existing code follow existing patterns and include only targeted improvements that serve the goal.
5. **Write the spec** to `.planning/specs/YYYY-MM-DD-<topic>-design.md` from `gin specs template design-spec.md` (`Epic: <id>` for a roadmap epic; when it had comments, end `## Goal and scope` with the confirmed summary and the line `Comments considered: <count>, latest <created_at of the newest comment>`), with user stories from `specs template user-story.md`. Commit it on `feat/<topic>` (create it from the base branch if needed), never on `main`/`master`.
   With `project.layout: sdd` (`gin state --format json`), steps 5–8 follow the `sdd` skill instead: change folder, REQ-IDs, and `chat` or `pr` spec review.
   In team mode, spec review and the `requirement-confirmed` evidence also follow the `team` skill. When the codebase docs folder (`.planning/codebase/`, or `docs/codebase/` with the SDD layout) has `11-GLOSSARY.md`, name business concepts with its `confirmed` English terms; add a missing term there as `proposed` and list it under the spec's assumptions.
6. **Self-review the spec** and fix inline: placeholders (TBD/TODO), contradictions, scope too large for one plan, requirements readable two ways. Every user story has acceptance criteria and, with REQ-IDs, at least one `REQ:`; every new REQ has a story or a stated technical reason. In the legacy layout, `gin specs lint --spec <path>` must print `ok`; `record requirement-confirmed` refuses the spec otherwise.
7. **User review** — "Spec written to `<path>`. Please review it and tell me about any changes before we write the implementation plan." Apply changes and repeat step 6 until the user explicitly confirms.
8. **Record** — `gin record requirement-confirmed --evidence <spec-path> --actor <user-id>`; without a roadmap epic, pass `--workflow-id <topic>` where `<topic>` is the spec's topic slug, and name it in the spec as `Workflow: <topic>` for later stages.

## Exit

Done only when the user has explicitly confirmed the summarized understanding and the gate is recorded. Return `requirement_confirmed`; the next stage is `plan`. Do not invoke it.

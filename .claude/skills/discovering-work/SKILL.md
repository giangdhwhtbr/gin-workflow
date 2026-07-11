---
name: discovering-work
description: Extends superpowers:brainstorming with requirement-focused discovery, explicit user-confirmation gating, and a strict handoff to planning.
---

# Discovering Work Skill

This skill extends `superpowers:brainstorming` for the `gin-workflow` plugin.

## Base Skill

When `superpowers:brainstorming` is available, use it first as the base discovery and discussion contract. Then apply the Gin Workflow overlay below.

If `superpowers:brainstorming` is unavailable, continue with this skill's self-contained rules and say that the Superpowers base skill could not be loaded.

## Gin Workflow Overlay

Gin Workflow keeps the Superpowers brainstorming standard, with these plugin-specific overrides:

1. Treat this skill as the entry point for Requirement Discovery / Discussion.
2. The user starts with a requirement, not a Beads task. Do not require the user to run manual `bd` commands during normal chat-driven discovery.
3. Use repository context and conversation context to understand the requirement before talking about execution.
4. Do not create the durable implementation plan in this skill.
5. Do not create, claim, or orchestrate Beads tasks in this skill.
6. The output of this phase is a summarized understanding that must be explicitly confirmed by the user.
7. Only after user confirmation should the workflow transition to `writing-plans` or `/plan`.

## Execution Rules

1. Explore the relevant repository context before asking detailed questions.
2. Ask clarifying questions until the problem, scope, constraints, and success criteria are clear.
3. Identify missing information, edge cases, risks, dependencies, and assumptions.
4. Suggest improvements, alternatives, or stronger approaches when appropriate.
5. Challenge assumptions when they create product, technical, or workflow risk.
6. Summarize the final understanding clearly and wait for explicit user confirmation.
7. Do not implement code, create worktrees, write the plan, or start orchestration from this skill.

## Exit Standard

This phase is complete only when:

1. The requirement is understood deeply enough to plan.
2. The user and agent have aligned on scope, constraints, and success criteria.
3. The final understanding has been summarized clearly.
4. The user has explicitly confirmed that understanding.
5. The next action is clearly to invoke `writing-plans` or `/plan`.

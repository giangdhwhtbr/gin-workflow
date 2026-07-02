---
name: brainstorming
description: Structured exploration of design options and trade-offs without committing to implementation.
---

# Brainstorming Skill

This skill guides structured exploration of design options and trade-offs for a topic or question. It is non-destructive by default and produces a written summary the user can feed into `/plan`.

## Core Flow

1. **Frame the Question**:
   - Restate the topic or question from the args to confirm shared understanding.
   - Identify the decisions to be made and the constraints (functional, non-functional, environmental) that bound the options.
2. **Gather Context**:
   - Use read-only analysis tools to survey the relevant code, configs, and prior decisions. Read source, inspect existing patterns, and search for precedent — do not make changes.
   - Stay non-destructive: no edits, no writes, no restarts, no state mutation. Exploration only.
3. **Enumerate Options**:
   - List two or more credible design options that could satisfy the question. Avoid a single pre-chosen answer; surface genuine alternatives.
   - For each option, capture what it entails and the assumptions it depends on.
4. **Assess Trade-offs**:
   - For each option, record pros and cons across the dimensions that matter: correctness, complexity, maintainability, performance, risk, scope/effort, and alignment with existing patterns.
   - Note explicit non-trade-offs: things that do not actually differ between options, to keep the comparison honest.
5. **Recommend a Direction**:
   - Give a recommended direction, with the reasoning tied to the trade-offs above. Mark it as a recommendation, not a commitment — the user decides.
   - If the evidence does not support a clear recommendation, say so and present the decision the user needs to make.

## Output

Produce a written summary with these sections:

- **Question**: the framed question and constraints.
- **Options**: each option with a brief description and its assumptions.
- **Trade-offs**: pros/cons per option across the relevant dimensions.
- **Recommendation**: the suggested direction and the reasoning behind it, flagged as non-binding.

## Non-destructive by Default

- Use read-only tools (Read, search, inspect, trace) for all investigation. Do not edit, write, or mutate state during brainstorming.
- If deeper validation of an option requires running something potentially mutating, stop and ask the user before proceeding.

## Next Step

- The summary is intended to be convertible into a plan. Hand off to the `writing-plans` skill (via `/plan`) as the next step once the user has chosen a direction.
- Do not start implementation during brainstorming — the output is a decision input, not a plan or code.

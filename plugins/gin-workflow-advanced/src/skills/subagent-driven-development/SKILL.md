---
name: subagent-driven-development
description: When to split work across subagents versus doing it inline, and the handoff contract between parent and child.
---

# Subagent Driven Development Skill

This skill defines when to parallelize work across subagents and when to keep it inline, and the contract that makes a subagent handoff safe. The mechanics of spawning subagents — platform detection, concurrency limits, context minimization — are covered by the dispatching-parallel-agents skill; this skill is about the decision and the contract, not the tool calls.

## When to Split Across Subagents

Split the work into subagents when:

- **The tracks are independent.** Each track's files do not overlap with the others', so two subagents cannot edit the same file and clobber each other. Independence is the hard requirement; without it, parallelism produces merge conflicts and race conditions.
- **The work is large enough to amortize the handoff cost.** Spawning a subagent, transferring context, and reintegrating its result has overhead. A task that takes a few edits is faster done inline.
- **The tracks are the units the plan already defines.** A plan with multiple tracks is the natural split — one subagent per track. Do not invent a finer split than the plan prescribes.

## When to Do It Inline

Keep the work in the parent agent when:

- **The tracks are coupled.** If finishing one track changes the code another track depends on, serialize them — do the foundation track inline, then split the dependents once the shared surface is stable.
- **The task is small or exploratory.** A single file edit, a quick fix, or a "let me see what this code does" probe belongs inline.
- **You need tight feedback.** If the next step depends on the output of the current one and you'd spend the subagent's time waiting, inline is faster.

A reasonable default: split when the plan has 2+ independent tracks with real work in each; otherwise inline.

## The Handoff Contract

Every subagent handoff follows this contract. The parent provides the assignment; the child returns a structured result.

### Parent → Child (the assignment)

The parent gives the child a scoped assignment containing:

1. **Objective**: What the child must produce, stated as a concrete outcome ("create these four skill files matching these conventions"), not a process ("work on the quality track").
2. **In-scope files**: The exact files the child may create or edit. The child must not touch files outside this list; if it needs to, it stops and reports back.
3. **Acceptance criteria**: The criteria the result must meet, copied from the plan. The child self-checks against these before returning.
4. **Conventions to match**: Pointers to reference files the child must mirror (frontmatter format, heading style, section structure). Do not paraphrase the conventions — name the files.
5. **Boundaries**: What the child must not do (no commits, no branch switches, no edits outside scope). State these explicitly.

### Child → Parent (the result)

The child returns a structured result containing:

1. **Files created/edited**: The absolute path of each file touched and whether it was created or edited.
2. **Acceptance-criteria checklist**: For each criterion, a one-line confirmation that it is met, with the evidence (e.g. "frontmatter present with name + description", "references verification-before-completion").
3. **Deviations**: Anything the child did differently from the assignment, with the reason. No deviation is silently introduced.
4. **Blockers**: Anything the child could not complete and why, so the parent can decide whether to reassign, expand scope, or finish inline.

The parent does not re-derive the result from the files — it trusts the child's report and audits it against the acceptance criteria. If the report and the files disagree, the files win and the parent corrects the discrepancy.

## Mechanics

For spawning subagents, concurrency limits, and platform-specific tooling, follow dispatching-parallel-agents. This skill only adds the decision rule above and the handoff contract; it does not duplicate the dispatch mechanics.

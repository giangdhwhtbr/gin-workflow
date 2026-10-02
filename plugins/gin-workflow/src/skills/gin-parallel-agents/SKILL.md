---
name: gin-parallel-agents
description: Use when several independent tasks or failures can be worked concurrently — one bounded agent per domain.
---

# Parallel Agents

Dispatch one agent per independent problem domain and let them work concurrently. Agents never inherit your session; you construct exactly the context they need.

## Use only when
- There are several tasks or failures with different root causes or subsystems,
- each can be understood without the others, and
- they share no state: no common files, resources, or ordering.

Do not use it for related failures (fixing one may fix the others), exploratory debugging, work that needs whole-system understanding, or agents that would edit the same files. Production-impacting parallel work or an execution-strategy change needs explicit user approval, recorded first.

## Pattern
1. **Group** the work by what it affects, and confirm each group is dependency-ready in Beads (`bd ready`).
2. **Brief each agent** with:
   - one focused goal (one test file, subsystem, or bead);
   - its dependencies;
   - an explicit file scope it may edit;
   - its validation command;
   - pointers for on-demand lookup;
   - the expected return (root cause, changes, evidence).
   Include the exact error messages and test names. Never pass your transcript, secrets, or concrete model names.
3. **Dispatch** through the harness's worker or subagent mechanism within the configured concurrency, giving each agent its own worktree (`gin-worktrees`) and one bead claim.
4. **Integrate**: read each summary, record the outcome in the bead (`bd update <id> --notes`), check for edits outside the approved scopes or conflicting changes, run the full suite, and spot-check, since agents make systematic errors.

## Example brief
```
Fix the 3 failing tests in src/agents/agent-tool-abort.test.ts:
1. "aborts tool with partial output" — expects 'interrupted at' in message
2. "mixed completed and aborted tools" — fast tool aborted instead of completed
3. "tracks pendingToolCount" — expects 3 results, gets 0
Find the root cause (timing vs real bug). Replace arbitrary timeouts with event-based waits;
do NOT just raise timeouts. Scope: that test file and test utilities only.
Validate: npm test -- agent-tool-abort. Return: root cause, changes, test output.
```
Avoid briefs that are too broad ("fix all the tests"), lack context ("fix the race"), set no scope, or ask for a vague result ("fix it").

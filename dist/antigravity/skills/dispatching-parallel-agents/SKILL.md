---
name: dispatching-parallel-agents
description: Guidelines for parallel subagent coordination and routing tasks based on platform capabilities.
---

# Dispatching Parallel Agents Skill

This skill governs how tasks are assigned to parallel workers across platforms (Claude Code vs. Antigravity CLI).

## Execution Rules

1. **Platform Detection**:
   - On **Antigravity CLI**, use the `invoke_subagent` tool with a customized prompt containing the bead's JSON config.
   - On **Claude Code**, spawn parallel runs or background sub-processes if supported, or route tasks via subagent commands.
2. **Context Minimization**:
   - Provide each subagent only with the details of the specific bead it needs to execute. Do not overload subagent memory with unrelated plans or files.
3. **Resource Control**:
   - Adhere strictly to the `--max-tracks` concurrency limit to avoid API rate-limiting or CPU exhaustion.

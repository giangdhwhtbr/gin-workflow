---
name: dispatching-parallel-agents
description: Extends superpowers:dispatching-parallel-agents with platform detection (Antigravity vs Claude Code) and concurrency control.
---

# Dispatching Parallel Agents Skill

This skill extends `superpowers:dispatching-parallel-agents` for the `gin-workflow` plugin.

## Base Skill

When `superpowers:dispatching-parallel-agents` is available, use it first as the base contract. Then apply the Gin Workflow overlay below.

If `superpowers:dispatching-parallel-agents` is unavailable, continue with this skill's self-contained rules and say that the Superpowers base skill could not be loaded.

## Gin Workflow Overlay

Gin Workflow keeps the Superpowers standards, with these plugin-specific overrides:

1. **Platform Detection**:
   - On **Antigravity CLI**, use the `invoke_subagent` tool with a customized prompt containing the bead's JSON config.
   - On **Claude Code**, spawn parallel runs or background sub-processes if supported, or route tasks via subagent commands.
2. **Context Minimization**:
   - Provide each subagent only with the details of the specific bead it needs to execute. Do not overload subagent memory with unrelated plans or files.
3. **Resource Control**:
   - Adhere strictly to the `--max-tracks` concurrency limit to avoid API rate-limiting or CPU exhaustion.

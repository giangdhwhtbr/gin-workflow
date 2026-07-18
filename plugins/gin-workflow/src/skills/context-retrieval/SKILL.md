---
name: context-retrieval
description: Fetch relevant stories, module indexes, and recent decisions from the Obsidian vault at session start.
---

# Context Retrieval Skill

Use this skill at the beginning of any agent session, specifically during the **Requirement Discovery / Discussion** phase. 

This skill guides the agent to query the Obsidian Second Brain via the `obsidian` MCP server to establish the codebase context, business logic, and past decisions before formulating a plan.

## Purpose

To prevent context fragmentation and ensure the agent inherits all tribal knowledge, design choices, and bug documentation registered in the Second Brain from past executions.

## Execution Steps

1. **Identify Key Terms**:
   Extract project names, module names, user story codes (e.g. `US_RM23`), and important technical terms from the user request or the claimed Beads task.

2. **Query the Obsidian Vault**:
   Use the `obsidian` MCP tools to search the vault:
   - Call `search_notes` with the story code (e.g. `US_RM23`) to find the main User Story note.
   - Call `search_notes` with the module name (e.g. `Returns Management`) or project name to locate the relevant MOC (Map of Content) index under `/indexes/`.
   - Call `search_notes` with technical keywords to find related decisions or lessons-learned notes.

3. **Read and Inject Content**:
   - Read the main story note using `read_note` to retrieve acceptance criteria, examples, and designs.
   - Read the corresponding project/module indexes to identify dependencies and related stories.
   - Inject the verbatim text of these notes into your local context, explicitly separating the Obsidian-retrieved details from the transient user request.

4. **Identify Gaps**:
   Compare the retrieved context with the codebase. If they conflict, make it a discussion point with the user.

---
name: map-codebase
description: Analyze project structure, modules, and dependencies to produce a read-only structural summary.
---

# /map-codebase Command

Map the structure of the current project (or a specified directory) and surface the modules, dependencies, and files relevant to a given task.

## Instructions

1. Dispatch the `codebase-mapper` specialist agent (see [codebase-mapper.md](file://../agents/codebase-mapper.md)) to perform a read-only structural analysis.
2. Pass along any scope hint the user supplied (a directory, a feature area, or a question to focus the mapping).
3. Render the agent's output as a structural summary: key modules, dependency edges, and the specific files most relevant to the task. Do not modify any files — this command is read-only and produces a summary the user can act on.

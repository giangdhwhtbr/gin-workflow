---
name: context-retrieval
description: Fetch relevant project knowledge through the configured knowledge capability.
---

# Context Retrieval Skill

Use this skill during requirement discovery to discover bounded project knowledge without binding the lifecycle to a concrete knowledge adapter.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- stage-specific `ContextManifest`
- native-harness `ApprovalDecision`

## Execution

1. Extract project names, module names, story identifiers, and technical terms from required context.
2. Use `knowledge.search` for the story, module/project index, related decisions, and relevant lessons.
3. Add only references and concise relevant facts to the manifest. Do not inject full notes, parent transcripts, private reasoning, unrelated history, or secrets.
4. Keep related symbols and tests discoverable through their configured capabilities rather than eagerly loading them.
5. Compare retrieved facts with the codebase and return contradictions to `discuss` as explicit questions.

If the provider is unavailable, record that evidence and continue with repository context; do not call a concrete fallback adapter.

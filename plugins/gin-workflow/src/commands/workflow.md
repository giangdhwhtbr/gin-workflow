---
name: workflow
description: Route current durable state to exactly one guarded lifecycle action.
---

# /workflow Command

Read durable state with `gin-workflow state --format json`, keep its routing decision and evidence, and select one next action.

Use the `workflow` skill.

Invoke at most one of `discuss`, `plan`, `orchestrate`, `execute`, `verify`, `ship`, or `progress`. Never loop, combine stages, or infer success from a prior action; a later `/workflow` re-reads state.

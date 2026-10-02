---
name: plan
description: Turn a confirmed requirement into a durable implementation plan.
---

# /plan Command

Produce a durable, git-tracked plan from a confirmed requirement: tracks, file scope, dependencies, validation intent, risks, provider role, and reasoning.

Use the `plan` skill.

Require `requirement_confirmed` first; otherwise return to `discuss`. Stop after `plan_approved`; never orchestrate in the same action.

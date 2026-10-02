---
name: tech-doc
description: Scan the codebase and write split technical documentation (stack, architecture, conventions, testing, risks).
---

# /tech-doc Command

Generate evidence-backed technical documentation for the repository or a scoped area, for onboarding, planning, and review.

Use the `tech-doc` skill.

Default target is `.planning/codebase/` (scoped: `.planning/codebase/<scope-slug>/`); write a single combined document only when explicitly requested. Prefer codegraph when `.codegraph/` exists and verify claims against files. Documentation is planning evidence, never task status; Beads stays the source of truth.

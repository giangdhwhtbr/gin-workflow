---
id: lean
tier: core
applies_to: ["**/*"]
---
- [high] `reuse-existing`: Reuse an existing helper, type, or pattern from the repository before writing a new one.
- [high] `no-new-dependency`: Add no dependency for what the standard library, the platform, an installed dependency, or a few lines already do.
- `ladder`: Prefer, in order: not building it, existing code, the standard library, a platform feature, an installed dependency, one line, then minimal new code.
- `no-speculative`: Add no abstraction, option, or extension point without a second real use; no scaffolding for later.
- `delete-first`: Prefer deleting or shrinking code to adding it; shortest correct diff.
- `root-cause`: Fix a bug once in the shared code every caller goes through, not in each caller.
- `simplified-marker`: Mark a deliberate simplification with a `simplified:` comment naming its limit and upgrade path.
- `never-cut`: Never trim validation at trust boundaries, error handling, security, accessibility, tests the plan requires, or anything requested.

## Why
- `reuse-existing`: A second copy of existing logic drifts from the first and doubles every fix.
- `no-new-dependency`: Each dependency adds supply-chain, upgrade, and licence cost for the life of the project.

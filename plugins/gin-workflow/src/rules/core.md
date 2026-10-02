---
id: core
tier: core
applies_to: ["**/*"]
---
- [critical] `scope`: Change only files in the task scope; report needed changes elsewhere instead of making them.
- [critical] `no-secrets`: Never commit secrets, tokens, or credentials; read them from the environment or a secret store.
- [high] `errors-explicit`: Handle or propagate every error; never swallow one or log-and-continue without a stated reason.
- [high] `validate-boundaries`: Validate input where it enters the system (HTTP, CLI, files, queues); trust it inside.
- [high] `test-behavior`: Test observable behavior through public interfaces, not private helpers.
- `reuse-first`: Reuse existing helpers and patterns before adding an abstraction or dependency.
- `domain-names`: Name things for what they mean in the domain; no new abbreviations.
- `one-job`: Give each function one responsibility; split it when describing it needs "and".

## Why
- `scope`: Out-of-scope edits bypass the plan and the review that approved it.
- `no-secrets`: Committed secrets leak through history even after deletion.
- `errors-explicit`: Swallowed errors turn failures into silent data corruption.

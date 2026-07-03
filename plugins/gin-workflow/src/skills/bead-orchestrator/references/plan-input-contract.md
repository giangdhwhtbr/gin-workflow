# Plan Input Contract

`/orchestrate` accepts plan markdown of this exact shape. Reject on malformed input.

---

## Required structure

```markdown
# <Plan title>             ← H1, used as epic title

## <Task title>            ← H2 = 1 bd issue
[File scope: <glob list>]  ← optional, recommended
[Risk: LOW|MEDIUM|HIGH]    ← optional, default LOW
[Depends on: <Task A>, <Task B>]  ← optional; "none" = parallel-ready

<Body markdown — implementation notes, acceptance criteria>
```

### Example

```markdown
# Refactor SDK exports

## Update SDK public API
File scope: packages/sdk/src/**, packages/sdk/index.ts
Risk: MEDIUM
Depends on: none

Remove deprecated `v1` re-exports. Update `index.ts` to export only `v2` symbols.
Acceptance: `pnpm --filter @org/sdk test` passes; no `v1` imports in apps/.

## Update app consumers
File scope: apps/dashboard/**, apps/admin/**
Risk: LOW
Depends on: Update SDK public API

Replace all `import { ... } from '@org/sdk/v1'` with the new `@org/sdk` path.
Acceptance: all apps build (`pnpm build`) without type errors.
```

---

## Rules

1. Plan MUST have at least one H2.
2. H2 titles must be unique within the plan.
3. `File scope` = comma-separated globs (e.g. `packages/sdk/**, apps/server/api/**`).
4. `Risk: HIGH` — in v1, orchestrator emits a warning only; no spike bead is created (deferred to v2).
5. `Depends on:` references are matched by H2 title (exact string match, case-sensitive).
6. Default dependency when `Depends on:` is absent = sequential (Task N depends on Task N-1).
   Override with `Depends on: none` to mark a task as parallel-ready (no predecessor dependency).
7. Body markdown becomes the bd issue description verbatim.

---

## Why this shape

- **H2 = atomic bd unit.** One heading maps to one trackable issue. Clean split between
  plan intent (H2 title) and implementation detail (body).
- **File scope = parallel safety.** Non-overlapping scopes let the orchestrator assign tasks
  to independent execution lanes (tracks) without git conflicts.
- **Risk metadata = reserved for v2 spike beads.** Captured now so plans round-trip cleanly
  when v2 activates HIGH-risk handling (see spec §15).
- **Sequential default = safe baseline.** Plans without explicit `Depends on:` still execute
  correctly — each task waits for the previous before starting.
- **Body is the source-of-truth.** Goes verbatim into `bd update <bid> --description` so the
  issue tracker holds the complete implementation spec without duplication.

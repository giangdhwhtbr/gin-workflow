# Plan: {title}

## Objective
{What success looks like}

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `brainstorm`: `high_reasoning`
  - `design`: `high_reasoning`
  - `plan`: `standard_impl`
  - `implement`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: Use `high_reasoning` for planning only when execution boundaries, dependency sequencing, or major tradeoffs are still unresolved.

## Requirement Analysis
- Problem statement: ...
- Success criteria: ...
- Constraints: ...
- Non-goals: ...

## Approach Options
### Option 1: {name}
- Summary: ...
- Pros: ...
- Cons: ...

### Option 2: {name}
- Summary: ...
- Pros: ...
- Cons: ...

### Recommended Approach
- Selected option: ...
- Reasoning: ...

## Scope
- In scope: ...
- Out of scope: ...

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Concrete reason for the selected mode
```

- Valid pairings are only `direct` with `workers.mode: sequential`, and `worker` with `workers.mode: parallel`.
- Use `direct` / `sequential` for sequential work, explicitly one-agent work, work with three or fewer tasks, or work without a qualifying worker condition.
- Use `worker` / `parallel` only for more than three independent parallel tasks, long-running work, specialized work, or an independent review.
- `workers.mode` declares scheduling behavior only. It never contains provider model names, commands, credentials, or implementation methodology.

## Tasks
### Track 1: {name}
- **Dependencies**: none | Track N
- **Files**: list of files to modify
- **Provider role**: `backend`
- **Reasoning**: `low` | `medium` | `high`
- **Acceptance criteria**: ...
- **Estimated complexity**: low | medium | high

### Track 2: {name}
...

## Integration
- **Branch**: {integration-branch-name}
- **Merge strategy**: sequential | parallel-then-merge

## Validation
- [ ] All tests pass
- [ ] Type checks clean
- [ ] Manual verification steps

## Notes
- Model guidance is planning metadata, not Beads state.
- If omitted, agents should assume `standard_impl`.
- Use provider-neutral model classes only; do not name vendor-specific models in the plan schema.
- Every implementation or review track must declare a portable provider role and reasoning tier.
- Select `low` for mechanical edits, simple documentation, or predictable boilerplate.
- Select `medium` for normal implementation with clear requirements and bounded design.
- Select `high` for complex architecture, security, migration, or concurrency work, or other unusually constrained tasks.
- Provider roles describe responsibility rather than filename patterns. The user may override role or reasoning before plan approval.
- Concrete providers and models are resolved from machine-local configuration during orchestration; they never belong in the portable plan.
- Deliverable merge-holds (e.g. "remain open until human-confirmed merge") apply exclusively to the Parent Bead. Individual track beads must close upon passing tests and code review to unblock downstream dependent tracks.
